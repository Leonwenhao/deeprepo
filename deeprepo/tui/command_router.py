"""Slash command routing for the TUI shell."""

import argparse
import shlex
from pathlib import Path

from rich.console import Console


_console = Console()


def _rewrite_env_error(exc: EnvironmentError) -> dict:
    """Translate EnvironmentError messages for TUI users."""
    msg = str(exc)
    if "ANTHROPIC_API_KEY" in msg:
        return {
            "status": "error",
            "message": "Anthropic API key not set. Run: export ANTHROPIC_API_KEY=sk-ant-...",
            "data": {},
        }
    if "OPENROUTER_API_KEY" in msg:
        return {
            "status": "error",
            "message": "OpenRouter API key not set. Run: export OPENROUTER_API_KEY=sk-or-...",
            "data": {},
        }
    return {"status": "error", "message": f"Command failed: {exc}", "data": {}}


class CommandRouter:
    """Parses slash commands and dispatches to existing cmd_* handlers."""

    def __init__(self, project_path: str):
        self.project_path = project_path
        self._commands = self._build_command_registry()

    def route(self, raw_input: str) -> dict:
        """Parse and execute a slash command. Returns result dict."""
        text = raw_input.lstrip("/").strip()
        if not text:
            return {
                "status": "error",
                "message": "Empty command. Type /help for available commands.",
                "data": {},
            }

        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return {"status": "error", "message": f"Parse error: {exc}", "data": {}}

        cmd_name = tokens[0].lower()
        cmd_args = tokens[1:]

        if cmd_name not in self._commands:
            available = ", ".join(f"/{cmd}" for cmd in self._commands)
            return {
                "status": "error",
                "message": f"Unknown command: /{cmd_name}. Available: {available}",
                "data": {},
            }

        try:
            return self._commands[cmd_name]["handler"](cmd_args)
        except Exception as exc:
            return {"status": "error", "message": f"Command failed: {exc}", "data": {}}

    def _build_command_registry(self) -> dict:
        return {
            "init": {
                "handler": self._do_init,
                "help": "Analyze project and generate .deeprepo/ context",
            },
            "context": {
                "handler": self._do_context,
                "help": "Copy project context to clipboard",
            },
            "status": {"handler": self._do_status, "help": "Show project status"},
            "log": {"handler": self._do_log, "help": "View or add to session log"},
            "refresh": {
                "handler": self._do_refresh,
                "help": "Refresh project context",
            },
            "help": {"handler": self._do_help, "help": "Show available commands"},
            "team": {
                "handler": self._do_team,
                "help": "Switch team configuration (coming soon)",
            },
            "quit": {"handler": self._do_quit, "help": "Exit deeprepo"},
            "exit": {"handler": self._do_exit, "help": "Exit deeprepo"},
        }

    def _do_help(self, tokens: list[str]) -> dict:
        """List available commands."""
        del tokens
        lines = []
        for name, entry in self._commands.items():
            lines.append(f"  /{name:<12} {entry['help']}")
        return {
            "status": "success",
            "message": "Available commands",
            "data": {
                "commands": list(self._commands.keys()),
                "help_text": "\n".join(lines),
            },
        }

    def _do_init(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_init

        deeprepo_dir = Path(self.project_path) / ".deeprepo"
        project_md = deeprepo_dir / "PROJECT.md"

        # Auto-force initialization when .deeprepo exists but PROJECT.md is missing.
        explicit_force = "--force" in tokens
        auto_force = deeprepo_dir.is_dir() and not project_md.is_file()
        force = explicit_force or auto_force
        args = argparse.Namespace(
            path=self.project_path,
            force=force,
            quiet=True,
            team="analyst",
            root_model=None,
            sub_model=None,
            max_turns=None,
        )
        try:
            with _console.status("[cyan]Analyzing project...[/cyan]", spinner="dots"):
                return cmd_init(args, quiet=True)
        except EnvironmentError as exc:
            return _rewrite_env_error(exc)

    def _do_context(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_context

        fmt = "markdown"
        copy_flag = True
        for i, tok in enumerate(tokens):
            if tok == "--format" and i + 1 < len(tokens):
                fmt = tokens[i + 1]
            if tok == "--no-copy":
                copy_flag = False

        args = argparse.Namespace(
            path=self.project_path,
            copy=copy_flag,
            format=fmt,
        )
        return cmd_context(args, quiet=True)

    def _do_status(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_status

        del tokens
        args = argparse.Namespace(path=self.project_path)
        return cmd_status(args, quiet=True)

    def _do_log(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_log

        if not tokens:
            args = argparse.Namespace(
                path=self.project_path, action="show", message=None, count=5
            )
            return cmd_log(args, quiet=True)

        if tokens[0].lower() == "show":
            count = 5
            if len(tokens) > 1:
                try:
                    count = int(tokens[1])
                except ValueError:
                    pass
            args = argparse.Namespace(
                path=self.project_path, action="show", message=None, count=count
            )
            return cmd_log(args, quiet=True)

        if tokens[0].lower() == "add" and len(tokens) > 1:
            message = " ".join(tokens[1:])
            args = argparse.Namespace(
                path=self.project_path, action=message, message=None, count=5
            )
            return cmd_log(args, quiet=True)

        message = " ".join(tokens)
        args = argparse.Namespace(
            path=self.project_path, action=message, message=None, count=5
        )
        return cmd_log(args, quiet=True)

    def _do_refresh(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_refresh

        full = "--full" in tokens
        args = argparse.Namespace(
            path=self.project_path,
            full=full,
            quiet=True,
        )
        try:
            with _console.status("[cyan]Refreshing context...[/cyan]", spinner="dots"):
                return cmd_refresh(args, quiet=True)
        except EnvironmentError as exc:
            return _rewrite_env_error(exc)

    def _do_team(self, tokens: list[str]) -> dict:
        del tokens
        return {"status": "info", "message": "Team switching coming soon", "data": {}}

    def _do_quit(self, tokens: list[str]) -> dict:
        del tokens
        return {"status": "exit", "message": "Goodbye.", "data": {}}

    def _do_exit(self, tokens: list[str]) -> dict:
        del tokens
        return {"status": "exit", "message": "Goodbye.", "data": {}}
