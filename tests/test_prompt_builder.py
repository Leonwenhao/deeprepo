"""Tests for TUI prompt builder."""

from pathlib import Path

import pytest

from deeprepo.tui.prompt_builder import PromptBuilder


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal project with .deeprepo/ for testing."""
    dr = tmp_path / ".deeprepo"
    dr.mkdir()
    (dr / "config.yaml").write_text("project_name: TestProject\nversion: 1\n", encoding="utf-8")
    (dr / "COLD_START.md").write_text(
        "# TestProject Cold Start\n\nThis is the project context.\n",
        encoding="utf-8",
    )
    return dr


def test_builder_creation() -> None:
    builder = PromptBuilder(".")
    assert builder is not None
    assert builder.project_path


def test_build_without_deeprepo_returns_error(tmp_path: Path) -> None:
    builder = PromptBuilder(str(tmp_path))
    result = builder.build("fix bug")

    assert result["status"] == "error"
    assert "init" in result["message"].lower()


def test_build_assembles_cold_start_and_ask(tmp_path: Path, monkeypatch) -> None:
    _setup_project(tmp_path)
    builder = PromptBuilder(str(tmp_path))
    monkeypatch.setattr(builder, "_copy_to_clipboard", lambda text: True)

    result = builder.build("fix the WebSocket bug")

    assert result["status"] == "success"
    prompt = result["data"]["prompt"]
    assert "TestProject Cold Start" in prompt
    assert "fix the WebSocket bug" in prompt
    assert result["data"]["token_estimate"] > 0


def test_build_includes_matching_files(tmp_path: Path, monkeypatch) -> None:
    _setup_project(tmp_path)
    (tmp_path / "websocket.py").write_text("def handle_websocket():\n    pass\n", encoding="utf-8")
    builder = PromptBuilder(str(tmp_path))
    monkeypatch.setattr(builder, "_copy_to_clipboard", lambda text: True)

    result = builder.build("fix the websocket handler")

    assert result["status"] == "success"
    assert any(path.endswith("websocket.py") for path in result["data"]["files_included"])


def test_build_excludes_non_matching_files(tmp_path: Path, monkeypatch) -> None:
    _setup_project(tmp_path)
    (tmp_path / "websocket.py").write_text("def handle_websocket():\n    pass\n", encoding="utf-8")
    (tmp_path / "unrelated.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    builder = PromptBuilder(str(tmp_path))
    monkeypatch.setattr(builder, "_copy_to_clipboard", lambda text: True)

    result = builder.build("fix websocket")

    assert result["status"] == "success"
    included = result["data"]["files_included"]
    assert any(path.endswith("websocket.py") for path in included)
    assert not any(path.endswith("unrelated.py") for path in included)


def test_build_respects_token_budget(tmp_path: Path, monkeypatch) -> None:
    _setup_project(tmp_path)
    (tmp_path / "websocket.py").write_text("x" * 5000, encoding="utf-8")
    builder = PromptBuilder(str(tmp_path), token_budget=100)
    monkeypatch.setattr(builder, "_copy_to_clipboard", lambda text: True)

    result = builder.build("websocket")

    assert result["status"] == "success"
    assert not result["data"]["files_included"]


def test_find_relevant_files_scores_filename_higher(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    (tmp_path / "router.py").write_text("def route():\n    pass\n", encoding="utf-8")
    nested = tmp_path / "utils" / "router"
    nested.mkdir(parents=True)
    (nested / "helpers.py").write_text("def helper():\n    pass\n", encoding="utf-8")

    builder = PromptBuilder(str(tmp_path))
    files = builder._find_relevant_files("router")

    assert len(files) >= 2
    assert files[0][0].endswith("router.py")


def test_cold_start_is_cached(tmp_path: Path, monkeypatch) -> None:
    _setup_project(tmp_path)
    builder = PromptBuilder(str(tmp_path))
    monkeypatch.setattr(builder, "_copy_to_clipboard", lambda text: True)

    first = builder.build("websocket")
    assert first["status"] == "success"
    assert builder._cold_start is not None

    second = builder.build("router")
    assert second["status"] == "success"
    assert builder._cold_start is not None


def test_clipboard_failure_returns_copied_false(tmp_path: Path, monkeypatch) -> None:
    _setup_project(tmp_path)
    builder = PromptBuilder(str(tmp_path))

    pyperclip = pytest.importorskip("pyperclip")

    def _boom(_: str) -> None:
        raise RuntimeError("clipboard unavailable")

    monkeypatch.setattr(pyperclip, "copy", _boom)

    result = builder.build("fix websocket")

    assert result["status"] == "success"
    assert result["data"]["copied"] is False


def test_assemble_prompt_structure(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    builder = PromptBuilder(str(tmp_path))

    prompt = builder._assemble_prompt(
        "# TestProject Cold Start\n\nThis is context.\n",
        [("websocket.py", "def handle_websocket():\n    pass\n")],
        "fix websocket",
    )

    assert "# Project Context" in prompt
    assert "# Relevant Files" in prompt
    assert "# Your Task" in prompt


def test_no_matching_files_still_succeeds(tmp_path: Path, monkeypatch) -> None:
    _setup_project(tmp_path)
    (tmp_path / "websocket.py").write_text("def handle_websocket():\n    pass\n", encoding="utf-8")
    builder = PromptBuilder(str(tmp_path))
    monkeypatch.setattr(builder, "_copy_to_clipboard", lambda text: True)

    result = builder.build("quantum singularity")

    assert result["status"] == "success"
    assert result["data"]["files_included"] == []
    prompt = result["data"]["prompt"]
    assert "TestProject Cold Start" in prompt
    assert "quantum singularity" in prompt
