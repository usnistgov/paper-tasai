#!/usr/bin/env python3
"""Foreground executor for prepared mailbox batches."""

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
from llm_campaign_manager import connect_db, mailbox_base, prepared_dir, now_ts


def claim_ready_batch(conn: sqlite3.Connection, run_id: str | None) -> sqlite3.Row | None:
    if run_id:
        row = conn.execute(
            "SELECT * FROM batches WHERE run_id=? AND state='ready_local' ORDER BY batch_idx LIMIT 1",
            (run_id,),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT b.* FROM batches b
            JOIN campaigns c ON c.run_id=b.run_id
            WHERE c.status='active' AND b.state='ready_local'
            ORDER BY c.priority DESC, b.run_id, b.batch_idx
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE batches SET state='running_foreground', claimed_at=?, updated_at=? WHERE run_id=? AND batch_idx=?",
        (now_ts(), now_ts(), row["run_id"], row["batch_idx"]),
    )
    conn.commit()
    return conn.execute(
        "SELECT * FROM batches WHERE run_id=? AND batch_idx=?",
        (row["run_id"], row["batch_idx"]),
    ).fetchone()


def run_one(conn: sqlite3.Connection, batch: sqlite3.Row, prepared_root: Path) -> None:
    campaign = conn.execute("SELECT * FROM campaigns WHERE run_id=?", (batch["run_id"],)).fetchone()
    if not campaign:
        raise SystemExit("campaign missing")
    key = batch["mailbox_key"]
    run_dir = prepared_dir(prepared_root, batch["run_id"])
    prompt_path = Path(batch["prompt_path"]) if batch["prompt_path"] else run_dir / f"prompt_{int(batch['batch_idx']):03d}.txt"
    meta_path = run_dir / f"meta_{int(batch['batch_idx']):03d}.json"
    prompt = prompt_path.read_text()
    payload = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    if campaign["mode"] == "overseer":
        batch_meta = payload.get("meta", {}) or {}
        result = watcher.run_llm_overseer(
            prompt,
            codex_model=campaign["codex_model"],
            decider=campaign["decider"],
            batch_idx=int(batch_meta.get("batch", batch["batch_idx"])),
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
            {"run_id": batch["run_id"], "batch": key, "mode": "overseer", "usage": result.get("usage", {})},
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
            {"run_id": batch["run_id"], "batch": key, "mode": "suggestions", "usage": result.get("usage", {})},
        )

    ok = watcher.http_post(f"{mailbox_base(campaign)}/suggestions/{key}", campaign["token"], body)
    if not ok:
        conn.execute(
            "UPDATE batches SET state='ready_local', last_error=?, updated_at=? WHERE run_id=? AND batch_idx=?",
            ("post failed", now_ts(), batch["run_id"], batch["batch_idx"]),
        )
        conn.commit()
        raise SystemExit(1)

    usage_path = str(Path(campaign["usage_log_dir"]) / f"usage_{key}.json")
    conn.execute(
        """
        UPDATE batches
        SET state='posted', suggestions_ready=1, posted_at=?, usage_path=?, last_error=NULL, updated_at=?
        WHERE run_id=? AND batch_idx=?
        """,
        (now_ts(), usage_path, now_ts(), batch["run_id"], batch["batch_idx"]),
    )
    conn.commit()
    print(json.dumps({"ok": True, "run_id": batch["run_id"], "batch_idx": int(batch["batch_idx"])}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--prepared-root", default="run_logs/llm_prepared")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--sleep", type=float, default=5.0)
    args = parser.parse_args()

    conn = connect_db(Path(args.db))
    prepared_root = Path(args.prepared_root)
    while True:
        batch = claim_ready_batch(conn, args.run_id)
        if not batch:
            if args.loop:
                time.sleep(args.sleep)
                continue
            print(json.dumps({"ok": True, "message": "no ready batch"}))
            return
        run_one(conn, batch, prepared_root)
        if not args.loop:
            return


if __name__ == "__main__":
    main()
