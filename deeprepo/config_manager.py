from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import yaml


@dataclass
class ProjectConfig:
    """User-editable project preferences from config.yaml."""

    version: int = 1
    root_model: str = "anthropic/claude-sonnet-4-6"
    sub_model: str = "minimax/minimax-m2.5"
    max_turns: int = 20
    cost_limit: float = 2.00
    context_max_tokens: int = 3000
    session_log_count: int = 3
    include_scratchpad: bool = True
    include_tech_debt: bool = True
    auto_refresh: bool = False
    stale_threshold_hours: int = 72
    project_name: str = ""
    project_description: str = ""
    team: str = ""
    ignore_paths: list[str] = field(default_factory=list)


@dataclass
class ProjectState:
    """Internal state from .state.json, not user-editable."""

    last_refresh: str = ""
    last_commit: str = ""
    file_hashes: dict[str, str] = field(default_factory=dict)
    analysis_cost: float = 0.0
    analysis_turns: int = 0
    sub_llm_dispatches: int = 0
    created_at: str = ""
    created_with: str = ""
    original_intent: str = ""


class ConfigManager:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.deeprepo_dir = self.project_path / ".deeprepo"

    def is_initialized(self) -> bool:
        """Check if .deeprepo/ exists and has config.yaml."""
        return (self.deeprepo_dir / "config.yaml").is_file()

    def initialize(self, config: ProjectConfig | None = None) -> None:
        """Create .deeprepo/ directory with template files."""
        if self.is_initialized():
            raise FileExistsError(
                f".deeprepo/ already initialized at {self.deeprepo_dir}"
            )

        self.deeprepo_dir.mkdir(parents=True, exist_ok=True)

        if config is None:
            config = ProjectConfig()
        if not config.project_name:
            config.project_name = self.detect_project_name()
        self.save_config(config)

        (self.deeprepo_dir / "SESSION_LOG.md").write_text(
            SESSION_LOG_TEMPLATE,
            encoding="utf-8",
        )
        (self.deeprepo_dir / "SCRATCHPAD.md").write_text(
            SCRATCHPAD_TEMPLATE,
            encoding="utf-8",
        )

        state = ProjectState(created_at=datetime.now(timezone.utc).isoformat())
        self.save_state(state)

        (self.deeprepo_dir / ".gitignore").write_text(
            ".state.json\nmodules/\n",
            encoding="utf-8",
        )

    def load_config(self) -> ProjectConfig:
        """Read config.yaml into ProjectConfig. Missing keys use defaults."""
        config_path = self.deeprepo_dir / "config.yaml"
        if not config_path.is_file():
            return ProjectConfig()

        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        defaults = ProjectConfig()
        kwargs = {}
        for field_name in ProjectConfig.__dataclass_fields__:
            kwargs[field_name] = data.get(field_name, getattr(defaults, field_name))
        return ProjectConfig(**kwargs)

    def save_config(self, config: ProjectConfig) -> None:
        """Write ProjectConfig to config.yaml."""
        config_path = self.deeprepo_dir / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.dump(
                asdict(config),
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def load_state(self) -> ProjectState:
        """Read .state.json into ProjectState. Returns default if file missing."""
        state_path = self.deeprepo_dir / ".state.json"
        if not state_path.is_file():
            return ProjectState()

        data = json.loads(state_path.read_text(encoding="utf-8"))
        defaults = ProjectState()
        kwargs = {}
        for field_name in ProjectState.__dataclass_fields__:
            kwargs[field_name] = data.get(field_name, getattr(defaults, field_name))
        return ProjectState(**kwargs)

    def save_state(self, state: ProjectState) -> None:
        """Write ProjectState to .state.json."""
        state_path = self.deeprepo_dir / ".state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(asdict(state), indent=2) + "\n",
            encoding="utf-8",
        )

    def detect_project_name(self) -> str:
        """Auto-detect project name from common project files."""
        pyproject = self.project_path / "pyproject.toml"
        if pyproject.is_file():
            match = re.search(
                r'^name\s*=\s*["\']([^"\']+)["\']',
                pyproject.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if match:
                return match.group(1)

        pkg_json = self.project_path / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                if "name" in data:
                    return data["name"]
            except json.JSONDecodeError:
                pass

        cargo = self.project_path / "Cargo.toml"
        if cargo.is_file():
            match = re.search(
                r'^name\s*=\s*["\']([^"\']+)["\']',
                cargo.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if match:
                return match.group(1)

        return self.project_path.name

    def detect_stack(self) -> dict[str, str]:
        """Detect language, framework, package manager, and test framework."""
        result = {
            "language": "unknown",
            "framework": "",
            "package_manager": "",
            "test_framework": "",
        }

        pyproject = self.project_path / "pyproject.toml"
        if pyproject.is_file():
            text = pyproject.read_text(encoding="utf-8").lower()
            result["language"] = "python"

            if "fastapi" in text:
                result["framework"] = "fastapi"
            elif "django" in text:
                result["framework"] = "django"
            elif "flask" in text:
                result["framework"] = "flask"

            if (self.project_path / "uv.lock").is_file():
                result["package_manager"] = "uv"
            elif (self.project_path / "poetry.lock").is_file():
                result["package_manager"] = "poetry"
            else:
                result["package_manager"] = "pip"

            if "pytest" in text:
                result["test_framework"] = "pytest"
            else:
                result["test_framework"] = "unittest"

            return result

        pkg_json = self.project_path / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                text = json.dumps(data).lower()
            except json.JSONDecodeError:
                text = ""

            result["language"] = (
                "typescript"
                if (self.project_path / "tsconfig.json").is_file()
                else "javascript"
            )

            if "next" in text:
                result["framework"] = "nextjs"
            elif "express" in text:
                result["framework"] = "express"
            elif "react" in text:
                result["framework"] = "react"

            if (self.project_path / "pnpm-lock.yaml").is_file():
                result["package_manager"] = "pnpm"
            elif (self.project_path / "yarn.lock").is_file():
                result["package_manager"] = "yarn"
            else:
                result["package_manager"] = "npm"

            return result

        if (self.project_path / "Cargo.toml").is_file():
            result["language"] = "rust"
            result["package_manager"] = "cargo"
            return result

        if (self.project_path / "go.mod").is_file():
            result["language"] = "go"
            result["package_manager"] = "go"
            return result

        return result


SESSION_LOG_TEMPLATE = """# Session Log

> Track what happens across AI-assisted work sessions.
> Add entries: `deeprepo log "description of what you did"`
> View recent: `deeprepo log show`

---
"""


SCRATCHPAD_TEMPLATE = """# Scratchpad

> Coordinate work between multiple AI agents.
> This file is included in your cold-start prompt via `deeprepo context`.
>
> Usage:
> 1. Write a task spec in "Current Task" for the implementing agent
> 2. The implementing agent writes results in "Latest Handoff"
> 3. Review and write the next task

## Status
- **Current Task:** None
- **Phase:** IDLE

## Current Task

[Write task specifications here]

## Latest Handoff

[Implementation results go here]

## Decision Log

[Append-only - record architectural decisions here]
"""
