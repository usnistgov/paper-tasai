#!/usr/bin/env python3
"""
Poll remote TACC LLM output dirs for prompt files, run local LLMs,
and upload suggestions_batchXXX.json back to TACC.

Example:
  python scripts/llm_external_watcher.py \
    --remote stampede3 \
    --dirs /work2/09870/williamratcliff/stampede3/tasai_paper_clean/run_outputs/llm_scenarios/scenario3a_llm_loggp/llm \
           /work2/09870/williamratcliff/stampede3/tasai_paper_clean/run_outputs/llm_scenarios/scenario3b_llm_sym_preloggp/llm \
    --interval 10 \
    --max-points 3 \
    --codex-model gpt-5.2-codex
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Tuple


PROMPT_RE = re.compile(r"prompt_.*_batch(\d{3})\.txt$")


def run(cmd: List[str], input_bytes: bytes | None = None) -> Tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode, proc.stdout.decode("utf-8", errors="replace"), proc.stderr.decode("utf-8", errors="replace")


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


def consensus_suggestions(all_suggestions: Dict[str, List[Dict]], max_points: int) -> List[Dict]:
    bucket: Dict[Tuple[float, float], List[Dict]] = {}
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


def run_llms(prompt: str, max_points: int, codex_model: str) -> Dict:
    responses = {}
    suggestions = {}
    timings = {}

    # Claude
    if Path("/Users/williamratcliff/.local/bin/claude").exists():
        start = time.time()
        rc, out, err = run(["/Users/williamratcliff/.local/bin/claude"], input_bytes=prompt.encode("utf-8"))
        timings["claude"] = time.time() - start
        responses["claude"] = (rc, out, err)

    # Gemini
    start = time.time()
    rc, out, err = run(["gemini"], input_bytes=prompt.encode("utf-8"))
    timings["gemini"] = time.time() - start
    responses["gemini"] = (rc, out, err)

    # Codex
    start = time.time()
    rc, out, err = run(["codex", "exec", "-m", codex_model, "-"], input_bytes=prompt.encode("utf-8"))
    timings["codex"] = time.time() - start
    responses["codex"] = (rc, out, err)

    for name, (rc, out, _err) in responses.items():
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
        "raw": {k: v[1] for k, v in responses.items()},
    }


def list_remote_prompts(remote: str, remote_dir: str) -> List[str]:
    cmd = ["ssh", remote, f"ls -1 {remote_dir}/prompt_*_batch*.txt 2>/dev/null"]
    rc, out, _err = run(cmd)
    if rc != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def remote_file_exists(remote: str, path: str) -> bool:
    rc, _out, _err = run(["ssh", remote, f"test -f {path}"])
    return rc == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", required=True, help="SSH host (e.g. stampede3)")
    parser.add_argument("--dirs", nargs="+", required=True, help="Remote LLM output dirs")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval seconds")
    parser.add_argument("--max-points", type=int, default=3, help="Max points per batch")
    parser.add_argument("--codex-model", type=str, default="gpt-5.2-codex")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle then exit")
    args = parser.parse_args()

    while True:
        for rdir in args.dirs:
            prompts = list_remote_prompts(args.remote, rdir)
            for prompt_path in prompts:
                m = PROMPT_RE.search(os.path.basename(prompt_path))
                if not m:
                    continue
                batch = m.group(1)
                sugg_path = f"{rdir}/suggestions_batch{batch}.json"
                if remote_file_exists(args.remote, sugg_path):
                    continue

                with tempfile.TemporaryDirectory() as tmp:
                    local_prompt = Path(tmp) / "prompt.txt"
                    rc, _out, err = run(["scp", f"{args.remote}:{prompt_path}", str(local_prompt)])
                    if rc != 0:
                        print(f"[watcher] scp prompt failed for {prompt_path}: {err.strip()}", flush=True)
                        return
                    prompt = local_prompt.read_text()

                    result = run_llms(prompt, max_points=args.max_points, codex_model=args.codex_model)
                    payload = {"suggestions": result["suggestions"]}
                    local_sugg = Path(tmp) / f"suggestions_batch{batch}.json"
                    local_sugg.write_text(json.dumps(payload, indent=2))
                    rc, _out, _err = run(["scp", str(local_sugg), f"{args.remote}:{sugg_path}"])
                    if rc != 0:
                        print(f"[watcher] scp suggestions failed for {sugg_path}", flush=True)
                        return

                    detail_payload = {
                        "suggestions_by_model": result.get("suggestions_by_model", {}),
                        "raw": result.get("raw", {}),
                    }
                    detail_path = Path(tmp) / f"llm_raw_batch{batch}.json"
                    detail_path.write_text(json.dumps(detail_payload, indent=2))
                    rc, _out, _err = run(["scp", str(detail_path), f"{args.remote}:{rdir}/llm_raw_batch{batch}.json"])
                    if rc != 0:
                        print(f"[watcher] scp raw log failed for batch {batch}", flush=True)
                        return

                    timing_path = Path(tmp) / f"llm_timing_batch{batch}.json"
                    timing_path.write_text(json.dumps(result["timings"], indent=2))
                    rc, _out, _err = run(["scp", str(timing_path), f"{args.remote}:{rdir}/llm_timing_local_batch{batch}.json"])
                    if rc != 0:
                        print(f"[watcher] scp timing log failed for batch {batch}", flush=True)
                        return

        if args.once:
            break
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
