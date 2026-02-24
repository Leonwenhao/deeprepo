"""Diff-aware refresh engine for deeprepo context."""

from datetime import datetime, timezone
from pathlib import Path

from .config_manager import ProjectConfig, ProjectState


class RefreshEngine:
    """Compares file hashes and triggers context re-analysis."""

    def __init__(self, project_path: str, config: ProjectConfig, state: ProjectState):
        self.project_path = Path(project_path).resolve()
        self.config = config
        self.state = state

    def get_changes(self) -> dict:
        """Compare current file hashes against ``state.file_hashes``."""
        from .cli_commands import compute_file_hashes, get_changed_files

        current_hashes = compute_file_hashes(self.project_path)
        changes = get_changed_files(self.project_path, self.state)

        unchanged_count = len(current_hashes) - len(changes["modified"]) - len(
            changes["added"]
        )
        changes["unchanged_count"] = max(unchanged_count, 0)
        changes["current_hashes"] = current_hashes

        return changes

    def refresh(self, full: bool = False) -> dict:
        """Run diff-aware or full refresh."""
        from .cli_commands import compute_file_hashes
        from .context_generator import ContextGenerator
        from .rlm_scaffold import run_analysis

        if full:
            result = run_analysis(
                codebase_path=str(self.project_path),
                verbose=True,
                max_turns=self.config.max_turns,
                root_model=self.config.root_model,
                sub_model=self.config.sub_model,
                use_cache=True,
                domain="context",
            )

            generator = ContextGenerator(str(self.project_path), self.config)
            generator.generate(result["analysis"], self.state)

            self.state.file_hashes = compute_file_hashes(self.project_path)
            self.state.last_refresh = datetime.now(timezone.utc).isoformat()
            self.state.analysis_cost = result["usage"].total_cost
            self.state.analysis_turns = result["turns"]
            self.state.sub_llm_dispatches = result["usage"].sub_calls
            analysis_status = result.get("status", "completed")
            refresh_status = (
                "refreshed" if analysis_status == "completed" else analysis_status
            )

            return {
                "changed_files": len(self.state.file_hashes),
                "cost": result["usage"].total_cost,
                "turns": result["turns"],
                "status": refresh_status,
            }

        changes = self.get_changes()
        changed_count = (
            len(changes["modified"]) + len(changes["added"]) + len(changes["deleted"])
        )
        if changed_count == 0:
            return {
                "changed_files": 0,
                "cost": 0.0,
                "turns": 0,
                "status": "up_to_date",
            }

        result = run_analysis(
            codebase_path=str(self.project_path),
            verbose=True,
            max_turns=self.config.max_turns,
            root_model=self.config.root_model,
            sub_model=self.config.sub_model,
            use_cache=True,
            domain="context",
        )

        generator = ContextGenerator(str(self.project_path), self.config)
        generator.generate(result["analysis"], self.state)

        self.state.file_hashes = changes["current_hashes"]
        self.state.last_refresh = datetime.now(timezone.utc).isoformat()
        self.state.analysis_cost = result["usage"].total_cost
        self.state.analysis_turns = result["turns"]
        self.state.sub_llm_dispatches = result["usage"].sub_calls
        analysis_status = result.get("status", "completed")
        refresh_status = (
            "refreshed" if analysis_status == "completed" else analysis_status
        )

        return {
            "changed_files": changed_count,
            "cost": result["usage"].total_cost,
            "turns": result["turns"],
            "status": refresh_status,
        }
