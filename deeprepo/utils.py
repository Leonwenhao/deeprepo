"""Retry utilities for LLM API calls."""

import asyncio
import random
import sys
import time
from functools import wraps

MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0
JITTER_FACTOR = 0.5


def _is_retryable(exc: Exception) -> bool:
    """Determine if an exception should be retried."""
    import anthropic
    import openai

    if isinstance(
        exc,
        (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        ),
    ):
        return True

    if isinstance(exc, (anthropic.APIStatusError, openai.APIStatusError)):
        return exc.status_code in (429, 500, 502, 503, 504)

    return False


def retry_with_backoff(max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY):
    """Decorator that retries a sync function with exponential backoff + jitter."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if not _is_retryable(exc):
                        raise
                    last_exception = exc
                    if attempt == max_retries:
                        raise

                    delay = min(base_delay * (2 ** attempt), MAX_DELAY)
                    jitter = random.uniform(0, JITTER_FACTOR * delay)
                    total_delay = delay + jitter
                    print(
                        f"[RETRY] Attempt {attempt + 1}/{max_retries} failed: {exc}",
                        file=sys.stderr,
                    )
                    print(f"[RETRY] Retrying in {total_delay:.1f}s...", file=sys.stderr)
                    time.sleep(total_delay)

            raise last_exception

        return wrapper

    return decorator


async def async_retry_with_backoff(
    coro_func,
    *args,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    **kwargs,
):
    """Async retry wrapper for coroutine callables with exponential backoff."""
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            last_exception = exc
            if attempt == max_retries:
                raise

            delay = min(base_delay * (2 ** attempt), MAX_DELAY)
            jitter = random.uniform(0, JITTER_FACTOR * delay)
            total_delay = delay + jitter
            print(
                f"[RETRY] Async attempt {attempt + 1}/{max_retries} failed: {exc}",
                file=sys.stderr,
            )
            print(f"[RETRY] Retrying in {total_delay:.1f}s...", file=sys.stderr)
            await asyncio.sleep(total_delay)

    raise last_exception
