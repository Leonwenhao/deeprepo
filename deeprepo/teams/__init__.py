from .base import AgentConfig, TeamConfig

TEAM_REGISTRY: dict[str, TeamConfig] = {}


def register_team(team: TeamConfig) -> None:
    TEAM_REGISTRY[team.name] = team


def get_team(name: str) -> TeamConfig:
    if name not in TEAM_REGISTRY:
        available = ", ".join(sorted(TEAM_REGISTRY.keys()))
        raise ValueError(f"Unknown team '{name}'. Available: {available}")
    return TEAM_REGISTRY[name]


def list_teams() -> list[TeamConfig]:
    return list(TEAM_REGISTRY.values())


ANALYST_TEAM = TeamConfig(
    name="analyst",
    display_name="The Analyst",
    description="Single-agent analysis using RLM orchestration",
    tagline="Sonnet + MiniMax workers",
    agents=[
        AgentConfig(
            role="orchestrator",
            model="anthropic/claude-sonnet-4-6",
            description="Root model for RLM orchestration",
        ),
    ],
    workflow="sequential",
    can_scaffold=False,
    can_analyze=True,
    can_implement=False,
    estimated_cost_per_task="$0.30-$1.50",
)

register_team(ANALYST_TEAM)


__all__ = [
    "AgentConfig",
    "TeamConfig",
    "TEAM_REGISTRY",
    "ANALYST_TEAM",
    "register_team",
    "get_team",
    "list_teams",
]
