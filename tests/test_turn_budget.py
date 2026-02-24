"""Tests for turn-budget control and partial output salvage in RLMEngine."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

from deeprepo.domains.base import DomainConfig
from deeprepo.llm_clients import TokenUsage
from deeprepo.rlm_scaffold import RLMEngine


def _domain() -> DomainConfig:
    return DomainConfig(
        name="code",
        label="Codebase Analysis",
        description="test",
        loader=lambda _path: {
            "codebase": {"a.py": "print('hi')"},
            "file_tree": "a.py",
            "metadata": {"total_files": 1, "total_chars": 10},
        },
        format_metadata=lambda _metadata: "meta",
        root_system_prompt="system",
        sub_system_prompt="sub",
        user_prompt_template="{metadata_str}\n{file_tree}",
        baseline_system_prompt="baseline",
        data_variable_name="codebase",
    )


def _tool_response(turn: int, code: str):
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                id=f"toolu_{turn}",
                name="execute_python",
                input={"code": code},
            ),
        ]
    )


def _text_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def _text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)
    return str(content)


def test_turn_countdown_injected_and_tool_choice_forced_on_final_two_turns():
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    engine = RLMEngine(
        root_client=root,
        sub_client=sub,
        usage=usage,
        max_turns=4,
        verbose=False,
    )

    responses = [
        _tool_response(1, "print('turn1')"),
        _tool_response(2, "print('turn2')"),
        _tool_response(3, "print('turn3')"),
        _tool_response(4, "print('turn4')"),
    ]
    captured = []

    def _complete(**kwargs):
        captured.append({
            "tool_choice": kwargs.get("tool_choice"),
            "last_user": deepcopy(kwargs["messages"][-1]),
        })
        return responses[len(captured) - 1]

    root.complete.side_effect = _complete

    result = engine.analyze(".", domain=_domain())

    assert result["status"] == "partial"
    assert "Partial REPL Findings" in result["analysis"]

    assert len(captured) == 4
    assert captured[0]["tool_choice"] is None
    assert captured[1]["tool_choice"] is None
    assert captured[2]["tool_choice"] == {"type": "any"}
    assert captured[3]["tool_choice"] == {"type": "any"}

    for idx, call in enumerate(captured, start=1):
        assert call["last_user"]["role"] == "user"
        text = _text_from_content(call["last_user"]["content"])
        assert f"[Turn {idx}/4" in text


def test_max_turns_without_output_marks_failed():
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    engine = RLMEngine(
        root_client=root,
        sub_client=sub,
        usage=usage,
        max_turns=2,
        verbose=False,
    )
    root.complete.side_effect = [
        _tool_response(1, "x = 1"),
        _tool_response(2, "y = 2"),
    ]

    result = engine.analyze(".", domain=_domain())

    assert result["status"] == "failed"
    assert result["analysis"] == "[Analysis incomplete — max turns reached]"


def test_last_assistant_prose_is_salvaged_when_no_code_runs():
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    engine = RLMEngine(
        root_client=root,
        sub_client=sub,
        usage=usage,
        max_turns=1,
        verbose=False,
    )
    root.complete.return_value = _text_response("Findings: likely auth bug in middleware.")

    result = engine.analyze(".", domain=_domain())

    assert result["status"] == "partial"
    assert "Latest Model Notes" in result["analysis"]
    assert "auth bug in middleware" in result["analysis"]
