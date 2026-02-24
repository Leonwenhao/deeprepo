# CLAUDE_CODE_DIAGNOSIS.md — DeepRepo v0.2.2

> Generated: 2026-02-24T12:00:00Z
> Agent: Claude Code (Opus 4.6)
> Scope: Issues #18, #19, #20, #21, #22, #23

---

## Issue #18 — 🔴 Security: `__builtins__` unrestricted in REPL namespace

### Root Cause

The REPL namespace grants the root model's generated code **unrestricted access to all Python builtins** via `namespace["__builtins__"] = __builtins__` at `rlm_scaffold.py:340`. Additionally, the `os` module is explicitly injected at line 335 (`"os": __import__("os")`). Together, these give LLM-generated code access to `open()`, `__import__()`, `eval()`, `exec()`, `compile()`, `os.system()`, `os.environ` (leaking API keys), file I/O, subprocess spawning, and network access. The existing `EXEC_TIMEOUT_SECONDS = 120` timeout (line 40) only prevents long-running attacks — single-shot operations like `os.environ["ANTHROPIC_API_KEY"]` or `open("/etc/passwd").read()` execute instantly.

### Evidence

**`deeprepo/rlm_scaffold.py:340`** — Full builtins injected:
```python
namespace["__builtins__"] = __builtins__
```

**`deeprepo/rlm_scaffold.py:334-337`** — Pre-imported modules include `os`:
```python
"re": re,
"os": __import__("os"),
"json": __import__("json"),
"collections": __import__("collections"),
```

**`deeprepo/rlm_scaffold.py:773-775`** — Code execution via bare `exec()`:
```python
with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
    exec(code, namespace)
```

**Tests confirm no sandbox tests exist:** `grep -rn "sandbox\|restricted\|safe_" tests/` returns zero relevant matches. The test files `test_execute_code.py` and `test_tool_use.py` both use `"__builtins__": __builtins__` in their own namespaces, replicating the vulnerability.

### Confirmed Findings Validated

- **CF-1 partially relevant:** `tool_choice` is never set, so the model could also produce prose instead of tool calls, but this is a separate concern from the security surface.
- No contradictions found. The vulnerability is confirmed as described.

### Proposed Fix Plan

1. **Define a safe builtins allowlist** in `rlm_scaffold.py`:
   ```python
   SAFE_BUILTINS = {
       "print", "len", "range", "enumerate", "zip", "map", "filter",
       "sorted", "reversed", "list", "dict", "set", "tuple", "str",
       "int", "float", "bool", "type", "isinstance", "issubclass",
       "hasattr", "getattr", "setattr", "any", "all", "sum", "min",
       "max", "abs", "round", "divmod", "pow", "hash", "id", "repr",
       "iter", "next", "callable", "format", "chr", "ord",
       "True", "False", "None", "StopIteration", "ValueError",
       "TypeError", "KeyError", "IndexError", "AttributeError",
       "RuntimeError", "Exception",
   }
   safe_builtins = {k: v for k, v in __builtins__.__dict__.items() if k in SAFE_BUILTINS}
   namespace["__builtins__"] = safe_builtins
   ```
2. **Remove `"os": __import__("os")`** from the namespace. The root model's generated code uses `os` only for `os.path`-style operations on the codebase dict keys, which can be replaced with `pathlib` or string operations. If `os.path` is needed, inject only `os.path` as a standalone module.
3. **Block `__import__`** by excluding it from safe builtins. This prevents `__import__("subprocess")` etc.
4. **Add sandbox tests** in `tests/test_execute_code.py` that verify blocked operations raise errors.

**Complexity:** Medium — requires careful allowlist tuning to avoid breaking legitimate code patterns the root model uses.

### Risk Assessment

- **False positives:** The root model's generated code may use builtins not on the allowlist (e.g., `open()` to read files from the `codebase` dict, or `collections.Counter`). Need to audit example trajectories to build the allowlist.
- **`os` removal:** The root model sometimes uses `os.path.basename()` or `os.path.splitext()` in its generated code. May need to keep `os.path` while blocking `os.system`, `os.environ`, etc.
- **Not a full sandbox:** `exec()` in CPython cannot be truly sandboxed. This is defense-in-depth, not a security guarantee. Consider a process-level sandbox (e.g., `bubblewrap`, `nsjail`) for production hardening.

---

## Issue #19 — 🟡 Infrastructure: Add GitHub Actions CI

### Root Cause

No `.github/` directory exists at all in the repository. The 27 test files in `tests/` and the pytest configuration in `pyproject.toml` are never run automatically on push or PR. This means regressions can be merged silently, and contributors have no automated feedback loop.

### Evidence

**No `.github/` directory:**
```
$ ls -la .github/ 2>/dev/null || echo "No .github/ directory at all"
No .github/ directory at all
```

**27 test files exist:**
```
$ find tests/ -name "test_*.py" | wc -l
27
```

**Pytest is configured in `pyproject.toml:45-46`:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Dev dependencies are minimal (`pyproject.toml:48-52`):**
```toml
[dependency-groups]
dev = [
    "build>=1.4.0",
    "twine>=6.2.0",
]
```
Note: `pytest` is not listed as a dev dependency. It must be installed separately.

**7 test files reference API keys or API clients** (need mocking or exclusion from CI):
- `tests/test_tool_use.py`
- `tests/test_async_batch.py`
- `tests/test_command_router.py`
- `tests/test_onboarding.py`
- `tests/test_config_manager.py`
- `tests/test_retry.py`
- `tests/test_connectivity.py`

**Tests that can likely run offline (pure unit tests):** `test_extract_code.py`, `test_loader.py`, `test_prompts.py`, `test_cache.py`, `test_content_loader.py`, `test_cli_log_status.py`, `test_context_domain.py`, `test_context_gen.py`, `test_scaffold.py`, `test_teams.py`, `test_cli_commands.py`, `test_session_state.py`, `test_prompt_builder.py`, `test_tui_shell.py`, `test_execute_code.py`, `test_tui_polish.py`, `test_cli_entry.py`, `test_baseline.py`, `test_refresh.py` — approximately 20 tests.

### Confirmed Findings Validated

No CF findings are directly related to this issue. Confirmed: no CI exists.

### Proposed Fix Plan

1. **Create `.github/workflows/ci.yml`** with:
   - Trigger on push to `main` and all PRs
   - Python 3.11+ matrix
   - Install dependencies: `pip install -e ".[dev]"` and `pip install pytest`
   - Run: `pytest tests/ -k "not connectivity and not rlm_integration" --ignore=tests/test_connectivity.py`
   - Use a pytest marker (`@pytest.mark.requires_api`) to exclude API-dependent tests
2. **Add `pytest` to dev dependencies** in `pyproject.toml`
3. **Add pytest markers** to `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   markers = ["requires_api: tests that need real API keys"]
   ```
4. **Mark API-requiring tests** with `@pytest.mark.requires_api` and add `-m "not requires_api"` to CI.

**Complexity:** Low — straightforward workflow file creation and pytest marker setup.

### Risk Assessment

- **API-dependent tests:** Must be correctly identified and excluded. Running them in CI without keys would cause failures.
- **Test dependencies:** Some tests may import modules that fail without API SDKs installed. The `except Exception` fallback in `cli.py:22` and `baseline.py:13` suggests this is already a known issue.
- **Flaky tests:** Unknown until CI is running. First CI run will reveal issues.

---

## Issue #20 — 🟡 Bug: `scaffold.py` `_call_llm()` missing retry logic

### Root Cause

`scaffold.py:_call_llm()` (lines 149-179) makes a raw `client.chat.completions.create()` call without wrapping it in the `retry_with_backoff()` decorator that protects every other LLM call in the codebase. A transient HTTP 429 (rate limit), 500 (server error), or timeout during `deeprepo new` will crash with an unhandled exception instead of retrying.

### Evidence

**`deeprepo/scaffold.py:172`** — Raw API call with no retry:
```python
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": prompt}],
    max_tokens=8192,
    temperature=0.0,
)
```

**Contrast with `deeprepo/llm_clients.py`** — Every other API call is protected:
- Line 157: `@retry_with_backoff()` on `RootModelClient._stream_call()`
- Line 173: `@retry_with_backoff()` on `RootModelClient._call()`
- Line 255: `@retry_with_backoff()` on `OpenRouterRootClient._call()`
- Line 328: `@retry_with_backoff()` on `SubModelClient.query._call()`
- Line 374: `async_retry_with_backoff()` on `SubModelClient._async_query()`

**The retry utility is already importable from `deeprepo/utils.py:37`:**
```python
def retry_with_backoff(max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY):
```

**No other unprotected calls found:** `grep -rn "completions.create" deeprepo/ --include="*.py"` shows only `scaffold.py:172` lacks retry protection. All `llm_clients.py` calls are wrapped.

### Confirmed Findings Validated

No CF findings are directly about this issue. The finding is new and confirmed.

### Proposed Fix Plan

1. **Import `retry_with_backoff`** in `scaffold.py`:
   ```python
   from .utils import retry_with_backoff
   ```
2. **Wrap the API call** in `_call_llm()`:
   ```python
   @retry_with_backoff()
   def _api_call():
       return client.chat.completions.create(
           model=model,
           messages=[{"role": "user", "content": prompt}],
           max_tokens=8192,
           temperature=0.0,
       )
   response = _api_call()
   ```
3. **Add error wrapping** consistent with `llm_clients.py` pattern:
   ```python
   try:
       response = _api_call()
   except Exception as e:
       raise RuntimeError(f"Scaffold LLM error on {model} after retries: {e}") from e
   ```

**Complexity:** Trivial — 5-line change following established pattern.

### Risk Assessment

- **Minimal risk.** The retry logic is already battle-tested in `llm_clients.py`.
- **Only consideration:** The `_call_llm` method creates a new `openai.OpenAI` client on every call (line 167-169). This is fine for retry since the client is stateless.

---

## Issue #21 — 🟢 Improvement: Silent exception swallowing in TUI shell

### Root Cause

Multiple `except Exception: pass` (or equivalent fallback-to-plain-text) blocks in the TUI shell silently discard errors with no logging, no debug output, and no user feedback. This is a deliberate pattern to prevent TUI crashes when Rich rendering fails, but it makes debugging impossible because exceptions vanish completely. The codebase has **zero logging infrastructure** — no `import logging`, no `getLogger()`, no `--debug` CLI flag.

### Evidence

**`deeprepo/tui/shell.py:122`** — `_display_result()` catches all Rich rendering errors:
```python
except Exception:
    if status == "error":
        print(f"Error: {message}")
    ...
```

**`deeprepo/tui/shell.py:139`** — `_get_version()` catches metadata lookup failure:
```python
except Exception:
    return "dev"
```

**`deeprepo/tui/shell.py:208`** — `_print_welcome()` catches Rich rendering failure:
```python
except Exception:
    print("deeprepo")
    ...
```

**`deeprepo/tui/shell.py:220`** — `_print_goodbye()` catches Rich rendering failure:
```python
except Exception:
    print("\nGoodbye.")
```

**`deeprepo/cli_commands.py:308`** — `cmd_context()` catches clipboard failure:
```python
except Exception:
    token_est = len(content) // 4
    if not quiet:
        ui.print_msg("Could not copy to clipboard...")
```
Note: This one is actually **partially acceptable** — it does inform the user about clipboard failure. But it discards the exception details.

**`deeprepo/tui/prompt_builder.py:311`** — `_copy_to_clipboard()` catches pyperclip failure:
```python
except Exception:
    return False
```

**No logging infrastructure exists:**
```
$ grep -rn "import logging\|getLogger\|logging\." deeprepo/ --include="*.py"
(zero matches)
```

**No `--debug` flag:** The CLI has `--quiet` (`-q`) but no `--verbose` or `--debug` flag for general use. The `verbose` parameter in `rlm_scaffold.py` controls REPL output verbosity, not error logging.

### Confirmed Findings Validated

No CF findings directly address this. The reported locations at shell.py:122, 139, 208, 220 and cli_commands.py:308 and prompt_builder.py:311 are all confirmed.

### Proposed Fix Plan

1. **Add a logger** to each affected module:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   ```
2. **Replace `except Exception: pass` / fallback blocks** with `logger.debug()`:
   ```python
   except Exception:
       logger.debug("Rich rendering failed, falling back to plain text", exc_info=True)
       # ... existing fallback code ...
   ```
3. **Add `--debug` flag** to the CLI (`cli.py`) that sets `logging.basicConfig(level=logging.DEBUG)`.
4. **Optionally add `DEEPREPO_DEBUG=1`** env var check for TUI mode (where CLI flags aren't available).

**Complexity:** Low — mechanical changes across ~6 locations, plus a small CLI flag addition.

### Risk Assessment

- **No behavior change for users** unless `--debug` is set. Default behavior remains identical (silent fallbacks).
- **Log output volume:** `logger.debug()` with `exc_info=True` produces stack traces. Only emitted at DEBUG level, so no noise by default.
- **TUI interaction:** Logging to stderr while the TUI is running could interfere with prompt_toolkit. Consider a file handler or only enabling debug logging in non-TUI mode.

---

## Issue #22 — 🔴 Bug: Root model has no turn-budget awareness

### Root Cause

The REPL loop in `rlm_scaffold.py` (line 142: `while turn < self.max_turns`) never injects turn-count information into the model's context. The root model has **zero awareness** of how many turns it has used or how many remain. Neither the system prompts (`prompts.py`, `domains/context.py`) nor the per-turn messages include any turn countdown. The system prompt says "Aim for 3-6 REPL turns" (line 110) but doesn't tell the model the actual limit or current position. Combined with CF-1 (no `tool_choice` forcing), the model can spend all turns exploring without ever calling `set_answer()`.

### Evidence

**`deeprepo/rlm_scaffold.py:142-148`** — The REPL loop prints turn info to stdout but never injects it into the model's messages:
```python
while turn < self.max_turns:
    turn += 1
    if self.verbose:
        print(f"\n{'='*60}")
        print(f"REPL Turn {turn}/{self.max_turns}")
        print(f"{'='*60}")
```

**No turn-count injection anywhere in the message chain.** The messages sent to the model are:
- Initial user prompt (line 138): no turn info
- Re-prompt when no code found (lines 182-188): no turn info
- REPL output feedback (lines 246-262): no turn info

**System prompts contain no turn budget language:**
- `prompts.py:110`: "Aim for 3-6 REPL turns" — but no mention of the actual `max_turns` limit
- `domains/context.py:49`: "Aim for 3-6 turns by batching work" — same vague guidance
- Neither prompt says "you will be terminated after N turns" or "you are on turn X of Y"

**CF-1 confirmed: `tool_choice` is never set.** `grep -rn "tool_choice" deeprepo/ --include="*.py"` returns zero matches. The model is free to respond with text-only blocks instead of tool calls on any turn, including the final turn.

**CF-2 confirmed: No turn-countdown logic exists.** The string "turn" appears in the verbose `print()` statements but never in any message sent to the model.

**CF-5 confirmed: Split `max_turns` defaults:**
- `rlm_scaffold.py:38`: `MAX_TURNS = 15`
- `rlm_scaffold.py:81`: `max_turns: int = MAX_TURNS` (15)
- `cli.py:358`: `default=15`
- `cli.py:367`: `default=15`
- `config_manager.py:17`: `max_turns: int = 20`
- `cli_commands.py:88`: Uses `config.max_turns` (20) for `init`/`refresh`
- `refresh.py:42,80`: Uses `self.config.max_turns` (20)

The `init` and `refresh` commands get 20 turns (via config), while `analyze` and `compare` get 15 (via CLI default).

### Confirmed Findings Validated

- **CF-1:** Confirmed — zero `tool_choice` matches in codebase.
- **CF-2:** Confirmed — no turn countdown injected into model messages.
- **CF-5:** Confirmed — split defaults: CLI=15, config_manager=20. Commit `793b340` changed `config_manager.py` from 10→20 but didn't update `rlm_scaffold.py` or `cli.py`.

### Proposed Fix Plan

1. **Inject turn countdown** into the user message or tool_result on every turn. Add to the REPL loop (after line 147):
   ```python
   turn_context = (
       f"[Turn {turn}/{self.max_turns}] "
       f"{'⚠️ FINAL TURN — you MUST call set_answer() now!' if turn == self.max_turns else ''}"
   )
   ```
   Prepend this to the user message or tool_result content.

2. **Set `tool_choice="any"`** on the final 1-2 turns to force the model to call `execute_python` instead of producing prose:
   ```python
   if turn >= self.max_turns - 1:
       kwargs["tool_choice"] = {"type": "any"}
   ```

3. **Add turn-budget guidance** to the system prompts:
   ```
   You have a maximum of {max_turns} turns. Plan your exploration/synthesis
   budget accordingly. If you are on your final turn, you MUST call set_answer().
   ```

4. **Unify `max_turns` defaults** to a single source of truth (config_manager's 20) and remove the hardcoded 15 from `cli.py` and `rlm_scaffold.py`.

**Complexity:** Medium — touches REPL loop, system prompts, CLI defaults, and API call kwargs.

### Risk Assessment

- **`tool_choice="any"` on final turn:** May cause the model to produce a low-quality forced tool call. Better than zero output, but the synthesis quality on a forced final turn may be poor.
- **Turn countdown injection:** Adds tokens to every turn's context. Minimal cost (~20 tokens per turn).
- **Default unification:** Changing CLI default from 15→20 is a behavior change for `deeprepo analyze` users. Should be documented.

---

## Issue #23 — 🔴 Bug: Silent failure on max-turns — charges user, writes empty file

### Root Cause

When the model exhausts all turns without calling `set_answer()`, three things go wrong in sequence:

1. **Fallback discards prose** (`rlm_scaffold.py:265-272`): If `answer["ready"]` is False and `answer["content"]` is empty, the engine sets `answer["content"] = "[Analysis incomplete — max turns reached]"`. The intermediate REPL outputs (accumulated in `trajectory[*]["repl_output"]`) contain valuable exploration data but are **not salvaged** — only `answer["content"]` is returned.

2. **Success banner is printed anyway** (`terminal_ui.py:64-79`): The `print_onboarding()` function prints "Your project now has AI memory" regardless of whether the analysis produced meaningful output. The `print_init_complete()` function (line 48-61) prints "Done! Generated:" with cost info. Neither checks the analysis content for the `[Analysis incomplete]` marker.

3. **Empty PROJECT.md is written** (`context_generator.py:23-25`): The `generate()` method writes whatever `analysis_output` it receives — including the placeholder `[Analysis incomplete — max turns reached]` — to `PROJECT.md` with a metadata header. There is no validation that the content is meaningful.

### Evidence

**`deeprepo/rlm_scaffold.py:265-272`** — Fallback logic:
```python
if not answer["ready"]:
    if self.verbose:
        print(f"\n⚠️ Max turns ({self.max_turns}) reached without answer[\"ready\"] = True")
    if answer["content"]:
        if self.verbose:
            print("Using partial answer from answer[\"content\"]")
    else:
        answer["content"] = "[Analysis incomplete — max turns reached]"
```

**`deeprepo/rlm_scaffold.py:233`** — REPL outputs are stored in trajectory but never salvaged:
```python
"repl_output": combined_output,
```
The trajectory is returned in the result dict but the `cli_commands.py` and `context_generator.py` only use `result["analysis"]` (which is `answer["content"]`).

**`deeprepo/context_generator.py:19-25`** — Writes analysis output without validation:
```python
def generate(self, analysis_output: str, state: ProjectState) -> dict:
    self.deeprepo_dir.mkdir(parents=True, exist_ok=True)
    project_md = self.generate_project_md(analysis_output)
    project_md_path = self.deeprepo_dir / "PROJECT.md"
    project_md_path.write_text(project_md, encoding="utf-8")
```

**`deeprepo/terminal_ui.py:48-79`** — Success banner always prints:
```python
def print_init_complete(generated_files, cost, turns, sub_dispatches):
    print_msg("Done! Generated:")
    ...
def print_onboarding():
    content = "  Your project now has AI memory.\n"
    ...
```

**`deeprepo/cli_commands.py:118-130`** — Called unconditionally after analysis:
```python
if not quiet:
    ui.print_init_complete(generated_files, ...)
    ...
    ui.print_onboarding()
```
There is no check for `result["analysis"]` containing the incomplete marker.

**CF-4 confirmed:** `_validate_messages()` at `rlm_scaffold.py:579-602` only checks list-type content blocks. String content of `""` passes validation:
```python
if not isinstance(content, list):
    continue  # Skips string content entirely
```
An empty string message would cause an API 400 error: "text content blocks must be non-empty".

### Confirmed Findings Validated

- **CF-3:** Confirmed — fallback at lines 265-272 discards prose, returns placeholder.
- **CF-4:** Confirmed — `_validate_messages()` doesn't check string content `""`. The check at line 587 (`if not isinstance(content, list): continue`) skips string validation entirely.
- **CF-5:** Confirmed — relevant because different defaults mean users hit max-turns at different thresholds depending on entry point.
- **CF-6:** Confirmed — `cost_limit: float = 2.00` at `config_manager.py:18` is defined but never checked anywhere. `grep -rn "cost_limit" deeprepo/ --include="*.py"` returns only the definition. The user pays regardless.

### Proposed Fix Plan

1. **Salvage REPL outputs** when `answer["ready"]` is False. After line 272 in `rlm_scaffold.py`:
   ```python
   if not answer["content"] or answer["content"] == "[Analysis incomplete — max turns reached]":
       # Salvage intermediate outputs from trajectory
       salvaged_parts = []
       for entry in trajectory:
           if entry["repl_output"] and entry["repl_output"] != "[No output]":
               salvaged_parts.append(entry["repl_output"])
       if salvaged_parts:
           answer["content"] = (
               "[Analysis incomplete — max turns reached. Partial results below]\n\n"
               + "\n\n---\n\n".join(salvaged_parts)
           )
   ```

2. **Add failure detection** in `cli_commands.py`. Before calling `print_init_complete()`:
   ```python
   if "[Analysis incomplete" in result["analysis"]:
       ui.print_error(f"Analysis incomplete after {result['turns']} turns (${result['usage'].total_cost:.4f})")
       ui.print_msg("Try increasing --max-turns or using a different root model.")
   else:
       ui.print_init_complete(...)
       ui.print_onboarding()
   ```

3. **Fix `_validate_messages()`** to handle string content. After line 587:
   ```python
   if isinstance(content, str):
       if not content.strip():
           msg["content"] = "[Acknowledged]"
       continue
   ```

4. **Enforce `cost_limit`** (CF-6 fix). In the REPL loop, check `self.usage.total_cost` against the configured limit and break if exceeded, with a clear message.

**Complexity:** Medium — touches REPL engine, CLI output logic, message validation, and optionally cost enforcement.

### Risk Assessment

- **Salvage quality:** REPL outputs are raw execution results (print statements, error traces). They're better than nothing but not polished analysis. May confuse users expecting a clean document.
- **`_validate_messages` fix:** Could mask real issues if a model legitimately sends empty content. The `[Acknowledged]` placeholder is already used elsewhere (line 601) so this is consistent.
- **Cost limit enforcement:** Requires deciding behavior when limit is hit mid-analysis. Should it salvage and stop, or warn and continue?

---

## Cross-Cutting Findings

### Additional Issues Discovered

1. **`os` module in REPL namespace is a security concern** beyond just `__builtins__` (Issue #18). The `os` module at `rlm_scaffold.py:335` provides `os.system()`, `os.environ`, `os.remove()`, etc. even if `__builtins__` is restricted.

2. **`cost_limit` is dead code (CF-6 expansion):** `config_manager.py:18` defines `cost_limit: float = 2.00` but it is never checked or enforced anywhere in the codebase. The user can rack up unbounded costs. This is especially dangerous combined with Issue #22 (model wastes turns without producing output).

3. **`pytest` is not a dev dependency:** `pyproject.toml:48-52` lists only `build` and `twine` in dev dependencies. `pytest` must be installed manually. This should be added for Issue #19 CI.

4. **No `--debug` or logging infrastructure at all:** `grep -rn "import logging" deeprepo/` returns zero matches. This affects debugging for all issues, not just #21.

5. **`_estimate_tons` typo alias** in `prompt_builder.py:301-302`: A method named `_estimate_tons` exists as a "backward-compatible alias for spec typo." This is minor but indicates a history of spec-driven development without cleanup.

6. **`scaffold.py` creates its own `openai.OpenAI` client** on every call (lines 167-169) instead of reusing the `SubModelClient` or a shared client. This is inconsistent with the architecture of `llm_clients.py`.

### Dependency Map

```
Issue #22 (no turn-budget) ←──── CF-1 (no tool_choice)
         │                 ←──── CF-2 (no turn countdown)
         │                 ←──── CF-5 (split max_turns defaults)
         ↓
Issue #23 (silent failure) ←──── CF-3 (fallback discards prose)
         │                 ←──── CF-4 (empty string validation)
         │                 ←──── CF-6 (cost_limit dead code)
         ↓
Issue #18 (security)       — independent but affects risk of #22/#23 (malicious code during wasted turns)
Issue #20 (retry)          — independent
Issue #21 (logging)        — independent but helps debug all others
Issue #19 (CI)             — independent but validates all fixes
```

**Shared root causes:**
- Issues #22 and #23 share CF-1, CF-2, CF-3, CF-5 — they are two symptoms of the same problem (model can waste turns without consequence).
- CF-5 (split defaults) affects both #22 (how many turns the model gets) and #23 (when the failure triggers).
- CF-6 (dead cost_limit) exacerbates #23 (user pays for wasted analysis).

### Recommended Fix Order

1. **Issue #22 + #23 together (critical, shared root cause)** — Fix turn-budget awareness, `tool_choice` forcing, output salvaging, and failure detection. These are the highest-impact user-facing bugs and share root causes. Estimated: 1-2 days.

2. **Issue #20 (trivial)** — Add retry to `scaffold.py`. Can be done in 10 minutes. Quick win.

3. **Issue #18 (security)** — Restrict builtins and `os` module. Requires careful allowlist tuning against real trajectories. Estimated: half day.

4. **Issue #21 (logging)** — Add logging infrastructure and `--debug` flag. Helps debug all other issues during development. Estimated: half day.

5. **Issue #19 (CI)** — Create GitHub Actions workflow. Should be done last so it can validate all the above fixes. Estimated: 1-2 hours.

6. **CF-5 (max_turns unification)** — Part of #22 fix. Unify to config_manager's value of 20.

7. **CF-6 (cost_limit enforcement)** — Optional, can be done alongside #23 or as a follow-up.
