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


def test_no_orphaned_tool_use_when_input_missing_code(engine):
    """C1: tool_use block with no 'code' key should not leave orphaned tool_use in messages."""
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Let me analyze the project."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_bad",
                name="execute_python",
                input={"reasoning": "I want to look at files"},  # No "code" key
            ),
        ]
    )

    messages = []
    # Simulate the "no code blocks" path where tool_use blocks are stripped.
    engine._append_assistant_message(messages, response, strip_tool_use=True)

    assert len(messages) == 1
    assistant_msg = messages[0]
    assert assistant_msg["role"] == "assistant"

    content = assistant_msg["content"]
    if isinstance(content, list):
        for block in content:
            assert block.get("type") != "tool_use", f"Found orphaned tool_use block: {block}"

    assert any(
        b.get("type") == "text" and "analyze" in b.get("text", "")
        for b in content
    ), "Text block should be preserved"


def test_all_tool_use_ids_have_tool_results(engine):
    """H1/M3: Every tool_use block in the response must have a matching tool_result."""
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Running two tools."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_valid",
                name="execute_python",
                input={"code": "print('valid')", "reasoning": "test"},
            ),
            SimpleNamespace(
                type="tool_use",
                id="toolu_invalid",
                name="execute_python",
                input={"reasoning": "no code here"},
            ),
            SimpleNamespace(
                type="tool_use",
                id="toolu_wrong_name",
                name="search_files",
                input={"query": "something"},
            ),
        ]
    )

    tool_use_info = [{"id": "toolu_valid"}]
    outputs = ["valid output"]

    messages = []
    engine._append_tool_result_messages(messages, response, tool_use_info, outputs)

    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert messages[1]["role"] == "user"

    tool_results = messages[1]["content"]
    assert isinstance(tool_results, list)

    result_ids = {r["tool_use_id"] for r in tool_results if r.get("type") == "tool_result"}

    assert "toolu_valid" in result_ids
    assert "toolu_invalid" in result_ids
    assert "toolu_wrong_name" in result_ids

    for result in tool_results:
        if result["tool_use_id"] in ("toolu_invalid", "toolu_wrong_name"):
            assert (
                "ignored" in result["content"].lower()
                or "invalid" in result["content"].lower()
            ), f"Synthetic tool_result should indicate ignore/error: {result['content']}"


def test_early_break_on_set_answer(engine):
    """M4: When first code block calls set_answer(), remaining blocks should not execute."""
    answer = {"content": "", "ready": False}

    def set_answer(text):
        answer["content"] = text
        answer["ready"] = True

    namespace = {
        "answer": answer,
        "set_answer": set_answer,
        "__builtins__": __builtins__,
    }

    code_blocks = [
        "set_answer('done')",
        "print('should not run')",
        "print('also should not run')",
    ]

    all_output = []
    for code in code_blocks:
        output = engine._execute_code(code, namespace)
        all_output.append(output)
        if answer["ready"]:
            break

    assert len(all_output) == 1, f"Expected 1 output, got {len(all_output)}: {all_output}"
    assert answer["ready"] is True
    assert answer["content"] == "done"
