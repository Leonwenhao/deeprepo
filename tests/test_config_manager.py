import shutil
from datetime import datetime
from pathlib import Path

import pytest

from deeprepo.config_manager import ConfigManager, ProjectConfig, ProjectState


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Copy sample_project fixture to a temp directory."""
    src = Path(__file__).parent / "fixtures" / "sample_project"
    dst = tmp_path / "sample_project"
    shutil.copytree(src, dst)
    return dst


@pytest.fixture
def bare_dir(tmp_path: Path) -> Path:
    """A bare directory with no project files."""
    project_dir = tmp_path / "bare_project"
    project_dir.mkdir()
    return project_dir


def test_initialize_creates_all_files(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))

    manager.initialize()

    assert (project_dir / ".deeprepo" / "config.yaml").is_file()
    assert (project_dir / ".deeprepo" / "SESSION_LOG.md").is_file()
    assert (project_dir / ".deeprepo" / "SCRATCHPAD.md").is_file()
    assert (project_dir / ".deeprepo" / ".state.json").is_file()
    assert (project_dir / ".deeprepo" / ".gitignore").is_file()


def test_initialize_raises_if_already_initialized(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))

    manager.initialize()

    with pytest.raises(FileExistsError):
        manager.initialize()


def test_config_roundtrip(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))

    config = ProjectConfig(
        version=2,
        root_model="openai/gpt-5",
        sub_model="openai/gpt-5-mini",
        max_turns=22,
        cost_limit=10.5,
        context_max_tokens=12345,
        session_log_count=5,
        include_scratchpad=False,
        include_tech_debt=False,
        auto_refresh=True,
        stale_threshold_hours=12,
        project_name="custom-project",
        project_description="Custom description",
        team="platform",
        ignore_paths=["node_modules", ".venv"],
    )

    manager.save_config(config)
    loaded = manager.load_config()

    assert loaded == config


def test_state_roundtrip(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))

    state = ProjectState(
        last_refresh="2026-02-20T10:00:00+00:00",
        last_commit="abc123",
        file_hashes={"a.py": "hash1", "b.py": "hash2"},
        analysis_cost=1.25,
        analysis_turns=7,
        sub_llm_dispatches=3,
        created_at="2026-02-20T09:00:00+00:00",
        created_with="deeprepo@0.1.0",
        original_intent="Initial analysis",
    )

    manager.save_state(state)
    loaded = manager.load_state()

    assert loaded == state


def test_load_config_fills_defaults(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))
    manager.deeprepo_dir.mkdir(parents=True, exist_ok=True)
    (manager.deeprepo_dir / "config.yaml").write_text("version: 1\n", encoding="utf-8")

    loaded = manager.load_config()

    assert loaded == ProjectConfig(version=1)


def test_detect_project_name_from_pyproject(sample_project: Path) -> None:
    manager = ConfigManager(str(sample_project))
    assert manager.detect_project_name() == "sample-project"


def test_detect_project_name_fallback_to_dirname(bare_dir: Path) -> None:
    manager = ConfigManager(str(bare_dir))
    assert manager.detect_project_name() == bare_dir.name


def test_detect_stack_python_fastapi(sample_project: Path) -> None:
    manager = ConfigManager(str(sample_project))
    assert manager.detect_stack() == {
        "language": "python",
        "framework": "fastapi",
        "package_manager": "pip",
        "test_framework": "pytest",
    }


def test_is_initialized_false_then_true(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))

    assert manager.is_initialized() is False

    manager.initialize()

    assert manager.is_initialized() is True


def test_gitignore_contents(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))

    manager.initialize()

    gitignore = (project_dir / ".deeprepo" / ".gitignore").read_text(encoding="utf-8")
    assert ".state.json" in gitignore
    assert "modules/" in gitignore


def test_state_has_created_at(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(str(project_dir))

    manager.initialize()
    state = manager.load_state()

    assert state.created_at
    datetime.fromisoformat(state.created_at)


def test_initialize_auto_detects_project_name(sample_project: Path) -> None:
    manager = ConfigManager(str(sample_project))

    manager.initialize()
    config = manager.load_config()

    assert config.project_name == "sample-project"
