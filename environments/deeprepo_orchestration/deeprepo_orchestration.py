"""
DeepRepo Orchestration RL Environment for Prime Intellect.

Train models to exhaustively delegate codebase analysis tasks to sub-LLM workers
using the RLM (Recursive Language Model) pattern.

Env type: Custom MultiTurnEnv subclass
Reward: shaped — coverage (0.5) + finding quality (0.3) + efficiency (0.2)
"""

import ast
import builtins
import hashlib
import io
import json
import os
import re
import signal
import threading
import traceback
from contextlib import redirect_stdout, redirect_stderr
from difflib import SequenceMatcher
from types import SimpleNamespace

import verifiers as vf
from datasets import Dataset

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_OUTPUT_LENGTH = 8192
EXEC_TIMEOUT_SECONDS = 30

SAFE_BUILTIN_NAMES = {
    "__build_class__",
    "Exception", "TypeError", "ValueError", "RuntimeError",
    "AttributeError", "IndexError", "KeyError", "NameError",
    "AssertionError", "TimeoutError",
    "abs", "all", "any", "bool", "dict", "enumerate", "filter",
    "float", "format", "int", "isinstance", "issubclass", "len",
    "list", "map", "max", "min", "next", "print", "range", "repr",
    "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
}

SAFE_BUILTINS = {name: getattr(builtins, name) for name in SAFE_BUILTIN_NAMES}

# ---------------------------------------------------------------------------
# System prompt — Qwen-compatible, no Anthropic/Claude references
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert code analysis agent operating in a Python REPL environment.

## Your Situation
A codebase has been loaded into your REPL. You do NOT see the file contents \
directly — they are stored as variables you access through code. You will \
explore the codebase programmatically, dispatching focused analysis tasks to \
sub-LLM workers.

## Available Variables
- `codebase` — dict mapping relative file paths to file contents (strings)
- `file_tree` — string showing the directory structure
- `metadata` — dict with repo stats: total_files, total_chars, file_types, \
largest_files, entry_points

## Available Functions
- `print(x)` — display output (truncated to 8192 chars per turn)
- `llm_query(prompt: str) -> str` — send a focused task to a sub-LLM worker
- `llm_batch(prompts: list[str]) -> list[str]` — send multiple tasks in \
PARALLEL (faster, prefer this)
- `set_answer(text: str)` — submit your final analysis and end the session

## How to Write Code
Write your Python code inside a fenced code block:

```python
print(file_tree)
```

Each turn, write ONE code block. It will be executed and you will see the output.

## Your Task
Produce a comprehensive codebase analysis covering:
1. **Architecture Overview** — entry points, module dependencies, data flow
2. **Bug & Issue Audit** — security issues, logic errors, error handling gaps
3. **Code Quality Assessment** — patterns, test coverage, documentation
4. **Prioritized Recommendations** — P0/P1/P2 with what/why/complexity

## Strategy
1. **Explore first** — print file_tree and metadata
2. **Dispatch analysis to sub-LLMs** — use llm_batch() to analyze files in \
PARALLEL
3. **Be exhaustive** — analyze ALL important files, not just a few
4. **Synthesize findings** — combine sub-LLM results into your final analysis
5. **Call set_answer()** — submit your complete analysis when done

## Rules
1. Use llm_batch() for parallel analysis — faster than sequential llm_query()
2. Keep sub-LLM prompts focused — one file or one question per prompt
3. Build findings iteratively — accumulate results in variables across turns
4. Use print() to see output — truncated to 8192 chars
5. Use code to filter/search — do not print entire large files
6. Use set_answer() with the lines.append() pattern to submit your answer
7. Preloaded modules: re, json, collections, os.path (no import statements)
"""

# ---------------------------------------------------------------------------
# Built-in mini dataset (for smoke testing without prepare_dataset.py)
# ---------------------------------------------------------------------------

MINI_DATASET = [
    {
        "name": "mini-calculator",
        "codebase": {
            "calc/__init__.py": (
                "from .operations import add, subtract, multiply, divide\n"
                "from .advanced import power, sqrt, factorial\n"
            ),
            "calc/operations.py": (
                "def add(a, b):\n    return a + b\n\n"
                "def subtract(a, b):\n    return a - b\n\n"
                "def multiply(a, b):\n    return a * b\n\n"
                "def divide(a, b):\n"
                "    if b == 0:\n"
                "        raise ValueError('Cannot divide by zero')\n"
                "    return a / b\n"
            ),
            "calc/advanced.py": (
                "def power(base, exp):\n    return base ** exp\n\n"
                "def sqrt(n):\n"
                "    if n < 0:\n"
                "        raise ValueError('Cannot take sqrt of negative')\n"
                "    return n ** 0.5\n\n"
                "def factorial(n):\n"
                "    if n < 0:\n"
                "        raise ValueError('Negative factorial')\n"
                "    result = 1\n"
                "    for i in range(2, n + 1):\n"
                "        result *= i\n"
                "    return result\n"
            ),
            "calc/parser.py": (
                "def parse_expression(expr):\n"
                "    import re\n"
                "    tokens = re.findall(r'\\d+\\.?\\d*|[+\\-*/()]', expr)\n"
                "    return tokens\n\n"
                "def evaluate(expr):\n"
                "    # WARNING: eval is dangerous — should use a proper parser\n"
                "    try:\n"
                "        return eval(expr)\n"
                "    except Exception as e:\n"
                "        return str(e)\n"
            ),
            "tests/test_operations.py": (
                "from calc.operations import add, subtract, multiply, divide\n\n"
                "def test_add():\n    assert add(2, 3) == 5\n\n"
                "def test_subtract():\n    assert subtract(5, 3) == 2\n\n"
                "def test_divide_by_zero():\n"
                "    try:\n        divide(1, 0)\n        assert False\n"
                "    except ValueError:\n        pass\n"
            ),
            "README.md": "# Calculator\n\nA simple calculator library with basic and advanced operations.\n",
            "setup.py": (
                "from setuptools import setup, find_packages\n"
                "setup(name='calc', version='0.1.0', packages=find_packages())\n"
            ),
        },
        "file_tree": (
            "mini-calculator/\n"
            "  calc/\n"
            "    __init__.py\n"
            "    operations.py\n"
            "    advanced.py\n"
            "    parser.py\n"
            "  tests/\n"
            "    test_operations.py\n"
            "  README.md\n"
            "  setup.py"
        ),
        "metadata": {
            "repo_name": "mini-calculator",
            "total_files": 7,
            "total_chars": 1350,
            "total_lines": 58,
            "file_types": {".py": 5, ".md": 1},
            "largest_files": [
                ["calc/advanced.py", 310],
                ["calc/parser.py", 280],
                ["calc/operations.py", 220],
                ["tests/test_operations.py", 210],
            ],
            "entry_points": ["setup.py", "README.md"],
        },
        "ground_truth_dispatches": 4,
        "ground_truth_findings": [
            "eval() in parser.py is a security vulnerability allowing arbitrary code execution",
            "parse_expression uses import inside function body instead of top-level",
            "Test coverage is minimal — only 3 test cases for operations, none for advanced or parser",
            "Missing type hints throughout the codebase",
            "factorial could overflow for large inputs — no upper bound check",
            "No error handling in __init__.py imports",
        ],
        "llm_cache": {},
    },
    {
        "name": "mini-todo-api",
        "codebase": {
            "app.py": (
                "from flask import Flask, request, jsonify\n"
                "from database import db, init_db\n"
                "from routes import api\n\n"
                "app = Flask(__name__)\n"
                "app.config['SECRET_KEY'] = 'super-secret-key-123'\n"
                "app.register_blueprint(api)\n\n"
                "if __name__ == '__main__':\n"
                "    init_db()\n"
                "    app.run(debug=True, host='0.0.0.0')\n"
            ),
            "database.py": (
                "import sqlite3\n\n"
                "db = None\n\n"
                "def init_db():\n"
                "    global db\n"
                "    db = sqlite3.connect('todos.db')\n"
                "    db.execute('CREATE TABLE IF NOT EXISTS todos '\n"
                "               '(id INTEGER PRIMARY KEY, title TEXT, done BOOLEAN)')\n"
                "    db.commit()\n\n"
                "def query(sql, params=None):\n"
                "    cursor = db.execute(sql, params or [])\n"
                "    db.commit()\n"
                "    return cursor.fetchall()\n"
            ),
            "routes.py": (
                "from flask import Blueprint, request, jsonify\n"
                "from database import query\n\n"
                "api = Blueprint('api', __name__)\n\n"
                "@api.route('/todos', methods=['GET'])\n"
                "def get_todos():\n"
                "    rows = query('SELECT * FROM todos')\n"
                "    return jsonify([{'id': r[0], 'title': r[1], 'done': r[2]} for r in rows])\n\n"
                "@api.route('/todos', methods=['POST'])\n"
                "def create_todo():\n"
                "    data = request.get_json()\n"
                "    title = data['title']\n"
                "    query(f\"INSERT INTO todos (title, done) VALUES ('{title}', 0)\")\n"
                "    return jsonify({'status': 'created'}), 201\n\n"
                "@api.route('/todos/<int:todo_id>', methods=['DELETE'])\n"
                "def delete_todo(todo_id):\n"
                "    query(f'DELETE FROM todos WHERE id = {todo_id}')\n"
                "    return jsonify({'status': 'deleted'})\n"
            ),
            "auth.py": (
                "import hashlib\n\n"
                "USERS = {}\n\n"
                "def register(username, password):\n"
                "    hashed = hashlib.md5(password.encode()).hexdigest()\n"
                "    USERS[username] = hashed\n\n"
                "def login(username, password):\n"
                "    hashed = hashlib.md5(password.encode()).hexdigest()\n"
                "    return USERS.get(username) == hashed\n"
            ),
            "tests/test_routes.py": (
                "def test_get_todos():\n"
                "    # TODO: implement test\n"
                "    pass\n\n"
                "def test_create_todo():\n"
                "    # TODO: implement test\n"
                "    pass\n"
            ),
            "requirements.txt": "flask==3.0.0\n",
            "README.md": "# Todo API\n\nA simple Flask-based todo list API.\n",
        },
        "file_tree": (
            "mini-todo-api/\n"
            "  app.py\n"
            "  database.py\n"
            "  routes.py\n"
            "  auth.py\n"
            "  tests/\n"
            "    test_routes.py\n"
            "  requirements.txt\n"
            "  README.md"
        ),
        "metadata": {
            "repo_name": "mini-todo-api",
            "total_files": 7,
            "total_chars": 1480,
            "total_lines": 62,
            "file_types": {".py": 5, ".txt": 1, ".md": 1},
            "largest_files": [
                ["routes.py", 520],
                ["database.py", 350],
                ["auth.py", 230],
                ["app.py", 280],
            ],
            "entry_points": ["app.py", "README.md"],
        },
        "ground_truth_dispatches": 5,
        "ground_truth_findings": [
            "SQL injection in routes.py — f-string interpolation in INSERT and DELETE queries",
            "Hardcoded SECRET_KEY in app.py",
            "Using MD5 for password hashing in auth.py — cryptographically broken",
            "debug=True and host='0.0.0.0' in production is a security risk",
            "No authentication middleware — all routes are public",
            "SQLite connection is a global variable — not thread-safe",
            "Tests are empty stubs with no assertions",
            "No input validation on POST /todos",
        ],
        "llm_cache": {},
    },
    {
        "name": "mini-blog",
        "codebase": {
            "blog/app.py": (
                "from flask import Flask, render_template_string, request\n\n"
                "app = Flask(__name__)\n"
                "posts = []\n\n"
                "@app.route('/')\n"
                "def index():\n"
                "    html = '<h1>Blog</h1>'\n"
                "    for p in posts:\n"
                "        html += f'<h2>{p[\"title\"]}</h2><p>{p[\"body\"]}</p>'\n"
                "    return html\n\n"
                "@app.route('/post', methods=['POST'])\n"
                "def create_post():\n"
                "    title = request.form.get('title', '')\n"
                "    body = request.form.get('body', '')\n"
                "    posts.append({'title': title, 'body': body})\n"
                "    return 'Created', 201\n\n"
                "@app.route('/search')\n"
                "def search():\n"
                "    q = request.args.get('q', '')\n"
                "    results = [p for p in posts if q.lower() in p['title'].lower()]\n"
                "    html = f'<h1>Search: {q}</h1>'\n"
                "    for p in results:\n"
                "        html += f'<p>{p[\"title\"]}</p>'\n"
                "    return html\n"
            ),
            "blog/models.py": (
                "class Post:\n"
                "    def __init__(self, title, body, author='anonymous'):\n"
                "        self.title = title\n"
                "        self.body = body\n"
                "        self.author = author\n"
                "        self.comments = []\n\n"
                "    def add_comment(self, text):\n"
                "        self.comments.append(text)\n\n"
                "    def to_dict(self):\n"
                "        return {'title': self.title, 'body': self.body, "
                "'author': self.author, 'comments': self.comments}\n"
            ),
            "blog/utils.py": (
                "import os\n\n"
                "def read_config():\n"
                "    config_path = os.environ.get('CONFIG_PATH', 'config.json')\n"
                "    with open(config_path) as f:\n"
                "        return eval(f.read())  # should use json.load\n\n"
                "def sanitize(text):\n"
                "    # Incomplete sanitization\n"
                "    return text.replace('<script>', '')\n"
            ),
            "blog/config.json": '{"debug": true, "db_url": "sqlite:///blog.db"}\n',
            "tests/test_blog.py": (
                "def test_index():\n"
                "    pass  # not implemented\n\n"
                "def test_create_post():\n"
                "    pass  # not implemented\n"
            ),
            "README.md": "# Mini Blog\n\nA simple Flask blog application.\n",
        },
        "file_tree": (
            "mini-blog/\n"
            "  blog/\n"
            "    app.py\n"
            "    models.py\n"
            "    utils.py\n"
            "    config.json\n"
            "  tests/\n"
            "    test_blog.py\n"
            "  README.md"
        ),
        "metadata": {
            "repo_name": "mini-blog",
            "total_files": 6,
            "total_chars": 1180,
            "total_lines": 50,
            "file_types": {".py": 4, ".json": 1, ".md": 1},
            "largest_files": [
                ["blog/app.py", 520],
                ["blog/models.py", 300],
                ["blog/utils.py", 210],
            ],
            "entry_points": ["README.md"],
        },
        "ground_truth_dispatches": 4,
        "ground_truth_findings": [
            "XSS vulnerability in app.py — user input rendered directly in HTML without escaping",
            "eval() in utils.py read_config — should use json.load for config parsing",
            "Incomplete HTML sanitization in utils.py — only strips <script> tag, trivially bypassed",
            "In-memory posts list is not persistent — data lost on restart",
            "Post model in models.py is defined but never used — app.py uses raw dicts",
            "No CSRF protection on POST /post endpoint",
            "Tests are empty stubs",
            "Search endpoint reflects user query in HTML without escaping (reflected XSS)",
        ],
        "llm_cache": {},
    },
]

# ---------------------------------------------------------------------------
# Helper: extract Python code from markdown fences
# ---------------------------------------------------------------------------


def _extract_code_from_markdown(text: str) -> list[str]:
    """Extract Python code from markdown fenced blocks.

    Handles: ```python, ```py, and bare ``` fences.
    Also strips <think>...</think> tags (Qwen reasoning).
    """
    # Strip thinking tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    blocks: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if re.match(r"^```(?:python|py)?\s*$", lines[i]):
            i += 1
            code_lines: list[str] = []
            while i < len(lines):
                if re.match(r"^```\s*$", lines[i]):
                    break
                code_lines.append(lines[i])
                i += 1
            if code_lines:
                blocks.append("\n".join(code_lines))
        i += 1
    return blocks


# ---------------------------------------------------------------------------
# Helper: safe code execution with timeout
# ---------------------------------------------------------------------------


def _execute_code(code: str, namespace: dict) -> str:
    """Execute Python code in a restricted namespace with timeout."""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    timed_out = False

    def _timeout_handler(signum, frame):
        nonlocal timed_out
        timed_out = True
        raise TimeoutError("Code execution timed out")

    use_signal = (
        hasattr(signal, "SIGALRM")
        and threading.current_thread() is threading.main_thread()
    )
    old_handler = None
    timer = None

    if use_signal:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(EXEC_TIMEOUT_SECONDS)
    else:
        def _set_timed_out():
            nonlocal timed_out
            timed_out = True
        timer = threading.Timer(EXEC_TIMEOUT_SECONDS, _set_timed_out)
        timer.start()

    try:
        parsed = ast.parse(code, mode="exec")
        if any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            for node in ast.walk(parsed)
        ):
            raise PermissionError(
                "Import statements are blocked. "
                "Use preloaded modules: re, json, collections, os.path."
            )
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(compile(parsed, "<repl>", "exec"), namespace)
    except BaseException as exc:
        if isinstance(exc, TimeoutError) or timed_out:
            stdout_capture.write(
                f"\n[EXECUTION ERROR]\n"
                f"Code execution timed out after {EXEC_TIMEOUT_SECONDS}s."
            )
        elif isinstance(exc, (SystemExit, KeyboardInterrupt)):
            stdout_capture.write(
                f"\n[EXECUTION ERROR]\n{type(exc).__name__} is not allowed."
            )
        else:
            tb = traceback.format_exc()
            stdout_capture.write(f"\n[EXECUTION ERROR]\n{tb}")
    finally:
        if use_signal:
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
        elif timer is not None:
            timer.cancel()

    output = stdout_capture.getvalue()
    stderr_output = stderr_capture.getvalue()
    if stderr_output:
        output += f"\n[STDERR]\n{stderr_output}"
    return output if output else "[No output]"


# ---------------------------------------------------------------------------
# Helper: synthetic sub-LLM response (fallback when cache misses)
# ---------------------------------------------------------------------------


def _synthetic_response(prompt: str, codebase: dict) -> str:
    """Generate a synthetic sub-LLM response for uncached prompts."""
    for filepath, content in codebase.items():
        if filepath in prompt:
            lines = content.split("\n")
            defs = [
                l.strip()
                for l in lines
                if l.strip().startswith(("def ", "class "))
            ]
            defs_str = (
                "\n".join(f"  - {d}" for d in defs[:10])
                if defs
                else "  - No functions/classes found"
            )
            return (
                f"Analysis of {filepath}:\n"
                f"- Lines: {len(lines)}\n"
                f"- Key definitions:\n{defs_str}\n"
                f"- Purpose: Implements functionality related to "
                f"{filepath.split('/')[-1].replace('.py', '').replace('_', ' ')}.\n"
                f"- Issues: Review needed for error handling and edge cases.\n"
                f"- Quality: Code follows standard patterns."
            )
    return (
        "Analysis complete. The provided code follows standard patterns. "
        "No critical issues identified in this review. "
        "Consider adding more documentation and tests."
    )


# ---------------------------------------------------------------------------
# Helper: fuzzy matching for finding quality
# ---------------------------------------------------------------------------


def _fuzzy_recall(model_findings: list[str], ground_truth: list[str]) -> float:
    """Compute fuzzy recall of model findings against ground truth."""
    if not ground_truth:
        return 0.5  # no ground truth = partial credit
    if not model_findings:
        return 0.0

    matched = 0
    for gt in ground_truth:
        best_score = 0.0
        for mf in model_findings:
            score = SequenceMatcher(None, gt.lower(), mf.lower()).ratio()
            best_score = max(best_score, score)
        if best_score >= 0.4:
            matched += 1
    return matched / len(ground_truth)


def _extract_findings(answer_text: str) -> list[str]:
    """Extract individual findings from the model's answer text."""
    findings = []
    for line in answer_text.split("\n"):
        line = line.strip()
        if line.startswith(("- ", "* ", "• ")):
            finding = line.lstrip("-*• ").strip()
            if len(finding) > 10:
                findings.append(finding)
    return findings


# ---------------------------------------------------------------------------
# Environment class
# ---------------------------------------------------------------------------


class DeepRepoOrchestrationEnv(vf.MultiTurnEnv):
    """Multi-turn REPL environment for training LLMs to orchestrate
    codebase analysis via sub-LLM delegation."""

    async def setup_state(self, state, **kwargs):
        info = state["info"]
        state["codebase"] = info["codebase"]
        state["file_tree_str"] = info["file_tree"]
        state["repo_metadata"] = info["metadata"]
        state["ground_truth_dispatches"] = info.get("ground_truth_dispatches", 0)
        state["ground_truth_findings"] = info.get("ground_truth_findings", [])
        state["llm_cache"] = info.get("llm_cache", {})

        # Tracking state (mutated during rollout)
        state["dispatch_count"] = 0
        state["unique_files_dispatched"] = []
        state["dispatch_log"] = []
        state["turn_count"] = 0
        state["answer_dict"] = {"content": "", "ready": False}
        state["repl_namespace"] = None  # built lazily
        return await super().setup_state(state, **kwargs)

    def _build_namespace(self, state):
        """Build the isolated REPL namespace for this episode."""
        codebase = state["codebase"]
        file_tree = state["file_tree_str"]
        metadata = state["repo_metadata"]
        answer = state["answer_dict"]
        llm_cache = state["llm_cache"]

        def llm_query(prompt: str) -> str:
            state["dispatch_count"] += 1
            for filepath in codebase:
                if filepath in prompt and filepath not in state["unique_files_dispatched"]:
                    state["unique_files_dispatched"].append(filepath)
            state["dispatch_log"].append(prompt[:200])
            cache_key = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            if cache_key in llm_cache:
                return llm_cache[cache_key]
            return _synthetic_response(prompt, codebase)

        def llm_batch(prompts: list) -> list:
            return [llm_query(p) for p in prompts]

        def set_answer(text: str) -> None:
            answer["content"] = text
            answer["ready"] = True

        namespace = {
            "codebase": codebase,
            "file_tree": file_tree,
            "metadata": metadata,
            "llm_query": llm_query,
            "llm_batch": llm_batch,
            "set_answer": set_answer,
            "answer": answer,
            "re": re,
            "os": SimpleNamespace(path=os.path),
            "json": json,
            "collections": __import__("collections"),
        }
        namespace["__builtins__"] = SAFE_BUILTINS
        return namespace

    async def env_response(self, messages, state, **kwargs):
        state["turn_count"] += 1

        # Build namespace on first call
        if state["repl_namespace"] is None:
            state["repl_namespace"] = self._build_namespace(state)

        # Extract text from the model's last message
        last_content = messages[-1].get("content", "")
        if isinstance(last_content, list):
            last_content = " ".join(
                b.get("text", "")
                for b in last_content
                if isinstance(b, dict)
            )

        code_blocks = _extract_code_from_markdown(last_content)

        if not code_blocks:
            if state["answer_dict"]["ready"]:
                return [{"role": "user", "content": "Session complete."}]
            return [{"role": "user", "content": (
                "No Python code block found. Write your code inside a fenced block:\n\n"
                "```python\n# your code here\n```"
            )}]

        # Execute each code block
        all_output = []
        for code in code_blocks:
            output = _execute_code(code, state["repl_namespace"])
            all_output.append(output)
            if state["answer_dict"]["ready"]:
                break

        combined = "\n".join(all_output)
        if len(combined) > MAX_OUTPUT_LENGTH:
            combined = (
                combined[:MAX_OUTPUT_LENGTH]
                + f"\n\n[OUTPUT TRUNCATED at {MAX_OUTPUT_LENGTH} chars. "
                f"Total was {len(combined)} chars. Use code to filter/search.]"
            )

        # Turn budget reminder
        remaining = self.max_turns - state["turn_count"]
        if remaining <= 2:
            combined += (
                f"\n\n[WARNING: {remaining} turn(s) remaining. "
                "Call set_answer(text) NOW to submit your findings.]"
            )
        elif remaining <= 4:
            combined += (
                f"\n\n[{remaining} turns remaining — begin synthesizing.]"
            )

        return [{"role": "user", "content": f"REPL Output:\n```\n{combined}\n```"}]

    @vf.stop
    async def episode_done(self, state):
        return (
            state.get("answer_dict", {}).get("ready", False)
            or state.get("turn_count", 0) >= self.max_turns
        )


# ---------------------------------------------------------------------------
# Reward function
# ---------------------------------------------------------------------------


async def delegation_reward(state, **kwargs) -> float:
    """Shaped reward for delegation exhaustiveness.

    Components:
    - Coverage (0.5): fraction of files dispatched to sub-LLMs
    - Finding quality (0.3): fuzzy recall against ground truth
    - Efficiency (0.2): completing in reasonable turns
    """
    total_files = state.get("repo_metadata", {}).get("total_files", 1)
    unique_dispatched = len(state.get("unique_files_dispatched", []))
    dispatches = state.get("dispatch_count", 0)

    # Coverage score
    coverage = min(unique_dispatched / max(total_files, 1), 1.0)
    coverage_score = coverage * 0.5

    # Finding quality score
    answer_text = state.get("answer_dict", {}).get("content", "")
    model_findings = _extract_findings(answer_text)
    ground_truth = state.get("ground_truth_findings", [])
    recall = _fuzzy_recall(model_findings, ground_truth)
    finding_score = recall * 0.3

    # Efficiency score
    turns_used = state.get("turn_count", 0)
    if turns_used <= 8:
        efficiency = 1.0
    elif turns_used <= 15:
        efficiency = 1.0 - (turns_used - 8) / 14
    else:
        efficiency = 0.1
    efficiency_score = efficiency * 0.2

    return min(coverage_score + finding_score + efficiency_score, 1.0)


# ---------------------------------------------------------------------------
# load_environment (required entry point)
# ---------------------------------------------------------------------------


def load_environment(
    dataset_path: str = "",
    num_examples: int = -1,
    seed: int = 42,
    **kwargs,
) -> vf.Environment:
    """Load the DeepRepo orchestration environment.

    Args:
        dataset_path: Path to a dataset JSON file. If empty, uses built-in
            mini dataset for smoke testing.
        num_examples: Number of examples to use (-1 = all).
        seed: Random seed for shuffling.
    """
    import random

    # Load raw data
    if dataset_path and os.path.exists(dataset_path):
        with open(dataset_path) as f:
            raw_data = json.load(f)
    else:
        raw_data = MINI_DATASET

    rng = random.Random(seed)
    rng.shuffle(raw_data)

    if num_examples > 0:
        raw_data = raw_data[:num_examples]

    # Build HuggingFace dataset
    rows = []
    for entry in raw_data:
        metadata = entry["metadata"]
        file_tree = entry["file_tree"]

        meta_lines = [
            f"Repository: {entry['name']}",
            f"Total files: {metadata['total_files']}",
            f"Total characters: {metadata.get('total_chars', 0):,}",
        ]
        if "total_lines" in metadata:
            meta_lines.append(f"Total lines: {metadata['total_lines']:,}")
        meta_lines.append("")
        meta_lines.append("File types:")
        for ext, count in metadata.get("file_types", {}).items():
            meta_lines.append(f"  {ext}: {count} files")
        if metadata.get("largest_files"):
            meta_lines.append("")
            meta_lines.append("Largest files:")
            for path, chars in metadata["largest_files"][:10]:
                meta_lines.append(f"  {path}: {chars:,} chars")
        if metadata.get("entry_points"):
            meta_lines.append("")
            meta_lines.append("Entry points:")
            for ep in metadata["entry_points"]:
                meta_lines.append(f"  {ep}")
        metadata_str = "\n".join(meta_lines)

        question = (
            "Analyze this codebase and produce a comprehensive development report.\n\n"
            f"## Repository Metadata\n{metadata_str}\n\n"
            f"## File Tree\n{file_tree}\n\n"
            "## Instructions\n"
            "The full codebase is available in the `codebase` variable "
            "(dict: filepath -> content).\n"
            "Use the REPL to explore it programmatically. "
            "Dispatch analysis tasks to sub-LLMs.\n"
            "Submit your final analysis with set_answer()."
        )

        rows.append({
            "question": question,
            "answer": json.dumps(entry.get("ground_truth_findings", [])),
            "info": json.dumps({
                "name": entry["name"],
                "codebase": entry["codebase"],
                "file_tree": file_tree,
                "metadata": metadata,
                "ground_truth_dispatches": entry.get("ground_truth_dispatches", 0),
                "ground_truth_findings": entry.get("ground_truth_findings", []),
                "llm_cache": entry.get("llm_cache", {}),
            }),
        })

    dataset = Dataset.from_list(rows)
    rubric = vf.Rubric(funcs=[delegation_reward])

    return DeepRepoOrchestrationEnv(
        dataset=dataset,
        rubric=rubric,
        max_turns=20,
        system_prompt=SYSTEM_PROMPT,
    )
