#!/usr/bin/env python3
"""SQLite-backed mailbox campaign manager."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Optional

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import llm_danse2_watcher as watcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("llm_campaign_manager")


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS campaigns (
  run_id TEXT PRIMARY KEY,
  mailbox_url TEXT NOT NULL,
  token TEXT NOT NULL,
  mode TEXT NOT NULL DEFAULT 'overseer',
  decider TEXT NOT NULL DEFAULT 'codex',
  codex_model TEXT NOT NULL DEFAULT 'gpt-5.2-codex',
  llm_timeout INTEGER NOT NULL DEFAULT 180,
  usage_log_dir TEXT NOT NULL DEFAULT 'run_logs/llm_usage',
  priority INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active',
  next_batch_hint INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS batches (
  run_id TEXT NOT NULL,
  batch_idx INTEGER NOT NULL,
  mailbox_key TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending',
  prompt_ready INTEGER NOT NULL DEFAULT 0,
  suggestions_ready INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  worker_pid INTEGER,
  prompt_fetched_at REAL,
  claimed_at REAL,
  posted_at REAL,
  last_error TEXT,
  prompt_path TEXT,
  usage_path TEXT,
  updated_at REAL NOT NULL,
  PRIMARY KEY (run_id, batch_idx),
  FOREIGN KEY (run_id) REFERENCES campaigns(run_id)
);
"""


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(batches)")}
    if "prompt_path" not in cols:
        conn.execute("ALTER TABLE batches ADD COLUMN prompt_path TEXT")
        conn.commit()
    return conn


def now_ts() -> float:
    return time.time()


def upsert_campaign(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    ts = now_ts()
    conn.execute(
        """
        INSERT INTO campaigns (
          run_id, mailbox_url, token, mode, decider, codex_model, llm_timeout,
          usage_log_dir, priority, status, next_batch_hint, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          mailbox_url=excluded.mailbox_url,
          token=excluded.token,
          mode=excluded.mode,
          decider=excluded.decider,
          codex_model=excluded.codex_model,
          llm_timeout=excluded.llm_timeout,
          usage_log_dir=excluded.usage_log_dir,
          priority=excluded.priority,
          status=excluded.status,
          updated_at=excluded.updated_at
        """,
        (
            args.run_id,
            args.mailbox_url,
            args.token,
            args.mode,
            args.decider,
            args.codex_model,
            args.llm_timeout,
            args.usage_log_dir,
            args.priority,
            args.status,
            0,
            ts,
            ts,
        ),
    )
    conn.commit()


def list_campaigns(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return conn.execute(
        "SELECT run_id, mode, status, priority, next_batch_hint, updated_at FROM campaigns ORDER BY priority DESC, run_id"
    )


def mailbox_base(campaign: sqlite3.Row) -> str:
    base = str(campaign["mailbox_url"]).rstrip("/")
    if campaign["mode"] == "overseer":
        return base if base.endswith("/tasai_mailbox_overseer") else base + "/tasai_mailbox_overseer"
    return base if base.endswith("/tasai_mailbox") else base + "/tasai_mailbox"


def scan_campaign(conn: sqlite3.Connection, campaign: sqlite3.Row, scan_span: int) -> None:
    base = mailbox_base(campaign)
    token = campaign["token"]
    start = int(campaign["next_batch_hint"] or 0)
    ts = now_ts()
    max_seen = start
    for batch_idx in range(start, start + scan_span):
        key = f"{campaign['run_id']}_{batch_idx:03d}"
        status = watcher.http_get(f"{base}/status/{key}", token)
        if not status:
            continue
        prompt_ready = int(bool(status.get("prompt_ready")))
        suggestions_ready = int(bool(status.get("suggestions_ready")))
        existing = conn.execute(
            "SELECT state FROM batches WHERE run_id=? AND batch_idx=?",
            (campaign["run_id"], batch_idx),
        ).fetchone()
        if existing and existing["state"] == "posted":
            max_seen = max(max_seen, batch_idx + 1)
            continue
        if existing and existing["state"] in {"ready_local", "running_foreground"} and prompt_ready and not suggestions_ready:
            state = existing["state"]
        else:
            state = "pending" if prompt_ready and not suggestions_ready else ("posted" if suggestions_ready else "waiting")
        conn.execute(
            """
            INSERT INTO batches (
              run_id, batch_idx, mailbox_key, state, prompt_ready, suggestions_ready, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, batch_idx) DO UPDATE SET
              state=excluded.state,
              prompt_ready=excluded.prompt_ready,
              suggestions_ready=excluded.suggestions_ready,
              updated_at=excluded.updated_at
            """,
            (campaign["run_id"], batch_idx, key, state, prompt_ready, suggestions_ready, ts),
        )
        if suggestions_ready:
            max_seen = max(max_seen, batch_idx + 1)
        if prompt_ready and not suggestions_ready:
            break
    conn.execute(
        "UPDATE campaigns SET next_batch_hint=?, updated_at=? WHERE run_id=?",
        (max_seen, ts, campaign["run_id"]),
    )
    conn.commit()


def next_pending_batch(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT b.run_id, b.batch_idx, b.mailbox_key
        FROM batches b
        JOIN campaigns c ON c.run_id = b.run_id
        WHERE c.status='active' AND b.state='pending'
        ORDER BY c.priority DESC, b.run_id, b.batch_idx
        LIMIT 1
        """
    ).fetchone()


def prepared_dir(root: Path, run_id: str) -> Path:
    return root / run_id


def prepare_batch(conn: sqlite3.Connection, campaign: sqlite3.Row, batch: sqlite3.Row, root: Path) -> None:
    base = mailbox_base(campaign)
    token = campaign["token"]
    key = batch["mailbox_key"]
    status = watcher.http_get(f"{base}/status/{key}", token)
    if not status:
        conn.execute(
            "UPDATE batches SET state='pending', last_error=?, updated_at=? WHERE run_id=? AND batch_idx=?",
            ("status fetch failed", now_ts(), batch["run_id"], batch["batch_idx"]),
        )
        conn.commit()
        return
    if status.get("suggestions_ready"):
        conn.execute(
            "UPDATE batches SET state='posted', suggestions_ready=1, posted_at=?, updated_at=? WHERE run_id=? AND batch_idx=?",
            (now_ts(), now_ts(), batch["run_id"], batch["batch_idx"]),
        )
        conn.commit()
        return
    if not status.get("prompt_ready"):
        conn.execute(
            "UPDATE batches SET state='waiting', prompt_ready=0, updated_at=? WHERE run_id=? AND batch_idx=?",
            (now_ts(), batch["run_id"], batch["batch_idx"]),
        )
        conn.commit()
        return

    payload = watcher.http_get(f"{base}/prompt/{key}", token)
    if not payload:
        conn.execute(
            "UPDATE batches SET state='pending', last_error=?, updated_at=? WHERE run_id=? AND batch_idx=?",
            ("prompt fetch failed", now_ts(), batch["run_id"], batch["batch_idx"]),
        )
        conn.commit()
        return

    run_dir = prepared_dir(root, batch["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / f"prompt_{int(batch['batch_idx']):03d}.txt"
    meta_path = run_dir / f"meta_{int(batch['batch_idx']):03d}.json"
    prompt_path.write_text(payload.get("prompt", ""))
    meta_path.write_text(json.dumps(payload, indent=2))
    conn.execute(
        """
        UPDATE batches
        SET state='ready_local', prompt_ready=1, prompt_fetched_at=?, prompt_path=?, last_error=NULL, updated_at=?
        WHERE run_id=? AND batch_idx=?
        """,
        (now_ts(), str(prompt_path), now_ts(), batch["run_id"], batch["batch_idx"]),
    )
    conn.commit()


def reconcile_stale_claims(conn: sqlite3.Connection, stale_seconds: int) -> None:
    ts = now_ts()
    conn.execute(
        """
        UPDATE batches
        SET state='pending', worker_pid=NULL, last_error='stale claim reset', updated_at=?
        WHERE state='claimed' AND claimed_at IS NOT NULL AND (? - claimed_at) > ?
        """,
        (ts, ts, stale_seconds),
    )
    conn.execute(
        """
        UPDATE batches
        SET state='pending', worker_pid=NULL, last_error='orphaned claim reset', updated_at=?
        WHERE state='claimed' AND (prompt_path IS NULL OR prompt_path = '')
        """,
        (ts,),
    )
    conn.commit()


def run_manager(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    conn = connect_db(db_path)
    prep_root = Path(args.prepared_root)
    LOG.info("campaign manager start db=%s prepare_only=1", db_path)
    while True:
        reconcile_stale_claims(conn, args.stale_claim_seconds)

        campaigns = list(conn.execute("SELECT * FROM campaigns WHERE status='active' ORDER BY priority DESC, run_id"))
        for campaign in campaigns:
            scan_campaign(conn, campaign, args.scan_span)

        while True:
            batch = next_pending_batch(conn)
            if not batch:
                break
            campaign = conn.execute("SELECT * FROM campaigns WHERE run_id=?", (batch["run_id"],)).fetchone()
            prepare_batch(conn, campaign, batch, prep_root)
            LOG.info("prepared batch run_id=%s batch=%03d", batch["run_id"], int(batch["batch_idx"]))

        time.sleep(args.poll_sleep)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add-campaign")
    p_add.add_argument("--db", required=True)
    p_add.add_argument("--run-id", required=True)
    p_add.add_argument("--mailbox-url", required=True)
    p_add.add_argument("--token", required=True)
    p_add.add_argument("--mode", choices=["overseer", "suggestions"], default="overseer")
    p_add.add_argument("--decider", choices=["rotate", "claude", "gemini", "codex"], default="codex")
    p_add.add_argument("--codex-model", default="gpt-5.2-codex")
    p_add.add_argument("--llm-timeout", type=int, default=180)
    p_add.add_argument("--usage-log-dir", default="run_logs/llm_usage")
    p_add.add_argument("--priority", type=int, default=0)
    p_add.add_argument("--status", choices=["active", "paused"], default="active")

    p_list = sub.add_parser("list")
    p_list.add_argument("--db", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("--db", required=True)
    p_run.add_argument("--poll-sleep", type=float, default=5.0)
    p_run.add_argument("--scan-span", type=int, default=20)
    p_run.add_argument("--stale-claim-seconds", type=int, default=600)
    p_run.add_argument("--prepared-root", default="run_logs/llm_prepared")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.cmd == "add-campaign":
        conn = connect_db(Path(args.db))
        upsert_campaign(conn, args)
        print(json.dumps({"ok": True, "run_id": args.run_id}))
        return
    if args.cmd == "list":
        conn = connect_db(Path(args.db))
        rows = [dict(r) for r in list_campaigns(conn)]
        print(json.dumps(rows, indent=2))
        return
    if args.cmd == "run":
        run_manager(args)
        return


if __name__ == "__main__":
    main()
