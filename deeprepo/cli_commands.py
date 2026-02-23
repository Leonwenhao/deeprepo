"""Command handlers for new deeprepo CLI commands."""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from .config_manager import ProjectState
from . import terminal_ui as ui


ROOT_MODEL_MAP = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "minimax": "minimax/minimax-m2.5",
    "anthropic/claude-opus-4-6": "claude-opus-4-6",
    "anthropic/claude-sonnet-4-6": "claude-sonnet-4-6",
    "anthropic/claude-sonnet-4-5": "claude-sonnet-4-6",
}


def cmd_init(args, *, quiet=None):
    """Run context domain analysis and generate .deeprepo/ directory."""
    from .config_manager import ConfigManager, ProjectConfig
    from .context_generator import ContextGenerator
    from .rlm_scaffold import run_analysis

    project_path = getattr(args, "path", ".") or "."
    project_path = str(Path(project_path).resolve())
    quiet = quiet if quiet is not None else getattr(args, "quiet", False)
    force = getattr(args, "force", False)

    cm = ConfigManager(project_path)
    if cm.is_initialized():
        if not force:
            if not quiet:
                ui.print_error(f".deeprepo/ already exists at {cm.deeprepo_dir}")
                ui.print_msg("Use --force to overwrite.")
                sys.exit(1)
            return {
                "status": "error",
                "message": f".deeprepo/ already exists at {cm.deeprepo_dir}",
                "data": {},
            }
        shutil.rmtree(cm.deeprepo_dir, ignore_errors=True)

    config = ProjectConfig()
    config.project_name = cm.detect_project_name()
    stack = cm.detect_stack()
    cm.initialize(config)

    config = cm.load_config()
    team_name = getattr(args, "team", "analyst") or "analyst"
    from .teams import get_team
    get_team(team_name)  # Raises ValueError if invalid
    config.team = team_name

    language = stack.get("language", "").strip()
    framework = stack.get("framework", "").strip()
    if language and framework:
        config.project_description = f"{language} {framework} project"
    elif language:
        config.project_description = f"{language} project"
    else:
        config.project_description = "project"
    cm.save_config(config)

    if not quiet:
        stack_lang = stack.get("language", "unknown") or "unknown"
        stack_framework = stack.get("framework", "unknown") or "unknown"
        ui.print_header(
            config.project_name,
            f"{stack_lang}/{stack_framework}",
            project_path,
        )

    root_model_arg = getattr(args, "root_model", None)
    sub_model_arg = getattr(args, "sub_model", None)
    max_turns_arg = getattr(args, "max_turns", None)

    root_model = root_model_arg if root_model_arg is not None else config.root_model
    root_model = ROOT_MODEL_MAP.get(root_model, root_model)
    sub_model = sub_model_arg if sub_model_arg is not None else config.sub_model
    max_turns = max_turns_arg if max_turns_arg is not None else config.max_turns

    if not quiet:
        ui.print_msg("Analyzing project with context domain...")
        ui.print_msg()

    result = run_analysis(
        codebase_path=project_path,
        verbose=not quiet,
        max_turns=max_turns,
        root_model=root_model,
        sub_model=sub_model,
        use_cache=True,
        domain="context",
    )

    state = cm.load_state()
    state.analysis_cost = result["usage"].total_cost
    state.analysis_turns = result["turns"]
    state.sub_llm_dispatches = result["usage"].sub_calls
    state.last_refresh = datetime.now(timezone.utc).isoformat()
    if not state.created_with:
        state.created_with = "init"
    if not state.original_intent:
        state.original_intent = "Initialize deeprepo project context"

    generator = ContextGenerator(project_path, config)
    generated_files = generator.generate(result["analysis"], state)
    cm.save_state(state)

    if not quiet:
        ui.print_init_complete(
            generated_files,
            result["usage"].total_cost,
            result["turns"],
            result["usage"].sub_calls,
        )
        ui.print_msg()
        ui.print_msg("Next steps:")
        ui.print_msg("  deeprepo context --copy   # Copy cold-start to clipboard")
        ui.print_msg('  deeprepo log "message"    # Record session activity')
        ui.print_msg("  deeprepo status           # Check context health")
        ui.print_onboarding()

    return {
        "status": "success",
        "message": f"Initialized .deeprepo/ for {config.project_name}",
        "data": {
            "project_name": config.project_name,
            "project_path": project_path,
            "cost": result["usage"].total_cost,
            "turns": result["turns"],
            "sub_dispatches": result["usage"].sub_calls,
            "generated_files": list(generated_files.values()),
        },
    }


def cmd_list_teams(args, *, quiet=False):
    """List available teams."""
    from .teams import list_teams

    teams = list_teams()
    if not teams:
        if not quiet:
            ui.print_msg("No teams registered.")
        return {
            "status": "info",
            "message": "No teams registered",
            "data": {"teams": []},
        }
    if not quiet:
        ui.print_team_list(teams)
    return {
        "status": "success",
        "message": f"{len(teams)} teams available",
        "data": {"teams": [team.name for team in teams]},
    }


def cmd_new(args):
    """Interactive or non-interactive greenfield project creation."""
    from .scaffold import ProjectScaffolder
    from .teams import get_team

    description = getattr(args, "description", None)
    stack_str = getattr(args, "stack", None)
    name = getattr(args, "name", None)
    team_name = getattr(args, "team", "analyst") or "analyst"
    output = getattr(args, "output", ".") or "."
    yes = getattr(args, "yes", False)

    if not description:
        description = input("What are you building? ").strip()
        if not description:
            ui.print_msg("Description is required.")
            sys.exit(1)

    if not stack_str:
        ui.print_msg("\nStack options:")
        ui.print_msg("  1. python-fastapi")
        ui.print_msg("  2. python-django")
        ui.print_msg("  3. node-express")
        ui.print_msg("  4. typescript-nextjs")
        ui.print_msg("  5. other")
        choice = input("\nStack preference [1]: ").strip() or "1"
        stack_map = {
            "1": "python-fastapi",
            "2": "python-django",
            "3": "node-express",
            "4": "typescript-nextjs",
            "5": "other",
        }
        stack_str = stack_map.get(choice, choice)

    if not name:
        suggested = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:30]
        name_input = input(f"\nProject name [{suggested}]: ").strip()
        name = name_input if name_input else suggested

    stack = _parse_stack_string(stack_str)
    team = get_team(team_name)

    if not yes:
        ui.print_msg(f"\n  Project:     {name}")
        ui.print_msg(f"  Description: {description}")
        ui.print_msg(f"  Stack:       {stack_str}")
        ui.print_msg(f"  Team:        {team.display_name}")
        ui.print_msg(f"  Output:      {Path(output).resolve() / name}")
        if team.estimated_cost_per_task:
            ui.print_msg(f"  Est. cost:   {team.estimated_cost_per_task}")
        confirm = input("\nProceed? [Y/n] ").strip().lower()
        if confirm and confirm not in ("y", "yes"):
            ui.print_msg("Cancelled.")
            sys.exit(0)

    ui.print_msg(f"\nScaffolding {name}...")

    scaffolder = ProjectScaffolder(team)
    result = scaffolder.scaffold(
        description=description,
        stack=stack,
        project_name=name,
        output_dir=output,
    )

    ui.print_msg(f"\nCreated {name} at {result['project_path']}")
    ui.print_msg(f"  Files: {len(result['files'])}")
    for filepath in result["files"][:10]:
        ui.print_msg(f"    {filepath}")
    if len(result["files"]) > 10:
        ui.print_msg(f"    ... and {len(result['files']) - 10} more")
    ui.print_msg()
    ui.print_msg("Next steps:")
    ui.print_msg(f"  cd {result['project_path']}")
    ui.print_msg("  deeprepo context --copy   # Copy cold-start to clipboard")
    ui.print_onboarding()


def cmd_context(args, *, quiet=False):
    """Output the cold-start prompt. No API call; reads local files."""
    from .config_manager import ConfigManager
    from .context_generator import ContextGenerator

    project_path = getattr(args, "path", ".") or "."
    project_path = str(Path(project_path).resolve())
    copy_flag = getattr(args, "copy", False)
    fmt = getattr(args, "format", "markdown") or "markdown"

    cm = ConfigManager(project_path)
    if not cm.is_initialized():
        if not quiet:
            ui.print_error("No .deeprepo/ directory found.")
            ui.print_msg(f"Run 'deeprepo init {project_path}' first.")
            sys.exit(1)
        return {
            "status": "error",
            "message": "No .deeprepo/ directory found",
            "data": {},
        }

    config = cm.load_config()
    generator = ContextGenerator(project_path, config)

    try:
        content = generator.update_cold_start()
    except FileNotFoundError as exc:
        if not quiet:
            ui.print_error(str(exc))
            ui.print_msg("Run 'deeprepo init' to generate project context.")
            sys.exit(1)
        return {"status": "error", "message": str(exc), "data": {}}

    if fmt == "cursor":
        out_path = Path(project_path) / ".cursorrules"
        out_path.write_text(content, encoding="utf-8")
        if not quiet:
            ui.print_msg(f"Wrote .cursorrules to {out_path}")
        return {
            "status": "success",
            "message": f"Wrote .cursorrules to {out_path}",
            "data": {"format": "cursor", "path": str(out_path)},
        }

    if copy_flag:
        try:
            _copy_to_clipboard(content)
            token_est = len(content) // 4
            if not quiet:
                ui.print_context_copied(token_est)
            return {
                "status": "success",
                "message": f"Copied cold-start prompt to clipboard ({token_est} tokens)",
                "data": {
                    "format": "markdown",
                    "token_count": token_est,
                    "copied": True,
                    "content": content,
                },
            }
        except Exception:
            token_est = len(content) // 4
            if not quiet:
                ui.print_msg("Could not copy to clipboard. Printing to stdout instead:")
                ui.print_msg()
                ui.print_msg(content)
            return {
                "status": "success",
                "message": "Clipboard unavailable, content returned in data",
                "data": {
                    "format": "markdown",
                    "token_count": token_est,
                    "copied": False,
                    "content": content,
                },
            }

    if not quiet:
        ui.print_msg(content)
    token_est = len(content) // 4
    return {
        "status": "success",
        "message": "Context output",
        "data": {
            "format": "markdown",
            "token_count": token_est,
            "content": content,
        },
    }


def cmd_log(args, *, quiet=False):
    """Record a session entry or show recent entries."""
    from .config_manager import ConfigManager
    from .context_generator import ContextGenerator

    project_path = getattr(args, "path", ".") or "."
    project_path = str(Path(project_path).resolve())

    cm = ConfigManager(project_path)
    if not cm.is_initialized():
        if not quiet:
            ui.print_error("No .deeprepo/ directory found.")
            ui.print_msg(f"Run 'deeprepo init {project_path}' first.")
            sys.exit(1)
        return {
            "status": "error",
            "message": "No .deeprepo/ directory found",
            "data": {},
        }

    action = getattr(args, "action", None)
    message = getattr(args, "message", None)

    if action == "show":
        count = getattr(args, "count", 5) or 5
        entries = show_log_entries(cm.deeprepo_dir, count)
        if not entries:
            if not quiet:
                ui.print_msg("No session log entries yet.")
                ui.print_msg('Add one: deeprepo log "what you did"')
            return {
                "status": "info",
                "message": "No session log entries yet",
                "data": {"entries": []},
            }
        if not quiet:
            for entry in entries:
                ui.print_msg(f"  {entry['timestamp']}  {entry['message']}")
        return {
            "status": "success",
            "message": f"{len(entries)} log entries",
            "data": {"entries": entries},
        }

    log_message = action or message
    if not log_message:
        if not quiet:
            ui.print_error("No message provided.")
            ui.print_msg('Usage: deeprepo log "description of what you did"')
            sys.exit(1)
        return {
            "status": "error",
            "message": "No message provided",
            "data": {},
        }

    append_log_entry(cm.deeprepo_dir, log_message)

    config = cm.load_config()
    generator = ContextGenerator(project_path, config)
    try:
        generator.update_cold_start()
    except FileNotFoundError:
        pass

    if not quiet:
        ui.print_msg(f'Logged: "{log_message}"')
    return {
        "status": "success",
        "message": f'Logged: "{log_message}"',
        "data": {"entry": log_message},
    }


def append_log_entry(deeprepo_dir: Path, message: str) -> None:
    """Append a timestamped entry to SESSION_LOG.md."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n---\n## {timestamp}\n\n{message}\n"

    log_path = deeprepo_dir / "SESSION_LOG.md"
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(entry)


def show_log_entries(deeprepo_dir: Path, count: int = 5) -> list[dict]:
    """Parse SESSION_LOG.md and return the most recent entries."""
    log_path = deeprepo_dir / "SESSION_LOG.md"
    if not log_path.is_file():
        return []

    text = log_path.read_text(encoding="utf-8")
    entries: list[dict[str, str]] = []
    pattern = (
        r"^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\n"
        r"(.*?)(?=^---\s*$|^##\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s*$|\Z)"
    )
    for match in re.finditer(pattern, text, re.MULTILINE | re.DOTALL):
        timestamp = match.group(1).strip()
        message = match.group(2).strip()
        if timestamp and message:
            entries.append({"timestamp": timestamp, "message": message})

    count = max(int(count), 0)
    if count == 0:
        return []
    return entries[-count:] if len(entries) > count else entries


def cmd_status(args, *, quiet=False):
    """Show context health at a glance."""
    from .config_manager import ConfigManager

    project_path = getattr(args, "path", ".") or "."
    project_path = str(Path(project_path).resolve())

    cm = ConfigManager(project_path)
    if not cm.is_initialized():
        if not quiet:
            ui.print_error("No .deeprepo/ directory found.")
            ui.print_msg(f"Run 'deeprepo init {project_path}' first.")
            sys.exit(1)
        return {
            "status": "error",
            "message": "No .deeprepo/ directory found",
            "data": {"initialized": False},
        }

    config = cm.load_config()
    state = cm.load_state()

    project_name = config.project_name or cm.detect_project_name()
    if not quiet:
        ui.print_status_header(project_name)
        ui.print_msg()

    project_md = cm.deeprepo_dir / "PROJECT.md"
    project_md_exists = project_md.is_file()
    project_md_age_hours = 0.0
    project_md_stale = False
    if project_md.is_file():
        mtime = project_md.stat().st_mtime
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        project_md_age_hours = age_hours
        project_md_stale = age_hours >= config.stale_threshold_hours
        age_str = _format_age(age_hours)
        if not quiet:
            if age_hours < config.stale_threshold_hours:
                ui.print_status_line(
                    "PROJECT.md    ", "[OK]", f"current   (refreshed {age_str} ago)"
                )
            else:
                ui.print_status_line(
                    "PROJECT.md    ", "[!!]", f"stale     (refreshed {age_str} ago)"
                )
    else:
        if not quiet:
            ui.print_status_line("PROJECT.md    ", "[X]", "missing    (run deeprepo init)")

    cold_start = cm.deeprepo_dir / "COLD_START.md"
    cold_start_exists = cold_start.is_file()
    if cold_start.is_file():
        if not quiet:
            ui.print_status_line("COLD_START.md ", "[OK]", "current   (synced)")
    else:
        if not quiet:
            ui.print_status_line("COLD_START.md ", "[X]", "missing")

    session_log_path = cm.deeprepo_dir / "SESSION_LOG.md"
    entries = show_log_entries(cm.deeprepo_dir, count=999999)
    entry_count = len(entries)
    last_ts = None
    if entry_count > 0:
        last_ts = entries[-1]["timestamp"]
        suffix = "s" if entry_count != 1 else ""
        if not quiet:
            ui.print_status_line(
                "SESSION_LOG.md",
                "[OK]",
                f"{entry_count} session{suffix}  (last: {last_ts})",
            )
    else:
        if not quiet:
            ui.print_status_line("SESSION_LOG.md", "[~]", "empty")

    scratchpad = cm.deeprepo_dir / "SCRATCHPAD.md"
    scratchpad_exists = scratchpad.is_file()
    scratchpad_active = False
    if scratchpad.is_file():
        scratchpad_text = scratchpad.read_text(encoding="utf-8")
        if (
            "**Current Task:** None" in scratchpad_text
            or "**Phase:** IDLE" in scratchpad_text
        ):
            if not quiet:
                ui.print_status_line(
                    "SCRATCHPAD.md ", "[OK]", "clean     (no active tasks)"
                )
        else:
            scratchpad_active = True
            if not quiet:
                ui.print_status_line(
                    "SCRATCHPAD.md ", "[!!]", "active    (has current task)"
                )
    else:
        if not quiet:
            ui.print_status_line("SCRATCHPAD.md ", "[~]", "missing")

    changes_data = None
    if state.file_hashes:
        changes = get_changed_files(Path(project_path), state)
        changes_data = {
            "modified": len(changes["modified"]),
            "added": len(changes["added"]),
            "deleted": len(changes["deleted"]),
        }
        total_changes = (
            len(changes["modified"]) + len(changes["added"]) + len(changes["deleted"])
        )
        if not quiet:
            if total_changes > 0:
                ui.print_msg()
                ui.print_msg("  Changed since last refresh:")
                for filepath in changes["modified"][:10]:
                    ui.print_msg(f"    modified: {filepath}")
                for filepath in changes["added"][:10]:
                    ui.print_msg(f"    added:    {filepath}")
                for filepath in changes["deleted"][:10]:
                    ui.print_msg(f"    deleted:  {filepath}")
                if total_changes > 30:
                    ui.print_msg(f"    ... and {total_changes - 30} more")
                ui.print_msg()
                ui.print_msg("  Run `deeprepo refresh` to update context.")
            else:
                ui.print_msg()
                ui.print_msg("  No files changed since last refresh.")

    return {
        "status": "success",
        "message": f"Project: {project_name}",
        "data": {
            "project_name": project_name,
            "initialized": True,
            "project_md": {
                "exists": project_md_exists,
                "age_hours": project_md_age_hours,
                "stale": project_md_stale,
            },
            "cold_start": {"exists": cold_start_exists},
            "session_log": {
                "exists": session_log_path.is_file(),
                "entry_count": entry_count,
                "last_timestamp": last_ts,
            },
            "scratchpad": {
                "exists": scratchpad_exists,
                "active": scratchpad_active,
            },
            "changes": changes_data,
        },
    }


def cmd_refresh(args, *, quiet=None):
    """Diff-aware or full refresh of project context."""
    from .config_manager import ConfigManager
    from .refresh import RefreshEngine

    project_path = getattr(args, "path", ".") or "."
    project_path = str(Path(project_path).resolve())
    full = getattr(args, "full", False)
    quiet = quiet if quiet is not None else getattr(args, "quiet", False)

    cm = ConfigManager(project_path)
    if not cm.is_initialized():
        if not quiet:
            ui.print_error("No .deeprepo/ directory found.")
            ui.print_msg(f"Run 'deeprepo init {project_path}' first.")
            sys.exit(1)
        return {
            "status": "error",
            "message": "No .deeprepo/ directory found",
            "data": {},
        }

    config = cm.load_config()
    state = cm.load_state()

    # Map model short names
    config.root_model = ROOT_MODEL_MAP.get(config.root_model, config.root_model)

    engine = RefreshEngine(project_path, config, state)

    if not full:
        changes = engine.get_changes()
        changed_count = (
            len(changes["modified"]) + len(changes["added"]) + len(changes["deleted"])
        )
        if changed_count == 0:
            if not quiet:
                ui.print_msg("Already up to date.")
            return {
                "status": "info",
                "message": "Already up to date",
                "data": {"changed_files": 0},
            }

        if not quiet:
            ui.print_msg(f"Found {changed_count} changed file(s):")
            for filepath in changes["modified"][:5]:
                ui.print_msg(f"  modified: {filepath}")
            for filepath in changes["added"][:5]:
                ui.print_msg(f"  added:    {filepath}")
            for filepath in changes["deleted"][:5]:
                ui.print_msg(f"  deleted:  {filepath}")
            ui.print_msg()

    if not quiet:
        mode = "full" if full else "diff-aware"
        ui.print_msg(f"Running {mode} refresh...")
        ui.print_msg()

    result = engine.refresh(full=full)
    cm.save_state(state)

    if not quiet:
        ui.print_refresh_complete(result["changed_files"], result["cost"], result["turns"])

    return {
        "status": "success",
        "message": f"Refreshed {result['changed_files']} files",
        "data": {
            "changed_files": result["changed_files"],
            "cost": result["cost"],
            "turns": result["turns"],
        },
    }


def _parse_stack_string(stack_str: str) -> dict:
    """Parse 'python-fastapi' into {'language': 'python', 'framework': 'fastapi'}."""
    parts = stack_str.lower().replace("/", "-").split("-", 1)
    result = {"language": parts[0]}
    if len(parts) > 1:
        result["framework"] = parts[1]
    return result


def get_changed_files(project_path: Path, state: ProjectState) -> dict:
    """Compare current file hashes against .state.json."""
    current_hashes = compute_file_hashes(project_path)
    old_hashes = state.file_hashes or {}

    modified: list[str] = []
    added: list[str] = []
    deleted: list[str] = []

    for path, hash_value in current_hashes.items():
        if path not in old_hashes:
            added.append(path)
        elif old_hashes[path] != hash_value:
            modified.append(path)

    for path in old_hashes:
        if path not in current_hashes:
            deleted.append(path)

    return {
        "modified": sorted(modified),
        "added": sorted(added),
        "deleted": sorted(deleted),
    }


def compute_file_hashes(project_path: Path) -> dict[str, str]:
    """SHA-256 hash files using codebase_loader-compatible include rules."""
    from .codebase_loader import ALL_EXTENSIONS, EXTENSIONLESS_FILES, SKIP_DIRS

    skip_dirs = set(SKIP_DIRS) | {".deeprepo"}
    hashes: dict[str, str] = {}

    for dirpath, dirnames, filenames in os.walk(project_path):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in skip_dirs]
        base_path = Path(dirpath)

        for filename in filenames:
            file_path = base_path / filename
            extension = file_path.suffix.lower()
            if extension not in ALL_EXTENSIONS and filename not in EXTENSIONLESS_FILES:
                continue

            try:
                digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            except (OSError, PermissionError):
                continue

            relative = str(file_path.relative_to(project_path))
            hashes[relative] = digest

    return hashes


def _format_age(hours: float) -> str:
    """Format age in hours into a short string."""
    if hours < 1:
        return f"{max(int(hours * 60), 0)}m"
    if hours < 24:
        return f"{int(hours)}h"
    return f"{int(hours / 24)}d"


def _copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard."""
    if sys.platform == "darwin":
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(text.encode("utf-8"))
        if proc.returncode == 0:
            return

    try:
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(text.encode("utf-8"))
        if proc.returncode == 0:
            return
    except FileNotFoundError:
        pass

    try:
        proc = subprocess.Popen(
            ["xsel", "--clipboard", "--input"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(text.encode("utf-8"))
        if proc.returncode == 0:
            return
    except FileNotFoundError:
        pass

    raise RuntimeError("No clipboard tool available")
