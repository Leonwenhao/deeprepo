"""Tests for tool_use-aware code extraction in RLMEngine."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from deeprepo.llm_clients import TokenUsage
from deeprepo.rlm_scaffold import RLMEngine


@pytest.fixture
def engine():
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    return RLMEngine(root_client=root, sub_client=sub, usage=usage, verbose=False)


def test_extract_code_from_anthropic_tool_use(engine):
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Running analysis."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="execute_python",
                input={"code": "print('hello from tool')", "reasoning": "Inspect files."},
            ),
        ]
    )

    code_blocks, tool_use_info = engine._extract_code_from_response(response)

    assert code_blocks == ["print('hello from tool')"]
    assert tool_use_info == [{"id": "toolu_1"}]


def test_extract_code_from_openai_tool_calls(engine):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="I will run code now.",
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="execute_python",
                                arguments='{"code":"x = 1\\nprint(x)","reasoning":"Quick check."}',
                            ),
                        )
                    ],
                )
            )
        ]
    )

    code_blocks, tool_use_info = engine._extract_code_from_response(response)

    assert code_blocks == ["x = 1\nprint(x)"]
    assert tool_use_info == [{"id": "call_1"}]


def test_extract_code_falls_back_to_legacy_parser_when_no_tool_use(engine):
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text="Try this:\n```python\nx = 1\nprint(x)\n```",
            )
        ]
    )

    code_blocks, tool_use_info = engine._extract_code_from_response(response)

    assert len(code_blocks) == 1
    assert "x = 1" in code_blocks[0]
    assert "print(x)" in code_blocks[0]
    assert tool_use_info == []
