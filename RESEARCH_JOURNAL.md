# deeprepo — Research Journal

**Author**: Leon
**Started**: February 14, 2026
**Status**: V0 experimentation complete, pre-training phase

---

## What This Is

A running journal of key findings from building and benchmarking a Recursive Language Model (RLM) scaffold for codebase analysis. This project uses the RLM pattern from MIT research (arXiv:2512.24601) and Prime Intellect's extensions to orchestrate multi-model code analysis — a root LLM writes Python in a REPL loop, dispatching focused tasks to cheaper sub-LLM workers.

The endgame is training a model via reinforcement learning to natively operate as an RLM orchestrator. This document captures what I've learned along the way. It will be refactored into a publishable Substack piece alongside the eventual launch.

---

## Part 1: V0 Experimentation — The Three-Way Comparison

### The Setup

I built a standalone RLM scaffold (not using Prime Intellect's RLMEnv, which now requires their proprietary sandbox infrastructure) and benchmarked three root model configurations against the same codebase — my Jianghu V3 RPG project (289 files, 2.07M chars, ~55K lines of TypeScript/React).

All three RLM runs used MiniMax M2.5 via OpenRouter as the sub-LLM worker. The only variable was the root orchestrator model.

| Configuration | Root Model | Sub-LLM | Root Pricing |
|--------------|-----------|---------|-------------|
| V0.0 | Claude Opus 4.6 | MiniMax M2.5 | $15/$75 per M tokens |
| V0.2 | Claude Sonnet 4.5 | MiniMax M2.5 | $3/$15 per M tokens |
| V0.3 | MiniMax M2.5 | MiniMax M2.5 | $0.20/$1.10 per M tokens |
| Baseline | Claude Opus 4.6 (single call, no REPL) | None | $15/$75 per M tokens |

### The Results at a Glance

| Metric | M2.5 Root | Sonnet Root | Opus Root | Baseline |
|--------|:---------:|:-----------:|:---------:|:--------:|
| Cost | $0.024 | $0.74 | $5.04 | $1.39 |
| Sub-LLM calls dispatched | 0 | 9 | 61 | N/A |
| Files analyzed via sub-LLM | 0 | ~35 | 225 | 108 (direct) |
| Unique deep bugs found | 0 | 2 | 18 | ~5 |
| Analysis quality | D | B | A | B+ |

---

### Key Finding #1: The Sub-LLM Layer is Essentially Free

This is the most important discovery from V0.

Opus dispatched 61 sub-LLM calls to MiniMax M2.5. Total sub-LLM cost: **$0.10**. That's 2% of the total run cost. Sonnet dispatched 9 calls for $0.015. Even a hypothetical 100-call run would cost ~$0.16 in sub-LLM fees.

The entire cost structure of an RLM system lives in the root model. The workers are practically free.

**Why this matters:** The conventional intuition is that more LLM calls = more cost, so you should minimize calls. In an RLM architecture with asymmetric pricing (expensive root, cheap workers), the opposite is true. The root model should delegate as aggressively as possible. Every task it tries to do itself costs 50-75x more than handing it to a worker.

**The analogy:** A CEO with access to unlimited free analysts. The optimal strategy is to delegate everything and focus purely on synthesis and decision-making. Opus behaved this way instinctively. Sonnet and M2.5 didn't.

**Projected economics at scale:**

| Sub-LLM Calls | Sub-LLM Cost | Root Cost (Sonnet) | Total | Sub as % |
|:-------------:|:------------:|:------------------:|:-----:|:--------:|
| 9 (actual) | $0.015 | $0.72 | $0.74 | 2% |
| 61 (Opus-level) | ~$0.10 | ~$0.90 | ~$1.00 | 10% |
| 100 | ~$0.16 | ~$1.05 | ~$1.21 | 13% |

Even tripling sub-LLM usage barely moves the total cost needle. The optimization target is clear: make the root model dispatch more, not less.

---

### Key Finding #2: Quality Scales Linearly with Delegation

The correlation between sub-LLM dispatches and analysis quality is almost perfect.

Opus dispatched 61 calls → 18 unique deep bugs found. Sonnet dispatched 9 → 2 unique deep bugs. M2.5 dispatched 0 → 0 unique deep bugs.

Every deep architectural bug that only Opus found (Zustand race conditions, cache mutation, IDB memory leaks, non-atomic state restoration) had the same root cause for why other models missed it: **the file was never dispatched to a sub-LLM for analysis.**

The bugs aren't hard to find. MiniMax M2.5 as a *worker* is perfectly capable of identifying them when given focused, single-file prompts. The bottleneck is the root model's willingness to actually send the files for analysis.

**What this means for training:** The quality problem reduces to a quantity problem. I don't need to train a better code analyst — M2.5 handles that at $0.002 per file. I need to train a better *delegator*. The root model's job is strategy, coverage, and synthesis. The more it delegates, the better the output.

---

### Key Finding #3: Three Distinct Capability Tiers Exist for RLM Orchestration

The three root models don't sit on a smooth gradient. They fall into clean tiers with sharp capability boundaries.

**Tier 1 — Cannot orchestrate (M2.5 as root)**

M2.5 failed at the mechanical level. It attempted 5 `llm_batch()` calls — all crashed with the same `SyntaxError` (f-strings with triple quotes inside `exec()`). The model hit this identical error 17 times across 3 turns and never adapted. It eventually produced an analysis by reading ~12 files directly via `codebase[]`, but found nothing that the other models didn't find with more specificity.

The critical failure: **zero in-context learning from execution errors.** The RLM pattern requires a root model that can adapt its code when something breaks. M2.5 kept writing the same broken pattern turn after turn. This isn't a reasoning limitation — it's a code generation limitation in constrained execution environments (specifically, `exec()` with shared namespaces).

**Tier 2 — Can orchestrate, won't explore (Sonnet as root)**

Sonnet is mechanically competent. It wrote working `llm_batch()` calls, correctly parsed sub-LLM results, used the REPL environment properly. No issues with `exec()` syntax. It's a functional RLM orchestrator.

But it stopped after 9 sub-LLM dispatches when it could have done 60+. It set `answer["ready"]` after examining a fraction of the codebase. This is satisficing — producing a plausible answer with minimum effort rather than being thorough.

Sonnet's problem is purely behavioral, not mechanical. It knows how to dispatch more calls. It chooses not to.

**Tier 3 — Orchestrates exhaustively (Opus as root)**

Opus dispatched 61 sub-LLM calls across 5 systematic batches, covering every file group in the codebase. It continued working through turn 4 before finalizing on turn 5. Its exploration strategy was methodical: entry points first, then stores, then game logic, then components, then infrastructure.

This is the target behavior for training.

**The implication:** There are two distinct gaps to close. The gap from Tier 1 to Tier 2 (M2.5 → Sonnet) requires solving code generation reliability in constrained environments — a hard problem. The gap from Tier 2 to Tier 3 (Sonnet → Opus) requires changing a behavioral policy from satisficing to exhaustive exploration — a well-defined RL training objective. The second gap is far more tractable.

---

### Key Finding #4: The Training Target is Sonnet, Not M2.5

The economics and capability analysis point clearly to Sonnet as the model to train.

**The cost math:**

A trained Sonnet that dispatches Opus-level sub-LLM calls (60+) would cost approximately $1.00 per analysis run. That's a **5x cost reduction** from Opus ($5.04) with potentially equivalent quality — since the sub-LLM layer (which does the actual file analysis) is identical.

Training M2.5 to serve as root would require first solving its code generation failures in `exec()` environments, then its inability to learn from errors within a session, and *then* training it to be a thorough delegator. That's three separate training objectives stacked on top of each other, versus Sonnet's single objective (dispatch more).

**The behavioral gap is specific and measurable:**

| Behavior | Sonnet (current) | Opus (target) | Gap |
|----------|:----------------:|:-------------:|:---:|
| Sub-LLM calls dispatched | 9 | 61 | 6.8x |
| File groups covered | 2 batches | 5 batches | 2.5x |
| Turns with active sub-LLM work | 2 of 4 | 4 of 5 | 2x |
| Answer finalized after | Turn 2 sub-LLM work | Turn 4 sub-LLM work | 2 turns early |
| Unique deep bugs | 2 | 18 | 9x |

Every item in this table is a trainable behavior with a clear reward signal. RL training should penalize early finalization and reward coverage, batch usage, and issue discovery.

**The architecture going forward:**

Trained Sonnet 4.5 as root orchestrator + untrained MiniMax M2.5 as sub-LLM workers. The training optimizes the orchestrator's delegation behavior while the worker stays as-is — already proven, already cheap.

---

### Key Finding #5: Prompt Engineering Has a Ceiling, but It's Worth Testing First

The three-way comparison suggests an intermediate experiment before training: updating the root system prompt to explicitly mandate exhaustive file coverage before allowing `answer["ready"] = True`.

If a prompt tweak pushes Sonnet from 9 dispatches to 40+, that's a meaningful improvement at zero training cost. But prompt-based behavior changes are inherently brittle — they work sometimes, break under different conditions, and don't generalize. The MIT paper found that the same RLM prompt doesn't work across models, and even per-model tuned prompts produce inconsistent behavior.

RL training makes thorough delegation *intrinsic* to the model's policy. The model doesn't dispatch more because the prompt says to — it dispatches more because its reward function optimized for coverage and issue discovery. That's the difference between telling someone to be thorough and training someone to be thorough.

The prompt experiment establishes a pre-training ceiling. The delta between prompt-optimized Sonnet and RL-trained Sonnet becomes the measurable value of the training run.

---

### What Comes Next

1. **Migrate evaluation to industry benchmarks.** Jianghu V3 served its purpose for V0 prototyping, but training and publishable results need standard benchmarks — likely SWE-bench Verified, which is the metric the field recognizes for code analysis tasks.

2. **Design the reward function.** The behavioral gap table above maps directly to reward signal components: positive reward for file coverage, batch utilization, and validated issue detection; negative reward for early finalization and redundant dispatches.

3. **Set up Prime Intellect training environment.** Package the RLM scaffold as a verifiers-compatible environment. The V0 codebase already implements the core `llm_query`/`llm_batch`/`answer` interface — adaptation to their framework should be straightforward.

4. **Run the training.** Train Sonnet 4.5 on Prime Intellect's prime-rl stack, using the behavioral specification from this document as the optimization target.

5. **Benchmark trained model.** Compare trained Sonnet against all three untrained configurations. The target: Opus-quality analysis at Sonnet pricing (~$1.00 per run).

---

*Last updated: February 14, 2026*
*Next update: Post SWE-bench migration and reward function design*
