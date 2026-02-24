# Engineer Task: Task B — TUI UX Fixes + Test Cleanup

## Context

deeprepo v0.2.1's TUI has four UX bugs and two test issues. The onboarding flow only checks for one of two required API keys. The `/init` and `/refresh` commands show no loading indicator during multi-minute analysis. The ASCII banner leaks Rich markup tags. Error messages reference `.env file` which makes no sense for TUI users. Two pre-existing test failures use the wrong assertion method.

This task fixes 5 issues across 4 source files + 2 test files, and adds 4 new tests.

---

## Files to Modify

- `deeprepo/tui/onboarding.py` — H4: dual API key onboarding
- `deeprepo/tui/command_router.py` — H5: loading spinner, M2: error message rewriting
- `deeprepo/tui/shell.py` — M1: Rich markup leak fix
- `tests/test_onboarding.py` — T5: new test for Anthropic key check
- `tests/test_command_router.py` — T6: new test for error message rewriting
- `tests/test_tui_polish.py` — T7: new test for banner markup
- `tests/test_async_batch.py` — T9: fix pre-existing test failures

---

## Bug Descriptions and Fixes

### Fix 1: H4 — Onboarding only checks OpenRouter key, not Anthropic key

**The bug:** `needs_onboarding()` and `run_onboarding()` in `onboarding.py` only check and prompt for `OPENROUTER_API_KEY`. The root model requires `ANTHROPIC_API_KEY` (set up in `llm_clients.py`). If a user has OpenRouter configured but not Anthropic, onboarding says everything is fine, but `/init` immediately fails.

**Current `needs_onboarding` (lines 50-74):**
```python
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
```

**Current `load_global_api_key` (lines 15-33):**
```python
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
```

**Current `save_global_api_key` (lines 36-47):**
```python
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
```

**Current `run_onboarding` (lines 77-132):**
```python
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
        _console.print("[cyan]deeprepo uses OpenRouter for AI model access.[/cyan]")
        _console.print("[dim]Get your key at: https://openrouter.ai/keys[/dim]")
        api_key = input_fn("Enter your OpenRouter API key (or press Enter to skip): ").strip()
        if api_key:
            save_global_api_key(api_key)
            _console.print(
                f"[green]API key saved to ~/.deeprepo/config.yaml ({api_key[:8]}...).[/green]"
            )
            result["api_key_configured"] = True
        else:
            _console.print(
                "[yellow]Skipped. Commands needing API access won't work until a key is set.[/yellow]"
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
```

**Fix approach:**

1. **`load_global_api_key`** — Rename to `load_global_api_keys` (plural). Return a dict instead of a single string:
```python
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
```

Also keep the old name as an alias so existing callers don't break:
```python
def load_global_api_key() -> str | None:
    """Legacy wrapper — returns OpenRouter key only."""
    return load_global_api_keys()["api_key"]
```

2. **`save_global_api_key`** — Replace with `save_global_api_keys` that saves both keys. Keep old name as alias:
```python
def save_global_api_keys(
    openrouter_key: str | None = None,
    anthropic_key: str | None = None,
) -> None:
    """Save API key(s) to ~/.deeprepo/config.yaml and set in os.environ."""
    # Load existing config to preserve any key we're not updating
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
```

3. **`needs_onboarding`** — Check both keys. Return separate flags:
```python
def needs_onboarding(project_path: str) -> dict:
    """Check what onboarding steps are needed.

    Returns:
        {
            "needs_api_key": bool,        # No OPENROUTER_API_KEY (kept for backward compat)
            "needs_anthropic_key": bool,   # No ANTHROPIC_API_KEY
            "needs_init": bool,            # No .deeprepo/ in project directory
        }
    """
    # Check OpenRouter key
    env_or_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    needs_openrouter = not bool(env_or_key)

    # Check Anthropic key
    env_ant_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    needs_anthropic = not bool(env_ant_key)

    # Try loading from global config if env vars are missing
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
```

4. **`run_onboarding`** — Prompt for both keys separately:
```python
def run_onboarding(project_path: str, *, input_fn=None) -> dict:
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

    # Prompt for Anthropic key (root model — the orchestrator)
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
            _console.print(
                "[yellow]Skipped. /init requires an Anthropic API key.[/yellow]"
            )
            result["anthropic_key_configured"] = False

    # Prompt for OpenRouter key (sub-model workers)
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
```

5. **Shell integration** — In `shell.py` line 42, update the check to include the new key:
```python
# Current:
check = needs_onboarding(self.project_path)
if check["needs_api_key"] or check["needs_init"]:
    run_onboarding(self.project_path)

# New:
check = needs_onboarding(self.project_path)
if check["needs_api_key"] or check.get("needs_anthropic_key", False) or check["needs_init"]:
    run_onboarding(self.project_path)
```

---

### Fix 2: H5 — No loading indicator during `/init` and `/refresh`

**The bug:** `_do_init` and `_do_refresh` in `command_router.py` call `cmd_init` and `cmd_refresh` synchronously with no spinner. Analysis takes 2-5 minutes during which the TUI appears frozen.

**Current `_do_init` (lines 86-105):**
```python
    def _do_init(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_init

        deeprepo_dir = Path(self.project_path) / ".deeprepo"
        project_md = deeprepo_dir / "PROJECT.md"

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
        return cmd_init(args, quiet=True)
```

**Current `_do_refresh` (lines 166-175):**
```python
    def _do_refresh(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_refresh

        full = "--full" in tokens
        args = argparse.Namespace(
            path=self.project_path,
            full=full,
            quiet=True,
        )
        return cmd_refresh(args, quiet=True)
```

**Fix:** Add `from rich.console import Console` at the top of `command_router.py`. Create a module-level `_console = Console()`. Wrap the `cmd_init` and `cmd_refresh` calls in `_console.status()`:

```python
from rich.console import Console

_console = Console()
```

For `_do_init`:
```python
    def _do_init(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_init

        deeprepo_dir = Path(self.project_path) / ".deeprepo"
        project_md = deeprepo_dir / "PROJECT.md"

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
        with _console.status("[cyan]Analyzing project...[/cyan]", spinner="dots"):
            return cmd_init(args, quiet=True)
```

For `_do_refresh`:
```python
    def _do_refresh(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_refresh

        full = "--full" in tokens
        args = argparse.Namespace(
            path=self.project_path,
            full=full,
            quiet=True,
        )
        with _console.status("[cyan]Refreshing context...[/cyan]", spinner="dots"):
            return cmd_refresh(args, quiet=True)
```

---

### Fix 3: M1 — Rich markup leak in ASCII banner

**The bug:** In `shell.py` line 188, the ASCII art line ends with a backslash that immediately precedes the `[/bold magenta]` closing tag. Rich interprets `\[` as an escaped literal `[`, so the closing tag is rendered as literal text instead of being processed.

**Current line 188:**
```python
"[bold magenta] / _` |/ _ \\/ _ \\ '_ \\| '__/ _ \\ '_ \\ / _ \\[/bold magenta]",
```

In the resolved Python string, this becomes:
```
[bold magenta] / _` |/ _ \/ _ \ '_ \| '__/ _ \ '_ \ / _ \[/bold magenta]
```

The `\` before `[/bold magenta]` creates `\[` which Rich treats as an escaped bracket.

**Fix:** Add a space before the closing tag to break the `\[` sequence:
```python
"[bold magenta] / _` |/ _ \\/ _ \\ '_ \\| '__/ _ \\ '_ \\ / _ \\ [/bold magenta]",
```

The trailing space is invisible in the terminal.

---

### Fix 4: M2 — Error messages reference `.env file`

**The bug:** When `/init` fails because API keys aren't set, the error message says "Add it to your .env file or export it as an environment variable." This comes from `llm_clients.py` and is caught by the generic `except Exception` in `command_router.py:43-44`. TUI users don't know what a `.env file` is.

**Fix:** In `_do_init` and `_do_refresh`, catch `EnvironmentError` specifically and rewrite the message:

```python
    def _do_init(self, tokens: list[str]) -> dict:
        from deeprepo.cli_commands import cmd_init

        deeprepo_dir = Path(self.project_path) / ".deeprepo"
        project_md = deeprepo_dir / "PROJECT.md"

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
```

Add a module-level helper:
```python
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
```

Apply the same pattern to `_do_refresh`:
```python
        try:
            with _console.status("[cyan]Refreshing context...[/cyan]", spinner="dots"):
                return cmd_refresh(args, quiet=True)
        except EnvironmentError as exc:
            return _rewrite_env_error(exc)
```

---

### Fix 5: L2 — Fix `test_async_batch.py` await_count assertions

**The bug:** Two tests in `test_async_batch.py` assert `create_mock.await_count == N` but get `0` because `batch()` runs async code via `asyncio.run()` in a separate event loop context, so the mock's `await_count` isn't incremented. The tests should assert on `usage.sub_calls` instead (which IS correctly incremented).

**Current `tests/test_async_batch.py`:**
```python
def test_batch_sync_context_still_works():
    """batch() should keep working from normal synchronous callers."""
    client, usage, create_mock = _build_client()

    results = client.batch(["a", "b", "c"], system="sys", max_tokens=32, max_concurrent=2)

    assert results == ["ok:a", "ok:b", "ok:c"]
    assert create_mock.await_count == 3
    assert usage.sub_calls == 3
    assert usage.sub_input_tokens == 33
    assert usage.sub_output_tokens == 21


def test_batch_inside_existing_event_loop():
    """batch() should not raise when called from a running event loop."""
    client, usage, create_mock = _build_client()

    async def _run_inside_loop():
        return client.batch(["x", "y"], system="sys", max_tokens=32, max_concurrent=2)

    results = asyncio.run(_run_inside_loop())

    assert results == ["ok:x", "ok:y"]
    assert create_mock.await_count == 2
    assert usage.sub_calls == 2
    assert usage.sub_input_tokens == 22
    assert usage.sub_output_tokens == 14
```

**Fix:** Remove the `assert create_mock.await_count == N` lines from both tests. The `usage.sub_calls` assertion already verifies the calls were made correctly:

In `test_batch_sync_context_still_works`, delete line:
```python
    assert create_mock.await_count == 3
```

In `test_batch_inside_existing_event_loop`, delete line:
```python
    assert create_mock.await_count == 2
```

---

## Tests to Add

### T5: `tests/test_onboarding.py` — Anthropic key check

Add this test to the existing file:

```python
def test_needs_onboarding_missing_anthropic_key(tmp_path, monkeypatch):
    """H4: needs_onboarding should detect missing ANTHROPIC_API_KEY."""
    onboarding_mod, _, _ = _patch_global_config(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-ready")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    deeprepo_dir = tmp_path / ".deeprepo"
    deeprepo_dir.mkdir(parents=True)
    (deeprepo_dir / "config.yaml").write_text("project_name: demo\n", encoding="utf-8")

    result = onboarding_mod.needs_onboarding(str(tmp_path))

    assert result["needs_api_key"] is False  # OpenRouter is fine
    assert result["needs_anthropic_key"] is True  # Anthropic is missing
    assert result["needs_init"] is False
```

### T6: `tests/test_command_router.py` — Error message rewriting

Add this test to the existing file:

```python
def test_route_init_rewrites_env_error(monkeypatch, tmp_path):
    """M2: /init with missing ANTHROPIC_API_KEY shows user-friendly error."""
    def fake_cmd_init(args, *, quiet=False):
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file or export it."
        )

    import deeprepo.cli_commands as cli_commands
    monkeypatch.setattr(cli_commands, "cmd_init", fake_cmd_init)

    router = CommandRouter(str(tmp_path))
    result = router.route("/init")

    assert result["status"] == "error"
    assert "export ANTHROPIC_API_KEY" in result["message"]
    assert ".env" not in result["message"]
```

### T7: `tests/test_tui_polish.py` — Banner markup doesn't leak

Add this test to the existing file:

```python
def test_banner_no_markup_leak(tmp_path):
    """M1: Banner should not show literal Rich markup tags like [/bold magenta]."""
    from io import StringIO
    from rich.console import Console
    from deeprepo.tui.shell import DeepRepoShell

    shell = DeepRepoShell(str(tmp_path))

    # Render the banner through Rich Console to a StringIO to capture actual output
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=True, width=120)

    # Re-render the ASCII lines through a test console
    ascii_lines = [
        "[bold bright_cyan]     _                                [/bold bright_cyan]",
        "[bold cyan]  __| | ___  ___ _ __  _ __ ___ _ __   ___[/bold cyan]",
        "[bold magenta] / _` |/ _ \\/ _ \\ '_ \\| '__/ _ \\ '_ \\ / _ \\ [/bold magenta]",
        "[bold bright_magenta]| (_| |  __/  __/ |_) | | |  __/ |_) | (_) |[/bold bright_magenta]",
        "[bold purple] \\__,_|\\___|\\___|  __/|_|  \\___|  __/ \\___/[/bold purple]",
        "[bold bright_cyan]               |_|            |_|[/bold bright_cyan]",
    ]
    for line in ascii_lines:
        test_console.print(line)

    output = buf.getvalue()
    assert "[/bold" not in output, f"Markup leak detected in banner output: {output}"
    assert "[/cyan" not in output, f"Markup leak detected in banner output: {output}"
    assert "[/magenta" not in output, f"Markup leak detected in banner output: {output}"
```

**IMPORTANT for T7:** The test must use the FIXED version of the banner line (with the trailing space before `[/bold magenta]`). The test verifies that after the fix, no literal markup tags appear in the rendered output. If you're running the test before applying Fix 3, it will fail (as expected).

---

## Acceptance Criteria

- [ ] `python -m pytest tests/test_onboarding.py -v` — all existing + 1 new test pass (T5)
- [ ] `python -m pytest tests/test_command_router.py -v` — all existing + 1 new test pass (T6)
- [ ] `python -m pytest tests/test_tui_polish.py -v` — all existing + 1 new test pass (T7)
- [ ] `python -m pytest tests/test_async_batch.py -v` — both previously-failing tests now pass (T9)
- [ ] `python -m pytest tests/ -v` — ALL tests pass (0 failures), excluding network-dependent tests (test_baseline.py, test_connectivity.py, test_rlm_integration.py)
- [ ] `needs_onboarding()` returns `needs_anthropic_key: True` when `ANTHROPIC_API_KEY` is not set
- [ ] `run_onboarding()` prompts for both Anthropic and OpenRouter keys when both are missing
- [ ] `/init` and `/refresh` show a spinner during execution
- [ ] `/init` with missing `ANTHROPIC_API_KEY` shows "Run: export ANTHROPIC_API_KEY=sk-ant-..." not ".env file"
- [ ] Banner renders without any literal `[/bold magenta]` or similar markup tags

## Anti-Patterns (Do NOT)

- Do NOT modify `deeprepo/rlm_scaffold.py` — that was Task A.
- Do NOT modify `deeprepo/llm_clients.py` — the error messages there are fine for CLI users; we only rewrite them in the command router for TUI.
- Do NOT break backward compatibility on `load_global_api_key` or `save_global_api_key` — keep them as aliases/wrappers for the new functions.
- Do NOT make onboarding auto-run `/init` — just tell the user to run it.
- Do NOT add new dependencies to `pyproject.toml` — Rich is already a dependency.
- Do NOT change the visual design of the banner — only fix the markup escape bug.
- Do NOT modify any existing test assertions except removing the two `await_count` lines in `test_async_batch.py`.

## Test Commands

```bash
# Run just the modified test files
python -m pytest tests/test_onboarding.py tests/test_command_router.py tests/test_tui_polish.py tests/test_async_batch.py -v

# Run full suite (excluding network tests)
python -m pytest tests/ -v --ignore=tests/test_baseline.py --ignore=tests/test_connectivity.py --ignore=tests/test_rlm_integration.py

# Smoke test specific new tests
python -m pytest tests/test_onboarding.py::test_needs_onboarding_missing_anthropic_key -v
python -m pytest tests/test_command_router.py::test_route_init_rewrites_env_error -v
python -m pytest tests/test_tui_polish.py::test_banner_no_markup_leak -v
python -m pytest tests/test_async_batch.py -v
```

## When Done

Update `SCRATCHPAD_ENGINEER.md` with:
- What you implemented (files changed, approach taken)
- Any deviations from the spec and why
- Any issues or questions encountered
- Test results (paste `pytest` output)
