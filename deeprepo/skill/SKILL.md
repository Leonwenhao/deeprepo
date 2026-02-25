---
name: deeprepo
description: AI project memory skill. Automatically loads .deeprepo/COLD_START.md project context at session start, and provides commands to analyze, refresh, and manage project memory. Use when starting work on a project, when asked about project architecture, or when the user invokes /deeprepo.
---

# deeprepo

deeprepo is a CLI tool that generates and maintains a `.deeprepo/` project memory directory. This skill integrates it into your Claude Code workflow so project context is available automatically — no more re-explaining your architecture every session.

## Session Start Protocol

At the start of every session, check whether `.deeprepo/COLD_START.md` exists in the current working directory. If it does, read it immediately and tell the user their project context has been loaded. If it doesn't, offer to initialize it.

**If `.deeprepo/COLD_START.md` exists:**
Read the file and internalize the project context. Tell the user:
> "Project context loaded from `.deeprepo/COLD_START.md`."

**If `.deeprepo/` does not exist:**
Tell the user:
> "No project context found. Run `/deeprepo:init` to analyze this project (~$0.50–$1, 1–10 min)."

## Commands

### /deeprepo or /deeprepo:init — Analyze project and generate memory

Run:
```bash
deeprepo init .
```

This analyzes the codebase using recursive multi-model orchestration and generates `.deeprepo/` with:
- `PROJECT.md` — full architecture bible (architecture, patterns, decisions, dependencies)
- `COLD_START.md` — compressed context optimized for AI tool context windows
- `SESSION_LOG.md` — running history of sessions
- `SCRATCHPAD.md` — working notes for coordination

After init completes, read `.deeprepo/COLD_START.md` and summarize what was discovered.

**Options:**
- `--root-model opus` — use Claude Opus for maximum quality (costs more)
- `--force` — re-analyze and overwrite existing context
- `--max-turns 30` — allow more exploration turns (default: 20)

**Prerequisites:** `ANTHROPIC_API_KEY` and `OPENROUTER_API_KEY` must be set.

**Cost:** $0.43–$0.95 for most projects. Sub-LLM layer is ~2% of total cost.

### /deeprepo:context — Load or copy project context

Read and display the current project context:
```bash
cat .deeprepo/COLD_START.md
```

Copy to clipboard for pasting into other tools:
```bash
deeprepo context --copy
```

### /deeprepo:status — Check context freshness

```bash
deeprepo status
```

Reports whether `.deeprepo/` exists, when context was last generated, and whether a refresh is recommended.

### /deeprepo:refresh — Update context after changes

```bash
deeprepo refresh
```

Re-analyzes changed files and updates `PROJECT.md` and `COLD_START.md`. Run after major refactors or adding significant new features.

For a full re-analysis from scratch:
```bash
deeprepo refresh --full
```

### /deeprepo:log — Record session activity

Log what was accomplished in this session:
```bash
deeprepo log "what was done this session"
```

View recent session history:
```bash
deeprepo log show
```

Recent sessions are automatically included in `COLD_START.md` so future sessions have continuity.

## Typical Workflow

**First-time setup (once per project):**
1. `/deeprepo:init` — analyze the project
2. Context is auto-loaded in all future sessions

**Every session:**
1. Skill auto-loads `COLD_START.md` → Claude has instant project awareness
2. Work on tasks
3. End of session → `/deeprepo:log "brief summary"` to capture progress

**After significant changes:**
- `/deeprepo:refresh` to keep context current

## Installation

If `deeprepo` is not installed:
```bash
pipx install deeprepo-cli
```

Then install this skill into Claude Code:
```bash
deeprepo install-skill
```
