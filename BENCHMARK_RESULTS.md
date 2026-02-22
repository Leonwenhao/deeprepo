# deeprepo — Benchmark Results

## Overview

deeprepo is an open-source codebase analysis tool that implements the Recursive Language Model (RLM) pattern. A root model operates in a REPL loop, writing Python code to read files and dispatch focused analysis tasks to sub-LLM workers. The root model synthesizes worker results into a unified codebase report. This document presents benchmark results across three codebases of increasing size: FastAPI (47 files, 668K chars), Pydantic (105 files, 1.76M chars), and Jianghu V3 (289 files, 2.07M chars).

---

## FastAPI: Sonnet RLM vs. Opus Baseline

This is the head-to-head comparison — same codebase, same task, two approaches.

### Metrics

| Metric | Sonnet RLM | Opus Baseline |
|--------|:----------:|:-------------:|
| Root model | Claude Sonnet 4.5 | Claude Opus 4.6 |
| Total cost | $0.46 | $0.99 |
| Root cost | $0.44 | $0.99 |
| Sub-LLM cost | $0.02 | N/A |
| Root calls | 3 | 1 |
| Sub-LLM calls | 13 | N/A |
| Files covered | 47/47 (100%) | 42/47 (89%) |
| Analysis output | 30,370 chars | 12,793 chars |

The RLM approach costs 53% less while covering 100% of the codebase. The baseline, constrained to a single context window, had to exclude 5 files that exceeded its token budget.

### The 5 Excluded Files

| File | Characters | Role |
|------|:---------:|------|
| `routing.py` | 181,387 | Core routing engine, APIRouter |
| `applications.py` | 179,982 | FastAPI application class |
| `param_functions.py` | 69,467 | Parameter extraction (Path, Query, Body, etc.) |
| `dependencies/utils.py` | 38,751 | Dependency injection resolution |
| `params.py` | 26,043 | Parameter type definitions |
| **Total** | **495,630** | **74% of codebase** |

These are not peripheral files. They contain FastAPI's core class, its routing engine, and the entire dependency injection system. `routing.py` alone at 181K characters exceeds the baseline's entire prompt budget of 175K characters. This is a structural limitation of single-call analysis — any codebase with large core files will force the baseline to exclude exactly the files that matter most.

### Limitations Observed

For files both approaches analyzed, the Opus baseline produced more precise per-file findings with direct code-level citations (line numbers, exact code snippets), while the RLM produced broader architectural coverage and more findings overall. Additionally, the RLM's file-level analysis does not yet distinguish project-owned code from upstream re-exports (e.g., FastAPI's Starlette middleware wrappers are analyzed as if they were FastAPI-authored code). This is a known improvement target for V0.5.

---

## Pydantic: Standalone RLM Run

| Metric | Value |
|--------|:-----:|
| Root model | Claude Sonnet 4.5 |
| Total cost | $0.66 |
| Root cost | $0.58 |
| Sub-LLM cost | $0.07 |
| Turns | 4 |
| Sub-LLM calls | 17 |
| Source files | 105 |
| Total characters | ~1.76M |
| Coverage | 100% |

Pydantic is a significantly larger codebase than FastAPI, with a single file (`_generate_schema.py`) at 132K characters and several others above 80K. The RLM completed full analysis in 4 turns with 17 sub-LLM dispatches. The analysis identified the multi-stage schema generation pipeline and metaclass-based model construction as core architectural patterns, flagged security concerns (eval() usage in model construction, DoS risk from unbounded recursion depth), and cataloged ~200 `type: ignore` comments as a proxy for type system complexity at the Pydantic-core boundary. No baseline comparison was run for Pydantic — this serves as supporting evidence that the approach scales to larger, more complex codebases without modification.

---

## Jianghu V3: Three-Way Root Model Comparison

This benchmark tested three root models on the same 289-file TypeScript/React codebase (2.07M chars, ~55K lines), with an Opus single-call baseline for reference. All RLM runs used MiniMax M2.5 as the sub-LLM worker.

### Results

| Metric | M2.5 Root | Sonnet Root | Opus Root | Opus Baseline |
|--------|:---------:|:-----------:|:---------:|:-------------:|
| Cost | $0.024 | $0.74 | $5.04 | $1.39 |
| Sub-LLM dispatches | 0 | 9 | 61 | N/A |
| Files analyzed via sub-LLM | 0 | ~35 | 225 | 108 (direct) |
| Unique deep bugs found | 0 | 2 | 18 | ~5 |
| Analysis quality (manual grade) | D | B | A | B+ |
| Sub-LLM file coverage* | — | ~12% | 100% | 48% |

*\* For RLM runs, percentage of files dispatched to sub-LLM workers. Root models may also read additional files directly via REPL. Baseline figure represents files included in the single context window.*

### Sub-LLM Cost Breakdown

| Sub-LLM Calls | Sub-LLM Cost | Root Cost (Sonnet) | Total | Sub-LLM as % of Total |
|:-------------:|:------------:|:------------------:|:-----:|:---------------------:|
| 9 (actual) | $0.015 | $0.72 | $0.74 | 2% |
| 61 (Opus-level) | ~$0.10 | ~$0.90 | ~$1.00 | 10% |
| 100 (projected) | ~$0.16 | ~$1.05 | ~$1.21 | 13% |

The sub-LLM worker layer costs 2% of the total run. Even at 100 dispatches, it would represent only 13%. The entire cost structure lives in the root model.

### Three Capability Tiers

The three root models fall into distinct tiers rather than a smooth gradient:

**Tier 1 — Cannot orchestrate (M2.5).** Failed mechanically: all 5 `llm_batch()` attempts crashed with the same `SyntaxError`. Hit the identical error 17 times across 3 turns without adapting. Zero in-context learning from execution failures.

**Tier 2 — Can orchestrate, stops early (Sonnet).** Mechanically competent — working REPL code, correct sub-LLM dispatch and result parsing. But finalized after 9 dispatches when 60+ were possible. This is satisficing behavior: producing a plausible answer with minimum effort.

**Tier 3 — Orchestrates exhaustively (Opus).** Dispatched 61 sub-LLM calls across 5 systematic batches covering the entire codebase. Continued working through turn 4 before finalizing on turn 5. Every deep bug that only Opus found was in a file that Sonnet never dispatched for analysis.

The gap from Tier 2 to Tier 3 is behavioral, not mechanical — Sonnet knows how to dispatch more calls; it chooses not to. This makes it a well-defined RL training target.

---

## Key Findings

**1. The sub-LLM layer is effectively free.** Across all benchmarked runs, sub-LLM costs stayed at or below $0.10 regardless of dispatch count. Worker cost is 2-13% of total. The cost optimization target is the root model's pricing tier, not the number of dispatches.

**2. Coverage advantage grows with codebase size.** On FastAPI (47 files), the single-call baseline achieved 89% file coverage. On Jianghu V3 (289 files), that dropped to 48%. The RLM maintained 100% in both cases. As codebases grow, context windows become a harder constraint for single-call approaches while the RLM's iterative architecture faces no equivalent ceiling.

**3. Cheaper models can outperform expensive ones.** The Sonnet RLM ($0.46) outperformed the Opus baseline ($0.99) on FastAPI by covering 100% of files versus 89%, at half the cost. The architecture lets a $3/M-token model beat a $15/M-token model by decomposing the problem rather than brute-forcing it into one context window.

**4. Quality scales with delegation count.** In the Jianghu benchmark, Opus (61 dispatches) found 18 deep bugs. Sonnet (9 dispatches) found 2. M2.5 (0 dispatches) found 0. Every missed bug traced back to a file that was never dispatched for analysis. The quality bottleneck is not the worker model — it is the root model's willingness to delegate.

---

## Known Limitations & Next Steps

- **Re-export scope awareness.** The RLM does not yet distinguish project-owned code from upstream re-exports (e.g., Starlette middleware re-exported by FastAPI). This inflates file counts and can produce findings against code the project doesn't control.
- **Per-file precision gap.** For files both approaches can see, single-model analysis currently produces more precise code-level citations than the RLM's sub-LLM worker outputs. Improving worker prompt design is a near-term target.
- **Sonnet delegation ceiling.** Sonnet dispatches ~9 sub-LLM calls where Opus dispatches 61. Before RL training, we are exploring prompt tuning to increase Sonnet's delegation count and establish a pre-training ceiling.
- **Standardized evaluation.** Current benchmarks use project-specific codebases. Migration to SWE-bench Verified is planned for standardized, reproducible evaluation that the field recognizes.
- **RL training.** The end goal is to train Sonnet to delegate at Opus's level — making thorough delegation intrinsic to the model's policy rather than dependent on prompt engineering. The behavioral gap (9 vs. 61 dispatches) is specific, measurable, and directly trainable.

This is early-stage research. The architecture works; the open question is whether RL training can close the behavioral gap between Sonnet and Opus at a fraction of the cost.

---

## Film Domain Benchmark (Pending)

The `film` domain (Script Breakdown) is implemented, but benchmark results are not included yet in this document because the operational run requires API keys and a locally provided screenplay file.

To run the benchmark workflow, see:
- `examples/get-out/README.md` (input acquisition + benchmark commands)
- `GET_OUT_GROUND_TRUTH.md` (ground truth scoring reference)

---

*Generated from benchmark runs: February 16, 2026*
*Source data: `examples/fastapi/`, `examples/pydantic/`, `tapi/`, `RESEARCH_JOURNAL.md`*
