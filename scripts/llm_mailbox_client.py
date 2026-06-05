#!/usr/bin/env python3
"""
Simple helper for the danse2 mailbox.

Examples:
  python scripts/llm_mailbox_client.py status --url https://example.org/tasai_mailbox --token TOKEN --batch 000
  python scripts/llm_mailbox_client.py post-prompt --url https://example.org/tasai_mailbox --token TOKEN --batch 000 --prompt-file prompt.txt
  python scripts/llm_mailbox_client.py get-suggestions --url https://example.org/tasai_mailbox --token TOKEN --batch 000
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Dict


def http_get(url: str, token: str) -> Dict | None:
    req = urllib.request.Request(url, headers={"X-LLM-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception:
        return None


def http_post(url: str, token: str, payload: Dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-LLM-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            _ = resp.read().decode("utf-8")
            return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common(p):
        p.add_argument("--url", required=True)
        p.add_argument("--token", required=True)
        p.add_argument("--batch", required=True)

    p_status = sub.add_parser("status")
    add_common(p_status)

    p_prompt = sub.add_parser("post-prompt")
    add_common(p_prompt)
    p_prompt.add_argument("--prompt-file", required=True)
    p_prompt.add_argument("--checkpoint-file", default=None)

    p_sugg = sub.add_parser("get-suggestions")
    add_common(p_sugg)

    args = parser.parse_args()

    if args.cmd == "status":
        payload = http_get(f"{args.url}/status/{args.batch}", args.token)
        print(json.dumps(payload, indent=2))
        return

    if args.cmd == "post-prompt":
        prompt = Path(args.prompt_file).read_text()
        checkpoint = None
        if args.checkpoint_file:
            checkpoint = json.loads(Path(args.checkpoint_file).read_text())
        payload = {
            "prompt": prompt,
            "checkpoint": checkpoint,
            "meta": {"batch": args.batch},
        }
        ok = http_post(f"{args.url}/prompt/{args.batch}", args.token, payload)
        print(json.dumps({"ok": ok}))
        return

    if args.cmd == "get-suggestions":
        payload = http_get(f"{args.url}/suggestions/{args.batch}", args.token)
        print(json.dumps(payload, indent=2))
        return


if __name__ == "__main__":
    main()
