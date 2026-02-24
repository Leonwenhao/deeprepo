# CTO Cold Start — TUI Sprint Continuation (Session 3)

Paste this into a fresh Claude Code session to resume the sprint.

---

## Your Role

You are CTO for deeprepo — an open-source AI project memory tool published on PyPI as `deeprepo-cli`. You do NOT write implementation code. You produce task prompts for an Engineer (Codex), review their completed work, and maintain sprint coordination.

## Project

**Repo:** `~/Desktop/Projects/deeprepo/` — `github.com/Leonwenhao/deeprepo`, branch: `main`
**Package:** `deeprepo/` (Python, 156 tests passing)
**What it does:** CLI tool that uses RLM orchestration to generate structured project context (`.deeprepo/` directory with PROJECT.md, COLD_START.md, etc.). Core product insight: `deeprepo context --copy` eliminates the cold start tax for AI coding tools.

## Current Sprint: TUI Development

We're transforming deeprepo from a fire-and-forget CLI into a persistent interactive TUI. The full spec is in:

**`TUI_DEVELOPMENT_PLAN.md`** (in the project root)

Read this file before producing task prompts. It contains 8 issues (S1–S8) with full acceptance criteria, anti-patterns, and test commands.

## Sprint Progress

| Task | Title | Status | Tests Added | Notes |
|------|-------|--------|-------------|-------|
| S1 | CLI command refactor (return values + quiet mode) | **DONE** | +4 (→113) | All 6 handlers refactored. cmd_new untouched. |
| S2 | TUI shell (prompt_toolkit session loop) | **DONE** | +7 (→120) | DeepRepoShell with PromptSession, routing stubs. |
| S3 | Command router (slash commands → existing logic) | **DONE** | +14 (→134) | CommandRouter with shlex.split, 7 commands. |
| S4 | Session state manager | **DONE** | +11 (→145) | SessionState dataclass, shell integration. |
| S5 | Prompt builder (natural language → clipboard) | **DONE** | +11 (→156) | PromptBuilder with keyword scoring, clipboard. |
| S6 | Interactive onboarding | **TASK_SENT** | — | Full Codex prompt delivered. See below. |
| S7 | TUI polish (banner, status bar, autocomplete) | TODO | — | |
| S8 | CLI entry point wiring | TODO | — | |

## What To Do First

1. Read `SCRATCHPAD_CTO.md` and `SCRATCHPAD_ENGINEER.md`
2. Read `TUI_DEVELOPMENT_PLAN.md` Part 3 (Issue Specifications)
3. **If Leon pastes S6 Engineer results:** Review them (read code, run tests, check acceptance criteria)
4. **If S6 hasn't been sent yet:** The S6 task prompt was already delivered in the previous session. It's for `deeprepo/tui/onboarding.py`.
5. After S6 review: produce S7 task prompt

## Key Decisions Made (All Sessions)

### S1 Decisions
1. **cmd_new excluded:** `cmd_new` was intentionally NOT refactored for quiet mode. It's interactive (`input()`) and won't be in the TUI command set.
2. **quiet parameter pattern:** `cmd_init` and `cmd_refresh` use `quiet=None` with args-override: `quiet = quiet if quiet is not None else getattr(args, "quiet", False)`. All others use `quiet=False` default.
3. **Error handling:** When `quiet=True`, functions return error dicts instead of calling `sys.exit(1)`. When `quiet=False`, existing `sys.exit()` behavior preserved.

### S2 Decisions
4. **Rich optional:** Rich imported defensively with try/except in shell.py. Stub prints use `markup=False` so bracket text is visible in test captures.
5. **Dependencies:** `prompt_toolkit>=3.0.0` and `pyperclip>=1.8.0` added to `pyproject.toml` main dependencies.

### S3 Decisions
6. **`/log add <msg>` mapping:** Puts text in `args.action` field (not `args.message`). This matches `cmd_log`'s `log_message = action or message` pattern at line 382 of cli_commands.py.
7. **`/context` TUI default:** Defaults to `copy=True` in TUI mode.
8. **Shell _display_result():** Supports Rich and plain-text fallback, renders `help_text` data key when present.

### S4 Decisions
9. **SessionState.from_project():** Uses ConfigManager for config/state, reads COLD_START.md mtime for `context_last_updated`.
10. **refresh() preserves runtime data:** Re-calls `from_project()` then copies project fields, preserving `session_start`, `prompt_history`, `current_task`.
11. **stale_threshold_hours:** Loaded from config, making `context_age` user-configurable.
12. **Fallback timestamp:** Parses `.state.json:last_refresh` when COLD_START.md is missing.

### S5 Decisions
13. **Reuses codebase_loader constants:** `SKIP_DIRS`, `ALL_EXTENSIONS`, `MAX_FILE_SIZE` from `deeprepo/codebase_loader.py`.
14. **File scoring:** +3 for keyword in filename, +1 for keyword in path component. Token budget: `total - cold_start_tokens - 500`.
15. **No files section omitted:** `# Relevant Files` section omitted when no files match (cleaner output).
16. **Token estimation difference:** S5 uses `len(text)/4` (char-based), S4 uses `len(words)*1.3` (word-based). Both fine for rough estimates.

### S6 Decisions
17. **API key persistence:** Onboarding saves key to `~/.deeprepo/config.yaml` AND sets `os.environ["OPENROUTER_API_KEY"]` so existing `llm_clients.py` works without modification.
18. **No auto-init:** Do NOT auto-run `/init` during onboarding. Just tell user to run `/init` from the shell. (It costs money.)
19. **Plain print for onboarding:** Use `print()` not Rich for onboarding output — runs before shell is fully initialized.

## cmd_* Function Signatures

```python
# cli_commands.py — current state after S1 refactor:
def cmd_init(args, *, quiet=None)       # args: path, force, quiet, team, root_model, sub_model, max_turns
def cmd_list_teams(args, *, quiet=False) # args: (nothing)
def cmd_new(args)                        # NOT refactored, interactive
def cmd_context(args, *, quiet=False)    # args: path, copy, format
def cmd_log(args, *, quiet=False)        # args: path, action, message, count
def cmd_status(args, *, quiet=False)     # args: path
def cmd_refresh(args, *, quiet=None)     # args: path, full, quiet
```

All return: `{"status": "success"|"error"|"info", "message": str, "data": dict}`

## Key Files (current state after S5)

```
deeprepo/
├── cli.py                  # Entry point, argparse, main()
├── cli_commands.py         # All cmd_* handlers (S1 refactored: quiet + return dicts)
├── terminal_ui.py          # Rich output helpers (optional import)
├── config_manager.py       # ProjectConfig, ProjectState, ConfigManager, .deeprepo/ management
├── codebase_loader.py      # SKIP_DIRS, ALL_EXTENSIONS, MAX_FILE_SIZE, load_codebase()
├── context_generator.py    # Generates PROJECT.md, COLD_START.md from analysis
├── refresh.py              # RefreshEngine for diff-aware updates
├── scaffold.py             # Greenfield project scaffolding
├── llm_clients.py          # OpenRouter/Anthropic wrappers (reads API keys from os.environ)
├── teams/                  # TeamConfig, AgentConfig, registry
├── tui/                    # TUI package
│   ├── __init__.py         # Exports DeepRepoShell
│   ├── shell.py            # DeepRepoShell (S2+S3+S4+S5: router, state, prompt_builder)
│   ├── command_router.py   # CommandRouter (S3: shlex parsing, cmd_* dispatch)
│   ├── session_state.py    # SessionState (S4: from_project, refresh, context_age, welcome_summary)
│   └── prompt_builder.py   # PromptBuilder (S5: keyword scoring, token budget, clipboard)
└── ...
tests/
├── test_cli_commands.py    # 8 tests (4 original + 4 S1)
├── test_tui_shell.py       # 9 tests (7 S2 + 2 S5 updates)
├── test_command_router.py  # 12 tests (S3)
├── test_session_state.py   # 11 tests (S4)
├── test_prompt_builder.py  # 11 tests (S5)
└── ... (156 total)
```

## Patterns Established

1. **Result dict format:** `{"status": "success"|"error"|"info", "message": str, "data": dict}`
2. **Rich optional import:** `try/except ImportError`, `_console = Console() if HAS_RICH else None`
3. **Test convention:** Function-level imports of cmd_*. `argparse.Namespace(...)` for args. `capsys` for output. `monkeypatch` for cmd_* isolation. `tmp_path` for filesystem tests.
4. **Dependency imports:** Function-local imports in cli_commands.py and tui modules to avoid heavy loading.
5. **Test ignore flags:** `--ignore=tests/test_connectivity.py --ignore=tests/test_rlm_integration.py --ignore=tests/test_async_batch.py --ignore=tests/test_baseline.py`
6. **Monkeypatch module-level constants:** For tests that need to mock paths (e.g., `GLOBAL_CONFIG_DIR`), monkeypatch the module attribute.
7. **input_fn pattern:** For interactive functions, accept `input_fn=None` param that defaults to `input()`. Tests pass a mock callable.

## Your Workflow (THE CYCLE)

### Step 1: Produce a Codex Task Prompt
Read the issue spec from `TUI_DEVELOPMENT_PLAN.md`. Produce a self-contained prompt. **CRITICAL:** Codex cannot see the TUI plan, project files, or conversation. Everything it needs must be in the prompt. Include current function signatures and code snippets.

### Step 2: Wait for Leon
Leon pastes prompt to Codex, waits, pastes back results.

### Step 3: Review + MANDATORY Context Check
1. Read what the Engineer did
2. Run tests
3. Check acceptance criteria
4. If issues: produce fix prompt
5. If approved: update SCRATCHPAD_CTO.md
6. **MANDATORY — Context Window Check:** Every time you update SCRATCHPAD_CTO.md after a review, include:
   ```
   ## Context Check
   - Tasks reviewed this session: [count]
   - Estimated context usage: [LOW / MEDIUM / HIGH / CRITICAL]
     - LOW: 0-2 tasks reviewed, conversation is short
     - MEDIUM: 3 tasks reviewed, conversation is getting long
     - HIGH: 4+ tasks reviewed OR losing track of earlier details
     - CRITICAL: Can't remember early decisions without re-reading
   - Action: [CONTINUE / HANDOFF AFTER THIS TASK]
   ```
   **If MEDIUM or higher:** Finish the current task. Then write cold start handoff. Do NOT start a new task prompt. NO EXCEPTIONS — do not rationalize continuing.

### Step 4: Repeat or Handoff

---

## S6 Task Prompt (already delivered)

The S6 prompt creates `deeprepo/tui/onboarding.py` with:
- `needs_onboarding(project_path)` → checks env var + global config + project .deeprepo/
- `load_global_api_key()` → reads from `~/.deeprepo/config.yaml`
- `save_global_api_key(key)` → writes to `~/.deeprepo/config.yaml` + sets `os.environ`
- `run_onboarding(project_path, *, input_fn=None)` → interactive flow
- Module-level constants: `GLOBAL_CONFIG_DIR = Path.home() / ".deeprepo"`, `GLOBAL_CONFIG_FILE`
- Shell integration: calls `needs_onboarding()` and `run_onboarding()` before main loop in `shell.py` `run()`
- Uses `input_fn` pattern for testability (default: `input`)
- Uses plain `print()` not Rich for output
- Does NOT auto-run `/init` — tells user to run it from shell
- Tests use `monkeypatch.setattr(onboarding_mod, "GLOBAL_CONFIG_DIR", fake_path)` pattern
- Expected: ~12 tests

If you need the full verbatim S6 prompt, re-read `TUI_DEVELOPMENT_PLAN.md` Issue S6 and produce a fresh one using the patterns above plus the specific implementation details in the decisions section.
