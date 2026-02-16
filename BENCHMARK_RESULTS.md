# deeprepo — V0 Benchmark Results

**Date**: February 14, 2026
**Author**: Leon + Claude Code

---

## 1. V0 Build Summary

deeprepo V0 is a Python CLI that analyzes codebases using the Recursive Language Model pattern. Opus 4.6 orchestrates via a REPL loop, dispatching focused analysis tasks to MiniMax M2.5 workers via OpenRouter.

### Architecture

```
User CLI -> codebase_loader.py -> load files into dict
         -> rlm_scaffold.py (RLMEngine)
              -> Root model (Opus 4.6) writes Python code
              -> exec() in REPL namespace with codebase + llm functions
              -> llm_query/llm_batch -> Sub-LLM (MiniMax M2.5 via OpenRouter)
              -> REPL output fed back to root model
              -> Iterates until answer["ready"] = True
         -> cli.py saves .md analysis + _metrics.json
```

### Verification Steps (all passed)

| Step | Module | Test | Result |
|------|--------|------|--------|
| 1 | `llm_clients.py` | API connectivity — Opus 4.6 + MiniMax M2.5 | **PASS** — both respond with token counts |
| 2 | `codebase_loader.py` | Load `tests/test_small/` — 3 files, metadata, tree | **PASS** — 3 files, correct types/entries |
| 3 | `prompts.py` | Template formatting, placeholder validation | **PASS** — all strings valid, templates render |
| 4 | `rlm_scaffold.py` | Full RLM analysis on `test_small` — find 5 planted bugs | **PASS** — 5/5 bugs found (SQL injection, hardcoded secret, debug mode, MD5, unclosed connections) |
| 5 | `baseline.py` | Single-model baseline on `test_small` | **PASS** — 5/5 bugs found, cost tracked |
| 6 | `cli.py` | CLI commands: analyze, baseline, compare — output file saving | **PASS** — .md + _metrics.json saved to outputs/ |

### Test Codebase (`tests/test_small/`)

3 files with intentionally planted bugs:
- `app.py` — Flask task API with SQL injection, hardcoded secret key, debug mode, unclosed DB connections, missing input validation
- `utils.py` — MD5 password hashing (no salt), permissive email regex, incomplete sanitization
- `config.json` — Duplicate hardcoded secrets, debug=true

---

## 2. String Escaping Fix

### Problem

The root model's code frequently contained triple backticks (` ``` `) inside Python strings — for wrapping code in sub-LLM prompts, and for setting markdown content in `answer["content"]`. The code extraction regex treated these inline backticks as code fence closers, truncating code blocks mid-string. This caused cascading `SyntaxError`s and wasted 2-4 REPL turns per run.

### Changes Made

**Fix 1: Code extraction regex** (`src/rlm_scaffold.py` — `_extract_code`)

```python
# BEFORE: matches inline ``` anywhere in the response
pattern = r'```(?:python)?\s*\n(.*?)```'
blocks = re.findall(pattern, response, re.DOTALL)

# AFTER: requires ``` at line boundaries (start-of-line anchors)
pattern = r'^```(?:python)?\s*\n(.*?)\n```\s*$'
blocks = re.findall(pattern, response, re.DOTALL | re.MULTILINE)
```

The `^` and `$` anchors with `re.MULTILINE` ensure only proper markdown code fences (at line start/end) are matched, not ` ``` ` embedded inside Python string literals.

**Fix 2: `set_answer()` helper** (`src/rlm_scaffold.py` — `_build_namespace`)

Added a helper function to the REPL namespace:

```python
def set_answer(text: str) -> None:
    answer["content"] = text
    answer["ready"] = True
```

Updated `src/prompts.py` to:
- Document `set_answer()` in Available Functions
- Replace the Step 5 example with `lines.append()` + `set_answer("\n".join(lines))` pattern
- Add Rule 8: "Always use set_answer() + lines.append() pattern"

### Before/After on `test_small`

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| REPL turns | 5 | **1** | 5x fewer |
| Total time | 329s | **114s** | 2.9x faster |
| Total cost | $2.59 | **$0.34** | 7.6x cheaper |
| SyntaxErrors | 10+ | **0** | Eliminated |
| Sub-LLM calls | 0 (never reached) | **4** | Actually dispatched |
| Bugs found | 5/5 | 4/5 | Slight regression (missed "unclosed connections") |

The regex fix was the critical change — it allowed the root model's `llm_batch()` calls (which embed ` ``` ` in prompt strings) to execute on the first try.

---

## 3. Jianghu V3 Benchmark

Full benchmark against [Jianghu RPG](https://github.com/Leonwenhao/jianghu-game) — a Next.js 14 martial arts RPG with 225 files, 1.77M characters.

### Metrics

| Metric | RLM | Baseline |
|--------|-----|----------|
| **Total cost** | $5.04 | $1.36 |
| **Time** | ~12 min (5 turns) | ~2 min (1 call) |
| **Root tokens (in/out)** | 128,461 / 40,221 | 60,148 / 6,100 |
| **Root cost** | $4.94 | $1.36 |
| **Sub-LLM calls** | 61 | 0 |
| **Sub-LLM cost** | $0.10 | N/A |
| **Analysis length** | 21,081 chars | 22,497 chars |
| **Files analyzed** | **225/225 (100%)** | **108/225 (48%)** |
| **Files excluded** | 0 | 117 (context limit) |
| **Bugs/issues cataloged** | 32 items | 25 items |

### Qualitative Comparison

**RLM advantages (things baseline missed):**
- Race conditions in all Zustand store actions (B1) — cross-store `getState()` reads stale data
- Blockchain minting is non-functional (B2) — `useWriteContract()` return value unused
- Scene cache mutation corruption (B3) — in-place mutation of cached objects
- IDB persistence memory leak (B9) — `clear()` doesn't cancel pending timers
- Meditation breakthrough off-by-one (B6)
- Non-atomic state restoration (B5)
- Module-level counter persistence bug (B8)
- dangerouslySetInnerHTML XSS (S3)

**Baseline advantages (things RLM missed):**
- `toastRitual.ts` Math.ceil rounding inconsistency
- `Act1NPCCard` interface duplicated 7 times across files
- `as unknown as Technique` double-casts (3 techniques bypass type safety)
- Demo mode URL parameter doesn't persist to localStorage
- Micro-event double random roll (selection doesn't respect trigger probability)
- Mei Lingxi schedule override edge case
- Mountain path hardcoded discovery logic

**Both found:**
- No API rate limiting or authentication (P0 critical)
- Missing env var validation (FAL_KEY, ANTHROPIC_API_KEY)
- Prompt injection vulnerability
- Zero store/component/API route test coverage
- ~50 console.log statements in production
- Scene schema duality (prologue .ts vs Act 1 .json)
- No E2E tests
- Excessive cross-store coupling via getState()

### Key Observation

The baseline's 117 excluded files included many stores, components, and game logic files — exactly the files where RLM found its deepest bugs (race conditions, cache mutation, non-functional blockchain). RLM's ability to analyze all 225 files through sub-LLM dispatch is its core structural advantage on codebases that exceed single-prompt context limits.

---

## 4. Key Learnings

### Sub-LLM Economics Validated

61 MiniMax M2.5 calls cost only **$0.10** — less than 2% of total cost. The sub-LLM tier is essentially free. At $0.20/M input + $1.10/M output, we can afford hundreds of focused analysis calls per run. This validates the RLM architecture's core economic premise: cheap workers, expensive orchestrator.

### Root Model is the Cost Bottleneck

| Component | Jianghu Cost | % of Total |
|-----------|-------------|------------|
| Root model (Opus 4.6) | $4.94 | 98% |
| Sub-LLM (M2.5 x61) | $0.10 | 2% |
| **Total** | **$5.04** | 100% |

The root model's cost comes from conversation history accumulation — each turn adds the full prior context. By turn 5, input tokens hit 128K. Reducing turns (via the string escaping fix) or using a cheaper root model would cut costs dramatically.

### Multi-Turn History Causes Token Bloat

The RLM loop appends assistant + user messages each turn. Token growth is roughly quadratic:

| Turn | Approx Input Tokens | Cumulative |
|------|---------------------|------------|
| 1 | ~5K | 5K |
| 2 | ~15K | 20K |
| 3 | ~25K | 45K |
| 4 | ~30K | 75K |
| 5 | ~35K | 110K |

Strategies to reduce this:
- Summarize/compress conversation history between turns
- Cap the REPL output length more aggressively
- Minimize wasted turns (the string escaping fix already helped here)

### RLM Coverage Advantage is Real

On a 225-file, 1.77M-char codebase:
- Baseline fit 108/225 files (48%) — limited by ~180K char prompt window
- RLM analyzed all 225 files through programmatic access + parallel sub-LLM dispatch
- The 117 excluded files were where RLM found its deepest bugs

This advantage scales: on a 500+ file codebase, the baseline would cover <25% while RLM still covers 100%.

### String Escaping Fix Was High-Impact

Single highest-ROI change of the session:
- `test_small`: 5 turns/$2.59 -> 1 turn/$0.34 (7.6x cheaper)
- Eliminated all SyntaxError cascades
- Root cause was dual: regex matching inline backticks + model using triple-quoted strings in exec()
- Note: some residual issues remain on larger codebases (model still occasionally uses `f"""..."""` with backticks), but recovery is now 1-2 turns instead of 4-5

---

## 5. Next Steps

### Immediate: Swap Root Model to Sonnet 4.5

Sonnet 4.5 pricing: $3/M input, $15/M output (vs Opus $15/$75).
Expected Jianghu cost reduction: ~$5.04 -> ~$1.00 (5x cheaper).
Need to benchmark quality — will Sonnet write valid REPL code as reliably as Opus?

**Action items:**
1. Add `--root-model` CLI flag to select between `claude-opus-4-6` and `claude-sonnet-4-5-20250929`
2. Rerun Jianghu benchmark with Sonnet root
3. Compare analysis quality, turns needed, and cost

### Future Improvements

- **History compression**: Summarize prior REPL turns to reduce input token growth
- **Smarter code extraction**: Parse Python AST instead of regex for code block extraction
- **Retry logic**: Add exponential backoff for OpenRouter rate limits on large batch calls
- **Prompt string helper**: Add `build_prompt()` to REPL namespace to avoid backtick issues in sub-LLM prompts
- **Parallel baseline**: Run baseline with multiple calls on file subsets, then merge — hybrid approach
- **Sandbox execution**: Move exec() to subprocess for V1 safety
