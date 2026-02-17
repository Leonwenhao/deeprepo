# deeprepo — Development Guide (V0)

## For: Claude Code implementation reference
## Author: Leon
## Date: February 14, 2026

---

## What This Project Is

A Python CLI tool that analyzes codebases using the Recursive Language Model (RLM) pattern. NOT model training — this is an inference scaffold that orchestrates API calls between two LLMs.

**Core loop:**
1. Load a codebase into a Python dict (filepath → content)
2. Give Claude Opus 4.6 (root model) only METADATA (file tree, sizes, types)
3. Opus writes Python code → we execute it in a controlled namespace
4. That code can call `llm_query()`/`llm_batch()` → hits MiniMax M2.5 via OpenRouter
5. We feed REPL output back to Opus → it writes more code → iterates
6. When Opus sets `answer["ready"] = True`, we return the analysis

---

## Tech Stack

- **Python 3.11+** with `uv` package manager
- **anthropic** SDK — for Opus 4.6 root model calls
- **openai** SDK — for MiniMax M2.5 via OpenRouter (OpenAI-compatible API)
- **python-dotenv** — env var management
- **asyncio** — parallel sub-LLM dispatch in `llm_batch()`
- No web framework, no database, no frontend. Pure CLI tool.

---

## API Configuration

### Environment Variables (.env file)
```
ANTHROPIC_API_KEY=sk-ant-...        # For Opus 4.6 root model
OPENROUTER_API_KEY=sk-or-...        # For MiniMax M2.5 sub-LLM
```

### Root Model (Opus 4.6)
- SDK: `anthropic` Python package
- Model string: `claude-opus-4-6`
- Endpoint: Anthropic API directly (NOT through OpenRouter)
- Max tokens per response: 8192
- Temperature: 0.0
- Pricing: $15/M input, $75/M output

### Sub-LLM (MiniMax M2.5)
- SDK: `openai` Python package (OpenRouter is OpenAI-compatible)
- Model string: `minimax/minimax-m2.5`
- Base URL: `https://openrouter.ai/api/v1`
- API key: OpenRouter key (NOT MiniMax key)
- Max tokens per response: 4096
- Temperature: 0.0
- Pricing: $0.20/M input, $1.10/M output
- Supports async via `openai.AsyncOpenAI`

### API Call Examples

**Root model call:**
```python
import anthropic
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=8192,
    system="You are operating in an RLM environment...",
    messages=[{"role": "user", "content": "..."}],
    temperature=0.0,
)
text = response.content[0].text
input_tokens = response.usage.input_tokens
output_tokens = response.usage.output_tokens
```

**Sub-LLM call (sync):**
```python
import openai
client = openai.OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)
response = client.chat.completions.create(
    model="minimax/minimax-m2.5",
    messages=[
        {"role": "system", "content": "You are a code analysis expert..."},
        {"role": "user", "content": "Analyze this file: ..."},
    ],
    max_tokens=4096,
    temperature=0.0,
)
text = response.choices[0].message.content
```

**Sub-LLM call (async, for llm_batch):**
```python
import openai
async_client = openai.AsyncOpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)
response = await async_client.chat.completions.create(
    model="minimax/minimax-m2.5",
    messages=[...],
    max_tokens=4096,
)
```

---

## Module Architecture

### Build Order (do these in sequence)

#### Step 1: `deeprepo/llm_clients.py` — API Wrappers

**Purpose:** Thin wrappers around Anthropic + OpenRouter APIs with token tracking.

**Classes:**

`TokenUsage` (dataclass):
- Fields: `root_input_tokens`, `root_output_tokens`, `sub_input_tokens`, `sub_output_tokens`, `root_calls`, `sub_calls`
- Properties: `root_cost`, `sub_cost`, `total_cost` (calculated from token counts × pricing)
- Method: `summary() -> str` (human-readable cost report)

`RootModelClient`:
- Constructor: takes `usage: TokenUsage`, `model: str = "claude-opus-4-6"`
- Creates `anthropic.Anthropic` client from env var
- Method: `complete(messages, system, max_tokens, temperature) -> str`
- Must update `usage` after each call (input/output tokens, call count)

`SubModelClient`:
- Constructor: takes `usage: TokenUsage`, `model: str = "minimax/minimax-m2.5"`
- Creates both `openai.OpenAI` and `openai.AsyncOpenAI` clients
- Method: `query(prompt, system, max_tokens) -> str` (sync, single call)
- Method: `batch(prompts, system, max_tokens, max_concurrent) -> list[str]` (async parallel)
- `batch()` uses `asyncio.Semaphore(max_concurrent)` to limit parallelism (default 5)
- `batch()` calls `asyncio.run()` internally — caller doesn't need to be async
- Must handle exceptions in batch: convert to `"[ERROR: ...]"` strings, don't crash

**Test criteria:** Can call both APIs and get text responses. Token counts are tracked.

#### Step 2: `deeprepo/codebase_loader.py` — Codebase Loading

**Purpose:** Load a local directory into a structured format for the REPL.

**Functions:**

`clone_repo(url: str, target_dir: str | None) -> str`:
- Runs `git clone --depth 1 <url> <target_dir>`
- Returns the target directory path

`load_codebase(path: str) -> dict`:
- Walks the directory tree
- Skips: `node_modules`, `.git`, `__pycache__`, `venv`, `dist`, `build`, etc.
- Includes files with code extensions (`.py`, `.js`, `.ts`, etc.), config extensions (`.json`, `.yaml`, `.toml`), and doc extensions (`.md`, `.txt`)
- Skips files > 500KB
- Returns:
  ```python
  {
      "codebase": {"src/main.py": "file content...", ...},  # filepath → content
      "file_tree": "repo_name/\n  src/\n    main.py\n  ...",  # visual tree string
      "metadata": {
          "repo_name": "my-repo",
          "total_files": 42,
          "total_chars": 150000,
          "total_lines": 4200,
          "file_types": {".py": 20, ".js": 10, ...},
          "largest_files": [("src/big.py", 50000), ...],  # top 15, sorted desc
          "entry_points": ["main.py", "app.py", ...],      # detected entry points
      }
  }
  ```

`format_metadata_for_prompt(metadata: dict) -> str`:
- Formats metadata dict into a human-readable string
- This goes into the root model's context (the ONLY info about the codebase it sees directly)

**Entry point detection:** Look for common filenames (`main.py`, `app.py`, `index.js`, `manage.py`, etc.) and files containing `if __name__ == "__main__"`.

**Test criteria:** Load `tests/test_small/` → get 3 files, correct tree, metadata.

#### Step 3: `deeprepo/prompts.py` — System Prompts

**Purpose:** Two prompts that drive the RLM behavior.

**`ROOT_SYSTEM_PROMPT`** — tells Opus how to be an RLM orchestrator:
- Explains the REPL environment
- Documents available variables: `codebase`, `file_tree`, `metadata`
- Documents available functions: `print()`, `llm_query()`, `llm_batch()`
- Defines the analysis task (architecture, bugs, quality, dev plan)
- Gives concrete code examples for each workflow step
- Key rules: don't finalize early, use llm_batch for parallelism, iterate

**`SUB_SYSTEM_PROMPT`** — tells M2.5 how to analyze code:
- Concise, focused analysis
- Cover: purpose, issues, quality, suggestions
- Keep responses under 1000 words

**`ROOT_USER_PROMPT_TEMPLATE`** — the initial user message:
- Contains `{metadata_str}` and `{file_tree}` placeholders
- Tells the model to start exploring

**Test criteria:** Prompts are strings, template formats without error.

#### Step 4: `deeprepo/rlm_scaffold.py` — The Core Engine

**Purpose:** The REPL loop that ties everything together. This is the heart of the project.

**Class: `RLMEngine`**

Constructor params:
- `root_client: RootModelClient`
- `sub_client: SubModelClient`  
- `usage: TokenUsage`
- `max_turns: int = 15`
- `max_output_length: int = 8192`
- `verbose: bool = True`

**Method: `analyze(codebase_path: str) -> dict`**

This is the main loop. Here's the exact flow:

```
1. Call load_codebase(path) → get codebase, file_tree, metadata
2. Create answer = {"content": "", "ready": False}
3. Build REPL namespace dict with: codebase, file_tree, metadata, llm_query, llm_batch, answer, re, os, json, collections
4. Format initial user message with metadata + file_tree (NOT file contents)
5. messages = [{"role": "user", "content": user_prompt}]
6. LOOP (max_turns iterations):
   a. Call root_client.complete(messages, system=ROOT_SYSTEM_PROMPT) → response_text
   b. Extract Python code blocks from response_text (look for ```python ... ```)
   c. If no code blocks found:
      - If answer["ready"], break
      - Otherwise append assistant msg + user msg asking for code, continue
   d. For each code block:
      - Execute with exec(code, namespace)
      - Capture stdout via io.StringIO + contextlib.redirect_stdout
      - Catch exceptions, include traceback in output
   e. Combine all outputs, truncate to max_output_length
   f. Record trajectory step
   g. If answer["ready"], break
   h. Append assistant msg + user msg with REPL output to messages
7. Return {"analysis": answer["content"], "turns": N, "usage": usage, "trajectory": [...]}
```

**Key implementation details:**

The REPL namespace — what the root model's code has access to:
```python
namespace = {
    "codebase": codebase,           # dict: filepath → content
    "file_tree": file_tree,         # string
    "metadata": metadata,           # dict
    "llm_query": llm_query,         # function: str → str
    "llm_batch": llm_batch,         # function: list[str] → list[str]
    "set_answer": set_answer,       # function: str → None (sets answer + marks ready)
    "answer": answer,               # dict: {"content": "", "ready": False}
    "re": re,                       # standard library
    "os": os,
    "json": json,
    "collections": collections,
    "__builtins__": __builtins__,    # Python builtins (print, len, etc.)
}
```

Code extraction — parse the root model's response for Python code:
- Primary: regex for ```python\n...\n``` blocks **with line-boundary anchors** (`^`/`$` + `re.MULTILINE`)
- This prevents inline ` ``` ` inside Python strings from being matched as code fence closers
- Pattern: `r'^```(?:python)?\s*\n(.*?)\n```\s*$'` with `re.DOTALL | re.MULTILINE`
- Fallback: heuristic detection of bare Python lines
- Return list of code strings

`set_answer(text)` helper — avoids string-escaping issues:
- The root model's code runs via `exec()`, where triple-quoted strings containing markdown backticks cause SyntaxErrors
- `set_answer(text)` sets `answer["content"] = text` and `answer["ready"] = True` in one call
- The system prompt instructs the model to build text via `lines.append()` + `set_answer("\n".join(lines))`
- This eliminated all string-escaping failures and reduced test_small from 5 turns to 1 turn

Code execution — run in controlled namespace:
- Use `exec(code, namespace)` 
- Capture stdout with `io.StringIO` + `contextlib.redirect_stdout`
- Catch all exceptions, return traceback as output string
- The namespace persists across code blocks within a turn AND across turns (variables accumulate)

Output truncation:
- Cap REPL output at 8192 chars
- If truncated, append message: "[OUTPUT TRUNCATED at 8192 chars. Use code to filter/search.]"
- This forces the model to use programmatic approaches instead of dumping raw content

Message threading — how conversation with root model works:
```python
# Turn 1:
messages = [{"role": "user", "content": initial_prompt_with_metadata}]
response = root_client.complete(messages, system=ROOT_SYSTEM_PROMPT)
# Execute code, get output
messages.append({"role": "assistant", "content": response})
messages.append({"role": "user", "content": f"REPL Output:\n```\n{output}\n```\nContinue..."})

# Turn 2:
response = root_client.complete(messages, system=ROOT_SYSTEM_PROMPT)
# Execute code, get output
messages.append({"role": "assistant", "content": response})
messages.append({"role": "user", "content": f"REPL Output:\n```\n{output}\n```\nContinue..."})

# ... until answer["ready"] = True or max_turns
```

**Convenience function: `run_analysis(codebase_path, verbose, max_turns) -> dict`**
- Handles git URL cloning
- Creates TokenUsage, RootModelClient, SubModelClient
- Instantiates and runs RLMEngine
- Returns result dict

**Test criteria:** Run against `tests/test_small/` (3 files with planted bugs). The analysis should identify at least: SQL injection, hardcoded secret key, debug mode, MD5 hashing, unclosed DB connections.

#### Step 5: `deeprepo/baseline.py` — Single-Model Comparison

**Purpose:** Run the same analysis task through a single Opus call (no REPL, no sub-LLMs) for comparison.

**Function: `run_baseline(codebase_path, max_chars, verbose) -> dict`**
- Loads codebase same as RLM
- Concatenates file contents into one big prompt (entry points first, then smallest files first to maximize coverage)
- Stops adding files when hitting `max_chars` (default 180,000 — ~45k tokens, leaving room for response)
- Sends everything to Opus in a single call
- Tracks which files were included vs excluded
- Returns: `{"analysis": str, "usage": TokenUsage, "included_files": [], "excluded_files": [], "prompt_chars": int, "elapsed_seconds": float}`

**Test criteria:** Run on same test codebase, produces analysis, tracks cost.

#### Step 6: `deeprepo/cli.py` — CLI Interface

**Purpose:** Command-line entry point.

**Commands:**
```bash
python -m deeprepo.cli analyze /path/to/repo          # RLM analysis
python -m deeprepo.cli analyze https://github.com/... # Clone + analyze
python -m deeprepo.cli baseline /path/to/repo          # Single-model comparison
python -m deeprepo.cli compare /path/to/repo           # Run both, show metrics side-by-side
```

**Options:**
- `-o, --output-dir` — where to save results (default: `outputs/`)
- `-q, --quiet` — suppress verbose output
- `--max-turns` — max REPL iterations (default: 15)

**Output files:**
- `outputs/deeprepo_{repo}_{timestamp}.md` — the analysis document
- `outputs/deeprepo_{repo}_{timestamp}_metrics.json` — token counts, costs, timing

---

## Data Flow Diagram

```
User runs CLI
    │
    ▼
cli.py → codebase_loader.py
    │         │
    │         ▼
    │     load_codebase()
    │         │
    │         ▼
    │     {codebase, file_tree, metadata}
    │
    ▼
rlm_scaffold.py (RLMEngine)
    │
    ├─── Build REPL namespace with codebase data + llm functions
    │
    ├─── Format initial prompt (metadata + tree, NOT file contents)
    │
    └─── REPL LOOP:
         │
         ├── root_client.complete() ──→ llm_clients.py ──→ Anthropic API (Opus 4.6)
         │       │
         │       ▼
         │   Response contains Python code
         │       │
         │       ▼
         │   exec(code, namespace)  ←── Code can access codebase dict
         │       │                      Code can call llm_query/llm_batch
         │       │
         │       ├── llm_query() ──→ llm_clients.py ──→ OpenRouter API (M2.5)
         │       ├── llm_batch() ──→ llm_clients.py ──→ OpenRouter API (M2.5) × N parallel
         │       │
         │       ▼
         │   Capture stdout as REPL output
         │       │
         │       ▼
         │   Feed output back as next user message
         │       │
         │       ▼
         │   Check answer["ready"] → if True, exit loop
         │
         ▼
    Return answer["content"] + metrics
```

---

## Known Issues & Edge Cases to Handle

1. **asyncio.run() inside sync code:** `llm_batch()` calls `asyncio.run()` internally. If the caller already has an event loop running, this will error. May need `nest_asyncio` as a fallback, or restructure to use `loop.run_until_complete()`.

2. **Root model not writing code blocks:** Sometimes the model will respond with plain text analysis instead of code. The engine should detect this and prompt it to write code.

3. **Root model setting answer["ready"] too early:** The system prompt warns against this, but it may still happen on turn 1. The engine should check if `answer["content"]` is substantive before accepting.

4. **Large codebases:** If the codebase has hundreds of files, `llm_batch()` with all files would be expensive. The root model should be strategic — the prompt encourages analyzing key files first.

5. **OpenRouter rate limits:** With parallel batch calls, we might hit rate limits. The semaphore (default 5 concurrent) helps, but may need retry logic with backoff.

6. **Code execution safety:** For V0, we use `exec()` in the same process. This means the root model's code could theoretically do anything (delete files, make network calls). For V0 this is acceptable since we control the input. For V1+, move to subprocess or sandbox.

7. **REPL namespace persistence:** The namespace dict persists across turns AND across code blocks within a turn. Variables set in turn 1 are available in turn 3. This is intentional — it mirrors a real REPL.

8. **~~String escaping in exec():~~** ✅ FIXED. Root model's code containing triple backticks (` ``` `) inside strings was truncated by the code extraction regex. Fixed with line-boundary anchors in the regex + `set_answer()` helper. Reduced test_small from 5 turns/$2.59 to 1 turn/$0.34. Residual: model occasionally uses `f"""..."""` with embedded backticks on large codebases, causing 1-2 wasted turns before self-correcting.

9. **Conversation history token bloat:** Multi-turn REPL loop accumulates full conversation history. On Jianghu (5 turns), input tokens reached 128K. Root model cost is ~98% of total. Future: add history summarization/compression between turns.

10. **`run_baseline()` git URL handling:** ✅ FIXED. `run_baseline()` and `cmd_compare()` now handle git URLs (clone before loading). Previously, passing a URL to baseline loaded 0 files.

---

## Testing Sequence

1. **Unit test API connectivity:**
   ```python
   # Test Anthropic
   client = anthropic.Anthropic()
   resp = client.messages.create(model="claude-opus-4-6", max_tokens=100, messages=[{"role":"user","content":"Say hello"}])
   print(resp.content[0].text)
   
   # Test OpenRouter → M2.5
   client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
   resp = client.chat.completions.create(model="minimax/minimax-m2.5", messages=[{"role":"user","content":"Say hello"}], max_tokens=100)
   print(resp.choices[0].message.content)
   ```

2. **Unit test codebase loader:** Load `tests/test_small/`, verify 3 files, correct metadata.

3. **Integration test — small codebase:** Run full `analyze` on `tests/test_small/`. Should complete in 3-5 turns, find the planted bugs. Cost should be < $0.50.

4. **Integration test — real codebase:** Run on Jianghu V3 (or any real repo). Expect 8-15 turns, $1-3.

5. **Comparison test:** Run `compare` command on `tests/test_small/`. Verify both approaches produce analysis, metrics are captured.

---

## Success Criteria for V0

- [ ] Both API connections work (Anthropic + OpenRouter)
- [ ] Codebase loader correctly parses directory structures
- [ ] Root model writes executable Python code in the REPL
- [ ] `llm_query()` and `llm_batch()` successfully call M2.5
- [ ] REPL output is captured and fed back to root model
- [ ] Root model iterates and eventually sets `answer["ready"] = True`
- [ ] Final analysis identifies real issues in the test codebase
- [ ] Baseline comparison runs and produces metrics
- [ ] Total cost per analysis run is < $5
