#!/usr/bin/env python3
"""
Poll danse2 mailbox for prompts, run local LLMs, and post suggestions back.

Example:
  python scripts/llm_danse2_watcher.py \
    --mailbox-url https://example.org/tasai_mailbox \
    --token YOUR_TOKEN \
    --interval 60 \
    --max-points 3 \
    --codex-model gpt-5.2-codex
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import shutil
import socket
import time
from typing import Dict, List, Sequence

import urllib.request
import subprocess

PROMPT_PREFIX = "prompt_batch"
SUGGEST_PREFIX = "suggestions_batch"
USE_CURL = True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
socket.setdefaulttimeout(20)


def http_get(url: str, token: str, log_request: bool = False) -> Dict | None:
    if USE_CURL:
        try:
            if log_request:
                logging.info("GET %s", url)
            proc = subprocess.run(
                ["curl", "-sS", "--max-time", "20", "-H", f"X-LLM-Token: {token}", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=25,
            )
            if log_request:
                logging.info("GET returncode=%s", proc.returncode)
            if proc.returncode != 0:
                logging.warning("GET curl failed for %s: %s", url, proc.stderr.decode("utf-8", errors="replace"))
                return None
            return json.loads(proc.stdout.decode("utf-8"))
        except Exception as exc:
            logging.warning("GET curl exception for %s: %s", url, exc)
            return None
    req = urllib.request.Request(url, headers={"X-LLM-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as exc:
        logging.warning("GET failed for %s: %s", url, exc)
        return None


def http_post(url: str, token: str, payload: Dict) -> bool:
    if USE_CURL:
        try:
            proc = subprocess.run(
                [
                    "curl",
                    "-sS",
                    "--max-time",
                    "30",
                    "-H",
                    "Content-Type: application/json",
                    "-H",
                    f"X-LLM-Token: {token}",
                    "-d",
                    json.dumps(payload),
                    url,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if proc.returncode != 0:
                logging.warning("POST curl failed for %s: %s", url, proc.stderr.decode("utf-8", errors="replace"))
                return False
            return True
        except Exception as exc:
            logging.warning("POST curl exception for %s: %s", url, exc)
            return False
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-LLM-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            _ = resp.read().decode("utf-8")
            return True
    except Exception as exc:
        logging.warning("POST failed for %s: %s", url, exc)
        return False


def mailbox_base(mailbox_url: str, overseer: bool) -> str:
    base = mailbox_url.rstrip("/")
    if overseer:
        return base + "/tasai_mailbox_overseer"
    return base


def batch_key(run_id: str | None, batch: int) -> str:
    b = f"{batch:03d}"
    return f"{run_id}_{b}" if run_id else b


def scan_batches(frontier: int, scan_ahead: int, scan_backfill: int, cycle: int) -> Sequence[int]:
    start = max(0, frontier - scan_backfill)
    stop = frontier + max(1, scan_ahead)
    batches = list(range(start, stop + 1))
    if cycle > 0 and cycle % 10 == 0 and start > 0:
        # Sparse legacy sweep in case prompts are written out of order.
        sparse = range(0, start, max(1, scan_ahead))
        seen = set(batches)
        for batch in sparse:
            if batch not in seen:
                batches.append(batch)
    return batches


def extract_json(text: str) -> Dict | None:
    text = text.strip()
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}")
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def approx_tokens(text: str) -> int:
    if not text:
        return 0
    # Conservative heuristic for audit/provenance, not billing-grade usage.
    return max(1, math.ceil(len(text) / 4.0))


def usage_record(model: str, prompt: str, stdout: str, stderr: str, seconds: float, ok: bool) -> Dict:
    return {
        "model": model,
        "ok": bool(ok),
        "seconds": float(seconds),
        "prompt_chars": len(prompt),
        "prompt_bytes": len(prompt.encode("utf-8")),
        "response_chars": len(stdout),
        "response_bytes": len(stdout.encode("utf-8")),
        "stderr_chars": len(stderr),
        "approx_prompt_tokens": approx_tokens(prompt),
        "approx_response_tokens": approx_tokens(stdout),
        "approx_total_tokens": approx_tokens(prompt) + approx_tokens(stdout),
    }


def write_usage_sidecar(log_dir: Path, key: str, payload: Dict) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"usage_{key}.json"
    path.write_text(json.dumps(payload, indent=2))


def consensus_suggestions(all_suggestions: Dict[str, List[Dict]], max_points: int) -> List[Dict]:
    bucket: Dict[tuple, List[Dict]] = {}
    for _, suggestions in all_suggestions.items():
        for s in suggestions:
            try:
                h = round(float(s["h"]), 3)
                e = round(float(s["e"] if "e" in s else s.get("E")), 3)
            except Exception:
                continue
            bucket.setdefault((h, e), []).append(s)
    ranked = sorted(bucket.items(), key=lambda kv: len(kv[1]), reverse=True)
    final: List[Dict] = []
    for (h, e), group in ranked:
        if len(final) >= max_points:
            break
        merged = dict(group[0])
        merged["h"] = h
        merged["e"] = e
        if "E" in merged:
            merged.pop("E")
        if "reason" not in merged:
            merged["reason"] = "consensus pick"
        merged["llm_votes"] = len(group)
        final.append(merged)
    return final


def run_llm_single(model: str, prompt: str, codex_model: str, llm_timeout: int) -> Dict:
    import subprocess

    start = time.time()
    try:
        if model == "claude":
            claude_path = shutil.which("claude")
            if not claude_path:
                return {"model": model, "ok": False, "error": "claude not found"}
            proc = subprocess.run(
                [claude_path],
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=llm_timeout,
            )
        elif model == "gemini":
            proc = subprocess.run(
                ["gemini"],
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=llm_timeout,
            )
        elif model == "codex":
            proc = subprocess.run(
                ["codex", "exec", "-m", codex_model, "-"],
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=llm_timeout,
            )
        else:
            return {"model": model, "ok": False, "error": "unknown model"}
    except Exception as exc:
        return {"model": model, "ok": False, "error": str(exc)}

    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    return {
        "model": model,
        "ok": proc.returncode == 0,
        "stdout": out,
        "stderr": err,
        "seconds": time.time() - start,
        "usage": usage_record(model, prompt, out, err, time.time() - start, proc.returncode == 0),
    }


def run_llms(prompt: str, max_points: int, codex_model: str, llm_timeout: int) -> Dict:

    responses = {}
    suggestions = {}
    timings = {}
    usage = {}

    for model in ("claude", "gemini", "codex"):
        result = run_llm_single(model, prompt, codex_model, llm_timeout)
        usage[model] = result.get("usage", {})
        if not result.get("ok"):
            continue
        timings[model] = result["seconds"]
        responses[model] = result["stdout"]

    for name, out in responses.items():
        payload = extract_json(out)
        if payload and "suggestions" in payload:
            suggestions[name] = payload["suggestions"]

    final = consensus_suggestions(suggestions, max_points=max_points)
    if not final and suggestions:
        first = next(iter(suggestions.values()))[:max_points]
        final = [{"h": float(s["h"]), "e": float(s.get("e", s.get("E"))), "reason": s.get("reason", "")}
                 for s in first]

    return {
        "suggestions": final,
        "suggestions_by_model": suggestions,
        "timings": timings,
        "raw": responses,
        "usage": usage,
    }


def run_llm_overseer(prompt: str, codex_model: str, decider: str, batch_idx: int, llm_timeout: int) -> Dict:
    models = ["claude", "gemini", "codex"]
    if decider == "rotate":
        decider_model = models[batch_idx % len(models)]
        proposers = [m for m in models if m != decider_model]
    else:
        decider_model = decider
        # If the operator pins a specific decider, do not force the other local
        # CLIs to run as proposers. This keeps the mailbox watcher usable on
        # machines where only one provider is reliable.
        proposers = []

    proposals = {}
    raw = {}
    timings = {}
    usage = {}

    logging.info("Overseer batch %d: proposers=%s decider=%s", batch_idx, proposers, decider_model)
    for model in proposers:
        try:
            result = run_llm_single(model, prompt, codex_model, llm_timeout)
        except Exception as exc:
            logging.exception("LLM call failed (%s): %s", model, exc)
            raise
        usage[model] = result.get("usage", {})
        raw[model] = result.get("stdout", "")
        if result.get("ok"):
            timings[model] = result["seconds"]
            payload = extract_json(result.get("stdout", ""))
            if payload:
                proposals[model] = payload
            else:
                logging.warning("LLM %s returned no JSON payload", model)
        else:
            logging.warning("LLM %s returned ok=false", model)

    decision_prompt = prompt + "\n\nTwo proposals (JSON):\n" + json.dumps(proposals, indent=2) + \
        "\n\nChoose a mode and (if mode=llm_points) provide exactly 5 points in JSON."

    try:
        result = run_llm_single(decider_model, decision_prompt, codex_model, llm_timeout)
    except Exception as exc:
        logging.exception("Decider call failed (%s): %s", decider_model, exc)
        raise
    usage[decider_model] = result.get("usage", {})
    raw[decider_model] = result.get("stdout", "")
    if result.get("ok"):
        timings[decider_model] = result["seconds"]
    decision = extract_json(result.get("stdout", "")) if result.get("stdout") else None
    if decision is None and proposals:
        # Fall back to first proposer payload
        decision = next(iter(proposals.values()))

    return {
        "decision": decision,
        "timings": timings,
        "proposals": proposals,
        "raw": raw,
        "decider": decider_model,
        "usage": usage,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mailbox-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--max-points", type=int, default=3)
    parser.add_argument("--codex-model", default="gpt-5.2-codex")
    parser.add_argument("--run-id", default=None,
                        help="Optional run-id prefix used in mailbox batch keys (e.g., 3a)")
    parser.add_argument("--overseer", action="store_true",
                        help="Use overseer mailbox mode (mode decisions + points)")
    parser.add_argument("--decider", default="rotate",
                        choices=["rotate", "claude", "gemini", "codex"],
                        help="Which model decides in overseer mode")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--once-timeout", type=int, default=60,
                        help="Max seconds to wait in --once mode")
    parser.add_argument("--llm-timeout", type=int, default=120,
                        help="Max seconds to wait per LLM call")
    parser.add_argument("--no-curl", action="store_true",
                        help="Disable curl and use urllib only")
    parser.add_argument("--usage-log-dir", default="run_logs/llm_usage",
                        help="Directory for per-batch approximate usage JSON sidecars")
    parser.add_argument("--scan-ahead", type=int, default=16,
                        help="How far ahead of the current frontier to poll each cycle")
    parser.add_argument("--scan-backfill", type=int, default=4,
                        help="How far behind the frontier to keep polling for out-of-order batches")
    parser.add_argument("--heartbeat-secs", type=int, default=300,
                        help="Seconds between watcher heartbeat logs")
    args = parser.parse_args()

    global USE_CURL
    if args.no_curl:
        USE_CURL = False

    logging.info(
        "Watcher start mailbox=%s run_id=%s overseer=%s once=%s",
        args.mailbox_url,
        args.run_id,
        args.overseer,
        args.once,
    )

    deadline = time.time() + args.once_timeout if args.once else None
    base = mailbox_base(args.mailbox_url, args.overseer)
    frontier = 0
    cycle = 0
    polls_since_heartbeat = 0
    last_heartbeat = time.time()

    handled = False
    while True:
        for batch in scan_batches(frontier, args.scan_ahead, args.scan_backfill, cycle):
            key = batch_key(args.run_id, batch)
            log_request = args.once and batch == frontier
            status = http_get(f"{base}/status/{key}", args.token, log_request=log_request)
            polls_since_heartbeat += 1
            if not status or not status.get("prompt_ready"):
                if status and status.get("suggestions_ready"):
                    frontier = max(frontier, batch + 1)
                continue
            if status.get("suggestions_ready"):
                frontier = max(frontier, batch + 1)
                continue
            logging.info("Prompt ready for %s", key)
            payload = http_get(f"{base}/prompt/{key}", args.token, log_request=True)
            if not payload:
                logging.warning("Prompt fetch failed for %s", key)
                continue
            frontier = max(frontier, batch)
            prompt = payload.get("prompt", "")
            if args.overseer:
                batch_idx = int(payload.get("meta", {}).get("batch", 0)) if payload.get("meta") else 0
                result = run_llm_overseer(
                    prompt,
                    codex_model=args.codex_model,
                    decider=args.decider,
                    batch_idx=batch_idx,
                    llm_timeout=args.llm_timeout,
                )
                ok = http_post(
                    f"{base}/suggestions/{key}",
                    args.token,
                    {
                        "decision": result["decision"],
                        "meta": {
                            "timings": result["timings"],
                            "proposals": result["proposals"],
                            "raw": result["raw"],
                            "decider": result["decider"],
                            "usage": result.get("usage", {}),
                        },
                    },
                )
                write_usage_sidecar(
                    Path(args.usage_log_dir),
                    key,
                    {
                        "run_id": args.run_id,
                        "batch": key,
                        "mode": "overseer",
                        "usage": result.get("usage", {}),
                    },
                )
            else:
                result = run_llms(
                    prompt,
                    max_points=args.max_points,
                    codex_model=args.codex_model,
                    llm_timeout=args.llm_timeout,
                )
                ok = http_post(
                    f"{base}/suggestions/{key}",
                    args.token,
                    {
                        "suggestions": result["suggestions"],
                        "meta": {
                            "timings": result["timings"],
                            "suggestions_by_model": result["suggestions_by_model"],
                            "raw": result["raw"],
                            "usage": result.get("usage", {}),
                        },
                    },
                )
                write_usage_sidecar(
                    Path(args.usage_log_dir),
                    key,
                    {
                        "run_id": args.run_id,
                        "batch": key,
                        "mode": "suggestions",
                        "usage": result.get("usage", {}),
                    },
                )
            if not ok:
                logging.error("Failed to post suggestions for %s", key)
                return
            logging.info("Posted suggestions for %s", key)
            frontier = max(frontier, batch + 1)
            handled = True
            break

        now = time.time()
        if now - last_heartbeat >= max(30, args.heartbeat_secs):
            logging.info(
                "Heartbeat run_id=%s frontier=%03d polls=%d handled=%s",
                args.run_id,
                frontier,
                polls_since_heartbeat,
                handled,
            )
            last_heartbeat = now
            polls_since_heartbeat = 0
        cycle += 1

        if args.once:
            if handled:
                return
            if deadline and time.time() >= deadline:
                logging.info("Once timeout after %ss with no prompt handled", args.once_timeout)
                break
            time.sleep(1)
            continue
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
