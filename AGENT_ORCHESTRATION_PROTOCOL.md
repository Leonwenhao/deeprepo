# Multi-Agent Orchestration & Communication Protocol

> **Usage:** Paste this into a Claude chat session to establish a CTO ↔ Engineer agent coordination workflow using scratchpad-based communication. Replace placeholders in `[BRACKETS]` with your project specifics.

---

## Agent Roles & Behavior

This project uses a **three-party orchestration pattern**: a human operator relays work between a CTO agent (Claude Code) and an Engineer agent (Codex). The agents never share a context window — they communicate exclusively through persistent markdown scratchpad files and the human relay.

### The Human Operator (You)

You are the bridge. Your job:

1. **Start a CTO session** — paste the cold start prompt into Claude Code.
2. **Relay task prompts** — copy the CTO's Codex task prompt, paste it into a Codex session.
3. **Relay results** — copy Codex's scratchpad update and completion output, paste it back into the CTO session.
4. **Monitor context** — if the CTO doesn't self-trigger a handoff, prompt it to check (see Context Window Management below).
5. **Manage session boundaries** — when the CTO writes a cold start handoff, close the session and start fresh.

You do not need to understand the code. You are the message bus.

### Agent 1: CTO (Claude Code)

The CTO is the technical lead. It does NOT write implementation code. Its job is to:

1. **Read the current scratchpad** (`SCRATCHPAD_CTO.md`) to understand where we are.
2. **Review completed work** from the Engineer by examining the codebase and test results.
3. **Produce a task prompt** for the Engineer — a precise, self-contained specification for the next unit of work.
4. **Run tests** after the Engineer's work is merged to verify correctness.
5. **Update the CTO scratchpad** with status, decisions, and next steps.
6. **Monitor its own context window** and write a continuation cold start prompt before capacity runs out.

The CTO should NEVER start coding a task without first checking the scratchpad. If the scratchpad doesn't exist yet, create it from the template below.

**After each review cycle, the CTO produces a task prompt in this format:**

```
## Engineer Task: [ISSUE/TASK_ID] — [SHORT_TITLE]

### Context
[1-2 sentences: what this task is and why it matters]

### Files to Create
- `path/to/new_file.py` — [purpose]

### Files to Modify
- `path/to/file` — [what changes needed]
- `tests/test_file` — [what tests to add]

### Specification
[Detailed spec: function signatures, logic flow, edge cases.
CRITICAL: Include relevant code snippets from existing files.
The Engineer cannot see the sprint plan or project docs —
everything it needs must be in this prompt.]

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

**Task prompt self-containment rule:** The Engineer operates in an isolated context. It cannot read the sprint plan, the project's development docs, or the CTO's conversation history. Every function signature, data structure, import path, and convention the Engineer needs must be included verbatim in the task prompt. If the task modifies existing code, include the current state of that code. "See the plan" is never acceptable.

### Agent 2: Engineer (Codex / Claude Code / any coding agent)

The Engineer receives task prompts from the CTO and executes them. Its job is to:

1. **Read `SCRATCHPAD_ENGINEER.md`** to see if there's a pending task or context from previous work.
2. **Read the task prompt** provided by the CTO.
3. **Implement the changes** according to the specification.
4. **Run tests** to verify the implementation works.
5. **Update `SCRATCHPAD_ENGINEER.md`** with what was done, test results, and any questions.

**After each task, the Engineer produces a handoff report:**

```
## Completed: [ISSUE/TASK_ID] — [SHORT_TITLE]

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

## Context Window Management

### The Problem

LLM agents lose track of instructions read at the start of a session as the context window fills. The CTO is particularly vulnerable — it reads the cold start prompt once, then enters a review-produce-review cycle with strong momentum that crowds out self-monitoring. Without a structural trigger, context checks get skipped 100% of the time.

### The Fix: Mandatory Scratchpad Check

The context check is embedded in the scratchpad update — the one step the CTO performs every review cycle. It cannot be skipped because it's a required field in the scratchpad template.

**Every time the CTO updates `SCRATCHPAD_CTO.md` after a review, it MUST include:**

```
## Context Check
- Tasks reviewed this session: [count]
- Estimated context usage: [LOW | MEDIUM | HIGH | CRITICAL]
- Action: [CONTINUE | HANDOFF AFTER THIS TASK]
```

**Severity scale (introspective, not just count-based):**

| Level | Signals | Action |
|-------|---------|--------|
| **LOW** | Conversation feels short. Can recall all decisions without effort. | Continue. |
| **MEDIUM** | Have to think to recall early decisions. 3+ review cycles done. | Finish current task, then write handoff. Do NOT start a new task. |
| **HIGH** | Can't confidently recall early task details without scrolling up. | Finish current task, then write handoff immediately. |
| **CRITICAL** | Paraphrasing from memory instead of quoting specifics. Losing details. | Finish current task, then write handoff immediately. |

### Handoff Protocol

When context reaches MEDIUM or higher:

1. **Finish the current task FIRST.** Complete the review, approve or send fixes, confirm DONE, update scratchpad. NEVER abandon a task mid-review.
2. **Write a continuation cold start prompt.** A new markdown document the human can paste into a fresh session. Must include:
   - Which tasks are completed, with deviations and decisions made
   - Current state of both scratchpads (summarized)
   - The next task to work on
   - Patterns, conventions, and bugs discovered during this session
   - Any file context (function signatures, data structures) needed again
   - The context check protocol itself (so the fix persists)
3. **Signal the human:** "Ready for fresh session. Here's the handoff."

### Human Override

If the CTO hasn't self-triggered a handoff and you suspect context is getting tight (long conversation, 4+ review cycles, responses getting less precise), paste this:

```
CONTEXT WINDOW CHECK — READ THIS IMMEDIATELY

You may be past your context threshold. Answer honestly:
1. Can you recall the key decisions from your first review this session without scrolling?
2. What's your estimated context level? (LOW / MEDIUM / HIGH / CRITICAL)

If MEDIUM+: finish current task, then write your handoff.
```

---

## Scratchpad Protocol

Both agents communicate through scratchpad files in the project root. These files persist across sessions and serve as the **shared memory** between agents.

### File: `SCRATCHPAD_CTO.md`

```markdown
# CTO Scratchpad — [PROJECT_NAME]

## Current Status
- **Last Updated:** [date/time]
- **Current Task:** #[N] — [title]
- **Phase:** [PLANNING | TASK_SENT | REVIEWING | DONE]
- **Tasks Completed:** [list]
- **Tasks Remaining:** [list]

## Context Check
- Tasks reviewed this session: [count]
- Estimated context usage: [LOW | MEDIUM | HIGH | CRITICAL]
- Action: [CONTINUE | HANDOFF AFTER THIS TASK]

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

### File: `SCRATCHPAD_ENGINEER.md`

```markdown
# Engineer Scratchpad — [PROJECT_NAME]

## Current Status
- **Last Updated:** [date/time]
- **Current Task:** [TASK_ID] — [title] | IDLE
- **Status:** [IN_PROGRESS | DONE | BLOCKED]

## Latest Handoff
[The completed task report — see handoff format above]

## Running Context
- [Any context that carries across tasks, e.g., "retry decorator is in src/utils.py"]
- [Patterns established, e.g., "all new CLI flags follow the argparse pattern in cli.py"]
```

### Rules for Scratchpad Communication

1. **Always read before writing.** Both agents must read their own scratchpad AND the other agent's scratchpad before doing anything.
2. **Never delete history.** Append new entries, don't overwrite old ones. Use `---` separators between entries.
3. **Timestamps matter.** Always include a timestamp on status updates so the other agent knows what's fresh.
4. **Be specific.** "It works" is not useful. "All 9 existing tests pass + 3 new tests added, `pytest tests/ -v` output below" is useful.
5. **Flag blockers immediately.** If the Engineer hits something that requires a CTO decision, set status to BLOCKED and describe the decision needed.

---

## Cold Start Prompts

Use these when starting a fresh session (new context window) for either agent.

### Cold Start: CTO

```
You are acting as CTO for [PROJECT_NAME] — [1-sentence project description].

Repo: [REPO_PATH]
Key files: [list key source files]

You are coordinating a sprint with an Engineer agent (Codex). Your job:
1. Read SCRATCHPAD_CTO.md and SCRATCHPAD_ENGINEER.md to see current status
2. If the Engineer completed work: review it, run tests, approve or request fixes
3. If ready for next task: read [SPRINT_DOC] for the issue spec,
   produce a task prompt for the Engineer following the standard format
4. Update SCRATCHPAD_CTO.md with your decisions and status

CRITICAL — Task prompts must be FULLY SELF-CONTAINED. The Engineer cannot see
[SPRINT_DOC], project files, or this conversation. Include all code snippets,
function signatures, and conventions the Engineer needs.

CRITICAL — Context window monitoring. Every time you update SCRATCHPAD_CTO.md
after a review, you MUST fill in the Context Check section:
- Tasks reviewed this session: [count]
- Estimated context usage: [LOW | MEDIUM | HIGH | CRITICAL]
- Action: [CONTINUE | HANDOFF AFTER THIS TASK]
If MEDIUM+: finish current task, then write a cold start handoff for a fresh
session. Do NOT start a new task prompt.

The sprint covers these tasks in order:
[TASK_1] → [TASK_2] → [TASK_3] → ...

Read both scratchpads now and tell me where we are.
```

### Cold Start: Engineer

```
You are a senior engineer working on [PROJECT_NAME] — [1-sentence project description].

Repo structure:
- [path] — [description]
- [path] — [description]

Your CTO coordinates your work via scratchpads.

1. Read SCRATCHPAD_ENGINEER.md for your current task and any context from previous work
2. Read SCRATCHPAD_CTO.md for the latest task prompt from your CTO
3. Execute the task according to the spec
4. Run tests to verify
5. Update SCRATCHPAD_ENGINEER.md with your handoff report

Start by reading both scratchpads to see what's assigned to you.
```

---

## Sprint Execution Workflow

### Step 1: Initialize Scratchpads
```bash
touch SCRATCHPAD_CTO.md SCRATCHPAD_ENGINEER.md
```

### Step 2: First CTO Session
Paste the CTO Cold Start Prompt into Claude Code. The CTO reads the sprint doc, reads the scratchpads (empty), and produces the first Engineer task prompt.

### Step 3: Relay to Engineer
Copy the CTO's task prompt. Paste it into a Codex session (with the Engineer Cold Start if it's a fresh session). Codex implements, runs tests, and writes a handoff report to `SCRATCHPAD_ENGINEER.md`.

### Step 4: Relay Back to CTO
Copy the Engineer's scratchpad update and any relevant output. Paste it back into the CTO's Claude Code session. The CTO reviews, runs tests, and either approves (moves to next task) or produces a fix prompt.

### Step 5: Repeat
CTO reviews → updates scratchpad (with context check) → sends task → you relay to Codex → Codex completes → you relay back → CTO reviews.

### Step 6: Context Handoff
When the CTO's context check hits MEDIUM+, it finishes the current task, writes a continuation cold start prompt, and signals you. Close the session, open a fresh one, paste the new cold start.

### Step 7: Sprint Completion
When all tasks are done, the CTO produces a final session log entry and end-of-sprint summary.

---

## Key Design Principles

- **Scratchpads are the single source of truth.** Agents never rely on conversation memory — everything is persisted in markdown files.
- **Task prompts are self-contained.** An Engineer should be able to execute a task from just the task prompt, without needing any prior conversation context or access to sprint docs.
- **The CTO never implements, the Engineer never architects.** Clear separation of concerns prevents scope creep and keeps both agents focused.
- **Context monitoring is structural, not aspirational.** The check is a mandatory scratchpad field, not an instruction to remember. Anything that depends on an agent "remembering" an instruction from the start of a long session will fail.
- **Recovery is built in.** Cold start prompts and scratchpads mean you can always resume from a fresh context window without losing progress.
- **Append-only history.** Never overwriting scratchpad entries creates a decision log that both agents (and you) can reference.
- **The human is the message bus, not the bottleneck.** You relay, you don't interpret. If something needs a decision, the CTO asks you explicitly.
