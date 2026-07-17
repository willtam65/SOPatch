"""core/store.py -- persistence for automated review runs and their audit trail.

When the Jira webhook (or a manual analysis) flags SOPs, SOPatch records the run
so a reviewer can open it later, approve or reject the drafted edits, and leave a
record that survives a restart. Backed by SQLite from the standard library, so
there is no new dependency and the demo needs no external database.

Every state change also appends an append-only audit event, so a change is
traceable end to end: from the Jira source, to the SOPs it flagged, to the
approval decision and who made it. That audit trail is the point of the review
loop, not a side effect.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

# Default DB lives under data/ next to the other bundled sample data.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(_BASE_DIR, "data", "sopatch.db")

VALID_DECISIONS = {"approved", "rejected"}


def _now():
    """UTC timestamp, second precision, ISO 8601. Stored as text for portability."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ReviewStore:
    """SQLite-backed store of review runs and their audit events.

    A fresh connection is opened per operation. That is more than fast enough for
    the webhook's traffic and sidesteps SQLite's cross-thread connection rules
    under gunicorn, at the cost of not supporting an in-memory database (each
    connection would see its own empty one). Tests point SOPATCH_DB at a temp file.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv("SOPATCH_DB") or DEFAULT_DB_PATH
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at     TEXT    NOT NULL,
                    source         TEXT    NOT NULL,
                    change_note    TEXT    NOT NULL,
                    result_json    TEXT    NOT NULL,
                    affected_count INTEGER NOT NULL,
                    status         TEXT    NOT NULL DEFAULT 'pending',
                    decided_at     TEXT,
                    approver       TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id  INTEGER NOT NULL,
                    at      TEXT    NOT NULL,
                    event   TEXT    NOT NULL,
                    actor   TEXT    NOT NULL DEFAULT '',
                    detail  TEXT    NOT NULL DEFAULT '',
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );
                """
            )

    def create_run(self, source, change_note, result):
        """Record a new flagged run (status pending) and its 'created' audit event.
        Returns the new run id."""
        affected = int(result.get("affected_count", 0))
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO runs (created_at, source, change_note, result_json, "
                "affected_count, status) VALUES (?, ?, ?, ?, ?, 'pending')",
                (now, source, change_note, json.dumps(result), affected),
            )
            run_id = cur.lastrowid
            conn.execute(
                "INSERT INTO audit_events (run_id, at, event, actor, detail) "
                "VALUES (?, ?, 'created', 'system', ?)",
                (run_id, now, f"{affected} SOP(s) flagged from {source}"),
            )
        return run_id

    def record_event(self, run_id, event, actor="system", detail=""):
        """Append an audit event without changing run state (e.g. 'notified')."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_events (run_id, at, event, actor, detail) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, _now(), event, actor, detail),
            )

    def set_decision(self, run_id, decision, actor="reviewer"):
        """Approve or reject a run, stamping who decided and when, plus an audit
        event. Returns the updated run, or None if the run does not exist."""
        if decision not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")
        now = _now()
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE runs SET status = ?, decided_at = ?, approver = ? WHERE id = ?",
                (decision, now, actor, run_id),
            )
            conn.execute(
                "INSERT INTO audit_events (run_id, at, event, actor, detail) "
                "VALUES (?, ?, ?, ?, '')",
                (run_id, now, decision, actor),
            )
        return self.get_run(run_id)

    def get_run(self, run_id):
        """Return one run with its parsed result and ordered audit events, or None."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            events = conn.execute(
                "SELECT at, event, actor, detail FROM audit_events "
                "WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        run = dict(row)
        run["result"] = json.loads(run.pop("result_json"))
        run["audit"] = [dict(e) for e in events]
        return run

    def list_runs(self, limit=50):
        """Return recent run summaries, newest first (no result body)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, source, affected_count, status, decided_at, "
                "approver FROM runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
