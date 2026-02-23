"""Session-level project state for the interactive TUI."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from deeprepo.config_manager import ConfigManager


@dataclass
class SessionState:
    """Tracks project metadata and runtime session data for the TUI shell."""

    # Project info (loaded from .deeprepo/)
    project_path: str
    project_name: str = ""
    initialized: bool = False
    context_tokens: int = 0
    context_last_updated: datetime | None = None
    files_tracked: int = 0
    stale_threshold_hours: int = 72

    # Session info (runtime only)
    session_start: datetime = field(default_factory=datetime.now)
    prompt_history: list[dict] = field(default_factory=list)
    current_task: str | None = None

    @classmethod
    def from_project(cls, project_path: str) -> "SessionState":
        """Load state from a project's .deeprepo/ directory if present."""
        abs_path = str(Path(project_path).resolve())
        fallback_name = Path(abs_path).name

        cm = ConfigManager(abs_path)
        if not cm.is_initialized():
            return cls(
                project_path=abs_path,
                project_name=fallback_name,
                initialized=False,
            )

        config = cm.load_config()
        project_state = cm.load_state()

        state = cls(
            project_path=abs_path,
            project_name=(config.project_name.strip() or fallback_name),
            initialized=True,
            files_tracked=len(project_state.file_hashes),
            stale_threshold_hours=config.stale_threshold_hours,
        )

        # Keep a fallback timestamp from .state.json when available.
        state.context_last_updated = cls._parse_iso_datetime(project_state.last_refresh)

        cold_start_path = cm.deeprepo_dir / "COLD_START.md"
        if cold_start_path.is_file():
            content = cold_start_path.read_text(encoding="utf-8", errors="ignore")
            state.context_tokens = int(round(len(content.split()) * 1.3))
            state.context_last_updated = datetime.fromtimestamp(
                cold_start_path.stat().st_mtime
            )

        return state

    def refresh(self):
        """Reload project metadata from .deeprepo/ while preserving runtime state."""
        refreshed = self.from_project(self.project_path)

        self.project_path = refreshed.project_path
        self.project_name = refreshed.project_name
        self.initialized = refreshed.initialized
        self.context_tokens = refreshed.context_tokens
        self.context_last_updated = refreshed.context_last_updated
        self.files_tracked = refreshed.files_tracked
        self.stale_threshold_hours = refreshed.stale_threshold_hours

    def record_prompt(self, user_input: str, generated_prompt: str):
        """Store a prompt generation event in session history."""
        self.prompt_history.append(
            {
                "timestamp": datetime.now(),
                "user_input": user_input,
                "input": user_input,
                "generated_prompt": generated_prompt,
            }
        )

    @property
    def context_age(self) -> str:
        """Human-readable freshness string for current project context."""
        if self.context_last_updated is None:
            return "Not initialized"

        if self.context_last_updated.tzinfo is not None:
            now = datetime.now(self.context_last_updated.tzinfo)
        else:
            now = datetime.now()

        delta_seconds = max((now - self.context_last_updated).total_seconds(), 0.0)

        if delta_seconds < 5 * 60:
            return "Fresh"
        if delta_seconds < 60 * 60:
            minutes = max(1, int(delta_seconds // 60))
            return f"{minutes} min ago"
        if delta_seconds < 24 * 60 * 60:
            hours = max(1, int(delta_seconds // (60 * 60)))
            unit = "hour" if hours == 1 else "hours"
            return f"{hours} {unit} ago"

        days = max(1, int(delta_seconds // (24 * 60 * 60)))
        stale_cutoff_seconds = max(1, self.stale_threshold_hours) * 60 * 60
        if delta_seconds >= stale_cutoff_seconds:
            unit = "day" if days == 1 else "days"
            return f"Stale ({days} {unit})"

        unit = "day" if days == 1 else "days"
        return f"{days} {unit} ago"

    @property
    def welcome_summary(self) -> str:
        """One-line project/context summary for the shell welcome banner."""
        display_name = self.project_name or Path(self.project_path).name
        if not self.initialized:
            return (
                f"Project: {display_name} | "
                "Context: Not initialized (run /init)"
            )

        return (
            f"Project: {display_name} | "
            f"Context: {self.context_age} | "
            f"{self.context_tokens:,} tokens | "
            f"{self.files_tracked} files"
        )

    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime | None:
        """Parse an ISO string into datetime; return None on empty/invalid input."""
        if not value:
            return None

        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
