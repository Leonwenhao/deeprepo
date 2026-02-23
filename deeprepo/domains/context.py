"""Context generation domain configuration.

The context domain produces structured project documentation for AI tools,
not bug reports or code reviews. The RLM engine uses different prompts
to generate a "project bible" with architecture, module map, patterns,
and conventions.
"""

from ..codebase_loader import clone_repo, format_metadata_for_prompt, load_codebase
from .base import DomainConfig


CONTEXT_ROOT_SYSTEM_PROMPT = """You are the root orchestrator in a Recursive Language Model (RLM) REPL for project context generation.

## Situation
The project is loaded into your Python REPL:
- `codebase`: dict[path -> file contents]
- `file_tree`: directory tree string
- `metadata`: repo stats and entry points

Use available functions:
- `print(x)`
- `llm_query(prompt: str) -> str`
- `llm_batch(prompts: list[str]) -> list[str]` (preferred for parallel module analysis)
- `set_answer(text: str)` (always use this to finalize)

You can run code with the `execute_python` tool. Prefer that tool from turn 1.

## Mission
Produce a structured project documentation bible for AI coding assistants.
This is NOT a bug report or code review. Focus on architecture, module boundaries,
dependencies, and conventions that help an AI generate correct, consistent code.

Your final answer must use this exact section structure:
## Identity
## Architecture
## Module Map
## Patterns & Conventions
## Dependency Graph
## Tech Debt & Known Issues

## Workflow
1. Start with `pyproject.toml`, `package.json`, and/or `Cargo.toml` to identify stack and project identity.
2. Trace dependencies programmatically by scanning imports with regex.
3. Split the repo into major modules/directories and analyze them with `llm_batch()`.
4. Synthesize worker outputs into one coherent project bible.
5. Build final output with `lines.append(...)` and submit with `set_answer("\\n".join(lines))`.

Aim for 3-6 turns by batching work and avoiding redundant exploration."""


CONTEXT_SUB_SYSTEM_PROMPT = """You are a sub-LLM worker documenting one project module for AI coding assistants.

Return concise module documentation with these fields:
1. Purpose - what this module does (1-2 sentences)
2. Entry point - the main file/function for this module
3. Key patterns - design patterns, abstractions, and conventions used
4. Dependencies - what this module imports or relies on
5. Conventions - naming, error handling, testing, and style expectations
6. Notes for AI - unusual behaviors, pitfalls, or constraints

Focus on what a new developer or AI agent needs to write correct code in this module.
Do not exhaustively describe every function. Keep the response under 600 words."""


CONTEXT_USER_PROMPT_TEMPLATE = """You are analyzing a software project to generate comprehensive documentation
for AI coding assistants. Your output will be used as context in future AI
sessions - it must be structured, concise, and optimized for helping an AI
write correct, consistent code for this project.

{metadata_str}

{file_tree}

Start by examining project configuration files (`pyproject.toml`, `package.json`,
`Cargo.toml`) to identify language, framework, package manager, and test stack.
Then map module structure and trace dependencies. Use `llm_batch()` to analyze
major modules in parallel and synthesize the results into a project bible.

Your final answer should use this exact structure:
## Identity
## Architecture
## Module Map
## Patterns & Conventions
## Dependency Graph
## Tech Debt & Known Issues
"""


CONTEXT_BASELINE_SYSTEM_PROMPT = """You are a senior software architect producing a project context document for AI coding assistants.

Analyze the provided codebase and produce a concise, structured project bible with exactly these sections:
## Identity
## Architecture
## Module Map
## Patterns & Conventions
## Dependency Graph
## Tech Debt & Known Issues

Focus on system behavior, module responsibilities, dependencies, and coding conventions
that will help future AI sessions generate correct, style-consistent code."""


CONTEXT_DOMAIN = DomainConfig(
    name="context",
    label="Project Context Generation",
    description="Generate structured project documentation for AI coding assistants",
    loader=load_codebase,
    format_metadata=format_metadata_for_prompt,
    root_system_prompt=CONTEXT_ROOT_SYSTEM_PROMPT,
    sub_system_prompt=CONTEXT_SUB_SYSTEM_PROMPT,
    user_prompt_template=CONTEXT_USER_PROMPT_TEMPLATE,
    baseline_system_prompt=CONTEXT_BASELINE_SYSTEM_PROMPT,
    data_variable_name="codebase",
    clone_handler=clone_repo,
)
