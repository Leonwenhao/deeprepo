"""Tests for tool_choice passthrough on root model clients."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from deeprepo.llm_clients import OpenRouterRootClient, RootModelClient, TokenUsage


def test_anthropic_root_client_forwards_tool_choice():
    usage = TokenUsage()
    client = RootModelClient.__new__(RootModelClient)
    client.client = MagicMock()
    client.model = "claude-sonnet-4-6"
    client.usage = usage

    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=3, output_tokens=2),
        content=[SimpleNamespace(type="text", text="ok")],
    )
    client.client.messages.create.return_value = response

    tools = [
        {
            "name": "execute_python",
            "description": "run code",
            "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}},
        }
    ]

    result = client.complete(
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
        tool_choice={"type": "any"},
        stream=False,
    )

    assert result is response
    kwargs = client.client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "any"}


def test_openrouter_root_client_converts_any_tool_choice_to_required():
    usage = TokenUsage()
    client = OpenRouterRootClient.__new__(OpenRouterRootClient)
    client.client = MagicMock()
    client.model = "minimax/minimax-m2.5"
    client.usage = usage

    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=1),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="ok",
                    tool_calls=None,
                )
            )
        ],
    )
    client.client.chat.completions.create.return_value = response

    tools = [
        {
            "name": "execute_python",
            "description": "run code",
            "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}},
        }
    ]

    result = client.complete(
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
        tool_choice={"type": "any"},
        stream=False,
    )

    assert result is response
    kwargs = client.client.chat.completions.create.call_args.kwargs
    assert kwargs["tool_choice"] == "required"
