"""SQLite connection manager and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".research_cli"
DB_PATH = DB_DIR / "db.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_runs (
    run_id             TEXT PRIMARY KEY,
    timestamp          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    pass_rate          REAL NOT NULL,
    hallucination_rate REAL NOT NULL,
    avg_iterations     REAL NOT NULL,
    coverage_rate      REAL NOT NULL,
    individual_results TEXT NOT NULL,
    git_hash           TEXT
);
"""


class Database:
    """Manages the SQLite connection and schema lifecycle."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Return a connection with WAL mode and foreign keys enabled."""
        if self._conn is not None:
            return self._conn
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._ensure_schema(self._conn)
        return self._conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(_SCHEMA)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
