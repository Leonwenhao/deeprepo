# Engineer Task: Task A — Engine Message Integrity + REPL Safety

## Context

deeprepo v0.2.1 has a **critical Anthropic API 400 error** when running `/init`. The RLM engine's REPL loop appends `tool_use` content blocks to the message history without matching `tool_result` messages. The Anthropic API rejects this on the next call. There are also two REPL safety bugs: `sys.exit()` in generated code kills the host process, and infinite loops hang forever.

All bugs are in one file: `deeprepo/rlm_scaffold.py`. This task fixes 7 issues and adds 5 tests.

---

## Files to Modify

- `deeprepo/rlm_scaffold.py` — all 7 fixes below
- `tests/test_tool_use.py` — add 3 new tests (T1, T2, T8)
- `tests/test_execute_code.py` — **new file**, 2 tests (T3, T4)

---

## Bug Descriptions and Fixes

### Fix 1: C1 — tool_use/tool_result mismatch in "no code blocks" path (CRITICAL)

**The bug:** When the Anthropic model returns a `tool_use` block for `execute_python` but the `input` dict has no `"code"` key, `_extract_code_from_response` filters it out — returning empty `code_blocks` and empty `tool_use_info`. But the raw `response` object still contains the `tool_use` content block. The main loop takes the "no code blocks" path (line 167), calls `_append_assistant_message(messages, response)` at line 173, which serializes ALL content blocks from the response — including the tool_use block. The next message (lines 174-180) is a plain text user message with NO `tool_result`. The Anthropic API rejects this with HTTP 400.

**Location:** Lines 167-181 (the `if not code_blocks:` branch in the REPL loop)

**Current code:**
```python
            if not code_blocks:
                if self.verbose:
                    print("No code blocks found in response. Checking if model is done...")
                if answer["ready"]:
                    break
                # Prompt model to use the tool
                self._append_assistant_message(messages, response)
                messages.append({
                    "role": "user",
                    "content": (
                        "Please use the execute_python tool to write and run Python code "
                        "to continue your analysis. Use the REPL to explore the codebase."
                    ),
                })
                continue
```

**Fix:** Call `_append_assistant_message(messages, response, strip_tool_use=True)` at line 173 so tool_use blocks are stripped from the serialized assistant message. (The `strip_tool_use` parameter is added in Fix 3 below.)

---

### Fix 2: C2 — tool_use/tool_result mismatch in "legacy text" path (CRITICAL)

**The bug:** Same mechanism as C1, different code path. When `_extract_code_from_response` finds tool_use blocks with invalid input, it falls through to the text fallback parser. If the text portions contain code fences, `code_blocks` is non-empty but `tool_use_info` is empty. The main loop takes the `else` branch at line 231 (legacy text path), calls `_append_assistant_message(messages, response)` at line 233 — which serializes ALL content blocks including tool_use blocks. The next message (lines 234-240) is a plain text user message with no tool_results.

**Location:** Lines 231-240 (the `else` branch — legacy text path)

**Current code:**
```python
            else:
                # Text-only path: send as user message (legacy behavior)
                self._append_assistant_message(messages, response)
                messages.append({
                    "role": "user",
                    "content": (
                        f"REPL Output:\n```\n{combined_output}\n```\n\n"
                        "Continue your analysis. Remember to call set_answer(text) when done."
                    ),
                })
```

**Fix:** Call `_append_assistant_message(messages, response, strip_tool_use=True)` at line 233.

---

### Fix 3: Add `strip_tool_use` parameter to `_append_assistant_message`

**Location:** Lines 556-604 (the `_append_assistant_message` method)

**Current code:**
```python
    def _append_assistant_message(self, messages: list[dict], response) -> None:
        """Append the assistant's response to the message list."""
        if isinstance(response, str):
            messages.append({"role": "assistant", "content": response})
            return

        if hasattr(response, "content") and isinstance(response.content, list):
            # Anthropic — serialize content blocks to dicts
            content_blocks = []
            for block in response.content:
                if hasattr(block, "model_dump"):
                    exclude = getattr(block, "__api_exclude__", None)
                    content_blocks.append(block.model_dump(exclude=exclude))
                else:
                    if block.type == "text":
                        content_blocks.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
            messages.append({"role": "assistant", "content": content_blocks})
            return

        if hasattr(response, "choices"):
            # OpenAI — reconstruct the assistant message
            msg = response.choices[0].message
            entry: dict = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                tool_calls = []
                for tc in msg.tool_calls:
                    if hasattr(tc, "model_dump"):
                        tool_calls.append(tc.model_dump())
                    else:
                        tool_calls.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        })
                entry["tool_calls"] = tool_calls
            messages.append(entry)
            return

        messages.append({"role": "assistant", "content": str(response)})
```

**Fix:** Add a `strip_tool_use: bool = False` parameter. When `True`:

For the **Anthropic** path: skip blocks where `block.type == "tool_use"` (both the `model_dump` path and the manual dict path). Only serialize `text` blocks. If after filtering there are no content blocks, add a single `{"type": "text", "text": ""}` block to avoid an empty content list.

For the **OpenAI** path: omit the `tool_calls` key from the entry entirely (don't serialize any tool_calls).

**New signature:**
```python
def _append_assistant_message(self, messages: list[dict], response, strip_tool_use: bool = False) -> None:
```

---

### Fix 4: H1/M3 — Orphaned tool_use IDs in `_append_tool_result_messages`

**The bug (H1):** If the model returns multiple `tool_use` blocks but only SOME have valid code, `_extract_code_from_response` only adds the valid ones to `tool_use_info`. But `_append_assistant_message` (called at line 615) serializes ALL tool_use blocks. The `zip(tool_use_info, outputs)` at line 620 only generates tool_results for the valid ones. The invalid tool_use blocks have no matching tool_results.

**The bug (M3):** If the model hallucinates a tool name other than `execute_python`, that block is ignored during extraction but still serialized. No tool_result is generated.

**Location:** Lines 606-634 (the `_append_tool_result_messages` method)

**Current code:**
```python
    def _append_tool_result_messages(
        self,
        messages: list[dict],
        response,
        tool_use_info: list[dict],
        outputs: list[str],
    ) -> None:
        """Append assistant message + tool_result messages after tool_use execution."""
        # First, append the assistant's response (includes tool_use blocks)
        self._append_assistant_message(messages, response)

        if hasattr(response, "content") and isinstance(response.content, list):
            # Anthropic format: tool_results go in a single user message
            tool_results = []
            for info, output in zip(tool_use_info, outputs):
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": info["id"],
                    "content": output,
                })
            messages.append({"role": "user", "content": tool_results})
        elif hasattr(response, "choices"):
            # OpenAI format: each tool_result is a separate "tool" role message
            for info, output in zip(tool_use_info, outputs):
                messages.append({
                    "role": "tool",
                    "tool_call_id": info["id"],
                    "content": output,
                })
```

**Fix:** After the existing `zip` loop, scan the response for ALL tool_use block IDs. For any ID that is NOT in `tool_use_info`, append a synthetic error tool_result.

For the **Anthropic** path, after the zip loop:
```python
# Generate synthetic error tool_results for orphaned tool_use blocks
covered_ids = {info["id"] for info in tool_use_info}
for block in response.content:
    if block.type == "tool_use" and block.id not in covered_ids:
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": "[Tool call ignored: invalid or unrecognized tool call. "
                       "Please use the execute_python tool with a 'code' parameter.]",
        })
```

For the **OpenAI** path, same logic:
```python
covered_ids = {info["id"] for info in tool_use_info}
if hasattr(response, "choices"):
    msg = response.choices[0].message
    if msg.tool_calls:
        for tc in msg.tool_calls:
            if tc.id not in covered_ids:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": "[Tool call ignored: invalid or unrecognized tool call. "
                               "Please use the execute_python tool with a 'code' parameter.]",
                })
```

---

### Fix 5: M4 — Early break when `set_answer()` called during multi-block execution

**The bug:** When the model returns multiple tool_use blocks and the first one calls `set_answer()`, the remaining blocks still execute. This wastes time and sub-LLM calls.

**Location:** Lines 184-197 (the `for i, code in enumerate(code_blocks)` loop)

**Current code:**
```python
            # Execute each code block in the REPL
            all_output = []
            for i, code in enumerate(code_blocks):
                if self.verbose:
                    # Show first 200 chars of code
                    preview = code[:200] + ("..." if len(code) > 200 else "")
                    print(f"\nExecuting code block {i+1}/{len(code_blocks)}:")
                    print(f"  {preview}")

                output = self._execute_code(code, repl_namespace)
                all_output.append(output)

                if self.verbose:
                    preview = output[:300] + ("..." if len(output) > 300 else "")
                    print(f"  Output: {preview}")
```

**Fix:** After `all_output.append(output)`, check if `answer["ready"]` is True and break:
```python
                output = self._execute_code(code, repl_namespace)
                all_output.append(output)

                if answer["ready"]:
                    if self.verbose:
                        print(f"  Answer marked ready — skipping remaining {len(code_blocks) - i - 1} block(s)")
                    break
```

**IMPORTANT:** After the inner loop, if early break happened, `all_output` may be shorter than `tool_use_info`. Before calling `_append_tool_result_messages` (line 228), pad `all_output`:
```python
            # Pad all_output to match tool_use_info length (early break case)
            while len(all_output) < len(tool_use_info):
                all_output.append("[Execution skipped: answer already finalized]")
```

Place this padding **after** the inner for loop and **before** the trajectory recording and `_append_tool_result_messages` call. Specifically, right after line 197 (end of the inner for loop), before line 199 (combined_output).

---

### Fix 6: H2 — `sys.exit()` in REPL code kills the entire process

**The bug:** `_execute_code` catches `Exception` but `SystemExit` inherits from `BaseException`, not `Exception`. If the model's code calls `sys.exit()`, it kills the deeprepo process.

**Location:** Lines 636-660 (the `_execute_code` method)

**Current code:**
```python
    def _execute_code(self, code: str, namespace: dict) -> str:
        """
        Execute Python code in the controlled REPL namespace.

        Captures stdout and returns it as a string.
        Catches exceptions and returns the traceback.
        """
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, namespace)
        except Exception:
            # Capture the traceback
            tb = traceback.format_exc()
            stdout_capture.write(f"\n[EXECUTION ERROR]\n{tb}")

        output = stdout_capture.getvalue()
        stderr_output = stderr_capture.getvalue()

        if stderr_output:
            output += f"\n[STDERR]\n{stderr_output}"

        return output if output else "[No output]"
```

**Fix:** Change `except Exception:` to `except BaseException as exc:`. Add a specific message for SystemExit:
```python
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, namespace)
        except BaseException as exc:
            if isinstance(exc, SystemExit):
                stdout_capture.write(
                    f"\n[EXECUTION ERROR]\n"
                    f"Code called sys.exit({exc.code}). "
                    f"This is not allowed in the REPL — use set_answer() to submit results."
                )
            elif isinstance(exc, KeyboardInterrupt):
                stdout_capture.write(
                    "\n[EXECUTION ERROR]\nKeyboardInterrupt caught in REPL code."
                )
            else:
                tb = traceback.format_exc()
                stdout_capture.write(f"\n[EXECUTION ERROR]\n{tb}")
```

---

### Fix 7: H3 — No execution timeout

**The bug:** `_execute_code` runs `exec(code, namespace)` with no timeout. If the model generates an infinite loop, the process hangs forever.

**Location:** Same method as Fix 6 — `_execute_code`

**Fix:** Add a timeout mechanism. Use `signal.alarm()` on Unix, with a `threading.Timer` fallback for non-Unix platforms.

Add this import at the top of the file (near the existing imports, around line 17):
```python
import signal
import threading
```

(`signal` may need to be added — check if it's already imported. `threading` is definitely not imported yet.)

Add a constant near the other constants (around line 37):
```python
EXEC_TIMEOUT_SECONDS = 120  # Maximum execution time per code block
```

Rewrite `_execute_code` to include the timeout:
```python
    def _execute_code(self, code: str, namespace: dict) -> str:
        """
        Execute Python code in the controlled REPL namespace.

        Captures stdout and returns it as a string.
        Catches exceptions and returns the traceback.
        Enforces a timeout to prevent infinite loops.
        """
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        timed_out = False

        def _timeout_handler(signum, frame):
            nonlocal timed_out
            timed_out = True
            raise TimeoutError("Code execution timed out")

        # Set up timeout — prefer signal.alarm on Unix, fall back to threading
        use_signal = hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()
        old_handler = None
        timer = None

        if use_signal:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(EXEC_TIMEOUT_SECONDS)
        else:
            timer = threading.Timer(EXEC_TIMEOUT_SECONDS, lambda: None)
            timer.start()

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, namespace)
        except BaseException as exc:
            if isinstance(exc, TimeoutError) or timed_out:
                stdout_capture.write(
                    f"\n[EXECUTION ERROR]\n"
                    f"Code execution timed out after {EXEC_TIMEOUT_SECONDS} seconds. "
                    f"Avoid infinite loops and long-running operations."
                )
            elif isinstance(exc, SystemExit):
                stdout_capture.write(
                    f"\n[EXECUTION ERROR]\n"
                    f"Code called sys.exit({exc.code}). "
                    f"This is not allowed in the REPL — use set_answer() to submit results."
                )
            elif isinstance(exc, KeyboardInterrupt):
                stdout_capture.write(
                    "\n[EXECUTION ERROR]\nKeyboardInterrupt caught in REPL code."
                )
            else:
                tb = traceback.format_exc()
                stdout_capture.write(f"\n[EXECUTION ERROR]\n{tb}")
        finally:
            # Clean up timeout
            if use_signal:
                signal.alarm(0)  # Cancel any pending alarm
                if old_handler is not None:
                    signal.signal(signal.SIGALRM, old_handler)
            elif timer is not None:
                timer.cancel()

        output = stdout_capture.getvalue()
        stderr_output = stderr_capture.getvalue()

        if stderr_output:
            output += f"\n[STDERR]\n{stderr_output}"

        return output if output else "[No output]"
```

**Note on timeout limitation:** `signal.alarm` only works on Unix and only in the main thread. The `threading.Timer` fallback does NOT actually interrupt the exec — it just sets a flag. For v0.2.2, the signal-based approach is sufficient (we run on macOS/Linux). The timer fallback is a graceful degradation, not a hard kill. A production solution would use `multiprocessing`, but that's out of scope.

---

## Existing Test File: `tests/test_tool_use.py`

Here is the current content — add new tests below the existing ones:

```python
"""Tests for tool_use-aware code extraction in RLMEngine."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from deeprepo.llm_clients import TokenUsage
from deeprepo.rlm_scaffold import RLMEngine


@pytest.fixture
def engine():
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    return RLMEngine(root_client=root, sub_client=sub, usage=usage, verbose=False)


def test_extract_code_from_anthropic_tool_use(engine):
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Running analysis."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="execute_python",
                input={"code": "print('hello from tool')", "reasoning": "Inspect files."},
            ),
        ]
    )

    code_blocks, tool_use_info = engine._extract_code_from_response(response)

    assert code_blocks == ["print('hello from tool')"]
    assert tool_use_info == [{"id": "toolu_1"}]


def test_extract_code_from_openai_tool_calls(engine):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="I will run code now.",
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="execute_python",
                                arguments='{"code":"x = 1\\nprint(x)","reasoning":"Quick check."}',
                            ),
                        )
                    ],
                )
            )
        ]
    )

    code_blocks, tool_use_info = engine._extract_code_from_response(response)

    assert code_blocks == ["x = 1\nprint(x)"]
    assert tool_use_info == [{"id": "call_1"}]


def test_extract_code_falls_back_to_legacy_parser_when_no_tool_use(engine):
    response = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text="Try this:\n```python\nx = 1\nprint(x)\n```",
            )
        ]
    )

    code_blocks, tool_use_info = engine._extract_code_from_response(response)

    assert len(code_blocks) == 1
    assert "x = 1" in code_blocks[0]
    assert "print(x)" in code_blocks[0]
    assert tool_use_info == []
```

---

## Tests to Add

### T1: `tests/test_tool_use.py` — tool_use with invalid input, no orphaned tool_use

Add this test to the existing file:

```python
def test_no_orphaned_tool_use_when_input_missing_code(engine):
    """C1: tool_use block with no 'code' key should not leave orphaned tool_use in messages."""
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Let me analyze the project."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_bad",
                name="execute_python",
                input={"reasoning": "I want to look at files"},  # No "code" key!
            ),
        ]
    )

    messages = []
    # This simulates the "no code blocks" path — strip_tool_use=True
    engine._append_assistant_message(messages, response, strip_tool_use=True)

    assert len(messages) == 1
    assistant_msg = messages[0]
    assert assistant_msg["role"] == "assistant"

    # Verify no tool_use blocks in the serialized content
    content = assistant_msg["content"]
    if isinstance(content, list):
        for block in content:
            assert block.get("type") != "tool_use", \
                f"Found orphaned tool_use block: {block}"
    # It should only have the text block
    assert any(
        b.get("type") == "text" and "analyze" in b.get("text", "")
        for b in content
    ), "Text block should be preserved"
```

### T2: `tests/test_tool_use.py` — mixed valid/invalid tool_use blocks all get tool_results

```python
def test_all_tool_use_ids_have_tool_results(engine):
    """H1/M3: Every tool_use block in the response must have a matching tool_result."""
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Running two tools."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_valid",
                name="execute_python",
                input={"code": "print('valid')", "reasoning": "test"},
            ),
            SimpleNamespace(
                type="tool_use",
                id="toolu_invalid",
                name="execute_python",
                input={"reasoning": "no code here"},  # Missing "code"
            ),
            SimpleNamespace(
                type="tool_use",
                id="toolu_wrong_name",
                name="search_files",  # Not execute_python
                input={"query": "something"},
            ),
        ]
    )

    # Only the valid block should be in tool_use_info
    tool_use_info = [{"id": "toolu_valid"}]
    outputs = ["valid output"]

    messages = []
    engine._append_tool_result_messages(messages, response, tool_use_info, outputs)

    # Should have: 1 assistant message + 1 user message with tool_results
    assert len(messages) == 2
    assert messages[0]["role"] == "assistant"
    assert messages[1]["role"] == "user"

    tool_results = messages[1]["content"]
    assert isinstance(tool_results, list)

    # Collect all tool_result IDs
    result_ids = {r["tool_use_id"] for r in tool_results if r.get("type") == "tool_result"}

    # ALL three tool_use IDs must have matching tool_results
    assert "toolu_valid" in result_ids, "Valid tool_use should have a tool_result"
    assert "toolu_invalid" in result_ids, "Invalid tool_use should have a synthetic error tool_result"
    assert "toolu_wrong_name" in result_ids, "Unknown tool name should have a synthetic error tool_result"

    # The synthetic ones should have error messages
    for r in tool_results:
        if r["tool_use_id"] in ("toolu_invalid", "toolu_wrong_name"):
            assert "ignored" in r["content"].lower() or "invalid" in r["content"].lower(), \
                f"Synthetic tool_result should indicate the call was ignored: {r['content']}"
```

### T8: `tests/test_tool_use.py` — early break when set_answer() called

```python
def test_early_break_on_set_answer(engine):
    """M4: When first code block calls set_answer(), remaining blocks should not execute."""
    answer = {"content": "", "ready": False}

    def set_answer(text):
        answer["content"] = text
        answer["ready"] = True

    namespace = {
        "answer": answer,
        "set_answer": set_answer,
        "__builtins__": __builtins__,
    }

    code_blocks = [
        "set_answer('done')",           # Block 1: sets answer
        "print('should not run')",       # Block 2: should be skipped
        "print('also should not run')",  # Block 3: should be skipped
    ]

    # Execute blocks with early break logic (simulating the main loop)
    all_output = []
    for code in code_blocks:
        output = engine._execute_code(code, namespace)
        all_output.append(output)
        if answer["ready"]:
            break

    # Only block 1 should have executed
    assert len(all_output) == 1, f"Expected 1 output, got {len(all_output)}: {all_output}"
    assert answer["ready"] is True
    assert answer["content"] == "done"
```

### T3: `tests/test_execute_code.py` — sys.exit() caught, not fatal (NEW FILE)

Create this as a new file:

```python
"""Tests for REPL code execution safety in RLMEngine."""

from unittest.mock import MagicMock

import pytest

from deeprepo.llm_clients import TokenUsage
from deeprepo.rlm_scaffold import RLMEngine


@pytest.fixture
def engine():
    usage = TokenUsage()
    root = MagicMock()
    sub = MagicMock()
    return RLMEngine(root_client=root, sub_client=sub, usage=usage, verbose=False)


def test_sys_exit_caught_not_fatal(engine):
    """H2: sys.exit() in REPL code should be caught, not kill the process."""
    namespace = {"__builtins__": __builtins__}
    output = engine._execute_code("import sys; sys.exit(0)", namespace)

    assert "EXECUTION ERROR" in output
    assert "sys.exit" in output
    # The fact that this test completes means the process survived


def test_sys_exit_nonzero_caught(engine):
    """H2: sys.exit(1) should also be caught."""
    namespace = {"__builtins__": __builtins__}
    output = engine._execute_code("import sys; sys.exit(1)", namespace)

    assert "EXECUTION ERROR" in output
    assert "sys.exit" in output
```

### T4: `tests/test_execute_code.py` — timeout enforced

Add to the same new file:

```python
def test_execution_timeout(engine):
    """H3: Long-running code should be interrupted by timeout."""
    import deeprepo.rlm_scaffold as scaffold

    # Temporarily set a short timeout for testing
    original_timeout = scaffold.EXEC_TIMEOUT_SECONDS
    scaffold.EXEC_TIMEOUT_SECONDS = 2  # 2 seconds for test

    try:
        namespace = {"__builtins__": __builtins__}
        output = engine._execute_code("import time; time.sleep(999)", namespace)

        assert "EXECUTION ERROR" in output
        assert "timed out" in output.lower()
    finally:
        scaffold.EXEC_TIMEOUT_SECONDS = original_timeout
```

**Note on T4:** This test only works reliably on Unix (macOS/Linux) where `signal.SIGALRM` is available. If running on Windows, the threading.Timer fallback won't actually interrupt `time.sleep()`, so the test would hang. If you need to handle this, add `@pytest.mark.skipif(not hasattr(signal, 'SIGALRM'), reason="signal.SIGALRM not available")` to the test. Import `signal` at the top of the test file.

---

## Acceptance Criteria

- [ ] `python -m pytest tests/test_tool_use.py -v` — all existing + 3 new tests pass
- [ ] `python -m pytest tests/test_execute_code.py -v` — 3 new tests pass (T3 x2, T4)
- [ ] `python -m pytest tests/ -v` — all 186+ existing tests still pass (2 pre-existing failures in test_async_batch.py are known and acceptable)
- [ ] No `tool_use` block in the messages list ever lacks a matching `tool_result` — verified by T1 and T2
- [ ] `sys.exit()` in REPL code returns an error string, does not kill the process — verified by T3
- [ ] Long-running code is interrupted by timeout — verified by T4
- [ ] `set_answer()` in first code block prevents remaining blocks from executing — verified by T8
- [ ] The `strip_tool_use` parameter defaults to `False` so all existing call sites are unaffected
- [ ] The synthetic error tool_results in `_append_tool_result_messages` include helpful error messages guiding the model to use the correct tool

## Anti-Patterns (Do NOT)

- Do NOT modify `_extract_code_from_response` — it correctly filters invalid blocks. The bug is in message serialization, not extraction.
- Do NOT change any existing test assertions — only add new tests.
- Do NOT add timeout logic using `multiprocessing` — `signal.alarm` is sufficient for v0.2.2.
- Do NOT remove or rename existing methods — only modify `_append_assistant_message`, `_append_tool_result_messages`, `_execute_code`, and the main REPL loop in `analyze()`.
- Do NOT add new dependencies to `pyproject.toml` — `signal` and `threading` are stdlib.
- Do NOT touch any files outside of `deeprepo/rlm_scaffold.py`, `tests/test_tool_use.py`, and `tests/test_execute_code.py`.

## Test Commands

```bash
# Run just the new and modified tests
python -m pytest tests/test_tool_use.py tests/test_execute_code.py -v

# Run full test suite to verify no regressions
python -m pytest tests/ -v

# Quick smoke test for specific new tests
python -m pytest tests/test_tool_use.py::test_no_orphaned_tool_use_when_input_missing_code -v
python -m pytest tests/test_tool_use.py::test_all_tool_use_ids_have_tool_results -v
python -m pytest tests/test_tool_use.py::test_early_break_on_set_answer -v
python -m pytest tests/test_execute_code.py::test_sys_exit_caught_not_fatal -v
python -m pytest tests/test_execute_code.py::test_execution_timeout -v
```

## When Done

Update `SCRATCHPAD_ENGINEER.md` with:
- What you implemented (files changed, approach taken)
- Any deviations from the spec and why
- Any issues or questions encountered
- Test results (paste `pytest` output)
