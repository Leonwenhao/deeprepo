"""Unit tests for retry utilities."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from deeprepo.utils import async_retry_with_backoff, retry_with_backoff


def _status_error(status_code: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(status_code=status_code, request=request)
    return openai.APIStatusError("error", response=response, body={})


def test_retry_on_500():
    """Retries transient 5xx errors and eventually succeeds."""
    call_count = 0

    @retry_with_backoff(max_retries=3, base_delay=0.1)
    def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise _status_error(500)
        return "ok"

    with patch("deeprepo.utils.random.uniform", return_value=0.0), patch("deeprepo.utils.time.sleep") as sleep_mock:
        result = flaky_call()

    assert result == "ok"
    assert call_count == 3
    assert sleep_mock.call_count == 2


def test_no_retry_on_400():
    """Does not retry non-transient 4xx validation/auth failures."""
    call_count = 0

    @retry_with_backoff(max_retries=3, base_delay=0.1)
    def bad_request_call():
        nonlocal call_count
        call_count += 1
        raise _status_error(400)

    with patch("deeprepo.utils.random.uniform", return_value=0.0), patch("deeprepo.utils.time.sleep") as sleep_mock:
        with pytest.raises(openai.APIStatusError):
            bad_request_call()

    assert call_count == 1
    sleep_mock.assert_not_called()


def test_max_retries_exceeded():
    """Raises after max_retries + 1 attempts for persistent transient errors."""
    call_count = 0

    @retry_with_backoff(max_retries=2, base_delay=0.1)
    def always_fails():
        nonlocal call_count
        call_count += 1
        raise _status_error(500)

    with patch("deeprepo.utils.random.uniform", return_value=0.0), patch("deeprepo.utils.time.sleep") as sleep_mock:
        with pytest.raises(openai.APIStatusError):
            always_fails()

    assert call_count == 3
    assert sleep_mock.call_count == 2


def test_async_retry_on_timeout():
    """Async wrapper retries transient timeout errors and succeeds."""

    async def _run():
        call_count = 0
        request = httpx.Request("POST", "https://example.test/v1/chat/completions")

        async def flaky_async_call():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise openai.APITimeoutError(request=request)
            return "ok"

        sleep_mock = AsyncMock()
        with patch("deeprepo.utils.random.uniform", return_value=0.0), patch(
            "deeprepo.utils.asyncio.sleep", sleep_mock
        ):
            result = await async_retry_with_backoff(flaky_async_call, max_retries=3, base_delay=0.1)

        assert result == "ok"
        assert call_count == 3
        assert sleep_mock.await_count == 2

    asyncio.run(_run())
