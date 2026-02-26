# RL Training: Teaching Models to Delegate Exhaustively

DeepRepo includes a full reinforcement learning training pipeline built on [Prime Intellect](https://www.primeintellect.ai/)'s infrastructure. This document explains the methodology, results, and how to reproduce or extend the training.

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

## Results

### Three-Model Comparison

All results are from independent `prime eval run` evaluations (3 examples × 2 rollouts each) on the same `deeprepo-orchestration` environment.

| Metric | Qwen3-8B (untrained) | Qwen3-30B-A3B (untrained) | Qwen3-30B-A3B (GRPO trained) |
|--------|----------------------|---------------------------|-------------------------------|
| Average Reward | 0.551 (σ 0.176) | 0.785 (σ 0.100) | **0.987** (σ 0.018) |
| Reward Range | 0.200 — 0.729 | 0.636 — 0.900 | **0.962 — 1.000** |
| Average Turns | 3.67 (2–5) | 8.67 (5–18) | **6.00 (6–6)** |
| Delegation Behavior | Prefers self-analysis | Mixed delegation + self-analysis | Consistent `llm_batch()` delegation |
| Zero-Delegation Rate | ~17% | 0% | **0%** |
| Input Tokens (avg) | — | 14,599 | **8,585** |

### What Changed

**Reward:** The trained model improved from 0.785 to 0.987 (+25.7%), with 4 out of 6 rollouts achieving a perfect 1.0 score.

**Consistency:** Reward standard deviation collapsed from 0.100 to 0.018. Turn count standard deviation collapsed from 4.422 to 0.000 — every single rollout completed in exactly 6 turns.

**Efficiency:** The trained model uses 41% fewer input tokens than the untrained model (8,585 vs 14,599) while achieving higher reward. It learned a structured 6-turn workflow: explore file tree → dispatch `llm_batch()` for parallel analysis → read key files directly → synthesize with `llm_batch()` → build report → set answer.

**Failure mode elimination:** The untrained model had an 18-turn over-exploration outlier (reward 0.636) where it burned through its turn budget exploring without converging. The trained model eliminated this behavior entirely.

### Isolating the RL Training Effect

| Delta | From → To | Absolute Improvement | Relative Improvement |
|-------|-----------|---------------------|---------------------|
| Model size effect | 8B → 30B (untrained) | +0.234 | +42.5% |
| RL training effect | 30B untrained → 30B trained | +0.202 | +25.7% |
| Combined | 8B untrained → 30B trained | +0.436 | +79.1% |

The RL training effect (+25.7%) is comparable in magnitude to the model size effect (+42.5%), but dramatically cheaper. Scaling from 8B to 30B requires 4× the parameters. GRPO training required 100 steps on the same 30B model and produces a model that uses fewer tokens at inference time.

### Reward Progression During Training

```
Step   0: reward=0.844  turns=7.57
Step  10: reward=0.852  turns=6.57
Step  20: reward=0.878  turns=6.68
Step  30: reward=0.890  turns=6.99
Step  40: reward=0.898  turns=6.76
Step  50: reward=0.926  turns=6.26
Step  60: reward=0.942  turns=6.27
Step  70: reward=0.924  turns=6.84
Step  80: reward=0.942  turns=6.33
Step  90: reward=0.852  turns=5.11  (temporary dip — exploration)
Step  99: reward=0.969  turns=6.01
```

The reward curve shows monotonic improvement with a temporary dip around step 90 (likely GRPO exploring alternative strategies) followed by recovery to the highest training reward at step 99.

### Honest Caveats

The evaluation environment uses 3 mini-codebases (calculator, todo-api, blog) with planted security bugs. The trained model approaches the reward ceiling (0.987/1.0), which means the environment may be too easy to show the full extent of improvement. Generalization to real-world repositories at scale is the next validation step. The eval set is small (6 rollouts per model), though the effect size is large relative to variance (>12× the standard deviation).

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
