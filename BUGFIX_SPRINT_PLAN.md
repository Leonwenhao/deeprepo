# deeprepo v0.2.2 — Bug Fix Sprint Plan

**Author:** Leon (with Claude)
**Date:** February 23, 2026
**Sprint Goal:** Fix all Critical and High bugs from AUDIT_FINDINGS.md, fix Medium UX bugs, add missing tests. Ship a share-ready v0.2.2.
**Agents:** Claude Code (CTO) + Codex (Engineer)
**Protocol:** AGENT_ORCHESTRATION_PROTOCOL.md — scratchpad relay, self-contained task prompts, context window monitoring.

---

## Audit Summary

| Severity | Count | Items |
|----------|-------|-------|
| Critical | 2 | C1, C2 — tool_use/tool_result message mismatch |
| High | 5 | H1 — partial tool_use mismatch, H2 — sys.exit kills process, H3 — no execution timeout, H4 — onboarding missing Anthropic key, H5 — no loading indicator |
| Medium | 4 | M1 — Rich markup leak, M2 — bad error messages, M3 — non-execute_python tool_use, M4 — no early break on set_answer |
| Low | 5 | L1-L5 — minor tech debt |
| Tests | 9 | T1-T9 — new tests to add |

---

## Task Breakdown

### Batch 1: Engine Message Integrity (Codex — one shot)

**Fixes:** C1, C2, H1, M3, M4

All five bugs live in `deeprepo/rlm_scaffold.py` and share a single root cause: `_append_assistant_message` blindly serializes all tool_use blocks from the response, regardless of whether tool_results will follow. The fix is unified:

1. Add `strip_tool_use` parameter to `_append_assistant_message` (default False). When True, filter out all tool_use blocks from serialized content.
2. Call with `strip_tool_use=True` in the "no code blocks" path (line 173) and "legacy text" path (line 233).
3. In `_append_tool_result_messages`, after serializing the assistant message, generate synthetic error tool_results for any tool_use IDs in the response that are NOT in `tool_use_info`.
4. In the code block execution loop (line 185), add early break on `answer["ready"]`. Pad `all_output` to match `tool_use_info` length before calling `_append_tool_result_messages`.

**Tests to add (T1, T2, T8):**
- Mock response with tool_use block, no "code" key → no orphaned tool_use
- Mock response with 2 tool_use blocks, 1 valid, 1 invalid → all have tool_results
- Mock 3 code blocks, block 1 calls set_answer → blocks 2-3 don't execute

---

### Batch 2: REPL Safety (Codex — one shot)

**Fixes:** H2, H3

Both are in `_execute_code` in `rlm_scaffold.py`.

1. Change `except Exception:` to `except BaseException:` to catch `SystemExit` and `KeyboardInterrupt`.
2. Add execution timeout using `signal.alarm()` (Unix) with `threading.Timer` fallback (cross-platform). Default 120 seconds. Catch timeout and return error string.

**Tests to add (T3, T4):**
- `sys.exit(0)` in REPL code → returns error string, process survives
- `time.sleep(999)` with short timeout → returns timeout error within expected time

---

### Batch 3: TUI UX Fixes (Codex — one shot)

**Fixes:** H4, H5, M1, M2

Four separate files, no dependencies between them. One prompt, one pass.

1. **Onboarding (H4):** Update `needs_onboarding()` to check both `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY`. Update `run_onboarding()` to prompt for both with explanations. Update config.yaml schema to store both keys. Load both on startup.
2. **Spinner (H5):** Wrap `cmd_init` and `cmd_refresh` calls in `command_router.py` with `rich.console.Console.status()` spinner.
3. **Markup leak (M1):** Fix the backslash-bracket collision in the ASCII art line. Add trailing space before closing tag.
4. **Error messages (M2):** Add specific exception handling in `_do_init` and `_do_refresh` that catches `EnvironmentError` and rewrites messages for TUI context.

**Tests to add (T5, T6, T7):**
- `needs_onboarding()` with missing Anthropic key → reports key needed
- `/init` with missing Anthropic key → user-friendly error, no ".env" reference
- Banner lines rendered through Rich Console → no literal `[/` in output

---

### Batch 4: Test Cleanup (Codex — one shot)

**Fixes:** L2

1. Fix `test_async_batch.py` — replace `await_count` assertions with `usage.sub_calls` assertions.

**Tests to fix (T9):**
- Both failing tests should pass after fixing assertions.

---

## Execution Order

```
Batch 1 (engine) → Batch 2 (safety) → Batch 3 (TUI) → Batch 4 (tests)
```

Batch 1 is the critical path — it fixes the release-blocking API error. Batches 2 and 3 can theoretically run in parallel since they touch different files, but sequential is safer to avoid merge conflicts. Batch 4 is cleanup.

**Alternatively:** If Codex can handle a large prompt, Batches 1+2 can be combined (all `rlm_scaffold.py` changes) and Batches 3+4 can be combined (all TUI/test changes). This reduces to 2 Codex tasks instead of 4, cutting relay cycles in half.

**Recommended:** 2 tasks. Task A = Batches 1+2 (engine). Task B = Batches 3+4 (TUI + tests).

---

## CTO Review Checkpoints

### After Task A (engine fixes):
- `python -m pytest tests/ -v` — all tests pass including new T1-T4, T8
- Manual test: `deeprepo init .` on any project — completes without API 400 error
- Code review: trace every message append path, verify no orphaned tool_use blocks possible

### After Task B (TUI + test fixes):
- `python -m pytest tests/ -v` — all tests pass including new T5-T7, T9
- Manual test: `deeprepo` TUI launch — no markup leak in banner
- Manual test: `/init` with missing keys — user-friendly error messages
- Manual test: `/init` with valid keys — spinner visible during analysis
- All 186+ existing tests still pass, plus ~9 new tests

### Release:
- Bump version to 0.2.2
- `git add -A && git commit -m "v0.2.2: engine message integrity, REPL safety, TUI UX fixes"`
- `git tag v0.2.2 && git push origin main --tags`
- `python -m build && twine upload dist/deeprepo_cli-0.2.2*`
- Update GitHub release notes (short: "Bug fixes and stability improvements for the TUI. Fixes API errors during project analysis, adds execution safety, improves onboarding flow.")

---

## Files Changed Summary

| File | Batches | Changes |
|------|---------|---------|
| `deeprepo/rlm_scaffold.py` | 1, 2 | Message threading fix, strip_tool_use, execution timeout, sys.exit catch, early break |
| `deeprepo/tui/onboarding.py` | 3 | Dual API key check and prompt, config schema update |
| `deeprepo/tui/command_router.py` | 3 | Rich spinner for init/refresh, error message rewriting |
| `deeprepo/tui/shell.py` | 3 | Fix Rich markup escape in banner |
| `tests/test_tool_use.py` | 1, 2 | New tests: T1, T2, T3, T8 |
| `tests/test_execute_code.py` | 2 | New test: T4 (timeout) |
| `tests/test_onboarding.py` | 3 | New test: T5 |
| `tests/test_command_router.py` | 3 | New tests: T6 |
| `tests/test_tui_polish.py` | 3 | New test: T7 |
| `tests/test_async_batch.py` | 4 | Fix T9: await_count → usage.sub_calls |
