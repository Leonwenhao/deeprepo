"""Post-processor that splits RLM analysis output into .deeprepo/ files."""

from datetime import datetime, timezone
from pathlib import Path
import re

from . import __version__
from .config_manager import ProjectConfig, ProjectState


class ContextGenerator:
    """Takes raw RLM analysis output and produces .deeprepo/ files."""

    def __init__(self, project_path: str, config: ProjectConfig):
        self.project_path = Path(project_path).resolve()
        self.config = config
        self.deeprepo_dir = self.project_path / ".deeprepo"

    def generate(self, analysis_output: str, state: ProjectState) -> dict:
        """Take raw RLM output and produce .deeprepo/ files."""
        self.deeprepo_dir.mkdir(parents=True, exist_ok=True)

        project_md = self.generate_project_md(analysis_output)
        project_md_path = self.deeprepo_dir / "PROJECT.md"
        project_md_path.write_text(project_md, encoding="utf-8")

        cold_start = self.generate_cold_start(project_md)
        cold_start_path = self.deeprepo_dir / "COLD_START.md"
        cold_start_path.write_text(cold_start, encoding="utf-8")

        state.last_refresh = datetime.now(timezone.utc).isoformat()

        return {
            "project_md": str(project_md_path),
            "cold_start_md": str(cold_start_path),
        }

    def generate_project_md(self, analysis_output: str) -> str:
        """Add metadata header to analysis output."""
        timestamp = datetime.now(timezone.utc).isoformat()
        body = analysis_output.strip()
        return (
            "---\n"
            f"generated_by: deeprepo v{__version__}\n"
            f"timestamp: {timestamp}\n"
            "refresh_command: deeprepo refresh\n"
            "---\n\n"
            f"{body}\n"
        )

    def generate_cold_start(self, project_md: str) -> str:
        """Compress PROJECT.md into a token-efficient cold-start prompt."""
        content = re.sub(r"^---\n.*?\n---\n", "", project_md, flags=re.DOTALL)
        sections = self._parse_sections(content)
        parts: list[str] = []

        if "Identity" in sections:
            parts.append("## Identity\n" + sections["Identity"].strip())

        if "Architecture" in sections:
            parts.append("## Architecture\n" + sections["Architecture"].strip())

        if "Module Map" in sections:
            compressed = self._compress_module_map(sections["Module Map"])
            parts.append("## Module Map\n" + compressed.strip())

        if "Patterns & Conventions" in sections:
            parts.append(
                "## Patterns & Conventions\n"
                + sections["Patterns & Conventions"].strip()
            )

        if self.config.include_tech_debt and "Tech Debt & Known Issues" in sections:
            parts.append(
                "## Tech Debt & Known Issues\n"
                + sections["Tech Debt & Known Issues"].strip()
            )

        active_state = self._get_active_state()
        if active_state:
            parts.append(active_state)

        result = "\n\n".join(part for part in parts if part.strip()) + "\n"

        token_estimate = self._estimate_tokens(result)
        if token_estimate > self.config.context_max_tokens:
            max_chars = max(self.config.context_max_tokens * 4, 0)
            result = (
                result[:max_chars].rstrip()
                + "\n\n[Truncated to fit token budget]\n"
            )

        return result

    def update_cold_start(self) -> str:
        """Re-generate COLD_START.md from existing PROJECT.md and active state."""
        project_md_path = self.deeprepo_dir / "PROJECT.md"
        if not project_md_path.is_file():
            raise FileNotFoundError(
                f"PROJECT.md not found at {project_md_path}. "
                "Run `deeprepo init` to generate project context."
            )

        project_md = project_md_path.read_text(encoding="utf-8")
        cold_start = self.generate_cold_start(project_md)

        cold_start_path = self.deeprepo_dir / "COLD_START.md"
        cold_start_path.write_text(cold_start, encoding="utf-8")
        return cold_start

    def _parse_sections(self, markdown: str) -> dict[str, str]:
        """Parse markdown by ## headers into a header->content mapping."""
        sections: dict[str, str] = {}
        current_header: str | None = None
        current_lines: list[str] = []

        for line in markdown.splitlines():
            match = re.match(r"^##\s+(.+?)\s*$", line)
            if match:
                if current_header is not None:
                    sections[current_header] = "\n".join(current_lines).strip() + "\n"
                current_header = match.group(1)
                current_lines = []
                continue

            if current_header is not None:
                current_lines.append(line)

        if current_header is not None:
            sections[current_header] = "\n".join(current_lines).strip() + "\n"

        return sections

    def _compress_module_map(self, module_map_content: str) -> str:
        """Keep only each module header and the first descriptive line."""
        lines = module_map_content.splitlines()
        compressed: list[str] = []
        index = 0

        while index < len(lines):
            line = lines[index]
            if line.startswith("### "):
                compressed.append(line)
                index += 1

                while index < len(lines) and not lines[index].strip():
                    index += 1

                if index < len(lines) and not lines[index].startswith("### "):
                    compressed.append(lines[index])
                continue

            if "### " not in module_map_content:
                compressed.append(line)

            index += 1

        return "\n".join(compressed).strip()

    def _get_active_state(self) -> str:
        """Build the Active State section for cold-start."""
        recent_sessions: list[str] = []

        session_log = self.deeprepo_dir / "SESSION_LOG.md"
        if session_log.is_file():
            log_text = session_log.read_text(encoding="utf-8")
            entries = re.findall(
                r"^##\s+(.+?)\n(.*?)(?=^##\s+|\Z)",
                log_text,
                flags=re.MULTILINE | re.DOTALL,
            )
            for title, body in entries:
                body_lines = [line.strip() for line in body.splitlines() if line.strip()]
                summary = body_lines[0] if body_lines else ""
                if summary:
                    recent_sessions.append(f"- {title}: {summary}")
                else:
                    recent_sessions.append(f"- {title}")

        max_entries = max(self.config.session_log_count, 0)
        if max_entries == 0:
            recent_sessions = []
        elif len(recent_sessions) > max_entries:
            recent_sessions = recent_sessions[-max_entries:]

        if not recent_sessions:
            recent_sessions = ["- None yet"]

        status_text = "None"
        current_task_text = "None"

        scratchpad = self.deeprepo_dir / "SCRATCHPAD.md"
        if scratchpad.is_file():
            scratchpad_sections = self._parse_sections(
                scratchpad.read_text(encoding="utf-8")
            )
            status_candidate = scratchpad_sections.get("Status", "").strip()
            if status_candidate:
                status_text = status_candidate

            task_candidate = scratchpad_sections.get("Current Task", "").strip()
            if task_candidate and task_candidate != "[Write task specifications here]":
                current_task_text = task_candidate

        parts = [
            "## Active State",
            "",
            "### Recent Sessions",
            *recent_sessions,
            "",
            "### Scratchpad Status",
            status_text,
            "",
            "### Current Task",
            current_task_text,
        ]
        return "\n".join(parts).strip()

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate."""
        return len(text) // 4
