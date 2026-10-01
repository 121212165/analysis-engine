"""Request-level SQLite cache: url → response body + fetched_at, TTL 淘汰."""
import json
import sqlite3
import threading
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS request_cache (
    url        TEXT PRIMARY KEY,
    body       TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS search_runs (
    queries_key TEXT PRIMARY KEY,
    params      TEXT NOT NULL,
    result      TEXT NOT NULL,
    fetched_at  REAL NOT NULL
);
"""


class RequestCache:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        return conn

    def get(self, url: str, ttl_hours: float | None = None) -> str | None:
        with self._lock, self._conn() as conn:
            row = conn.execute("SELECT body, fetched_at FROM request_cache WHERE url = ?", (url,)).fetchone()
        if not row:
            return None
        body, fetched_at = row
        if ttl_hours is not None and time.time() - fetched_at > ttl_hours * 3600:
            return None
        return body

    def put(self, url: str, body: str, ttl_hours: float | None = None) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO request_cache (url, body, fetched_at) VALUES (?, ?, ?)",
                (url, body, time.time()),
            )

    def stats(self) -> dict:
        with self._lock, self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM request_cache").fetchone()[0]
        return {"entries": count}
