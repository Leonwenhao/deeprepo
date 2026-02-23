"""Autocomplete definitions for the deeprepo TUI shell."""

from prompt_toolkit.completion import WordCompleter


COMMAND_LIST = [
    "/init",
    "/context",
    "/context --copy",
    "/context --format cursor",
    "/status",
    "/log",
    "/log add",
    "/log show",
    "/refresh",
    "/help",
    "/team",
    "exit",
    "quit",
]


def build_completer() -> WordCompleter:
    """Create slash-command autocomplete completer."""
    return WordCompleter(COMMAND_LIST, sentence=True, ignore_case=True)
