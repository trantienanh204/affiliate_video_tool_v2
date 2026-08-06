"""
Job history persistence (SQLite).

Stores completed / failed jobs for the History tab and debugging.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.config import settings
from core.logging import get_logger
from models.job import JobResult

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'done',
    product_name TEXT,
    category    TEXT,
    concept     TEXT,
    scenes      INTEGER,
    duration    REAL,
    video_path  TEXT,
    caption     TEXT,
    script_text TEXT,
    meta_json   TEXT,
    error       TEXT,
    created_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
"""


def _db_path() -> Path:
    p = settings.history_db
    if not p.is_absolute():
        p = settings.project_root / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def save_result(result: JobResult, *, status: str = "done", error: str | None = None) -> None:
    """Persist a successful (or failed) job."""
    meta = result.meta or {}
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO jobs
            (id, status, product_name, category, concept, scenes, duration,
             video_path, caption, script_text, meta_json, error, created_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.job_id,
                status,
                meta.get("product_name") or "",
                meta.get("category") or "",
                meta.get("concept") or "",
                meta.get("scenes") or 0,
                result.duration,
                str(result.video_path) if result.video_path else None,
                result.caption,
                result.script_text,
                json.dumps(meta, ensure_ascii=False),
                error,
                now,
                now,
            ),
        )
        conn.commit()
    logger.info("History saved | job=%s | status=%s", result.job_id, status)


def save_failure(
    job_id: str,
    product_name: str,
    error: str,
    *,
    category: str = "",
) -> None:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO jobs
            (id, status, product_name, category, error, created_at, finished_at)
            VALUES (?, 'failed', ?, ?, ?, ?, ?)
            """,
            (job_id, product_name, category, error, now, now),
        )
        conn.commit()


def list_jobs(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent jobs (newest first)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def clear_history() -> int:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM jobs")
        conn.commit()
        return cur.rowcount
