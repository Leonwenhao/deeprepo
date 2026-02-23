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


# ---------------------------------------------------------------------------
# T1 — strip_tool_use with tool_use-only response (no text blocks at all)
# ---------------------------------------------------------------------------
def test_strip_tool_use_only_response_no_empty_text(engine):
    """After stripping a tool_use-only response, no empty text blocks remain."""
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="execute_python",
                input={"code": "print(1)"},
            ),
        ]
    )

    messages = []
    engine._append_assistant_message(messages, response, strip_tool_use=True)

    assert len(messages) == 1
    content = messages[0]["content"]
    assert isinstance(content, list)

    for block in content:
        if block.get("type") == "text":
            assert block["text"].strip(), f"Empty text block found: {block}"


# ---------------------------------------------------------------------------
# T2 — strip_tool_use with mixed response preserves text, no empty blocks
# ---------------------------------------------------------------------------
def test_strip_tool_use_mixed_response_preserves_text(engine):
    """Stripping tool_use from a mixed response keeps text intact, no empties."""
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Analyzing the project structure."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_2",
                name="execute_python",
                input={"code": "print('hi')"},
            ),
        ]
    )

    messages = []
    engine._append_assistant_message(messages, response, strip_tool_use=True)

    assert len(messages) == 1
    content = messages[0]["content"]
    assert isinstance(content, list)

    text_blocks = [b for b in content if b.get("type") == "text"]
    assert len(text_blocks) == 1
    assert "Analyzing" in text_blocks[0]["text"]

    for block in content:
        if block.get("type") == "text":
            assert block["text"].strip(), f"Empty text block found: {block}"


# ---------------------------------------------------------------------------
# T3 — _validate_messages catches and fixes empty text blocks
# ---------------------------------------------------------------------------
def test_validate_messages_catches_empty_text(engine):
    """Pre-flight validation must fix empty text content blocks."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": [{"type": "text", "text": ""}]},
        {"role": "assistant", "content": [
            {"type": "text", "text": "  "},
            {"type": "text", "text": "Valid text"},
        ]},
    ]

    engine._validate_messages(messages)

    # First message (plain string) should be untouched
    assert messages[0]["content"] == "Hello"

    # Second message had only an empty block — should get placeholder
    content1 = messages[1]["content"]
    assert isinstance(content1, list)
    assert len(content1) == 1
    assert content1[0]["text"].strip()  # non-empty

    # Third message: empty block removed, valid block preserved
    content2 = messages[2]["content"]
    assert isinstance(content2, list)
    assert len(content2) == 1
    assert content2[0]["text"] == "Valid text"


# ---------------------------------------------------------------------------
# T4 — End-to-end: first turn message construction has no empty text blocks
# ---------------------------------------------------------------------------
def test_first_turn_messages_valid(engine):
    """The initial message list for the first API call must pass validation."""
    messages = [{"role": "user", "content": "Analyze this codebase."}]

    # Simulate a tool_use-only response on the first turn (model returns no text)
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                id="toolu_first",
                name="execute_python",
                input={"code": "import os; print(os.listdir('.'))"},
            ),
        ]
    )

    # This is the "no code blocks extracted" path where strip_tool_use=True
    engine._append_assistant_message(messages, response, strip_tool_use=True)
    messages.append({
        "role": "user",
        "content": "Please use the execute_python tool to continue.",
    })

    # Run pre-flight validation — should not raise
    engine._validate_messages(messages)

    # Verify no empty text blocks anywhere
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    assert block["text"].strip(), f"Empty text block in: {msg}"
