"""Tests for ContextGenerator."""

import shutil
from pathlib import Path

import pytest

from deeprepo.config_manager import ConfigManager, ProjectConfig, ProjectState
from deeprepo.context_generator import ContextGenerator


@pytest.fixture
def initialized_project(tmp_path: Path) -> Path:
    """Create an initialized .deeprepo/ project."""
    src = Path(__file__).parent / "fixtures" / "sample_project"
    dst = tmp_path / "project"
    shutil.copytree(src, dst)
    cm = ConfigManager(str(dst))
    cm.initialize()
    return dst


SAMPLE_ANALYSIS = """## Identity
Language: Python
Framework: FastAPI
Package Manager: pip

## Architecture
Entry point: src/main.py
Simple REST API with one route.

## Module Map

### src/
Core application module.
Entry: main.py
Patterns: FastAPI routing
Dependencies: fastapi, uvicorn

### utils/
Utility helpers.
Entry: utils.py
Patterns: pure functions

## Patterns & Conventions
- Use type hints on all functions
- pytest for testing

## Dependency Graph
src/ -> utils/

## Tech Debt & Known Issues
- No authentication
- No database layer
"""


def test_generate_creates_project_md(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState(created_at="2026-01-01T00:00:00+00:00")

    files = gen.generate(SAMPLE_ANALYSIS, state)

    project_md_path = initialized_project / ".deeprepo" / "PROJECT.md"
    project_md = project_md_path.read_text(encoding="utf-8")
    assert "## Identity" in project_md
    assert "## Architecture" in project_md
    assert "project_md" in files
    assert files["project_md"] == str(project_md_path)


def test_generate_creates_cold_start_md(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    cold_start = (initialized_project / ".deeprepo" / "COLD_START.md").read_text(
        encoding="utf-8"
    )
    assert "## Identity" in cold_start
    assert "## Architecture" in cold_start


def test_project_md_has_metadata_header(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    project_md = (initialized_project / ".deeprepo" / "PROJECT.md").read_text(
        encoding="utf-8"
    )
    assert "generated_by:" in project_md
    assert "timestamp:" in project_md


def test_cold_start_skips_dependency_graph(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    cold_start = (initialized_project / ".deeprepo" / "COLD_START.md").read_text(
        encoding="utf-8"
    )
    assert "## Dependency Graph" not in cold_start


def test_cold_start_compresses_module_map(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    cold_start = (initialized_project / ".deeprepo" / "COLD_START.md").read_text(
        encoding="utf-8"
    )
    assert "## Module Map" in cold_start
    assert "src/" in cold_start
    assert "Entry: main.py" not in cold_start
    assert "Patterns: FastAPI routing" not in cold_start


def test_cold_start_keeps_patterns_section(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    cold_start = (initialized_project / ".deeprepo" / "COLD_START.md").read_text(
        encoding="utf-8"
    )
    assert "## Patterns & Conventions" in cold_start
    assert "type hints" in cold_start


def test_cold_start_has_active_state(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    cold_start = (initialized_project / ".deeprepo" / "COLD_START.md").read_text(
        encoding="utf-8"
    )
    assert "Active State" in cold_start


def test_update_cold_start_regenerates(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    log_path = initialized_project / ".deeprepo" / "SESSION_LOG.md"
    log_content = log_path.read_text(encoding="utf-8")
    log_content += "\n---\n## 2026-02-22 14:30\n\nAdded auth module\n"
    log_path.write_text(log_content, encoding="utf-8")

    new_cold_start = gen.update_cold_start()
    assert "Added auth module" in new_cold_start


def test_update_cold_start_raises_if_no_project_md(initialized_project: Path) -> None:
    config = ProjectConfig(project_name="test")
    gen = ContextGenerator(str(initialized_project), config)

    with pytest.raises(FileNotFoundError):
        gen.update_cold_start()


def test_parse_sections() -> None:
    config = ProjectConfig()
    gen = ContextGenerator("/tmp/fake", config)

    text = "## Foo\nfoo content\n## Bar\nbar content\n"
    sections = gen._parse_sections(text)

    assert "Foo" in sections
    assert "Bar" in sections
    assert "foo content" in sections["Foo"]
    assert "bar content" in sections["Bar"]


def test_estimate_tokens() -> None:
    config = ProjectConfig()
    gen = ContextGenerator("/tmp/fake", config)
    assert gen._estimate_tokens("a" * 400) == 100


def test_token_budget_truncation(initialized_project: Path) -> None:
    """Cold start respects context_max_tokens."""
    config = ProjectConfig(project_name="test", context_max_tokens=50)
    gen = ContextGenerator(str(initialized_project), config)
    state = ProjectState()

    gen.generate(SAMPLE_ANALYSIS, state)

    cold_start = (initialized_project / ".deeprepo" / "COLD_START.md").read_text(
        encoding="utf-8"
    )
    token_est = len(cold_start) // 4
    assert token_est < 100
    assert "[Truncated to fit token budget]" in cold_start
