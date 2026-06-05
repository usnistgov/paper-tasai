#!/usr/bin/env python3
"""Local mailbox watcher for audit ablation batches."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


def http_get(url: str, token: str) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers={"X-LLM-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def http_post(url: str, token: str, payload: Dict[str, Any]) -> bool:
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
    except Exception:
        return False


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    decoder = json.JSONDecoder()
    best: Optional[Dict[str, Any]] = None
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[idx:])
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        best = payload
        if "inject_ids" in payload or "decision" in payload:
            return payload
    return best


def estimate_tokens(text: str) -> int:
    text = text or ""
    # Lightweight fallback for local CLI accounting when provider usage is unavailable.
    return max(1, int(round(len(text) / 4.0)))


def run_llm(command: str, prompt: str) -> Dict[str, Any]:
    proc = subprocess.run(
        command.split(),
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))
    stdout_text = proc.stdout.decode("utf-8", errors="replace")
    payload = extract_json(stdout_text)
    if not payload:
        raise RuntimeError("LLM output did not contain JSON")
    usage = {
        "prompt_tokens_est": estimate_tokens(prompt),
        "completion_tokens_est": estimate_tokens(stdout_text),
        "total_tokens_est": estimate_tokens(prompt) + estimate_tokens(stdout_text),
    }
    decision = payload.get("decision", payload)
    return {"decision": decision, "usage": usage, "raw": stdout_text}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mailbox-url", required=True)
    parser.add_argument("--mailbox-token", required=True)
    parser.add_argument("--run-id", required=True, help="Prefix to watch, e.g. audit_ablation_20260319")
    parser.add_argument("--seeds", nargs="+", type=int, required=True, help="Seed ids to watch")
    parser.add_argument("--max-batches", type=int, default=200, help="Max batches per seed to probe")
    parser.add_argument("--llm-command", default="codex exec --ephemeral -m gpt-5.2 -")
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--log-file", default=None)
    args = parser.parse_args()

    base = args.mailbox_url.rstrip("/")
    log_path = Path(args.log_file) if args.log_file else None

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(line, flush=True)
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    seen = set()
    log(f"audit mailbox runner start prefix={args.run_id}")

    while True:
        for seed in args.seeds:
            for batch_idx in range(args.max_batches):
                batch_key = f"{args.run_id}_llm_seed{seed:03d}_{batch_idx:03d}"
                if batch_key in seen:
                    continue
                status = http_get(f"{base}/status/{batch_key}", args.mailbox_token)
                if not status or not status.get("prompt_ready") or status.get("suggestions_ready"):
                    continue
                prompt_payload = http_get(f"{base}/prompt/{batch_key}", args.mailbox_token)
                if not prompt_payload:
                    continue
                prompt = str(prompt_payload.get("prompt", ""))
                log(f"prompt ready for {batch_key}")
                try:
                    result = run_llm(args.llm_command, prompt)
                    decision = result["decision"]
                    usage = result["usage"]
                    ok = http_post(
                        f"{base}/suggestions/{batch_key}",
                        args.mailbox_token,
                        {
                            "decision": decision,
                            "suggestions": [decision] if isinstance(decision, dict) else [],
                            "meta": {
                                "decider": "audit_mailbox_runner",
                                "usage": usage,
                                "raw": result.get("raw", ""),
                            },
                        },
                    )
                    if ok:
                        seen.add(batch_key)
                        log(f"posted decision for {batch_key} usage={usage}")
                except Exception as exc:
                    log(f"error for {batch_key}: {exc}")
        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    main()
