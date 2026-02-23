"""Interactive first-run onboarding for the deeprepo TUI."""

import os
from pathlib import Path

import yaml


GLOBAL_CONFIG_DIR = Path.home() / ".deeprepo"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"


def load_global_api_key() -> str | None:
    """Read API key from ~/.deeprepo/config.yaml if it exists."""
    if not GLOBAL_CONFIG_FILE.is_file():
        return None

    try:
        data = yaml.safe_load(GLOBAL_CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None

    if not isinstance(data, dict):
        return None

    api_key = data.get("api_key")
    if not isinstance(api_key, str):
        return None

    key = api_key.strip()
    return key or None


def save_global_api_key(api_key: str) -> None:
    """Save API key to ~/.deeprepo/config.yaml and set in os.environ."""
    key = api_key.strip()
    if not key:
        raise ValueError("api_key cannot be empty")

    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    GLOBAL_CONFIG_FILE.write_text(
        yaml.safe_dump({"api_key": key}, sort_keys=False),
        encoding="utf-8",
    )
    os.environ["OPENROUTER_API_KEY"] = key


def needs_onboarding(project_path: str) -> dict:
    """Check what onboarding steps are needed.

    Returns:
        {
            "needs_api_key": bool,   # No OPENROUTER_API_KEY in env or global config
            "needs_init": bool,      # No .deeprepo/ in project directory
        }
    """
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    needs_api_key = not bool(env_key)

    if needs_api_key:
        global_key = load_global_api_key()
        if global_key:
            os.environ["OPENROUTER_API_KEY"] = global_key
            needs_api_key = False

    project_deeprepo_dir = Path(project_path).resolve() / ".deeprepo"
    needs_init = not project_deeprepo_dir.is_dir()

    return {
        "needs_api_key": needs_api_key,
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
            "project_initialized": bool,
            "skipped": bool,  # True if nothing was needed
        }
    """
    if input_fn is None:
        input_fn = input

    check = needs_onboarding(project_path)
    skipped = not (check["needs_api_key"] or check["needs_init"])

    result = {
        "api_key_configured": not check["needs_api_key"],
        "project_initialized": not check["needs_init"],
        "skipped": skipped,
    }

    if skipped:
        return result

    if check["needs_api_key"]:
        print("deeprepo uses OpenRouter for AI model access.")
        print("Get your key at: https://openrouter.ai/keys")
        api_key = input_fn("Enter your OpenRouter API key (or press Enter to skip): ").strip()
        if api_key:
            save_global_api_key(api_key)
            print(f"API key saved to ~/.deeprepo/config.yaml ({api_key[:8]}...)")
            result["api_key_configured"] = True
        else:
            print("Skipped. Commands needing API access won't work until a key is set.")
            result["api_key_configured"] = False

    if check["needs_init"]:
        should_analyze = input_fn("Would you like to analyze this project now? (y/n): ").strip()
        if should_analyze.lower() in {"y", "yes"}:
            print("Run /init after entering the shell to analyze your project.")
        else:
            print("No problem. Run /init when you're ready.")
        result["project_initialized"] = False

    result["skipped"] = False
    return result
