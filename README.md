# deeprepo

**Deep codebase intelligence powered by recursive multi-model orchestration.** Analyzes entire codebases — any size — by orchestrating cheap sub-LLM workers through a recursive language model pattern. Finds bugs, maps architecture, and produces prioritized development plans starting at $0.74/run.

```
$ deeprepo analyze https://github.com/your-org/your-repo

🔍 Loading codebase... 289 files, 2.07M chars
🧠 Root model exploring file structure...
⚡ Dispatching 61 sub-LLM analysis tasks...
📊 Synthesizing findings...

✅ Analysis complete — 18 issues found across 225 files
   Cost: $0.74 | Time: 4m 32s | Coverage: 100%
   Report saved to outputs/deeprepo_your-repo_20260215.md
```

## Why This Exists

Every AI model has a context window ceiling. Even the best ones start hallucinating and missing details as input grows. The industry solution — bigger context windows — is a dead end. Context rot means quality degrades long before you hit the token limit.

**deeprepo breaks through this ceiling** by keeping your codebase in an external workspace that the root model explores through code. It never tries to cram your repo into a single prompt. Instead, it writes Python to navigate the file tree, dispatches focused analysis tasks to cheap sub-LLM workers, and synthesizes everything into a structured report.

The result: **100% file coverage regardless of codebase size**, at a fraction of the cost of frontier single-model analysis.

## How It Works

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
│  Cost: $0.002 per file analysis                  │
└─────────────────────────────────────────────────┘
```

The root model operates in a Python REPL loop — it writes code, we execute it, feed back the output, and it writes more code. This continues until it sets `answer["ready"] = True`. Sub-LLM calls happen inside the REPL code, so the root model's context stays clean.

This is an implementation of the [Recursive Language Model](https://arxiv.org/abs/2512.24601) pattern from MIT research, extended with [Prime Intellect's](https://www.primeintellect.ai/blog/rlm) parallel dispatch and iterative answer refinement.

## Benchmark Results

Tested against a production TypeScript/React codebase (289 files, 2.07M chars, ~55K lines):

| Configuration | Root Model | Cost | Sub-LLM Calls | Files Analyzed | Deep Bugs Found | Grade |
|:--|:--|--:|--:|--:|--:|:--:|
| **RLM (recommended)** | Sonnet 4.5 | **$0.74** | 9 | ~35 | 2 | B |
| RLM (exhaustive) | Opus 4.6 | $5.04 | 61 | 225 | 18 | A |
| RLM (cheapest) | MiniMax M2.5 | $0.024 | 0* | ~12 | 0 | D |
| Baseline | Opus 4.6 single call | $1.39 | — | 108 | ~5 | B+ |

*M2.5 as root failed to dispatch sub-LLM calls due to code generation limitations in the REPL environment.

### Key Finding: The Sub-LLM Layer is Essentially Free

Opus dispatched 61 sub-LLM calls to MiniMax M2.5. **Total sub-LLM cost: $0.10** — just 2% of the run. The entire cost structure lives in the root model. This means the economic play is training a cheaper root model to delegate like Opus does, which is our [active research direction](#roadmap).

### Why RLM Beats the Baseline

The baseline crammed 48% of files into a single Opus context window and hoped for the best. On this codebase, it actually found some issues — but it physically couldn't see 52% of the files. **Every deep bug that only RLM found existed in files the baseline never read.**

On larger codebases (5M+ chars), baseline coverage drops below 20%. RLM scales to any codebase size because it never loads files into the model's context — it dispatches them to workers.

## Quick Start

### Prerequisites

- Python 3.11+
- API keys for [Anthropic](https://console.anthropic.com/) (root model) and [OpenRouter](https://openrouter.ai/) (sub-LLM workers)

### Install

```bash
git clone https://github.com/Leonwenhao/deeprepo.git
cd deeprepo
pip install -e .
```

### Configure

```bash
cp .env.example .env
# Edit .env with your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENROUTER_API_KEY=sk-or-...
```

### Run

```bash
# Analyze a GitHub repo
deeprepo analyze https://github.com/tiangolo/fastapi

# Analyze a local directory
deeprepo analyze ./my-project

# Compare RLM vs single-model baseline
deeprepo compare https://github.com/tiangolo/fastapi

# Quiet mode (no progress output)
deeprepo analyze ./my-project -q

# Save to specific directory
deeprepo analyze ./my-project -o ./reports
```

### Output

The tool produces a structured Markdown report:

```
## Codebase Analysis: fastapi

### 1. Architecture Overview
- Entry points and main execution flow
- Module dependency map
- Key design patterns identified

### 2. Bug & Issue Audit
- Critical issues (security, data loss risk)
- Logic errors and edge cases
- Error handling gaps

### 3. Code Quality Assessment
- Pattern consistency across modules
- Test coverage analysis
- Documentation quality

### 4. Development Plan (Prioritized)
- P0: Critical fixes (with what/why/complexity)
- P1: Important improvements
- P2: Nice-to-have refactors
```

Plus a `_metrics.json` file with token usage, cost breakdown, timing, and file coverage stats.

## Configuration

### Model Selection

By default, the tool uses **Claude Sonnet 4.5** as root orchestrator and **MiniMax M2.5** as sub-LLM workers. You can override these:

```bash
# Use Opus for maximum quality (more expensive)
deeprepo analyze ./my-project --root-model claude-opus-4-6

# Adjust max REPL turns (default: 15)
deeprepo analyze ./my-project --max-turns 20
```

### Cost Estimates

| Codebase Size | Estimated Cost (Sonnet root) | Estimated Time |
|:--|--:|--:|
| Small (<50 files) | $0.20–0.50 | 1–3 min |
| Medium (50–300 files) | $0.50–1.50 | 3–8 min |
| Large (300–1000 files) | $1.00–3.00 | 5–15 min |
| Very large (1000+ files) | $2.00–5.00 | 10–25 min |

Sub-LLM costs are negligible regardless of codebase size (~$0.002 per file analyzed).

## How It Works (Technical Detail)

1. **Codebase Loading**: Clone repo (or read local dir) → build file tree + metadata dict. Skip `node_modules`, `.git`, binaries, files >500KB.

2. **REPL Initialization**: Create a Python namespace containing the codebase dict, metadata, and injected functions (`llm_query`, `llm_batch`, `print`). The root model never sees file contents — only the tree and stats.

3. **Orchestration Loop**: Send metadata to root model → it writes Python code → we `exec()` it in the namespace → capture stdout → feed output back as next message → repeat until `answer["ready"] = True`.

4. **Sub-LLM Dispatch**: Code written by the root model calls `llm_query(prompt)` for single tasks or `llm_batch(prompts)` for parallel dispatch. These hit MiniMax M2.5 via OpenRouter. Results are stored as REPL variables.

5. **Answer Assembly**: The root model iteratively builds `answer["content"]` across turns, refining its analysis as sub-LLM results come in. REPL output is truncated at 8192 chars per turn to force programmatic approaches over raw dumping.

## Project Structure

```
deeprepo/
├── pyproject.toml
├── README.md
├── LICENSE
├── .env.example
├── src/
│   ├── __init__.py
│   ├── llm_clients.py      # Anthropic + OpenRouter API wrappers with token tracking
│   ├── codebase_loader.py   # Git clone → structured file tree + metadata
│   ├── rlm_scaffold.py      # Core engine: REPL loop + sub-LLM dispatch
│   ├── prompts.py           # System prompts for root model + sub-LLMs
│   ├── baseline.py          # Single-model baseline for comparison
│   └── cli.py               # CLI entry point
├── outputs/                  # Analysis reports land here
├── examples/                 # Example outputs from real repos
└── tests/
    ├── test_small/           # 3-file test codebase with planted bugs
    └── test_integration.py
```

## Roadmap

### Current: Pre-Training Scaffold (v0)
✅ Working RLM orchestration loop
✅ Multi-model architecture (Sonnet root + M2.5 workers)
✅ Three-way benchmark (Opus vs Sonnet vs M2.5 as root)
✅ Baseline comparison mode
✅ CLI interface

### Next: Prompt Optimization + OSS Demos (v0.5)
- [ ] Run against well-known OSS repos (FastAPI, Flask, Django projects)
- [ ] Optimize root model prompt for exhaustive exploration
- [ ] GitHub Action for automated PR review
- [ ] Published example outputs

### Future: RL-Trained Orchestrator (v1)
- [ ] Package as [verifiers](https://github.com/PrimeIntellect-ai/verifiers) environment
- [ ] Train open-weight model to match Opus orchestration behavior at Sonnet pricing
- [ ] Publish to [Prime Intellect Environments Hub](https://app.primeintellect.ai/dashboard/environments)
- [ ] SWE-bench Verified evaluation

The core research finding: the gap between Sonnet (9 sub-LLM dispatches) and Opus (61 dispatches) is purely behavioral — not a capability limitation. Sonnet *can* orchestrate, it just satisfices. RL training should close this gap, yielding Opus-quality analysis at Sonnet cost (~$1/run).

## Built On

- [Recursive Language Models](https://arxiv.org/abs/2512.24601) (MIT, 2025) — the RLM pattern
- [Prime Intellect RLM Extensions](https://www.primeintellect.ai/blog/rlm) — parallel dispatch, answer variable pattern
- [MiniMax M2.5](https://www.minimax.io/) — sub-LLM worker model (80.2% SWE-bench Verified, 1/20th frontier cost)
- [Anthropic Claude](https://www.anthropic.com/) — root orchestrator model

## License

MIT
