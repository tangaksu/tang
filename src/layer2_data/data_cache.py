"""Layer 2 – SQLite-backed data cache with TTL support."""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".openclaw" / "cache.db"

# TTL constants (seconds)
TTL_REALTIME = 5 * 60         # 5 minutes  – quotes / K-lines
TTL_FINANCIAL = 24 * 3600     # 1 day      – financial statements
TTL_RESEARCH = 6 * 3600       # 6 hours    – analyst reports
TTL_INDUSTRY = 12 * 3600      # 12 hours   – industry / index data


class DataCache:
    """Thread-safe SQLite cache.

    Key format: ``{source}:{data_type}:{symbol}``
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._path = Path(db_path) if db_path else _DEFAULT_DB
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS cache (
                    key      TEXT PRIMARY KEY,
                    value    TEXT NOT NULL,
                    expires  REAL NOT NULL
                )"""
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires)")
            self._conn.commit()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    async def get(self, key: str) -> Any | None:
        """Return cached value or *None* if missing / expired."""
        async with self._lock:
            return self._get_sync(key)

    async def set(self, key: str, value: Any, ttl: float = TTL_REALTIME) -> None:
        """Store *value* under *key* for *ttl* seconds."""
        async with self._lock:
            self._set_sync(key, value, ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    async def purge_expired(self) -> int:
        """Delete all expired entries; return number removed."""
        async with self._lock:
            conn = self._get_conn()
            cur = conn.execute("DELETE FROM cache WHERE expires < ?", (time.time(),))
            conn.commit()
            return cur.rowcount

    # sync variants (used internally and by synchronous callers)
    def get_sync(self, key: str) -> Any | None:
        return self._get_sync(key)

    def set_sync(self, key: str, value: Any, ttl: float = TTL_REALTIME) -> None:
        self._set_sync(key, value, ttl)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _get_sync(self, key: str) -> Any | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value, expires FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value_str, expires = row
        if time.time() > expires:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()
            return None
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            logger.warning("Cache value for key %s is not valid JSON", key)
            return None

    def _set_sync(self, key: str, value: Any, ttl: float) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?, ?, ?)",
            (key, json.dumps(value, default=str), time.time() + ttl),
        )
        conn.commit()


# Module-level singleton
_cache: DataCache | None = None


def get_cache() -> DataCache:
    global _cache
    if _cache is None:
        _cache = DataCache()
    return _cache
