# deeprepo v0.2.1 — Infrastructure Audit Findings

**Auditor:** CTO code review
**Date:** 2026-02-23
**Branch:** main
**Test suite:** 186 passed, 2 failed (test infrastructure issue, not production)

---

## Critical (blocks release)

### C1: tool_use/tool_result mismatch — "no code blocks" path

**Root cause:** When the Anthropic model returns a `tool_use` block for `execute_python` but the `input` dict has no `"code"` key (or `code` is not a string), `_extract_code_from_response` correctly filters it out — returning empty `code_blocks` and empty `tool_use_info`. However, the raw `response` object still contains the `tool_use` content block. The main loop takes the "no code blocks" path (line 167), calls `_append_assistant_message(messages, response)` at line 173, which serializes ALL content blocks from the response — including the tool_use block. The next message appended (lines 174-180) is a plain text user message with no `tool_result`. The Anthropic API rejects this on the next call with HTTP 400.

**Exact lines:**
- `rlm_scaffold.py:167-181` — the "no code blocks" branch
- `rlm_scaffold.py:498-503` — extraction filters out tool_use blocks with invalid input, but only from `code_blocks`/`tool_use_info`, not from the response object
- `rlm_scaffold.py:556-579` — `_append_assistant_message` unconditionally serializes ALL content blocks from the response, including tool_use blocks that were filtered out by extraction

**Trigger scenario:** The model returns a response like:
```
content: [
  TextBlock("Let me analyze..."),
  ToolUseBlock(id="toolu_xyz", name="execute_python", input={"reasoning": "..."})  # no "code" key
]
```
Extraction returns `([], [])`. Main loop hits `if not code_blocks:`, appends the assistant message (with tool_use), then a plain text user message. API 400 on next turn.

**Fix approach (Option A — preferred):** Add a `strip_tool_use=False` parameter to `_append_assistant_message`. When `True`, filter out `tool_use` blocks from the serialized content, keeping only `text` blocks. Call with `strip_tool_use=True` in the "no code blocks" path (line 173) and the "legacy text" path (line 233).

**Fix approach (Option B):** In the "no code blocks" path, before appending the plain text user message, scan the response for tool_use blocks. For each one, generate a synthetic `tool_result` with an error message like `"[Tool call ignored: no valid code provided. Please use the execute_python tool with a 'code' parameter.]"`.

**Affected files:** `deeprepo/rlm_scaffold.py`

**How to verify:**
1. Unit test: construct a mock Anthropic response with a tool_use block where `input={"reasoning": "..."}` (no "code" key). Feed it through the engine's message handling. Assert the resulting messages list either has no tool_use blocks or has matching tool_results.
2. Integration: `deeprepo init .` on any project — should complete without API 400 errors.

---

### C2: tool_use/tool_result mismatch — "legacy text" path

**Root cause:** Same mechanism as C1, but on a different code path. When `_extract_code_from_response` finds tool_use blocks with invalid input, it falls through to the text fallback parser (lines 527-529). If the text portions contain code fences, `code_blocks` is non-empty but `tool_use_info` is empty. The main loop takes the `else` branch at line 231 (legacy text path), calls `_append_assistant_message(messages, response)` at line 233 — which serializes ALL content blocks from the response, including the tool_use blocks. The next message (lines 234-240) is a plain text user message with no tool_results.

**Exact lines:**
- `rlm_scaffold.py:231-240` — the "legacy text" branch
- `rlm_scaffold.py:524-529` — fallback to text extraction returns empty `tool_use_info`
- `rlm_scaffold.py:556-579` — `_append_assistant_message` serializes tool_use blocks unconditionally

**Trigger scenario:** Model returns both a malformed tool_use block AND code fences in the text portion. Extraction fails on tool_use (no valid code), falls back to text parser, finds code in text. `code_blocks` is non-empty, `tool_use_info` is empty → legacy path. But assistant message still has tool_use blocks.

**Fix approach:** Same as C1 — use `strip_tool_use=True` when calling `_append_assistant_message` in the legacy text path (line 233).

**Affected files:** `deeprepo/rlm_scaffold.py`

**How to verify:** Unit test: mock response with a malformed tool_use block AND code fences in the text portion. Verify messages list has no orphaned tool_use blocks.

---

## High (should fix before sharing)

### H1: Partial tool_use/tool_result mismatch in multi-block responses

**Root cause:** If the model returns multiple `tool_use` blocks in a single response but only SOME have valid code, `_extract_code_from_response` only adds the valid ones to `code_blocks` and `tool_use_info`. But `_append_assistant_message` (called by `_append_tool_result_messages` at line 615) serializes ALL tool_use blocks from the response. The `zip(tool_use_info, outputs)` at line 620 only generates tool_results for the valid ones. The invalid tool_use blocks have no matching tool_results.

**Exact lines:**
- `rlm_scaffold.py:606-626` — `_append_tool_result_messages`
- `rlm_scaffold.py:614-615` — calls `_append_assistant_message` which includes ALL tool_use blocks
- `rlm_scaffold.py:620` — `zip(tool_use_info, outputs)` only covers valid blocks

**Fix approach:** In `_append_tool_result_messages`, after the `zip` loop, scan the response for any remaining tool_use block IDs not in `tool_use_info` and append synthetic error tool_results for them. Alternatively, use the `strip_tool_use` approach from C1 to only serialize tool_use blocks that are in `tool_use_info`.

**Affected files:** `deeprepo/rlm_scaffold.py`

**How to verify:** Unit test: mock response with 2 tool_use blocks, one with valid code and one without. Verify all tool_use IDs have corresponding tool_results.

---

### H2: `sys.exit()` in REPL code kills the entire process

**Root cause:** `_execute_code` at line 636 catches `Exception` but `SystemExit` inherits from `BaseException`, not `Exception`. If the model's generated code calls `sys.exit()`, the exception propagates past the catch block and terminates the deeprepo process.

**Exact lines:**
- `rlm_scaffold.py:646-652` — `except Exception:` does not catch `BaseException` subclasses
- `rlm_scaffold.py:648` — `exec(code, namespace)` where the code may call `sys.exit()`

**Fix approach:** Change `except Exception:` to `except BaseException:` (or specifically catch `except (Exception, SystemExit):`). Log the SystemExit attempt in the output so the root model knows the code tried to exit.

**Affected files:** `deeprepo/rlm_scaffold.py`

**How to verify:** Unit test: execute code containing `sys.exit(0)` through `_execute_code`, verify it returns an error string instead of killing the process.

---

### H3: No execution timeout — infinite loops block forever

**Root cause:** `_execute_code` runs `exec(code, namespace)` with no timeout. If the model generates code with an infinite loop (e.g., `while True: pass`), the process hangs indefinitely. There is no way for the user to recover without killing the process.

**Exact lines:**
- `rlm_scaffold.py:647-648` — `exec(code, namespace)` with no timeout mechanism

**Fix approach:** Use `signal.alarm()` on Unix (or `threading.Timer` for cross-platform) to enforce a maximum execution time (e.g., 120 seconds). Catch `TimeoutError` and return an error message to the root model.

**Affected files:** `deeprepo/rlm_scaffold.py`

**How to verify:** Unit test: execute code containing `import time; time.sleep(999)` with a short timeout. Verify it raises/returns a timeout error within the expected timeframe.

---

### H4: Onboarding only checks for OpenRouter key, not Anthropic key

**Root cause:** `needs_onboarding()` and `run_onboarding()` in `onboarding.py` only check and prompt for `OPENROUTER_API_KEY`. The root model requires `ANTHROPIC_API_KEY` (set up in `llm_clients.py:119`). If a user has OpenRouter configured but not Anthropic, onboarding says everything is fine, but `/init` immediately fails with `EnvironmentError("ANTHROPIC_API_KEY not set...")`.

**Exact lines:**
- `tui/onboarding.py:59` — only checks `OPENROUTER_API_KEY`
- `tui/onboarding.py:107-121` — only prompts for OpenRouter key
- `tui/onboarding.py:36-47` — `save_global_api_key` only saves as `api_key` (OpenRouter) in config.yaml
- `llm_clients.py:119-123` — `RootModelClient.__init__` requires `ANTHROPIC_API_KEY`

**Fix approach:**
1. In `needs_onboarding()`, add a check: `needs_anthropic_key = not bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())`
2. In `run_onboarding()`, prompt for Anthropic key separately with explanation: "Anthropic API key (root model — the orchestrator)"
3. In `save_global_api_key` (or a new function), save both keys to `config.yaml` under `api_key` (OpenRouter) and `anthropic_api_key` (Anthropic)
4. In `load_global_api_key` (or a new function), load and set both env vars on startup

**Affected files:** `deeprepo/tui/onboarding.py`

**How to verify:** Unit test: mock `os.environ` with OpenRouter set but Anthropic missing. Verify `needs_onboarding()` reports a key is needed. Verify `run_onboarding()` prompts for it.

---

### H5: No loading indicator during `/init` and `/refresh`

**Root cause:** `_do_init` in `command_router.py:86-105` calls `cmd_init(args, quiet=True)` directly, synchronously, with no spinner or progress message. The `quiet=True` flag suppresses ALL engine output. The analysis takes 2-5 minutes. During this time the TUI appears completely frozen — no visual feedback whatsoever. Same for `_do_refresh` at line 166-175.

**Exact lines:**
- `tui/command_router.py:105` — `return cmd_init(args, quiet=True)` with no surrounding UI
- `tui/command_router.py:175` — `return cmd_refresh(args, quiet=True)` with no surrounding UI

**Fix approach:** Wrap the `cmd_init` and `cmd_refresh` calls in `rich.console.Console.status()`:
```python
from rich.console import Console
console = Console()

def _do_init(self, tokens):
    ...
    with console.status("[cyan]Analyzing project...[/cyan]", spinner="dots"):
        return cmd_init(args, quiet=True)
```
Rich's `status()` runs the spinner animation in a background thread automatically, so it works even though `cmd_init` blocks the main thread.

**Affected files:** `deeprepo/tui/command_router.py`

**How to verify:** Manual test: run `deeprepo` TUI, type `/init`. A spinner with "Analyzing project..." should be visible during analysis.

---

## Medium (fix in v0.2.2)

### M1: Rich markup leak in ASCII banner

**Root cause:** In `shell.py:188`, the ASCII art line ends with a backslash character that immediately precedes the closing Rich markup tag `[/bold magenta]`. In the resolved Python string:

```
[bold magenta] / _` |/ _ \/ _ \ '_ \| '__/ _ \ '_ \ / _ \[/bold magenta]
```

Rich interprets `\[` as an escaped literal `[` (this is Rich's markup escape syntax). The `\` at the end of the ASCII art consumes the `[` of the closing tag, so `[/bold magenta]` is rendered as literal text instead of being processed as a closing markup tag.

**Exact lines:**
- `tui/shell.py:188` — the third ASCII art line:
  ```python
  "[bold magenta] / _` |/ _ \\/ _ \\ '_ \\| '__/ _ \\ '_ \\ / _ \\[/bold magenta]",
  ```
  The final `\\` (Python) → `\` (string) + `[` (start of closing tag) → Rich sees `\[` = escaped bracket.

**Fix approach:** Add a space before the closing tag to break the `\[` sequence:
```python
"[bold magenta] / _` |/ _ \\/ _ \\ '_ \\| '__/ _ \\ '_ \\ / _ \\ [/bold magenta]",
```
Or use Rich's `Text` object with `highlight=False` / `markup=False` for the ASCII art, and apply styles programmatically. The space approach is simplest and preserves the visual alignment (an extra trailing space is invisible).

Alternatively, use Rich's escape mechanism: `\\[` in Rich markup produces a literal `\` followed by a normal `[`. So the Python string could use `\\\\ [/bold magenta]` but this is fragile. The trailing space is cleaner.

**Affected files:** `deeprepo/tui/shell.py`

**How to verify:** Run `deeprepo` and confirm no `[/bold magenta]` literal text is visible in the banner.

---

### M2: `/init` error messages reference `.env file` — misleading for TUI users

**Root cause:** `RootModelClient.__init__` in `llm_clients.py:121-123` raises:
```python
EnvironmentError("ANTHROPIC_API_KEY not set. Add it to your .env file or export it as an environment variable.")
```
This error propagates to the TUI's `command_router.py:43-44` generic exception handler:
```python
except Exception as exc:
    return {"status": "error", "message": f"Command failed: {exc}", "data": {}}
```
The raw exception text including ".env file" is shown to TUI users who may not know what a .env file is. Same pattern for `OPENROUTER_API_KEY` at `llm_clients.py:207-209` and `llm_clients.py:299-303`.

**Exact lines:**
- `llm_clients.py:121-123` — Anthropic key error message
- `llm_clients.py:207-209` — OpenRouter root client key error message
- `llm_clients.py:299-303` — Sub-model client key error message
- `tui/command_router.py:43-44` — generic error handler, no rewriting

**Fix approach:** In `_do_init` and `_do_refresh`, catch specific exceptions and rewrite error messages:
```python
def _do_init(self, tokens):
    ...
    try:
        return cmd_init(args, quiet=True)
    except EnvironmentError as exc:
        msg = str(exc)
        if "ANTHROPIC_API_KEY" in msg:
            return {"status": "error", "message": "Anthropic API key not set. Run: export ANTHROPIC_API_KEY=sk-ant-...", "data": {}}
        if "OPENROUTER_API_KEY" in msg:
            return {"status": "error", "message": "OpenRouter API key not set. Run: export OPENROUTER_API_KEY=sk-or-...", "data": {}}
        return {"status": "error", "message": f"Command failed: {exc}", "data": {}}
```

**Affected files:** `deeprepo/tui/command_router.py`, `deeprepo/llm_clients.py`

**How to verify:** Unset `ANTHROPIC_API_KEY`, run `deeprepo` TUI, type `/init`. Error should say "Run: export ANTHROPIC_API_KEY=..." not "Add it to your .env file".

---

### M3: Non-`execute_python` tool_use blocks cause orphaned tool_use IDs

**Root cause:** `_extract_code_from_response` only processes tool_use blocks where `block.name == "execute_python"` (line 498). If the model hallucinates a different tool name, that block is ignored during extraction but still serialized by `_append_assistant_message`. No tool_result is generated for it.

**Exact lines:**
- `rlm_scaffold.py:498` — `if block.type == "tool_use" and block.name == "execute_python":`
- `rlm_scaffold.py:565-578` — `_append_assistant_message` serializes ALL blocks regardless of name

**Fix approach:** In `_append_assistant_message`, only serialize tool_use blocks that match known tool names, OR generate error tool_results for unknown tool names.

**Affected files:** `deeprepo/rlm_scaffold.py`

**How to verify:** Unit test: mock response with a tool_use block named "search_files" (not in our tool list). Verify no orphaned tool_use in messages.

---

### M4: No early break when `set_answer()` is called during multi-block execution

**Root cause:** When the model returns multiple tool_use blocks and the first one calls `set_answer()`, the remaining blocks still execute (lines 185-197 — the `for i, code in enumerate(code_blocks)` loop has no check for `answer["ready"]`). This wastes time and potentially calls sub-LLMs unnecessarily.

**Exact lines:**
- `rlm_scaffold.py:185-197` — inner loop over code_blocks with no early break

**Fix approach:** After each `_execute_code` call, check if `answer["ready"]` is True and break out of the inner loop:
```python
output = self._execute_code(code, repl_namespace)
all_output.append(output)
if answer["ready"]:
    break
```
Note: even with this fix, `tool_use_info` and `all_output` may have different lengths. The `_append_tool_result_messages` `zip` will truncate. This is fine since we're about to break out of the outer loop too — but to be safe, pad `all_output` to match `tool_use_info` length before calling `_append_tool_result_messages`.

**Affected files:** `deeprepo/rlm_scaffold.py`

**How to verify:** Unit test: mock 3 code blocks where block 1 calls `set_answer()`. Verify blocks 2 and 3 don't execute.

---

## Low (polish / tech debt)

### L1: Retry utility doesn't retry 400 errors (by design, but worth noting)

`utils.py:31-33` — `_is_retryable` only retries status codes `429, 500, 502, 503, 504`. The tool_use/tool_result mismatch produces a 400 error which is NOT retried (correct behavior — retrying the same malformed request would fail again). But after fixing C1/C2, if a transient API formatting issue causes a 400, the retry logic won't help. This is fine as-is.

### L2: Test failures in `test_async_batch.py` — mock `await_count` tracking

Two tests fail because `create_mock.await_count == 0` despite correct results. The `AsyncMock`'s await tracking doesn't work because `batch()` runs the async code via `asyncio.run()` in a separate context (or `ThreadPoolExecutor` + `asyncio.run`). The mock's `await_count` isn't incremented because the awaits happen in a different event loop. The tests should assert on results and `usage.sub_calls` instead of `await_count`.

**Files:** `tests/test_async_batch.py`

### L3: `_execute_code` exposes full tracebacks to root model

`rlm_scaffold.py:650-652` — full Python tracebacks are sent back as REPL output. While useful for debugging, they consume tokens. Consider truncating tracebacks to the last N frames.

### L4: `save_global_api_key` only saves under generic `api_key` field name

`onboarding.py:43-47` — saves to `config.yaml` as `api_key` which implicitly means OpenRouter. When Anthropic key support is added (H4), the config schema needs updating. Not a bug today but a design limitation.

### L5: `_do_log` action parameter overloaded

`command_router.py:153-164` — when the user types `/log add some message`, the `action` is set to `"some message"` (the full text after "add"), not `"add"`. This happens to work because `cmd_log` treats any non-"show" action as a log message. But it's confusing — the Namespace has `action="some message"` and `message=None`. Should be `action="add", message="some message"`.

---

## Tests to Add

### T1: tool_use with invalid input → no orphaned tool_use in messages
**What it tests:** C1 — model returns tool_use block with no "code" key. After message handling, the messages list should have no tool_use blocks without matching tool_results.
**Where:** `tests/test_tool_use.py`
**Setup:** Mock Anthropic response with `ToolUseBlock(input={"reasoning": "..."})`. Run through the REPL loop's message handling logic. Assert messages.

### T2: tool_use with mixed valid/invalid blocks → all tool_use have tool_results
**What it tests:** H1 — response has 2 tool_use blocks, one valid, one without code. All serialized tool_use blocks must have tool_results.
**Where:** `tests/test_tool_use.py`

### T3: `sys.exit()` in REPL code → caught, not fatal
**What it tests:** H2 — `_execute_code("import sys; sys.exit(0)", namespace)` returns an error string, doesn't kill the process.
**Where:** `tests/test_tool_use.py` or new `tests/test_execute_code.py`

### T4: Infinite/long-running code → timeout enforced
**What it tests:** H3 — `_execute_code("import time; time.sleep(999)", namespace)` returns a timeout error within a reasonable time.
**Where:** `tests/test_execute_code.py`

### T5: Onboarding checks for both API keys
**What it tests:** H4 — `needs_onboarding()` detects missing ANTHROPIC_API_KEY. `run_onboarding()` prompts for both keys.
**Where:** `tests/test_onboarding.py`

### T6: Error message rewriting in TUI
**What it tests:** M2 — `/init` with missing ANTHROPIC_API_KEY shows user-friendly error, not ".env file" reference.
**Where:** `tests/test_command_router.py`

### T7: Rich markup renders clean (no literal tags)
**What it tests:** M1 — banner lines render without `[/bold magenta]` appearing as text.
**Where:** `tests/test_tui_polish.py` — render each banner line through `Console(file=StringIO())` and check output doesn't contain literal `[/`.

### T8: `set_answer()` during multi-block execution → early break
**What it tests:** M4 — when first code block calls `set_answer()`, remaining blocks should not execute (after fix).
**Where:** `tests/test_tool_use.py`

### T9: Fix `test_async_batch.py` await_count assertions
**What it tests:** L2 — replace `await_count` assertions with `usage.sub_calls` assertions.
**Where:** `tests/test_async_batch.py`
