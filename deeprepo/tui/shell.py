"""Interactive TUI shell for deeprepo."""

import os
import re
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.panel import Panel

from deeprepo.tui.command_router import CommandRouter
from deeprepo.tui.completions import build_completer
from deeprepo.tui.onboarding import needs_onboarding, run_onboarding
from deeprepo.tui.prompt_builder import PromptBuilder
from deeprepo.tui.session_state import SessionState

_console = Console()


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
        self._should_exit = False

    def run(self):
        """Main loop. Blocks until exit."""
        check = needs_onboarding(self.project_path)
        if check["needs_api_key"] or check.get("needs_anthropic_key", False) or check["needs_init"]:
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
                if self._should_exit:
                    break
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
        if result.get("status") == "exit":
            self._should_exit = True
            return
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
        """Display a command result dict with Rich styling."""
        status = result.get("status", "info")
        message = result.get("message", "")
        data = result.get("data", {})

        try:
            if status == "error":
                _console.print(
                    Panel(
                        f"[bold red]Error:[/bold red] {message}",
                        border_style="red",
                        expand=False,
                    )
                )
            elif status == "success":
                _console.print(
                    Panel(
                        f"[bold green]OK:[/bold green] {message}",
                        border_style="green",
                        expand=False,
                    )
                )
            else:
                _console.print(f"[cyan]{message}[/cyan]")

            if "help_text" in data:
                help_text = re.sub(r"(/\w+)", r"[bold cyan]\1[/bold cyan]", data["help_text"])
                _console.print(help_text)
        except Exception:
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

        ascii_lines = [
            "[bold bright_cyan]     _                                [/bold bright_cyan]",
            "[bold cyan]  __| | ___  ___ _ __  _ __ ___ _ __   ___[/bold cyan]",
            "[bold magenta] / _` |/ _ \\/ _ \\ '_ \\| '__/ _ \\ '_ \\ / _ \\ [/bold magenta]",
            "[bold bright_magenta]| (_| |  __/  __/ |_) | | |  __/ |_) | (_) |[/bold bright_magenta]",
            "[bold purple] \\__,_|\\___|\\___|  __/|_|  \\___|  __/ \\___/[/bold purple]",
            "[bold bright_cyan]               |_|            |_|[/bold bright_cyan]",
        ]
        info_lines = [
            f"[dim]deeprepo v{version}[/dim]",
            f"[cyan]Project:[/cyan] {project_name}",
            f"[dim]{context_line}[/dim]",
            "[dim]Type /help for commands, /quit to exit, or just ask anything.[/dim]",
        ]

        try:
            print()
            for line in ascii_lines:
                _console.print(line)
            _console.print()
            for line in info_lines:
                _console.print(line)
            _console.print()
        except Exception:
            print("deeprepo")
            print(f"deeprepo v{version}")
            print(f"Project: {project_name}")
            print(context_line)
            print("Type /help for commands, /quit to exit, or just ask anything.")
            print()

    def _print_goodbye(self):
        """Print exit message."""
        try:
            _console.print("\n[dim cyan]Goodbye.[/dim cyan]")
        except Exception:
            print("\nGoodbye.")
