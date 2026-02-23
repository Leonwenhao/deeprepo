from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Configuration for a single agent in a team."""

    role: str
    model: str
    description: str
    system_prompt: str = ""
    max_tokens: int = 8192
    temperature: float = 0.0


@dataclass
class TeamConfig:
    """Configuration for a multi-agent team."""

    name: str
    display_name: str
    description: str
    tagline: str = ""
    agents: list[AgentConfig] = field(default_factory=list)
    workflow: str = "sequential"
    can_scaffold: bool = False
    can_analyze: bool = True
    can_implement: bool = False
    estimated_cost_per_task: str = ""
