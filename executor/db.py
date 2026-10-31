"""SQLite store for tasks, events, consents, receipts and the vault.

One process, one file. Every call is a sub-millisecond local write, so the
async code calls it directly. Swap for Postgres only if several executor
processes must share one queue.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL,
    task_json TEXT NOT NULL,
    citizen_token TEXT NOT NULL,
    error TEXT,
    receipt_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_task ON events(task_id, seq);
CREATE TABLE IF NOT EXISTS consents (consent_id TEXT PRIMARY KEY, consent_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profiles (citizen_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS receipts (receipt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, receipt_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vault (vault_ref TEXT PRIMARY KEY, ciphertext BLOB NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (doc_id TEXT PRIMARY KEY, path TEXT NOT NULL, media_type TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS flags (name TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def _exec(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, args)

    def _one(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, args).fetchone()

    def _all(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    # tasks -----------------------------------------------------------------
    def insert_task(self, task_id: str, idem: str, task: dict, token: str) -> bool:
        """Returns False if the idempotency key already exists."""
        ts = now_iso()
        try:
            self._exec(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, idem, "queued", json.dumps(task), token, None, None, ts, ts),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def task_by_idem(self, idem: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM tasks WHERE idempotency_key=?", (idem,))

    def get_task(self, task_id: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM tasks WHERE task_id=?", (task_id,))

    def set_status(self, task_id: str, status: str, error: str | None = None) -> None:
        self._exec(
            "UPDATE tasks SET status=?, error=COALESCE(?, error), updated_at=? WHERE task_id=?",
            (status, error, now_iso(), task_id),
        )

    def set_receipt(self, task_id: str, receipt_id: str) -> None:
        self._exec("UPDATE tasks SET receipt_id=?, updated_at=? WHERE task_id=?", (receipt_id, now_iso(), task_id))

    def claim_next_queued(self) -> sqlite3.Row | None:
        """Atomically move the oldest queued task to validating."""
        with self._lock:
            row = self._conn.execute(
                "SELECT task_id FROM tasks WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                return None
            cur = self._conn.execute(
                "UPDATE tasks SET status='validating', updated_at=? WHERE task_id=? AND status='queued'",
                (now_iso(), row["task_id"]),
            )
            if cur.rowcount != 1:
                return None
            return self._conn.execute("SELECT * FROM tasks WHERE task_id=?", (row["task_id"],)).fetchone()

    def requeue_interrupted(self) -> list[str]:
        """On startup, tasks left mid-run by a crash go to needs_review (never auto-resubmit)."""
        rows = self._all(
            "SELECT task_id FROM tasks WHERE status NOT IN ('queued','completed','failed','needs_review')"
        )
        ids = [r["task_id"] for r in rows]
        for tid in ids:
            self.set_status(tid, "needs_review", "executor restarted while this task was running")
        return ids

    # events ----------------------------------------------------------------
    def add_event(self, task_id: str, event: dict) -> int:
        cur = self._exec("INSERT INTO events (task_id, event_json) VALUES (?,?)", (task_id, "{}"))
        seq = cur.lastrowid
        event["seq"] = seq
        self._exec("UPDATE events SET event_json=? WHERE seq=?", (json.dumps(event, default=str), seq))
        return seq

    def last_event(self, task_id: str) -> dict | None:
        row = self._one("SELECT event_json FROM events WHERE task_id=? ORDER BY seq DESC LIMIT 1", (task_id,))
        return json.loads(row["event_json"]) if row else None

    def recent_tasks(self, limit: int = 25) -> list[sqlite3.Row]:
        return self._all("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))

    def events_after(self, task_id: str, after_seq: int = 0) -> list[dict]:
        rows = self._all("SELECT event_json FROM events WHERE task_id=? AND seq>? ORDER BY seq", (task_id, after_seq))
        return [json.loads(r["event_json"]) for r in rows]

    # consents / profiles ---------------------------------------------------
    def put_consent(self, consent: dict) -> None:
        self._exec("INSERT OR REPLACE INTO consents VALUES (?,?)", (consent["consent_id"], json.dumps(consent, default=str)))

    def get_consent(self, consent_id: str) -> dict | None:
        row = self._one("SELECT consent_json FROM consents WHERE consent_id=?", (consent_id,))
        return json.loads(row["consent_json"]) if row else None

    def put_profile(self, profile: dict) -> None:
        self._exec("INSERT OR REPLACE INTO profiles VALUES (?,?)", (profile["citizen_id"], json.dumps(profile)))

    def get_profile(self, citizen_id: str) -> dict | None:
        row = self._one("SELECT profile_json FROM profiles WHERE citizen_id=?", (citizen_id,))
        return json.loads(row["profile_json"]) if row else None

    # receipts --------------------------------------------------------------
    def put_receipt(self, receipt: dict) -> None:
        self._exec(
            "INSERT OR REPLACE INTO receipts VALUES (?,?,?)",
            (receipt["receipt_id"], receipt["task_id"], json.dumps(receipt, default=str)),
        )

    def get_receipt(self, receipt_id: str) -> dict | None:
        row = self._one("SELECT receipt_json FROM receipts WHERE receipt_id=?", (receipt_id,))
        return json.loads(row["receipt_json"]) if row else None

    # vault -----------------------------------------------------------------
    def put_vault(self, ref: str, ciphertext: bytes, expires_at: str) -> None:
        self._exec("INSERT OR REPLACE INTO vault VALUES (?,?,?)", (ref, ciphertext, expires_at))

    def get_vault(self, ref: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM vault WHERE vault_ref=?", (ref,))

    def delete_vault(self, ref: str) -> None:
        self._exec("DELETE FROM vault WHERE vault_ref=?", (ref,))

    def purge_expired_vault(self) -> int:
        return self._exec("DELETE FROM vault WHERE expires_at < ?", (now_iso(),)).rowcount

    # documents -------------------------------------------------------------
    def put_document(self, doc_id: str, path: str, media_type: str | None) -> None:
        self._exec("INSERT INTO documents VALUES (?,?,?,?)", (doc_id, path, media_type, now_iso()))

    def get_document(self, doc_id: str) -> sqlite3.Row | None:
        return self._one("SELECT * FROM documents WHERE doc_id=?", (doc_id,))

    # flags (kill switch) ---------------------------------------------------
    def set_flag(self, name: str, value: Any) -> None:
        self._exec("INSERT OR REPLACE INTO flags VALUES (?,?)", (name, json.dumps(value)))

    def get_flag(self, name: str, default: Any = None) -> Any:
        row = self._one("SELECT value FROM flags WHERE name=?", (name,))
        return json.loads(row["value"]) if row else default
