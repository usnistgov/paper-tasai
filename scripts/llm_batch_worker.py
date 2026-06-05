#!/usr/bin/env python3
"""Execute exactly one mailbox batch claimed by the campaign manager."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import llm_danse2_watcher as watcher


def connect_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def now_ts() -> float:
    return time.time()


def mailbox_base(campaign: sqlite3.Row) -> str:
    base = str(campaign["mailbox_url"]).rstrip("/")
    if campaign["mode"] == "overseer":
        return base if base.endswith("/tasai_mailbox_overseer") else base + "/tasai_mailbox_overseer"
    return base if base.endswith("/tasai_mailbox") else base + "/tasai_mailbox"


def mark(conn: sqlite3.Connection, run_id: str, batch_idx: int, **fields) -> None:
    assignments = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values())
    values.extend([run_id, batch_idx])
    conn.execute(
        f"UPDATE batches SET {assignments}, updated_at=? WHERE run_id=? AND batch_idx=?",
        values[:-2] + [now_ts()] + values[-2:],
    )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--batch-idx", type=int, required=True)
    args = parser.parse_args()

    conn = connect_db(Path(args.db))
    campaign = conn.execute("SELECT * FROM campaigns WHERE run_id=?", (args.run_id,)).fetchone()
    batch = conn.execute(
        "SELECT * FROM batches WHERE run_id=? AND batch_idx=?",
        (args.run_id, args.batch_idx),
    ).fetchone()
    if not campaign or not batch:
        raise SystemExit("campaign/batch not found")

    base = mailbox_base(campaign)
    token = campaign["token"]
    key = batch["mailbox_key"]

    status = watcher.http_get(f"{base}/status/{key}", token)
    if not status:
        mark(conn, args.run_id, args.batch_idx, state="pending", last_error="status fetch failed")
        raise SystemExit(1)
    if status.get("suggestions_ready"):
        mark(conn, args.run_id, args.batch_idx, state="posted", suggestions_ready=1, posted_at=now_ts())
        return
    if not status.get("prompt_ready"):
        mark(conn, args.run_id, args.batch_idx, state="waiting", prompt_ready=0, suggestions_ready=0)
        return

    payload = watcher.http_get(f"{base}/prompt/{key}", token)
    if not payload:
        mark(conn, args.run_id, args.batch_idx, state="pending", last_error="prompt fetch failed")
        raise SystemExit(1)

    prompt = payload.get("prompt", "")
    mark(conn, args.run_id, args.batch_idx, prompt_ready=1, prompt_fetched_at=now_ts())
    if campaign["mode"] == "overseer":
        batch_meta = payload.get("meta", {}) or {}
        result = watcher.run_llm_overseer(
            prompt,
            codex_model=campaign["codex_model"],
            decider=campaign["decider"],
            batch_idx=int(batch_meta.get("batch", args.batch_idx)),
            llm_timeout=int(campaign["llm_timeout"]),
        )
        body = {
            "decision": result["decision"],
            "meta": {
                "timings": result["timings"],
                "proposals": result["proposals"],
                "raw": result["raw"],
                "decider": result["decider"],
                "usage": result.get("usage", {}),
            },
        }
        watcher.write_usage_sidecar(
            Path(campaign["usage_log_dir"]),
            key,
            {"run_id": args.run_id, "batch": key, "mode": "overseer", "usage": result.get("usage", {})},
        )
    else:
        result = watcher.run_llms(
            prompt,
            max_points=3,
            codex_model=campaign["codex_model"],
            llm_timeout=int(campaign["llm_timeout"]),
        )
        body = {
            "suggestions": result["suggestions"],
            "meta": {
                "timings": result["timings"],
                "suggestions_by_model": result["suggestions_by_model"],
                "raw": result["raw"],
                "usage": result.get("usage", {}),
            },
        }
        watcher.write_usage_sidecar(
            Path(campaign["usage_log_dir"]),
            key,
            {"run_id": args.run_id, "batch": key, "mode": "suggestions", "usage": result.get("usage", {})},
        )

    ok = watcher.http_post(f"{base}/suggestions/{key}", token, body)
    if not ok:
        mark(conn, args.run_id, args.batch_idx, state="pending", last_error="post failed")
        raise SystemExit(1)

    usage_path = str(Path(campaign["usage_log_dir"]) / f"usage_{key}.json")
    mark(
        conn,
        args.run_id,
        args.batch_idx,
        state="posted",
        suggestions_ready=1,
        posted_at=now_ts(),
        usage_path=usage_path,
        last_error=None,
    )


if __name__ == "__main__":
    main()
