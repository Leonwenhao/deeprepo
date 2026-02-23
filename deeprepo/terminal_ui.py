"""Terminal output formatting with optional rich support."""

from __future__ import annotations

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    HAS_RICH = True
except ImportError:  # pragma: no cover - exercised when rich is absent
    HAS_RICH = False

# Module-level console — only created if rich is available.
# force_terminal=False lets rich auto-detect TTY (important for tests).
_console = Console() if HAS_RICH else None


def _rich_tty() -> bool:
    """Return True when rich is available and attached to a real terminal."""
    return _console is not None and _console.is_terminal


def print_msg(text: str = "", **kwargs) -> None:
    """Print a message. Uses rich console when available."""
    if _console is not None:
        _console.print(text, highlight=False, **kwargs)
    else:
        print(text)


def print_error(text: str) -> None:
    """Print an error message."""
    if _console is not None:
        _console.print(f"[bold red]Error:[/bold red] {text}", highlight=False)
    else:
        print(f"Error: {text}")


def print_header(project_name: str, stack: str, path: str) -> None:
    """Print init header with project info."""
    print_msg(f"deeprepo init: {project_name}")
    print_msg(f"  Stack: {stack}")
    print_msg(f"  Path: {path}")
    print_msg()


def print_init_complete(
    generated_files: dict,
    cost: float,
    turns: int,
    sub_dispatches: int,
) -> None:
    """Print completion info after init."""
    print_msg("Done! Generated:")
    for path in generated_files.values():
        print_msg(f"  {path}")
    print_msg()
    print_msg(f"  Cost: ${cost:.4f}")
    print_msg(f"  Turns: {turns}")
    print_msg(f"  Sub-LLM dispatches: {sub_dispatches}")


def print_onboarding() -> None:
    """Print onboarding guidance after init/new."""
    content = (
        "\n"
        "  Your project now has AI memory.\n"
        "\n"
        "  Start every AI session:\n"
        "    $ deeprepo context --copy\n"
        "    Then paste into Claude Code, Cursor, ChatGPT, etc.\n"
        "\n"
        "  After each session:\n"
        '    $ deeprepo log "what you did and what\'s next"\n'
        "\n"
        "  When your code changes:\n"
        "    $ deeprepo refresh\n"
    )

    if _rich_tty():
        _console.print()
        _console.print(Panel(content, expand=False))
    else:
        print()
        border = "+" + "-" * 58 + "+"
        print(border)
        for line in content.strip().splitlines():
            print(f"| {line:<56} |")
        print(border)


def print_status_header(project_name: str) -> None:
    """Print status command header."""
    if _console is not None:
        _console.print(f"[bold]deeprepo[/bold] - {project_name}", highlight=False)
    else:
        print(f"deeprepo - {project_name}")


def print_status_line(label: str, marker: str, detail: str) -> None:
    """Print a single status line with marker."""
    if _console is not None:
        color_map = {
            "[OK]": "[green][OK][/green]",
            "[!!]": "[yellow][!!][/yellow]",
            "[X]": "[red][X][/red]",
            "[~]": "[dim][~][/dim]",
        }
        styled_marker = color_map.get(marker, marker)
        _console.print(f"  {label} {styled_marker} {detail}", highlight=False)
    else:
        print(f"  {label} {marker} {detail}")


def print_team_list(teams: list) -> None:
    """Print available teams."""
    if _rich_tty():
        table = Table(title="Available Teams", show_header=True, header_style="bold")
        table.add_column("Name")
        table.add_column("Display Name")
        table.add_column("Description")
        table.add_column("Agents")
        table.add_column("Est. Cost")
        for team in teams:
            agents_str = ", ".join(agent.role for agent in team.agents)
            table.add_row(
                team.name,
                team.display_name,
                team.description,
                agents_str,
                team.estimated_cost_per_task or "-",
            )
        _console.print(table)
    else:
        # Plain text fallback — must match existing test assertions.
        print("Available teams:\n")
        for team in teams:
            print(f"  {team.name}")
            print(f"    {team.display_name} — {team.description}")
            if team.tagline:
                print(f"    {team.tagline}")
            agents_str = ", ".join(agent.role for agent in team.agents)
            print(f"    Agents: {agents_str}")
            if team.estimated_cost_per_task:
                print(f"    Est. cost: {team.estimated_cost_per_task}")
            print()


def print_refresh_complete(changed_files: int, cost: float, turns: int) -> None:
    """Print refresh completion summary."""
    print_msg()
    print_msg("Refresh complete:")
    print_msg(f"  Changed files: {changed_files}")
    print_msg(f"  Cost: ${cost:.4f}")
    print_msg(f"  Turns: {turns}")


def print_context_copied(token_count: int) -> None:
    """Print confirmation after context --copy."""
    print_msg(f"Cold-start prompt copied to clipboard ({token_count} estimated tokens)")
