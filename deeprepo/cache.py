"""Content-hash cache for sub-LLM query results."""

import hashlib
import json
import os
import time


CACHE_DIR = os.path.expanduser("~/.cache/deeprepo")
CACHE_EXPIRY_DAYS = 7


def _cache_key(prompt: str, system: str, model: str) -> str:
    """Generate a cache key from the prompt, system message, and model."""
    content = f"{model}||{system}||{prompt}"
    return hashlib.sha256(content.encode()).hexdigest()


def get_cached(prompt: str, system: str, model: str) -> str | None:
    """Return cached result if it exists and hasn't expired."""
    key = _cache_key(prompt, system, model)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data["timestamp"] > CACHE_EXPIRY_DAYS * 86400:
            os.remove(cache_file)
            return None
        return data["result"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def set_cached(prompt: str, system: str, model: str, result: str) -> None:
    """Store a result in the cache."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        key = _cache_key(prompt, system, model)
        cache_file = os.path.join(CACHE_DIR, f"{key}.json")

        data = {
            "timestamp": time.time(),
            "model": model,
            "prompt_hash": key,
            "result": result,
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        return


def clear_cache() -> int:
    """Delete all cached results. Returns number of entries deleted."""
    import shutil

    if not os.path.exists(CACHE_DIR):
        return 0
    try:
        entries = len([f for f in os.listdir(CACHE_DIR) if f.endswith(".json")])
        shutil.rmtree(CACHE_DIR)
        return entries
    except OSError:
        return 0


def cache_stats() -> dict:
    """Return cache statistics."""
    if not os.path.exists(CACHE_DIR):
        return {"entries": 0, "size_mb": 0.0}
    try:
        files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
        total_size = sum(
            os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files
        )
        return {
            "entries": len(files),
            "size_mb": round(total_size / 1024 / 1024, 2),
        }
    except OSError:
        return {"entries": 0, "size_mb": 0.0}
