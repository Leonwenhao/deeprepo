# deeprepo

Your AI tools forget everything between sessions. deeprepo gives them memory.

Run `deeprepo` in any project directory and drop into an interactive session — slash commands for project infrastructure, natural language for generating context-rich prompts that copy straight to your clipboard. Paste into Claude Code, Codex, Cursor, or any AI tool. No more re-explaining your codebase every session.

## Quickstart

```bash
pip install deeprepo-cli
cd your-project/
deeprepo
```

The first time, deeprepo walks you through API key setup and project initialization. After that, you're in a persistent session:

```
╭──────────────────────────────────────────────────╮
│  deeprepo v0.2.0                                 │
│  Project: your-project                           │
│  Context: Fresh · 3,008 tokens · 23 files        │
│                                                  │
│  Type /help for commands or ask anything.        │
╰──────────────────────────────────────────────────╯
deeprepo> fix the broken WebSocket connection
OK: Copied prompt (4,200 tokens, 3 files) to clipboard
```

Type natural language and deeprepo assembles your project context + relevant files + your ask into a clipboard-ready prompt. Paste it into any AI coding tool.

## Install

```bash
pip install deeprepo-cli
```

Requires Python 3.11+. One dependency: an [OpenRouter](https://openrouter.ai/keys) API key for the initial project analysis (~$0.50 one-time cost).

## What it generates

```
.deeprepo/
├── config.yaml      # project configuration
├── PROJECT.md       # full project analysis (architecture, patterns, conventions)
├── COLD_START.md    # compressed context prompt optimized for AI consumption
├── SESSION_LOG.md   # running development history
└── SCRATCHPAD.md    # working notes for multi-agent coordination
```

`PROJECT.md` is the complete analysis. `COLD_START.md` is the same content compressed to fit inside a context window — typically under 3,000 tokens. That's what gets included in every prompt you generate.

## Interactive TUI

Running `deeprepo` with no arguments launches the interactive session:

**Slash commands** map to project infrastructure:

| Command | What it does |
|---------|-------------|
| `/init` | Analyze project and generate .deeprepo/ context |
| `/context` | Copy cold-start prompt to clipboard |
| `/context --format cursor` | Write .cursorrules file |
| `/status` | Show project context health |
| `/log add <message>` | Record development activity |
| `/refresh` | Diff-aware context update |
| `/help` | List all commands |

**Natural language** builds context-rich prompts:

```
deeprepo> add rate limiting to the API endpoints
OK: Copied prompt (5,100 tokens, 4 files) to clipboard
```

deeprepo reads your COLD_START.md, finds files matching your keywords, assembles everything into a structured prompt, and copies it to your clipboard. Paste into any AI tool.

**Keybindings:** Tab for autocomplete, Ctrl-L to clear, Ctrl-R to refresh context.

## CLI mode

Every command also works as a one-shot CLI call:

```bash
deeprepo init .                   # Analyze project, generate .deeprepo/
deeprepo context --copy           # Copy cold-start prompt to clipboard
deeprepo context --format cursor  # Write .cursorrules file
deeprepo refresh --full           # Full re-analysis
deeprepo status                   # Context health dashboard
deeprepo log "fixed auth bug"     # Record session activity
deeprepo tui /path/to/project     # Launch TUI for a specific path
```

## How it works

deeprepo uses a Recursive Language Model (RLM) pattern — a root LLM operates in a Python REPL loop, exploring your codebase and dispatching focused analysis tasks to cheap sub-LLM workers.

```
┌─────────────────────────────────────────────────┐
│  Root Orchestrator (Claude Sonnet 4.5)          │
│                                                  │
│  Sees: file tree, metadata, sizes               │
│  Does NOT see: actual file contents              │
│                                                  │
│  Writes Python → explores codebase → dispatches  │
│  analysis tasks → synthesizes findings           │
└──────────────────┬──────────────────────────────┘
                   │ llm_query() / llm_batch()
                   ▼
┌─────────────────────────────────────────────────┐
│  Sub-LLM Workers (MiniMax M2.5)                 │
│                                                  │
│  Each worker gets ONE focused task:              │
│  "Analyze auth.py for security issues"           │
│  "Map the data flow in this module"              │
│                                                  │
│  Cost: ~$0.002 per file analysis                 │
└─────────────────────────────────────────────────┘
```

The root model never sees raw file contents — it writes Python code to explore, dispatches individual files to cheap workers, and synthesizes findings across turns. All sub-LLM calls go through OpenRouter, so one API key gives you access to every model.

## Benchmarks

The RLM engine was benchmarked on FastAPI (47 files) — same codebase, same task, two approaches:

| Metric | Sonnet RLM | Opus Baseline |
|--------|:----------:|:-------------:|
| Total cost | $0.46 | $0.99 |
| Sub-LLM calls | 13 | N/A |
| Sub-LLM cost | $0.02 | N/A |
| Files covered | 47/47 (100%) | 42/47 (89%) |

The 5 files the baseline missed account for 74% of FastAPI's codebase by size — including the core FastAPI class, routing engine, and dependency injection system. The coverage gap widens with scale: the baseline dropped to 48% on a 289-file codebase while the RLM maintained 100%.

Full data in [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md).

## Configuration

```bash
# Required: OpenRouter key for sub-LLM workers + alternative root models
export OPENROUTER_API_KEY=sk-or-...

# Optional: Anthropic key for Claude root models (falls back to OpenRouter)
export ANTHROPIC_API_KEY=sk-ant-...
```

Or let deeprepo set it up for you — the interactive onboarding saves your key to `~/.deeprepo/config.yaml` on first run.

After `deeprepo init`, project settings live in `.deeprepo/config.yaml`:

```yaml
root_model: anthropic/claude-sonnet-4-5
sub_model: minimax/minimax-m2.5
context_max_tokens: 3000
include_tech_debt: true
```

Short aliases work on the CLI: `--root-model sonnet`, `--root-model opus`, `--sub-model minimax`.

## Roadmap

- **Teams** — named multi-agent compositions for different analysis workflows
- **More `--format` targets** — Windsurf, Aider, generic system prompt
- **Embeddings-based file matching** — smarter relevant file detection in prompt builder

## License

MIT
