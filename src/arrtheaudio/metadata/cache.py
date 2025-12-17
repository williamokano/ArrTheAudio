"""SQLite-based cache for TMDB API responses."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class TMDBCache:
    """SQLite-based cache for TMDB API responses with TTL support."""

    def __init__(self, db_path: Path, ttl_days: int = 30):
        """Initialize cache with database path and TTL.

        Args:
            db_path: Path to SQLite database file
            ttl_days: Time-to-live in days (default: 30)
        """
        self.db_path = db_path
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self._init_db()
        logger.info(
            "Initialized TMDB cache",
            db_path=str(db_path),
            ttl_days=ttl_days,
        )

    def _init_db(self):
        """Initialize database schema if not exists."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires
                ON cache(expires_at)
            """)
            conn.commit()
            logger.debug("Cache database schema initialized")
        finally:
            conn.close()

    def get(self, key: str) -> Optional[dict]:
        """Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value as dict, or None if not found or expired
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT value FROM cache WHERE key = ? AND expires_at > ?",
                (key, int(time.time())),
            )
            row = cursor.fetchone()

            if row:
                logger.debug("Cache hit", key=key)
                return json.loads(row[0])

            logger.debug("Cache miss", key=key)
            return None
        finally:
            conn.close()

    def set(self, key: str, value: dict):
        """Cache value with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            now = int(time.time())
            expires_at = now + self.ttl_seconds
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, json.dumps(value), expires_at, now),
            )
            conn.commit()
            logger.debug("Cached value", key=key, expires_at=expires_at)
        finally:
            conn.close()

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (int(time.time()),),
            )
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.info("Cleaned up expired cache entries", count=count)
            return count
        finally:
            conn.close()

    def clear(self):
        """Clear all cache entries."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("DELETE FROM cache")
            conn.commit()
            logger.info("Cache cleared")
        finally:
            conn.close()

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats (total, expired, valid)
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            now = int(time.time())

            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            total = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at < ?",
                (now,),
            )
            expired = cursor.fetchone()[0]

            return {
                "total": total,
                "expired": expired,
                "valid": total - expired,
            }
        finally:
            conn.close()
