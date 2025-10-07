"""
Tests for query result caching utilities.
"""

from src.cache import QueryCache


def test_in_memory_cache_roundtrip():
    cache = QueryCache(enabled=True, url=None, ttl_seconds=60)
    sql = "SELECT 1;"
    payload = {"results": [{"value": 1}], "columns": ["value"], "row_count": 1, "execution_time": 0.01}

    cache.set(sql, payload)
    cached = cache.get(sql)

    assert cached == payload
    assert cache.backend() in {"memory", "redis", "none"}
