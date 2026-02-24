# CODEX_DIAGNOSIS.md — DeepRepo v0.2.2

> Generated: 2026-02-24T22:17:48Z
> Agent: Codex
> Scope: Issues #18, #19, #20, #21, #22, #23

---

## Issue #18 — Security: `__builtins__` unrestricted in REPL namespace

### Root Cause
`RLMEngine` injects full Python builtins into the execution namespace and then runs root-model code via raw `exec()`. This exposes filesystem, process, dynamic import, and code-eval primitives to model-generated code without sandbox restrictions.

### Evidence
`deeprepo/rlm_scaffold.py:321-340`
```python
namespace = {
    ...
    "os": __import__("os"),
    "json": __import__("json"),
    "collections": __import__("collections"),
}
namespace["__builtins__"] = __builtins__
```

`deeprepo/rlm_scaffold.py:775`
```python
exec(code, namespace)
```

Reproduction (current codebase):
- `_execute_code("print(open('pyproject.toml').read().splitlines()[0])", ns)` returned `[build-system]`
- `_execute_code("import os; os.system('echo SAFE_DEMO_COMMAND')", ns)` executed shell command and returned `rc=0`

Tests currently mirror unrestricted builtins rather than restricting them:
- `tests/test_execute_code.py:22,31,47`
- `tests/test_tool_use.py:180`

No sandbox/security restriction tests found (`rg "sandbox|restricted|safe_builtin|os.system|__import__" tests/*.py` returned no matches).

### Confirmed Findings Validated
No direct CF-1..CF-6 dependency. Nothing contradicts prior findings.

### Proposed Fix Plan
1. In `deeprepo/rlm_scaffold.py`, replace `namespace["__builtins__"] = __builtins__` with an explicit allowlist dictionary (safe builtins only).
2. Remove `os` from default namespace injection (or wrap with restricted helper functions).
3. Add AST pre-check before `exec()` to block disallowed nodes (`Import`, `ImportFrom`, `Exec`-equivalent patterns) unless explicitly allowlisted.
4. Add unit tests in `tests/test_execute_code.py` verifying `open`, `__import__`, `eval`, and `os.system` are blocked.
5. Update prompt examples that currently suggest `import re` / `from collections import defaultdict` to use pre-injected `re`/`collections`.

Complexity: medium-high.

### Risk Assessment
Restricting builtins can break existing prompt patterns and model behaviors. The highest risk is over-restricting standard operations and degrading analysis quality; this needs compatibility tests for normal REPL workflows.

---

## Issue #19 — Infrastructure: Add GitHub Actions CI

### Root Cause
The repository has pytest-configured tests but no CI workflow directory, and the test suite mixes proper unit tests with script-style `test_*.py` files that execute top-level code during collection (including live API calls).

### Evidence
No CI workflow:
- `ls -la .github/workflows/` -> `No .github/workflows/ directory`
- `ls -la .github` -> `No .github directory`

Test inventory:
- `find tests/ -name "test_*.py" | wc -l` -> `27`

Script-style test files without `def test_*`:
- `tests/test_baseline.py`
- `tests/test_connectivity.py`
- `tests/test_loader.py`
- `tests/test_prompts.py`
- `tests/test_rlm_integration.py`

Live API calls at import-time:
- `tests/test_connectivity.py:17-25` (`anthropic.Anthropic(...).messages.create(...)`)
- `tests/test_connectivity.py:43-54` (`openai.OpenAI(...).chat.completions.create(...)`)
- `tests/test_baseline.py:13-16` (`run_baseline(...)` at module top-level)
- `tests/test_rlm_integration.py:13-17` (`run_analysis(...)` at module top-level)

Pytest config exists but no dedicated test dependency group:
- `pyproject.toml:45-46` (`[tool.pytest.ini_options]`)
- `pyproject.toml:48-52` only includes `build` and `twine` in `dev`.

Collection behavior demonstrates CI hazard:
- `pytest -q tests ... -k 'not connectivity ...'` still errored during collection because top-level modules executed before deselection.
- Offline-safe subset run succeeded when ignored explicitly:
  `PYTHONPATH=. pytest -q tests --ignore=tests/test_baseline.py --ignore=tests/test_connectivity.py --ignore=tests/test_rlm_integration.py` -> `202 passed`.

### Confirmed Findings Validated
No direct CF-1..CF-6 dependency. Nothing contradicts prior findings.

### Proposed Fix Plan
1. Add `.github/workflows/ci.yml` for push/PR with Python matrix.
2. Install package in CI via editable install (`pip install -e .`) and install pytest.
3. Run offline-safe suite by excluding or marking live API scripts.
4. Convert script-style files in `tests/` into real pytest test functions or move them to `scripts/` to avoid collection side effects.
5. Add separate opt-in workflow (manual/scheduled) for live API connectivity/integration checks with secrets.

Complexity: low-medium.

### Risk Assessment
Excluding live tests from default CI can hide provider integration regressions. Mitigate with a separate gated workflow for live checks and explicit docs on when to run it.

---

## Issue #20 — Bug: `scaffold.py` `_call_llm()` missing retry logic

### Root Cause
`ProjectScaffolder._call_llm()` calls OpenRouter directly with no retry wrapper, unlike all main LLM client paths that use `retry_with_backoff()`/`async_retry_with_backoff()`.

### Evidence
Unprotected call path:
- `deeprepo/scaffold.py:149-179`
```python
client = openai.OpenAI(...)
response = client.chat.completions.create(...)
```

Retry-protected patterns elsewhere:
- `deeprepo/llm_clients.py:157,173,255,328` use `@retry_with_backoff()`
- `deeprepo/llm_clients.py:374-380` uses `async_retry_with_backoff(...)`
- `deeprepo/utils.py:37` defines `retry_with_backoff(...)`

Repo-wide grep confirms only `scaffold.py` call is unwrapped:
- `grep -rn "completions.create" deeprepo/ --include="*.py"` found `deeprepo/scaffold.py:172` plus wrapped calls in `llm_clients.py`.

Behavior repro:
- Patched `openai.OpenAI` to always raise `APITimeoutError` in `_call_llm()` -> `create_calls=1` (no retry).
- Equivalent repro against `OpenRouterRootClient.complete()` -> retry logs + `create_calls=3`.

### Confirmed Findings Validated
No direct CF-1..CF-6 dependency. Nothing contradicts prior findings.

### Proposed Fix Plan
1. In `deeprepo/scaffold.py`, wrap `client.chat.completions.create(...)` in a local `@retry_with_backoff()` function.
2. Optionally refactor scaffolding to reuse existing client abstractions from `deeprepo/llm_clients.py`.
3. Add a unit test in `tests/test_scaffold.py` simulating transient timeout then success, asserting retries occurred.
4. Add test for non-retryable 4xx to preserve fast-fail behavior.

Complexity: low.

### Risk Assessment
Retry backoff increases worst-case latency for `deeprepo new`. Keep retry count bounded and surface clear timeout messages to avoid silent hangs.

---

## Issue #21 — Improvement: Silent exception swallowing in TUI shell

### Root Cause
Broad `except Exception` handlers in TUI/CLI fallback paths suppress exception detail and provide no logging. This preserves UX continuity but removes debugging visibility.

### Evidence
Reported locations still catch broad exceptions:
- `deeprepo/tui/shell.py:122,139,208,220`
- `deeprepo/cli_commands.py:308`
- `deeprepo/tui/prompt_builder.py:311`

Examples:
`deeprepo/tui/prompt_builder.py:304-312`
```python
try:
    import pyperclip
    pyperclip.copy(text)
    return True
except Exception:
    return False
```

`deeprepo/tui/shell.py:99-131` and `200-221` fallback to plain prints but do not log traceback/context.

No logging infrastructure detected:
- `rg "import logging|getLogger|logging\." deeprepo/*.py` -> no matches

CLI supports `--quiet`, but there is no debug flag for exception diagnostics:
- `deeprepo/cli.py:334,414,439`

Note: literal `except Exception: pass` blocks were not found in current code, but silent swallowing behavior remains via generic fallback returns/prints.

### Confirmed Findings Validated
No direct CF-1..CF-6 dependency. Prior issue intent still valid; implementation evolved from `pass` to silent fallback.

### Proposed Fix Plan
1. Add minimal logging utility (module-level logger with opt-in debug mode).
2. Replace broad handlers with `except Exception as exc:` and emit debug logs (traceback + context).
3. Preserve user-facing fallback behavior unchanged when debug is off.
4. Add CLI/TUI debug switch (e.g., `--debug` or env var) and tests asserting logs appear only in debug mode.

Complexity: low-medium.

### Risk Assessment
Logging can leak sensitive prompt/file content if not redacted. Logs should avoid raw document dumps and redact API keys/path-sensitive values.

---

## Issue #22 — Bug: Root model has no turn-budget awareness

### Root Cause
The REPL loop tracks turns internally but never injects remaining-turn budget into model context, and client wrappers do not expose `tool_choice` forcing. This allows the root model to keep exploring until budget exhaustion without finalizing.

### Evidence
Turn loop is internal only:
- `deeprepo/rlm_scaffold.py:142-147`
```python
while turn < self.max_turns:
    turn += 1
    print(f"REPL Turn {turn}/{self.max_turns}")  # console only
```

Model call has no `tool_choice`:
- `deeprepo/rlm_scaffold.py:154-159`
```python
response = self.root_client.complete(
    messages=messages,
    system=domain.root_system_prompt,
    tools=[EXECUTE_CODE_TOOL],
    stream=self.verbose,
)
```

Spy run confirmed kwargs keys were `['messages', 'stream', 'system', 'tools']` and `has_tool_choice=False`.

Repo search:
- `rg -n "tool_choice" deeprepo/` -> `No tool_choice matches`

Client wrapper currently lacks `tool_choice` parameter:
- `deeprepo/llm_clients.py:128-136` (`RootModelClient.complete`)
- `deeprepo/llm_clients.py:217-225` (`OpenRouterRootClient.complete`)

SDK supports it:
- `anthropic.messages.create` signature includes `tool_choice` with types including `auto/any/tool/none`.
- `openai.chat.completions.create` signature includes `tool_choice` (`none/auto/required` + named tool options).

Prompts mention only static guidance (`Aim for 3-6 turns`) rather than dynamic remaining-turn countdown:
- `deeprepo/prompts.py:110`
- `deeprepo/domains/context.py:49`
- `deeprepo/domains/content.py:150`

### Confirmed Findings Validated
Validated CF-1, CF-2, CF-5.
- CF-1: still no `tool_choice` usage.
- CF-2: still no turn-countdown injected into model context.
- CF-5: split defaults still present (`15` in CLI/engine vs `20` config default).
No contradictions found.

### Proposed Fix Plan
1. Extend root client APIs (`deeprepo/llm_clients.py`) to accept optional `tool_choice` and pass through provider-specific payload.
2. In `RLMEngine.analyze`, inject per-turn budget context (`turn`, `remaining_turns`, finalization requirement) into messages each turn.
3. Apply escalation policy:
   - normal turns: `tool_choice=auto`/unset
   - final 2 turns: force tool usage (`any` or provider equivalent)
   - final turn: strong directive to call `set_answer(...)`.
4. Unify `max_turns` defaults in one source of truth and propagate through CLI/config paths.
5. Add tests for countdown injection and final-turn tool enforcement behavior.

Complexity: medium.

### Risk Assessment
Over-forcing tool calls can cause repetitive/no-op tool loops or degraded reasoning quality. Provider differences (`Anthropic any/tool` vs OpenAI `required`) require compatibility testing.

---

## Issue #23 — Bug: Silent failure on max-turns — charges user, writes empty file

### Root Cause
If `answer["ready"]` is never set, engine fallback overwrites final output with a placeholder string and returns success-shaped data. `cmd_init` then writes `PROJECT.md` and prints success/onboarding regardless of completion quality.

### Evidence
Fallback logic:
- `deeprepo/rlm_scaffold.py:265-272`
```python
if not answer["ready"]:
    ...
    if answer["content"]:
        ...
    else:
        answer["content"] = "[Analysis incomplete — max turns reached]"
```

Only two `answer["content"]` assignment sites exist:
- `deeprepo/rlm_scaffold.py:318` (`set_answer`)
- `deeprepo/rlm_scaffold.py:272` (fallback placeholder)

Trajectory stores intermediate outputs but is not used to salvage result:
- `deeprepo/rlm_scaffold.py:229-233` stores `root_response`, `repl_output`, etc.
- `deeprepo/cli_commands.py:115` writes only `result["analysis"]` via `ContextGenerator.generate(...)`

Success messaging is unconditional after `run_analysis` return:
- `deeprepo/cli_commands.py:118-131` (`print_init_complete`, then onboarding)
- `deeprepo/terminal_ui.py:68` banner text: `"Your project now has AI memory."`

Behavior reproductions:
1. Root returns prose-only final turn (no code): result `analysis="[Analysis incomplete — max turns reached]"`, `trajectory_len=0`.
2. Root executes code but never calls `set_answer`: placeholder returned; trajectory still contained `repl_output="intermediate finding"`.

`_validate_messages()` still skips string `content` values:
- `deeprepo/rlm_scaffold.py:585-588` returns early unless `content` is a list.
- Repro: message `{"content": ""}` remained unchanged after `_validate_messages`, while empty list-block text was replaced.

### Confirmed Findings Validated
Validated CF-3, CF-4, CF-5.
- CF-3: fallback still discards useful prose and emits placeholder.
- CF-4: string `""` content still not validated.
- CF-5: split defaults still present.
No contradictions found.

### Proposed Fix Plan
1. Change `run_analysis`/`RLMEngine.analyze` output contract to include completion status (`completed`, `partial`, `failed`) and reason.
2. On max-turns without ready, salvage best available output in priority order:
   - explicit `answer["content"]`
   - last assistant prose text
   - synthesized summary from `trajectory` (`repl_output` + key findings).
3. In `cmd_init`/`cmd_refresh`, gate success banner and onboarding on completed status; show warning for partial/failed runs.
4. Write `PROJECT.md` with explicit incomplete header when partial, including recovered evidence.
5. Fix `_validate_messages()` to normalize empty string `content` to a non-empty placeholder.

Complexity: medium.

### Risk Assessment
Auto-salvaging model prose may include low-confidence or malformed output. Needs explicit labeling and deterministic formatting to prevent downstream tools from treating partial output as fully trusted context.

---

## Cross-Cutting Findings

### Additional Issues Discovered
1. Several `tests/test_*.py` files are script-style modules with top-level execution, causing side effects during pytest collection (including live API calls).
2. Running tests from repo root requires package install or `PYTHONPATH=.` in this environment; otherwise `ModuleNotFoundError: deeprepo` appears during collection.
3. Logging infrastructure is absent project-wide, limiting diagnostics for both TUI and runtime orchestration failures.
4. SDKs already support `tool_choice`, but deeprepo’s client abstraction currently drops that capability.

### Dependency Map
1. #22 and #23 share the same orchestration control gap (no enforced tool-finalization + no turn budgeting).
2. #23 also depends on output/UX contract flaws in CLI post-processing (`cmd_init` success flow).
3. #18 is largely orthogonal (execution safety boundary) but affects the same REPL execution surface as #22/#23.
4. #20 is independent functionally, but leverages existing retry utilities used in root/sub client paths.
5. #19 should protect all subsequent fixes with automated regression checks.
6. #21 improves observability needed to debug and validate #22/#23 behavior in real user sessions.

### Recommended Fix Order
1. Fix #18 first (critical security boundary around arbitrary model-executed code).
2. Fix #22 and #23 together in one orchestration/output-contract pass (shared root causes, highest user-facing harm).
3. Fix #20 next (single-call reliability gap with clear low-complexity patch).
4. Add #19 CI workflow immediately after core fixes to lock regressions.
5. Implement #21 logging/debug improvements to improve maintainability and production diagnostics.
