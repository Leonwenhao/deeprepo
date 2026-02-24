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


def _make_analysis_result(status: str = "completed") -> dict:
    return {
        "analysis": (
            "## Identity\nPython\n"
            "## Architecture\nFastAPI\n"
            "## Module Map\n\n### src/\nCore app.\nEntry: main.py\n"
            "## Patterns & Conventions\nUse type hints.\n"
            "## Dependency Graph\nsrc -> utils\n"
            "## Tech Debt & Known Issues\nNone\n"
        ),
        "status": status,
        "turns": 3,
        "usage": _make_mock_usage(),
    }


def test_cmd_init_creates_deeprepo_dir(sample_project: Path) -> None:
    """cmd_init creates .deeprepo/ with PROJECT.md and COLD_START.md."""
    from deeprepo.cli_commands import cmd_init

    mock_result = _make_analysis_result("completed")

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
        quiet=False,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with pytest.raises(SystemExit):
        cmd_init(args)


def test_cmd_init_returns_error_dict_when_quiet(sample_project: Path) -> None:
    """cmd_init returns an error dict in quiet mode when already initialized."""
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

    result = cmd_init(args)
    assert result["status"] == "error"
    assert "already exists" in result["message"]
    assert "data" in result


def test_cmd_init_completed_shows_success_banner(sample_project: Path) -> None:
    """Completed analysis should show success banner + onboarding."""
    from deeprepo.cli_commands import cmd_init

    args = argparse.Namespace(
        path=str(sample_project),
        force=False,
        quiet=False,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with (
        patch("deeprepo.rlm_scaffold.run_analysis", return_value=_make_analysis_result("completed")),
        patch("deeprepo.terminal_ui.print_init_complete") as complete_mock,
        patch("deeprepo.terminal_ui.print_onboarding") as onboarding_mock,
        patch("deeprepo.terminal_ui.print_init_partial") as partial_mock,
        patch("deeprepo.terminal_ui.print_init_failed") as failed_mock,
    ):
        result = cmd_init(args)

    assert result["data"]["analysis_status"] == "completed"
    complete_mock.assert_called_once()
    onboarding_mock.assert_called_once()
    partial_mock.assert_not_called()
    failed_mock.assert_not_called()


def test_cmd_init_partial_shows_warning_without_onboarding(sample_project: Path) -> None:
    """Partial analysis should show warning banner and suppress onboarding."""
    from deeprepo.cli_commands import cmd_init

    args = argparse.Namespace(
        path=str(sample_project),
        force=False,
        quiet=False,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with (
        patch("deeprepo.rlm_scaffold.run_analysis", return_value=_make_analysis_result("partial")),
        patch("deeprepo.terminal_ui.print_init_complete") as complete_mock,
        patch("deeprepo.terminal_ui.print_onboarding") as onboarding_mock,
        patch("deeprepo.terminal_ui.print_init_partial") as partial_mock,
        patch("deeprepo.terminal_ui.print_init_failed") as failed_mock,
    ):
        result = cmd_init(args)

    assert result["data"]["analysis_status"] == "partial"
    partial_mock.assert_called_once()
    complete_mock.assert_not_called()
    onboarding_mock.assert_not_called()
    failed_mock.assert_not_called()


def test_cmd_init_failed_shows_failure_warning(sample_project: Path) -> None:
    """Failed analysis should show failure warning and suppress success banner."""
    from deeprepo.cli_commands import cmd_init

    args = argparse.Namespace(
        path=str(sample_project),
        force=False,
        quiet=False,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with (
        patch("deeprepo.rlm_scaffold.run_analysis", return_value=_make_analysis_result("failed")),
        patch("deeprepo.terminal_ui.print_init_complete") as complete_mock,
        patch("deeprepo.terminal_ui.print_onboarding") as onboarding_mock,
        patch("deeprepo.terminal_ui.print_init_partial") as partial_mock,
        patch("deeprepo.terminal_ui.print_init_failed") as failed_mock,
    ):
        result = cmd_init(args)

    assert result["data"]["analysis_status"] == "failed"
    failed_mock.assert_called_once()
    complete_mock.assert_not_called()
    onboarding_mock.assert_not_called()
    partial_mock.assert_not_called()


def test_cmd_refresh_partial_hides_success_banner(sample_project: Path) -> None:
    """Partial refresh should not show success banner."""
    from deeprepo.cli_commands import cmd_refresh

    cm = ConfigManager(str(sample_project))
    cm.initialize()

    args = argparse.Namespace(
        path=str(sample_project),
        full=True,
        quiet=False,
    )

    with (
        patch(
            "deeprepo.refresh.RefreshEngine.refresh",
            return_value={
                "changed_files": 3,
                "cost": 0.12,
                "turns": 20,
                "status": "partial",
            },
        ),
        patch("deeprepo.terminal_ui.print_refresh_complete") as complete_mock,
        patch("deeprepo.terminal_ui.print_refresh_partial") as partial_mock,
        patch("deeprepo.terminal_ui.print_refresh_failed") as failed_mock,
    ):
        result = cmd_refresh(args)

    assert result["data"]["refresh_status"] == "partial"
    complete_mock.assert_not_called()
    partial_mock.assert_called_once()
    failed_mock.assert_not_called()


def test_cmd_refresh_failed_hides_success_banner(sample_project: Path) -> None:
    """Failed refresh should not show success banner."""
    from deeprepo.cli_commands import cmd_refresh

    cm = ConfigManager(str(sample_project))
    cm.initialize()

    args = argparse.Namespace(
        path=str(sample_project),
        full=True,
        quiet=False,
    )

    with (
        patch(
            "deeprepo.refresh.RefreshEngine.refresh",
            return_value={
                "changed_files": 3,
                "cost": 0.12,
                "turns": 20,
                "status": "failed",
            },
        ),
        patch("deeprepo.terminal_ui.print_refresh_complete") as complete_mock,
        patch("deeprepo.terminal_ui.print_refresh_partial") as partial_mock,
        patch("deeprepo.terminal_ui.print_refresh_failed") as failed_mock,
    ):
        result = cmd_refresh(args)

    assert result["data"]["refresh_status"] == "failed"
    complete_mock.assert_not_called()
    partial_mock.assert_not_called()
    failed_mock.assert_called_once()


def test_cmd_context_outputs_cold_start(sample_project: Path, capsys) -> None:
    """cmd_context prints COLD_START.md content."""
    from deeprepo.cli_commands import cmd_context, cmd_init

    mock_result = _make_analysis_result("completed")

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

    mock_result = _make_analysis_result("completed")

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


def test_cmd_context_quiet_not_initialized_returns_error_dict(tmp_path: Path) -> None:
    """cmd_context quiet mode returns error dict instead of raising."""
    from deeprepo.cli_commands import cmd_context

    args = argparse.Namespace(path=str(tmp_path), copy=False, format="markdown")
    result = cmd_context(args, quiet=True)

    assert result["status"] == "error"
    assert result["message"] == "No .deeprepo/ directory found"
    assert result["data"] == {}


def test_cmd_status_quiet_returns_structured_data(sample_project: Path) -> None:
    """cmd_status quiet mode returns status payload with expected keys."""
    from deeprepo.cli_commands import cmd_status

    cm = ConfigManager(str(sample_project))
    cm.initialize()
    (sample_project / ".deeprepo" / "PROJECT.md").write_text(
        "## Identity\nSample\n",
        encoding="utf-8",
    )

    args = argparse.Namespace(path=str(sample_project))
    result = cmd_status(args, quiet=True)

    assert result["status"] == "success"
    assert "message" in result
    assert "data" in result
    data = result["data"]
    assert "project_name" in data
    assert "initialized" in data
    assert "project_md" in data
    assert "cold_start" in data
    assert "session_log" in data
    assert "scratchpad" in data
    assert "changes" in data
