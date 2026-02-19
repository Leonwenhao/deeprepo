# deeprepo — Product Development Plan: Multi-Vertical RLM Platform

**Author:** Leon (with Claude)
**Date:** February 18, 2026
**Sprint Goal:** Refactor deeprepo from a code analysis tool into a domain-agnostic RLM agent platform, then ship marketing content intelligence as the second vertical proof point.
**Agents:** Claude Code (CTO) + Codex (Senior Engineer)

---

## Executive Summary

deeprepo's infrastructure sprint is complete. The RLM engine is hardened with retry logic, streaming, tool_use structured output, caching, and configurable models. The next step is not another coding feature — it's proving that the RLM pattern generalizes beyond code.

The architecture is already 90% domain-agnostic. Domain coupling exists in exactly three places: the document loader (`codebase_loader.py`), the prompts (`prompts.py`), and variable naming in the scaffold. This plan describes a plugin architecture refactoring followed by a marketing content intelligence vertical that demonstrates "same engine, any document corpus."

The deliverable: `deeprepo analyze --domain content ./marketing-library` producing a brand consistency audit, content gap analysis, and editorial calendar recommendations — using the same REPL loop, sub-LLM dispatch, caching, and streaming infrastructure that powers code analysis today.

---

## Part 1: Current Architecture Assessment

### What's Domain-Agnostic (no changes needed)

| Component | File | Why it's generic |
|-----------|------|-----------------|
| RLM REPL loop | `rlm_scaffold.py` | Operates on a `dict` of path→content, executes Python, feeds output back. Doesn't know what the content is. |
| Token tracking | `llm_clients.py` | Tracks tokens/cost for any API call regardless of domain. |
| Retry logic | `utils.py` | Retries API calls — domain-irrelevant. |
| Cache | `cache.py` | Content-hash caching — works on any prompt string. |
| Tool_use extraction | `rlm_scaffold.py` | Parses `execute_python` tool calls — domain-irrelevant. |
| Streaming | `llm_clients.py` | Streams root model responses — domain-irrelevant. |
| CLI framework | `cli.py` | argparse structure, output saving, metrics JSON — extensible. |

### What's Domain-Coupled (needs refactoring)

| Component | File | Coupling |
|-----------|------|---------|
| Document loader | `codebase_loader.py` | Hardcoded to code extensions (`.py`, `.js`, etc.), code skip dirs (`node_modules`), code entry point detection (`main.py`, `__main__`). |
| Root system prompt | `prompts.py` | Says "codebase analysis," instructs for bugs/architecture/dev-plan. |
| Sub-LLM system prompt | `prompts.py` | Says "code analysis expert." |
| Baseline prompt | `baseline.py` | Says "software architect" performing "codebase review." |
| User prompt template | `prompts.py` | References "codebase" variable, "source code files." |
| Namespace variable name | `rlm_scaffold.py` | `_build_namespace()` puts data under key `"codebase"`. Hardcodes `SUB_SYSTEM_PROMPT`. |
| `run_analysis()` | `rlm_scaffold.py` | Calls `load_codebase()` directly. |
| `run_baseline()` | `baseline.py` | Calls `load_codebase()` directly. |

### Key Observation

The REPL loop (`analyze()` lines 129–247) is a 118-line generic execution engine. The domain-specific parts are the 4 lines that call the loader and format the prompt (lines 105–122). The refactoring surface area is small.

---

## Part 2: Architecture — Plugin System

### Design Principle

Each vertical ("domain") is defined by a **DomainConfig** — a simple data object that provides:
1. A loader function (directory → `{documents, file_tree, metadata}`)
2. A set of prompts (root system, sub system, user template, baseline system)
3. A namespace variable name (what the root model calls the data)
4. Display metadata (domain label, file type description)

The engine doesn't change. The CLI gains a `--domain` flag that selects a config. New verticals are added by creating a new config module — no engine modifications required.

### DomainConfig Interface

```python
# deeprepo/domains/base.py

from dataclasses import dataclass, field
from typing import Callable

@dataclass
class DomainConfig:
    """Configuration for a deeprepo analysis domain."""
    
    # Identity
    name: str                           # e.g., "code", "content", "film"
    label: str                          # e.g., "Codebase Analysis", "Content Intelligence"
    description: str                    # One-line description for CLI help
    
    # Loader
    loader: Callable[[str], dict]       # path → {documents, file_tree, metadata}
    format_metadata: Callable[[dict], str]  # metadata → prompt string
    
    # Prompts
    root_system_prompt: str             # System prompt for root orchestrator
    sub_system_prompt: str              # System prompt for sub-LLM workers
    user_prompt_template: str           # Initial user message (with {metadata_str}, {file_tree})
    baseline_system_prompt: str         # System prompt for single-model baseline
    
    # Namespace
    data_variable_name: str = "documents"  # What the root model calls the data dict
    
    # File handling
    clone_handler: Callable[[str], str] | None = None  # Optional: handle URLs (git clone, etc.)
```

### Domain Registry

```python
# deeprepo/domains/__init__.py

from .code import CODE_DOMAIN
from .content import CONTENT_DOMAIN

DOMAIN_REGISTRY: dict[str, DomainConfig] = {
    "code": CODE_DOMAIN,
    "content": CONTENT_DOMAIN,
}

DEFAULT_DOMAIN = "code"

def get_domain(name: str) -> DomainConfig:
    if name not in DOMAIN_REGISTRY:
        available = ", ".join(DOMAIN_REGISTRY.keys())
        raise ValueError(f"Unknown domain '{name}'. Available: {available}")
    return DOMAIN_REGISTRY[name]
```

### Engine Changes (Minimal)

`RLMEngine.analyze()` changes from:

```python
def analyze(self, codebase_path: str) -> dict:
    data = load_codebase(codebase_path)
    codebase = data["codebase"]
    ...
    repl_namespace = self._build_namespace(codebase, file_tree, metadata, answer)
```

To:

```python
def analyze(self, path: str, domain: DomainConfig) -> dict:
    data = domain.loader(path)
    documents = data["documents"]
    ...
    repl_namespace = self._build_namespace(
        documents, file_tree, metadata, answer,
        data_var_name=domain.data_variable_name,
        sub_system_prompt=domain.sub_system_prompt,
    )
```

The `_build_namespace()` method adds one parameter — the variable name to expose the data under. For code analysis, the root model still sees `codebase["src/main.py"]`. For content analysis, it sees `documents["blog/ai-strategy.md"]`. The engine doesn't care.

---

## Part 3: Issue Specifications

### Issue Priority Order

| Order | Issue | Title | Complexity | Est. Time |
|:-----:|:-----:|-------|:----------:|:---------:|
| 1 | P1 | Domain abstraction layer (DomainConfig + registry) | Medium | 3–4 hours |
| 2 | P2 | Migrate code analysis to CODE_DOMAIN config | Medium | 2–3 hours |
| 3 | P3 | Content loader (`content_loader.py`) | Medium | 2–3 hours |
| 4 | P4 | Content prompts + CONTENT_DOMAIN config | Medium | 3–4 hours |
| 5 | P5 | CLI --domain flag + content baseline | Low-Medium | 2–3 hours |
| 6 | P6 | Example run + outputs (real content corpus) | Low | 1–2 hours |

**Total estimated time:** 13–19 hours (2–3 working days with agents)

---

### ISSUE P1 — Domain Abstraction Layer

**Problem:** The engine, loader, and prompts are tightly coupled. Adding a new vertical means forking the entire codebase.

**What to build:**
- `deeprepo/domains/` package with `base.py` (DomainConfig dataclass) and `__init__.py` (registry)
- DomainConfig holds: loader callable, prompt strings, metadata formatter, namespace variable name, optional clone handler
- Registry maps domain names to configs: `{"code": CODE_DOMAIN, "content": CONTENT_DOMAIN}`
- `get_domain(name)` helper with clear error for unknown domains

**Files to create:**
- `deeprepo/domains/__init__.py` — registry + `get_domain()`
- `deeprepo/domains/base.py` — `DomainConfig` dataclass

**Files to modify:**
- `deeprepo/rlm_scaffold.py` — `RLMEngine.analyze()` accepts `DomainConfig`, `_build_namespace()` accepts `data_var_name` and `sub_system_prompt` params, `run_analysis()` accepts `domain` param
- `deeprepo/baseline.py` — `run_baseline()` accepts `DomainConfig`, uses its loader and prompts

**Acceptance Criteria:**
- [ ] `DomainConfig` dataclass exists with all fields from spec above
- [ ] `get_domain("code")` returns a valid config (even if the code domain is a placeholder at this stage)
- [ ] `RLMEngine.analyze()` accepts `domain: DomainConfig` parameter
- [ ] `_build_namespace()` uses configurable variable name and sub-system prompt
- [ ] `run_analysis()` and `run_baseline()` accept `domain` string parameter, resolve via registry
- [ ] All existing tests still pass (backward compatibility)
- [ ] Default domain is `"code"` — existing behavior unchanged when `--domain` is not specified

**Anti-Patterns:**
- Do NOT create abstract base classes or inheritance hierarchies. DomainConfig is a dataclass, not an ABC.
- Do NOT change the return format of `analyze()` or `run_baseline()`.
- Do NOT move existing prompts or loader code yet — that's P2.

**Test Commands:**
```bash
cd ~/Desktop/Projects/deeprepo
python -m pytest tests/ -v
# All existing tests must pass
python -c "from deeprepo.domains import get_domain; d = get_domain('code'); print(d.name, d.label)"
```

---

### ISSUE P2 — Migrate Code Analysis to CODE_DOMAIN

**Problem:** After P1, the domain abstraction exists but the code analysis vertical still uses the old direct imports. This issue wraps the existing loader and prompts into a `CODE_DOMAIN` config.

**What to build:**
- `deeprepo/domains/code.py` — imports existing loader/prompts, assembles `CODE_DOMAIN` config
- The existing `codebase_loader.py` and code-specific prompts in `prompts.py` stay where they are — `code.py` just references them
- Update `rlm_scaffold.py` and `baseline.py` to use domain config by default

**Files to create:**
- `deeprepo/domains/code.py` — `CODE_DOMAIN = DomainConfig(name="code", ...)`

**Files to modify:**
- `deeprepo/domains/__init__.py` — register CODE_DOMAIN
- `deeprepo/rlm_scaffold.py` — `run_analysis()` defaults to `domain="code"`, resolves via registry
- `deeprepo/baseline.py` — `run_baseline()` defaults to `domain="code"`, uses domain's baseline prompt

**Key constraint:** This is a PURE REFACTOR. After this issue, running `deeprepo analyze ./some-repo` must produce identical behavior to before. The only difference is internal — the engine now routes through DomainConfig instead of direct imports.

**Acceptance Criteria:**
- [ ] `CODE_DOMAIN` config in `deeprepo/domains/code.py` references existing loader + prompts
- [ ] `run_analysis(path)` works exactly as before (domain defaults to "code")
- [ ] `run_baseline(path)` works exactly as before
- [ ] CLI works unchanged: `deeprepo analyze`, `deeprepo compare`, `deeprepo baseline`
- [ ] All existing tests pass
- [ ] The `documents` key in loader output is aliased from `codebase` (or the DomainConfig's `data_variable_name` is `"codebase"` for the code domain to preserve prompt compatibility)

**Anti-Patterns:**
- Do NOT rename the `codebase` variable in prompts or namespace for the code domain. The existing prompts reference `codebase` and that should continue working.
- Do NOT modify `codebase_loader.py` — it stays as-is, the domain config just wraps it.

**Test Commands:**
```bash
python -m pytest tests/ -v
# Verify CLI still works
python -m deeprepo.cli analyze --help
python -c "
from deeprepo.domains import get_domain
d = get_domain('code')
print(f'Domain: {d.name}')
print(f'Label: {d.label}')
print(f'Data var: {d.data_variable_name}')
print(f'Prompt preview: {d.root_system_prompt[:100]}...')
"
```

---

### ISSUE P3 — Content Loader

**Problem:** The code loader only handles source code files. For marketing content intelligence, we need a loader that handles document corpora — markdown, HTML, text, and optionally PDF.

**What to build:**
- `deeprepo/content_loader.py` — loads a directory of content documents into the same `{documents, file_tree, metadata}` format that the engine expects

**Content file types:**
- **Primary:** `.md`, `.txt`, `.html`, `.htm`
- **Secondary:** `.pdf` (text extraction via built-in libs if available, skip if not)
- **Data:** `.csv`, `.json`, `.yaml` (for analytics exports, CMS configs)
- **Skip:** images, videos, binaries, `node_modules`, `.git`, etc.

**Metadata differs from code domain:**
```python
metadata = {
    "corpus_name": "marketing-blog",
    "total_documents": 47,
    "total_chars": 250_000,
    "total_words": 42_000,       # Word count matters for content
    "document_types": {".md": 30, ".html": 10, ".txt": 7},
    "largest_documents": [("blog/q4-strategy.md", 15000), ...],
    "content_categories": [...],  # Detected from directory structure
    "date_range": {"earliest": "2024-01", "latest": "2026-02"},  # If dates detectable
}
```

**Category detection:** Use top-level subdirectory names as content categories (e.g., `blog/`, `email/`, `social/`, `landing-pages/`). If flat directory, use "uncategorized."

**Date detection:** Look for date patterns in filenames (`2026-01-15-post-title.md`) or front matter (`date: 2026-01-15`). Optional — don't fail if dates aren't found.

**Word count:** `len(content.split())` per document. Simple but useful for content analysis.

**Files to create:**
- `deeprepo/content_loader.py` — `load_content(path: str) -> dict`, `format_content_metadata(metadata: dict) -> str`

**Acceptance Criteria:**
- [ ] `load_content("./test-content/")` returns `{documents, file_tree, metadata}`
- [ ] Metadata includes `total_words` and `content_categories`
- [ ] Documents with `.md`, `.txt`, `.html` extensions are loaded
- [ ] Subdirectory names used as content categories
- [ ] `format_content_metadata()` produces a readable prompt string
- [ ] Files > 500KB are skipped (same as code domain)
- [ ] Empty directories raise `ValueError` with helpful message

**Anti-Patterns:**
- Do NOT install PDF parsing libraries in this issue. If `.pdf` files exist and `pypdf` or similar is available, use it. Otherwise, skip PDFs with a note in metadata.
- Do NOT try to parse HTML semantically — just load raw content. The sub-LLM can handle HTML.
- Do NOT over-engineer date parsing. Regex for `YYYY-MM-DD` in filenames + simple front matter check is sufficient.

**Test data:** Create `tests/test_content/` with:
- `blog/2025-06-ai-strategy.md` — a short marketing blog post
- `blog/2025-09-product-launch.md` — another blog post
- `email/newsletter-q3.html` — a simple HTML email
- `social/twitter-threads.txt` — social media content
- `brand-guidelines.md` — brand voice document

**Test Commands:**
```bash
python -m pytest tests/test_content_loader.py -v
python -c "
from deeprepo.content_loader import load_content
data = load_content('tests/test_content')
print(f'Documents: {data[\"metadata\"][\"total_documents\"]}')
print(f'Words: {data[\"metadata\"][\"total_words\"]}')
print(f'Categories: {data[\"metadata\"][\"content_categories\"]}')
"
```

---

### ISSUE P4 — Content Prompts + CONTENT_DOMAIN Config

**Problem:** The root model needs different instructions for content analysis than for code analysis. This issue creates the content-specific prompts and wires them into a CONTENT_DOMAIN config.

**What to build:**
- Content-specific system prompts for root and sub-LLMs
- `CONTENT_DOMAIN` config that uses `content_loader.py` + content prompts
- Register in domain registry

**Root System Prompt — Content Domain:**

The root model should analyze a content library for:
1. **Content Inventory** — what exists, organized by type/category/topic
2. **Brand Voice Audit** — consistency of tone, terminology, messaging across documents
3. **Content Gap Analysis** — topics covered vs. obvious gaps, audience segments underserved
4. **Quality Assessment** — writing quality, clarity, engagement, SEO considerations
5. **Editorial Recommendations** — prioritized list of content to create, update, or retire

The prompt structure mirrors the code domain: explain the REPL environment, document available variables (`documents` dict, `file_tree`, `metadata`), provide code examples for exploration and sub-LLM dispatch, define the `set_answer()` pattern.

**Key difference from code domain:** The root model should be instructed to:
- Read the brand guidelines document first (if one exists) as the reference standard
- Group analysis by content category (blog, email, social, etc.)
- Use `llm_batch()` to analyze documents for voice consistency against the brand guidelines
- Track terminology usage patterns across documents programmatically (regex, word frequency)

**Sub System Prompt — Content Domain:**

The sub-LLM worker receives individual documents and analyzes for:
1. **Summary** — what this document is about (1–2 sentences)
2. **Voice & Tone** — formal/casual, brand-aligned or drifting, terminology consistency
3. **Quality** — clarity, structure, engagement, any errors or issues
4. **Recommendations** — specific suggestions for improvement

Keep under 800 words per document analysis.

**Files to create:**
- `deeprepo/domains/content.py` — content prompts + `CONTENT_DOMAIN = DomainConfig(...)`

**Files to modify:**
- `deeprepo/domains/__init__.py` — add `CONTENT_DOMAIN` to registry

**Acceptance Criteria:**
- [ ] `CONTENT_DOMAIN` config exists with all required fields
- [ ] `get_domain("content")` returns valid config
- [ ] Root prompt references `documents` variable (not `codebase`)
- [ ] Root prompt includes content-specific analysis steps (brand voice, gaps, editorial plan)
- [ ] Sub prompt instructs for content analysis (not code analysis)
- [ ] Baseline prompt instructs for single-call content review
- [ ] `data_variable_name` is `"documents"` (not `"codebase"`)

**Anti-Patterns:**
- Do NOT copy-paste the code domain prompts and find-replace "code" with "content." The analysis tasks are fundamentally different. Write fresh prompts that make sense for content analysis.
- Do NOT make the prompts too long. The root model needs clear, actionable instructions — not a marketing strategy textbook.

**Test Commands:**
```bash
python -c "
from deeprepo.domains import get_domain
d = get_domain('content')
print(f'Domain: {d.name}')
print(f'Data var: {d.data_variable_name}')
assert d.data_variable_name == 'documents'
assert 'brand' in d.root_system_prompt.lower() or 'content' in d.root_system_prompt.lower()
print('PASS')
"
```

---

### ISSUE P5 — CLI --domain Flag + Content Baseline

**Problem:** The CLI only knows about code analysis. This issue adds the `--domain` flag and wires content analysis into all three CLI commands (`analyze`, `baseline`, `compare`).

**What to build:**
- `--domain` flag on common argument group (default: `"code"`)
- Thread domain through `cmd_analyze`, `cmd_baseline`, `cmd_compare`
- `list-domains` subcommand that shows available domains
- URL handling: for content domain, `--domain content` should NOT attempt `git clone` on non-git paths

**CLI changes:**

```bash
# Code analysis (existing, unchanged)
deeprepo analyze ./my-repo
deeprepo analyze ./my-repo --domain code  # explicit, same result

# Content analysis (new)
deeprepo analyze ./marketing-library --domain content
deeprepo baseline ./marketing-library --domain content
deeprepo compare ./marketing-library --domain content

# List available domains
deeprepo list-domains
```

**Output naming:** Content domain outputs should use `deeprepo_content_{name}_{timestamp}.md` instead of `deeprepo_{name}_{timestamp}.md`.

**Files to modify:**
- `deeprepo/cli.py` — add `--domain` to common args, thread through commands, add `list-domains` subcommand

**Acceptance Criteria:**
- [ ] `--domain code` produces identical behavior to current default
- [ ] `--domain content` routes to content loader + content prompts
- [ ] `deeprepo list-domains` shows available domains with descriptions
- [ ] Invalid `--domain` value produces helpful error message
- [ ] `deeprepo analyze --help` shows `--domain` flag with choices
- [ ] Content baseline works (single-model content analysis)
- [ ] Content compare works (RLM vs baseline for content)

**Anti-Patterns:**
- Do NOT change the default domain — it must remain `"code"` for backward compatibility.
- Do NOT require `--domain` on every command — it's optional with a sensible default.

**Test Commands:**
```bash
deeprepo list-domains
deeprepo analyze --help | grep domain
# Functional test (requires API keys, skip if not available):
# deeprepo analyze tests/test_content --domain content --max-turns 3 -q
```

---

### ISSUE P6 — Example Run + Outputs

**Problem:** The code domain has example outputs in `examples/fastapi/` and `examples/pydantic/`. The content domain needs at least one real example to demonstrate the vertical.

**What to build:**
- A sample content corpus in `examples/content-demo/input/` (5–10 markdown documents simulating a company's content library)
- Run deeprepo against it with `--domain content`
- Commit the output analysis + metrics to `examples/content-demo/`

**Sample corpus contents (create these):**
- `brand-guidelines.md` — company voice and messaging guidelines
- `blog/2025-06-ai-strategy.md` — thought leadership post
- `blog/2025-09-product-launch.md` — product announcement
- `blog/2026-01-year-in-review.md` — annual retrospective
- `email/onboarding-sequence.md` — customer onboarding email series
- `email/newsletter-q4.md` — quarterly newsletter
- `social/linkedin-posts.md` — collection of social posts
- `landing-pages/homepage.md` — homepage copy
- `landing-pages/pricing.md` — pricing page copy

These should be fictional but realistic — like a B2B SaaS company's content library. Keep each document 200–800 words. The brand guidelines should establish a voice that some documents follow and others drift from, giving the analysis something to find.

**Files to create:**
- `examples/content-demo/input/` — the sample corpus (9 files above)
- `examples/content-demo/` — output analysis + metrics (from running the tool)

**Acceptance Criteria:**
- [ ] Sample corpus exists with 9 documents across 4 categories
- [ ] Brand guidelines establish a reference voice/terminology
- [ ] At least 2 documents intentionally drift from brand voice (for the tool to catch)
- [ ] `deeprepo analyze examples/content-demo/input --domain content` produces a complete analysis
- [ ] Output committed to `examples/content-demo/`
- [ ] Cost is documented in output metrics

**This issue requires running against live APIs — budget ~$1–3 for the run.**

---

## Part 4: The Platform Narrative

### What This Proves

After P1–P6 ship, deeprepo demonstrates:

1. **Same engine, two verticals.** The RLM REPL loop, sub-LLM dispatch, caching, streaming, and retry infrastructure is shared. Only the loader and prompts change.

2. **The pattern generalizes.** Code analysis uses file extensions and import graphs. Content analysis uses word frequency and voice consistency. The root model adapts its exploration strategy to the domain based on the prompts — proving the REPL is genuinely flexible.

3. **Adding verticals is cheap.** A new vertical = one loader + one prompt file + one domain config. No engine changes. This is the "Environment Factory" from the pitch deck, pulled forward.

### How This Changes the Pitch

**Before:** "We built a coding agent that achieves 100% coverage at half the cost."
**After:** "We built an RLM orchestration platform that we proved on code analysis, then generalized to content intelligence in a week using the same engine. The third vertical is film production — where our founder has deep domain expertise. The moat is the recursive multi-model pattern, not any single vertical."

The MVP slide in the pitch deck gains a second column showing content intelligence alongside code analysis. The roadmap slide's "Environment Factory" phase moves from Q4 stretch goal to current-state proof point.

### Specific Deck Changes

- **Slide 5 (MVP):** Add content intelligence benchmark alongside code analysis benchmark. Show both use the same architecture diagram.
- **Slide 6 (Roadmap):** v0.5 becomes "Multi-vertical proof" — code + content shipped. v1 adds film/creative production as the third vertical with RL training.
- **Slide 14 (Why DeepRepo Wins):** Add bullet: "Domain-agnostic architecture — proven across verticals, not locked to code."
- **New slide (optional):** "Same Engine, Every Vertical" — architecture diagram with RLM engine in center, code/content/film as pluggable modules.

---

## Part 5: Multi-Agent Orchestration & Communication Protocol

This sprint uses a **two-agent orchestration pattern** where work is coordinated through persistent markdown scratchpad files. The agents never share a context window — they communicate exclusively through scratchpads.

---

### Agent Roles & Behavior

#### Agent 1: CTO (Claude Code / Claude Chat)

The CTO is the technical lead. It does NOT write all the code itself. Its job is to:

1. **Read the current scratchpad** (`SCRATCHPAD_CTO.md`) to understand where we are.
2. **Review completed work** from the Engineer by examining the codebase and test results.
3. **Produce a task prompt** for the Engineer — a precise, self-contained specification for the next unit of work.
4. **Run tests** after the Engineer's work is merged to verify correctness.
5. **Update the CTO scratchpad** with status, decisions, and next steps.

The CTO should NEVER start coding a task without first checking the scratchpad. If the scratchpad doesn't exist yet, create it from the template below.

**After each review cycle, the CTO produces a task prompt in this format:**

```
## Engineer Task: [P1–P6] — [SHORT_TITLE]

### Context
[1-2 sentences: what this task is and why it matters]

### Files to Modify
- `path/to/file` — [what changes needed]
- `tests/test_file` — [what tests to add]

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
Update SCRATCHPAD_ENGINEER.md with:
- What you implemented (files changed, approach taken)
- Any deviations from the spec and why
- Any issues or questions encountered
- Test results (paste output)
```

#### Agent 2: Engineer (Codex / Claude Code / any coding agent)

The Engineer receives task prompts from the CTO and executes them. Its job is to:

1. **Read `SCRATCHPAD_ENGINEER.md`** to see if there's a pending task or context from previous work.
2. **Read the task prompt** provided by the CTO.
3. **Implement the changes** according to the specification.
4. **Run tests** to verify the implementation works.
5. **Update `SCRATCHPAD_ENGINEER.md`** with what was done, test results, and any questions.

**After each task, the Engineer produces a handoff report:**

```
## Completed: [P1–P6] — [SHORT_TITLE]

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

### Scratchpad Protocol

Both agents communicate through scratchpad files in the project root. These files persist across sessions and serve as the **shared memory** between agents.

#### File: `SCRATCHPAD_CTO.md`

```markdown
# CTO Scratchpad — deeprepo Multi-Vertical Sprint

## Current Status
- **Last Updated:** [date/time]
- **Current Task:** P[N] — [title]
- **Phase:** [PLANNING | TASK_SENT | REVIEWING | DONE]
- **Tasks Completed:** [list]
- **Tasks Remaining:** [list]

## Current Task
[The task prompt currently sent to Engineer, or "awaiting Engineer handoff"]

## Review Notes
[Notes from reviewing Engineer's completed work — what passed, what needs fixes]

## Decisions Made
- [Decision 1 and rationale]
- [Decision 2 and rationale]

## Open Questions
- [Question 1]
```

#### File: `SCRATCHPAD_ENGINEER.md`

```markdown
# Engineer Scratchpad — deeprepo Multi-Vertical Sprint

## Current Status
- **Last Updated:** [date/time]
- **Current Task:** P[N] — [title] | IDLE
- **Status:** [IN_PROGRESS | DONE | BLOCKED]

## Latest Handoff
[The completed task report — see handoff format above]

## Running Context
- Package is `deeprepo/` (renamed from `src/` during infrastructure sprint)
- `deeprepo/utils.py` — retry utilities
- `deeprepo/cache.py` — content-hash caching for sub-LLM results
- All new CLI flags follow the argparse pattern in `deeprepo/cli.py`
- Tests live in `tests/` — run with `python -m pytest tests/ -v`
- Domain configs go in `deeprepo/domains/` (new package created in P1)
```

#### Rules for Scratchpad Communication

1. **Always read before writing.** Both agents must read their own scratchpad AND the other agent's scratchpad before doing anything.
2. **Never delete history.** Append new entries, don't overwrite old ones. Use `---` separators between entries.
3. **Timestamps matter.** Always include a timestamp on status updates so the other agent knows what's fresh.
4. **Be specific.** "It works" is not useful. "All 18 existing tests pass + 3 new tests added, `pytest tests/ -v` output below" is useful.
5. **Flag blockers immediately.** If the Engineer hits something that requires a CTO decision, set status to BLOCKED and describe the decision needed.

---

### Cold Start Prompts

Use these when starting a fresh session (new context window) for either agent.

#### Cold Start: CTO

```
You are acting as CTO for the deeprepo project — an open-source RLM agent platform
that uses recursive multi-model orchestration for document analysis. A root LLM writes
Python in a REPL loop, dispatching focused tasks to cheap sub-LLM workers (MiniMax M2.5
via OpenRouter).

The project just completed an infrastructure sprint (6 issues: retry, asyncio, sub-model
config, tool_use, streaming, caching). Now we're building multi-vertical support to prove
the RLM pattern generalizes beyond code analysis.

Repo: ~/Desktop/Projects/deeprepo/ (github.com/Leonwenhao/deeprepo)
Key files: deeprepo/rlm_scaffold.py, deeprepo/codebase_loader.py, deeprepo/prompts.py,
deeprepo/llm_clients.py, deeprepo/cli.py, deeprepo/domains/ (new)

You are coordinating a sprint with an Engineer agent. Your job:
1. Read SCRATCHPAD_CTO.md and SCRATCHPAD_ENGINEER.md to see current status
2. If the Engineer completed work: review it, run tests, approve or request fixes
3. If ready for next task: read PRODUCT_DEVELOPMENT.md Part 3 for the issue spec,
   produce a task prompt for the Engineer following the standard format
4. Update SCRATCHPAD_CTO.md with your decisions and status

The sprint covers these tasks in order:
P1 (domain abstraction) → P2 (code domain migration) → P3 (content loader) →
P4 (content prompts) → P5 (CLI --domain) → P6 (example run)

Read both scratchpads now and tell me where we are.
```

#### Cold Start: Engineer

```
You are a senior engineer working on deeprepo — an RLM agent platform for
multi-model document analysis. The project uses a root LLM + REPL loop +
cheap sub-LLM workers pattern.

Repo structure:
- deeprepo/rlm_scaffold.py — Core RLM engine (REPL loop, tool_use, exec)
- deeprepo/codebase_loader.py — Code-specific document loader
- deeprepo/content_loader.py — Content-specific document loader (new, P3)
- deeprepo/prompts.py — Code-specific prompts
- deeprepo/llm_clients.py — API wrappers with retry, streaming, caching
- deeprepo/cli.py — CLI entry point
- deeprepo/domains/ — Domain plugin system: base.py (DomainConfig), code.py, content.py
- deeprepo/cache.py — Content-hash caching for sub-LLM results
- deeprepo/utils.py — Retry utilities
- tests/ — pytest test suite (18 tests passing as of infrastructure sprint)

Your CTO coordinates your work via scratchpads.

1. Read SCRATCHPAD_ENGINEER.md for your current task and any context from previous work
2. Read SCRATCHPAD_CTO.md for the latest task prompt from your CTO
3. Execute the task according to the spec
4. Run tests to verify
5. Update SCRATCHPAD_ENGINEER.md with your handoff report

Start by reading both scratchpads to see what's assigned to you.
```

#### Recovery Prompt (for either agent when context is getting tight)

```
Context window is getting tight. Before continuing:
1. Read SCRATCHPAD_CTO.md and SCRATCHPAD_ENGINEER.md
2. Summarize where we are in 3 sentences
3. Identify the single next action needed
4. Do that action and update your scratchpad

Reference PRODUCT_DEVELOPMENT.md Part 3 for full task specs if needed.
```

---

### Sprint Execution Workflow

#### Step 1: Initialize Scratchpads
```bash
cd ~/Desktop/Projects/deeprepo
touch SCRATCHPAD_CTO.md SCRATCHPAD_ENGINEER.md
```

#### Step 2: First CTO Session
Paste the CTO Cold Start Prompt. The CTO reads PRODUCT_DEVELOPMENT.md, reads the scratchpads (empty), and produces the first Engineer task prompt for P1 (domain abstraction layer).

#### Step 3: First Engineer Session
Paste the Engineer Cold Start Prompt + the task prompt from the CTO. The Engineer implements, runs tests, and writes a handoff report to `SCRATCHPAD_ENGINEER.md`.

#### Step 4: Review Cycle
Return to the CTO. It reads the Engineer's scratchpad, reviews the work, runs tests, and either approves (moves to next task) or requests fixes.

#### Step 5: Repeat
CTO reviews → sends task → Engineer implements → writes handoff → CTO reviews → next task.

Continue through P1 → P2 → P3 → P4 → P5 → P6.

#### Step 6: Context Window Recovery
When either agent's context is getting tight, use the Recovery Prompt. The agent reads the scratchpads, summarizes status, and continues from where it left off.

---

### Key Design Principles

- **Scratchpads are the single source of truth.** Agents never rely on conversation memory — everything is persisted in markdown files.
- **Task prompts are self-contained.** An Engineer should be able to execute a task from just the task prompt, without needing any prior conversation context.
- **The CTO never implements, the Engineer never architects.** Clear separation of concerns prevents scope creep and keeps both agents focused.
- **Recovery is built in.** The cold start and recovery prompts mean you can always resume from a fresh context window without losing progress.
- **Append-only history.** Never overwriting scratchpad entries creates a decision log that both agents (and you) can reference.

---

## Part 6: Post-Sprint — What Comes After

### Week 2: Real Content Corpus Testing

Run the content domain against real-world content libraries:
- Your own content (tweets, LinkedIn posts, any blog drafts)
- A public company blog (many are markdown on GitHub — Ghost, Gatsby, Hugo sites)
- Offer free brand audits to 3–5 marketing teams in your network

### Week 3: Film/Creative Production Vertical (Third Proof Point)

Create `deeprepo/domains/film.py` with:
- Film loader that handles scripts (`.fountain`, `.fdx`), budgets (`.csv`, `.xlsx`), call sheets, location reports
- Prompts for script breakdown (props, locations, cast, VFX), budget analysis, continuity checking
- This is where your personal moat is strongest

### Week 4: Fundraising with Platform Narrative

- Update pitch deck with multi-vertical proof
- Founders Inc application with "same engine, three verticals" story
- The code analysis benchmarks remain your proof-of-rigor anchor
- Content and film verticals demonstrate generalization

### Parallel: SWE-bench Migration

The domain abstraction also simplifies SWE-bench migration — it becomes another domain config that produces git patches instead of analysis reports. The REPL loop, sub-LLM dispatch, and answer assembly are identical.

---

## Appendix: Test Content Corpus

Here are the sample documents for `examples/content-demo/input/`. These are intentionally imperfect — some follow brand guidelines, others drift. This gives the analysis tool something to find.

### brand-guidelines.md

The company is "Meridian" — a B2B SaaS platform for operations teams. Voice: professional but approachable, data-driven, avoids jargon, uses "we" and "you" (not "Meridian" in third person). Key terminology: "operations intelligence" (not "ops analytics"), "workflow automation" (not "process automation"), "team" (not "users" or "customers").

### Intentional drift points:

- `blog/2026-01-year-in-review.md` should use "customers" instead of "team" and slip into corporate jargon
- `social/linkedin-posts.md` should use an overly casual tone that doesn't match brand guidelines
- `landing-pages/pricing.md` should reference "Meridian" in third person ("Meridian offers...") instead of "we"

These give the content analysis tool concrete findings to surface, making the example output more compelling as a demo.
