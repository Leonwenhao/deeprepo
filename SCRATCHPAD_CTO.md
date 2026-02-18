# CTO Scratchpad — deeprepo Infrastructure Sprint

## Current Sprint Status
- **Last Updated:** 2026-02-18 (Issue #14 reviewed and APPROVED — SPRINT COMPLETE)
- **Current Issue:** None — all 6 issues completed
- **Phase:** DONE
- **Issues Completed:** #4, #5, #7, #6, #15, #14
- **Issues Remaining:** None

## Codebase Notes (verified against actual code)
- Package is `deeprepo/` (renamed from `src/` in 431b2cb)
- `deeprepo/utils.py` — retry utilities (Issue #4)
- `deeprepo/llm_clients.py` — retry on all 4 API calls (Issue #4), event-loop-safe batch (Issue #5), dynamic sub-pricing (Issue #7)
- `SUB_MODEL_PRICING` dict + `DEFAULT_SUB_MODEL` constant in llm_clients.py
- `TokenUsage.set_sub_pricing(model)` — dynamic pricing, mirrors `set_root_pricing()`
- `SubModelClient.__init__` defaults to `DEFAULT_SUB_MODEL`, calls `set_sub_pricing()`
- `run_analysis()` accepts `sub_model` param, threads to `SubModelClient`
- CLI `common` argparse group has `--root-model` and `--sub-model`; `list-models` subcommand works
- `run_baseline()` does NOT use SubModelClient — no sub-LLM changes needed there
- `RootModelClient.complete()` returns `str` without tools (baseline compat), full response object with tools (Issue #6)
- `OpenRouterRootClient.complete()` converts Anthropic tool schema to OpenAI function format when tools provided
- `EXECUTE_CODE_TOOL` schema in rlm_scaffold.py; `_extract_code_from_response()` handles both Anthropic and OpenAI response formats
- Legacy `_extract_code()` preserved as fallback for text-only responses
- `analyze()` loop: tool_use path sends per-block `tool_result` messages; text path uses legacy combined output
- System prompt updated to prefer `execute_python` tool
- `RootModelClient.complete()` accepts `stream: bool = False` — uses `messages.stream()` + `get_final_message()` (Issue #15)
- `OpenRouterRootClient.complete()` accepts `stream: bool = False` — signature only, intentionally ignored (Issue #15)
- `analyze()` passes `stream=self.verbose` — quiet mode disables streaming (Issue #15)
- `deeprepo/cache.py` — content-hash caching for sub-LLM results (Issue #14)
- `SubModelClient` accepts `use_cache: bool = True`, checks/writes cache in `query()` and `batch()`
- `batch()` pre-filters cached prompts, sends only uncached to API, merges in original order
- `run_analysis()` accepts `use_cache`, threads to `SubModelClient`
- CLI: `--no-cache` flag on common args, `cache stats` and `cache clear` subcommands

---

## Review: Issue #5 — asyncio.run() Fix — APPROVED

**Reviewed:** 2026-02-18
**Verdict:** APPROVED — clean, correct implementation.

**What I verified:**
- `batch()` now detects running event loop via `asyncio.get_running_loop()`, falls back to `ThreadPoolExecutor(max_workers=1)` with `asyncio.run()` in the thread. Correct.
- Fresh `asyncio.Lock()` created inside `_run_batch()` and passed via `lock=` parameter to `_async_query`. Cross-loop issue properly handled.
- `_async_query` accepts optional `lock` param, uses `usage_lock = lock or self._lock`. Clean.
- Public API unchanged, semaphore + `return_exceptions=True` preserved, exception processing intact.
- Tests: 2 new tests — sync context guard + existing event loop scenario with fully mocked async client.
- **Test results:** 15/15 pass (9 extract + 4 retry + 2 async batch).

---

## Review: Issue #4 — Retry Logic — APPROVED

**Reviewed:** 2026-02-18
**Verdict:** APPROVED. See earlier notes.

---

## Review: Issue #6 — tool_use Structured Output — APPROVED

**Reviewed:** 2026-02-18
**Verdict:** APPROVED — clean, spec-compliant, zero deviations.

**What I verified:**
- `EXECUTE_CODE_TOOL` schema at module level (rlm_scaffold.py:37-60). Correct `input_schema` with `code` (required) and `reasoning` (optional).
- `RootModelClient.complete()` accepts `tools` param, passes to Anthropic API, returns full response when tools provided, str otherwise (llm_clients.py:128-176). Backward compatible — baseline unaffected.
- `OpenRouterRootClient.complete()` converts Anthropic tool schema to OpenAI function format (`input_schema` -> `parameters`), returns full response when tools provided (llm_clients.py:196-252).
- `_extract_code_from_response()` handles Anthropic (`response.content` blocks) and OpenAI (`response.choices[0].message.tool_calls`) formats. Falls back to `_extract_code()` for text-only responses (rlm_scaffold.py:466-516).
- Defensive: `isinstance` check on `block.input`, `json.loads` try/except for OpenAI args — good robustness.
- `_get_response_text()` for logging across response types (rlm_scaffold.py:518-541).
- `_append_assistant_message()` serializes content blocks via `model_dump()` with manual fallback (rlm_scaffold.py:543-590).
- `_append_tool_result_messages()` sends per-tool outputs: Anthropic `tool_result` in single user message, OpenAI `role=tool` per call (rlm_scaffold.py:592-620).
- `analyze()` loop passes `tools=[EXECUTE_CODE_TOOL]`, uses structured extraction first, fallback second. Per-block outputs via `all_output` list (not combined). `used_tool_use` in trajectory.
- Legacy parser fully preserved: `_extract_code`, `_is_prose_line`, `_split_wrapped_blocks`, `_extract_inner_fences`.
- System prompt: `## How to Execute Code` section added, Steps 1-5 updated to mention tool, Rule 1 updated. Existing code examples kept.
- `baseline.py` NOT modified. Import verified clean.
- No `tool_choice` forcing — model chooses freely.
- **Test results:** 18/18 pass (9 extract + 4 retry + 2 async batch + 3 tool_use).

---

## Review: Issue #7 — Configurable Sub-LLM Model — APPROVED

**Reviewed:** 2026-02-18
**Verdict:** APPROVED — clean, spec-compliant implementation.

**What I verified:**
- `SUB_MODEL_PRICING` dict with 5 models + `DEFAULT_SUB_MODEL` constant (llm_clients.py:28-36)
- `TokenUsage` instance fields replace class constants. `set_sub_pricing(model)` mirrors `set_root_pricing()` pattern (llm_clients.py:56-81)
- `summary()` uses dynamic `self.sub_model_label` (llm_clients.py:107)
- Unknown model fallback: $1.00/$1.00 + warning to stderr — verified with smoke test
- `SubModelClient.__init__` defaults to `DEFAULT_SUB_MODEL`, calls `self.usage.set_sub_pricing(model)` (llm_clients.py:243-256)
- `run_analysis()` accepts `sub_model` param, threads to `SubModelClient(usage=usage, model=sub_model)` (rlm_scaffold.py:448-494)
- CLI: `--sub-model` on common arg group (analyze/baseline/compare), `list-models` subcommand works (cli.py:266-293)
- `cmd_analyze` and `cmd_compare` pass `sub_model=args.sub_model` to `run_analysis()`; baseline ignores it
- **Deviation (acceptable):** `sub_model` added to saved metrics JSON — additive metadata only
- **Test results:** 15/15 pass. `list-models`, `analyze --help`, `compare --help`, `baseline --help` all show `--sub-model`.

---

## Review: Issue #14 — Content-Hash Caching for Sub-LLM — APPROVED

**Reviewed:** 2026-02-18
**Verdict:** APPROVED — clean, spec-compliant, one acceptable deviation.

**What I verified:**
- `deeprepo/cache.py` (new): `_cache_key()` uses SHA-256 over `model||system||prompt`. `get_cached()` checks expiry (7-day) and deletes expired files. `set_cached()` writes JSON. `clear_cache()` returns count. `cache_stats()` returns entries + size. OSError fail-safes throughout (acceptable deviation for restricted envs).
- `SubModelClient.__init__`: `use_cache: bool = True` param added, stored as `self.use_cache`.
- `SubModelClient.query()`: lazy-import cache check before API call, cache write after success, skips `[ERROR` results.
- `SubModelClient.batch()`: pre-filters all prompts against cache, builds `uncached_indices`, sends only uncached to existing async pipeline, merges results at correct indices, writes to cache. Existing semaphore/event-loop logic preserved.
- `run_analysis()`: `use_cache: bool = True` threaded to `SubModelClient(use_cache=use_cache)`.
- CLI: `--no-cache` on common args (analyze/baseline/compare). `cmd_cache` handles `stats` and `clear` sub-actions. `cache` subcommand registered without `common` parent.
- Tests: 6 tests — miss, hit, model key, expiry, clear, stats. `autouse` fixture monkeypatches `CACHE_DIR` to temp dir.
- No changes to baseline.py or prompts.py.
- **Deviation (acceptable):** OSError fail-safes in `set_cached`, `clear_cache`, `cache_stats` — additive robustness for restricted environments.
- **Test results:** 24/24 pass (9 extract + 4 retry + 2 async batch + 3 tool_use + 6 cache).
- CLI verified: `cache stats`, `cache clear`, `analyze --help`, `compare --help` all show correct output.

---

## Review: Issue #15 — Streaming Support for Root Model — APPROVED

**Reviewed:** 2026-02-18
**Verdict:** APPROVED — clean, spec-compliant, zero deviations.

**What I verified:**
- `RootModelClient.complete()`: `stream: bool = False` added. When `True`, uses `self.client.messages.stream(**kwargs)` context manager, streams tokens via `sys.stderr.write(text)` + `flush()`, trailing `\n`, `get_final_message()` for accurate usage tracking. Retry wraps the entire streaming call via `@retry_with_backoff()`.
- Return behavior unchanged: full response when tools provided, str without.
- `OpenRouterRootClient.complete()`: `stream: bool = False` added to signature only — intentionally ignored. Correct per spec.
- `RLMEngine.analyze()`: passes `stream=self.verbose` to `complete()`. `--quiet` sets `verbose=False` which disables streaming.
- No changes to baseline.py, cli.py, prompts.py, or sub-LLM clients. Correct per spec.
- No new test file (streaming is a display feature — spec says none required).
- **Test results:** 18/18 pass (9 extract + 4 retry + 2 async batch + 3 tool_use).

---

## Codex Task: #7 — Configurable Sub-LLM Model (--sub-model)

### Context
The sub-LLM model is hardcoded to `minimax/minimax-m2.5`. Users cannot swap to DeepSeek, Llama, Qwen, or other OpenRouter models without editing source code. Model-agnostic orchestration is the core pitch — hardcoding a single sub-LLM undermines this.

### Files to Modify
- `deeprepo/llm_clients.py` — add `SUB_MODEL_PRICING` dict, update `TokenUsage` for dynamic sub-pricing, update `SubModelClient.__init__`
- `deeprepo/cli.py` — add `--sub-model` flag and `--list-models` command
- `deeprepo/rlm_scaffold.py` — thread `sub_model` through `run_analysis()`
- (No changes to `deeprepo/baseline.py` — baseline doesn't use sub-LLM)

### Specification

**1. Add `SUB_MODEL_PRICING` dict to `deeprepo/llm_clients.py` (near line 18, after ROOT_MODEL_PRICING):**

```python
SUB_MODEL_PRICING = {
    "minimax/minimax-m2.5": {"input": 0.20, "output": 1.10},
    "deepseek/deepseek-chat-v3-0324": {"input": 0.14, "output": 0.28},
    "qwen/qwen-2.5-coder-32b-instruct": {"input": 0.20, "output": 0.20},
    "meta-llama/llama-3.3-70b-instruct": {"input": 0.39, "output": 0.39},
    "google/gemini-2.0-flash-001": {"input": 0.10, "output": 0.40},
}

DEFAULT_SUB_MODEL = "minimax/minimax-m2.5"
```

**2. Update `TokenUsage` (lines 26-84) to support dynamic sub-pricing:**

Currently `SUB_INPUT_PRICE = 0.20` and `SUB_OUTPUT_PRICE = 1.10` are class-level constants. Change them to instance fields and add a `set_sub_pricing()` method, mirroring the existing `set_root_pricing()`:

```python
@dataclass
class TokenUsage:
    # ... existing fields ...

    # Sub-LLM pricing — set per model via set_sub_pricing()
    sub_input_price: float = 0.20
    sub_output_price: float = 1.10
    sub_model_label: str = "MiniMax M2.5"

    def set_sub_pricing(self, model: str) -> None:
        """Configure sub-LLM pricing from a model string."""
        pricing = SUB_MODEL_PRICING.get(model)
        if pricing:
            self.sub_input_price = pricing["input"]
            self.sub_output_price = pricing["output"]
            self.sub_model_label = model.split("/")[-1] if "/" in model else model
        else:
            # Unknown model — use fallback pricing and warn
            self.sub_input_price = 1.00
            self.sub_output_price = 1.00
            self.sub_model_label = model.split("/")[-1] if "/" in model else model
            print(f"⚠️ Unknown sub-model '{model}' — using fallback pricing $1.00/$1.00 per M tokens", file=sys.stderr)
```

**Remove** the old class constants `SUB_INPUT_PRICE = 0.20` and `SUB_OUTPUT_PRICE = 1.10`.

**Update** `sub_cost` property and `summary()` to use the new instance fields:
```python
@property
def sub_cost(self) -> float:
    return (
        (self.sub_input_tokens / 1_000_000) * self.sub_input_price
        + (self.sub_output_tokens / 1_000_000) * self.sub_output_price
    )

def summary(self) -> str:
    return (
        f"=== Token Usage & Cost ===\n"
        f"Root ({self.root_model_label}): {self.root_calls} calls, "
        f"{self.root_input_tokens:,} in / {self.root_output_tokens:,} out, "
        f"${self.root_cost:.4f}\n"
        f"Sub ({self.sub_model_label}): {self.sub_calls} calls, "
        f"{self.sub_input_tokens:,} in / {self.sub_output_tokens:,} out, "
        f"${self.sub_cost:.4f}\n"
        f"Total cost: ${self.total_cost:.4f}"
    )
```

Note: `summary()` currently hardcodes `"Sub (M2.5)"` — update it to use `self.sub_model_label`. You'll need to add `import sys` at the top of `llm_clients.py` for the stderr warning.

**3. Update `SubModelClient.__init__` to call `set_sub_pricing`:**

The constructor already accepts `model` — just add a call to set pricing on the usage tracker:

```python
def __init__(self, usage: TokenUsage, model: str = DEFAULT_SUB_MODEL, ...):
    ...
    self.usage = usage
    self.usage.set_sub_pricing(model)  # <-- add this line
```

Use `DEFAULT_SUB_MODEL` constant instead of the hardcoded string.

**4. Update `run_analysis()` in `deeprepo/rlm_scaffold.py` (line 442):**

Add `sub_model` parameter and thread it to `SubModelClient`:

```python
def run_analysis(
    codebase_path: str,
    verbose: bool = True,
    max_turns: int = MAX_TURNS,
    root_model: str = "claude-opus-4-6",
    sub_model: str = "minimax/minimax-m2.5",  # <-- add this
) -> dict:
    ...
    sub_client = SubModelClient(usage=usage, model=sub_model)  # <-- pass sub_model
```

Import `DEFAULT_SUB_MODEL` from llm_clients and use it as the default instead of the hardcoded string.

**5. Update CLI (`deeprepo/cli.py`):**

**a) Add `--sub-model` to the `common` argument group (after `--root-model`, around line 245):**

```python
common.add_argument(
    "--sub-model",
    default="minimax/minimax-m2.5",
    help="Sub-LLM model for file analysis (default: minimax/minimax-m2.5). Any OpenRouter model string.",
)
```

Import `DEFAULT_SUB_MODEL` from llm_clients and use it as the default.

**b) Thread `sub_model` through cmd_analyze (line 28):**

```python
def cmd_analyze(args):
    ...
    result = run_analysis(
        codebase_path=args.path,
        verbose=not args.quiet,
        max_turns=args.max_turns,
        root_model=root_model,
        sub_model=args.sub_model,  # <-- add
    )
```

**c) Thread `sub_model` through cmd_compare (line 116):**

```python
rlm_result = run_analysis(
    codebase_path=actual_path,
    verbose=not args.quiet,
    max_turns=args.max_turns,
    root_model=rlm_model,
    sub_model=args.sub_model,  # <-- add
)
```

**d) `cmd_baseline` does NOT use sub-LLM** — just ignore the `--sub-model` arg (it'll be present on `args` but unused). No changes needed.

**e) Add `--list-models` command:**

Add a new subcommand `list-models` (or handle it as a top-level flag) that prints available sub-models with pricing:

```python
def cmd_list_models(args):
    """Print available sub-LLM models and pricing."""
    from .llm_clients import SUB_MODEL_PRICING, DEFAULT_SUB_MODEL
    print("Available sub-LLM models (for --sub-model flag):\n")
    print(f"  {'Model':<45} {'Input $/M':>10} {'Output $/M':>11}")
    print(f"  {'-'*45} {'-'*10} {'-'*11}")
    for model, pricing in SUB_MODEL_PRICING.items():
        default_marker = " (default)" if model == DEFAULT_SUB_MODEL else ""
        print(f"  {model:<45} ${pricing['input']:>8.2f}  ${pricing['output']:>9.2f}{default_marker}")
    print(f"\n  Any OpenRouter model string is accepted. Unknown models use $1.00/$1.00 fallback pricing.")
```

Register it as a subparser:
```python
p_list = subparsers.add_parser("list-models", help="List available sub-LLM models and pricing")
p_list.set_defaults(func=cmd_list_models)
```

Note: `list-models` doesn't need the `common` parent parser (no `path` argument needed).

### Acceptance Criteria
- [ ] `SUB_MODEL_PRICING` dict and `DEFAULT_SUB_MODEL` constant in `deeprepo/llm_clients.py`
- [ ] `TokenUsage` uses dynamic sub-pricing via `set_sub_pricing(model)`, no more class constants
- [ ] `TokenUsage.summary()` shows dynamic sub-model label instead of hardcoded "M2.5"
- [ ] `--sub-model` flag available on `analyze`, `baseline`, and `compare` commands (present on args even if baseline ignores it)
- [ ] Default behavior unchanged when no `--sub-model` provided (uses minimax/minimax-m2.5)
- [ ] Unknown models accepted with warning and $1.00/$1.00 fallback pricing
- [ ] `deeprepo list-models` prints available models and pricing
- [ ] `run_analysis()` accepts and threads `sub_model` parameter
- [ ] Existing tests pass: `uv run python -m pytest tests/test_extract_code.py tests/test_retry.py tests/test_async_batch.py -v`
- [ ] `uv run python -m deeprepo.cli list-models` works
- [ ] `uv run python -m deeprepo.cli analyze --help` shows `--sub-model`

### Anti-Patterns (Do NOT)
- Do NOT add model aliases for sub-models (unlike root models which have `sonnet`/`opus` aliases)
- Do NOT validate that the model exists on OpenRouter — just pass it through, let the API error
- Do NOT change the default sub-model from minimax/minimax-m2.5
- Do NOT modify `deeprepo/baseline.py` — baseline doesn't use sub-LLM
- Do NOT change any public API beyond adding the new optional parameters

### Test Commands
```bash
uv run python -m pytest tests/test_extract_code.py tests/test_retry.py tests/test_async_batch.py -v
uv run python -m deeprepo.cli list-models
uv run python -m deeprepo.cli analyze --help   # should show --sub-model
uv run python -m deeprepo.cli compare --help   # should show --sub-model
```

### When Done
Update SCRATCHPAD_CODEX.md with:
- What you implemented (files changed, approach taken)
- Any deviations from the spec and why
- Test results (paste output)

---

## Decisions Made This Sprint
- **Path correction:** Package is `deeprepo/` not `src/`.
- **Issue #4 (retry):** APPROVED. Clean `_is_retryable` + decorator approach.
- **Issue #5 (asyncio):** APPROVED. ThreadPoolExecutor fallback + per-loop lock.
- **Issue #7 (sub-model):** APPROVED. Dynamic sub-pricing, CLI flag on common args, `list-models` subcommand.
- **Issue #6 (tool_use):** APPROVED. `complete()` returns str without tools, full response with tools. Dual-format extraction (Anthropic + OpenAI). Legacy parser as fallback. System prompt prefers tool_use.
- **Issue #15 (streaming):** APPROVED. `stream: bool = False` on both root clients. Anthropic path uses `messages.stream()` + `get_final_message()`. OpenRouter accepts but ignores. `analyze()` passes `stream=self.verbose`.
- **Issue #14 (caching):** APPROVED. Content-hash caching in `deeprepo/cache.py`. `SubModelClient` pre-filters batch, caches query results. `--no-cache` CLI flag. `cache stats/clear` subcommands. OSError fail-safes acceptable.

## Sprint Summary
All 6 issues implemented and reviewed: #4 (retry) -> #5 (asyncio) -> #7 (sub-model) -> #6 (tool_use) -> #15 (streaming) -> #14 (caching). Total: 24 tests, all passing. Infrastructure sprint COMPLETE.

## Open Questions
- (none)
