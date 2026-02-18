# Codex Scratchpad — deeprepo Infrastructure Sprint

## Current Status
- **Last Updated:** 2026-02-18
- **Current Task:** #7 — Configurable Sub-LLM Model (--sub-model)
- **Status:** COMPLETED

## Latest Handoff
### Task #7 — Configurable Sub-LLM Model (--sub-model)

Implemented configurable sub-LLM model selection and dynamic sub-model pricing, then threaded `sub_model` through CLI -> `run_analysis()` -> `SubModelClient`.

- Files changed:
  - `deeprepo/llm_clients.py` (updated)
  - `deeprepo/cli.py` (updated)
  - `deeprepo/rlm_scaffold.py` (updated)

- Approach taken:
  - `deeprepo/llm_clients.py`:
    - Added `SUB_MODEL_PRICING` and `DEFAULT_SUB_MODEL`.
    - Updated `TokenUsage` to dynamic sub pricing fields:
      - Added `sub_input_price`, `sub_output_price`, `sub_model_label`.
      - Removed fixed class constants for sub pricing.
      - Added `set_sub_pricing(model)` with:
        - known-model pricing from `SUB_MODEL_PRICING`
        - unknown-model fallback pricing `$1.00/$1.00` and warning to `stderr`.
    - Updated `sub_cost` to use instance pricing fields.
    - Updated `summary()` to print `Sub ({self.sub_model_label})`.
    - Updated `SubModelClient.__init__`:
      - default model now `DEFAULT_SUB_MODEL`
      - calls `self.usage.set_sub_pricing(model)` after assigning `self.usage`.
  - `deeprepo/rlm_scaffold.py`:
    - Imported `DEFAULT_SUB_MODEL`.
    - Added `sub_model: str = DEFAULT_SUB_MODEL` to `run_analysis(...)`.
    - Threaded `sub_model` into `SubModelClient(usage=usage, model=sub_model)`.
  - `deeprepo/cli.py`:
    - Imported `DEFAULT_SUB_MODEL`.
    - Added `--sub-model` to shared/common args so it appears on `analyze`, `baseline`, and `compare`.
    - Passed `sub_model=args.sub_model` into `run_analysis()` in both `cmd_analyze` and `cmd_compare`.
    - Added `list-models` subcommand (`cmd_list_models`) to print built-in sub-model pricing and default marker.
    - `baseline` command unchanged in behavior (flag is accepted but ignored).

- Deviations from spec and why:
  - Added `sub_model` into saved RLM metrics JSON in `cmd_analyze` and `cmd_compare`. This is additive metadata only and does not affect public APIs or behavior.

- Test results (command output):

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_extract_code.py tests/test_retry.py tests/test_async_batch.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 15 items

tests/test_extract_code.py::test_basic_python_block PASSED               [  6%]
tests/test_extract_code.py::test_nested_backticks_in_fstring PASSED      [ 13%]
tests/test_extract_code.py::test_prose_before_code_not_extracted PASSED  [ 20%]
tests/test_extract_code.py::test_multiple_code_blocks PASSED             [ 26%]
tests/test_extract_code.py::test_fallback_rejects_pure_prose PASSED      [ 33%]
tests/test_extract_code.py::test_fallback_accepts_unfenced_code PASSED   [ 40%]
tests/test_extract_code.py::test_is_prose_line PASSED                    [ 46%]
tests/test_extract_code.py::test_wrapped_block_prose_with_inner_fences PASSED [ 53%]
tests/test_extract_code.py::test_code_block_with_inner_fences_not_split PASSED [ 60%]
tests/test_retry.py::test_retry_on_500 PASSED                            [ 66%]
tests/test_retry.py::test_no_retry_on_400 PASSED                         [ 73%]
tests/test_retry.py::test_max_retries_exceeded PASSED                    [ 80%]
tests/test_retry.py::test_async_retry_on_timeout PASSED                  [ 86%]
tests/test_async_batch.py::test_batch_sync_context_still_works PASSED    [ 93%]
tests/test_async_batch.py::test_batch_inside_existing_event_loop PASSED  [100%]

============================== 15 passed in 0.70s ===============================
```

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m deeprepo.cli list-models
Available sub-LLM models (for --sub-model flag):

  Model                                          Input $/M  Output $/M
  --------------------------------------------- ---------- -----------
  minimax/minimax-m2.5                          $    0.20  $     1.10 (default)
  deepseek/deepseek-chat-v3-0324                $    0.14  $     0.28
  qwen/qwen-2.5-coder-32b-instruct              $    0.20  $     0.20
  meta-llama/llama-3.3-70b-instruct             $    0.39  $     0.39
  google/gemini-2.0-flash-001                   $    0.10  $     0.40

  Any OpenRouter model string is accepted. Unknown models use $1.00/$1.00 fallback pricing.
```

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m deeprepo.cli analyze --help
usage: python3 -m deeprepo.cli analyze [-h] [-o OUTPUT_DIR] [-q]
                                       [--root-model ROOT_MODEL]
                                       [--sub-model SUB_MODEL]
                                       [--max-turns MAX_TURNS]
                                       path

positional arguments:
  path                  Path to codebase or git URL

options:
  -h, --help            show this help message and exit
  -o, --output-dir OUTPUT_DIR
                        Output directory
  -q, --quiet           Suppress verbose output
  --root-model ROOT_MODEL
                        Root model: opus, sonnet (default), minimax, or a full
                        model string like claude-opus-4-6
  --sub-model SUB_MODEL
                        Sub-LLM model for file analysis (default:
                        minimax/minimax-m2.5). Any OpenRouter model string.
  --max-turns MAX_TURNS
                        Max REPL turns
```

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m deeprepo.cli compare --help
usage: python3 -m deeprepo.cli compare [-h] [-o OUTPUT_DIR] [-q]
                                       [--root-model ROOT_MODEL]
                                       [--sub-model SUB_MODEL]
                                       [--max-turns MAX_TURNS]
                                       [--baseline-model BASELINE_MODEL]
                                       path

positional arguments:
  path                  Path to codebase or git URL

options:
  -h, --help            show this help message and exit
  -o, --output-dir OUTPUT_DIR
                        Output directory
  -q, --quiet           Suppress verbose output
  --root-model ROOT_MODEL
                        Root model: opus, sonnet (default), minimax, or a full
                        model string like claude-opus-4-6
  --sub-model SUB_MODEL
                        Sub-LLM model for file analysis (default:
                        minimax/minimax-m2.5). Any OpenRouter model string.
  --max-turns MAX_TURNS
                        Max REPL turns for RLM
  --baseline-model BASELINE_MODEL
                        Root model for baseline side: opus (default), sonnet,
                        or a full model string
```

### Task #5 — asyncio.run() Fix for Existing Event Loops

Implemented event-loop-safe `SubModelClient.batch()` execution and added tests for both sync and already-running loop contexts.

- Files changed:
  - `deeprepo/llm_clients.py` (updated)
  - `tests/test_async_batch.py` (new)

- Approach taken:
  - Updated `SubModelClient._async_query(...)` to accept optional `lock`:
    - New signature: `lock: asyncio.Lock | None = None`
    - Usage accounting now uses `usage_lock = lock or self._lock`.
  - Updated `SubModelClient.batch(...)` to detect running event loop:
    - If no running loop: keep existing behavior via `asyncio.run(_run_batch())`.
    - If loop is already running: execute `_run_batch()` in `ThreadPoolExecutor(max_workers=1)` and call `asyncio.run(...)` inside that thread.
  - Kept `batch()` public signature unchanged and retained semaphore + `return_exceptions=True`.

- asyncio.Lock cross-loop handling:
  - Created a fresh `asyncio.Lock()` inside `_run_batch()` (bound to that loop).
  - Passed that lock into each `_async_query(..., lock=lock)` call.
  - This avoids using `self._lock` across different event loops when batch runs inside thread fallback.
  - Kept `self._lock = asyncio.Lock()` in `__init__` as the default for direct `_async_query` calls.

- Deviations from spec and why:
  - Added one extra test for sync-path behavior (`test_batch_sync_context_still_works`) to explicitly verify current behavior is preserved in addition to the required existing-loop test.

- Issues/questions encountered:
  - No new issues beyond the existing `uv` cache sandbox restriction; commands were run with `UV_CACHE_DIR=/tmp/uv-cache`.

- Test results (command output):

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_extract_code.py tests/test_retry.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 13 items

tests/test_extract_code.py::test_basic_python_block PASSED               [  7%]
tests/test_extract_code.py::test_nested_backticks_in_fstring PASSED      [ 15%]
tests/test_extract_code.py::test_prose_before_code_not_extracted PASSED  [ 23%]
tests/test_extract_code.py::test_multiple_code_blocks PASSED             [ 30%]
tests/test_extract_code.py::test_fallback_rejects_pure_prose PASSED      [ 38%]
tests/test_extract_code.py::test_fallback_accepts_unfenced_code PASSED   [ 46%]
tests/test_extract_code.py::test_is_prose_line PASSED                    [ 53%]
tests/test_extract_code.py::test_wrapped_block_prose_with_inner_fences PASSED [ 61%]
tests/test_extract_code.py::test_code_block_with_inner_fences_not_split PASSED [ 69%]
tests/test_retry.py::test_retry_on_500 PASSED                            [ 76%]
tests/test_retry.py::test_no_retry_on_400 PASSED                         [ 84%]
tests/test_retry.py::test_max_retries_exceeded PASSED                    [ 92%]
tests/test_retry.py::test_async_retry_on_timeout PASSED                  [100%]

============================== 13 passed in 0.47s ===============================
```

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_async_batch.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 2 items

tests/test_async_batch.py::test_batch_sync_context_still_works PASSED    [ 50%]
tests/test_async_batch.py::test_batch_inside_existing_event_loop PASSED  [100%]

============================== 2 passed in 0.47s ===============================
```

### Task #4 — Retry Logic with Exponential Backoff

Implemented retry/backoff utilities and integrated them into all four LLM API call paths.

- Files changed:
  - `deeprepo/utils.py` (new)
  - `deeprepo/llm_clients.py` (updated)
  - `tests/test_retry.py` (new)

- Approach taken:
  - Added shared retry utilities in `deeprepo/utils.py`:
    - `_is_retryable(exc)` for Anthropic/OpenAI timeout, connection, and API status classification.
    - `retry_with_backoff(...)` decorator for sync calls.
    - `async_retry_with_backoff(...)` wrapper for async calls.
  - Retry policy:
    - Retryable: `429`, `500`, `502`, `503`, `504`, timeout, connection errors.
    - Not retryable: `400`, `401`, `403` (and other non-listed errors).
  - Backoff behavior:
    - Exponential delay (`base_delay * 2**attempt`) with cap at `MAX_DELAY`.
    - Added jitter (`random.uniform(0, JITTER_FACTOR * delay)`).
    - Retry attempts logged to `stderr`.
  - `deeprepo/llm_clients.py` updates:
    - `RootModelClient.complete()`: wrapped `self.client.messages.create(...)` with `@retry_with_backoff()`.
    - `OpenRouterRootClient.complete()`: wrapped `self.client.chat.completions.create(...)` with `@retry_with_backoff()`.
    - `SubModelClient.query()`: wrapped `self.client.chat.completions.create(...)` with `@retry_with_backoff()`.
    - `SubModelClient._async_query()`: wrapped async completion call via `async_retry_with_backoff(...)`.
    - In all four methods, only final failure is converted to `RuntimeError`, preserving SDK exception visibility during retry checks.
    - Usage/token accounting remains on successful responses only (failed attempts are not counted).
  - Added unit tests in `tests/test_retry.py`:
    - `test_retry_on_500` (fails twice, succeeds third call).
    - `test_no_retry_on_400` (fails immediately, no retry).
    - `test_max_retries_exceeded` (raises after `max_retries + 1` attempts).
    - `test_async_retry_on_timeout` (verifies async wrapper behavior).
    - Patched `time.sleep` / `asyncio.sleep` and `random.uniform` for deterministic, fast tests.

- Deviations from spec and why:
  - Added one extra test (`test_async_retry_on_timeout`) beyond the required minimum to explicitly validate `async_retry_with_backoff`.
  - Corrected spec typo `JITTE 0.5` to `JITTER_FACTOR = 0.5` for valid Python and intended behavior.

- Issues/questions encountered:
  - `uv` initially failed in sandbox due to cache path permissions at `~/.cache/uv`.
  - Resolved by running all `uv` commands with `UV_CACHE_DIR=/tmp/uv-cache`.
  - No unresolved questions.

- Test results (command output):

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_extract_code.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 9 items

tests/test_extract_code.py::test_basic_python_block PASSED               [ 11%]
tests/test_extract_code.py::test_nested_backticks_in_fstring PASSED      [ 22%]
tests/test_extract_code.py::test_prose_before_code_not_extracted PASSED  [ 33%]
tests/test_extract_code.py::test_multiple_code_blocks PASSED             [ 44%]
tests/test_extract_code.py::test_fallback_rejects_pure_prose PASSED      [ 55%]
tests/test_extract_code.py::test_fallback_accepts_unfenced_code PASSED   [ 66%]
tests/test_extract_code.py::test_is_prose_line PASSED                    [ 77%]
tests/test_extract_code.py::test_wrapped_block_prose_with_inner_fences PASSED [ 88%]
tests/test_extract_code.py::test_code_block_with_inner_fences_not_split PASSED [100%]

============================== 9 passed in 0.68s ===============================
```

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/test_retry.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 4 items

tests/test_retry.py::test_retry_on_500 PASSED                            [ 25%]
tests/test_retry.py::test_no_retry_on_400 PASSED                         [ 50%]
tests/test_retry.py::test_max_retries_exceeded PASSED                    [ 75%]
tests/test_retry.py::test_async_retry_on_timeout PASSED                  [100%]

============================== 4 passed in 0.54s ===============================
```

```bash
$ UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from deeprepo.utils import retry_with_backoff, async_retry_with_backoff; print('Import OK')"
Import OK
```

## Running Context
- Package is `deeprepo/` (not `src/`) — imports use `from deeprepo.xxx import yyy`
- CLI entry point: `deeprepo = "deeprepo.cli:main"` in pyproject.toml
- Existing tests: `tests/test_extract_code.py` (9 tests), plus test_loader, test_prompts, test_connectivity, test_baseline, test_rlm_integration
- LLM clients: `deeprepo/llm_clients.py` — 4 API call sites now use retry wrappers before final RuntimeError conversion
- `SubModelClient.batch()` is now safe in existing event loops via thread fallback + per-loop lock
- Sub-LLM model is configurable via CLI `--sub-model` and `deeprepo.cli list-models`
- Retry utilities are in `deeprepo/utils.py`
