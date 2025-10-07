"""
Query result caching utilities supporting Redis and in-memory backends.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Optional

try:
    import redis
    from redis import Redis
except ImportError:  # pragma: no cover - redis optional
    redis = None
    Redis = None  # type: ignore

from .config import settings


logger = logging.getLogger(__name__)


class InMemoryCache:
    """Simple thread-safe in-memory cache with TTL semantics."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Any] = {}
        self._expirations: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            expiry = self._expirations.get(key)
            if expiry and expiry < time.time():
                self._store.pop(key, None)
                self._expirations.pop(key, None)
                return None
            return self._store.get(key)

    def set(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            self._store[key] = value
            self._expirations[key] = time.time() + self.ttl_seconds


class QueryCache:
    """High-level cache facade for query results."""

    def __init__(self, enabled: bool, url: Optional[str], ttl_seconds: int) -> None:
        self.enabled = enabled
        self.ttl_seconds = ttl_seconds
        self._backend: Optional[Any] = None
        self._backend_type = "none"

        if not enabled:
            logger.info("Query cache disabled via configuration.")
            return

        if url and redis is not None:
            try:
                self._backend = redis.Redis.from_url(url, decode_responses=True)
                self._backend.ping()
                self._backend_type = "redis"
                logger.info("Query cache using Redis backend at %s", url)
                return
            except Exception as exc:  # pragma: no cover - connectivity failure
                logger.warning("Failed to initialize Redis cache (%s). Falling back to memory.", exc)

        # Fallback to in-memory cache
        self._backend = InMemoryCache(ttl_seconds)
        self._backend_type = "memory"
        logger.info("Query cache using in-memory backend with TTL=%ss", ttl_seconds)

    @staticmethod
    def _normalize_key(sql: str) -> str:
        digest = hashlib.sha1(sql.strip().encode("utf-8")).hexdigest()
        return f"text2sql:query:{digest}"

    def get(self, sql: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or not self._backend:
            return None

        key = self._normalize_key(sql)

        if self._backend_type == "redis":
            raw = self._backend.get(key)
            if raw:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Failed to decode cached payload for key %s", key)
                    self._backend.delete(key)
            return None

        if self._backend_type == "memory":
            return self._backend.get(key)  # type: ignore[return-value]

        return None

    def set(self, sql: str, payload: Dict[str, Any]) -> None:
        if not self.enabled or not self._backend:
            return

        key = self._normalize_key(sql)

        if self._backend_type == "redis":
            serialized = json.dumps(payload)
            self._backend.setex(key, self.ttl_seconds, serialized)
        elif self._backend_type == "memory":
            self._backend.set(key, payload)  # type: ignore[arg-type]

    def backend(self) -> str:
        """Return the active backend type."""
        return self._backend_type

    def clear(self) -> None:
        """Remove cached entries (used primarily in testing)."""
        if not self.enabled or not self._backend:
            return

        if self._backend_type == "redis":
            pattern = "text2sql:query:*"
            for key in self._backend.scan_iter(match=pattern):
                self._backend.delete(key)
        elif self._backend_type == "memory":
            self._backend = InMemoryCache(self.ttl_seconds)


# Global cache instance shared across modules
query_cache = QueryCache(
    enabled=settings.cache_enabled,
    url=settings.cache_url,
    ttl_seconds=settings.cache_ttl_seconds,
)
