# deeprepo — deep codebase analysis via recursive LLM orchestration

Context windows can't fit large codebases — and even when they can, quality degrades as input grows. deeprepo works around this with a root LLM that operates in a Python REPL loop, exploring your codebase as structured data and dispatching focused analysis tasks to cheap sub-LLM workers, rather than trying to cram everything into a single prompt. On FastAPI (47 files), a $0.46 Sonnet RLM achieved 100% file coverage where a $0.99 Opus single-call baseline reached only 89% — missing FastAPI's core application class, routing engine, and dependency injection system entirely. [Full benchmarks →](BENCHMARK_RESULTS.md)

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
│  Cost: ~$0.002 per file analysis                 │
└─────────────────────────────────────────────────┘
```

The root model writes code, we execute it, feed back the output, and it writes more code — looping until it sets `answer["ready"] = True`. Sub-LLM calls happen inside the REPL code, so the root model's context stays clean. This implements the [Recursive Language Model](https://arxiv.org/abs/2512.24601) pattern from MIT research, extended with [Prime Intellect's](https://www.primeintellect.ai/blog/rlm) parallel dispatch and iterative answer refinement.

## Results

Benchmarked across three codebases: FastAPI (47 files), Pydantic (105 files), and Jianghu V3 (289 files). The FastAPI head-to-head comparison is the cleanest test — same codebase, same task, two approaches:

| Metric | Sonnet RLM | Opus Baseline |
|--------|:----------:|:-------------:|
| Total cost | $0.46 | $0.99 |
| Sub-LLM calls | 13 | N/A |
| Sub-LLM cost | $0.02 | N/A |
| Files covered | 47/47 (100%) | 42/47 (89%) |

The 5 files the baseline excluded account for 74% of FastAPI's codebase by character count — including `applications.py` (the core FastAPI class), `routing.py` (the routing engine, which alone exceeds the baseline's entire prompt budget), and the dependency injection system. The sub-LLM worker layer cost only $0.02 for the entire run. The coverage advantage grows with codebase size: the baseline went from 89% on FastAPI's 47 files down to 48% on Jianghu V3's 289 files, while the RLM maintained 100% in both cases.

One honest caveat: for files both approaches can see, the Opus baseline produces more precise per-file findings with direct code-level citations. The RLM advantage is coverage breadth, not per-file depth.

Full data — including the Pydantic standalone run and Jianghu V3 three-way root model comparison — is in [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md).

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

Use `python -m deeprepo.cli` or the `deeprepo` entry point after `pip install -e .`.

```bash
# Analyze a GitHub repo
python -m deeprepo.cli analyze https://github.com/tiangolo/fastapi

# Analyze a local directory
python -m deeprepo.cli analyze ./my-project

# Run single-model baseline for comparison
python -m deeprepo.cli baseline ./my-project

# Compare RLM vs baseline (split-model: Sonnet RLM vs Opus baseline)
python -m deeprepo.cli compare https://github.com/tiangolo/fastapi --baseline-model opus

# Quiet mode (no progress output)
python -m deeprepo.cli analyze ./my-project -q

# Save to specific directory
python -m deeprepo.cli analyze ./my-project -o ./reports
```

### Output

The tool produces a structured Markdown report covering architecture overview, bug and issue audit, code quality assessment, and a prioritized development plan. A `_metrics.json` file with token usage, cost breakdown, timing, and file coverage stats is saved alongside the report.

## Configuration

### Model Selection

By default, the tool uses **Claude Sonnet 4.5** (`claude-sonnet-4-5-20250929`) as root orchestrator and **MiniMax M2.5** as sub-LLM workers. The `--root-model` flag accepts short aliases (`sonnet`, `opus`, `minimax`) or full model strings:

```bash
# Use Opus for maximum quality (more expensive)
python -m deeprepo.cli analyze ./my-project --root-model opus

# Use a specific model string directly
python -m deeprepo.cli analyze ./my-project --root-model claude-opus-4-6

# Adjust max REPL turns (default: 15)
python -m deeprepo.cli analyze ./my-project --max-turns 20
```

### Cost Estimates

| Codebase Size | Estimated Cost (Sonnet root) | Estimated Time |
|:--|--:|--:|
| Small (<50 files) | $0.20–0.50 | 1–3 min |
| Medium (50–300 files) | $0.50–1.50 | 3–8 min |
| Large (300–1000 files) | $1.00–3.00 | 5–15 min |
| Very large (1000+ files) | $2.00–5.00 | 10–25 min |

Sub-LLM costs are negligible regardless of codebase size (~$0.002 per file analyzed). Estimates for codebases above 300 files are extrapolated from observed scaling trends, not direct measurements.

For implementation details, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Project Structure

```
deeprepo/
├── pyproject.toml
├── README.md
├── LICENSE
├── .env.example
├── deeprepo/
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

## What's Next

- **Re-export scope awareness** — the RLM currently can't distinguish project code from upstream re-exports (e.g., Starlette middleware in FastAPI), leading to misattributed findings.
- **SWE-bench Verified migration** — adapting output format from markdown reports to git diffs/patches for industry-standard evaluation.
- **RL training** — closing the Sonnet-Opus behavioral gap (Sonnet satisfices at 9 dispatches vs Opus's 61) through reinforcement learning on delegation behavior.

## Built On

- [Recursive Language Models](https://arxiv.org/abs/2512.24601) (MIT, 2025) — the RLM pattern
- [Prime Intellect RLM Extensions](https://www.primeintellect.ai/blog/rlm) — parallel dispatch, answer variable pattern
- [MiniMax M2.5](https://www.minimax.io/) — sub-LLM worker model (80.2% SWE-bench Verified, 1/20th frontier cost)
- [Anthropic Claude](https://www.anthropic.com/) — root orchestrator model

## License

MIT
