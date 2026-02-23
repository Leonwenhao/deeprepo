"""Tests for TUI session state manager."""

from datetime import datetime, timedelta
from pathlib import Path

from deeprepo.tui.session_state import SessionState


def _create_deeprepo_dir(tmp_path: Path) -> Path:
    dr = tmp_path / ".deeprepo"
    dr.mkdir()
    (dr / "config.yaml").write_text(
        "project_name: TestProject\nversion: 1\n",
        encoding="utf-8",
    )
    (dr / ".state.json").write_text(
        '{"last_refresh": "", "file_hashes": {"a.py": "abc", "b.py": "def"}}',
        encoding="utf-8",
    )
    (dr / "COLD_START.md").write_text(
        "# Cold Start\n\n"
        "This is a test cold start prompt with enough words to estimate tokens.\n",
        encoding="utf-8",
    )
    return dr


def test_from_project_uninitialized(tmp_path: Path) -> None:
    state = SessionState.from_project(str(tmp_path))

    assert state.initialized is False
    assert state.project_path == str(tmp_path.resolve())
    assert state.project_name == tmp_path.name


def test_from_project_initialized(tmp_path: Path) -> None:
    _create_deeprepo_dir(tmp_path)

    state = SessionState.from_project(str(tmp_path))

    assert state.initialized is True
    assert state.project_name == "TestProject"
    assert state.context_tokens > 0
    assert state.context_last_updated is not None
    assert state.files_tracked == 2


def test_context_age_not_initialized() -> None:
    state = SessionState(project_path=".")
    assert state.context_age == "Not initialized"


def test_context_age_fresh() -> None:
    state = SessionState(
        project_path=".",
        context_last_updated=datetime.now() - timedelta(minutes=2),
    )
    assert state.context_age == "Fresh"


def test_context_age_minutes() -> None:
    state = SessionState(
        project_path=".",
        context_last_updated=datetime.now() - timedelta(minutes=30),
    )
    assert state.context_age == "30 min ago"


def test_context_age_hours() -> None:
    state = SessionState(
        project_path=".",
        context_last_updated=datetime.now() - timedelta(hours=5),
    )
    assert state.context_age == "5 hours ago"


def test_context_age_stale() -> None:
    state = SessionState(
        project_path=".",
        context_last_updated=datetime.now() - timedelta(days=4),
    )
    assert state.context_age == "Stale (4 days)"


def test_welcome_summary_initialized() -> None:
    state = SessionState(
        project_path=".",
        project_name="deeprepo",
        initialized=True,
        context_tokens=3008,
        context_last_updated=datetime.now() - timedelta(minutes=2),
        files_tracked=23,
    )

    summary = state.welcome_summary
    assert "Project: deeprepo" in summary
    assert "Context: Fresh" in summary
    assert "3,008 tokens" in summary
    assert "23 files" in summary


def test_welcome_summary_not_initialized() -> None:
    state = SessionState(project_path=".", project_name="deeprepo", initialized=False)
    summary = state.welcome_summary

    assert "Project: deeprepo" in summary
    assert "Not initialized" in summary


def test_record_prompt() -> None:
    state = SessionState(project_path=".")
    state.record_prompt("fix bug", "full prompt text")

    assert len(state.prompt_history) == 1
    entry = state.prompt_history[0]
    assert entry["user_input"] == "fix bug"
    assert entry["generated_prompt"] == "full prompt text"
    assert isinstance(entry["timestamp"], datetime)


def test_refresh_reloads_from_disk(tmp_path: Path) -> None:
    dr = _create_deeprepo_dir(tmp_path)
    state = SessionState.from_project(str(tmp_path))
    before = state.context_tokens

    (dr / "COLD_START.md").write_text(
        "# Cold Start\n\n"
        "This updated context has substantially more words than before "
        "to force a different token estimate during refresh logic.\n",
        encoding="utf-8",
    )

    state.refresh()

    assert state.context_tokens != before
