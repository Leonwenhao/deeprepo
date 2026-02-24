# CTO Audit: deeprepo Engine + TUI Infrastructure Review

## Your Role

You are acting as CTO for the deeprepo project. This is NOT a feature sprint — this is an infrastructure audit. The goal is to find and document every bug, edge case, and UX gap before we share v0.2.1 with users.

**Repo:** ~/Desktop/Projects/deeprepo/
**Branch:** main
**Version:** 0.2.1

## Why This Audit

During live user testing of v0.2.1, we hit a critical Anthropic API error when running `/init` in the TUI:

```
Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 
'message': 'messages.14: `tool_use` ids were found without `tool_result` blocks 
immediately after: toolu_011Le9TBcfKndX8BbgLTcqjy. Each `tool_use` block must 
have a corresponding `tool_result` block in the next message.'}}
```

This means the core RLM engine (`rlm_scaffold.py`) has a bug in message threading — a `tool_use` block is being added to the conversation without a matching `tool_result`. This is a release-blocking bug.

Additionally, multiple UX issues were found during testing. This audit covers everything.

---

## Phase 1: Core Engine Bug — tool_use/tool_result Mismatch

### The Bug

The Anthropic API requires that every `tool_use` block in an assistant message is followed by a `tool_result` in the next user message. Somewhere in the REPL loop, this contract is violated.

### Where to Look

**File: `deeprepo/rlm_scaffold.py`**

There are THREE code paths that handle message appending after a root model response. Each one is a potential source of the bug:

#### Path 1: "No code blocks" path (lines ~167-181)

```python
if not code_blocks:
    ...
    self._append_assistant_message(messages, response)
    messages.append({"role": "user", "content": "Please use the execute_python tool..."})
    continue
```

**SUSPECTED BUG:** The model can return a response that contains `tool_use` blocks where the `input` dict has no `"code"` key or `code` is not a string. In that case, `_extract_code_from_response` returns empty `code_blocks` and empty `tool_use_info`, but the raw response object STILL contains tool_use content blocks. When `_append_assistant_message` serializes the full response, those tool_use blocks get included. The following user message is plain text — no tool_results. API rejects on the next call.

#### Path 2: "Legacy text" path (lines ~231-240)

```python
else:
    # Text-only path: send as user message (legacy behavior)
    self._append_assistant_message(messages, response)
    messages.append({"role": "user", "content": f"REPL Output:..."})
```

**SUSPECTED BUG:** `_extract_code_from_response` has a fallback at lines ~527-529: if tool_use blocks exist but code extraction filtered them out, it falls back to extracting code from the TEXT parts and returns empty `tool_use_info`. The main loop then takes the legacy path. But `_append_assistant_message` still serializes the full response including any tool_use blocks. Same problem — tool_use without tool_result.

#### Path 3: tool_use path (lines ~226-229)

```python
if tool_use_info:
    self._append_tool_result_messages(messages, response, tool_use_info, all_output)
```

This path SHOULD be correct — `_append_tool_result_messages` appends the assistant message then the tool_results. But verify: does `zip(tool_use_info, outputs)` work correctly if they're different lengths? What happens if execution of one code block raises an exception that prevents subsequent blocks from executing?

### The Fix Pattern

The core principle: **never append a raw response containing tool_use blocks without also appending matching tool_results.** Two approaches:

**Option A (preferred):** In `_append_assistant_message`, strip tool_use blocks from the content when the caller doesn't intend to provide tool_results. Add a parameter like `strip_tool_use=False` and when True, only include text blocks in the serialized message.

**Option B:** In the "no code blocks" path, check if the response contains tool_use blocks. If it does, generate empty/error tool_results for each one before appending the "please use the tool" user message.

### Verification

After fixing, run this test scenario:
1. `deeprepo init .` on any local project — should complete without API errors
2. Run the existing test suite: `python -m pytest tests/ -v`
3. If possible, add a unit test that constructs a mock response with tool_use blocks where the input has no "code" key, feeds it through the engine's message handling, and verifies the resulting messages list has proper tool_use/tool_result pairing.

---

## Phase 2: TUI UX Bugs Found During Testing

### Bug 2.1: Rich markup leak in ASCII banner

**Screenshot evidence:** The ASCII art banner shows literal `[/bold magenta]` text next to the logo. A Rich closing tag is not being processed — it's being printed as raw text.

**File:** `deeprepo/tui/shell.py`, `_print_welcome` method

**What to check:** Look at how the ASCII art string is constructed. The Rich markup tags might be malformed (wrong nesting, extra bracket, missing opening tag). Print the raw string and verify every `[tag]` has a matching `[/tag]`. Check for line wrapping issues where a tag gets split across lines.

**Fix:** Correct the markup. Test by running `deeprepo` and visually confirming no raw markup tags are visible.

### Bug 2.2: No loading indicator during `/init`

**The problem:** When the user runs `/init`, the TUI calls `cmd_init(args, quiet=True)`. The `quiet=True` suppresses ALL progress output from the RLM engine. The analysis takes 2-5 minutes. During that time, the TUI appears completely frozen — no spinner, no "Working...", nothing. The user doesn't know if it's running or crashed.

**File:** `deeprepo/tui/command_router.py`, `_do_init` method
**File:** `deeprepo/tui/shell.py`, `_handle_slash_command` method

**Fix approach:** Before calling `cmd_init`, show a spinner or "Analyzing project..." message. Options:
- Use Rich's `console.status("Analyzing project...")` as a context manager around the `cmd_init` call
- Or use `threading` to run cmd_init in a background thread while showing a Rich spinner on the main thread
- Simplest viable: print "Analyzing project... this may take a few minutes" before the call, then show the result after. Not ideal but unblocks the frozen-screen problem.

The spinner approach is preferred since Rich already provides `console.status()`. Example:

```python
from rich.console import Console
console = Console()

def _do_init(self, tokens):
    from deeprepo.cli_commands import cmd_init
    # ... force logic ...
    with console.status("[cyan]Analyzing project...[/cyan]", spinner="dots"):
        return cmd_init(args, quiet=True)
```

**Important:** The `console.status` spinner runs on the same thread. Since `cmd_init` is synchronous (it blocks until analysis completes), this should work — Rich's status context manager handles the spinner animation in a background thread automatically.

Apply the same pattern to `/refresh` which also runs analysis.

### Bug 2.3: Onboarding only asks for OpenRouter key, not Anthropic

**The problem:** `deeprepo/tui/onboarding.py` checks for `OPENROUTER_API_KEY` and prompts if missing. But the root model requires `ANTHROPIC_API_KEY`. If the user has OpenRouter set but not Anthropic, `/init` fails with "ANTHROPIC_API_KEY not set."

**File:** `deeprepo/tui/onboarding.py`

**Fix:** Add Anthropic key check to `needs_onboarding()` and `run_onboarding()`:
- Check both `OPENROUTER_API_KEY` and `ANTHROPIC_API_KEY`
- Prompt for both during onboarding if missing
- Save Anthropic key to `~/.deeprepo/config.yaml` alongside the OpenRouter key
- Load both on startup

Update the onboarding flow to explain what each key is for:
- "Anthropic API key (root model — the orchestrator): https://console.anthropic.com/settings/keys"
- "OpenRouter API key (sub-LLM workers — cheap analysis): https://openrouter.ai/keys"

### Bug 2.4: `/init` error message is not user-friendly

When `/init` fails (API error, missing key, etc.), the TUI shows the raw Python exception in a red panel. For example: `Error: Command failed: ANTHROPIC_API_KEY not set. Add it to your .env file or export it as an environment variable.`

The `.env file` reference is wrong for TUI users — they should be told to set it as an environment variable or provide it during onboarding. 

**File:** `deeprepo/cli_commands.py`, error messages referencing `.env`
**File:** `deeprepo/tui/command_router.py`, error handling in `_do_init`

**Fix:** The TUI's `_do_init` wrapper should catch common errors and rewrite them:
- Missing ANTHROPIC_API_KEY → "Anthropic API key not set. Run: export ANTHROPIC_API_KEY=sk-ant-..."
- Missing OPENROUTER_API_KEY → "OpenRouter API key not set. Run: export OPENROUTER_API_KEY=sk-or-..."
- API rate limit errors → "API rate limited. Wait a moment and try again."
- Network errors → "Network error. Check your internet connection."

---

## Phase 3: Audit the Engine Under Stress

Beyond the specific bug above, do a systematic audit of `rlm_scaffold.py` for edge cases:

### 3.1 Message history integrity

Read through the entire REPL loop (lines ~139-257) and trace EVERY path that modifies the `messages` list. For each path, verify:
- Every assistant message with tool_use blocks is followed by tool_results
- No duplicate messages are appended
- Message roles alternate correctly (user → assistant → user → ...)

### 3.2 Error handling in code execution

Check `_execute_code`: what happens when:
- The code calls `llm_query()` and the sub-LLM API fails?
- The code runs an infinite loop?
- The code uses `sys.exit()`?
- Memory allocation exceeds limits?

### 3.3 The `set_answer()` function

Check: what happens if the model calls `set_answer()` inside executed code AND also returns more tool_use blocks in the same turn? Does the loop correctly break, or does it try to append more messages after the answer is ready?

### 3.4 Sub-LLM client error handling

**File:** `deeprepo/llm_clients.py`

Check the `batch()` method: if one of N parallel sub-LLM calls fails, does it:
- Return `"[ERROR: ...]"` for that slot (correct)?
- Crash the whole batch (bug)?
- Silently drop the result (bug)?

---

## Deliverables

When the audit is complete, produce a single document: `AUDIT_FINDINGS.md` in the project root.

Structure:

```markdown
# deeprepo v0.2.1 — Infrastructure Audit Findings

## Critical (blocks release)
- [Bug]: [description, root cause, fix approach]

## High (should fix before sharing)
- [Bug]: [description, root cause, fix approach]

## Medium (fix in v0.2.2)
- [Bug]: [description, root cause, fix approach]

## Low (polish / tech debt)
- [Item]: [description]

## Tests to Add
- [Test]: [what it tests, where it goes]
```

For each Critical and High bug, include:
1. **Root cause** — exactly which lines of code are wrong and why
2. **Fix approach** — specific code changes needed
3. **Affected files** — exact file paths
4. **How to verify** — test command or manual test

Do NOT fix anything yet. The goal is a complete findings document that we review before sending fixes to Codex. Read all the files mentioned above, trace the code paths, and document what you find.

## Start

Read these files in order:
1. `deeprepo/rlm_scaffold.py` — full file, trace the REPL loop carefully
2. `deeprepo/llm_clients.py` — error handling, retry logic, batch behavior
3. `deeprepo/tui/shell.py` — the banner markup bug
4. `deeprepo/tui/onboarding.py` — the missing Anthropic key
5. `deeprepo/tui/command_router.py` — the init/refresh UX

Then produce AUDIT_FINDINGS.md.
