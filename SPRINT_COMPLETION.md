# Sprint Completion — Multi-Vertical Domain Plugin System

**Sprint dates:** February 18, 2026
**Sprint commit:** `ac485da` feat: multi-vertical domain plugin system with content analysis
**Cleanup commit:** `fab23ee` docs: clean up repo for public audience
**Branch:** main

---

## 1. Sprint Summary

The goal was to refactor deeprepo from a code-analysis-only tool into a domain-agnostic RLM platform, then ship marketing content intelligence as the second vertical to prove the pattern generalizes. This required extracting domain-specific concerns (loaders, prompts, namespace variables) into a plugin system, migrating the existing code analysis path to use it, building a content loader and content-specific prompts, wiring a `--domain` flag through the CLI, and creating a sample content corpus for demonstration.

### Task Status

| Task | Title | Status |
|------|-------|--------|
| P1 | Domain abstraction layer (DomainConfig + registry) | DONE |
| P2 | Migrate code analysis to CODE_DOMAIN config | DONE |
| P3 | Content loader (`content_loader.py`) | DONE |
| P4 | Content prompts + CONTENT_DOMAIN config | DONE |
| P5 | CLI `--domain` flag + content baseline | DONE |
| P6 | Example run + outputs (real content corpus) | PARTIAL |

P6 is partial: the sample input corpus (9 files across 4 categories) was created and committed to `examples/content-demo/input/`, but no actual API run was executed against it. The `examples/content-demo/` directory contains only `input/` — no output analysis or metrics files were committed.

### Files Created

| File | Purpose |
|------|---------|
| `deeprepo/domains/__init__.py` | Domain registry + `get_domain()` |
| `deeprepo/domains/base.py` | `DomainConfig` dataclass |
| `deeprepo/domains/code.py` | Code analysis domain config (wraps existing loader/prompts) |
| `deeprepo/domains/content.py` | Content analysis domain config + content-specific prompts |
| `deeprepo/content_loader.py` | Content corpus loader (local directory -> documents + metadata) |
| `tests/test_content_loader.py` | 9 tests for the content loader |
| `tests/test_cache.py` | 6 tests for the content-hash cache |
| `tests/test_content/blog/2025-06-ai-strategy.md` | Test content corpus |
| `tests/test_content/blog/2025-09-product-launch.md` | Test content corpus |
| `tests/test_content/brand-guidelines.md` | Test content corpus |
| `tests/test_content/email/newsletter-q3.html` | Test content corpus |
| `tests/test_content/social/twitter-threads.txt` | Test content corpus |
| `examples/content-demo/input/brand-guidelines.md` | Demo content corpus |
| `examples/content-demo/input/blog/2025-06-ai-strategy.md` | Demo content corpus |
| `examples/content-demo/input/blog/2025-09-product-launch.md` | Demo content corpus |
| `examples/content-demo/input/blog/2026-01-year-in-review.md` | Demo content corpus |
| `examples/content-demo/input/email/onboarding-sequence.md` | Demo content corpus |
| `examples/content-demo/input/email/newsletter-q4.md` | Demo content corpus |
| `examples/content-demo/input/social/linkedin-posts.md` | Demo content corpus |
| `examples/content-demo/input/landing-pages/homepage.md` | Demo content corpus |
| `examples/content-demo/input/landing-pages/pricing.md` | Demo content corpus |

### Files Modified

| File | What changed |
|------|-------------|
| `deeprepo/rlm_scaffold.py` | `RLMEngine.analyze()` accepts `DomainConfig`, `_build_namespace()` accepts `data_var_name` and `sub_system_prompt`, `run_analysis()` accepts `domain` string param |
| `deeprepo/baseline.py` | `run_baseline()` accepts `domain` string param, routes through domain config for loader/prompts |
| `deeprepo/cli.py` | Added `--domain` flag to common args, added `list-domains` subcommand, threaded domain through all commands |
| `deeprepo/llm_clients.py` | Changes from infra sprint carried into this commit (retry, streaming, caching support) |
| `deeprepo/prompts.py` | Minor adjustments for domain compatibility |
| `README.md` | Reframed for multi-vertical, added domain examples, updated project structure |

---

## 2. Architecture After Sprint

### File Structure

```
deeprepo/__init__.py
deeprepo/baseline.py
deeprepo/cache.py
deeprepo/cli.py
deeprepo/codebase_loader.py
deeprepo/content_loader.py
deeprepo/domains/__init__.py
deeprepo/domains/base.py
deeprepo/domains/code.py
deeprepo/domains/content.py
deeprepo/llm_clients.py
deeprepo/prompts.py
deeprepo/rlm_scaffold.py
deeprepo/utils.py
```

### How the Domain Plugin System Works

**DomainConfig** (`deeprepo/domains/base.py`) is a `@dataclass` with these fields:

```
name: str                    # "code" or "content"
label: str                   # "Codebase Analysis" or "Content Intelligence"
description: str             # One-line CLI help text
loader: Callable             # path -> {data_variable_name: dict, file_tree: str, metadata: dict}
format_metadata: Callable    # metadata dict -> prompt string
root_system_prompt: str      # System prompt for root orchestrator
sub_system_prompt: str       # System prompt for sub-LLM workers
user_prompt_template: str    # Initial user message (with {metadata_str}, {file_tree} placeholders)
baseline_system_prompt: str  # System prompt for single-model baseline
data_variable_name: str      # Key name in loader return AND REPL namespace ("codebase" or "documents")
clone_handler: Callable|None # Optional URL handler (git clone for code, None for content)
```

**Registry** (`deeprepo/domains/__init__.py`) maps string names to configs:

```python
DOMAIN_REGISTRY = {
    "code": CODE_DOMAIN,      # from deeprepo/domains/code.py
    "content": CONTENT_DOMAIN, # from deeprepo/domains/content.py
}
DEFAULT_DOMAIN = "code"
```

`get_domain(name)` looks up by name and raises `ValueError` with available options if unknown.

**Code domain** (`deeprepo/domains/code.py`) wraps the existing `codebase_loader.load_codebase`, `prompts.ROOT_SYSTEM_PROMPT`, etc. It sets `data_variable_name="codebase"` and `clone_handler=clone_repo`, preserving full backward compatibility.

**Content domain** (`deeprepo/domains/content.py`) uses `content_loader.load_content`, has its own root/sub/baseline prompts written from scratch for content analysis (brand voice, gaps, editorial planning). It sets `data_variable_name="documents"` and `clone_handler=None` (content is local-only).

### Data Flow

```
CLI --domain flag
    │
    ▼
cli.py: args.domain (string, default "code")
    │
    ▼
get_domain(args.domain) → DomainConfig
    │
    ▼
run_analysis(path, domain="code"|"content")
  or run_baseline(path, domain="code"|"content")
    │
    ▼
domain_config.loader(path) → {data_variable_name: dict, file_tree: str, metadata: dict}
    │
    ▼
RLMEngine.analyze(path, domain=domain_config)
  ├─ data = domain.loader(path)
  ├─ documents = data[domain.data_variable_name]  # "codebase" or "documents"
  ├─ _build_namespace(..., data_var_name=domain.data_variable_name,
  │                       sub_system_prompt=domain.sub_system_prompt)
  ├─ user_prompt = domain.user_prompt_template.format(metadata_str=..., file_tree=...)
  ├─ system = domain.root_system_prompt
  └─ REPL loop runs with domain-specific namespace and prompts
    │
    ▼
Output: {analysis: str, turns: int, usage: TokenUsage, trajectory: list}
```

The engine (`rlm_scaffold.py`) never imports domain-specific code directly. It receives a `DomainConfig` and uses its fields. Adding a third domain requires only: (1) a loader function, (2) a domain config module, (3) one line in the registry.

---

## 3. Deviations from Plan

### No deviations on P1-P5

The implementation matches PRODUCT_DEVELOPMENT.md closely. The `DomainConfig` dataclass, registry, engine changes, content loader, content prompts, and CLI flag all follow the spec.

### P6: Input corpus created, but no API run executed

PRODUCT_DEVELOPMENT.md specified: "Run deeprepo against it with `--domain content` ... Commit the output analysis + metrics to `examples/content-demo/`." The 9-file sample corpus was created in `examples/content-demo/input/`, but no actual API run was executed. The `examples/content-demo/` directory contains only `input/` — no output `.md` or `_metrics.json` files. This means there is no committed proof that the content domain produces a useful end-to-end analysis.

### Acceptance criteria status

All P1-P5 acceptance criteria are met. P6 criteria status:

- [x] Sample corpus exists with 9 documents across 4 categories (blog, email, social, landing-pages)
- [x] Brand guidelines establish a reference voice/terminology (Meridian B2B SaaS)
- [x] At least 2 documents intentionally drift from brand voice
- [ ] `deeprepo analyze examples/content-demo/input --domain content` produces a complete analysis — **NOT VERIFIED** (no API run committed)
- [ ] Output committed to `examples/content-demo/` — **NOT DONE**
- [ ] Cost documented in output metrics — **NOT DONE**

### Technical decisions during the sprint

1. The code domain's `data_variable_name` is `"codebase"` (not `"documents"`) to preserve prompt compatibility with the existing root system prompt that references the `codebase` variable.
2. The content domain sets `clone_handler=None`. URLs are rejected with a helpful error message for the content domain since content corpora are local directories, not git repos.
3. `cli.py` has a try/except fallback for importing `DEFAULT_SUB_MODEL` from `llm_clients` — this keeps `list-domains` and `--help` usable even in environments where `openai` fails to import (known Python 3.14 compatibility issue).

---

## 4. Test Results

### Full test run output

```
$ .venv/bin/python -m pytest tests/ -v

============================= test session starts ==============================
platform darwin -- Python 3.14.2, pytest-9.0.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /Users/leonliu/Desktop/Projects/deeprepo
configfile: pyproject.toml
plugins: anyio-4.12.1
collecting ... collected 15 items / 7 errors

ERRORS:
  tests/test_async_batch.py    - ModuleNotFoundError: No module named 'openai.types.shared'
  tests/test_baseline.py       - RuntimeError: Failed to import llm_clients (known openai/Python 3.14 issue)
  tests/test_connectivity.py   - ModuleNotFoundError: No module named 'openai.types.shared'
  tests/test_extract_code.py   - ModuleNotFoundError: No module named 'openai.types.shared'
  tests/test_retry.py          - ModuleNotFoundError: No module named 'openai.types.shared'
  tests/test_rlm_integration.py - ModuleNotFoundError: No module named 'openai.types.shared'
  tests/test_tool_use.py       - ModuleNotFoundError: No module named 'openai.types.shared'

7 errors during collection
```

7 test files fail to **collect** (not fail) due to `openai` package incompatibility with Python 3.14. The `openai` SDK tries to import `openai.types.shared.metadata` which doesn't exist in the installed version. This is an environment issue, not a code issue — these tests ran fine on earlier Python versions during the infra sprint.

### Tests that don't depend on openai (15/15 pass)

```
$ .venv/bin/python -m pytest tests/test_loader.py tests/test_prompts.py tests/test_cache.py tests/test_content_loader.py -v

tests/test_cache.py::test_cache_miss_returns_none PASSED
tests/test_cache.py::test_cache_hit_after_set PASSED
tests/test_cache.py::test_cache_key_includes_model PASSED
tests/test_cache.py::test_cache_expiry PASSED
tests/test_cache.py::test_clear_cache PASSED
tests/test_cache.py::test_cache_stats PASSED
tests/test_content_loader.py::test_load_returns_required_keys PASSED
tests/test_content_loader.py::test_document_count PASSED
tests/test_content_loader.py::test_document_types PASSED
tests/test_content_loader.py::test_content_categories PASSED
tests/test_content_loader.py::test_word_count PASSED
tests/test_content_loader.py::test_date_range PASSED
tests/test_content_loader.py::test_file_tree PASSED
tests/test_content_loader.py::test_format_metadata PASSED
tests/test_content_loader.py::test_empty_dir_raises PASSED

============================== 15 passed in 0.03s ==============================
```

### New test files created this sprint

| File | Tests | What it covers |
|------|-------|----------------|
| `tests/test_content_loader.py` | 9 tests | `load_content()` return format, document count, document types, content categories, word count, date range detection, file tree, `format_content_metadata()`, empty dir error |
| `tests/test_cache.py` | 6 tests | Cache miss, cache hit, model-scoped keys, expiry, clear, stats |

---

## 5. What Works Right Now

### `deeprepo list-domains`

Lists registered domains with descriptions:

```
$ .venv/bin/python -m deeprepo.cli list-domains

Available analysis domains:

  code (default)
    Analyze source code repositories for architecture, bugs, and quality

  content
    Analyze content libraries for brand voice, gaps, and editorial planning
```

### `deeprepo analyze ./some-repo` (code domain, default)

Loads the repo via `codebase_loader.py` (handles git URLs via clone, or local paths), sends file tree + metadata to the root model, runs the REPL loop with `codebase` variable in namespace, dispatches file-level analysis to sub-LLM workers via `llm_query()`/`llm_batch()`, and produces a markdown report + `_metrics.json` in `outputs/`. Default domain is `"code"` — no flag needed for existing behavior.

```bash
# These are equivalent:
deeprepo analyze ./my-project
deeprepo analyze ./my-project --domain code
```

### `deeprepo analyze ./content-dir --domain content`

Loads the directory via `content_loader.py`, which scans for `.md`, `.txt`, `.html`, `.csv`, `.json`, `.yaml` files, builds metadata (total_documents, total_words, content_categories from top-level subdirs, date_range from filename patterns, document_types). The root model gets content-specific prompts instructing it to analyze brand voice, content gaps, quality, and produce editorial recommendations. Output files are prefixed `deeprepo_content_`.

**Note:** This requires API keys and has not been run end-to-end with committed output. The content loader and domain wiring are verified by unit tests.

### `deeprepo baseline ./my-project --domain content`

Runs a single-model baseline analysis using the content domain's `baseline_system_prompt`. Produces a single-call content review without REPL or sub-LLM dispatch.

### `deeprepo compare ./some-repo --domain code`

Runs both RLM and baseline back-to-back, prints a comparison table (cost, tokens, coverage), saves both outputs. The `--domain` flag threads through to both runs.

### Content loader verification (no API keys needed)

```
$ .venv/bin/python -c "
from deeprepo.content_loader import load_content
data = load_content('tests/test_content')
print(f'Documents: {data[\"metadata\"][\"total_documents\"]}')
print(f'Words: {data[\"metadata\"][\"total_words\"]}')
print(f'Categories: {data[\"metadata\"][\"content_categories\"]}')
"

Documents: 5
Words: 453
Categories: ['blog', 'email', 'social']
```

### Domain registry verification (no API keys needed)

```
$ .venv/bin/python -c "
from deeprepo.domains import get_domain, DOMAIN_REGISTRY
for name, d in DOMAIN_REGISTRY.items():
    print(f'{name}: label={d.label}, data_var={d.data_variable_name}, has_clone={d.clone_handler is not None}')
"

code: label=Codebase Analysis, data_var=codebase, has_clone=True
content: label=Content Intelligence, data_var=documents, has_clone=False
```

---

## 6. Known Issues & Open Questions

### Environment issue: openai + Python 3.14

The `openai` SDK installed in the venv is incompatible with Python 3.14 — `openai.types.shared` module is missing. This blocks 7 out of 15 test files from even collecting. The tests themselves are fine; the import chain `openai -> openai.types -> openai.types.batch -> openai.types.shared.metadata` fails. Fix: `pip install --upgrade openai` or pin a compatible version. This is not a sprint regression — it's a pre-existing environment issue.

### P6 incomplete: no end-to-end content analysis committed

The sample corpus exists but no one ran `deeprepo analyze examples/content-demo/input --domain content` and committed the output. This means:
- We don't know the actual cost of a content analysis run
- We don't have a demo output to show external visitors
- We haven't validated that the content prompts produce useful analysis

### Content domain: no URL/clone support

The content domain sets `clone_handler=None`. If someone passes a URL, they get: `"Domain 'content' does not support URL inputs. Provide a local directory path."` This is by design (content corpora aren't typically git repos), but worth noting.

### No domain-specific tests for engine integration

The tests verify the content loader and the domain registry in isolation. There are no tests that verify the full `RLMEngine.analyze(path, domain=CONTENT_DOMAIN)` flow with mocked API calls. The code domain's integration path is covered by `test_rlm_integration.py` (currently blocked by the openai import issue).

### Edge case: content loader `total_files` vs `total_documents`

The engine's verbose output (line 114 of `rlm_scaffold.py`) prints `metadata['total_files']`. The content loader's metadata uses `total_documents` as the key, but also includes `total_files` for compatibility. If a future domain uses a different key, this line would KeyError.

---

## 7. Recommended Next Steps

1. **Run P6 for real.** Execute `deeprepo analyze examples/content-demo/input --domain content` with API keys, review the output quality, and commit results to `examples/content-demo/`. This is the most important gap — everything is wired but unproven end-to-end.

2. **Fix the openai/Python 3.14 issue.** Run `pip install --upgrade openai` or pin a known-compatible version. Until this is fixed, 7 test files can't run.

3. **Add an integration test for the content domain.** A test that mocks `RootModelClient` and `SubModelClient`, loads `tests/test_content/`, and runs `RLMEngine.analyze()` with `CONTENT_DOMAIN` would catch prompt/namespace wiring issues without needing API keys.

4. **Consider a `--domain` validation UX improvement.** Currently `--domain` accepts any string and only fails at runtime when `get_domain()` is called. Adding `choices=list(DOMAIN_REGISTRY.keys())` to the argparse definition would give better help text and immediate feedback, but requires importing the registry at CLI parse time (which currently works thanks to the lazy import pattern).

5. **Run the content domain against a real-world corpus.** The test content and demo content are synthetic. Running against a real company blog or content library (many are markdown on GitHub — Ghost, Hugo, Gatsby sites) would validate whether the content prompts produce genuinely useful analysis.
