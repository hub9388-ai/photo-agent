from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from app.core.settings import get_settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_sequences (
    job_id TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    agent TEXT,
    type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    UNIQUE(job_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_events_job_seq ON events(job_id, seq);

CREATE TABLE IF NOT EXISTS results (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_results_job ON results(job_id);
"""


@dataclass(frozen=True)
class SQLiteDatabase:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


_DATABASE: SQLiteDatabase | None = None
_DATABASE_LOCK = RLock()


def get_database() -> SQLiteDatabase:
    global _DATABASE
    with _DATABASE_LOCK:
        if _DATABASE is None:
            _DATABASE = SQLiteDatabase(get_settings().database_path)
        return _DATABASE
