#!/usr/bin/env python3
"""Run the mailbox watcher in one-shot mode inside a durable supervisor loop."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--poll-sleep", type=float, default=5.0)
    parser.add_argument("--once-timeout", type=int, default=15)
    parser.add_argument("watcher_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.watcher_args:
        raise SystemExit("watcher args required after --")
    if args.watcher_args and args.watcher_args[0] == "--":
        args.watcher_args = args.watcher_args[1:]

    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", buffering=1) as log:
        while True:
            cmd = [sys.executable, "-u", "scripts/llm_danse2_watcher.py", *args.watcher_args, "--once", "--once-timeout", str(args.once_timeout)]
            log.write(f"[supervisor] start cmd={' '.join(cmd)}\n")
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=Path(__file__).resolve().parents[1],
                    stdout=log,
                    stderr=log,
                    check=False,
                )
                log.write(f"[supervisor] exit rc={proc.returncode}\n")
            except Exception as exc:  # pragma: no cover - defensive logging
                log.write(f"[supervisor] error {exc}\n")
            time.sleep(args.poll_sleep)


if __name__ == "__main__":
    main()
