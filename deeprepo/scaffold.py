import os
import re
from pathlib import Path

from .config_manager import ConfigManager, ProjectConfig
from .context_generator import ContextGenerator
from .teams.base import TeamConfig


class ProjectScaffolder:
    """Generate a new project with AI-generated structure."""

    def __init__(self, team: TeamConfig):
        self.team = team

    def scaffold(
        self,
        description: str,
        stack: dict,
        project_name: str,
        output_dir: str,
    ) -> dict:
        """Generate a new project and initialize .deeprepo context."""
        project_path = Path(output_dir) / project_name
        project_path.mkdir(parents=True, exist_ok=True)

        prompt = self.build_scaffold_prompt(description, stack, project_name)
        response = self._call_llm(prompt)
        parsed = self.parse_scaffold_response(response)

        created_files: list[str] = []
        for filepath, content in parsed["files"].items():
            full_path = project_path / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            created_files.append(filepath)

        config = ProjectConfig(
            project_name=project_name,
            project_description=description,
            team=self.team.name,
        )
        if stack.get("language"):
            # Reserved for stack-specific defaults in future iterations.
            pass

        cm = ConfigManager(str(project_path))
        cm.initialize(config)

        config = cm.load_config()
        state = cm.load_state()
        state.created_with = "new"
        state.original_intent = description

        generator = ContextGenerator(str(project_path), config)
        generator.generate(parsed["summary"], state)
        cm.save_state(state)

        from .cli_commands import append_log_entry

        append_log_entry(
            project_path / ".deeprepo",
            f"Project created with deeprepo new: {description}",
        )

        generator.update_cold_start()

        return {
            "project_path": str(project_path),
            "files": created_files,
            "summary": parsed["summary"],
        }

    def build_scaffold_prompt(
        self, description: str, stack: dict, project_name: str
    ) -> str:
        """Build the prompt that generates project structure."""
        language = stack.get("language", "Python")
        framework = stack.get("framework", "")

        stack_str = language
        if framework:
            stack_str = f"{language}/{framework}"

        return (
            f"You are generating a new software project called '{project_name}'.\n\n"
            f"Description: {description}\n"
            f"Stack: {stack_str}\n\n"
            "Generate a clean, minimal project scaffold (5-15 files). "
            "Include source code, configuration files, a README, and basic tests.\n\n"
            "Output format — use these EXACT delimiters:\n\n"
            "For each file:\n"
            "===FILE: path/to/file===\n"
            "[file content]\n"
            "===END_FILE===\n\n"
            "After all files, provide a project summary:\n"
            "===PROJECT_SUMMARY===\n"
            "[Structured documentation using these sections:]\n"
            "## Identity\n"
            "[language, framework, package manager, structure]\n"
            "## Architecture\n"
            "[how the system works, entry points, data flow]\n"
            "## Module Map\n"
            "[key modules with purpose]\n"
            "## Patterns & Conventions\n"
            "[coding style, naming, error handling]\n"
            "## Tech Debt & Known Issues\n"
            "[none for a new project — state that this is a fresh scaffold]\n"
            "===END_SUMMARY===\n"
        )

    def parse_scaffold_response(self, response: str) -> dict:
        """Parse LLM response into {filepath: content} dict + summary."""
        files: dict[str, str] = {}
        for match in re.finditer(
            r"===FILE:\s*(.+?)===\n(.*?)===END_FILE===",
            response,
            re.DOTALL,
        ):
            filepath = match.group(1).strip()
            content = match.group(2)
            if content.startswith("\n"):
                content = content[1:]
            if content.endswith("\n"):
                content = content[:-1]
            files[filepath] = content

        summary = ""
        summary_match = re.search(
            r"===PROJECT_SUMMARY===\n(.*?)===END_SUMMARY===",
            response,
            re.DOTALL,
        )
        if summary_match:
            summary = summary_match.group(1).strip()

        if not summary:
            file_list = "\n".join(f"- {filename}" for filename in sorted(files.keys()))
            summary = (
                "## Identity\nNew project scaffold\n\n"
                "## Architecture\nGenerated scaffold\n\n"
                f"## Module Map\n{file_list}\n\n"
                "## Patterns & Conventions\nStandard conventions\n\n"
                "## Tech Debt & Known Issues\nFresh scaffold — no tech debt\n"
            )

        return {"files": files, "summary": summary}

    def _call_llm(self, prompt: str) -> str:
        """Call the team's primary agent via OpenRouter."""
        import openai

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY to use deeprepo new."
            )

        model = (
            self.team.agents[0].model
            if self.team.agents
            else "anthropic/claude-sonnet-4-6"
        )

        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
            temperature=0.0,
        )

        return response.choices[0].message.content or ""
