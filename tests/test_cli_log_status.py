"""Tests for log and status CLI commands."""

import argparse
import shutil
from pathlib import Path

import pytest

from deeprepo.config_manager import ConfigManager, ProjectState


@pytest.fixture
def initialized_project(tmp_path: Path) -> Path:
    """Create an initialized .deeprepo/ project with PROJECT.md."""
    src = Path(__file__).parent / "fixtures" / "sample_project"
    dst = tmp_path / "project"
    shutil.copytree(src, dst)
    cm = ConfigManager(str(dst))
    cm.initialize()
    (dst / ".deeprepo" / "PROJECT.md").write_text(
        "---\ngenerated_by: test\n---\n\n## Identity\nTest project\n\n## Architecture\nSimple\n",
        encoding="utf-8",
    )
    return dst


def test_append_log_entry(initialized_project: Path) -> None:
    from deeprepo.cli_commands import append_log_entry

    deeprepo_dir = initialized_project / ".deeprepo"
    append_log_entry(deeprepo_dir, "Implemented auth module")

    log_text = (deeprepo_dir / "SESSION_LOG.md").read_text(encoding="utf-8")
    assert "Implemented auth module" in log_text
    assert "## 20" in log_text


def test_append_log_entry_multiple(initialized_project: Path) -> None:
    from deeprepo.cli_commands import append_log_entry

    deeprepo_dir = initialized_project / ".deeprepo"
    append_log_entry(deeprepo_dir, "First entry")
    append_log_entry(deeprepo_dir, "Second entry")

    log_text = (deeprepo_dir / "SESSION_LOG.md").read_text(encoding="utf-8")
    assert "First entry" in log_text
    assert "Second entry" in log_text


def test_show_log_entries(initialized_project: Path) -> None:
    from deeprepo.cli_commands import append_log_entry, show_log_entries

    deeprepo_dir = initialized_project / ".deeprepo"
    append_log_entry(deeprepo_dir, "Entry one")
    append_log_entry(deeprepo_dir, "Entry two")
    append_log_entry(deeprepo_dir, "Entry three")

    entries = show_log_entries(deeprepo_dir, count=2)
    assert len(entries) == 2
    assert entries[-1]["message"] == "Entry three"


def test_show_log_entries_empty(initialized_project: Path) -> None:
    from deeprepo.cli_commands import show_log_entries

    entries = show_log_entries(initialized_project / ".deeprepo", count=5)
    assert entries == []


def test_cmd_log_appends_and_regenerates_cold_start(initialized_project: Path) -> None:
    from deeprepo.cli_commands import cmd_log

    args = argparse.Namespace(
        action="Added tests for auth",
        message=None,
        path=str(initialized_project),
        count=5,
    )
    cmd_log(args)

    cold_start = (initialized_project / ".deeprepo" / "COLD_START.md").read_text(
        encoding="utf-8"
    )
    assert "Added tests for auth" in cold_start


def test_cmd_log_show(initialized_project: Path, capsys) -> None:
    from deeprepo.cli_commands import append_log_entry, cmd_log

    append_log_entry(initialized_project / ".deeprepo", "Test message")

    args = argparse.Namespace(
        action="show",
        message=None,
        path=str(initialized_project),
        count=5,
    )
    cmd_log(args)

    captured = capsys.readouterr()
    assert "Test message" in captured.out


def test_cmd_status_shows_health(initialized_project: Path, capsys) -> None:
    from deeprepo.cli_commands import cmd_status

    args = argparse.Namespace(path=str(initialized_project))
    cmd_status(args)

    captured = capsys.readouterr()
    assert "PROJECT.md" in captured.out
    assert "COLD_START.md" in captured.out
    assert "SESSION_LOG.md" in captured.out
    assert "SCRATCHPAD.md" in captured.out


def test_cmd_status_not_initialized(tmp_path: Path) -> None:
    from deeprepo.cli_commands import cmd_status

    args = argparse.Namespace(path=str(tmp_path))
    with pytest.raises(SystemExit):
        cmd_status(args)


def test_get_changed_files(initialized_project: Path) -> None:
    from deeprepo.cli_commands import compute_file_hashes, get_changed_files

    hashes = compute_file_hashes(initialized_project)
    state = ProjectState(file_hashes=hashes)

    (initialized_project / "src" / "main.py").write_text("# modified\n", encoding="utf-8")
    (initialized_project / "new_file.py").write_text("# new\n", encoding="utf-8")

    changes = get_changed_files(initialized_project, state)
    assert "src/main.py" in changes["modified"]
    assert "new_file.py" in changes["added"]


def test_get_changed_files_detects_deletion(initialized_project: Path) -> None:
    from deeprepo.cli_commands import compute_file_hashes, get_changed_files

    hashes = compute_file_hashes(initialized_project)
    state = ProjectState(file_hashes=hashes)

    (initialized_project / "src" / "utils.py").unlink()

    changes = get_changed_files(initialized_project, state)
    assert "src/utils.py" in changes["deleted"]


def test_compute_file_hashes_skips_deeprepo_dir(initialized_project: Path) -> None:
    from deeprepo.cli_commands import compute_file_hashes

    hashes = compute_file_hashes(initialized_project)
    for path in hashes:
        assert not path.startswith(".deeprepo")
