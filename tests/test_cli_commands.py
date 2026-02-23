"""Tests for CLI command handlers (init and context)."""

import argparse
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deeprepo.config_manager import ConfigManager


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    src = Path(__file__).parent / "fixtures" / "sample_project"
    dst = tmp_path / "sample_project"
    shutil.copytree(src, dst)
    return dst


def _make_mock_usage() -> MagicMock:
    usage = MagicMock()
    usage.total_cost = 0.25
    usage.root_cost = 0.20
    usage.sub_cost = 0.05
    usage.sub_calls = 3
    usage.root_calls = 5
    usage.summary.return_value = "Cost: $0.25"
    return usage


def test_cmd_init_creates_deeprepo_dir(sample_project: Path) -> None:
    """cmd_init creates .deeprepo/ with PROJECT.md and COLD_START.md."""
    from deeprepo.cli_commands import cmd_init

    mock_result = {
        "analysis": (
            "## Identity\nPython\n"
            "## Architecture\nFastAPI\n"
            "## Module Map\n\n### src/\nCore app.\nEntry: main.py\n"
            "## Patterns & Conventions\nUse type hints.\n"
            "## Dependency Graph\nsrc -> utils\n"
            "## Tech Debt & Known Issues\nNone\n"
        ),
        "turns": 3,
        "usage": _make_mock_usage(),
    }

    args = argparse.Namespace(
        path=str(sample_project),
        force=False,
        quiet=True,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        cmd_init(args)

    assert (sample_project / ".deeprepo" / "config.yaml").is_file()
    assert (sample_project / ".deeprepo" / "PROJECT.md").is_file()
    assert (sample_project / ".deeprepo" / "COLD_START.md").is_file()


def test_cmd_init_fails_if_already_initialized(sample_project: Path) -> None:
    """cmd_init exits if .deeprepo/ exists and --force is not set."""
    from deeprepo.cli_commands import cmd_init

    cm = ConfigManager(str(sample_project))
    cm.initialize()

    args = argparse.Namespace(
        path=str(sample_project),
        force=False,
        quiet=True,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with pytest.raises(SystemExit):
        cmd_init(args)


def test_cmd_context_outputs_cold_start(sample_project: Path, capsys) -> None:
    """cmd_context prints COLD_START.md content."""
    from deeprepo.cli_commands import cmd_context, cmd_init

    mock_result = {
        "analysis": (
            "## Identity\nPython\n"
            "## Architecture\nFastAPI\n"
            "## Module Map\n\n### src/\nCore app.\nEntry: main.py\n"
            "## Patterns & Conventions\nUse type hints.\n"
            "## Dependency Graph\nsrc -> utils\n"
            "## Tech Debt & Known Issues\nNone\n"
        ),
        "turns": 3,
        "usage": _make_mock_usage(),
    }

    init_args = argparse.Namespace(
        path=str(sample_project),
        force=False,
        quiet=True,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )
    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        cmd_init(init_args)

    context_args = argparse.Namespace(path=str(sample_project), copy=False, format="markdown")
    cmd_context(context_args)

    captured = capsys.readouterr()
    assert "Identity" in captured.out


def test_cmd_context_cursor_format(sample_project: Path, capsys) -> None:
    """cmd_context --format cursor writes .cursorrules file."""
    from deeprepo.cli_commands import cmd_context, cmd_init

    mock_result = {
        "analysis": (
            "## Identity\nPython\n"
            "## Architecture\nFastAPI\n"
            "## Module Map\n\n### src/\nCore app.\nEntry: main.py\n"
            "## Patterns & Conventions\nUse type hints.\n"
            "## Tech Debt & Known Issues\nNone\n"
        ),
        "turns": 3,
        "usage": _make_mock_usage(),
    }

    init_args = argparse.Namespace(
        path=str(sample_project),
        force=False,
        quiet=True,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )
    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        cmd_init(init_args)

    context_args = argparse.Namespace(path=str(sample_project), copy=False, format="cursor")
    cmd_context(context_args)

    cursorrules = sample_project / ".cursorrules"
    assert cursorrules.is_file()
    content = cursorrules.read_text(encoding="utf-8")
    assert "Identity" in content

    captured = capsys.readouterr()
    assert ".cursorrules" in captured.out


def test_cmd_context_fails_if_not_initialized(tmp_path: Path) -> None:
    """cmd_context exits if .deeprepo/ does not exist."""
    from deeprepo.cli_commands import cmd_context

    args = argparse.Namespace(path=str(tmp_path), copy=False, format="markdown")
    with pytest.raises(SystemExit):
        cmd_context(args)
