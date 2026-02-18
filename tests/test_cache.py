"""Tests for sub-LLM result cache."""

import json
import os
import time

import pytest

from deeprepo.cache import (
    CACHE_DIR,
    _cache_key,
    cache_stats,
    clear_cache,
    get_cached,
    set_cached,
)


@pytest.fixture(autouse=True)
def clean_cache(tmp_path, monkeypatch):
    """Use a temporary directory for cache during tests."""
    test_cache_dir = str(tmp_path / "deeprepo_cache")
    monkeypatch.setattr("deeprepo.cache.CACHE_DIR", test_cache_dir)
    yield test_cache_dir


def test_cache_miss_returns_none():
    """get_cached returns None when no cached entry exists."""
    assert get_cached("prompt", "system", "model/x") is None


def test_cache_hit_after_set():
    """set_cached stores a result and get_cached retrieves it."""
    set_cached("prompt", "system", "model/x", "result text")
    assert get_cached("prompt", "system", "model/x") == "result text"


def test_cache_key_includes_model():
    """Different models produce different cache keys."""
    key_a = _cache_key("prompt", "system", "model/a")
    key_b = _cache_key("prompt", "system", "model/b")
    assert key_a != key_b


def test_cache_expiry(clean_cache):
    """Expired entries are treated as cache misses."""
    set_cached("prompt", "system", "model/x", "old result")

    # Patch the stored timestamp to be 8 days ago
    key = _cache_key("prompt", "system", "model/x")
    cache_file = os.path.join(clean_cache, f"{key}.json")
    with open(cache_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["timestamp"] = time.time() - 8 * 86400
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    assert get_cached("prompt", "system", "model/x") is None
    assert not os.path.exists(cache_file)


def test_clear_cache():
    """clear_cache removes all entries."""
    set_cached("p1", "s", "m", "r1")
    set_cached("p2", "s", "m", "r2")
    deleted = clear_cache()
    assert deleted == 2
    assert get_cached("p1", "s", "m") is None
    assert get_cached("p2", "s", "m") is None


def test_cache_stats():
    """cache_stats reports correct entry count."""
    assert cache_stats()["entries"] == 0
    set_cached("p1", "s", "m", "r1")
    set_cached("p2", "s", "m", "r2")
    stats = cache_stats()
    assert stats["entries"] == 2
    assert stats["size_mb"] >= 0
