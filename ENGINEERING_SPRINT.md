# deeprepo — Infrastructure Sprint: Agent Coordination Plan

**Author:** Leon
**Date:** February 18, 2026
**Sprint Goal:** Resolve 6 critical infrastructure issues to prepare deeprepo for product layer (PR review agent, vertical products)
**Agents:** Claude Code (CTO) + Codex (Senior Engineer)

---

## Part 1: Agent Roles & Behavior

### Claude Code — CTO Role

Claude Code is the technical lead. It does NOT write all the code itself. Its job is to:

1. **Read the current scratchpad** (`SCRATCHPAD_CTO.md`) to understand where we are.
2. **Review completed work** from Codex by examining the codebase and test results.
3. **Produce a task prompt** for Codex — a precise, self-contained specification for the next unit of work.
4. **Run tests** after Codex's work is merged to verify correctness.
5. **Update the CTO scratchpad** with status, decisions, and next steps.

Claude Code should NEVER start coding a task without first checking the scratchpad. If the scratchpad doesn't exist yet, create it from the template in Part 3.

**After each review cycle, Claude Code produces:**

```
## Codex Task: [ISSUE_NUMBER] — [SHORT_TITLE]

### Context
[1-2 sentences: what this issue is and why it matters]

### Files to Modify
- `src/file.py` — [what changes needed]
- `tests/test_file.py` — [what tests to add]

### Specification
[Detailed spec: function signatures, logic flow, edge cases]

### Acceptance Criteria
- [ ] [Specific testable outcome 1]
- [ ] [Specific testable outcome 2]
- [ ] [Specific testable outcome 3]

### Anti-Patterns (Do NOT)
- [Thing to avoid 1]
- [Thing to avoid 2]

### Test Commands
```bash
[exact commands to verify the work]
```

### When Done
Update SCRATCHPAD_CODEX.md with:
- What you implemented (files changed, approach taken)
- Any deviations from the spec and why
- Any issues or questions encountered
- Test results (paste output)
```

### Codex — Senior Engineer Role

Codex receives task prompts from Claude Code CTO and executes them. Its job is to:

1. **Read `SCRATCHPAD_CODEX.md`** to see if there's a pending task or context from previous work.
2. **Read the task prompt** provided by Claude Code.
3. **Implement the changes** according to the specification.
4. **Run tests** to verify the implementation works.
5. **Update `SCRATCHPAD_CODEX.md`** with what was done, test results, and any questions.

**After each task, Codex produces a handoff report in `SCRATCHPAD_CODEX.md`:**

```
## Completed: [ISSUE_NUMBER] — [SHORT_TITLE]

### What I Did
- [File changed]: [What changed and why]
- [File changed]: [What changed and why]

### Test Results
```
[Paste test output here]
```

### Deviations from Spec
- [Any changes from the original task prompt and reasoning]

### Questions / Blockers
- [Anything CTO needs to decide or clarify]

### Status
[DONE | NEEDS_REVIEW | BLOCKED]
```

---

## Part 2: Scratchpad Protocol

Both agents communicate through scratchpad files in the project root. These files persist across sessions and serve as the shared memory between agents.

### File: `SCRATCHPAD_CTO.md`

The CTO's working document. Contains:

```markdown
# CTO Scratchpad — deeprepo Infrastructure Sprint

## Current Sprint Status
- **Last Updated:** [date/time]
- **Current Issue:** #[N] — [title]
- **Phase:** [PLANNING | TASK_SENT | REVIEWING | DONE]
- **Issues Completed:** [list]
- **Issues Remaining:** [list]

## Current Task
[The task prompt currently sent to Codex, or "awaiting Codex handoff"]

## Review Notes
[Notes from reviewing Codex's completed work — what passed, what needs fixes]

## Decisions Made This Sprint
- [Decision 1 and rationale]
- [Decision 2 and rationale]

## Open Questions
- [Question 1]
```

### File: `SCRATCHPAD_CODEX.md`

The engineer's working document. Contains:

```markdown
# Codex Scratchpad — deeprepo Infrastructure Sprint

## Current Status
- **Last Updated:** [date/time]
- **Current Task:** [ISSUE_NUMBER] — [title] | IDLE
- **Status:** [IN_PROGRESS | DONE | BLOCKED]

## Latest Handoff
[The completed task report — see format above]

## Running Context
- [Any context that carries across tasks, e.g., "retry decorator is in src/utils.py"]
- [Patterns established, e.g., "all new CLI flags follow the argparse pattern in cli.py"]
```

### Rules for Scratchpad Communication

1. **Always read before writing.** Both agents must read their own scratchpad and the other agent's scratchpad before doing anything.
2. **Never delete history.** Append new entries, don't overwrite old ones. Use `---` separators between entries.
3. **Timestamps matter.** Always include a timestamp on status updates so the other agent knows what's fresh.
4. **Be specific.** "It works" is not useful. "All 9 existing tests pass + 3 new tests added, `pytest tests/ -v` output below" is useful.
5. **Flag blockers immediately.** If Codex hits something that requires a CTO decision, set status to BLOCKED and describe the decision needed.

---

## Part 3: Cold Start Prompts

Use these prompts when starting a fresh session (new context window) for either agent. They provide enough context to resume work without re-reading the entire project history.

### Cold Start: Claude Code CTO

```
You are acting as CTO for the deeprepo project — an open-source codebase analysis tool
that uses the Recursive Language Model (RLM) pattern to orchestrate multi-model AI analysis.
A root LLM (Claude Sonnet 4.5) writes Python in a REPL loop, dispatching focused tasks to
cheap sub-LLM workers (MiniMax M2.5 via OpenRouter) for file-level analysis.

Repo: ~/Desktop/Projects/deeprepo/ (github.com/Leonwenhao/deeprepo)
Key files: src/llm_clients.py, src/rlm_scaffold.py, src/baseline.py, src/cli.py, src/prompts.py

You are coordinating an infrastructure sprint with Codex (senior engineer). Your job:
1. Read SCRATCHPAD_CTO.md and SCRATCHPAD_CODEX.md to see current status
2. If Codex completed work: review it, run tests, approve or request fixes
3. If ready for next task: read ENGINEERING_SPRINT.md for the issue spec, produce a
   task prompt for Codex
4. Update SCRATCHPAD_CTO.md with your decisions and status

The sprint covers 6 issues in this order:
#4 (retry logic) → #5 (asyncio fix) → #7 (sub-model flag) → #6 (tool_use parser) →
#15 (streaming) → #14 (caching)

Read both scratchpads now and tell me where we are.
```

### Cold Start: Codex Senior Engineer

```
You are a senior engineer working on deeprepo — an open-source codebase analysis tool.
The project uses the RLM pattern: a root LLM writes Python in a REPL, dispatching tasks
to cheap sub-LLM workers.

Repo structure:
- src/llm_clients.py — API wrappers (Anthropic root + OpenRouter sub-LLM)
- src/rlm_scaffold.py — Core RLM engine (REPL loop, code extraction, exec)
- src/baseline.py — Single-model comparison
- src/cli.py — CLI entry point (argparse)
- src/prompts.py — System prompts for root and sub-LLMs
- tests/test_extract_code.py — 9 pytest tests for code extraction

Your CTO (Claude Code) coordinates your work via scratchpads.

1. Read SCRATCHPAD_CODEX.md for your current task and any context from previous work
2. Read SCRATCHPAD_CTO.md for the latest task prompt from your CTO
3. Execute the task according to the spec
4. Run tests to verify
5. Update SCRATCHPAD_CODEX.md with your handoff report

Start by reading both scratchpads to see what's assigned to you.
```

### Recovery Prompt (for either agent when context is getting tight)

```
Context window is getting tight. Before continuing:
1. Read SCRATCHPAD_CTO.md and SCRATCHPAD_CODEX.md
2. Summarize where we are in 3 sentences
3. Identify the single next action needed
4. Do that action and update your scratchpad

Reference ENGINEERING_SPRINT.md for full issue specs if needed.
```

---

## Part 4: The Sprint — Issue Specifications

### Issue Priority Order

| Order | Issue | Title | Complexity | Est. Time |
|:-----:|:-----:|-------|:----------:|:---------:|
| 1 | #4 | Retry logic with exponential backoff | Low-Medium | 2-3 hours |
| 2 | #5 | asyncio.run() fix for existing event loops | Low | 1-2 hours |
| 3 | #7 | Configurable sub-LLM model (--sub-model) | Low | 1-2 hours |
| 4 | #6 | Replace code parser with tool_use | Medium-High | 4-6 hours |
| 5 | #15 | Streaming support for root model | Medium | 2-3 hours |
| 6 | #14 | Content-hash caching for sub-LLM | Medium | 3-4 hours |

---

### ISSUE #4 — Retry Logic with Exponential Backoff

**Problem:** A single transient API error (500, timeout, rate limit) kills the entire analysis mid-run. All root model work up to that point is lost. No retry logic exists anywhere in the codebase.

**Location:** `src/llm_clients.py` — all three client classes (`RootModelClient`, `OpenRouterRootClient`, `SubModelClient`)

**Why it matters:** On long-running analyses costing $1-5, a transient API blip at turn 4 wastes the entire run. This is the #1 reliability issue for any product built on top.

**Specification:**

Create a retry decorator or utility function that wraps all API calls. The implementation should live in a new file `src/utils.py` so it can be reused across the codebase.

```python
# src/utils.py

import time
import random
from functools import wraps

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 30.0  # seconds
JITTER_FACTOR = 0.5  # random jitter up to 50% of delay

# Retryable error conditions:
# - HTTP 429 (rate limit) — always retry
# - HTTP 500, 502, 503, 504 (server errors) — always retry
# - Connection errors (timeout, connection reset) — always retry
# - HTTP 400, 401, 403 — NEVER retry (client error, won't help)

def retry_with_backoff(max_retries=MAX_RETRIES, base_delay=BASE_DELAY):
    """Decorator that retries a function with exponential backoff + jitter."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e
                    if attempt == max_retries:
                        raise
                    delay = min(base_delay * (2 ** attempt), MAX_DELAY)
                    jitter = random.uniform(0, JITTER_FACTOR * delay)
                    total_delay = delay + jitter
                    # Log the retry (use verbose flag from client if available)
                    print(f"[RETRY] Attempt {attempt + 1}/{max_retries} failed: {e}")
                    print(f"[RETRY] Retrying in {total_delay:.1f}s...")
                    time.sleep(total_delay)
            raise last_exception
        return wrapper
    return decorator

# Also create an async version for batch() calls:
async def async_retry_with_backoff(coro_func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Async retry wrapper for individual sub-LLM calls within batch()."""
    # Same logic but uses asyncio.sleep instead of time.sleep
```

Apply the retry decorator to these methods:

1. `RootModelClient.complete()` — wraps the `self.client.messages.create()` call
2. `OpenRouterRootClient.complete()` — wraps the `self.client.chat.completions.create()` call
3. `SubModelClient.query()` — wraps the sync OpenRouter call
4. `SubModelClient.batch()` — wrap each individual async call within the batch (not the whole batch), so one failed sub-call doesn't kill the other parallel calls

For the Anthropic SDK, retryable exceptions include `anthropic.APIStatusError` (check status_code), `anthropic.APIConnectionError`, `anthropic.APITimeoutError`. For the OpenAI SDK (OpenRouter), retryable exceptions include `openai.APIStatusError`, `openai.APIConnectionError`, `openai.APITimeoutError`.

**Acceptance Criteria:**

- [ ] New file `src/utils.py` with `retry_with_backoff` decorator and async equivalent
- [ ] All four API call methods use the retry decorator
- [ ] Retry only on transient errors (429, 5xx, timeout, connection) — not on 400/401/403
- [ ] Exponential backoff with jitter (not fixed delays)
- [ ] Retry attempts are logged to stderr with attempt count and delay
- [ ] Existing tests still pass (`pytest tests/test_extract_code.py -v`)
- [ ] New test: `tests/test_retry.py` with at least 3 tests (retry on 500, no retry on 400, max retries exceeded)

**Anti-Patterns:**

- Do NOT retry on authentication errors (401) — it will never succeed and wastes time
- Do NOT wrap the entire `batch()` method in retry — retry individual calls within the batch so one failure doesn't restart all parallel calls
- Do NOT use `tenacity` library — keep it dependency-free with a simple decorator
- Do NOT add retry to `_execute_code()` or any non-API function

**Test Commands:**

```bash
pytest tests/test_extract_code.py -v  # existing tests still pass
pytest tests/test_retry.py -v         # new retry tests pass
python -c "from src.utils import retry_with_backoff; print('Import OK')"
```

---

### ISSUE #5 — asyncio.run() Fix for Existing Event Loops

**Problem:** `SubModelClient.batch()` calls `asyncio.run()` which raises `RuntimeError: This event loop is already running` when deeprepo is called from Jupyter, FastAPI, or any async context.

**Location:** `src/llm_clients.py` — `SubModelClient.batch()` method (around line 310)

**Why it matters:** The PR review agent will run inside an async web handler (GitHub webhook). This must work in async contexts.

**Specification:**

Replace the current `asyncio.run(_run_batch())` call with a pattern that detects whether an event loop is already running and handles both cases.

```python
# In SubModelClient.batch():

def batch(self, prompts, system=None, max_tokens=4096, max_concurrent=5):
    """Send multiple prompts in parallel. Works in both sync and async contexts."""

    async def _run_batch():
        # ... existing batch logic with semaphore ...
        pass

    # Detect if we're already in an async context
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        # No event loop running — safe to use asyncio.run()
        return asyncio.run(_run_batch())
    else:
        # Already in async context — run in a thread to avoid conflict
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _run_batch())
            return future.result()
```

This approach avoids the `nest_asyncio` dependency and works in all contexts: plain Python scripts, Jupyter notebooks, FastAPI handlers, and pytest-asyncio tests.

**Acceptance Criteria:**

- [ ] `SubModelClient.batch()` works when called from synchronous code (current behavior preserved)
- [ ] `SubModelClient.batch()` works when called from within an existing event loop (Jupyter, FastAPI)
- [ ] No new dependencies added (no `nest_asyncio`)
- [ ] Existing tests still pass
- [ ] New test: `tests/test_async_batch.py` — test batch() inside an `asyncio.run()` wrapper to simulate async context

**Anti-Patterns:**

- Do NOT add `nest_asyncio` as a dependency — it monkey-patches asyncio and causes subtle bugs
- Do NOT make `batch()` an async method — the callers (including exec'd code from the root model) are synchronous
- Do NOT change the public API signature of `batch()`

**Test Commands:**

```bash
pytest tests/test_extract_code.py -v
pytest tests/test_async_batch.py -v
python -c "
import asyncio
from src.llm_clients import SubModelClient, TokenUsage
# This should NOT raise RuntimeError
async def test():
    usage = TokenUsage()
    client = SubModelClient(usage)
    # We can't actually call the API in CI, but we can verify the method exists
    print('batch() exists and is callable:', callable(client.batch))
asyncio.run(test())
print('Async context test passed')
"
```

---

### ISSUE #7 — Configurable Sub-LLM Model (--sub-model flag)

**Problem:** The sub-LLM model is hardcoded to `minimax/minimax-m2.5`. Users cannot swap to DeepSeek, Llama, Qwen, or other OpenRouter models without editing source code.

**Location:** `src/llm_clients.py` (SubModelClient constructor), `src/cli.py` (argparse), `src/rlm_scaffold.py` (run_analysis)

**Why it matters:** Model-agnostic orchestration is the core pitch. Hardcoding a single sub-LLM undermines the narrative and limits users.

**Specification:**

1. **Add `SUB_MODEL_PRICING` dict to `src/llm_clients.py`:**

```python
SUB_MODEL_PRICING = {
    "minimax/minimax-m2.5": {"input": 0.20, "output": 1.10},
    "deepseek/deepseek-chat-v3-0324": {"input": 0.14, "output": 0.28},
    "qwen/qwen-2.5-coder-32b-instruct": {"input": 0.20, "output": 0.20},
    "meta-llama/llama-3.3-70b-instruct": {"input": 0.39, "output": 0.39},
    "google/gemini-2.0-flash-001": {"input": 0.10, "output": 0.40},
}

# Default sub-model
DEFAULT_SUB_MODEL = "minimax/minimax-m2.5"
```

2. **Update `SubModelClient.__init__`** to accept a `model` parameter and look up pricing dynamically. If the model isn't in the pricing dict, use a fallback pricing of $1.00/$1.00 per M tokens and print a warning.

3. **Update `TokenUsage`** to use dynamic pricing passed in from the client rather than hardcoded constants.

4. **Add `--sub-model` flag to CLI** (`src/cli.py`):

```bash
deeprepo analyze ./repo --sub-model deepseek/deepseek-chat-v3-0324
deeprepo compare ./repo --sub-model qwen/qwen-2.5-coder-32b-instruct
```

5. **Thread the sub-model selection** through `run_analysis()` and `run_baseline()` to the `SubModelClient` constructor.

6. **Add `--list-models` command** that prints available sub-models with pricing.

**Acceptance Criteria:**

- [ ] `--sub-model` flag works on `analyze`, `baseline`, and `compare` commands
- [ ] Default behavior unchanged (uses minimax/minimax-m2.5 when no flag provided)
- [ ] Cost tracking uses correct pricing for the selected sub-model
- [ ] Unknown models accepted with a warning and fallback pricing
- [ ] `deeprepo --list-models` prints available models and pricing
- [ ] Existing tests still pass

**Anti-Patterns:**

- Do NOT add model aliases for sub-models (unlike root models which have `sonnet`/`opus` aliases) — keep it simple, use full OpenRouter model strings
- Do NOT validate that the model actually exists on OpenRouter — just pass it through and let the API error if it's wrong
- Do NOT change the default sub-model from minimax/minimax-m2.5

**Test Commands:**

```bash
pytest tests/test_extract_code.py -v
python -m src.cli --list-models
python -m src.cli analyze --help  # should show --sub-model in help text
```

---

### ISSUE #6 — Replace Fragile Code Parser with Structured Output (tool_use)

**Problem:** `_extract_code()` is ~130 lines of fragile regex heuristics for parsing markdown code blocks. Sonnet's code generation discipline gap (prose in code blocks, double fences) causes wasted turns and failed executions. This is the most brittle part of the codebase.

**Location:** `src/rlm_scaffold.py` — `_extract_code()`, `_is_prose_line()`, `_split_wrapped_blocks()`, `_extract_inner_fences()`

**Why it matters:** This is the #1 source of wasted API spend. Every failed parse means a wasted root model turn at $0.05-0.50 each. Structured output eliminates the entire class of parsing bugs.

**Specification:**

This is the largest change in the sprint. The approach: instead of having the root model respond with markdown containing code blocks (which we then parse), we use Anthropic's `tool_use` feature to have the root model return code in a structured schema.

**Step 1: Define the tool schema**

```python
# In src/rlm_scaffold.py or a new src/tools.py

EXECUTE_CODE_TOOL = {
    "name": "execute_python",
    "description": "Execute Python code in the REPL environment. The code has access to: codebase (dict of filepath→content), file_tree (string), metadata (dict), llm_query(prompt) → str, llm_batch(prompts) → list[str], and answer (dict with 'content' and 'ready' keys).",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute in the REPL. Must be valid Python. Do not use markdown fencing."
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of what this code does and why (1-2 sentences)."
            }
        },
        "required": ["code"]
    }
}
```

**Step 2: Modify the root model call**

Update `RLMEngine.analyze()` to pass the tool definition in the Anthropic API call:

```python
response = self.root_client.complete(
    messages=messages,
    system=ROOT_SYSTEM_PROMPT,
    tools=[EXECUTE_CODE_TOOL],
    # Let the model choose: it can use the tool or respond with text
)
```

**Step 3: Parse the response for tool calls**

The Anthropic API returns a response with `content` blocks. Each block is either `type: "text"` or `type: "tool_use"`. Extract code from tool_use blocks:

```python
def _extract_code_from_response(self, response):
    """Extract code from tool_use blocks in the response.
    Falls back to legacy _extract_code() for text-only responses."""
    code_blocks = []
    text_parts = []

    for block in response.content:
        if block.type == "tool_use" and block.name == "execute_python":
            code_blocks.append(block.input["code"])
        elif block.type == "text":
            text_parts.append(block.text)

    if code_blocks:
        return code_blocks

    # Fallback: if model responded with text only (no tool use),
    # use legacy parser. This handles edge cases and ensures
    # backward compatibility.
    full_text = "\n".join(text_parts)
    return self._extract_code(full_text)
```

**Step 4: Handle tool_result messages**

After executing code, send the result back as a `tool_result` message:

```python
# After executing code from a tool_use block:
messages.append({"role": "assistant", "content": response.content})
messages.append({
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": block.id,  # from the tool_use block
            "content": repl_output
        }
    ]
})
```

**Step 5: Update the system prompt**

Modify `ROOT_SYSTEM_PROMPT` in `src/prompts.py` to tell the model to use the `execute_python` tool instead of writing code in markdown blocks. Keep the prompt backward-compatible — mention that the tool is preferred but markdown code blocks are also accepted.

**Step 6: Keep legacy parser as fallback**

Do NOT delete `_extract_code()` and related functions. Keep them as a fallback for when the model responds with text instead of tool_use (which can happen, especially with non-Anthropic root models via OpenRouter). The tool_use path is the happy path; the legacy parser is the safety net.

**Step 7: Update `RootModelClient.complete()`**

The `complete()` method needs to accept an optional `tools` parameter and pass it to the Anthropic API. It should return the full response object (not just text) when tools are provided, so the caller can inspect content blocks.

```python
def complete(self, messages, system, max_tokens=8192, temperature=0.0, tools=None):
    kwargs = {
        "model": self.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
    response = self.client.messages.create(**kwargs)
    # Update token tracking
    self.usage.root_input_tokens += response.usage.input_tokens
    self.usage.root_output_tokens += response.usage.output_tokens
    self.usage.root_calls += 1
    return response  # Return full response, not just text
```

**Important:** This changes the return type of `complete()` when tools are provided. Update all callers in `rlm_scaffold.py` to handle the response object instead of a plain string. The `baseline.py` caller does NOT use tools, so it should continue to work with the text-only path.

**Acceptance Criteria:**

- [ ] Root model calls include the `execute_python` tool definition
- [ ] Code is extracted from `tool_use` blocks when present
- [ ] Legacy `_extract_code()` is preserved as fallback for text-only responses
- [ ] Tool results are sent back correctly as `tool_result` messages
- [ ] System prompt updated to prefer tool_use over markdown code blocks
- [ ] `RootModelClient.complete()` accepts optional `tools` parameter
- [ ] `OpenRouterRootClient.complete()` also updated (OpenAI SDK has different tool format — adapt accordingly)
- [ ] All 9 existing `_extract_code` tests still pass (legacy parser preserved)
- [ ] New test: verify `_extract_code_from_response()` correctly extracts from mock tool_use blocks
- [ ] Baseline mode (`src/baseline.py`) still works without tools

**Anti-Patterns:**

- Do NOT delete the legacy code parser — it's the fallback
- Do NOT force `tool_use` via `tool_choice: "required"` — let the model choose, handle both paths
- Do NOT change the baseline flow — baseline doesn't use the REPL loop
- Do NOT add tool definitions for `llm_query` or `llm_batch` — those are REPL functions, not root model tools

**Test Commands:**

```bash
pytest tests/test_extract_code.py -v  # all 9 legacy tests still pass
pytest tests/test_tool_use.py -v      # new tool_use extraction tests
```

---

### ISSUE #15 — Streaming Support for Root Model Responses

**Problem:** Root model calls take 30-60 seconds with zero user feedback. The tool feels broken during long waits.

**Location:** `src/llm_clients.py` — `RootModelClient.complete()`

**Why it matters:** Table stakes for any user-facing product. Users need to see the model is working.

**Specification:**

Add streaming support to `RootModelClient.complete()` using the Anthropic streaming API.

```python
def complete(self, messages, system, max_tokens=8192, temperature=0.0, tools=None, stream=False):
    kwargs = {
        "model": self.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools

    if stream and self.verbose:
        # Use streaming API — show tokens in real-time
        collected_text = []
        with self.client.messages.stream(**kwargs) as stream_response:
            for text in stream_response.text_stream:
                sys.stderr.write(text)  # Real-time display on stderr
                collected_text.append(text)
            sys.stderr.write("\n")  # Newline after stream
            response = stream_response.get_final_message()
    else:
        response = self.client.messages.create(**kwargs)

    # Token tracking (same for both paths)
    self.usage.root_input_tokens += response.usage.input_tokens
    self.usage.root_output_tokens += response.usage.output_tokens
    self.usage.root_calls += 1
    return response
```

**Important considerations:**

1. Streaming should be controlled by the `verbose` flag — quiet mode should not stream.
2. Stream to `stderr` not `stdout` — stdout may be captured for the analysis output.
3. When tools are in use AND streaming is enabled, the Anthropic SDK handles tool_use blocks differently in streaming mode. Test that tool_use blocks are correctly assembled from the stream. The `stream_response.get_final_message()` should handle this, but verify.
4. The `RLMEngine.analyze()` loop should pass `stream=True` by default when `self.verbose` is True.

**Acceptance Criteria:**

- [ ] Root model responses stream tokens to stderr in verbose mode
- [ ] Non-verbose mode unchanged (no streaming output)
- [ ] Tool_use responses work correctly with streaming enabled
- [ ] Token tracking is accurate (uses final message usage, not stream estimates)
- [ ] Existing tests still pass
- [ ] The `--quiet` CLI flag disables streaming

**Anti-Patterns:**

- Do NOT stream to stdout — it would mix with the analysis output
- Do NOT add streaming to sub-LLM calls (they're fast and parallel — no benefit)
- Do NOT add the `rich` library yet — plain stderr output is fine for now

**Test Commands:**

```bash
pytest tests/test_extract_code.py -v
# Manual test: run a small analysis in verbose mode and verify streaming output appears
```

---

### ISSUE #14 — Content-Hash Caching for Sub-LLM Results

**Problem:** Analyzing the same repo twice re-runs all sub-LLM calls from scratch. Unchanged files produce identical results, wasting time and money.

**Location:** New file `src/cache.py`, modifications to `src/llm_clients.py` (`SubModelClient`)

**Why it matters:** For the PR review agent use case, most files in a repo don't change between PRs. Caching means a PR touching 3 files in a 300-file repo only runs 3 sub-LLM calls instead of 300.

**Specification:**

Create a file-based cache system that stores sub-LLM results keyed by the hash of the input (file content + prompt).

```python
# src/cache.py

import hashlib
import json
import os
import time

CACHE_DIR = os.path.expanduser("~/.cache/deeprepo")
CACHE_EXPIRY_DAYS = 7

def _cache_key(prompt: str, system: str | None, model: str) -> str:
    """Generate a cache key from the prompt, system message, and model."""
    content = f"{model}||{system or ''}||{prompt}"
    return hashlib.sha256(content.encode()).hexdigest()

def get_cached(prompt: str, system: str | None, model: str) -> str | None:
    """Return cached result if it exists and hasn't expired."""
    key = _cache_key(prompt, system, model)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, 'r') as f:
            data = json.load(f)

        # Check expiry
        if time.time() - data["timestamp"] > CACHE_EXPIRY_DAYS * 86400:
            os.remove(cache_file)
            return None

        return data["result"]
    except (json.JSONDecodeError, KeyError, OSError):
        return None

def set_cached(prompt: str, system: str | None, model: str, result: str):
    """Store a result in the cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = _cache_key(prompt, system, model)
    cache_file = os.path.join(CACHE_DIR, f"{key}.json")

    data = {
        "timestamp": time.time(),
        "model": model,
        "prompt_hash": key,
        "result": result
    }

    with open(cache_file, 'w') as f:
        json.dump(data, f)

def clear_cache():
    """Delete all cached results."""
    import shutil
    if os.path.exists(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)
        print(f"Cleared cache at {CACHE_DIR}")

def cache_stats() -> dict:
    """Return cache statistics."""
    if not os.path.exists(CACHE_DIR):
        return {"entries": 0, "size_mb": 0}
    files = os.listdir(CACHE_DIR)
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    return {"entries": len(files), "size_mb": round(total_size / 1024 / 1024, 2)}
```

**Integrate with SubModelClient:**

```python
# In SubModelClient.query():
def query(self, prompt, system=None, max_tokens=4096, use_cache=True):
    if use_cache:
        cached = get_cached(prompt, system, self.model)
        if cached is not None:
            if self.verbose:
                print("[CACHE HIT] Skipping sub-LLM call", file=sys.stderr)
            return cached

    # ... existing API call logic ...
    result = response.choices[0].message.content

    if use_cache:
        set_cached(prompt, system, self.model, result)

    return result
```

**CLI integration:**

```bash
deeprepo analyze ./repo                    # uses cache (default)
deeprepo analyze ./repo --no-cache         # bypasses cache
deeprepo cache clear                       # clears all cached results
deeprepo cache stats                       # shows cache entries and size
```

**Acceptance Criteria:**

- [ ] New file `src/cache.py` with get/set/clear/stats functions
- [ ] `SubModelClient.query()` checks cache before making API calls
- [ ] `SubModelClient.batch()` checks cache for each individual prompt
- [ ] Cache key includes model name (different models = different cache entries)
- [ ] `--no-cache` CLI flag bypasses all caching
- [ ] `deeprepo cache clear` and `deeprepo cache stats` commands work
- [ ] Cache files stored in `~/.cache/deeprepo/` with 7-day expiry
- [ ] Existing tests still pass
- [ ] New test: `tests/test_cache.py` — test cache hit, miss, expiry, and clear

**Anti-Patterns:**

- Do NOT cache root model results — only sub-LLM results (root model context changes every turn)
- Do NOT use a database — simple JSON files keyed by hash are sufficient for V0
- Do NOT cache failed results (error strings starting with "[ERROR:")
- Do NOT make caching mandatory — always respect `--no-cache`

**Test Commands:**

```bash
pytest tests/test_extract_code.py -v
pytest tests/test_cache.py -v
python -m src.cli cache stats
```

---

## Part 5: Sprint Execution Workflow

This is the step-by-step process Leon follows to execute the sprint.

### Step 1: Initialize Scratchpads

Before the first Claude Code session, create two empty scratchpad files in the repo root:

```bash
touch SCRATCHPAD_CTO.md SCRATCHPAD_CODEX.md
```

### Step 2: First Claude Code Session

Paste the **CTO Cold Start Prompt** from Part 3. Claude Code will read this document, read the scratchpads (empty), and produce the first Codex task prompt for Issue #4 (retry logic).

### Step 3: First Codex Session

Paste the **Codex Cold Start Prompt** from Part 3, followed by the task prompt that Claude Code produced. Codex implements the task, runs tests, and writes its handoff report to `SCRATCHPAD_CODEX.md`.

### Step 4: Review Cycle

Return to Claude Code. It reads Codex's scratchpad, reviews the work, runs tests, and either approves (moves to next issue) or requests fixes (sends a fix task to Codex).

### Step 5: Repeat

Continue the cycle: CTO reviews → sends task → Codex implements → writes handoff → CTO reviews → next issue.

### Step 6: Context Window Recovery

When either agent's context is getting tight, use the **Recovery Prompt** from Part 3. The agent will read the scratchpads, summarize status, and continue from where it left off.

---

## Part 6: Definition of Done for the Sprint

The sprint is complete when:

1. All 6 issues have been implemented and reviewed by CTO.
2. All existing tests pass (`pytest tests/test_extract_code.py -v`).
3. All new tests pass (`pytest tests/ -v`).
4. The CLI help text shows the new flags (`--sub-model`, `--no-cache`, `--list-models`).
5. A clean `git diff --stat` shows the changes are scoped to the right files.
6. CTO has committed all changes to the `main` branch with descriptive commit messages.

After the sprint, Leon and Claude (main chat) will review the updated codebase and plan the product layer sprint (PR review agent).

---

*End of sprint document. This file should live at the repo root alongside the scratchpad files.*
