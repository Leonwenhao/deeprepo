# deeprepo — TUI Development Plan: Interactive Command Center

**Author:** Leon (with Claude)
**Date:** February 23, 2026
**Sprint Goal:** Transform deeprepo from fire-and-forget CLI into a persistent interactive TUI session — the "AI development command center" that generates context-rich prompts for external coding tools.
**Agents:** Claude Code (CTO) + Codex (Senior Engineer)

---

## Executive Summary

deeprepo's core product works: `deeprepo init .` generates project context, `deeprepo context --copy` puts it on the clipboard. But the UX is wrong for the product vision. Every command runs and exits. There's no session, no continuity, no sense that deeprepo *knows* your project.

The TUI transforms the experience. Type `deeprepo` in any project directory → drop into a persistent session with project awareness, slash commands for infrastructure, and natural language input that assembles context-rich prompts and copies them to clipboard for use in Claude Code, Codex, or any other tool.

**Critical constraint:** deeprepo is NOT replacing coding agents. It's the context layer above them. The primary output is clipboard-ready prompts, not code. The RLM engine and API calls exist for `/init` and `/refresh`, but the moment-to-moment interaction is prompt assembly → clipboard → paste into external tool.

**Dependencies:** `prompt_toolkit` (input handling, history, autocomplete), `rich` (already in use for terminal_ui.py), `pyperclip` (clipboard — check if already a dep).

---

## Part 1: Current State Assessment

### What Exists (no changes needed)

| Component | File | Status |
|-----------|------|--------|
| CLI command handlers | `cli_commands.py` | All working: init, context, log, status, refresh, new |
| RLM engine | `rlm_scaffold.py` | Working REPL loop with tool_use, streaming, caching |
| API clients | `llm_clients.py` | OpenRouter wrappers with retry, token tracking |
| Rich terminal output | `terminal_ui.py` | Progress bars, panels, styled output |
| Context generation | `context_generator.py` | Splits RLM output into .deeprepo/ files |
| Project config | `config_manager.py` | ProjectConfig, ProjectState, .deeprepo/ management |
| Teams infrastructure | `teams/` | TeamConfig, AgentConfig, registry (plumbing only) |
| Test suite | `tests/` | 109 tests passing |

### What Needs to Change

| Component | Current | Target |
|-----------|---------|--------|
| Entry point | `deeprepo <command> [args]` → run → exit | `deeprepo` → persistent session |
| Command routing | argparse subcommands | Slash commands inside TUI session |
| User input | None (all via CLI args) | Natural language + slash commands |
| Session state | None (stateless) | Tracks current task, recent prompts, file relevance |
| Onboarding | Crash with API key error | Interactive setup wizard |
| Output | Terminal text | Clipboard-first with terminal feedback |

### Key Constraint: Backend Logic Doesn't Change

The TUI is a new frontend for existing backend functions. `cmd_init()`, `cmd_context()`, `cmd_status()`, `cmd_log()`, `cmd_refresh()` already work. The TUI calls them — it doesn't reimplement them. Any refactoring to make them callable from the TUI (e.g., returning data instead of printing directly) is acceptable, but the core logic stays.

---

## Part 2: Architecture

### Component Diagram

```
User types "deeprepo" in terminal
         │
         ▼
┌─────────────────────────────────────────────────────┐
│  TUI Shell (deeprepo/tui/shell.py)                  │
│                                                      │
│  prompt_toolkit session with:                        │
│  - Slash command recognition (/init, /context, etc.) │
│  - Natural language passthrough                      │
│  - History, autocomplete, keybindings                │
│  - Rich-formatted output panel                       │
│                                                      │
│  ┌──────────────┐   ┌──────────────────────┐        │
│  │ Command       │   │ Prompt Generator     │        │
│  │ Router        │   │ (prompt_builder.py)  │        │
│  │               │   │                      │        │
│  │ /init → cmd_  │   │ NL input → assemble  │        │
│  │   init()      │   │ cold_start + files + │        │
│  │ /context →    │   │ ask → clipboard      │        │
│  │   cmd_context │   │                      │        │
│  │ /status →     │   │                      │        │
│  │   cmd_status  │   │                      │        │
│  └──────┬───────┘   └──────────┬───────────┘        │
│         │                      │                     │
│         ▼                      ▼                     │
│  ┌──────────────────────────────────────────┐       │
│  │ Session State (session_state.py)          │       │
│  │                                           │       │
│  │ - project_config (from .deeprepo/)        │       │
│  │ - current_task (what user is working on)  │       │
│  │ - prompt_history (recent generated prompts│       │
│  │ - relevant_files (tracked file set)       │       │
│  └───────────────────────────────────────────┘       │
│                                                      │
│  ┌──────────────────────────────────────────┐       │
│  │ Onboarding (onboarding.py)                │       │
│  │                                           │       │
│  │ - First-run detection (no .deeprepo/)     │       │
│  │ - API key setup                           │       │
│  │ - Interactive init walkthrough             │       │
│  └───────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
         │
         ▼
    Existing backend: cli_commands.py, rlm_scaffold.py,
    llm_clients.py, context_generator.py, config_manager.py
```

### New Package Structure

```
deeprepo/
├── tui/                          # NEW — TUI package
│   ├── __init__.py
│   ├── shell.py                  # Main TUI session loop
│   ├── command_router.py         # Slash command parsing + dispatch
│   ├── prompt_builder.py         # Natural language → clipboard prompt
│   ├── session_state.py          # Session state management
│   ├── onboarding.py             # First-run interactive setup
│   └── completions.py            # Autocomplete definitions
├── cli.py                        # MODIFIED — add `deeprepo` no-args entry
├── cli_commands.py               # MODIFIED — return data, not just print
├── terminal_ui.py                # EXISTING — extended for TUI panels
└── ... (everything else unchanged)
```

---

## Part 3: Issue Specifications

### Issue Priority Order

| Order | Issue | Title | Complexity | Est. Time |
|:-----:|:-----:|-------|:----------:|:---------:|
| 1 | S1 | CLI command refactor — return values + suppressible output | Medium | 3–4 hours |
| 2 | S2 | TUI shell — prompt_toolkit session loop | Medium-High | 4–5 hours |
| 3 | S3 | Command router — slash commands dispatch to existing logic | Medium | 3–4 hours |
| 4 | S4 | Session state manager | Medium | 2–3 hours |
| 5 | S5 | Prompt builder — natural language → clipboard prompt | Medium-High | 4–5 hours |
| 6 | S6 | Interactive onboarding — first-run experience | Medium | 3–4 hours |
| 7 | S7 | TUI polish — welcome banner, status bar, keybindings | Low-Medium | 2–3 hours |
| 8 | S8 | CLI entry point wiring + `deeprepo` no-args behavior | Low | 1–2 hours |

**Total estimated time:** 22–30 hours (3–4 working days with agents)

---

### ISSUE S1 — CLI Command Refactor: Return Values + Suppressible Output

**Problem:** The existing `cmd_*` functions in `cli_commands.py` print directly to stdout via Rich console calls. The TUI needs to call these functions and control how output is displayed (TUI panel vs raw terminal). Functions need to return structured data AND optionally suppress their own printing.

**What to build:**

Refactor each command handler to:
1. Accept an optional `quiet: bool = False` parameter that suppresses direct console output
2. Return a structured result dict instead of (or in addition to) printing
3. Preserve existing behavior when called from argparse CLI (backward compatible)

**Result format convention:**

```python
# Every cmd_* function returns:
{
    "status": "success" | "error" | "info",
    "message": "Human-readable summary",
    "data": { ... }  # Command-specific structured data
}

# Examples:
# cmd_init returns:
{"status": "success", "message": "Initialized .deeprepo/ with 3,008 token context", 
 "data": {"token_count": 3008, "files_analyzed": 23, "cost": 0.63, "turns": 10}}

# cmd_context returns:
{"status": "success", "message": "Copied cold-start prompt to clipboard",
 "data": {"format": "default", "token_count": 3008, "copied": True}}

# cmd_status returns:
{"status": "success", "message": "Project: PokerPot · Context: Fresh · 23 files",
 "data": {"project_name": "PokerPot", "initialized": True, "files_tracked": 23,
          "context_age_seconds": 120, "context_tokens": 3008}}
```

**Files to modify:**
- `deeprepo/cli_commands.py` — add return values and `quiet` param to all `cmd_*` functions
- `deeprepo/cli.py` — ensure argparse handlers still work (they ignore return values)

**Acceptance Criteria:**
- [ ] Every `cmd_*` function returns a result dict with `status`, `message`, and `data` keys
- [ ] Every `cmd_*` function accepts `quiet=False` parameter
- [ ] When `quiet=False` (default), output is identical to current behavior
- [ ] When `quiet=True`, no direct console output — only the return value
- [ ] All 109 existing tests still pass
- [ ] CLI behavior is unchanged: `deeprepo init .`, `deeprepo context --copy`, etc. all work exactly as before

**Anti-Patterns:**
- Do NOT change function signatures in a breaking way. The `quiet` param must be optional with `False` default.
- Do NOT remove existing Rich console output. Wrap it in `if not quiet:` guards.
- Do NOT rewrite the functions. Add return statements and quiet guards, nothing else.
- Do NOT change the cli.py argparse wiring. The functions are called the same way — they just also return data now.

**Test Commands:**
```bash
cd ~/Desktop/Projects/deeprepo
python -m pytest tests/ -v
# Verify return values
python -c "
from deeprepo.cli_commands import cmd_status
result = cmd_status(quiet=True)
print(result)
assert 'status' in result
assert 'data' in result
print('PASS')
"
```

---

### ISSUE S2 — TUI Shell: prompt_toolkit Session Loop

**Problem:** deeprepo currently has no interactive mode. We need a persistent session that accepts user input, displays output, and maintains state across commands.

**What to build:**

A `prompt_toolkit`-based REPL session in `deeprepo/tui/shell.py` that:
1. Displays a welcome banner (project name, context status)
2. Presents a prompt (`> `) that accepts input
3. Routes slash commands to the command router (S3)
4. Routes natural language input to the prompt builder (S5)
5. Handles `exit`, `quit`, Ctrl-D, Ctrl-C gracefully
6. Maintains command history across the session (in-memory for now, file-based later)

**Key design decisions:**

- Use `prompt_toolkit.PromptSession` for the input loop — it handles history, keybindings, multiline, and autocomplete out of the box
- Use Rich for all output rendering — `terminal_ui.py` already uses Rich, extend it
- The shell does NOT handle command execution directly — it delegates to the router (S3) and prompt builder (S5)
- For S2, stub the router and prompt builder with placeholder functions

**Files to create:**
- `deeprepo/tui/__init__.py` — package init
- `deeprepo/tui/shell.py` — `DeepRepoShell` class with `run()` method

**Class: `DeepRepoShell`**

```python
class DeepRepoShell:
    def __init__(self, project_path: str = "."):
        self.project_path = os.path.abspath(project_path)
        self.session = PromptSession(history=InMemoryHistory())
        # self.router = CommandRouter(...)  # S3
        # self.state = SessionState(...)    # S4
        # self.prompt_builder = PromptBuilder(...)  # S5
    
    def run(self):
        """Main loop. Blocks until exit."""
        self._print_welcome()
        while True:
            try:
                user_input = self.session.prompt("> ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    break
                self._handle_input(user_input)
            except (EOFError, KeyboardInterrupt):
                break
        self._print_goodbye()
    
    def _handle_input(self, text: str):
        if text.startswith("/"):
            # Route to command router (S3)
            self._handle_slash_command(text)
        else:
            # Route to prompt builder (S5)
            self._handle_natural_language(text)
    
    def _handle_slash_command(self, text: str):
        # STUB for S2 — will be replaced in S3
        print(f"[slash command: {text}]")
    
    def _handle_natural_language(self, text: str):
        # STUB for S2 — will be replaced in S5
        print(f"[prompt generation: {text}]")
    
    def _print_welcome(self):
        # Rich panel with project info
        ...
    
    def _print_goodbye(self):
        ...
```

**Acceptance Criteria:**
- [ ] `deeprepo/tui/` package exists with `__init__.py` and `shell.py`
- [ ] `DeepRepoShell(".")` creates a shell instance
- [ ] `shell.run()` enters an interactive loop that accepts text input
- [ ] Typing `exit` or `quit` cleanly exits the loop
- [ ] Ctrl-C and Ctrl-D cleanly exit without traceback
- [ ] Slash commands (e.g., `/status`) are detected and routed to `_handle_slash_command()`
- [ ] Non-slash input is detected and routed to `_handle_natural_language()`
- [ ] Welcome banner displays using Rich
- [ ] Up-arrow recalls previous input (prompt_toolkit history)
- [ ] All 109 existing tests still pass

**Anti-Patterns:**
- Do NOT use `input()` — use `prompt_toolkit.PromptSession.prompt()`
- Do NOT implement command execution in the shell. The shell is a thin routing layer.
- Do NOT add async to the shell loop. Keep it synchronous. The command handlers can use async internally.
- Do NOT add autocomplete yet (that's S7). Keep S2 focused on the session loop.

**Dependencies to install:**
```bash
pip install prompt_toolkit pyperclip
# Add to pyproject.toml [project.dependencies]
```

**Test Commands:**
```bash
python -m pytest tests/ -v
# Manual test:
python -c "
from deeprepo.tui.shell import DeepRepoShell
shell = DeepRepoShell('.')
# Don't run shell.run() in automated test — it blocks
print(type(shell))
print('Shell created successfully')
"
```

---

### ISSUE S3 — Command Router: Slash Commands → Existing Logic

**Problem:** The TUI shell needs to parse slash commands (`/init`, `/context --copy`, `/status`, etc.) and dispatch them to the existing `cmd_*` functions in `cli_commands.py`.

**What to build:**

A `CommandRouter` class in `deeprepo/tui/command_router.py` that:
1. Parses slash command strings into command name + arguments
2. Maps command names to existing `cmd_*` handler functions
3. Calls handlers with `quiet=True` (from S1) and returns structured results
4. Handles unknown commands with helpful error messages
5. Supports `/help` to list available commands

**Command mapping:**

| Slash Command | Handler | Notes |
|--------------|---------|-------|
| `/init` | `cmd_init(quiet=True)` | Runs full RLM analysis |
| `/context` | `cmd_context(quiet=True)` | `--copy` is default in TUI |
| `/context --format cursor` | `cmd_context(format="cursor", quiet=True)` | Cursor rules format |
| `/status` | `cmd_status(quiet=True)` | Project status |
| `/log` | `cmd_log(quiet=True)` | Session log |
| `/log add <message>` | `cmd_log(action="add", message=..., quiet=True)` | Add log entry |
| `/refresh` | `cmd_refresh(quiet=True)` | Refresh context |
| `/help` | Built-in | List commands |
| `/team <name>` | Stub (future) | Team switching |

**Argument parsing:** Use `shlex.split()` to tokenize the slash command string, then match against a simple command registry. Do NOT use argparse for TUI commands — it calls `sys.exit()` on errors which would kill the TUI session.

**Files to create:**
- `deeprepo/tui/command_router.py` — `CommandRouter` class

**Files to modify:**
- `deeprepo/tui/shell.py` — replace `_handle_slash_command()` stub with router dispatch

**Class: `CommandRouter`**

```python
class CommandRouter:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self._commands = self._build_command_registry()
    
    def route(self, raw_input: str) -> dict:
        """Parse and execute a slash command. Returns result dict."""
        # Strip leading /
        # shlex.split the rest
        # Look up command name in registry
        # Call handler with parsed args
        # Return result dict
    
    def _build_command_registry(self) -> dict:
        return {
            "init": {"handler": self._do_init, "help": "Analyze project and generate .deeprepo/ context"},
            "context": {"handler": self._do_context, "help": "Copy project context to clipboard"},
            "status": {"handler": self._do_status, "help": "Show project status"},
            "log": {"handler": self._do_log, "help": "View or add to session log"},
            "refresh": {"handler": self._do_refresh, "help": "Refresh project context"},
            "help": {"handler": self._do_help, "help": "Show available commands"},
            "team": {"handler": self._do_team, "help": "Switch team configuration (coming soon)"},
        }
```

**Acceptance Criteria:**
- [ ] `CommandRouter(".")` creates a router instance
- [ ] `router.route("/status")` calls `cmd_status(quiet=True)` and returns result dict
- [ ] `router.route("/context --copy")` calls `cmd_context` with copy flag
- [ ] `router.route("/log add Fixed the WebSocket bug")` calls `cmd_log` with add action
- [ ] `router.route("/help")` returns list of available commands with descriptions
- [ ] `router.route("/nonexistent")` returns error result with helpful message
- [ ] Shell's `_handle_slash_command()` uses the router and displays results via Rich
- [ ] All 109 existing tests still pass

**Anti-Patterns:**
- Do NOT use argparse inside the router. Use manual parsing with `shlex.split()`.
- Do NOT catch and silently swallow exceptions from `cmd_*` functions. Return error results with the exception message.
- Do NOT duplicate command logic. The router ONLY dispatches to existing handlers.
- Do NOT add new commands that don't have existing backend implementations (except `/help` and `/team` stub).

**Test Commands:**
```bash
python -m pytest tests/ -v
python -c "
from deeprepo.tui.command_router import CommandRouter
router = CommandRouter('.')
result = router.route('/help')
print(result)
assert result['status'] == 'success'
print('PASS')
"
```

---

### ISSUE S4 — Session State Manager

**Problem:** The TUI needs to track session context: what project is loaded, whether it's initialized, what the user has been working on, and what prompts have been generated. This enables the welcome banner, `/status` responses, and context-aware prompt generation.

**What to build:**

A `SessionState` class in `deeprepo/tui/session_state.py` that:
1. Loads project state from `.deeprepo/` on startup (if it exists)
2. Tracks session-level information (current task, prompt history, timing)
3. Provides data for the welcome banner and status bar
4. Updates when commands modify project state (e.g., after `/init`)

**Class: `SessionState`**

```python
@dataclass
class SessionState:
    # Project info (loaded from .deeprepo/)
    project_path: str
    project_name: str = ""
    initialized: bool = False
    context_tokens: int = 0
    context_last_updated: datetime | None = None
    files_tracked: int = 0
    
    # Session info (runtime only)
    session_start: datetime = field(default_factory=datetime.now)
    prompt_history: list[dict] = field(default_factory=list)  # {"input": str, "timestamp": datetime}
    current_task: str = ""  # What the user said they're working on
    
    @classmethod
    def from_project(cls, project_path: str) -> "SessionState":
        """Load state from .deeprepo/ directory if it exists."""
        ...
    
    def refresh(self):
        """Reload state from .deeprepo/ (call after /init or /refresh)."""
        ...
    
    def record_prompt(self, user_input: str, generated_prompt: str):
        """Track a generated prompt for history."""
        ...
    
    @property
    def context_age(self) -> str:
        """Human-readable age: 'Fresh', '2 min ago', '3 hours ago', 'Stale (2 days)'"""
        ...
    
    @property
    def welcome_summary(self) -> str:
        """One-line summary for welcome banner."""
        ...
```

**State loading:** Read `.deeprepo/config.yaml` for project name and settings. Stat `.deeprepo/COLD_START.md` for last-modified time and approximate token count (`len(content.split()) * 1.3`). Count files in the project directory (using the same ignore rules as the codebase loader).

**Files to create:**
- `deeprepo/tui/session_state.py` — `SessionState` dataclass

**Files to modify:**
- `deeprepo/tui/shell.py` — instantiate `SessionState` on startup, pass to router and prompt builder, refresh after state-changing commands

**Acceptance Criteria:**
- [ ] `SessionState.from_project(".")` loads state from `.deeprepo/` if present
- [ ] `SessionState.from_project(".")` returns uninitialized state if `.deeprepo/` doesn't exist
- [ ] `state.context_age` returns human-readable string
- [ ] `state.welcome_summary` returns one-line project summary
- [ ] `state.record_prompt(input, output)` adds to `prompt_history`
- [ ] `state.refresh()` reloads from `.deeprepo/` after changes
- [ ] Shell welcome banner uses `state.welcome_summary`
- [ ] All 109 existing tests still pass

**Anti-Patterns:**
- Do NOT persist session state to disk. It's runtime-only. Project state (in `.deeprepo/`) is the persistent layer — session state reads from it but doesn't write to it.
- Do NOT import heavy dependencies. This is a lightweight data class, not a database.
- Do NOT cache file contents in session state. Only track metadata (counts, timestamps, paths).

**Test Commands:**
```bash
python -m pytest tests/ -v
python -c "
from deeprepo.tui.session_state import SessionState
state = SessionState.from_project('.')
print(f'Initialized: {state.initialized}')
print(f'Age: {state.context_age}')
print(f'Summary: {state.welcome_summary}')
print('PASS')
"
```

---

### ISSUE S5 — Prompt Builder: Natural Language → Clipboard Prompt

**Problem:** When a user types natural language in the TUI (e.g., "fix the broken WebSocket connection"), deeprepo needs to assemble a context-rich prompt containing the cold-start context, relevant files, and the user's ask — then copy it to clipboard.

This is the core product interaction. It's what makes deeprepo useful moment-to-moment.

**What to build:**

A `PromptBuilder` class in `deeprepo/tui/prompt_builder.py` that:
1. Reads the cold-start prompt from `.deeprepo/COLD_START.md`
2. Identifies relevant files based on keywords in the user's input
3. Assembles a structured prompt: cold start + relevant file contents + user's ask
4. Copies to clipboard via `pyperclip`
5. Returns a summary of what was assembled

**Prompt structure (what gets copied to clipboard):**

```
# Project Context
[contents of COLD_START.md]

# Relevant Files
## path/to/file1.py
```python
[file contents]
```

## path/to/file2.tsx
```tsx
[file contents]
```

# Your Task
[user's natural language input]
```

**File relevance detection (V1 — simple keyword matching):**

For the first version, use a straightforward approach:
1. Tokenize the user's input into keywords (lowercase, strip punctuation, remove stopwords)
2. Search filenames and file paths for keyword matches
3. If `.deeprepo/PROJECT.md` exists, look for file paths mentioned near matched keywords
4. Include matched files up to a token budget (default ~20K tokens worth of file content)
5. If no files match, include only the cold-start prompt + the ask

This doesn't need to be perfect. Even just the cold-start + ask is enormously more useful than pasting nothing. File matching is a bonus that improves over time (future: embeddings, AST-aware search, etc.).

**Token budgeting:**
- Cold-start prompt: typically 2K–5K tokens
- File content budget: ~20K tokens (rough estimate: `len(content) / 4`)
- User's ask: minimal
- Total target: stay under ~30K tokens so the prompt fits in most models' context windows
- If files exceed budget, prioritize by: (1) exact filename match, (2) path component match, (3) shortest files first

**Files to create:**
- `deeprepo/tui/prompt_builder.py` — `PromptBuilder` class

**Files to modify:**
- `deeprepo/tui/shell.py` — replace `_handle_natural_language()` stub with prompt builder dispatch

**Class: `PromptBuilder`**

```python
class PromptBuilder:
    def __init__(self, project_path: str, token_budget: int = 30000):
        self.project_path = project_path
        self.token_budget = token_budget
        self._cold_start: str | None = None
    
    def build(self, user_input: str) -> dict:
        """Assemble prompt, copy to clipboard, return summary.
        
        Returns:
            {
                "status": "success" | "error",
                "message": "Copied prompt (4,200 tokens, 3 files) to clipboard",
                "data": {
                    "prompt": str,           # The full assembled prompt
                    "token_estimate": int,
                    "files_included": list[str],
                    "copied": bool,
                }
            }
        """
        ...
    
    def _load_cold_start(self) -> str:
        """Read COLD_START.md, cache for session."""
        ...
    
    def _find_relevant_files(self, user_input: str) -> list[tuple[str, str]]:
        """Return list of (filepath, content) matching user's keywords."""
        ...
    
    def _assemble_prompt(self, cold_start: str, files: list[tuple[str, str]], user_ask: str) -> str:
        """Combine components into final prompt string."""
        ...
    
    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy to clipboard. Return False if clipboard unavailable (SSH, etc.)."""
        ...
```

**Acceptance Criteria:**
- [ ] `PromptBuilder(".")` creates a builder for the current project
- [ ] `builder.build("fix the WebSocket bug")` returns result dict with assembled prompt
- [ ] Prompt contains COLD_START.md content at the top
- [ ] Prompt contains relevant file contents (if matches found)
- [ ] Prompt contains the user's ask at the bottom
- [ ] Prompt is copied to clipboard (when available)
- [ ] If `.deeprepo/` doesn't exist, returns error with "Run /init first" message
- [ ] If clipboard is unavailable (SSH session, etc.), result includes `copied: False` and the prompt is printed to stdout instead
- [ ] Token estimate is included in result
- [ ] File inclusion respects token budget (doesn't assemble a 200K token prompt)
- [ ] Shell displays summary after prompt generation: "Copied prompt (4,200 tokens, 3 files) to clipboard"
- [ ] All existing tests still pass

**Anti-Patterns:**
- Do NOT make API calls in the prompt builder. It's pure text assembly — no LLM calls.
- Do NOT try to understand the code semantically. Keyword matching on filenames is the V1 approach.
- Do NOT include binary files, `node_modules`, `.git`, etc. in file search.
- Do NOT fail silently if clipboard is unavailable. Fall back to printing the prompt with a clear message.
- Do NOT include the full PROJECT.md in the prompt. Use COLD_START.md (the compressed version).

**Test Commands:**
```bash
python -m pytest tests/ -v
# Requires a .deeprepo/ directory to exist:
python -c "
from deeprepo.tui.prompt_builder import PromptBuilder
builder = PromptBuilder('.')
# If .deeprepo/ exists:
result = builder.build('fix the WebSocket connection')
print(f'Status: {result[\"status\"]}')
print(f'Message: {result[\"message\"]}')
if result['data'].get('files_included'):
    print(f'Files: {result[\"data\"][\"files_included\"]}')
print('PASS')
"
```

---

### ISSUE S6 — Interactive Onboarding: First-Run Experience

**Problem:** Currently, running `deeprepo` without API keys crashes with an error. The TUI should detect first-run conditions and walk the user through setup interactively.

**What to build:**

An `Onboarding` flow in `deeprepo/tui/onboarding.py` that handles:

1. **No `.deeprepo/` directory** — project not initialized
2. **No API key configured** — OpenRouter key not in env or config
3. **Both** — completely new user

**Onboarding flow:**

```
~/Projects/PokerPot $ deeprepo

  deeprepo v0.2.0
  
  Welcome! Let's set up deeprepo for this project.

  Step 1: API Key
  deeprepo uses OpenRouter for AI model access.
  Get your key at: https://openrouter.ai/keys
  
  Enter your OpenRouter API key (or press Enter to skip):
  > sk-or-...
  
  ✓ API key saved to ~/.deeprepo/config.yaml

  Step 2: Initialize Project
  Would you like to analyze this project now? (y/n)
  > y
  
  Analyzing project...
  ▓▓▓▓▓▓▓▓░░ 10 REPL turns · 5 sub-LLM calls · $0.63
  Generated .deeprepo/ with PROJECT.md, COLD_START.md, SESSION_LOG.md

  ✓ Ready! Type a request or /help to see commands.

> 
```

**API key storage:**
- Check (in order): `OPENROUTER_API_KEY` env var → `~/.deeprepo/config.yaml` → project `.deeprepo/config.yaml`
- Store new key in `~/.deeprepo/config.yaml` (global, not project-specific)
- Never echo the full key — show first 8 chars + `...`

**Skip behavior:**
- If user skips API key: TUI launches in "offline mode" — slash commands that don't need API work (`/status`, `/log`, `/help`), prompt builder works if COLD_START.md exists, `/init` shows clear message about needing an API key
- If user skips init: TUI launches but warns that context features are limited

**Files to create:**
- `deeprepo/tui/onboarding.py` — `run_onboarding(project_path) -> dict` function

**Files to modify:**
- `deeprepo/tui/shell.py` — call onboarding before main loop if conditions are met

**Acceptance Criteria:**
- [ ] `run_onboarding(".")` detects missing API key and prompts for it
- [ ] `run_onboarding(".")` detects uninitialized project and offers to init
- [ ] API key is saved to `~/.deeprepo/config.yaml` (global config)
- [ ] Entering an empty string for API key skips that step gracefully
- [ ] Declining project init launches TUI in limited mode
- [ ] If both API key exists and project is initialized, onboarding is skipped entirely
- [ ] The onboarding flow uses Rich formatting consistent with the rest of the TUI
- [ ] All existing tests still pass

**Anti-Patterns:**
- Do NOT store API keys in the project `.deeprepo/` directory. They should be in `~/.deeprepo/` (user-global).
- Do NOT block the TUI if onboarding is skipped. Always fall through to the session loop.
- Do NOT validate the API key by making an API call during onboarding. Just save it — validation happens when first command needs it.
- Do NOT auto-run `/init` without asking. The user should confirm (it costs money).

**Test Commands:**
```bash
python -m pytest tests/ -v
python -c "
from deeprepo.tui.onboarding import needs_onboarding
# Should return True if no global config or no .deeprepo/
print(f'Needs onboarding: {needs_onboarding(\".\")}'  )
print('PASS')
"
```

---

### ISSUE S7 — TUI Polish: Welcome Banner, Status Line, Autocomplete, Keybindings

**Problem:** The shell from S2 is functional but bare. This issue adds the polish that makes it feel like a real product.

**What to build:**

1. **Welcome banner** — Rich panel showing project name, context status, version
2. **Persistent status line** — bottom bar showing project name + context age (uses prompt_toolkit's `bottom_toolbar`)
3. **Autocomplete** — slash commands auto-complete on Tab
4. **Keybindings** — Ctrl-L to clear screen, Ctrl-R to refresh context
5. **Command output formatting** — Rich panels for command results, not raw text

**Welcome banner design:**

```
╭─────────────────────────────────────────────╮
│  deeprepo v0.2.0                            │
│  Project: PokerPot                          │
│  Context: Fresh · 3,008 tokens · 23 files   │
│                                             │
│  Type /help for commands or ask anything.   │
╰─────────────────────────────────────────────╯
```

**Status line (bottom toolbar):**

```
 deeprepo · PokerPot · Context: Fresh (2m ago) · 3 prompts generated
```

**Autocomplete definitions:**

```python
commands = [
    "/init", "/context", "/context --copy", "/context --format cursor",
    "/status", "/log", "/log add", "/log show",
    "/refresh", "/help", "/team", "exit", "quit"
]
```

Use `prompt_toolkit.completion.WordCompleter` with `sentence=True` to match full commands.

**Files to create:**
- `deeprepo/tui/completions.py` — autocomplete definitions

**Files to modify:**
- `deeprepo/tui/shell.py` — welcome banner, status toolbar, keybindings, output formatting

**Acceptance Criteria:**
- [ ] Welcome banner displays with project info on session start
- [ ] Bottom toolbar shows project name + context age
- [ ] Typing `/` and pressing Tab shows available slash commands
- [ ] Ctrl-L clears the screen
- [ ] Command results display in Rich-formatted panels
- [ ] Error results display in red-styled panels
- [ ] All existing tests still pass

**Anti-Patterns:**
- Do NOT over-design the UI. This is a terminal tool, not a GUI app. Clean and readable > fancy.
- Do NOT block the input loop for status bar updates. The toolbar should read from `SessionState` which is already up to date.
- Do NOT add mouse support or complex layouts. Keep it keyboard-driven.

**Test Commands:**
```bash
python -m pytest tests/ -v
# Manual visual test — run the TUI and verify:
# 1. Welcome banner shows
# 2. Tab completion works for /commands
# 3. Status bar updates after /init
```

---

### ISSUE S8 — CLI Entry Point Wiring

**Problem:** The TUI needs to be accessible as the default behavior when a user types `deeprepo` with no arguments.

**What to build:**

Modify `deeprepo/cli.py` so that:
1. `deeprepo` (no args) → launches TUI session
2. `deeprepo <command>` (with args) → existing CLI behavior, unchanged
3. `deeprepo --no-tui <command>` → explicit non-interactive mode (for scripts/CI)
4. `deeprepo tui` → explicit TUI launch (alias for no-args behavior)

**Entry point logic:**

```python
def main():
    if len(sys.argv) == 1:
        # No args → launch TUI
        from deeprepo.tui.shell import DeepRepoShell
        shell = DeepRepoShell(".")
        shell.run()
    else:
        # Args present → existing argparse CLI
        parser = build_parser()
        args = parser.parse_args()
        args.func(args)
```

**Files to modify:**
- `deeprepo/cli.py` — add no-args detection and TUI launch
- `pyproject.toml` — ensure `prompt_toolkit` and `pyperclip` are in dependencies, bump version to 0.2.0

**Acceptance Criteria:**
- [ ] `deeprepo` (no args) launches the TUI session
- [ ] `deeprepo init .` still works exactly as before (CLI mode)
- [ ] `deeprepo context --copy` still works exactly as before
- [ ] `deeprepo tui` explicitly launches TUI (same as no args)
- [ ] `prompt_toolkit` and `pyperclip` are listed in `pyproject.toml` dependencies
- [ ] Version bumped to 0.2.0 in `pyproject.toml`
- [ ] All existing tests still pass

**Anti-Patterns:**
- Do NOT break the existing CLI. Every existing command must work identically.
- Do NOT import `prompt_toolkit` at the top of `cli.py`. Import inside the TUI branch so the CLI path has zero new dependencies at import time.
- Do NOT change the `deeprepo` console_scripts entry point in pyproject.toml — it should still point to `cli.main`.

**Test Commands:**
```bash
python -m pytest tests/ -v
# CLI still works:
python -m deeprepo.cli init --help
python -m deeprepo.cli context --help
# TUI launches (manual):
# python -m deeprepo.cli
```

---

## Part 4: Scratchpad Protocol

Same protocol as the multi-vertical sprint. Both agents communicate through persistent markdown scratchpad files.

### Cold Start: CTO

```
You are acting as CTO for deeprepo — an open-source AI project memory tool that
generates context-rich prompts for AI coding tools. Published on PyPI as deeprepo-cli.

The project just completed the AI project memory sprint (8 issues, 109 tests passing,
PyPI published). Now we're building an interactive TUI that transforms deeprepo from
a fire-and-forget CLI into a persistent session.

Repo: ~/Desktop/Projects/deeprepo/ (github.com/Leonwenhao/deeprepo)
Key files: deeprepo/cli.py, deeprepo/cli_commands.py, deeprepo/terminal_ui.py,
deeprepo/config_manager.py, deeprepo/tui/ (new package)

You are coordinating a sprint with an Engineer agent. Your job:
1. Read SCRATCHPAD_CTO.md and SCRATCHPAD_ENGINEER.md to see current status
2. If the Engineer completed work: review it, run tests, approve or request fixes
3. If ready for next task: read TUI_DEVELOPMENT_PLAN.md Part 3 for the issue spec,
   produce a task prompt for the Engineer following the standard format
4. Update SCRATCHPAD_CTO.md with your decisions and status

The sprint covers these tasks in order:
S1 (command refactor) → S2 (TUI shell) → S3 (command router) → S4 (session state) →
S5 (prompt builder) → S6 (onboarding) → S7 (polish) → S8 (entry point wiring)

Read both scratchpads now and tell me where we are.
```

### Cold Start: Engineer

```
You are a senior engineer working on deeprepo — an AI project memory tool that
generates context-rich prompts for AI coding tools. Published on PyPI as deeprepo-cli.

Repo structure:
- deeprepo/cli.py — CLI entry point (argparse)
- deeprepo/cli_commands.py — All command handlers (init, context, log, status, refresh, new)
- deeprepo/terminal_ui.py — Rich output formatting
- deeprepo/config_manager.py — ProjectConfig, ProjectState, .deeprepo/ management
- deeprepo/tui/ — NEW TUI package (shell, command_router, prompt_builder, session_state, onboarding)
- tests/ — pytest test suite (109 tests passing)

Your CTO coordinates your work via scratchpads.

1. Read SCRATCHPAD_ENGINEER.md for your current task and any context from previous work
2. Read SCRATCHPAD_CTO.md for the latest task prompt from your CTO
3. Execute the task according to the spec
4. Run tests to verify
5. Update SCRATCHPAD_ENGINEER.md with your handoff report

Start by reading both scratchpads to see what's assigned to you.
```

---

## Part 5: Post-Sprint — What Comes After

### Week 2: Prompt Builder V2 — Smarter File Matching

Replace keyword matching with:
- AST-aware search for Python/TS files (find functions, classes, imports mentioned in the user's ask)
- `PROJECT.md` section lookup (find which files are documented near relevant keywords)
- Frequency-based relevance (files that appear in multiple contexts rank higher)
- User feedback loop: "Was this prompt helpful?" → adjust file selection

### Week 3: Session Continuity

- Persist session log to `.deeprepo/SESSION_LOG.md`
- Track which prompts the user generated and what they were working on
- On next session start, show: "Last session: worked on WebSocket fix, generated 4 prompts"
- `/resume` command to reload last session's context

### Week 4: Teams Integration

- `/team create my-team` → interactive team config
- `/team switch my-team` → change active team
- When natural language input is received with an active team, the prompt is formatted for the team's tools
- Direct execution mode: `/exec fix the WebSocket bug` → dispatches to team agents via API

### Parallel: v0.2.0 PyPI Release

Once S1–S8 ship:
- Bump version to 0.2.0
- Update README with TUI screenshots/demo
- Publish to PyPI
- Social post: "deeprepo is now an interactive AI development command center"
