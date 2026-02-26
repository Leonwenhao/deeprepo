# RL Training: Teaching Models to Delegate Exhaustively

DeepRepo includes a full reinforcement learning training pipeline built on [Prime Intellect](https://www.primeintellect.ai/)'s infrastructure. This document explains the methodology, baseline results, and how to reproduce or extend the training.

## The Problem: Models Satisfice

When an LLM orchestrates codebase analysis through DeepRepo's REPL loop, it has access to `llm_query()` and `llm_batch()` functions that dispatch focused analysis tasks to cheap sub-LLM workers. In practice, most models **satisfice** — they analyze a handful of files directly in-context and stop, rather than systematically delegating each file to a sub-LLM for thorough analysis.

We've observed this behavioral gap across model sizes:

| Model | Avg Dispatches | Coverage | Behavior |
|-------|---------------|----------|----------|
| Sonnet (untrained) | ~9 | ~20% | Satisfices — reads a few key files, stops early |
| Opus (untrained) | ~61 | ~95% | Explores exhaustively — dispatches nearly every file |
| Qwen3-8B (untrained) | ~3-5 | ~15% | Satisfices — prefers self-analysis over delegation |

The gap between Sonnet and Opus isn't a capability limitation — both models *can* write the code to dispatch more files. It's a **behavioral** difference: Opus keeps exploring while Sonnet decides it has "enough" information. This makes it an ideal target for RL training, where we reward the exploration behavior directly.

## The Solution: GRPO Training

We use [GRPO (Group Relative Policy Optimization)](https://arxiv.org/abs/2402.03300) to train models to delegate more exhaustively. GRPO generates multiple rollouts for the same input, scores them with a reward function, and updates the model to favor higher-scoring behaviors.

### Environment

Our training environment (`doloresresearch/deeprepo-orchestration`) is published on [Prime Intellect's Environments Hub](https://app.primeintellect.ai/dashboard/environments/doloresresearch/deeprepo-orchestration). It wraps DeepRepo's REPL loop as a `verifiers.MultiTurnEnv`:

**Dataset:** Pre-loaded codebases with planted security vulnerabilities, architectural issues, and code quality problems. Each codebase includes ground truth findings from expert (Opus-level) analysis.

**Harness:** Each episode is a multi-turn REPL session. The model receives file tree metadata (not file contents), writes Python code to explore the codebase, calls `llm_query()`/`llm_batch()` to dispatch analysis tasks, and iterates until it sets `answer["ready"] = True`.

**Reward Function:** Three-component reward targeting delegation exhaustiveness:

```
reward = coverage_score (0.5) + finding_quality (0.3) + efficiency (0.2)

coverage_score  = (unique_files_dispatched / total_files) * 0.5
finding_quality = fuzzy_recall(model_findings, ground_truth) * 0.3
efficiency      = turn_efficiency_curve(turns_used) * 0.2
```

Coverage is weighted highest because it directly measures delegation behavior — the more files the model dispatches to sub-LLMs, the higher the score.

### Training Configuration

```toml
# configs/rl/deeprepo-delegation.toml
model = "Qwen/Qwen3-30B-A3B-Instruct-2507"
max_steps = 100
batch_size = 128
rollouts_per_example = 8

[sampling]
max_tokens = 2048
temperature = 0.7

[[env]]
id = "doloresresearch/deeprepo-orchestration"
```

The Qwen3-30B-A3B model is a Mixture of Experts architecture with 30B total parameters but only 3B active at inference time, making it efficient to both train and deploy.

## Baseline Results

### Qwen3-8B (Untrained Baseline)

Evaluated with `prime eval run deeprepo-orchestration -m qwen/qwen3-8b -n 3 -r 2`:

| Metric | Value |
|--------|-------|
| Average Reward | 0.551 (std 0.176) |
| Reward Range | 0.200 — 0.729 |
| Average Turns | 3.67 (range 2-5) |
| Stop Condition | episode_done 100% (no errors) |

**Behavioral observations:** The model correctly identified real security vulnerabilities (SQL injection, weak MD5 hashing, missing input validation) but preferred self-analysis over delegation. It read files directly in the REPL namespace rather than dispatching them to sub-LLMs via `llm_query()`. The 0.2 outlier represents a rollout with zero delegation (coverage = 0). The reward variance (0.2 to 0.729) is ideal for GRPO training — the algorithm needs behavioral diversity to learn from.

### Training Results

*Training run in progress — results will be updated here.*

Run ID: `uo6bmz5849wujlwu8286j2r8`

## Reproducing the Training

### Prerequisites

- [Prime Intellect](https://app.primeintellect.ai) account (Hosted Training is free during Private Beta)
- `uv` package manager
- Prime CLI: `uv tool install prime && prime login`

### Steps

```bash
# Clone DeepRepo
git clone https://github.com/Leonwenhao/deeprepo.git
cd deeprepo

# Install dependencies including verifiers
uv sync

# Install the training environment locally
prime env install deeprepo-orchestration

# Run baseline eval
prime eval run deeprepo-orchestration -m qwen/qwen3-8b -n 3 -r 2

# View eval results
prime eval tui

# Start GRPO training (free during Private Beta)
prime rl start configs/rl/deeprepo-delegation.toml

# Monitor training
prime rl logs <RUN_ID> -f
```

### Custom Environments

To train on your own codebases, modify `environments/deeprepo_orchestration/prepare_dataset.py`:

```bash
# Generate dataset from a local codebase
python environments/deeprepo_orchestration/prepare_dataset.py /path/to/your/codebase

# Re-install the environment with updated dataset
prime env install deeprepo-orchestration
```

## Architecture

```
DeepRepo CLI/TUI (user-facing product)
        │
        ▼
RLM REPL Engine (domain-agnostic)
        │
        ├── Code Analysis Domain
        ├── Content Intelligence Domain  
        ├── Film/Screenplay Domain
        │
        ▼
verifiers Environment (training wrapper)
        │
        ├── Dataset: Pre-loaded codebases with ground truth
        ├── Harness: Multi-turn REPL with mocked sub-LLMs
        └── Rubric: Delegation coverage + finding quality + efficiency
        │
        ▼
Prime Intellect Hosted Training (GRPO)
        │
        ▼
Trained Model (improved delegation behavior)
        │
        ▼
Deploy back into DeepRepo as root orchestrator
```

## Related Resources

- [Prime Intellect Lab](https://www.primeintellect.ai/blog/lab) — The platform powering our training
- [Verifiers Library](https://github.com/PrimeIntellect-ai/verifiers) — Environment framework
- [GRPO Paper](https://arxiv.org/abs/2402.03300) — The training algorithm
- [DeepRepo Pitch Deck](./deeprepo_pitch_deck_V0.pdf) — Full company thesis
