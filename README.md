# deeprepo

Your AI tools forget everything between sessions. deeprepo gives them memory.

One command analyzes your project and generates a compressed context prompt that any AI coding tool can consume — architecture, patterns, conventions, and active development state. No more re-explaining your codebase every session.

## Quickstart

```bash
pip install deeprepo-cli
deeprepo init .
deeprepo context --copy   # paste into any AI tool
```

`init` runs a one-time analysis (~$0.50, takes 2-3 minutes). After that, `context` is instant — it reads local files, no API call needed.

## What it generates

```
.deeprepo/
├── config.yaml      # project configuration
├── PROJECT.md       # full project bible (architecture, patterns, conventions)
├── COLD_START.md    # compressed context prompt optimized for AI consumption
├── SESSION_LOG.md   # running development history
└── SCRATCHPAD.md    # working notes for multi-agent coordination
```

`PROJECT.md` is the complete analysis. `COLD_START.md` is the same content compressed to fit inside a context window — typically under 3,000 tokens. That's what `deeprepo context` outputs.

## Live proof

We ran `deeprepo init` on deeprepo itself. Cost: $0.63. Output: a 3,008-token cold-start prompt. A fresh Claude Code session immediately knew the architecture, file layout, and coding patterns — then implemented a new CLI feature without any re-explanation. The prompt paid for itself in the first interaction.

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

## Commands

```bash
# Core workflow
deeprepo init <path>              # Analyze project, generate .deeprepo/ context
deeprepo context [--copy]         # Output cold-start prompt (instant, no API)
deeprepo context --format cursor  # Write .cursorrules file
deeprepo refresh [--full]         # Diff-aware context update
deeprepo status                   # Context health dashboard

# Session tracking
deeprepo log "message"            # Record session activity
deeprepo log show                 # View recent sessions

# Advanced
deeprepo teams                    # List available agent teams
deeprepo new                      # Greenfield project scaffolding
deeprepo analyze <path>           # RLM codebase analysis (full report)
deeprepo baseline <path>          # Single-model comparison run
deeprepo compare <path>           # Run both, compare metrics
```

## Benchmarks

The RLM engine was benchmarked on FastAPI (47 files) — same codebase, same task, two approaches:

| Metric | Sonnet RLM | Opus Baseline |
|--------|:----------:|:-------------:|
| Total cost | $0.46 | $0.99 |
| Sub-LLM calls | 13 | N/A |
| Sub-LLM cost | $0.02 | N/A |
| Files covered | 47/47 (100%) | 42/47 (89%) |

The 5 files the baseline missed account for 74% of FastAPI's codebase by size — including the core FastAPI class, routing engine, and dependency injection system. The coverage gap widens with scale: the baseline dropped to 48% on a 289-file codebase while the RLM maintained 100%.

Honest caveat: for files both approaches can see, the Opus baseline produces more precise per-file findings. The RLM advantage is coverage breadth, not per-file depth.

Full data in [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md).

## Configuration

```bash
# Required: OpenRouter key for sub-LLM workers + alternative root models
export OPENROUTER_API_KEY=sk-or-...

# Optional: Anthropic key for Claude root models (falls back to OpenRouter)
export ANTHROPIC_API_KEY=sk-ant-...
```

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
- **PyPI publication** — `pip install deeprepo-cli` from the real package index

## License

MIT
