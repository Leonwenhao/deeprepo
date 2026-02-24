"""Tests for RefreshEngine and cmd_refresh."""

import argparse
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from deeprepo.config_manager import ConfigManager


@pytest.fixture
def initialized_project(tmp_path: Path) -> Path:
    """Create an initialized .deeprepo/ with PROJECT.md and file hashes."""
    src = Path(__file__).parent / "fixtures" / "sample_project"
    dst = tmp_path / "project"
    shutil.copytree(src, dst)

    cm = ConfigManager(str(dst))
    cm.initialize()

    (dst / ".deeprepo" / "PROJECT.md").write_text(
        "---\ngenerated_by: test\n---\n\n## Identity\nTest\n\n## Architecture\nSimple\n",
        encoding="utf-8",
    )

    from deeprepo.cli_commands import compute_file_hashes

    hashes = compute_file_hashes(dst)
    state = cm.load_state()
    state.file_hashes = hashes
    state.last_refresh = "2026-02-22T00:00:00+00:00"
    cm.save_state(state)

    return dst


def _make_mock_usage() -> MagicMock:
    usage = MagicMock()
    usage.total_cost = 0.15
    usage.root_cost = 0.10
    usage.sub_cost = 0.05
    usage.sub_calls = 2
    usage.root_calls = 3
    usage.summary.return_value = "Cost: $0.15"
    return usage


def test_get_changes_no_changes(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    engine = RefreshEngine(str(initialized_project), config, state)
    changes = engine.get_changes()

    assert len(changes["modified"]) == 0
    assert len(changes["added"]) == 0
    assert len(changes["deleted"]) == 0
    assert changes["unchanged_count"] > 0


def test_get_changes_detects_modification(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    (initialized_project / "src" / "main.py").write_text("# changed\n", encoding="utf-8")

    engine = RefreshEngine(str(initialized_project), config, state)
    changes = engine.get_changes()

    assert "src/main.py" in changes["modified"]


def test_refresh_up_to_date(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    engine = RefreshEngine(str(initialized_project), config, state)
    result = engine.refresh(full=False)

    assert result["status"] == "up_to_date"
    assert result["changed_files"] == 0
    assert result["cost"] == 0.0


def test_refresh_with_changes(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    (initialized_project / "src" / "main.py").write_text("# changed\n", encoding="utf-8")

    mock_result = {
        "analysis": "## Identity\nUpdated\n## Architecture\nNew\n",
        "turns": 2,
        "usage": _make_mock_usage(),
    }

    engine = RefreshEngine(str(initialized_project), config, state)

    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        result = engine.refresh(full=False)

    assert result["status"] == "refreshed"
    assert result["changed_files"] > 0
    assert result["cost"] == 0.15

    project_md = (initialized_project / ".deeprepo" / "PROJECT.md").read_text(
        encoding="utf-8"
    )
    assert "Updated" in project_md
    assert len(state.file_hashes) > 0


def test_refresh_full(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    mock_result = {
        "analysis": "## Identity\nFull refresh\n## Architecture\nComplete\n",
        "turns": 4,
        "usage": _make_mock_usage(),
    }

    engine = RefreshEngine(str(initialized_project), config, state)

    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        result = engine.refresh(full=True)

    assert result["status"] == "refreshed"
    assert result["turns"] == 4


def test_refresh_full_propagates_partial_status(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    mock_result = {
        "analysis": "## Identity\nPartial full refresh\n",
        "turns": 4,
        "status": "partial",
        "usage": _make_mock_usage(),
    }

    engine = RefreshEngine(str(initialized_project), config, state)

    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        result = engine.refresh(full=True)

    assert result["status"] == "partial"


def test_refresh_with_changes_propagates_failed_status(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    (initialized_project / "src" / "main.py").write_text("# changed\n", encoding="utf-8")

    mock_result = {
        "analysis": "## Identity\nFailed incremental refresh\n",
        "turns": 2,
        "status": "failed",
        "usage": _make_mock_usage(),
    }

    engine = RefreshEngine(str(initialized_project), config, state)

    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        result = engine.refresh(full=False)

    assert result["status"] == "failed"


def test_refresh_updates_state_hashes(initialized_project: Path) -> None:
    from deeprepo.refresh import RefreshEngine

    cm = ConfigManager(str(initialized_project))
    config = cm.load_config()
    state = cm.load_state()

    (initialized_project / "new_module.py").write_text("# new\n", encoding="utf-8")

    mock_result = {
        "analysis": "## Identity\nUpdated\n",
        "turns": 2,
        "usage": _make_mock_usage(),
    }

    engine = RefreshEngine(str(initialized_project), config, state)

    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        engine.refresh(full=False)

    assert "new_module.py" in state.file_hashes
    assert state.last_refresh != "2026-02-22T00:00:00+00:00"


def test_cmd_refresh_up_to_date(initialized_project: Path, capsys) -> None:
    from deeprepo.cli_commands import cmd_refresh

    args = argparse.Namespace(
        path=str(initialized_project),
        full=False,
        quiet=False,
    )
    cmd_refresh(args)

    captured = capsys.readouterr()
    assert "up to date" in captured.out.lower()


def test_cmd_refresh_not_initialized(tmp_path: Path) -> None:
    from deeprepo.cli_commands import cmd_refresh

    args = argparse.Namespace(path=str(tmp_path), full=False, quiet=False)
    with pytest.raises(SystemExit):
        cmd_refresh(args)
