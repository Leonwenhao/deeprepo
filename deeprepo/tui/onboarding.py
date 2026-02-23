"""Interactive first-run onboarding for the deeprepo TUI."""

import os
from pathlib import Path

import yaml
from rich.console import Console


GLOBAL_CONFIG_DIR = Path.home() / ".deeprepo"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"
_console = Console()


def load_global_api_keys() -> dict:
    """Read API keys from ~/.deeprepo/config.yaml if it exists.

    Returns:
        {"api_key": str | None, "anthropic_api_key": str | None}
    """
    result = {"api_key": None, "anthropic_api_key": None}
    if not GLOBAL_CONFIG_FILE.is_file():
        return result

    try:
        data = yaml.safe_load(GLOBAL_CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return result

    if not isinstance(data, dict):
        return result

    for field in ("api_key", "anthropic_api_key"):
        val = data.get(field)
        if isinstance(val, str) and val.strip():
            result[field] = val.strip()

    return result


def load_global_api_key() -> str | None:
    """Legacy wrapper — returns OpenRouter key only."""
    return load_global_api_keys()["api_key"]


def save_global_api_keys(
    openrouter_key: str | None = None,
    anthropic_key: str | None = None,
) -> None:
    """Save API key(s) to ~/.deeprepo/config.yaml and set in os.environ."""
    existing = load_global_api_keys()

    openrouter = (openrouter_key or "").strip() or existing["api_key"]
    anthropic = (anthropic_key or "").strip() or existing["anthropic_api_key"]

    if not openrouter and not anthropic:
        raise ValueError("At least one API key must be provided")

    config = {}
    if openrouter:
        config["api_key"] = openrouter
        os.environ["OPENROUTER_API_KEY"] = openrouter
    if anthropic:
        config["anthropic_api_key"] = anthropic
        os.environ["ANTHROPIC_API_KEY"] = anthropic

    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    GLOBAL_CONFIG_FILE.write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )


def save_global_api_key(api_key: str) -> None:
    """Legacy wrapper — saves OpenRouter key only."""
    save_global_api_keys(openrouter_key=api_key)


def needs_onboarding(project_path: str) -> dict:
    """Check what onboarding steps are needed.

    Returns:
        {
            "needs_api_key": bool,        # No OPENROUTER_API_KEY (backward compat key)
            "needs_anthropic_key": bool,  # No ANTHROPIC_API_KEY
            "needs_init": bool,           # No .deeprepo/ in project directory
        }
    """
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    needs_openrouter = not bool(env_key)

    env_anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    needs_anthropic = not bool(env_anthropic_key)

    if needs_openrouter or needs_anthropic:
        keys = load_global_api_keys()
        if needs_openrouter and keys["api_key"]:
            os.environ["OPENROUTER_API_KEY"] = keys["api_key"]
            needs_openrouter = False
        if needs_anthropic and keys["anthropic_api_key"]:
            os.environ["ANTHROPIC_API_KEY"] = keys["anthropic_api_key"]
            needs_anthropic = False

    project_deeprepo_dir = Path(project_path).resolve() / ".deeprepo"
    needs_init = not project_deeprepo_dir.is_dir()

    return {
        "needs_api_key": needs_openrouter,
        "needs_anthropic_key": needs_anthropic,
        "needs_init": needs_init,
    }


def run_onboarding(project_path: str, *, input_fn=None) -> dict:
    """Run the interactive onboarding flow.

    Args:
        project_path: Path to the current project
        input_fn: Optional callable for getting user input (default: built-in input()).
                  Used for testing. Signature: input_fn(prompt: str) -> str

    Returns:
        {
            "api_key_configured": bool,
            "anthropic_key_configured": bool,
            "project_initialized": bool,
            "skipped": bool,  # True if nothing was needed
        }
    """
    if input_fn is None:
        input_fn = input

    check = needs_onboarding(project_path)
    needs_any_key = check["needs_api_key"] or check.get("needs_anthropic_key", False)
    skipped = not (needs_any_key or check["needs_init"])

    result = {
        "api_key_configured": not check["needs_api_key"],
        "anthropic_key_configured": not check.get("needs_anthropic_key", False),
        "project_initialized": not check["needs_init"],
        "skipped": skipped,
    }

    if skipped:
        return result

    if check.get("needs_anthropic_key", False):
        _console.print("[cyan]deeprepo uses Anthropic Claude as the root orchestrator model.[/cyan]")
        _console.print("[dim]Get your key at: https://console.anthropic.com/settings/keys[/dim]")
        ant_key = input_fn("Enter your Anthropic API key (or press Enter to skip): ").strip()
        if ant_key:
            save_global_api_keys(anthropic_key=ant_key)
            _console.print(
                f"[green]Anthropic key saved to ~/.deeprepo/config.yaml ({ant_key[:8]}...).[/green]"
            )
            result["anthropic_key_configured"] = True
        else:
            _console.print("[yellow]Skipped. /init requires an Anthropic API key.[/yellow]")
            result["anthropic_key_configured"] = False

    if check["needs_api_key"]:
        _console.print("[cyan]deeprepo uses OpenRouter for sub-model AI workers.[/cyan]")
        _console.print("[dim]Get your key at: https://openrouter.ai/keys[/dim]")
        or_key = input_fn("Enter your OpenRouter API key (or press Enter to skip): ").strip()
        if or_key:
            save_global_api_keys(openrouter_key=or_key)
            _console.print(
                f"[green]OpenRouter key saved to ~/.deeprepo/config.yaml ({or_key[:8]}...).[/green]"
            )
            result["api_key_configured"] = True
        else:
            _console.print(
                "[yellow]Skipped. Commands needing AI workers won't work until a key is set.[/yellow]"
            )
            result["api_key_configured"] = False

    if check["needs_init"]:
        should_analyze = input_fn("Would you like to analyze this project now? (y/n): ").strip()
        if should_analyze.lower() in {"y", "yes"}:
            _console.print("[cyan]Run /init after entering the shell to analyze your project.[/cyan]")
        else:
            _console.print("[dim]No problem. Run /init when you're ready.[/dim]")
        result["project_initialized"] = False

    result["skipped"] = False
    return result
