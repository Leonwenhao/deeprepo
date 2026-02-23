"""Tests for SubModelClient.batch() in sync and async contexts."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from deeprepo.llm_clients import SubModelClient, TokenUsage


def _fake_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    )


def _build_client():
    async def _fake_create(*, model, messages, max_tokens, temperature):
        user_prompt = messages[-1]["content"]
        return _fake_response(f"ok:{user_prompt}")

    create_mock = AsyncMock(side_effect=_fake_create)
    async_client = MagicMock()
    async_client.chat.completions.create = create_mock

    usage = TokenUsage()
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False), patch(
        "deeprepo.llm_clients.openai.OpenAI", return_value=MagicMock()
    ), patch("deeprepo.llm_clients.openai.AsyncOpenAI", return_value=async_client):
        client = SubModelClient(usage=usage, use_cache=False)

    return client, usage, create_mock


def test_batch_sync_context_still_works():
    """batch() should keep working from normal synchronous callers."""
    client, usage, _ = _build_client()

    results = client.batch(["a", "b", "c"], system="sys", max_tokens=32, max_concurrent=2)

    assert results == ["ok:a", "ok:b", "ok:c"]
    assert usage.sub_calls == 3
    assert usage.sub_input_tokens == 33
    assert usage.sub_output_tokens == 21


def test_batch_inside_existing_event_loop():
    """batch() should not raise when called from a running event loop."""
    client, usage, _ = _build_client()

    async def _run_inside_loop():
        return client.batch(["x", "y"], system="sys", max_tokens=32, max_concurrent=2)

    results = asyncio.run(_run_inside_loop())

    assert results == ["ok:x", "ok:y"]
    assert usage.sub_calls == 2
    assert usage.sub_input_tokens == 22
    assert usage.sub_output_tokens == 14
