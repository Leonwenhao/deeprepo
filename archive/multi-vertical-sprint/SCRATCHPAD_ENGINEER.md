# Engineer Scratchpad — deeprepo Multi-Vertical Sprint

## Current Status
- **Last Updated:** 2026-02-19
- **Current Task:** P6 — Example Run + Outputs (Real Content Corpus)
- **Status:** COMPLETED

## Latest Handoff
### P6 — Example Run + Outputs (Real Content Corpus)

#### What I Implemented
- Created new sample corpus under `examples/content-demo/input/` with 9 realistic fictional Meridian documents across 4 categories:
  - `examples/content-demo/input/brand-guidelines.md` (343 words)
  - `examples/content-demo/input/blog/2025-06-ai-strategy.md` (479 words, front matter date `2025-06-15`)
  - `examples/content-demo/input/blog/2025-09-product-launch.md` (428 words, front matter date `2025-09-03`)
  - `examples/content-demo/input/blog/2026-01-year-in-review.md` (413 words, front matter date `2026-01-10`)
  - `examples/content-demo/input/email/onboarding-sequence.md` (393 words)
  - `examples/content-demo/input/email/newsletter-q4.md` (292 words)
  - `examples/content-demo/input/social/linkedin-posts.md` (201 words)
  - `examples/content-demo/input/landing-pages/homepage.md` (247 words)
  - `examples/content-demo/input/landing-pages/pricing.md` (254 words)
- Ensured on-brand corpus coverage (professional/approachable voice, "we/you", "operations intelligence", "workflow automation", "team") in:
  - `brand-guidelines.md`
  - `blog/2025-06-ai-strategy.md`
  - `blog/2025-09-product-launch.md`
  - `email/onboarding-sequence.md`
  - `email/newsletter-q4.md`
  - `landing-pages/homepage.md`
- Added intentional drift in 3 specified documents:
  - `blog/2026-01-year-in-review.md`: uses "customers", "ops analytics", and corporate jargon ("synergize", "leverage", "drive value")
  - `social/linkedin-posts.md`: overly casual/slang tone and emoji-heavy style
  - `landing-pages/pricing.md`: references Meridian in third person ("Meridian offers...", "Meridian's platform")
- No code files were modified.

#### Deviation from Spec
- Could not produce live analysis output artifacts under `examples/content-demo/` because the environment's known Python 3.14 + `openai` 2.21.0 issue prevents `llm_clients` import at runtime.
- I still attempted both requested commands; details are in Test Results below.

#### Issues / Questions Encountered
- `analyze --domain content` failed with:
  - `ModuleNotFoundError: No module named 'openai.types.shared'`
- `baseline --domain content` failed with:
  - `Error: Failed to import llm_clients (known openai/Python 3.14 issue in this environment).`

#### Test Results (verbatim output)

Command:
`uv run python -c "from deeprepo.content_loader import load_content; d = load_content('examples/content-demo/input'); print(f'Docs: {d[\"metadata\"][\"total_documents\"]}'); assert d['metadata']['total_documents'] == 9"`
```text
Docs: 9
```

Command:
`uv run python - <<'PY' ... loader metadata verification ... PY`
```text
Documents: 9
Words: 3050
Categories: ['blog', 'email', 'landing-pages', 'social']
Types: {'.md': 9}
Date range: {'earliest': '2025-06', 'latest': '2026-01'}
PASS
```

Command:
`uv run python - <<'PY' ... brand guideline presence verification ... PY`
```text
Brand guidelines found: PASS
```

Command:
`uv run python -m deeprepo.cli analyze examples/content-demo/input --domain content --max-turns 5 -o examples/content-demo`
```text
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/Users/leonliu/Desktop/Projects/deeprepo/deeprepo/cli.py", line 401, in <module>
    main()
    ~~~~^^
  File "/Users/leonliu/Desktop/Projects/deeprepo/deeprepo/cli.py", line 382, in main
    args.func(args)
    ~~~~~~~~~^^^^^^
  File "/Users/leonliu/Desktop/Projects/deeprepo/deeprepo/cli.py", line 39, in cmd_analyze
    from .rlm_scaffold import run_analysis
  File "/Users/leonliu/Desktop/Projects/deeprepo/deeprepo/rlm_scaffold.py", line 23, in <module>
    from .llm_clients import (
    ...<5 lines>...
    )
  File "/Users/leonliu/Desktop/Projects/deeprepo/deeprepo/llm_clients.py", line 15, in <module>
    import openai
  File "/Users/leonliu/Desktop/Projects/deeprepo/.venv/lib/python3.14/site-packages/openai/__init__.py", line 9, in <module>
    from . import types
  File "/Users/leonliu/Desktop/Projects/deeprepo/.venv/lib/python3.14/site-packages/openai/types/__init__.py", line 5, in <module>
    from .batch import Batch as Batch
  File "/Users/leonliu/Desktop/Projects/deeprepo/.venv/lib/python3.14/site-packages/openai/types/batch.py", line 9, in <module>
    from .shared.metadata import Metadata
ModuleNotFoundError: No module named 'openai.types.shared'
```

Command:
`uv run python -m deeprepo.cli baseline examples/content-demo/input --domain content -o examples/content-demo`
```text
Error: Failed to import llm_clients (known openai/Python 3.14 issue in this environment).
Loaded 9 files, 20,357 chars
```

Command:
`uv run python -m pytest tests/test_content_loader.py tests/test_cache.py -v`
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 15 items

tests/test_content_loader.py::test_load_returns_required_keys PASSED     [  6%]
tests/test_content_loader.py::test_document_count PASSED                 [ 13%]
tests/test_content_loader.py::test_document_types PASSED                 [ 20%]
tests/test_content_loader.py::test_content_categories PASSED             [ 26%]
tests/test_content_loader.py::test_word_count PASSED                     [ 33%]
tests/test_content_loader.py::test_date_range PASSED                     [ 40%]
tests/test_content_loader.py::test_file_tree PASSED                      [ 46%]
tests/test_content_loader.py::test_format_metadata PASSED                [ 53%]
tests/test_content_loader.py::test_empty_dir_raises PASSED               [ 60%]
tests/test_cache.py::test_cache_miss_returns_none PASSED                 [ 66%]
tests/test_cache.py::test_cache_hit_after_set PASSED                     [ 73%]
tests/test_cache.py::test_cache_key_includes_model PASSED                [ 80%]
tests/test_cache.py::test_cache_expiry PASSED                            [ 86%]
tests/test_cache.py::test_clear_cache PASSED                             [ 93%]
tests/test_cache.py::test_cache_stats PASSED                             [100%]

============================== 15 passed in 0.03s ==============================
```

### P5 — CLI --domain Flag + Content Baseline

#### What I Implemented
- Modified `deeprepo/cli.py` to add domain-aware CLI behavior across all relevant commands.
- Added `--domain` to the shared `common` args:
  - default: `"code"`
  - no `choices=` used (validation delegated to domain registry via `get_domain()`).
- Updated shared positional path help text to domain-generic:
  - from `"Path to codebase or git URL"`
  - to `"Path to data directory or git URL"`.
- Threaded `domain=args.domain` into:
  - `cmd_analyze()` -> `run_analysis(...)`
  - `cmd_baseline()` -> `run_baseline(...)`
  - `cmd_compare()` -> both `run_analysis(...)` and `run_baseline(...)`
- Refactored `cmd_compare()` clone behavior to be domain-aware:
  - removed direct `codebase_loader` dependency
  - now uses `domain_config = get_domain(args.domain)`
  - uses `domain_config.clone_handler` for URL inputs
  - raises clear error for URL inputs on domains without clone support.
- Added domain-aware output filename prefixes for non-code domains:
  - analyze: `deeprepo_<domain>_...` (falls back to `deeprepo_...` for code)
  - baseline: `baseline_<domain>_...` (falls back to `baseline_...` for code)
  - compare: same prefix logic for both analysis and metrics outputs.
- Added `"domain": args.domain` into metrics payloads in:
  - `cmd_analyze`
  - `cmd_baseline`
  - `cmd_compare` (both RLM and baseline metrics dicts)
- Added new `list-domains` subcommand:
  - `cmd_list_domains()` prints all registered domains, descriptions, and default marker.
  - registered parser in `main()`.
- Updated top-level parser description:
  - from codebase-only wording to domain-generic wording per spec.

#### Deviation from Spec
- Added a defensive `llm_clients` import fallback in `cli.py`:
  - `DEFAULT_SUB_MODEL` import is wrapped in `try/except` with fallback string.
  - This keeps `deeprepo.cli` importable for `--help`, `list-domains`, and early domain validation in the known Python 3.14 + openai 2.21.0 broken environment.
  - No behavior change in healthy environments where `llm_clients` imports successfully.
- Added early `get_domain(args.domain)` validation in command handlers before deeper runtime imports to ensure invalid domain errors come from registry consistently, even in this environment.

#### Issues / Questions Encountered
- Confirmed known environment issue: importing modules that eagerly import `llm_clients` can fail (`ModuleNotFoundError: openai.types.shared`) on Python 3.14 with openai 2.21.0.
- Also observed intermittent uv cache permission issue when running many uv commands in parallel; avoided with `UV_CACHE_DIR=/tmp/uv-cache` for verification commands.

#### Test Results (verbatim output)

Command:
`UV_CACHE_DIR=/tmp/uv-cache uv run python -m deeprepo.cli analyze --help 2>&1 | grep domain`
```text
                                       [--domain DOMAIN]
  --domain DOMAIN       Analysis domain (default: code). Use 'list-domains' to
```

Command:
`UV_CACHE_DIR=/tmp/uv-cache uv run python -m deeprepo.cli list-domains`
```text
Available analysis domains:

  code (default)
    Analyze source code repositories for architecture, bugs, and quality

  content
    Analyze content libraries for brand voice, gaps, and editorial planning
```

Command:
`UV_CACHE_DIR=/tmp/uv-cache uv run python -m deeprepo.cli analyze ./foo --domain bogus 2>&1 || true`
```text
Error: Unknown domain 'bogus'. Available: code, content
```

Command:
`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import inspect ... cmd_compare ..."`
```text
cmd_compare clean import: PASS
```

Command:
`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import inspect ... cmd_analyze/cmd_baseline/cmd_compare ..."`
```text
cmd_analyze: domain threaded - PASS
cmd_baseline: domain threaded - PASS
cmd_compare: domain threaded - PASS
```

Command:
`UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from deeprepo.domains import DOMAIN_REGISTRY ..."`
```text
Registry: PASS
```

Command:
`uv run python -m pytest tests/test_content_loader.py tests/test_cache.py -v`
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 15 items

tests/test_content_loader.py::test_load_returns_required_keys PASSED     [  6%]
tests/test_content_loader.py::test_document_count PASSED                 [ 13%]
tests/test_content_loader.py::test_document_types PASSED                 [ 20%]
tests/test_content_loader.py::test_content_categories PASSED             [ 26%]
tests/test_content_loader.py::test_word_count PASSED                     [ 33%]
tests/test_content_loader.py::test_date_range PASSED                     [ 40%]
tests/test_content_loader.py::test_file_tree PASSED                      [ 46%]
tests/test_content_loader.py::test_format_metadata PASSED                [ 53%]
tests/test_content_loader.py::test_empty_dir_raises PASSED               [ 60%]
tests/test_cache.py::test_cache_miss_returns_none PASSED                 [ 66%]
tests/test_cache.py::test_cache_hit_after_set PASSED                     [ 73%]
tests/test_cache.py::test_cache_key_includes_model PASSED                [ 80%]
tests/test_cache.py::test_cache_expiry PASSED                            [ 86%]
tests/test_cache.py::test_clear_cache PASSED                             [ 93%]
tests/test_cache.py::test_cache_stats PASSED                             [100%]

============================== 15 passed in 0.02s ==============================
```

### P4 — Content Prompts + CONTENT_DOMAIN Config

#### What I Implemented
- Added `deeprepo/domains/content.py` with four fresh content-specific prompt constants:
  - `CONTENT_ROOT_SYSTEM_PROMPT`
  - `CONTENT_SUB_SYSTEM_PROMPT`
  - `CONTENT_USER_PROMPT_TEMPLATE`
  - `CONTENT_BASELINE_SYSTEM_PROMPT`
- Root prompt is structurally aligned with REPL mechanics from code domain but rewritten for content analysis:
  - uses `documents`/`file_tree`/`metadata`
  - defines required content analysis sections: inventory, brand voice audit, gap analysis, quality, editorial recommendations
  - includes concrete workflow and code examples for:
    - structure exploration
    - brand-guidelines-first review
    - category grouping + `llm_batch()` dispatch
    - terminology/regex pattern analysis
    - `set_answer()` finalization with `lines.append()` pattern
  - includes explicit warning to avoid triple-quoted final strings
- Added `CONTENT_DOMAIN = DomainConfig(...)` in `deeprepo/domains/content.py` wired exactly per spec:
  - `loader=load_content`
  - `format_metadata=format_content_metadata`
  - `data_variable_name="documents"`
  - `clone_handler=None`
- Updated `deeprepo/domains/__init__.py`:
  - imported `CONTENT_DOMAIN`
  - registered `"content"` in `DOMAIN_REGISTRY`
  - left `DEFAULT_DOMAIN = "code"` unchanged
- No other files modified except required ones plus this scratchpad update.

#### Deviation from Spec
- None.

#### Issues / Questions Encountered
- No implementation issues.
- Known environment issue (`openai` 2.21.0 with Python 3.14) still applies for tests importing `llm_clients`; verification stayed on CTO-directed checks and test targets.

#### Test Results (verbatim output)

Command:
`uv run python -c "from deeprepo.domains import get_domain, DOMAIN_REGISTRY, DEFAULT_DOMAIN ..."`
```text
Registry keys: ['code', 'content']
Default: code
Domain: content
Label: Content Intelligence
Data var: documents
Has clone_handler: False
PASS
```

Command:
`uv run python -c "from deeprepo.domains import get_domain ..."`
```text
Code domain: PASS
```

Command:
`uv run python -c "from deeprepo.domains.content import (...) ..."`
```text
Root prompt: 6242 chars - OK
Sub prompt: 637 chars - OK
User template: 428 chars - OK
Baseline prompt: 696 chars - OK
All prompt checks PASS
```

Command:
`uv run python -m pytest tests/test_content_loader.py tests/test_cache.py -v`
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 15 items

tests/test_content_loader.py::test_load_returns_required_keys PASSED     [  6%]
tests/test_content_loader.py::test_document_count PASSED                 [ 13%]
tests/test_content_loader.py::test_document_types PASSED                 [ 20%]
tests/test_content_loader.py::test_content_categories PASSED             [ 26%]
tests/test_content_loader.py::test_word_count PASSED                     [ 33%]
tests/test_content_loader.py::test_date_range PASSED                     [ 40%]
tests/test_content_loader.py::test_file_tree PASSED                      [ 46%]
tests/test_content_loader.py::test_format_metadata PASSED                [ 53%]
tests/test_content_loader.py::test_empty_dir_raises PASSED               [ 60%]
tests/test_cache.py::test_cache_miss_returns_none PASSED                 [ 66%]
tests/test_cache.py::test_cache_hit_after_set PASSED                     [ 73%]
tests/test_cache.py::test_cache_key_includes_model PASSED                [ 80%]
tests/test_cache.py::test_cache_expiry PASSED                            [ 86%]
tests/test_cache.py::test_clear_cache PASSED                             [ 93%]
tests/test_cache.py::test_cache_stats PASSED                             [100%]

============================== 15 passed in 0.03s ==============================
```

### P3 — Content Loader (content_loader.py)

#### What I Implemented
- Added `deeprepo/content_loader.py` with:
  - `load_content(path: str) -> dict`
  - `format_content_metadata(metadata: dict) -> str`
- `load_content()` mirrors `codebase_loader` structure and returns:
  - `documents` (dict of relative path -> content)
  - `file_tree` (visual tree)
  - `metadata` with:
    - `corpus_name`
    - `total_files`
    - `total_documents`
    - `total_chars`
    - `total_words`
    - `document_types`
    - `largest_documents`
    - `content_categories`
    - `date_range`
- Implemented content-specific behavior per spec:
  - supported extensions: `.md`, `.txt`, `.html`, `.htm`, `.csv`, `.json`, `.yaml`, `.yml`
  - skipped directories list aligned with spec
  - max file size 500KB with placeholder message for oversized files
  - empty corpus raises `ValueError` with helpful message
  - category detection from top-level subdirectories; falls back to `["uncategorized"]`
  - best-effort date detection from filename (`YYYY-MM-DD` / `YYYY-MM`) and markdown front matter (`date:` in first 20 lines), normalized to `YYYY-MM`
  - word counting via `len(content.split())`
- Added fixture corpus under `tests/test_content/`:
  - `blog/2025-06-ai-strategy.md` (front matter date)
  - `blog/2025-09-product-launch.md` (front matter date)
  - `email/newsletter-q3.html`
  - `social/twitter-threads.txt`
  - `brand-guidelines.md`
- Added `tests/test_content_loader.py` with 9 pytest tests matching CTO spec.

#### Deviation from Spec
- None.

#### Issues / Questions Encountered
- No implementation issues in P3.
- Known environment issue still applies (`openai` 2.21.0 on Python 3.14), so verification stayed on loader/prompts/cache/content-loader tests as directed.

#### Test Results (verbatim output)

Command:
`uv run python -m pytest tests/test_content_loader.py -v`
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 9 items

tests/test_content_loader.py::test_load_returns_required_keys PASSED     [ 11%]
tests/test_content_loader.py::test_document_count PASSED                 [ 22%]
tests/test_content_loader.py::test_document_types PASSED                 [ 33%]
tests/test_content_loader.py::test_content_categories PASSED             [ 44%]
tests/test_content_loader.py::test_word_count PASSED                     [ 55%]
tests/test_content_loader.py::test_date_range PASSED                     [ 66%]
tests/test_content_loader.py::test_file_tree PASSED                      [ 77%]
tests/test_content_loader.py::test_format_metadata PASSED                [ 88%]
tests/test_content_loader.py::test_empty_dir_raises PASSED               [100%]

============================== 9 passed in 0.02s ===============================
```

Command:
`uv run python -m pytest tests/test_loader.py tests/test_prompts.py tests/test_cache.py -v`
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 6 items

tests/test_cache.py::test_cache_miss_returns_none PASSED                 [ 16%]
tests/test_cache.py::test_cache_hit_after_set PASSED                     [ 33%]
tests/test_cache.py::test_cache_key_includes_model PASSED                [ 50%]
tests/test_cache.py::test_cache_expiry PASSED                            [ 66%]
tests/test_cache.py::test_clear_cache PASSED                             [ 83%]
tests/test_cache.py::test_cache_stats PASSED                             [100%]

============================== 6 passed in 0.03s ===============================
```

Command:
`uv run python - <<'PY' ... load_content('tests/test_content') ... PY`
```text
Documents: 5
Words: 453
Categories: ['blog', 'email', 'social']
Date range: {'earliest': '2025-06', 'latest': '2025-09'}
Types: {'.md': 3, '.txt': 1, '.html': 1}

Corpus: test_content
Total documents: 5
Total characters: 3,189
Total words: 453

Document types:
  .md: 3 files
  .txt: 1 files
  .html: 1 files

Content categories:
  blog
  email
  social

Date range: 2025-06 to 2025-09

Largest documents:
  blog/2025-06-ai-strategy.md: 694 chars
  blog/2025-09-product-launch.md: 674 chars
  email/newsletter-q3.html: 658 chars
  social/twitter-threads.txt: 652 chars
  brand-guidelines.md: 511 chars

PASS
```

### P2 — Migrate Code Analysis to CODE_DOMAIN Config

#### What I Implemented
- Created `deeprepo/domains/code.py` and moved `CODE_DOMAIN` into it, preserving all existing field values and behavior:
  - loader/formatter from `codebase_loader`
  - prompts from `prompts.py`
  - `BASELINE_SYSTEM_PROMPT` from `baseline.py`
  - `data_variable_name="codebase"` and `clone_handler=clone_repo`
- Refactored `deeprepo/domains/__init__.py`:
  - removed inline `CODE_DOMAIN` definition
  - now imports `CODE_DOMAIN` from `.code`
  - kept `DomainConfig`, `DOMAIN_REGISTRY`, `DEFAULT_DOMAIN`, and `get_domain()` unchanged in behavior
- Removed dead imports from `deeprepo/rlm_scaffold.py`:
  - removed `from .codebase_loader import ...`
  - removed `from .prompts import ...`
  - kept `TYPE_CHECKING` `DomainConfig` import and all runtime behavior unchanged
- Removed dead import from `deeprepo/baseline.py`:
  - removed `from .codebase_loader import load_codebase, format_metadata_for_prompt`
  - kept `BASELINE_SYSTEM_PROMPT` at module level
  - kept the defensive `llm_clients` import guard in place

#### Deviation from Spec
- None.

#### Issues / Questions Encountered
- No new issues during P2.
- Known environment issue remains: `openai` 2.21.0 on Python 3.14 breaks tests importing `llm_clients`; verification limited to loader/prompts/cache tests per instruction.

#### Test Results (verbatim output)

Command:
`uv run python - <<'PY' ... get_domain('code') ... PY`
```text
Domain: code
Label: Codebase Analysis
Data var: codebase
Prompt preview: You are operating as the root orchestrator in a Recursive Language Model (RLM) environment for codeb...
Registry keys: ['code']
PASS
```

Command:
`uv run python - <<'PY' ... inspect.getsource(deeprepo.domains) ... PY`
```text
CLEAN: __init__.py has no direct loader/prompt/baseline imports
PASS
```

Command:
`uv run python - <<'PY' ... from deeprepo.domains.code import CODE_DOMAIN ... PY`
```text
CODE_DOMAIN.name: code
CODE_DOMAIN.data_variable_name: codebase
PASS
```

Command:
`uv run python -m pytest tests/test_loader.py tests/test_prompts.py tests/test_cache.py -v`
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 6 items

tests/test_cache.py::test_cache_miss_returns_none PASSED                 [ 16%]
tests/test_cache.py::test_cache_hit_after_set PASSED                     [ 33%]
tests/test_cache.py::test_cache_key_includes_model PASSED                [ 50%]
tests/test_cache.py::test_cache_expiry PASSED                            [ 66%]
tests/test_cache.py::test_clear_cache PASSED                             [ 83%]
tests/test_cache.py::test_cache_stats PASSED                             [100%]

============================== 6 passed in 0.02s ===============================
```

### P1 — Domain Abstraction Layer (DomainConfig + Registry)

#### What I Implemented
- Added `deeprepo/domains/base.py` with `DomainConfig` dataclass and all spec fields:
  - identity (`name`, `label`, `description`)
  - loader (`loader`, `format_metadata`)
  - prompts (`root_system_prompt`, `sub_system_prompt`, `user_prompt_template`, `baseline_system_prompt`)
  - namespace key (`data_variable_name`, default `"documents"`)
  - URL/file handler (`clone_handler`)
- Added `deeprepo/domains/__init__.py` with:
  - placeholder `CODE_DOMAIN` wiring existing code-domain loader/prompts/baseline prompt
  - `DOMAIN_REGISTRY = {"code": CODE_DOMAIN}`
  - `DEFAULT_DOMAIN = "code"`
  - `get_domain(name)` with helpful `ValueError` listing available domains
- Updated `deeprepo/rlm_scaffold.py`:
  - `RLMEngine.analyze()` now accepts `(path: str, domain: DomainConfig)` and uses:
    - `domain.loader`
    - `domain.data_variable_name`
    - `domain.format_metadata`
    - `domain.user_prompt_template`
    - `domain.root_system_prompt`
  - `_build_namespace()` now accepts `data_var_name` and `sub_system_prompt`, uses:
    - dynamic namespace key (`data_var_name: documents`)
    - sub-LLM calls using domain-specific `sub_system_prompt`
  - `run_analysis()` now accepts `domain="code"`, resolves via `get_domain()`, uses domain clone handler for URL inputs, and passes the resolved `domain_config` into `engine.analyze(...)`
  - Kept existing top-level imports from loader/prompts in place per CTO note (P2 cleanup)
- Updated `deeprepo/baseline.py`:
  - `run_baseline()` now accepts `domain="code"`
  - resolves `domain_config = get_domain(domain)` lazily inside function
  - URL clone handling now uses `domain_config.clone_handler` with unsupported-domain error
  - loader/prompt logic now uses:
    - `domain_config.loader`
    - `domain_config.data_variable_name`
    - `domain_config.format_metadata`
    - `domain_config.baseline_system_prompt`
  - kept `BASELINE_SYSTEM_PROMPT` module constant at top-level

#### Deviation from Spec
- Added a small defensive import guard in `deeprepo/baseline.py` around `llm_clients` import so `deeprepo.domains` can import `BASELINE_SYSTEM_PROMPT` under the known Python 3.14 + `openai` 2.21.0 breakage. Without this, `from deeprepo.domains import get_domain` crashes immediately via import chain (`domains -> baseline -> llm_clients -> openai`), blocking the CTO-mandated domain registry checks.
- Behavior impact:
  - No change in healthy environments.
  - In broken envs, importing `baseline` for constants works; calling `run_baseline()` still raises a clear runtime error tied to the known dependency issue.

#### Issues / Questions Encountered
- Confirmed known environment issue still exists: `openai` 2.21.0 import fails on Python 3.14 (`ModuleNotFoundError: openai.types.shared`).
- This is not fixed in this task (per CTO note), but import guard ensures P1 registry verification can run.

#### Test Results (verbatim output)

Command:
`uv run python -c "from deeprepo.domains import get_domain, DOMAIN_REGISTRY, DEFAULT_DOMAIN; d = get_domain('code'); print(f'Domain: {d.name}'); print(f'Label: {d.label}'); print(f'Data var: {d.data_variable_name}'); print(f'Description: {d.description}'); print(f'Has loader: {callable(d.loader)}'); print(f'Has clone_handler: {d.clone_handler is not None}'); print(f'Default domain: {DEFAULT_DOMAIN}'); print(f'Registry keys: {list(DOMAIN_REGISTRY.keys())}'); print('PASS')"`
```text
Domain: code
Label: Codebase Analysis
Data var: codebase
Description: Analyze source code repositories for architecture, bugs, and quality
Has loader: True
Has clone_handler: True
Default domain: code
Registry keys: ['code']
PASS
```

Command:
`uv run python - <<'PY' ... get_domain('nonexistent') ... PY`
```text
Error message: Unknown domain 'nonexistent'. Available: code
PASS
```

Command:
`uv run python -m pytest tests/test_loader.py tests/test_prompts.py tests/test_cache.py -v`
```text
============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0 -- /Users/leonliu/Desktop/Projects/deeprepo/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 6 items

tests/test_cache.py::test_cache_miss_returns_none PASSED                 [ 16%]
tests/test_cache.py::test_cache_hit_after_set PASSED                     [ 33%]
tests/test_cache.py::test_cache_key_includes_model PASSED                [ 50%]
tests/test_cache.py::test_cache_expiry PASSED                            [ 66%]
tests/test_cache.py::test_clear_cache PASSED                             [ 83%]
tests/test_cache.py::test_cache_stats PASSED                             [100%]

============================== 6 passed in 0.03s ===============================
```

## Running Context
- Package is `deeprepo/` (renamed from `src/` during infrastructure sprint)
- `deeprepo/utils.py` — retry utilities
- `deeprepo/cache.py` — content-hash caching for sub-LLM results
- All new CLI flags follow the argparse pattern in `deeprepo/cli.py`
- Tests live in `tests/` — run with `uv run python -m pytest tests/ -v`
- Domain configs go in `deeprepo/domains/` (new package created in P1)
- **Environment note:** `openai` 2.21.0 is broken on Python 3.14 — tests importing `llm_clients` fail at collection. Use `test_loader.py`, `test_prompts.py`, `test_cache.py` for verification.
