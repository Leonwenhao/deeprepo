"""Tests for greenfield project scaffolding."""

import argparse
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from deeprepo.config_manager import ConfigManager
from deeprepo.teams import get_team


MOCK_SCAFFOLD_RESPONSE = """===FILE: src/main.py===
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello"}
===END_FILE===

===FILE: tests/test_main.py===
def test_root():
    assert True
===END_FILE===

===FILE: pyproject.toml===
[project]
name = "test-project"
version = "0.1.0"
===END_FILE===

===FILE: README.md===
# Test Project
A test project.
===END_FILE===

===PROJECT_SUMMARY===
## Identity
Python FastAPI project

## Architecture
Single FastAPI application with REST endpoints

## Module Map
### src/
Core application code

## Patterns & Conventions
Standard Python conventions

## Tech Debt & Known Issues
Fresh scaffold — no tech debt
===END_SUMMARY===
"""


@pytest.fixture
def scaffolder():
    from deeprepo.scaffold import ProjectScaffolder

    return ProjectScaffolder(get_team("analyst"))


def test_parse_scaffold_response_extracts_files(scaffolder) -> None:
    parsed = scaffolder.parse_scaffold_response(MOCK_SCAFFOLD_RESPONSE)
    assert len(parsed["files"]) == 4
    assert "src/main.py" in parsed["files"]
    assert "README.md" in parsed["files"]


def test_parse_scaffold_response_extracts_summary(scaffolder) -> None:
    parsed = scaffolder.parse_scaffold_response(MOCK_SCAFFOLD_RESPONSE)
    assert "## Identity" in parsed["summary"]


def test_parse_scaffold_response_no_summary_fallback(scaffolder) -> None:
    response = """===FILE: app.py===
print("hello")
===END_FILE===
"""
    parsed = scaffolder.parse_scaffold_response(response)
    assert "## Identity" in parsed["summary"]
    assert "Fresh scaffold" in parsed["summary"]


def test_build_scaffold_prompt_has_delimiters(scaffolder) -> None:
    prompt = scaffolder.build_scaffold_prompt(
        description="Task manager API",
        stack={"language": "python", "framework": "fastapi"},
        project_name="task-manager",
    )
    assert "===FILE: path/to/file===" in prompt
    assert "===END_FILE===" in prompt
    assert "===PROJECT_SUMMARY===" in prompt
    assert "===END_SUMMARY===" in prompt


def test_build_scaffold_prompt_includes_description(scaffolder) -> None:
    description = "A weather dashboard with FastAPI backend"
    prompt = scaffolder.build_scaffold_prompt(
        description=description,
        stack={"language": "python", "framework": "fastapi"},
        project_name="weather-dashboard",
    )
    assert description in prompt


def test_scaffold_creates_project_files(scaffolder, tmp_path: Path) -> None:
    with patch.object(scaffolder, "_call_llm", return_value=MOCK_SCAFFOLD_RESPONSE):
        result = scaffolder.scaffold(
            description="Test scaffold",
            stack={"language": "python", "framework": "fastapi"},
            project_name="demo-app",
            output_dir=str(tmp_path),
        )

    project_path = Path(result["project_path"])
    assert (project_path / "src" / "main.py").is_file()
    assert (project_path / "tests" / "test_main.py").is_file()
    assert (project_path / "pyproject.toml").is_file()
    assert (project_path / "README.md").is_file()


def test_scaffold_creates_deeprepo_dir(scaffolder, tmp_path: Path) -> None:
    with patch.object(scaffolder, "_call_llm", return_value=MOCK_SCAFFOLD_RESPONSE):
        result = scaffolder.scaffold(
            description="Inventory service",
            stack={"language": "python", "framework": "fastapi"},
            project_name="inventory-service",
            output_dir=str(tmp_path),
        )

    project_path = Path(result["project_path"])
    deeprepo_dir = project_path / ".deeprepo"
    assert deeprepo_dir.is_dir()
    assert (deeprepo_dir / "config.yaml").is_file()
    assert (deeprepo_dir / "PROJECT.md").is_file()
    assert (deeprepo_dir / "COLD_START.md").is_file()
    assert (deeprepo_dir / "SESSION_LOG.md").is_file()


def test_scaffold_state_has_created_with_new(scaffolder, tmp_path: Path) -> None:
    description = "Analytics API scaffold"
    with patch.object(scaffolder, "_call_llm", return_value=MOCK_SCAFFOLD_RESPONSE):
        result = scaffolder.scaffold(
            description=description,
            stack={"language": "python", "framework": "fastapi"},
            project_name="analytics-api",
            output_dir=str(tmp_path),
        )

    project_path = Path(result["project_path"])
    cm = ConfigManager(str(project_path))
    config = cm.load_config()
    state = cm.load_state()

    assert config.team == "analyst"
    assert state.created_with == "new"
    assert state.original_intent == description

    session_log = (project_path / ".deeprepo" / "SESSION_LOG.md").read_text(
        encoding="utf-8"
    )
    assert "Project created with deeprepo new" in session_log
    assert description in session_log


def test_parse_stack_string() -> None:
    from deeprepo.cli_commands import _parse_stack_string

    assert _parse_stack_string("python-fastapi") == {
        "language": "python",
        "framework": "fastapi",
    }
    assert _parse_stack_string("python") == {"language": "python"}


def test_cmd_new_non_interactive(tmp_path: Path, capsys) -> None:
    from deeprepo.cli_commands import cmd_new

    args = argparse.Namespace(
        description="Payments service API",
        stack="python-fastapi",
        name="payments-service",
        team="analyst",
        output=str(tmp_path),
        yes=True,
    )

    with patch("deeprepo.scaffold.ProjectScaffolder._call_llm", return_value=MOCK_SCAFFOLD_RESPONSE):
        cmd_new(args)

    project_path = tmp_path / "payments-service"
    assert project_path.is_dir()
    assert (project_path / ".deeprepo" / "PROJECT.md").is_file()

    captured = capsys.readouterr()
    assert "Scaffolding payments-service" in captured.out
    assert "Created payments-service" in captured.out


def test_cmd_new_appears_in_help(monkeypatch, capsys) -> None:
    from deeprepo import cli

    monkeypatch.setattr(sys, "argv", ["deeprepo", "--help"])
    with pytest.raises(SystemExit):
        cli.main()

    captured = capsys.readouterr()
    assert "new" in captured.out
