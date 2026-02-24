"""Best-effort version update check for CLI and TUI entry points."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from urllib.request import urlopen

from packaging.version import InvalidVersion, Version

from . import __version__

logger = logging.getLogger(__name__)

CACHE_PATH = Path.home() / ".deeprepo" / "update_check.json"
CACHE_TTL = timedelta(hours=24)
PYPI_URL = "https://pypi.org/pypi/deeprepo-cli/json"
PYPI_TIMEOUT_SECONDS = 2.0

try:
    from rich.console import Console
    from rich.panel import Panel

    _console = Console()
except Exception:  # pragma: no cover - rich import/runtime edge cases
    _console = None


def _stdout_is_tty() -> bool:
    """Return True when stdout appears interactive."""
    isatty = getattr(sys.stdout, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


def _read_cache(path: Path | None = None) -> dict[str, str] | None:
    """Read and validate the update cache schema."""
    cache_path = path or CACHE_PATH
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    last_checked = data.get("last_checked")
    latest_version = data.get("latest_version")
    if not isinstance(last_checked, str) or not isinstance(latest_version, str):
        return None
    return {"last_checked": last_checked, "latest_version": latest_version}


def _write_cache(latest_version: str, path: Path | None = None) -> None:
    """Persist latest version and check timestamp."""
    cache_path = path or CACHE_PATH
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "latest_version": latest_version,
        }
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        logger.debug("Failed to write update check cache", exc_info=True)


def _is_cache_fresh(last_checked: str, now: datetime | None = None) -> bool:
    """Return True when the timestamp is within CACHE_TTL."""
    try:
        checked_at = datetime.fromisoformat(last_checked)
    except Exception:
        return False

    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)

    current = now or datetime.now(timezone.utc)
    return current - checked_at <= CACHE_TTL


def _fetch_latest_version() -> str | None:
    """Fetch latest deeprepo-cli version from PyPI."""
    try:
        with urlopen(PYPI_URL, timeout=PYPI_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        latest = payload["info"]["version"]
        if isinstance(latest, str) and latest.strip():
            return latest.strip()
    except Exception:
        return None
    return None


def _get_latest_version() -> str | None:
    """Return latest known version using 24h cache policy."""
    cache_data = _read_cache()
    if cache_data and _is_cache_fresh(cache_data["last_checked"]):
        return cache_data["latest_version"]

    latest = _fetch_latest_version()
    if latest:
        _write_cache(latest)
    return latest


def _get_installed_version() -> str:
    """Return installed package version, falling back to local module version."""
    try:
        return package_version("deeprepo-cli")
    except (PackageNotFoundError, Exception):
        return __version__


def _print_plain_banner(current_version: str, latest_version: str) -> None:
    """Print a plain text upgrade banner."""
    inner_width = 50
    top = "╭" + ("─" * inner_width) + "╮"
    bottom = "╰" + ("─" * inner_width) + "╯"
    line1 = f"│  {'Update available: ' + current_version + ' → ' + latest_version:<48}│"
    line2 = "│  Run: pip install --upgrade deeprepo-cli             │"
    print(top)
    print(line1)
    print(line2)
    print(bottom)


def _print_banner(current_version: str, latest_version: str) -> None:
    """Print update message with rich when available, otherwise plain text."""
    if _console is not None and _console.is_terminal:
        try:
            _console.print(
                Panel(
                    (
                        f"[bold]Update available:[/bold] "
                        f"{current_version} [dim]→[/dim] {latest_version}\n"
                        "[bold]Run:[/bold] pip install --upgrade deeprepo-cli"
                    ),
                    border_style="cyan",
                    expand=False,
                )
            )
            return
        except Exception:
            logger.debug("Failed to print rich update banner", exc_info=True)

    _print_plain_banner(current_version, latest_version)


def check_for_update(quiet: bool = False) -> None:
    """Check PyPI for a newer version and print a banner when appropriate."""
    try:
        if os.environ.get("DEEPREPO_NO_UPDATE_CHECK", "").strip() in ("1", "true", "yes"):
            return

        if quiet or not _stdout_is_tty():
            return

        installed_version = _get_installed_version()
        latest_version = _get_latest_version()
        if not latest_version:
            return

        if Version(installed_version) < Version(latest_version):
            _print_banner(installed_version, latest_version)
    except (InvalidVersion, Exception):
        return
