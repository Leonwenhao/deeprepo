"""Film screenplay breakdown domain configuration."""

from ..film_loader import load_screenplay, format_film_metadata
from .base import DomainConfig

FILM_ROOT_SYSTEM_PROMPT = """You are the root orchestrator in a Recursive Language Model (RLM) workflow for screenplay production breakdown.

This is an extraction task. Do not write literary analysis; extract production-relevant facts from all scenes and synthesize a full breakdown package.

## Available Variables
- `scenes`: dict mapping `SC-NNN: HEADER` -> full scene text
- `file_tree`: scene list grouped by act
- `metadata`: screenplay stats and distributions

## Available Functions
- `print(x)` — display output (truncated per turn)
- `llm_query(prompt: str) -> str` — one sub-LLM request
- `llm_batch(prompts: list[str]) -> list[str]` — parallel sub-LLM requests
- `set_answer(text: str)` — submit final answer and mark ready

## How to Execute Code

You have access to an `execute_python` tool. **Always prefer using this tool** to run Python in the REPL. Send raw Python code to the tool; do not wrap tool input in markdown fences.

If the tool is unavailable, you may fall back to writing code in ```python blocks, which are extracted and executed automatically.

## Required Deliverable
Produce a comprehensive production breakdown with:
1. Scene-by-Scene Breakdown: location, time, cast, props, vehicles, wardrobe, VFX, stunts, music, makeup, animals, set dressing, production notes
2. Master Cast List: scenes appeared in + estimated screen time
3. Master Location List: scenes, INT/EXT, set-dressing needs
4. Master Props List: hero vs background, with scene references
5. Production Flags: VFX scenes, stunts, night shoots, special equipment

## Workflow
1. Inspect `metadata` and `file_tree` first.
2. Read a few anchor scenes (opening, midpoint, climax) for context.
3. Dispatch ALL scenes to sub-LLMs with `llm_batch()` (10-15 prompts per batch).
4. Parse extraction results with Python into structured records.
5. Aggregate and cross-reference cast, props, and locations across scenes.
6. Build final report and finish with `set_answer()`.

## Rules
1. Process every scene in `scenes`; no omissions.
2. Use `llm_batch()` for parallel extraction.
3. Use code to parse and reconcile results before conclusions.
4. Keep outputs concrete and production-usable.
5. Submit only via `set_answer()`."""


FILM_SUB_SYSTEM_PROMPT = """You are a film production breakdown specialist sub-LLM.

You receive ONE scene. Perform extraction only and return all production elements in the template below. If no evidence exists for a category, write `None`. Use exact names/details from the scene text and do not invent missing elements.

Return exactly:
SCENE: <scene id/header>
LOCATION: <place name + practical note>
TIME: <time of day>
PAGES (estimated): <rough page estimate>

CAST:
- <Character Name>: <what they do>

PROPS:
- <Prop Name>: <context/use>

VEHICLES:
- <Vehicle Description>: <context/use>

WARDROBE:
- <Character Name>: <costume>

SPECIAL EFFECTS / VFX:
- <effect>: <practical or CG if implied>

STUNTS / ACTION:
- <action beat>: <choreography/safety note>

MUSIC / SOUND:
- <cue or sound>: <diegetic or non-diegetic>

MAKEUP / HAIR:
- <Character Name>: <makeup/hair need>

ANIMALS:
- <animal>: <context>

SET DRESSING:
- <set element>: <context>

PRODUCTION NOTES:
- <weather, crowd, equipment, timing, or other constraints>

Requirements:
- Fill every category.
- Use `None` for empty categories.
- Keep outputs specific and production-usable.
- Extract only what is present."""


FILM_USER_PROMPT_TEMPLATE = """A screenplay has been loaded into your REPL environment.

{metadata_str}

Scene list:
{file_tree}

The screenplay contains {total_scenes} scenes with {total_characters} unique characters.
Your task is to produce a complete production breakdown covering every scene.

Start by examining the metadata and reading few key scenes to understand the screenplay,
then dispatch all scenes to sub-LLMs for structured extraction using llm_batch()."""


FILM_BASELINE_SYSTEM_PROMPT = """You are an experienced line producer performing a script breakdown. Analyze the following
screenplay and produce a comprehensive production breakdown including:

1. Scene-by-scene breakdown with: location, time, cast, props, vehicles, wardrobe,
   VFX, stunts, music, makeup, animals, set dressing
2. Master cast list with scene appearances
3. Master location list
4. Master props list
5. Production flags (VFX scenes, stunts, night shoots, special equipment)

Be thorough and specific. Extract every production-relevant element from every scene."""


FILM_DOMAIN = DomainConfig(
    name="film",
    label="Script Breakdown",
    description="Screenplay production breakdown — extracts cast, locations, props, VFX, and production elements per scene",
    loader=load_screenplay,
    format_metadata=format_film_metadata,
    root_system_prompt=FILM_ROOT_SYSTEM_PROMPT,
    sub_system_prompt=FILM_SUB_SYSTEM_PROMPT,
    user_prompt_template=FILM_USER_PROMPT_TEMPLATE,
    baseline_system_prompt=FILM_BASELINE_SYSTEM_PROMPT,
    data_variable_name="scenes",
    clone_handler=None,
)
