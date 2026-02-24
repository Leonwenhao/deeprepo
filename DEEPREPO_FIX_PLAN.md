# DeepRepo v0.2.2 → Production Fix Plan

> **Date:** 2026-02-24
> **Source:** Synthesized from CLAUDE_CODE_DIAGNOSIS.md + CODEX_DIAGNOSIS.md
> **Goal:** Resolve all 6 open GitHub issues and ship a production-ready v0.2.3

---

## Part 1: Agent Comparison — What Each Found

### Where Both Agents Agreed (High Confidence)

Both agents independently confirmed all 6 confirmed findings (CF-1 through CF-6) with no contradictions. The core architecture of the problem is well-understood: the REPL loop has no turn-budget injection, no `tool_choice` forcing, broken fallback logic, and a security-wide-open execution namespace. Both agents identified the same source files and line numbers for every issue, and both agree that #22 and #23 share root causes and should be fixed together.

### Where Codex Was Stronger

Codex ran actual reproduction tests rather than relying purely on static analysis, which matters a lot for a debugging session.

**Reproduction testing (#18):** Codex actually executed `_execute_code("print(open('pyproject.toml').read().splitlines()[0])", ns)` and confirmed it returned `[build-system]`. It also ran `os.system('echo SAFE_DEMO_COMMAND')` through the REPL namespace and confirmed shell command execution. Claude Code described the vulnerability theoretically but didn't prove it live.

**Spy-based verification (#22):** Codex patched the root client's `complete()` method with a spy to capture actual kwargs, confirming `has_tool_choice=False` at runtime. It also checked both the Anthropic SDK and OpenAI SDK signatures to verify that `tool_choice` is supported but simply not being passed through. Claude Code did the grep but didn't verify at the SDK level.

**Retry behavior verification (#20):** Codex patched `openai.OpenAI` to always raise `APITimeoutError` and measured `create_calls=1` (no retry) on `scaffold.py` vs `create_calls=3` (retry) on `llm_clients.py`. This is concrete evidence, not just a code review assertion.

**Critical CI discovery (#19):** Codex found that several test files (`test_baseline.py`, `test_connectivity.py`, `test_rlm_integration.py`) are **script-style modules with top-level execution** — they make live API calls at import time, not inside `def test_*()` functions. This means `pytest -k "not connectivity"` still fails because collection triggers the imports before deselection happens. The only safe approach is `--ignore=` flags. Codex actually ran the test suite and got `202 passed` with the correct exclusion set. Claude Code listed which tests "likely" need exclusion but didn't run them to verify.

**Output contract design (#23):** Codex proposed a proper completion status enum (`completed` / `partial` / `failed`) as the return contract from `run_analysis`, which is architecturally cleaner than Claude Code's approach of string-matching on `[Analysis incomplete` in the output.

### Where Claude Code Was Stronger

**`os` module as independent risk (#18):** Claude Code explicitly called out that even if `__builtins__` is restricted, the `os` module at `rlm_scaffold.py:335` still provides `os.system()`, `os.environ`, `os.remove()` etc. This is an important nuance — restricting builtins alone doesn't close the security hole if `os` remains in the namespace. Codex mentioned removing `os` but didn't emphasize it as a separate attack vector.

**Detailed line-number mapping (#22):** Claude Code traced the exact message construction chain in the REPL loop — initial user prompt (line 138), re-prompt when no code found (lines 182-188), REPL output feedback (lines 246-262) — confirming that none of these injection points include turn context. This level of tracing is useful for the implementation phase.

**`scaffold.py` client instantiation pattern:** Claude Code noted that `scaffold.py` creates a new `openai.OpenAI` client on every `_call_llm()` call (lines 167-169) instead of reusing the client architecture from `llm_clients.py`. This is a minor inconsistency but worth noting for an eventual refactor.

**`_estimate_tons` typo:** Claude Code found a backward-compatible alias `_estimate_tons` in `prompt_builder.py` — a minor code hygiene issue but indicative of spec-driven development without cleanup.

### Where They Disagreed

**Fix order:** Claude Code recommends #22/#23 first (highest user-facing impact), then #20, #18, #21, #19. Codex recommends #18 first (security), then #22/#23, #20, #19, #21. The right answer depends on your priorities — see Part 3 below.

**#18 approach depth:** Codex proposes an AST pre-check before `exec()` to block disallowed nodes (`Import`, `ImportFrom`), which is a deeper defense layer beyond just restricting builtins. Claude Code's approach is builtins-only. The AST check is more robust but adds complexity.

**#21 severity assessment:** Codex flagged a privacy risk with logging — debug logs could leak API keys or sensitive document content if not redacted. Claude Code mentioned the TUI interaction risk (logging to stderr interfering with prompt_toolkit) but didn't flag the data leakage concern. Both are valid risks that need to be addressed in the implementation.

---

## Part 2: The Unified Root Cause Map

The 6 issues decompose into 3 root cause clusters plus 2 independent issues:

**Cluster A — Orchestration Control Gap (Issues #22 + #23, CF-1/2/3/4/5/6)**
The REPL loop gives the model no turn awareness, no forced tool usage, and no graceful degradation. When the model wastes all turns exploring, the fallback writes empty output and shows a success banner. The user pays money and gets nothing. This is the single biggest production blocker.

**Cluster B — Execution Security (Issue #18)**
The REPL namespace is wide open. Model-generated code can read files, access environment variables, spawn processes, and import arbitrary modules. The timeout from Issue #1 prevents long-running attacks but not instant operations. This is the highest-severity vulnerability.

**Independent — Retry Gap (Issue #20)**
One API call path (`scaffold.py`) lacks the retry wrapper every other path uses. Straightforward fix.

**Independent — Observability (Issue #21)**
Zero logging infrastructure across the entire codebase. Silent exception swallowing makes debugging impossible for both developers and users.

**Independent — CI (Issue #19)**
No automated testing despite 27 test files. Script-style test files that make live API calls at import time add a wrinkle.

---

## Part 3: Implementation Plan — All Tasks to Codex

Given that Claude Code's previous debugging rounds had gaps (the first round missed issues #18-21 entirely, and it tends toward theoretical analysis over practical verification), assigning all implementation to Codex is the right call. Codex's reproduction-first approach — actually running code to verify behavior — is exactly what you need for a "ship to production" sprint.

The fix order below prioritizes getting to a production-safe state as fast as possible. Security first (because a security hole in production is worse than a UX bug), then the user-facing critical bugs (because they're losing you users right now), then the quick wins and infrastructure.

### Task 1: Issue #18 — Restrict REPL Namespace (Security)

**Why first:** A security vulnerability that allows model-generated code to exfiltrate API keys or execute shell commands is an existential risk. Every minute this is live in production, you're exposed. Fix it before anything else.

**Scope:**
The task has three parts. First, replace `namespace["__builtins__"] = __builtins__` at `rlm_scaffold.py:340` with a safe builtins allowlist. The allowlist should include data types (`str`, `int`, `float`, `bool`, `list`, `dict`, `set`, `tuple`), iteration helpers (`range`, `enumerate`, `zip`, `map`, `filter`, `sorted`, `reversed`), math (`sum`, `min`, `max`, `abs`, `round`), introspection (`type`, `isinstance`, `hasattr`, `getattr`), output (`print`, `repr`, `format`), and common exceptions. It must exclude `open`, `__import__`, `eval`, `exec`, `compile`, `globals`, `locals`, `breakpoint`, `exit`, `quit`.

Second, replace `"os": __import__("os")` at line 335 with `"os_path": __import__("os").path` — the model uses `os.path.basename()` and `os.path.splitext()` in practice, but never needs `os.system()`, `os.environ`, or `os.remove()`. Injecting only `os.path` closes the gap. Update any prompts that reference `os.xxx` to use `os_path.xxx` instead, or keep the name as `os` but make it point to the path submodule only (check the prompts to decide which is less disruptive).

Third, add an AST pre-check before `exec()` at line 775 to block `Import` and `ImportFrom` nodes. This prevents `__import__("subprocess")` even if it somehow gets through the builtins restriction. This is Codex's recommendation and it's the right defense-in-depth approach.

**Tests to add:** Verify that `open()`, `__import__()`, `eval()`, `exec()`, `os.system()` all raise errors when executed in the restricted namespace. Verify that the safe builtins (`print`, `len`, `range`, `sorted`, `list`, `dict`, etc.) all work normally. Run the existing test suite to confirm no regressions.

**Estimated complexity:** Medium. The allowlist itself is quick, but you need to audit the model's actual code patterns to make sure the allowlist doesn't break legitimate analysis. Run a few `deeprepo init` analyses after the fix to verify.

**Risk:** Over-restricting could degrade analysis quality. The model may use builtins not on the allowlist in rare cases. Mitigate by running 2-3 real analyses after the fix and checking for `NameError` in REPL outputs.

---

### Task 2: Issues #22 + #23 — Turn Budget + Output Salvage (Critical UX)

**Why second:** This is the bug your test users hit. Paying $0.36 and getting an empty file with a success banner is a product-killing experience. These two issues share root causes and must be fixed together.

**Scope — four interlocking changes:**

**2A. Inject turn countdown into model context.** In the REPL loop at `rlm_scaffold.py:142-148`, after incrementing `turn`, construct a turn-context string and prepend it to the tool result or user message sent to the model. Normal turns get a status line like `[Turn 3/15 — 12 turns remaining]`. When 3 turns remain, escalate to a warning: `[Turn 13/15 — ⚠️ 2 turns remaining. Begin synthesizing findings into set_answer().]`. On the final turn, make it unmistakable: `[Turn 15/15 — 🚨 FINAL TURN. You MUST call set_answer() now with your complete analysis. Any findings not included will be lost.]`.

**2B. Add `tool_choice` support to client wrappers and force it on final turns.** Extend `RootModelClient.complete()` at `llm_clients.py:128-136` and `OpenRouterRootClient.complete()` at `llm_clients.py:217-225` to accept an optional `tool_choice` kwarg and pass it through to the SDK. Both the Anthropic SDK and OpenAI SDK already support it (Codex verified this). In the REPL loop, set `tool_choice={"type": "any"}` for the final 2 turns. This forces the model to produce a tool call (which means it must call `execute_python`, which is the only way to call `set_answer()`). For all earlier turns, leave `tool_choice` unset (defaults to `auto`).

**2C. Unify `max_turns` defaults.** Change `rlm_scaffold.py:38` from `MAX_TURNS = 15` to `MAX_TURNS = 20` (matching `config_manager.py:17`). Change `cli.py:358` and `cli.py:367` defaults from `15` to `20`. This eliminates the split-default confusion where `init`/`refresh` get 20 turns but `analyze`/`compare` get 15.

**2D. Salvage partial results and fix the success/failure flow.** When `answer["ready"]` is False after the loop exits at `rlm_scaffold.py:265-272`, instead of just writing the placeholder, collect all `trajectory[*]["repl_output"]` entries that aren't empty or `[No output]` and concatenate them as partial results. Also check if the model's last assistant message contains prose that could serve as a partial analysis. Return a structured result with a `status` field (`completed` / `partial` / `failed`) — this is Codex's cleaner approach.

In `cli_commands.py:118-131`, gate the success banner on `result["status"] == "completed"`. For `partial`, show: `⚠️ Analysis partially complete (X/Y turns used, $Z.ZZ cost). Partial results saved to PROJECT.md. Try: deeprepo init . --force --max-turns 25`. For `failed`, show: `❌ Analysis failed — no results produced. Cost: $Z.ZZ. Try a smaller codebase or increase --max-turns.`. Never show the "Your project now has AI memory" banner unless analysis actually completed.

Fix `_validate_messages()` at `rlm_scaffold.py:579-602` to handle string content `""` — when content is a string and empty, replace with `"[Acknowledged]"` (consistent with the existing list-block handling).

**Tests to add:** Test that turn countdown strings appear in messages at the right thresholds. Test that `tool_choice` is set to `{"type": "any"}` on the final 2 turns. Test that partial results are salvaged when `answer["ready"]` is False. Test that the success banner is suppressed when status is `partial` or `failed`. Test that empty string content is normalized by `_validate_messages()`.

**Estimated complexity:** Medium-high. This is the largest task because it touches the REPL loop, client wrappers, CLI output, and message validation. But it's the most impactful fix.

**Risk:** `tool_choice={"type": "any"}` on the final turn may produce a low-quality forced call. This is still better than empty output — the user gets *something* for their money. Provider differences between Anthropic (`any`/`tool`) and OpenAI (`required`) need testing. The turn countdown adds ~20 tokens per turn to context, which is negligible cost.

---

### Task 3: Issue #20 — Add Retry to scaffold.py (Quick Win)

**Why third:** Trivial fix, immediate reliability improvement, 5-minute task.

**Scope:** Import `retry_with_backoff` from `deeprepo/utils.py` in `scaffold.py`. Wrap the `client.chat.completions.create()` call at line 172 in a `@retry_with_backoff()` decorated inner function. Add a `try/except` that raises `RuntimeError(f"Scaffold LLM error on {model} after retries: {e}")` on final failure, consistent with the error wrapping pattern in `llm_clients.py`.

**Tests to add:** Mock the OpenAI client to raise `APITimeoutError` on first call and succeed on second, assert retry occurred. Mock to always fail, assert `RuntimeError` is raised after max retries.

**Estimated complexity:** Trivial. The pattern is already established in `llm_clients.py`.

---

### Task 4: Issue #21 — Add Logging Infrastructure (Observability)

**Why fourth:** Every future debugging session benefits from this. You need it before shipping to more users because silent exception swallowing is what made the first debugging round incomplete.

**Scope:** Add `import logging` and `logger = logging.getLogger(__name__)` to each affected module (`tui/shell.py`, `cli_commands.py`, `tui/prompt_builder.py`). In each `except Exception` block, add `logger.debug("description of what failed", exc_info=True)` before the existing fallback behavior. The user-facing behavior stays identical unless debug mode is on.

Add a `--debug` flag to the CLI in `cli.py` that calls `logging.basicConfig(level=logging.DEBUG, format="%(name)s:%(levelname)s: %(message)s")`. Also check for `DEEPREPO_DEBUG=1` environment variable so TUI mode (which doesn't go through CLI arg parsing) can enable debug logging too.

**Important safety note from Codex:** Debug logs must not leak API keys or sensitive document content. The `exc_info=True` flag prints stack traces which could include local variables. For the `tui/shell.py` handlers this is fine (they're Rich rendering failures). For `cli_commands.py:308` (clipboard), the `content` variable could contain the full project context. Log only the exception type and message, not the full traceback, in handlers that touch sensitive data.

**Tests to add:** Test that debug logs appear when `DEEPREPO_DEBUG=1` is set and an exception is triggered. Test that logs do NOT appear by default.

**Estimated complexity:** Low. Mechanical changes across ~6 locations plus a CLI flag.

---

### Task 5: Issue #19 — Add GitHub Actions CI (Regression Lock)

**Why last:** CI validates all the previous fixes and prevents regressions. But it only adds value after the fixes are in place.

**Scope:** Create `.github/workflows/ci.yml` with push/PR triggers, Python 3.11 + 3.12 matrix, editable install, and the offline-safe test command that Codex validated: `pytest tests/ -v --ignore=tests/test_baseline.py --ignore=tests/test_connectivity.py --ignore=tests/test_rlm_integration.py` (this got 202 passing tests).

Add `pytest>=7.0` and `ruff>=0.4.0` to the dev dependency group in `pyproject.toml`. Add a lint job that runs `ruff check deeprepo/`.

The script-style test files (`test_baseline.py`, `test_connectivity.py`, `test_rlm_integration.py`) that execute at import time should either be converted to proper pytest functions with `@pytest.mark.requires_api` markers, or moved to a `scripts/` directory. Converting them is cleaner, but moving them is faster — let Codex decide based on how much refactoring each file needs.

**Tests to add:** The CI itself is the test. Verify it passes on a clean checkout.

**Estimated complexity:** Low-medium. The workflow file is straightforward, but the script-style test files need attention.

---

## Part 4: Codex Cold Start Prompt

Below is the implementation prompt to paste into a fresh Codex session. It covers all 5 tasks in order.

```
You are implementing bug fixes for the DeepRepo project — an open-source RLM agent
platform. Repo is at the current directory. Package: deeprepo/. Version: 0.2.2.

Read DEBUGGING_SESSION.md for full context on all 6 issues and confirmed findings.
Read DEEPREPO_FIX_PLAN.md for the exact implementation plan.

You have 5 tasks in order. Complete each one fully (code changes + tests + verify)
before moving to the next.

TASK 1 — Issue #18: Restrict REPL namespace (security)
Files: deeprepo/rlm_scaffold.py (lines 334-340, 775), tests/test_execute_code.py
- Replace __builtins__ with safe allowlist
- Replace os with os.path only
- Add AST pre-check before exec() to block Import/ImportFrom nodes
- Add tests proving open(), __import__(), eval(), os.system() are blocked
- Run existing tests to verify no regressions

TASK 2 — Issues #22 + #23: Turn budget + output salvage (critical UX)
Files: deeprepo/rlm_scaffold.py (REPL loop ~142-272, _validate_messages ~579-602),
       deeprepo/llm_clients.py (RootModelClient.complete, OpenRouterRootClient.complete),
       deeprepo/cli.py (defaults at 358, 367),
       deeprepo/cli_commands.py (post-analysis flow ~118-131),
       deeprepo/terminal_ui.py (banners)
- Inject turn countdown into model messages each turn
- Add tool_choice param to client wrappers, force {"type": "any"} on final 2 turns
- Unify max_turns defaults to 20 everywhere
- Salvage trajectory outputs when answer["ready"] is False
- Add status field (completed/partial/failed) to result
- Gate success banner on completed status; show appropriate warnings for partial/failed
- Fix _validate_messages() to handle empty string content
- Add tests for all of the above

TASK 3 — Issue #20: Add retry to scaffold.py (quick win)
Files: deeprepo/scaffold.py (~line 172), deeprepo/utils.py (retry_with_backoff)
- Wrap API call in @retry_with_backoff() following llm_clients.py pattern
- Add tests for retry on transient error and final failure

TASK 4 — Issue #21: Add logging infrastructure (observability)
Files: deeprepo/tui/shell.py, deeprepo/cli_commands.py, deeprepo/tui/prompt_builder.py,
       deeprepo/cli.py
- Add logging.getLogger(__name__) to each affected module
- Add logger.debug() with exc_info=True to each except block (KEEP existing fallback behavior)
- Add --debug CLI flag and DEEPREPO_DEBUG=1 env var support
- Do NOT log sensitive content (API keys, full document text) in tracebacks
- Add tests for debug log presence/absence

TASK 5 — Issue #19: Add GitHub Actions CI
Files: .github/workflows/ci.yml, pyproject.toml
- Create CI workflow: push/PR trigger, Python 3.11+3.12 matrix
- Use: pytest tests/ -v --ignore=tests/test_baseline.py --ignore=tests/test_connectivity.py --ignore=tests/test_rlm_integration.py
- Add pytest and ruff to dev dependencies
- Add lint job: ruff check deeprepo/
- Convert or move script-style test files that execute at import time

After each task, run: pytest tests/ -v --ignore=tests/test_baseline.py --ignore=tests/test_connectivity.py --ignore=tests/test_rlm_integration.py

When all 5 tasks are done, run the full safe test suite one final time and report results.
Produce IMPLEMENTATION_REPORT.md with what changed, test results, and any deviations.
```

---

## Part 5: Definition of Done — v0.2.3 Release Checklist

Before cutting the release, verify:

1. All 202+ tests pass (existing safe subset + new tests from Tasks 1-4)
2. `deeprepo init .` on a 200+ file codebase produces a non-empty PROJECT.md
3. The success banner only appears when analysis completes
4. Partial results are saved when the model runs out of turns
5. `open()`, `__import__()`, `os.system()` are blocked in the REPL namespace
6. `deeprepo new` retries on transient API errors
7. `--debug` flag produces exception traces in debug.log or stderr
8. CI workflow passes on a clean push to main
9. `max_turns` defaults are 20 everywhere (CLI, config, engine)
10. No `except Exception: pass` blocks without `logger.debug()` remain

After verification, bump version to 0.2.3 in `pyproject.toml`, push, and publish to PyPI.
