"""Tests for team registry and team-related CLI commands."""

import argparse
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _restore_registry() -> None:
    from deeprepo import teams

    snapshot = dict(teams.TEAM_REGISTRY)
    yield
    teams.TEAM_REGISTRY.clear()
    teams.TEAM_REGISTRY.update(snapshot)


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


def test_analyst_team_registered() -> None:
    from deeprepo.teams import get_team
    from deeprepo.teams.base import TeamConfig

    team = get_team("analyst")
    assert isinstance(team, TeamConfig)


def test_analyst_team_fields() -> None:
    from deeprepo.teams import get_team

    team = get_team("analyst")
    assert team.name == "analyst"
    assert team.display_name == "The Analyst"
    assert "Single-agent analysis" in team.description
    assert team.workflow == "sequential"
    assert team.can_analyze is True


def test_analyst_team_has_orchestrator_agent() -> None:
    from deeprepo.teams import get_team

    team = get_team("analyst")
    assert len(team.agents) == 1
    assert team.agents[0].role == "orchestrator"


def test_list_teams_returns_all() -> None:
    from deeprepo.teams import list_teams

    names = [team.name for team in list_teams()]
    assert "analyst" in names


def test_get_team_unknown_raises() -> None:
    from deeprepo.teams import get_team

    with pytest.raises(ValueError):
        get_team("nonexistent")


def test_get_team_error_message_lists_available() -> None:
    from deeprepo.teams import get_team

    with pytest.raises(ValueError) as exc:
        get_team("nonexistent")
    assert "analyst" in str(exc.value)


def test_register_custom_team() -> None:
    from deeprepo.teams import AgentConfig, TeamConfig, list_teams, register_team

    custom = TeamConfig(
        name="builder",
        display_name="Builder Team",
        description="Build-focused team",
        agents=[
            AgentConfig(
                role="engineer",
                model="minimax/minimax-m2.5",
                description="Implementation worker",
            )
        ],
        can_implement=True,
        estimated_cost_per_task="$0.10-$0.40",
    )
    register_team(custom)

    names = [team.name for team in list_teams()]
    assert "builder" in names
    assert "analyst" in names


def test_cmd_list_teams_output(capsys) -> None:
    from deeprepo.cli_commands import cmd_list_teams

    cmd_list_teams(argparse.Namespace())

    captured = capsys.readouterr()
    out = captured.out
    assert "Available teams" in out
    assert "analyst" in out
    assert "The Analyst" in out
    assert "Single-agent analysis using RLM orchestration" in out
    assert "Sonnet + MiniMax workers" in out
    assert "Agents: orchestrator" in out
    assert "Est. cost: $0.30-$1.50" in out


def test_cmd_init_stores_team(sample_project: Path) -> None:
    from deeprepo.cli_commands import cmd_init
    from deeprepo.config_manager import ConfigManager

    mock_result = {
        "analysis": (
            "## Identity\nPython\n"
            "## Architecture\nFastAPI\n"
            "## Module Map\n\n### src/\nCore app.\n"
            "## Patterns & Conventions\nUse type hints.\n"
            "## Dependency Graph\nsrc -> utils\n"
            "## Tech Debt & Known Issues\nNone\n"
        ),
        "turns": 3,
        "usage": _make_mock_usage(),
    }

    args = argparse.Namespace(
        path=str(sample_project),
        team="analyst",
        force=False,
        quiet=True,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with patch("deeprepo.rlm_scaffold.run_analysis", return_value=mock_result):
        cmd_init(args)

    cm = ConfigManager(str(sample_project))
    config = cm.load_config()
    assert config.team == "analyst"


def test_cmd_init_invalid_team_raises(sample_project: Path) -> None:
    from deeprepo.cli_commands import cmd_init

    args = argparse.Namespace(
        path=str(sample_project),
        team="nonexistent",
        force=False,
        quiet=True,
        root_model=None,
        sub_model=None,
        max_turns=None,
    )

    with pytest.raises(ValueError) as exc:
        cmd_init(args)
    assert "analyst" in str(exc.value)
