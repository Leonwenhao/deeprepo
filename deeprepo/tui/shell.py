"""Interactive TUI shell for deeprepo."""

import os
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings

from deeprepo.tui.command_router import CommandRouter
from deeprepo.tui.completions import build_completer
from deeprepo.tui.onboarding import needs_onboarding, run_onboarding
from deeprepo.tui.prompt_builder import PromptBuilder
from deeprepo.tui.session_state import SessionState

# Rich is optional — import defensively
try:
    from rich.console import Console
    from rich.panel import Panel

    _console = Console()
except ImportError:
    _console = None


class DeepRepoShell:
    """Persistent interactive session for deeprepo.

    Routes slash commands to the command router (S3, stubbed for now)
    and natural language input to the prompt builder (S5, stubbed for now).
    """

    def __init__(self, project_path: str = "."):
        self.project_path = os.path.abspath(project_path)
        self.completer = build_completer()
        self.session = PromptSession(history=InMemoryHistory(), completer=self.completer)
        self.router = CommandRouter(self.project_path)
        self.prompt_builder = PromptBuilder(self.project_path)
        self.state = SessionState.from_project(self.project_path)
        self.key_bindings = self._build_key_bindings()

    def run(self):
        """Main loop. Blocks until exit."""
        check = needs_onboarding(self.project_path)
        if check["needs_api_key"] or check["needs_init"]:
            run_onboarding(self.project_path)
            self.state.refresh()

        self._print_welcome()
        while True:
            try:
                user_input = self.session.prompt(
                    "deeprepo> ",
                    bottom_toolbar=self._get_toolbar,
                    key_bindings=self.key_bindings,
                ).strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    break
                self._handle_input(user_input)
            except (EOFError, KeyboardInterrupt):
                break
        self._print_goodbye()

    def _handle_input(self, text: str):
        """Route input to slash command handler or natural language handler."""
        if text.startswith("/"):
            self._handle_slash_command(text)
        else:
            self._handle_natural_language(text)

    def _handle_slash_command(self, text: str):
        """Route slash command through CommandRouter and display result."""
        result = self.router.route(text)
        self._display_result(result)

        cmd_text = text.lstrip("/")
        cmd = cmd_text.split()[0].lower() if cmd_text.strip() else ""
        if cmd in ("init", "refresh"):
            self.state.refresh()

    def _handle_natural_language(self, text: str):
        """Build context-rich prompt and copy it to clipboard."""
        result = self.prompt_builder.build(text)
        self._display_result(result)

        if result.get("status") == "success":
            self.state.record_prompt(text, result["data"].get("prompt", ""))

    def _display_result(self, result: dict):
        """Display a command result dict using Rich panels or plain text."""
        status = result.get("status", "info")
        message = result.get("message", "")
        data = result.get("data", {})

        if _console is not None:
            if status == "error":
                _console.print(
                    Panel(
                        f"[red]{message}[/red]",
                        title="Error",
                        border_style="red",
                        expand=False,
                    )
                )
            elif status == "success":
                _console.print(
                    Panel(
                        message,
                        title="[green]OK[/green]",
                        border_style="green",
                        expand=False,
                    )
                )
            else:
                _console.print(message)

            if "help_text" in data:
                _console.print(data["help_text"])
        else:
            if status == "error":
                print(f"Error: {message}")
            elif status == "success":
                print(f"OK: {message}")
            else:
                print(message)

            if "help_text" in data:
                print(data["help_text"])

    def _get_version(self) -> str:
        """Read package version. Returns dev if package metadata is unavailable."""
        try:
            from importlib.metadata import version

            return version("deeprepo-cli")
        except Exception:
            return "dev"

    def _get_toolbar(self) -> str:
        """Build status toolbar text."""
        project_name = self.state.project_name or Path(self.project_path).name
        prompt_count = len(self.state.prompt_history)
        prompt_text = (
            "0 prompts generated"
            if prompt_count == 0
            else ("1 prompt generated" if prompt_count == 1 else f"{prompt_count} prompts generated")
        )

        return (
            f"deeprepo | Project: {project_name} | Context: {self.state.context_age} | "
            f"{prompt_text} | Ctrl-R refresh | Ctrl-L clear"
        )

    def _build_key_bindings(self):
        """Create key bindings for shell usability helpers."""
        kb = KeyBindings()

        @kb.add("c-l")
        def _clear_screen(event):
            event.app.renderer.clear()

        @kb.add("c-r")
        def _refresh_context(event):
            self.state.refresh()
            event.app.output.write("\nContext refreshed.\n")
            event.app.output.flush()

        return kb

    def _print_welcome(self):
        """Print welcome banner with project info."""
        version = self._get_version()
        project_name = self.state.project_name or Path(self.project_path).name
        if self.state.initialized:
            context_line = (
                f"Context: {self.state.context_age} "
                f"\u00b7 {self.state.context_tokens:,} tokens \u00b7 {self.state.files_tracked} files"
            )
        else:
            context_line = "Context: Not initialized (run /init)"

        banner_text = (
            f"  deeprepo v{version}\n"
            f"  Project: {project_name}\n"
            f"  {context_line}\n"
            "  \n"
            "  Type /help for commands or ask anything."
        )

        if _console is not None:
            try:
                _console.print()
                _console.print(Panel(banner_text, expand=False))
                _console.print()
            except Exception:
                print(banner_text)
                print()
        else:
            print()
            print(banner_text)
            print()

    def _print_goodbye(self):
        """Print exit message."""
        if _console is not None:
            _console.print("\n[dim]Goodbye.[/dim]")
        else:
            print("\nGoodbye.")
