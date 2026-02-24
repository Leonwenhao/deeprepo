# deeprepo

**AI project memory for every coding tool.** Analyze your project once, paste context anywhere. No more re-explaining your architecture to Claude, Cursor, Codex, or ChatGPT at the start of every session.

```
$ pipx install deeprepo-cli
$ deeprepo
```

DeepRepo analyzes your codebase using recursive multi-model orchestration, then generates a `.deeprepo/` directory with everything an AI tool needs to understand your project. Run `deeprepo context --copy`, paste into any tool, and the cold start tax disappears.

**Cost:** $0.43–$0.95 per project analysis. The sub-LLM layer is essentially free (~2% of total cost).

## How It Works

```
pipx install deeprepo-cli    # Install once
deeprepo                      # Launch interactive TUI
/init                         # Analyze your project → generates .deeprepo/
/context                      # Copy project context to clipboard
                              # Paste into any AI tool. Done.
```

DeepRepo launches into an interactive shell with guided onboarding. First-time users are walked through API key setup, project initialization, and their first context generation — no README required.

### What `.deeprepo/` Contains

When you run `/init`, DeepRepo generates a project memory directory:

| File | Purpose |
|------|---------|
| `PROJECT.md` | Full project bible — architecture, patterns, decisions, dependencies |
| `COLD_START.md` | Compressed context prompt optimized for pasting into AI tools |
| `SESSION_LOG.md` | Running log of what's happened across sessions |
| `SCRATCHPAD.md` | Working notes for multi-agent coordination |
| `config.yaml` | Project settings, model preferences, team configuration |

The `COLD_START.md` is the key artifact. It's a compressed representation of your entire project that fits within AI tool context windows and gives any model instant project awareness.

## The Interactive TUI

Run `deeprepo` with no arguments to enter the interactive shell:

```
 ██████╗ ███████╗███████╗██████╗ ██████╗ ███████╗██████╗  ██████╗
 ██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔═══██╗
 ██║  ██║█████╗  █████╗  ██████╔╝██████╔╝█████╗  ██████╔╝██║   ██║
 ██║  ██║██╔══╝  ██╔══╝  ██╔═══╝ ██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║
 ██████╔╝███████╗███████╗██║     ██║  ██║███████╗██║     ╚██████╔╝
 ╚═════╝ ╚══════╝╚══════╝╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝

deeprepo>
```

### Slash Commands

| Command | What It Does |
|---------|-------------|
| `/init` | Analyze your project and generate `.deeprepo/` context |
| `/context` | Copy project context to clipboard |
| `/status` | Check context freshness and project health |
| `/log` | View session history |
| `/config` | Show current configuration |
| `/help` | List all available commands |
| `/quit` | Exit the shell |

Natural language works too — type questions or instructions and DeepRepo routes them through the RLM engine. The TUI is the primary interface, but every command also works as a CLI flag for scripting and CI.

## Why This Exists

Every AI coding tool starts every session from zero. They don't know your architecture, your conventions, your decisions. You re-explain the same context every time.

DeepRepo generates a persistent project memory that any tool can consume. Analyze once, paste anywhere — Claude Code, Cursor, Codex, ChatGPT, or any tool that accepts text context.

DeepRepo sits in a unique position between three categories:

- **Multi-agent frameworks** (CrewAI, MetaGPT) remove the human — DeepRepo keeps you in the loop
- **AI coding agents** (Claude Code, Codex, Cursor) have zero awareness of each other — DeepRepo is the coordination layer
- **Single-tool memory** (CLAUDE.md) is locked to one tool — DeepRepo is memory for your whole workflow

## Install

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/) (for the root orchestrator model)
- An [OpenRouter API key](https://openrouter.ai/) (for sub-LLM workers)

### macOS (recommended)

```bash
pipx install deeprepo-cli
```

### pip

```bash
pip install deeprepo-cli
```

Then run `deeprepo` and follow the interactive onboarding.

### CLI Usage (non-interactive)

```bash
deeprepo init .              # Generate project memory
deeprepo context --copy      # Copy context to clipboard
deeprepo status              # Check context health
deeprepo new                 # Scaffold .deeprepo/ for a greenfield project
```

## Domain-Agnostic Architecture

DeepRepo isn't just for code. The RLM engine supports pluggable analysis domains through configurable `DomainConfig` dataclasses:

| Domain | Use Case |
|--------|----------|
| **Code** | Codebase architecture, patterns, dependencies, tech debt |
| **Content** | Marketing documents, content libraries, editorial workflows |
| **Context** | General project documentation and knowledge bases |

Same engine, any document corpus. New domains are added by defining a config — no engine changes required.

## How the Engine Works

Under the hood, DeepRepo implements the [Recursive Language Model](https://arxiv.org/abs/2512.24601) pattern. A root LLM (Claude Sonnet 4.6) writes Python in a REPL loop, exploring your codebase programmatically rather than trying to cram it into a single context window. When it needs to analyze specific files, it dispatches focused tasks to cheap sub-LLM workers (MiniMax M2.5 via OpenRouter).

```
┌─────────────────────────────────────────────────┐
│  Root Orchestrator (Claude Sonnet 4.6)          │
│                                                  │
│  Sees: file tree, metadata, sizes               │
│  Does NOT see: actual file contents              │
│                                                  │
│  Writes Python → explores codebase → dispatches  │
│  analysis tasks → synthesizes into PROJECT.md    │
└──────────────────┬──────────────────────────────┘
                   │ llm_query() / llm_batch()
                   ▼
┌─────────────────────────────────────────────────┐
│  Sub-LLM Workers (MiniMax M2.5 via OpenRouter)  │
│                                                  │
│  Focused tasks: "summarize auth flow in this     │
│  module", "list exports", "describe data flow"   │
│                                                  │
│  Cost: ~$0.002 per file analysis                 │
└─────────────────────────────────────────────────┘
```

The root model never loads your entire codebase into its context. It navigates programmatically and delegates, which means it scales to any codebase size without hitting context window limits.

### Engine Performance

Tested on real projects:

| Project | Type | Turns | Sub-LLM Calls | Cost | Output |
|---------|------|-------|---------------|------|--------|
| DeepRepo | Python CLI + TUI | 10 | 9 | $0.95 | Full project bible |
| PokerPot | TypeScript/Next.js/Solidity | 9 | 6 | $0.43 | 462-line architecture + security analysis |

### Benchmark: RLM vs Single-Model

From our research phase, tested against a 289-file TypeScript/React codebase (2.07M chars):

| Configuration | Root Model | Cost | Sub-LLM Calls | Files Analyzed | Grade |
|---------------|-----------|------|---------------|----------------|-------|
| **RLM (recommended)** | Sonnet | **$0.74** | 9 | ~35 | B |
| RLM (exhaustive) | Opus | $5.04 | 61 | 225 | A |
| Baseline (single call) | Opus | $1.39 | — | 108 | B+ |

The baseline crammed 48% of files into a single context window. Every deep finding that only the RLM discovered existed in files the baseline couldn't see. On larger codebases, baseline coverage drops below 20% — the RLM scales regardless of size.

## Configuration

### Model Selection

Default configuration uses **Claude Sonnet 4.6** as root orchestrator and **MiniMax M2.5** as sub-LLM workers. Override via CLI flags:

```bash
# Use Opus for maximum quality (more expensive)
deeprepo init . --root-model claude-opus-4-6

# Adjust max REPL turns (default: 20)
deeprepo init . --max-turns 30
```

### Teams

Named agent compositions let you define reusable analysis configurations — which root model, which workers, what analysis focus, what output format. Create a team once, invoke it by name.

### Cost Estimates

| Codebase Size | Estimate | Estimated Time |
|--------------|---------------|----------------|
| Small (<50 files) | $0.20–0.50 | 1–3 min |
| Medium (50–300 files) | $0.50–1.50 | 3–8 min |
| Large (300+ files) | $1.00–3.00 | 5–15 min |

Sub-LLM costs are negligible regardless of codebase size.

## Built On

- [Recursive Language Models](https://arxiv.org/abs/2512.24601) (MIT, 2025) — the RLM pattern
- [Prime Intellect RLM Extensions](https://www.primeintellect.ai/blog/rlm) — parallel dispatch, answer variable pattern
- [MiniMax M2.5](https://www.minimax.io/) — sub-LLM worker model
- [Anthropic Claude](https://www.anthropic.com/) — root orchestrator model

## Contributing

DeepRepo is open source under the MIT license. Issues and PRs welcome.

```bash
git clone https://github.com/Leonwenhao/deeprepo.git
cd deeprepo
pip install -e ".[dev]"
pytest
```

## License

MIT
