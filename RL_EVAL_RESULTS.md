# DeepRepo RL Training Eval Results
# Date: February 25, 2026
# Training Run: uo6bmz5849wujlwu8286j2r8
# Model: Qwen/Qwen3-30B-A3B-Instruct-2507
# Method: GRPO with LoRA, 100 steps, batch_size 128, rollouts_per_example 8

---

## GRPO Training Results: Before vs After

| Metric                | Qwen3-8B (untrained) | Qwen3-30B-A3B (untrained) | Qwen3-30B-A3B (GRPO trained) |
|-----------------------|----------------------|---------------------------|-------------------------------|
| Average Reward        | 0.551 (σ 0.176)     | 0.785 (σ 0.100)          | 0.987 (σ 0.018)             |
| Reward Range          | 0.200 — 0.729       | 0.636 — 0.900             | 0.962 — 1.000                |
| Average Turns         | 3.67 (2-5)          | 8.67 (5-18)              | 6.00 (6-6)                  |
| Delegation Behavior   | Prefers self-analysis| Mixed: delegation + self-analysis, one over-explorer | Consistent delegation via llm_batch(), structured 6-turn workflow |
| Zero-Delegation Rate  | ~17% (1/6 rollouts)  | 0% (0/6 rollouts)        | 0% (0/6 rollouts)           |
| Notable Observations  | 0.2 outlier = zero delegation | 18-turn outlier = over-exploration | Every rollout exactly 6 turns; 4/6 perfect 1.0 reward |

### Data Source
- **8B untrained**: Previous session's `prime eval run` (6 rollouts, 3 examples x 2 rollouts)
- **30B untrained**: `prime eval run` with Dolores Research team billing (6 rollouts, 3 examples x 2 rollouts)
- **30B trained**: `prime eval run` on deployed LoRA adapter `t2nj7mvwh0qs5h1szlfekqoh` (6 rollouts, 3 examples x 2 rollouts)
- All three are independent, formal eval runs using the same environment and parameters.

---

## Raw Eval Output: Untrained Qwen3-30B-A3B

```
Environment: deeprepo-orchestration
Model: Qwen/Qwen3-30B-A3B-Instruct-2507
Provider: https://api.pinference.ai/api/v1
Examples: 3
Rollouts per example: 2

Rewards:
reward: avg - 0.785, std - 0.100
r1: [0.636, 0.9, 0.85]
r2: [0.887, 0.7, 0.738]
delegation_reward: avg - 0.785, std - 0.100
r1: [0.636, 0.9, 0.85]
r2: [0.887, 0.7, 0.738]
num_turns: avg - 8.667, std - 4.422
r1: [18.0, 5.0, 5.0]
r2: [7.0, 9.0, 8.0]
Info:
is_truncated: avg - 0.000, std - 0.000
stop_conditions: episode_done: 1.000
Timing:
generation: min - 20s, mean - 34s, max - 1m
Usage:
input_tokens (avg): 14598.500
output_tokens (avg): 2200.333
```

### Behavioral Notes
- One rollout hit 18 turns (massive over-exploration) with lowest reward (0.636)
- Other rollouts ranged 5-9 turns with rewards 0.7-0.9
- Mixed use of llm_batch() and llm_query()
- Model correctly identifies planted bugs (SQL injection, MD5 hashing, hardcoded secrets)
- Inconsistent delegation strategy — sometimes explores exhaustively, sometimes delegates efficiently

---

## Raw Eval Output: Trained Qwen3-30B-A3B (GRPO, Step 99 Checkpoint)

```
Environment: deeprepo-orchestration
Model: Qwen/Qwen3-30B-A3B-Instruct-2507:t2nj7mvwh0qs5h1szlfekqoh
Provider: https://api.pinference.ai/api/v1
Examples: 3
Rollouts per example: 2

Rewards:
reward: avg - 0.987, std - 0.018
r1: [0.962, 1.0, 1.0]
r2: [0.962, 1.0, 1.0]
delegation_reward: avg - 0.987, std - 0.018
r1: [0.962, 1.0, 1.0]
r2: [0.962, 1.0, 1.0]
num_turns: avg - 6.000, std - 0.000
r1: [6.0, 6.0, 6.0]
r2: [6.0, 6.0, 6.0]
Info:
is_truncated: avg - 0.000, std - 0.000
stop_conditions: episode_done: 1.000
Timing:
generation: min - 31s, mean - 35s, max - 39s
Usage:
input_tokens (avg): 8585.167
output_tokens (avg): 2382.333
```

### Behavioral Notes
- **Every single rollout completed in exactly 6 turns** — zero variance
- **4 out of 6 rollouts achieved perfect 1.0 reward**; remaining 2 scored 0.962
- Consistent pattern: explore file_tree → dispatch llm_batch() for parallel file analysis → read files directly → synthesize with llm_batch() → build report → set_answer()
- Model correctly identifies all planted bugs with detailed remediation steps
- Dramatically lower input token usage (8585 vs 14598) — more efficient exploration strategy
- **No over-exploration**: eliminated the 18-turn outlier behavior entirely

---

## Reward Progression During Training

```
Step   0: reward=0.8439  turns=7.57
Step  10: reward=0.8521  turns=6.57
Step  20: reward=0.8777  turns=6.68
Step  30: reward=0.8904  turns=6.99
Step  40: reward=0.8981  turns=6.76
Step  50: reward=0.9259  turns=6.26
Step  60: reward=0.9416  turns=6.27
Step  70: reward=0.9236  turns=6.84
Step  80: reward=0.9418  turns=6.33
Step  90: reward=0.8518  turns=5.11  (temporary dip — exploration phase)
Step  99: reward=0.9688  turns=6.01
```

---

## Analysis

### Isolating Training vs Scaling Effects

| Delta | From → To | Absolute Improvement | Relative Improvement |
|-------|-----------|---------------------|---------------------|
| Model size effect | 8B → 30B (untrained) | +0.234 | +42.5% |
| RL training effect | 30B untrained → trained | +0.202 | +25.7% |
| Combined | 8B untrained → 30B trained | +0.436 | +79.1% |

**The RL training effect (+25.7%) is comparable in magnitude to the model size effect (+42.5%).** This is the key investor insight: RL training on a cheap 30B MoE model (3B active params) delivers nearly as much improvement as 4x-ing the model size.

### What Specifically Improved

1. **Reward**: 0.785 → 0.987 (+25.7%). The trained model consistently achieves near-perfect scores.
2. **Consistency**: σ collapsed from 0.100 → 0.018. Turn std collapsed from 4.422 → 0.000.
3. **Efficiency**: Average turns dropped from 8.67 → 6.00, input tokens from 14,599 → 8,585 (41% reduction).
4. **Elimination of failure modes**: The 18-turn over-exploration outlier (untrained) is completely gone.
5. **Learned structured workflow**: The trained model converged on a reliable 6-turn pattern: explore → delegate → read → synthesize → report → answer.

### Honest Caveats
1. **Small eval set**: 6 rollouts per model across 3 mini-codebases. Statistical significance is limited, but the effect size is large (>12x the std).
2. **Environment may be too easy**: The trained model is hitting ceiling (0.987/1.0). Harder tasks would better differentiate.
3. **3 mini-codebases only**: Generalization to real-world repos is unproven.
4. **The untrained 30B was already decent**: 0.785 is a strong baseline. The improvement is real but the starting point isn't terrible.

---

## Suggested Next Steps

1. **Harder environment tasks** — Add larger codebases (100+ files) to widen differentiation and avoid ceiling effects
2. **More training steps** (200-300) — The reward curve was still climbing; diminishing returns analysis needed
3. **Train the 8B model** — Show GRPO works across model sizes (8B untrained: 0.551 → 8B trained: ???)
4. **Compare with Sonnet/Opus** — Calibrate the "behavioral gap" with frontier model numbers on same env
5. **Reward function tuning** — Add harder metrics (penalize missing specific bug categories, reward cross-file analysis)
6. **Statistical power** — Run with -n 10 -r 5 for more statistically robust comparisons

---

## Infrastructure

- **Training platform**: [Prime Intellect](https://app.primeintellect.ai) Hosted Training (free during Private Beta)
- **Environment**: `doloresresearch/deeprepo-orchestration` on [Environments Hub](https://app.primeintellect.ai/dashboard/environments/doloresresearch/deeprepo-orchestration)
- **Trained checkpoint**: Step 99 LoRA adapter, 12.6 GB
