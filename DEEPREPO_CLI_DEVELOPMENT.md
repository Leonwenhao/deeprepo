# deeprepo — CLI Product Sprint: Development Guide

## For: Claude Code (CTO) + Codex (Engineer) implementation
## Author: Leon (with Claude)
## Date: February 22, 2026
## Branch: `feature/cli-product` (off `main`)

---

## What We're Building

deeprepo is pivoting from "codebase analysis CLI" to "AI project memory CLI." The product generates and maintains structured project context that any AI tool (Claude Code, Cursor, Codex, ChatGPT) can consume instantly. It also supports greenfield project creation with AI-generated scaffolds and documentation.

The core thesis: every AI coding session starts from zero context. `deeprepo init` eliminates the cold start. `deeprepo context --copy` gives any AI tool full project awareness in one paste. `deeprepo new` creates projects that are context-aware from the first commit.

**What exists today:** A working RLM engine (`rlm_scaffold.py`) with domain plugin architecture (`domains/`), code + content + film domain configs, sub-LLM dispatch, caching, streaming, retry logic, and a CLI (`cli.py`) with `analyze`, `baseline`, `compare`, and `list-domains` commands.

**What we're adding:** New CLI commands (`init`, `context`, `log`, `status`, `refresh`, `new`), a "context" domain config that generates project bibles instead of bug reports, a Teams abstraction layer for multi-agent orchestration, greenfield project scaffolding, and a `.deeprepo/` directory structure that persists context across AI sessions.

---

## Architecture Overview

### System Design

```
User runs: deeprepo init ./my-project
                │
                ▼
        ┌──────────────────┐
        │   CLI Layer       │  cli_commands.py — new commands
        │   (init, context, │  cli.py — existing, extended
        │    log, new, etc) │
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │  Context Domain   │  domains/context.py — new DomainConfig
        │  (project bible   │  Prompts optimized for doc generation,
        │   generation)     │  not bug hunting
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │  RLM Engine       │  rlm_scaffold.py — UNCHANGED
        │  (REPL loop,      │  Root model writes Python, dispatches
        │   sub-LLM dispatch)│  sub-LLM workers, iterates
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │  Post-Processor   │  context_generator.py — NEW
        │  (split RLM output│  Splits analysis into .deeprepo/ files
        │   into .deeprepo/)│  Generates COLD_START.md from PROJECT.md
        └────────┬─────────┘
                 │
                 ▼
        .deeprepo/
        ├── PROJECT.md      — Full project bible
        ├── COLD_START.md   — Compressed context prompt
        ├── SESSION_LOG.md  — Session tracking
        ├── SCRATCHPAD.md   — Multi-agent coordination
        ├── config.yaml     — Project preferences
        └── .state.json     — File hashes + timestamps (gitignored)
```

### For greenfield (`deeprepo new`):

```
User runs: deeprepo new
                │
                ▼
        ┌──────────────────┐
        │  Interactive TUI  │  Collects: description, stack, team
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │  Team Router      │  teams/base.py — TeamConfig
        │  (selects agents, │  teams/__init__.py — registry
        │   workflow pattern)│
        └────────┬─────────┘
                 │
        ┌────────▼─────────┐
        │  Scaffold Agent   │  Uses selected team to generate:
        │  (LLM call via    │  - Project structure
        │   OpenRouter)     │  - Boilerplate files
        └────────┬─────────┘  - .deeprepo/ (pre-populated with intent)
                 │
                 ▼
        new-project/
        ├── src/            — AI-generated scaffold
        ├── tests/
        ├── .deeprepo/      — Context docs (generated alongside code)
        └── pyproject.toml
```

### API Configuration

All LLM calls go through OpenRouter. One API key. One endpoint. Access to every model.

```
OPENROUTER_API_KEY=sk-or-...     # Single key for everything
```

Root model calls (orchestration):
- Default: `anthropic/claude-sonnet-4-5` via OpenRouter
- SDK: `openai` Python package with `base_url="https://openrouter.ai/api/v1"`
- Fallback: Direct Anthropic API if `ANTHROPIC_API_KEY` is set

Sub-LLM calls (workers):
- Default: `minimax/minimax-m2.5` via OpenRouter
- Alternatives: `deepseek/deepseek-chat-v3`, `qwen/qwen3-coder`
- All via the same OpenRouter endpoint

The "Chinese AI with American characteristics" play: MiniMax M2.5, DeepSeek V3, Qwen3 — all world-class open-source models at 1/10th to 1/20th frontier US pricing. OpenRouter abstracts the provider, so users never deal with Chinese API endpoints, payment systems, or documentation. They get American UX backed by Chinese compute economics.

```python
# Every LLM call in the system uses this pattern
import openai

client = openai.OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

# Root model (orchestration)
root_response = client.chat.completions.create(
    model="anthropic/claude-sonnet-4-5",  # or any model via OpenRouter
    messages=[...],
    max_tokens=8192,
)

# Sub-LLM (focused analysis)
sub_response = client.chat.completions.create(
    model="minimax/minimax-m2.5",
    messages=[...],
    max_tokens=4096,
)
```

---

## Tech Stack

- **Python 3.11+** with `uv` package manager
- **openai** SDK — for ALL model calls via OpenRouter
- **anthropic** SDK — optional, for direct Anthropic API fallback
- **rich** — terminal progress, colors, tables, panels
- **click** or **typer** — CLI framework (evaluate vs existing argparse)
- **pyyaml** — config file handling
- **python-dotenv** — env var management
- **asyncio** — parallel sub-LLM dispatch
- No web framework, no database, no frontend. Pure CLI tool.

---

## New Module Architecture

### Files to Create (in build order)

```
deeprepo/
├── config_manager.py       # S1 — Read/write config.yaml + .state.json
├── domains/context.py      # S2 — Context generation DomainConfig
├── context_generator.py    # S3 — Post-process RLM output → .deeprepo/ files
├── cli_commands.py         # S4 — New command handlers (init, context, log, etc.)
├── refresh.py              # S5 — Diff-aware refresh logic
├── teams/                  # S6 — Teams abstraction
│   ├── __init__.py         #      Registry + get_team()
│   └── base.py             #      TeamConfig dataclass
├── scaffold.py             # S7 — Greenfield project generation
└── terminal_ui.py          # S8 — Rich output formatting

tests/
├── test_config_manager.py  # S1
├── test_context_domain.py  # S2
├── test_context_gen.py     # S3
├── test_cli_commands.py    # S4
├── test_refresh.py         # S5
├── test_teams.py           # S6
├── test_scaffold.py        # S7
└── fixtures/
    └── sample_project/     # Tiny project for testing init/refresh
```

### Files to Modify

```
deeprepo/cli.py             # Mount new commands alongside existing ones
deeprepo/llm_clients.py     # Add OpenRouter-only mode, update defaults
deeprepo/domains/__init__.py # Register "context" domain
```

---

## Issue Specifications

### Sprint Priority Sequence

S1 → S2 → S3 → S4 (these four = working `deeprepo init`)
S5 (refresh)
S6 → S7 (teams + greenfield)
S8 (terminal polish)

Issues S1-S4 are the critical path. After S4 ships, `deeprepo init` and `deeprepo context` work end-to-end. S5-S8 add depth and the greenfield flow.

**Codex performance note:** Last sprint Codex completed 70% of issues with 50% context window remaining. This sprint, issues are sized larger — each one is a complete feature, not a refactoring step. Push Codex with full specs and trust it to handle multi-file changes. Reserve the CTO pass for integration review, not hand-holding.

---

### ISSUE S1 — Config Manager + .deeprepo/ Directory Structure

**Problem:** deeprepo needs a standard project-local directory (`.deeprepo/`) for persisting context across sessions, plus config management for project preferences and internal state.

**What to build:**

`deeprepo/config_manager.py` — handles three responsibilities:
1. Initialize a `.deeprepo/` directory with template files
2. Read/write `config.yaml` (user-editable preferences)
3. Read/write `.state.json` (internal tracking, gitignored)

**Class: `ConfigManager`**

```python
@dataclass
class ProjectConfig:
    """User-editable project preferences from config.yaml"""
    version: int = 1
    root_model: str = "anthropic/claude-sonnet-4-5"
    sub_model: str = "minimax/minimax-m2.5"
    max_turns: int = 10
    cost_limit: float = 2.00
    context_max_tokens: int = 3000
    session_log_count: int = 3        # Recent sessions to include in cold-start
    include_scratchpad: bool = True
    include_tech_debt: bool = True
    auto_refresh: bool = False
    stale_threshold_hours: int = 72
    project_name: str = ""            # Auto-detected or overridden
    project_description: str = ""
    team: str = ""                    # Default team (set by `deeprepo new`)
    ignore_paths: list[str] = field(default_factory=list)

@dataclass
class ProjectState:
    """Internal state from .state.json — not user-editable"""
    last_refresh: str = ""            # ISO timestamp
    last_commit: str = ""             # Git commit hash
    file_hashes: dict[str, str] = field(default_factory=dict)  # path → sha256
    analysis_cost: float = 0.0
    analysis_turns: int = 0
    sub_llm_dispatches: int = 0
    created_at: str = ""              # ISO timestamp
    created_with: str = ""            # "init" or "new"
    original_intent: str = ""         # From `deeprepo new` description

class ConfigManager:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.deeprepo_dir = self.project_path / ".deeprepo"
    
    def is_initialized(self) -> bool:
        """Check if .deeprepo/ exists and has config.yaml"""
    
    def initialize(self, config: ProjectConfig | None = None) -> None:
        """Create .deeprepo/ directory with template files.
        Creates: config.yaml, SESSION_LOG.md, SCRATCHPAD.md, .state.json
        Does NOT create PROJECT.md or COLD_START.md (those come from analysis).
        Creates .gitignore inside .deeprepo/ that ignores: .state.json, modules/"""
    
    def load_config(self) -> ProjectConfig:
        """Read config.yaml → ProjectConfig"""
    
    def save_config(self, config: ProjectConfig) -> None:
        """Write ProjectConfig → config.yaml"""
    
    def load_state(self) -> ProjectState:
        """Read .state.json → ProjectState"""
    
    def save_state(self, state: ProjectState) -> None:
        """Write ProjectState → .state.json"""
    
    def detect_project_name(self) -> str:
        """Auto-detect from directory name, pyproject.toml, or package.json"""
    
    def detect_stack(self) -> dict:
        """Detect language, framework, package manager from project files.
        Returns: {"language": "python", "framework": "fastapi", 
                  "package_manager": "uv", "test_framework": "pytest"}"""
```

**Template files created by `initialize()`:**

`SESSION_LOG.md`:
```markdown
# Session Log

> Track what happens across AI-assisted work sessions.
> Add entries: `deeprepo log "description of what you did"`
> View recent: `deeprepo log show`

---
```

`SCRATCHPAD.md`:
```markdown
# Scratchpad

> Coordinate work between multiple AI agents.
> This file is included in your cold-start prompt via `deeprepo context`.
>
> Usage:
> 1. Write a task spec in "Current Task" for the implementing agent
> 2. The implementing agent writes results in "Latest Handoff"
> 3. Review and write the next task

## Status
- **Current Task:** None
- **Phase:** IDLE

## Current Task

[Write task specifications here]

## Latest Handoff

[Implementation results go here]

## Decision Log

[Append-only — record architectural decisions here]
```

`.gitignore` (inside `.deeprepo/`):
```
.state.json
modules/
```

**Files to create:**
- `deeprepo/config_manager.py` — ConfigManager class + dataclasses
- `tests/test_config_manager.py` — unit tests
- `tests/fixtures/sample_project/` — tiny project for testing (3 Python files, a pyproject.toml, a README)

**Acceptance Criteria:**
- [ ] `ConfigManager("/path/to/project").initialize()` creates `.deeprepo/` with config.yaml, SESSION_LOG.md, SCRATCHPAD.md, .state.json, .gitignore
- [ ] `load_config()` → `ProjectConfig` round-trips correctly through YAML
- [ ] `load_state()` → `ProjectState` round-trips correctly through JSON
- [ ] `detect_project_name()` reads from pyproject.toml `[project] name` if available, falls back to directory name
- [ ] `detect_stack()` identifies Python/FastAPI from `pyproject.toml` with fastapi dependency
- [ ] `is_initialized()` returns True after `initialize()`, False on a bare directory
- [ ] `.deeprepo/.gitignore` excludes `.state.json` and `modules/`
- [ ] All tests pass: `python -m pytest tests/test_config_manager.py -v`

**Anti-Patterns:**
- Do NOT use `configparser` — use PyYAML for config.yaml
- Do NOT store API keys in config.yaml — those go in env vars or `~/.config/deeprepo/`
- Do NOT create PROJECT.md or COLD_START.md during `initialize()` — those come from the RLM analysis in S3

**Test Commands:**
```bash
python -m pytest tests/test_config_manager.py -v
python -c "
from deeprepo.config_manager import ConfigManager
cm = ConfigManager('tests/fixtures/sample_project')
cm.initialize()
config = cm.load_config()
print(f'Project: {cm.detect_project_name()}')
print(f'Stack: {cm.detect_stack()}')
print(f'Initialized: {cm.is_initialized()}')
"
```

---

### ISSUE S2 — Context Domain Config

**Problem:** The existing domain configs (code, content, film) are optimized for analysis reports and bug hunting. The new "context" domain generates structured project documentation designed for AI tools to consume as session context.

**What to build:**

`deeprepo/domains/context.py` — a new DomainConfig where the RLM engine produces a project bible instead of a codebase review.

The root model's task is different: instead of "find bugs and assess quality," it's "map architecture, identify patterns and conventions, trace module dependencies, and produce structured documentation that gives an AI agent complete project awareness."

The sub-LLM worker's task is different: instead of "analyze this file for issues," it's "describe this module's purpose, key abstractions, dependencies, conventions, and anything a new developer (or AI) needs to know to work on it effectively."

**Root System Prompt — Context Domain:**

The root model should produce:

1. **Identity** — language, framework, package manager, test framework, structure (detected programmatically from files, not from LLM guessing)
2. **Architecture** — how the system works as a whole (entry points, request lifecycle, data flow, key abstractions)
3. **Module Map** — for each significant module: purpose, entry file, key patterns, depends-on, depended-on-by (3-5 lines each)
4. **Patterns & Conventions** — error handling, naming, testing, config, imports — the things that make generated code match existing style
5. **Dependency Graph** — ASCII or structured representation of module relationships
6. **Tech Debt & Known Issues** — things an AI tool should be aware of when working on the codebase

The root model should be instructed to:
- Start by examining `pyproject.toml`/`package.json`/`Cargo.toml` for identity info
- Map the dependency graph programmatically by tracing imports with regex
- Dispatch sub-LLM workers for each major module/directory
- Synthesize sub-LLM results into the structured output above
- Use a structured output format (markdown with consistent headers) that `context_generator.py` can parse

**Sub System Prompt — Context Domain:**

The sub-LLM receives a module (group of related files) and produces:
- **Purpose** — what this module does (1-2 sentences)
- **Entry point** — which file/function is the main entry
- **Key patterns** — design patterns, abstractions, conventions used
- **Dependencies** — what this module imports from other modules
- **Conventions** — naming, error handling, testing patterns specific to this module
- **Notes for AI** — anything unusual that would trip up an AI generating code for this module

Keep under 600 words per module. Focus on "what would a new developer need to know" not "describe every function."

**User Prompt Template:**

The initial user message provides metadata + file tree (same as code domain) but frames the task differently:

```
You are analyzing a software project to generate comprehensive documentation 
for AI coding assistants. Your output will be used as context in future AI 
sessions — it needs to be structured, concise, and focused on information 
that helps an AI agent write correct, consistent code for this project.

{metadata_str}

{file_tree}

Start by examining the project configuration files to identify the tech stack, 
then map the module structure and trace dependencies. Use llm_batch() to 
analyze each major module in parallel. Synthesize everything into a structured 
project bible.

Your final answer should use this exact structure:
## Identity
## Architecture  
## Module Map
## Patterns & Conventions
## Dependency Graph
## Tech Debt & Known Issues
```

**Files to create:**
- `deeprepo/domains/context.py` — `CONTEXT_DOMAIN = DomainConfig(...)`

**Files to modify:**
- `deeprepo/domains/__init__.py` — register CONTEXT_DOMAIN in registry

**Acceptance Criteria:**
- [ ] `get_domain("context")` returns a valid DomainConfig
- [ ] Root prompt instructs for documentation generation, not bug hunting
- [ ] Root prompt specifies the exact output structure (Identity through Tech Debt)
- [ ] Sub prompt focuses on module understanding for AI consumption
- [ ] `data_variable_name` is `"codebase"` (same variable name as code domain — the loader is shared)
- [ ] Prompt includes instruction to start with config files for stack detection
- [ ] Prompt includes instruction to use `llm_batch()` for parallel module analysis
- [ ] Domain registered and accessible via `list-domains`

**Anti-Patterns:**
- Do NOT copy the code domain prompts and find-replace — the tasks are fundamentally different
- Do NOT make prompts excessively long — the root model needs clear, actionable instructions, not a manual
- Do NOT change the codebase loader — the context domain uses the same `load_codebase()` function

**Test Commands:**
```bash
python -c "
from deeprepo.domains import get_domain
d = get_domain('context')
print(f'Domain: {d.name}')
print(f'Label: {d.label}')
assert 'Identity' in d.root_system_prompt or 'identity' in d.root_system_prompt
assert 'Architecture' in d.root_system_prompt or 'architecture' in d.root_system_prompt
assert d.data_variable_name == 'codebase'
print('PASS')
"
```

---

### ISSUE S3 — Context Generator + `deeprepo init` Command

**Problem:** The RLM engine produces a single markdown analysis as `answer["content"]`. The `init` command needs to run the context domain analysis AND split the output into the `.deeprepo/` file structure (PROJECT.md, COLD_START.md, modules/).

**What to build:**

**Part A: `deeprepo/context_generator.py`**

This module takes raw RLM analysis output and produces the `.deeprepo/` files.

```python
class ContextGenerator:
    def __init__(self, project_path: str, config: ProjectConfig):
        self.project_path = Path(project_path)
        self.config = config
        self.deeprepo_dir = self.project_path / ".deeprepo"
    
    def generate(self, analysis_output: str, state: ProjectState) -> dict:
        """Take raw RLM output, produce .deeprepo/ files.
        
        1. Parse analysis_output by ## headers into sections
        2. Write PROJECT.md with full analysis + metadata header
        3. Generate COLD_START.md by compressing PROJECT.md
        4. Update .state.json with analysis metadata
        5. Return dict of generated file paths
        """
    
    def generate_project_md(self, analysis_output: str) -> str:
        """Add metadata header to analysis output.
        Header includes: generated-by version, timestamp, commit hash, 
        refresh command."""
    
    def generate_cold_start(self, project_md: str) -> str:
        """Compress PROJECT.md into a token-efficient cold-start prompt.
        
        Algorithm:
        1. Extract Identity section (keep full — small)
        2. Extract Architecture section (keep full — critical)
        3. Extract Module Map (keep headers + purpose only, drop details)
        4. Extract Patterns & Conventions (keep full — critical for code gen)
        5. Skip Dependency Graph (too large, low value for cold-start)
        6. Extract Tech Debt (keep if under token budget)
        7. Append Active State from SESSION_LOG.md and SCRATCHPAD.md
        8. Check total against config.context_max_tokens
        9. If over budget, trim module map entries
        
        The cold-start is LOCAL ONLY — no API call. Must be instant."""
    
    def update_cold_start(self) -> str:
        """Re-generate COLD_START.md from existing PROJECT.md + current 
        session log + scratchpad state. Called by `deeprepo context` and 
        after `deeprepo log`."""
```

The cold-start compression is the most important function in the whole product. A 2K token cold-start that captures the right information is worth more than a 10K token dump. The algorithm is mechanical (section parsing + token budgeting), not LLM-based — it must be instant and free.

**Part B: `deeprepo init` command**

Add to `deeprepo/cli_commands.py` (new file for all new commands):

```python
def cmd_init(args):
    """Run context domain analysis and generate .deeprepo/ directory.
    
    Flow:
    1. Check if .deeprepo/ already exists → warn and confirm overwrite
    2. ConfigManager.initialize() → create directory + templates
    3. ConfigManager.detect_project_name() + detect_stack() → populate config
    4. run_analysis(path, domain="context") → get analysis output
    5. ContextGenerator.generate(output) → write PROJECT.md + COLD_START.md
    6. Print onboarding instructions
    """
```

**Part C: `deeprepo context` command**

```python
def cmd_context(args):
    """Output the cold-start prompt. No API call — reads .deeprepo/ files.
    
    Flags:
    --copy    Copy to clipboard (uses pyperclip or subprocess pbcopy/xclip)
    --format  Tool-specific output (raw, cursor, claude-code, codex) — V1, stub for now
    
    Flow:
    1. Check .deeprepo/ exists
    2. ContextGenerator.update_cold_start() → regenerate from current state
    3. Print to stdout or copy to clipboard
    4. Show token count and what's included
    """
```

**Files to create:**
- `deeprepo/context_generator.py` — ContextGenerator class
- `deeprepo/cli_commands.py` — cmd_init, cmd_context handlers

**Files to modify:**
- `deeprepo/cli.py` — mount `init` and `context` subcommands, wire to cli_commands

**Acceptance Criteria:**
- [ ] `deeprepo init tests/fixtures/sample_project` creates `.deeprepo/` directory with all expected files
- [ ] `PROJECT.md` contains the RLM analysis with a metadata header (version, timestamp, commit)
- [ ] `COLD_START.md` is a compressed version of PROJECT.md under 3000 tokens
- [ ] `COLD_START.md` includes Active State section pulled from SESSION_LOG.md
- [ ] `deeprepo context` outputs COLD_START.md content to stdout
- [ ] `deeprepo context --copy` copies to clipboard (or falls back to stdout with message if clipboard unavailable)
- [ ] `deeprepo init` on an already-initialized project warns and asks for confirmation
- [ ] `.state.json` is updated with analysis cost, turns, timestamp
- [ ] config.yaml has auto-detected project name and stack

**Anti-Patterns:**
- Do NOT call an LLM for cold-start generation — it must be instant and free
- Do NOT require `rich` for basic functionality — use it for pretty output but fall back to plain text
- Do NOT block on clipboard — if pyperclip/pbcopy fails, print to stdout with a helpful message
- Do NOT change `rlm_scaffold.py` — the context domain uses the existing engine as-is

**Test Commands:**
```bash
# Unit tests
python -m pytest tests/test_context_gen.py -v

# Integration test (requires API keys, costs ~$0.30)
python -m deeprepo.cli init tests/fixtures/sample_project -q
cat tests/fixtures/sample_project/.deeprepo/PROJECT.md | head -20
python -m deeprepo.cli context --path tests/fixtures/sample_project
```

---

### ISSUE S4 — Session Log + Status Commands

**Problem:** Context goes stale without session tracking. `deeprepo log` lets developers record what happened in each AI session. `deeprepo status` shows the health of project context.

**What to build:**

**`deeprepo log` command:**

```python
def cmd_log(args):
    """Two modes:
    
    deeprepo log "description"     → Append entry to SESSION_LOG.md
    deeprepo log show              → Print recent entries
    deeprepo log show --count 10   → Print last 10 entries
    """

def append_log_entry(deeprepo_dir: Path, message: str) -> None:
    """Append timestamped entry to SESSION_LOG.md.
    Format:
    ---
    ## YYYY-MM-DD HH:MM
    
    {message}
    """

def show_log_entries(deeprepo_dir: Path, count: int = 5) -> list[dict]:
    """Parse SESSION_LOG.md, return recent entries.
    Each entry: {"timestamp": str, "message": str}"""
```

After appending a log entry, automatically regenerate COLD_START.md so the next `deeprepo context` call includes the new session info. This calls `ContextGenerator.update_cold_start()` which is local-only (no API call).

**`deeprepo status` command:**

```python
def cmd_status(args):
    """Show context health at a glance.
    
    Checks:
    1. Does .deeprepo/ exist?
    2. How old is PROJECT.md? (stale threshold from config)
    3. How many files changed since last refresh? (compare file hashes in .state.json)
    4. How many session log entries?
    5. Scratchpad state (IDLE / active task)
    
    Output:
    deeprepo · myproject
    
    PROJECT.md     ✓ current     (refreshed 2h ago)
    COLD_START.md  ✓ current     (synced)
    SESSION_LOG.md ⚠ 3 sessions  (last: Feb 21)
    SCRATCHPAD.md  ✓ clean       (no active tasks)
    
    Changed since last refresh:
      modified: src/auth/handlers.py
      added:    src/middleware/rate_limit.py
    
    Run `deeprepo refresh` to update context.
    """

def get_changed_files(project_path: Path, state: ProjectState) -> dict:
    """Compare current file hashes against .state.json.
    Returns: {"modified": [...], "added": [...], "deleted": [...]}
    Uses SHA-256 of file contents."""
```

**Files to create:**
- Add `cmd_log`, `cmd_status`, `append_log_entry`, `show_log_entries`, `get_changed_files` to `deeprepo/cli_commands.py`
- `tests/test_cli_commands.py` — tests for log and status

**Files to modify:**
- `deeprepo/cli.py` — mount `log` and `status` subcommands

**Acceptance Criteria:**
- [ ] `deeprepo log "test message"` appends timestamped entry to SESSION_LOG.md
- [ ] `deeprepo log show` prints the 5 most recent entries
- [ ] `deeprepo log show --count 10` prints the 10 most recent entries
- [ ] After `deeprepo log`, COLD_START.md is regenerated to include the new entry
- [ ] `deeprepo status` shows context health (current/stale/missing for each file)
- [ ] `deeprepo status` lists files changed since last refresh
- [ ] `deeprepo status` on an uninitialized project prints helpful "run deeprepo init first" message
- [ ] File hash comparison correctly detects modified, added, and deleted files

**Anti-Patterns:**
- Do NOT use a database for session logs — it's a markdown file, append-only
- Do NOT call any LLM in `log` or `status` — these must be instant
- Do NOT parse git for changed files — use file hash comparison from .state.json (git-independent)

**Test Commands:**
```bash
python -m pytest tests/test_cli_commands.py -v

# Manual testing (after S3 ships)
cd tests/fixtures/sample_project
python -m deeprepo.cli log "Test session entry"
python -m deeprepo.cli log show
python -m deeprepo.cli status
```

---

### ISSUE S5 — Diff-Aware Refresh

**Problem:** After initial `init`, the codebase evolves. `deeprepo refresh` re-analyzes changed files and updates context docs without re-analyzing the entire project.

**What to build:**

`deeprepo/refresh.py`:

```python
class RefreshEngine:
    def __init__(self, project_path: str, config: ProjectConfig, state: ProjectState):
        self.project_path = Path(project_path)
        self.config = config
        self.state = state
    
    def get_changes(self) -> dict:
        """Compare current file hashes against state.file_hashes.
        Returns: {"modified": [paths], "added": [paths], "deleted": [paths], 
                  "unchanged_count": int}"""
    
    def refresh(self, full: bool = False) -> dict:
        """Run diff-aware refresh.
        
        If full=True: re-analyze everything (same as init).
        
        If full=False (default):
        1. get_changes() → identify modified/added/deleted files
        2. If no changes: print "Already up to date" and return
        3. Load cached module analyses from .deeprepo/modules/ for unchanged files
        4. Run RLM analysis with context domain, but only dispatch sub-LLM 
           workers for changed files
        5. Merge new module analyses with cached ones
        6. Re-synthesize PROJECT.md from merged analyses
        7. Regenerate COLD_START.md
        8. Update .state.json with new hashes + timestamp
        
        Returns: {"changed_files": int, "cost": float, "turns": int}
        """
    
    def compute_file_hashes(self) -> dict[str, str]:
        """SHA-256 hash every file that would be loaded by codebase_loader.
        Returns: {filepath: hash}"""
```

The key optimization: for diff-aware refresh, the root model receives the FULL project metadata (file tree, sizes) plus a note about which files changed. It can read cached analyses for unchanged modules and only dispatch workers for changed files. This typically drops the refresh to 1-2 REPL turns and 2-5 sub-LLM dispatches ($0.05-$0.15).

**Command handler:**

```python
def cmd_refresh(args):
    """deeprepo refresh          → diff-aware refresh (cheap, fast)
       deeprepo refresh --full   → full re-analysis (same as init)
    """
```

**Files to create:**
- `deeprepo/refresh.py` — RefreshEngine class
- `tests/test_refresh.py`

**Files to modify:**
- `deeprepo/cli_commands.py` — add cmd_refresh
- `deeprepo/cli.py` — mount refresh subcommand

**Acceptance Criteria:**
- [ ] `deeprepo refresh` with no file changes prints "Already up to date"
- [ ] `deeprepo refresh` after modifying a file only dispatches sub-LLM for that file
- [ ] `deeprepo refresh --full` re-analyzes everything
- [ ] `.state.json` file hashes are updated after refresh
- [ ] PROJECT.md and COLD_START.md are regenerated
- [ ] Refresh cost for a single changed file is < $0.20

**Anti-Patterns:**
- Do NOT re-analyze unchanged files — that defeats the purpose
- Do NOT require git — hash comparison works on any directory
- Do NOT store full module analyses in .state.json — they go in .deeprepo/modules/ (gitignored)

---

### ISSUE S6 — Teams Infrastructure

**Problem:** deeprepo needs an abstraction layer for multi-agent orchestration. Users select a "team" (a named configuration of agents + workflow pattern), and the orchestration happens under the hood. This issue builds the infrastructure only — specific team definitions come later.

**What to build:**

`deeprepo/teams/base.py`:

```python
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class AgentConfig:
    """Configuration for a single agent in a team."""
    role: str                          # "architect", "engineer", "researcher", etc.
    model: str                         # OpenRouter model string
    description: str                   # What this agent does
    system_prompt: str = ""            # Role-specific system prompt
    max_tokens: int = 8192
    temperature: float = 0.0

@dataclass 
class TeamConfig:
    """Configuration for a multi-agent team."""
    
    # Identity
    name: str                          # e.g., "dream-team", "sprinter", "reviewer"
    display_name: str                  # e.g., "The Dream Team", "The Sprinter"
    description: str                   # One-line for CLI help
    tagline: str = ""                  # e.g., "Codex + Claude Code + Gemini"
    
    # Agents
    agents: list[AgentConfig] = field(default_factory=list)
    
    # Workflow
    workflow: str = "sequential"       # "sequential", "parallel", "adversarial"
    # sequential: agents take turns (architect → engineer → reviewer)
    # parallel: agents work simultaneously on different aspects
    # adversarial: one agent writes, another critiques, iterate
    
    # Capabilities
    can_scaffold: bool = False         # Can this team create new projects?
    can_analyze: bool = True           # Can this team analyze existing projects?
    can_implement: bool = False        # Can this team write code?
    
    # Cost profile
    estimated_cost_per_task: str = ""  # e.g., "$0.50-$1.50"
```

`deeprepo/teams/__init__.py`:

```python
from .base import TeamConfig, AgentConfig

TEAM_REGISTRY: dict[str, TeamConfig] = {}

def register_team(team: TeamConfig) -> None:
    """Add a team to the registry."""
    TEAM_REGISTRY[team.name] = team

def get_team(name: str) -> TeamConfig:
    """Get a team by name. Raise ValueError with available teams if not found."""
    if name not in TEAM_REGISTRY:
        available = ", ".join(TEAM_REGISTRY.keys())
        raise ValueError(f"Unknown team '{name}'. Available: {available}")
    return TEAM_REGISTRY[name]

def list_teams() -> list[TeamConfig]:
    """Return all registered teams."""
    return list(TEAM_REGISTRY.values())
```

**Initial team registrations (placeholder — real team definitions come later):**

Register one default team so the system is functional:

```python
# The Analyst — single-agent team for analysis tasks (what deeprepo init uses today)
ANALYST_TEAM = TeamConfig(
    name="analyst",
    display_name="The Analyst",
    description="Single-agent analysis using RLM orchestration",
    tagline="Sonnet + MiniMax workers",
    agents=[
        AgentConfig(
            role="orchestrator",
            model="anthropic/claude-sonnet-4-5",
            description="Root model for RLM orchestration"
        ),
    ],
    workflow="sequential",
    can_scaffold=False,
    can_analyze=True,
    can_implement=False,
    estimated_cost_per_task="$0.30-$1.50",
)

register_team(ANALYST_TEAM)
```

**CLI additions:**

```python
def cmd_list_teams(args):
    """deeprepo teams → list available teams with descriptions"""

# Add --team flag to init and new commands
# Default team: "analyst" for init, user-selected for new
```

**Files to create:**
- `deeprepo/teams/__init__.py`
- `deeprepo/teams/base.py`
- `tests/test_teams.py`

**Files to modify:**
- `deeprepo/cli.py` — add `teams` subcommand, add `--team` flag to init/new
- `deeprepo/config_manager.py` — store selected team in config.yaml

**Acceptance Criteria:**
- [ ] `TeamConfig` and `AgentConfig` dataclasses exist with all fields from spec
- [ ] `get_team("analyst")` returns the default team
- [ ] `list_teams()` returns all registered teams
- [ ] `get_team("nonexistent")` raises ValueError with helpful message
- [ ] `deeprepo teams` lists available teams with display name, description, tagline
- [ ] `--team` flag exists on `init` subcommand (stored in config.yaml)
- [ ] Default team is "analyst" when `--team` is not specified

**Anti-Patterns:**
- Do NOT implement actual multi-agent orchestration yet — this is the abstraction ONLY
- Do NOT create a complex agent dispatch system — that comes when real teams are defined
- Do NOT use abstract base classes — TeamConfig is a dataclass, not an ABC
- Do NOT couple teams to specific API providers — models are OpenRouter strings

---

### ISSUE S7 — Greenfield Project Scaffolding (`deeprepo new`)

**Problem:** Developers who don't have an existing codebase should be able to start a project from the terminal with full AI context from the first commit.

**What to build:**

`deeprepo/scaffold.py`:

```python
class ProjectScaffolder:
    def __init__(self, team: TeamConfig):
        self.team = team
    
    def scaffold(self, 
                 description: str,
                 stack: dict,
                 project_name: str,
                 output_dir: str) -> dict:
        """Generate a new project with AI-generated structure.
        
        1. Build a scaffold prompt from description + stack preferences
        2. Call the team's primary agent via OpenRouter
        3. Parse the response into a file structure
        4. Write files to output_dir
        5. Initialize .deeprepo/ with:
           - config.yaml (with team, stack, original_intent)
           - PROJECT.md (generated from the scaffold, not from analysis)
           - COLD_START.md (compressed)
           - SESSION_LOG.md (with "Project created" as first entry)
        6. Return dict of created files
        """
    
    def build_scaffold_prompt(self, 
                               description: str,
                               stack: dict) -> str:
        """Build the prompt that generates the project structure.
        
        The prompt asks the LLM to output a structured response:
        - File tree with descriptions
        - Content for each file (actual code)
        - A project summary (becomes PROJECT.md)
        
        Output format uses a parseable structure:
        ===FILE: path/to/file===
        [file content]
        ===END_FILE===
        
        ===PROJECT_SUMMARY===
        [structured project documentation]
        ===END_SUMMARY===
        """
    
    def parse_scaffold_response(self, response: str) -> dict:
        """Parse the LLM response into {filepath: content} dict + summary.
        Returns: {"files": {path: content}, "summary": str}"""
```

**Interactive flow for `deeprepo new`:**

```python
def cmd_new(args):
    """Interactive project creation.
    
    Flow:
    1. Ask: "What are you building?" → free text description
    2. Ask: "Stack preference?" → detect from description or ask
       Options: Python/FastAPI, Python/Django, Node/Express, 
                TypeScript/Next.js, Let the team decide, Other
    3. Ask: "Project name?" → suggest from description, allow override
    4. Show: team recommendation + cost estimate
    5. Confirm → run scaffolding
    6. Print: created files + next steps
    
    Non-interactive mode:
    deeprepo new --description "..." --stack python-fastapi --name my-api -y
    """
```

For V0, the scaffold uses a single LLM call (the team's primary agent) to generate the project structure. The multi-agent orchestration where different agents handle different parts of scaffolding is a future enhancement when real teams are defined.

The critical detail: `.deeprepo/` is created simultaneously with the project scaffold. The `config.yaml` includes `created_with: "new"` and `original_intent: "user's description"`. The PROJECT.md is generated from the scaffold response summary, not from an analysis pass. This means the project is context-aware from the first commit — no separate `init` step needed.

**Files to create:**
- `deeprepo/scaffold.py` — ProjectScaffolder class
- `tests/test_scaffold.py`

**Files to modify:**
- `deeprepo/cli_commands.py` — add cmd_new
- `deeprepo/cli.py` — mount `new` subcommand

**Acceptance Criteria:**
- [ ] `deeprepo new` starts an interactive flow (description → stack → name → confirm)
- [ ] `deeprepo new --description "REST API for recipes" --stack python-fastapi --name recipe-api -y` runs non-interactively
- [ ] Generated project has a sensible directory structure matching the described stack
- [ ] `.deeprepo/` is created inside the new project with config.yaml, PROJECT.md, COLD_START.md, SESSION_LOG.md
- [ ] `config.yaml` includes `created_with: new` and `original_intent` fields
- [ ] `SESSION_LOG.md` has "Project created with deeprepo new" as first entry
- [ ] COLD_START.md includes the original intent and project description
- [ ] `deeprepo context` works immediately in the new project directory
- [ ] Non-interactive mode works with all required flags

**Anti-Patterns:**
- Do NOT generate enormous projects — the scaffold should be a clean starting point (5-15 files), not a complete application
- Do NOT hard-code specific frameworks — the scaffold prompt adapts to whatever stack the user chooses
- Do NOT skip `.deeprepo/` creation — that's the whole point of using `deeprepo new` over a regular scaffold tool
- Do NOT require git — create the project directory without initializing a git repo (user can do that themselves)

**Test Commands:**
```bash
python -m pytest tests/test_scaffold.py -v

# Integration test (requires API key, costs ~$0.10-$0.30)
python -m deeprepo.cli new --description "Simple TODO API" --stack python-fastapi --name test-todo -y -o /tmp/
ls -la /tmp/test-todo/
ls -la /tmp/test-todo/.deeprepo/
cat /tmp/test-todo/.deeprepo/COLD_START.md
```

---

### ISSUE S8 — Terminal Output Polish

**Problem:** The CLI needs professional terminal output — progress bars, colored status, panels, and the onboarding experience that teaches the workflow.

**What to build:**

`deeprepo/terminal_ui.py`:

```python
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.tree import Tree

console = Console()

def print_header(version: str) -> None:
    """Print 'deeprepo v0.5.0' styled header"""

def print_scan_results(metadata: dict) -> None:
    """Print file counts, detected stack, estimated cost"""

def print_analysis_progress(turn: int, max_turns: int, description: str, 
                             dispatches: int, cost: float) -> None:
    """Print per-turn progress during RLM analysis"""

def print_init_complete(files_created: dict, cost: float, 
                         dispatches: int, turns: int) -> None:
    """Print the created file tree + metrics"""

def print_onboarding() -> None:
    """Print the boxed onboarding instructions.
    This is the teaching moment — shows the three-command workflow."""

def print_status(project_name: str, file_status: dict, 
                  changed_files: dict) -> None:
    """Print the status dashboard"""

def print_team_list(teams: list) -> None:
    """Print available teams with display names and descriptions"""

def print_context_copied(token_count: int, includes: list[str]) -> None:
    """Print confirmation after context --copy"""

def print_cost_estimate(estimated_min: float, estimated_max: float) -> None:
    """Print cost estimate with confirmation prompt"""

def confirm(message: str, default: bool = True) -> bool:
    """Prompt for yes/no confirmation. Returns default if --yes flag is set."""
```

All `print_*` functions should gracefully degrade to plain text if `rich` is not installed. This means wrapping rich imports in try/except and providing plain-text fallbacks. `rich` should be an optional dependency, not required.

**The onboarding panel (printed after `deeprepo init`):**

```
╭──────────────────────────────────────────────────────────╮
│                                                          │
│  Your project now has AI memory.                         │
│                                                          │
│  Start every AI session:                                 │
│    $ deeprepo context --copy                             │
│    Then paste into Claude Code, Cursor, ChatGPT, etc.    │
│                                                          │
│  After each session:                                     │
│    $ deeprepo log "what you did and what's next"         │
│                                                          │
│  When your code changes:                                 │
│    $ deeprepo refresh                                    │
│                                                          │
╰──────────────────────────────────────────────────────────╯
```

**Files to create:**
- `deeprepo/terminal_ui.py`
- No separate tests needed — output formatting is tested visually

**Files to modify:**
- `deeprepo/cli_commands.py` — replace print() calls with terminal_ui functions
- `setup.cfg` or `pyproject.toml` — add `rich` as optional dependency

**Acceptance Criteria:**
- [ ] All CLI commands use terminal_ui for output
- [ ] Progress bars show during analysis (turn-by-turn)
- [ ] Onboarding panel prints after `deeprepo init`
- [ ] `deeprepo status` shows colored health indicators (✓ green, ⚠ yellow)
- [ ] Everything works without `rich` installed (plain text fallback)
- [ ] `-q` flag suppresses all progress output, only prints final result

---

## Multi-Agent Orchestration Protocol

This sprint uses the same CTO + Engineer pattern from the multi-vertical sprint, with Codex pushed harder based on 70% completion rate from last sprint.

### Agent Roles

**CTO (Claude Code):** Reviews, tests, produces task prompts. Does NOT implement. Reads SCRATCHPAD_CTO.md first, always.

**Engineer (Codex):** Implements according to task prompts. Runs tests. Updates SCRATCHPAD_ENGINEER.md.

### Codex Optimization Notes

Codex completed 70% of last sprint's issues with 50% context window remaining. This means:

1. **Push bigger issues.** Each issue in this sprint is a complete feature, not a refactoring step. Codex can handle multi-file creation + tests in a single task.

2. **Include full code examples in task prompts.** Codex performs best when the spec includes concrete signatures, data structures, and expected output. Every issue above has these.

3. **Reduce round-trips.** Instead of CTO sending 2-3 small tasks, send 1 large task with clear acceptance criteria. The Engineer handoff should be "here are 4 files I created and all tests pass" not "I started the file, what next?"

4. **Trust the context window.** With 50% context remaining, Codex can handle specs that include the full issue write-up plus the relevant existing code it needs to reference.

### Task Prompt Format (CTO → Engineer)

Same as previous sprint — see PRODUCT_DEVELOPMENT.md Part 5. Each issue above is already in the correct format.

### Scratchpad Files

```bash
cd ~/Desktop/Projects/deeprepo
touch SCRATCHPAD_CTO.md SCRATCHPAD_ENGINEER.md
```

### Sprint Execution Order

```
S1 (config manager) → S2 (context domain) → S3 (init + context commands) → S4 (log + status)
                                                                                    ↓
                                           S8 (terminal polish) ← S7 (new) ← S6 (teams) ← S5 (refresh)
```

S1-S4 is the critical path to a working `deeprepo init` + `deeprepo context`.
S5-S7 adds refresh, teams, and greenfield.
S8 is polish applied across all commands.

---

## Success Criteria for Sprint

After this sprint ships:

- [ ] `deeprepo init ./my-project` → generates `.deeprepo/` with project bible + cold-start prompt
- [ ] `deeprepo context --copy` → copies cold-start prompt to clipboard
- [ ] `deeprepo log "message"` → appends session entry, updates cold-start
- [ ] `deeprepo status` → shows context health
- [ ] `deeprepo refresh` → diff-aware update of context docs
- [ ] `deeprepo new` → interactive greenfield project creation with .deeprepo/ included
- [ ] `deeprepo teams` → lists available teams
- [ ] All commands work with `OPENROUTER_API_KEY` as the only required key
- [ ] Terminal output is professional (progress bars, colors, onboarding panel)
- [ ] Total cost per `init` on a medium project (50-100 files) is < $1.00
