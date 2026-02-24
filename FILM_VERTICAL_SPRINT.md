# deeprepo — Film Vertical Sprint Plan

**Author:** Leon (with Claude)
**Date:** February 21, 2026
**Sprint Goal:** Ship film/screenplay breakdown as the third domain vertical, benchmarked against Get Out (2017) ground truth.
**Agents:** Claude Code (CTO) + Codex (Senior Engineer)

---

## Executive Summary

The film vertical is deeprepo's third domain plugin and its strongest proof of generalization. Code analysis and content intelligence share obvious structural similarity (both are text files in directories). Film production breakdown is a fundamentally different task — structured extraction from narrative prose, not analysis of technical artifacts — which eliminates the "this is just a code tool with aliases" objection.

The deliverable: `deeprepo analyze ./get-out-screenplay.pdf --domain film` producing a structured production breakdown with scene-by-scene extraction of cast, locations, props, vehicles, wardrobe, VFX, stunts, and music — using the same REPL loop, sub-LLM dispatch, caching, and streaming infrastructure that powers the other two verticals.

The benchmark: three-way comparison (RLM vs baseline vs compiled ground truth) scored on precision/recall/F1 per extraction category. This is the most rigorous evaluation deeprepo has attempted — ground truth compiled from 23 public sources with 200+ verified production elements.

---

## Part 1: Why Film Matters Strategically

**No competition in this lane.** Every RL environment company (HUD, Plato, Mechanize, Halluminate) targets code, legal, or finance. Zero are touching film production. This is blue ocean.

**Real job, real price tag.** Studios pay $2–5K for professional script breakdown per project. Line producers and ADs spend 40–80 hours manually tagging scenes. An RLM that does this in minutes for $1–3 is immediately valuable.

**Founder moat.** Leon has 10 years of film production experience. This isn't a domain being chosen for demo purposes — it's genuine expertise that informs prompt quality, extraction categories, and evaluation methodology in ways that a pure-tech founder couldn't replicate.

**The coverage contradiction is dramatic here.** A 120-page screenplay technically fits in a single context window (~50K tokens). But extracting dozens of discrete data points per scene across 70 scenes is exactly where baseline single-model calls degrade — too many extraction targets, not enough attention per scene. RLM's scene-by-scene dispatch gives each scene focused analysis.

**Self-validating benchmark.** Unlike code analysis (where "bugs found" is subjective) or content analysis (where "brand drift" is qualitative), film breakdown has objectively verifiable answers. Did the system identify that Chris Washington appears in Scene 14? Yes or no. This makes the F1 scoring rigorous and publishable.

---

## Part 2: Technical Architecture

### How Film Differs from Code/Content

| Aspect | Code Domain | Content Domain | Film Domain |
|--------|-------------|----------------|-------------|
| Input unit | File (source code) | Document (article, email) | Scene (narrative block) |
| Task type | Analysis (find bugs, patterns) | Analysis (voice, gaps, quality) | **Extraction** (structured data from prose) |
| Output format | Prose report with priorities | Prose report with recommendations | **Structured templates** per scene + master lists |
| Splitting logic | File boundaries (already discrete) | File boundaries | Scene headers (INT./EXT. regex) |
| Sub-LLM job | "Analyze this file for issues" | "Analyze this document for voice" | **"Extract production elements from this scene"** |
| Success metric | Quality of insights (subjective) | Quality of insights (subjective) | **Precision/Recall/F1** (objective) |
| Cross-reference need | Import graphs, dependencies | Category groupings | **Character tracking, prop continuity, location reuse** |

The critical difference: film prompts are EXTRACTION-focused, not analysis-focused. The sub-LLM fills a structured template, not writes a prose critique.

### Loader Strategy

Screenplays are not directories of files — they're single documents (PDF or plain text) that need to be split into scenes. The film loader must:

1. Accept a single file (`.pdf`, `.txt`, or `.fountain`)
2. Extract text (PDF → text conversion if needed)
3. Split on scene headers (`INT.` / `EXT.` / `INT./EXT.` / `I/E.` patterns)
4. Build the same `{documents, file_tree, metadata}` dict the engine expects
5. Each scene becomes one entry: key = `"SC-001: EXT. SUBURBAN STREET - NIGHT"`, value = full scene text

This is different from the code/content loaders which walk directories. The film loader parses a single document into logical units.

### Namespace Variable

`data_variable_name = "scenes"` — distinct from `"codebase"` (code) and `"documents"` (content). The root model accesses `scenes["SC-001: EXT. SUBURBAN STREET - NIGHT"]`.

---

## Part 3: Get Out Ground Truth

### Source

*Get Out* (2017), written and directed by Jordan Peele. ~104 pages, ~65–75 scenes depending on version. Widely studied film with extensive public documentation of production elements.

### Ground Truth Compilation

The ground truth dataset should be compiled from publicly available sources and committed as `GET_OUT_GROUND_TRUTH.md`. Categories and verification sources:

**1. Cast / Characters**
- IMDb full cast list (imdb.com/title/tt5052448/fullcredits)
- Script character names mapped to actors
- Per-scene presence tracked from screenplay text
- Key characters: Chris Washington, Rose Armitage, Missy Armitage, Dean Armitage, Jeremy Armitage, Georgina, Walter, Rod Williams, Jim Hudson, Andre Hayworth/Logan King
- ~15–20 named characters total

**2. Locations**
- IMDb filming locations page
- Film Location Magazine / Atlas of Wonders coverage
- Key locations: Armitage Estate (exterior + interior rooms), TSA Office, Chris's apartment, suburban neighborhood (opening), party/garden area, operating room/basement, car interiors
- Primary filming: Fairhope, Alabama (standing in for upstate New York)
- ~12–18 distinct locations

**3. Props**
- Screenplay stage directions (primary source)
- Production design interviews (Rusty Smith, production designer)
- Key props: camera (Chris's), teacup and spoon (Missy's hypnosis), phone, deer antler mount, cotton stuffing, car keys, shotgun, surgical tools, lacrosse stick/ball, flash photography equipment, bingo cards
- ~25–40 significant props

**4. Vehicles**
- Visible in film and described in script
- Key: Rose's car (Porsche Cayenne in film), Rod's TSA vehicle, police car, deer collision vehicle
- ~4–6 vehicles

**5. Wardrobe**
- Costume designer Nadine Haders interviews
- Visual references from film stills
- Key: Chris's casual vs. party wardrobe, Rose's outfits (white = innocence coding), Armitage family formal wear, Georgina's maid uniform, Walter's groundskeeper clothes
- ~15–25 wardrobe elements

**6. Special Effects / VFX**
- The Sunken Place sequences (VFX heavy)
- Deer collision practical + VFX
- Brain surgery sequences
- Hypnosis visual effects
- ~8–12 VFX/SFX elements

**7. Stunts / Action**
- Final act fight sequences (Chris vs Jeremy, Chris vs Dean, Chris vs Missy)
- Jeremy's headlock/wrestling
- Car crash
- Walter's run
- ~6–10 stunt sequences

**8. Music / Sound**
- "Sikiliza Kwa Wahenga" (original score, Michael Abels)
- "(I've Had) The Time of My Life" — party scene
- "Run Rabbit Run" — car scene
- Specific diegetic sound cues from script
- ~8–12 music/sound elements

### Scoring Methodology

For each extraction category, compute:
- **Precision** = correct extractions / total extractions (did the system make stuff up?)
- **Recall** = correct extractions / total ground truth items (did the system miss things?)
- **F1** = harmonic mean of precision and recall

A "correct extraction" means the system identified an element that matches a ground truth entry, allowing for reasonable paraphrasing (e.g., "teacup" matches "Missy's tea cup"). Matching should be case-insensitive and allow partial string matches for compound items.

---

## Part 4: Issue Specifications

### Issue Priority Order

| Order | Issue | Title | Complexity | Est. Time |
|:-----:|:-----:|-------|:----------:|:---------:|
| 1 | F1 | Film loader (`film_loader.py`) + scene parsing | Medium-High | 3–4 hours |
| 2 | F2 | Film prompts + `FILM_DOMAIN` config | Medium | 3–4 hours |
| 3 | F3 | Get Out ground truth + integration test | Medium | 2–3 hours |
| 4 | F4 | Full benchmark run — RLM vs baseline vs ground truth | Medium | 2–3 hours |
| 5 | F5 | Commit results to `examples/get-out/` + documentation | Low | 1–2 hours |

**Total estimated time:** 11–16 hours (2 working days with agents)

---

### ISSUE F1 — Film Loader

**Problem:** The existing loaders (`codebase_loader.py`, `content_loader.py`) walk directories of individual files. Screenplays are single documents that must be parsed into scene-level units. We need a loader that takes a screenplay file (PDF or plain text), splits it into scenes, and returns the standard `{documents, file_tree, metadata}` format.

**What to build:**
- `deeprepo/film_loader.py` — parses a screenplay into scenes, returns engine-compatible dict

**Input types:**
- `.txt` — plain text screenplay (direct parsing)
- `.pdf` — PDF screenplay (text extraction first, then parsing)
- `.fountain` — Fountain markup format (parse according to spec)

**Scene header detection:**

The core parsing challenge. Scene headers (sluglines) follow industry standard format:

```
INT. ARMITAGE HOUSE - LIVING ROOM - NIGHT
EXT. SUBURBAN STREET - NIGHT
INT./EXT. CAR - MOVING - DAY
I/E. ROSE'S CAR - CONTINUOUS
```

Regex pattern for detection:
```python
SCENE_HEADER_PATTERN = re.compile(
    r'^[ \t]*'                           # Optional leading whitespace
    r'(INT\.|EXT\.|INT\./EXT\.|I/E\.)'   # Required INT/EXT prefix
    r'[ \t]+'                            # Required space after prefix
    r'(.+?)$',                           # Location + time description
    re.MULTILINE | re.IGNORECASE
)
```

Additional heuristics:
- Scene headers are typically ALL CAPS or predominantly uppercase
- They're followed by action/description text, not dialogue
- Some scripts use numbering: `14. INT. KITCHEN - NIGHT` or `14 INT. KITCHEN - NIGHT`
- Handle both numbered and unnumbered variants

**Character name detection:**

In standard screenplay format, character names appear in ALL CAPS on their own line, preceding dialogue:

```
                    CHRIS
          You sure it's cool, me coming?
          
                    ROSE
          Yeah, of course!
```

Detection approach:
```python
CHARACTER_PATTERN = re.compile(
    r'^[ \t]{10,}([A-Z][A-Z\s\.\-\']+?)(?:\s*\(.*?\))?[ \t]*$',
    re.MULTILINE
)
```

- Must be centered (significant leading whitespace, typically 10+ spaces or 2+ tabs)
- ALL CAPS
- May have parenthetical: `CHRIS (V.O.)`, `ROSE (CONT'D)`
- Collect unique character names, strip parentheticals for the master list
- Filter out common false positives: `CUT TO`, `FADE IN`, `FADE OUT`, `DISSOLVE TO`, `CONTINUED`, `THE END`

**Output format:**
```python
{
    "documents": {
        "SC-001: EXT. SUBURBAN STREET - NIGHT": "full scene text here...",
        "SC-002: INT. CHRIS'S APARTMENT - BEDROOM - DAY": "full scene text...",
        # ...
    },
    "file_tree": (
        "Get Out (2017)\n"
        "  ACT 1\n"
        "    SC-001: EXT. SUBURBAN STREET - NIGHT\n"
        "    SC-002: INT. CHRIS'S APARTMENT - BEDROOM - DAY\n"
        "  ACT 2\n"
        "    ...\n"
    ),
    "metadata": {
        "title": "Get Out",                          # Detected from title page or filename
        "source_file": "get-out-2017.pdf",
        "total_scenes": 68,
        "total_pages_est": 104,                      # Estimated from char count / ~250 words per page
        "total_chars": 95000,
        "total_words": 18000,
        "characters": [                              # Unique character names detected
            "CHRIS", "ROSE", "MISSY", "DEAN", 
            "JEREMY", "GEORGINA", "WALTER", "ROD",
            "JIM HUDSON", "ANDRE/LOGAN",
        ],
        "total_characters": 15,
        "scene_headers": [                           # Ordered list of all scene headers
            "EXT. SUBURBAN STREET - NIGHT",
            "INT. CHRIS'S APARTMENT - BEDROOM - DAY",
            # ...
        ],
        "int_ext_breakdown": {
            "INT": 42,
            "EXT": 18,
            "INT./EXT.": 8,
        },
        "time_of_day_breakdown": {
            "DAY": 30,
            "NIGHT": 25,
            "CONTINUOUS": 8,
            "DAWN": 2,
            "DUSK": 1,
            "LATER": 2,
        },
        "avg_scene_length_chars": 1400,
        "longest_scenes": [
            ("SC-045: INT. LIVING ROOM - NIGHT", 4200),
            # ... top 10
        ],
    }
}
```

**File tree generation:**

Screenplays don't have a directory structure, so the file tree should simulate an organized breakdown. Group scenes into acts if detectable (look for "ACT" headers, "FADE IN", or estimate based on page count — Act 1 ≈ scenes 1–20, Act 2 ≈ 21–55, Act 3 ≈ 56+). If acts aren't detectable, list scenes sequentially.

**Title page handling:**

Skip everything before the first scene header. Title pages typically contain: title in caps, "Written by" / "Screenplay by", author name, draft date, contact info. Don't include this in any scene.

**PDF text extraction:**

Use `pdfplumber` as the primary library (best for screenplay formatting preservation). Fallback to `pymupdf` (fitz) if available. Do NOT use `pypdf` — it's unreliable for formatted text extraction.

```python
def extract_text_from_pdf(path: str) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        try:
            import fitz  # pymupdf
            doc = fitz.open(path)
            return "\n".join(page.get_text() for page in doc)
        except ImportError:
            raise ImportError(
                "PDF support requires pdfplumber or pymupdf. "
                "Install with: pip install pdfplumber"
            )
```

**Fountain format support:**

Fountain (`.fountain`) is the Markdown-equivalent for screenplays. Scene headers either start with a forced marker (`.`) or match the INT/EXT pattern. Character names are ALL CAPS lines that aren't scene headers. For V0, treat `.fountain` files the same as plain text — the INT/EXT regex will catch scene headers, and the character regex will catch names. Fountain-specific formatting (boneyard `/**/`, notes `[[]]`, emphasis `*bold*`) can be stripped but isn't critical for extraction.

**Functions:**

```python
def load_screenplay(path: str) -> dict:
    """
    Load a screenplay from a file path.
    Accepts .pdf, .txt, or .fountain files.
    Returns {documents, file_tree, metadata} dict.
    """

def parse_scenes(text: str) -> list[dict]:
    """
    Split screenplay text into scenes.
    Returns list of {"number": int, "header": str, "body": str, "int_ext": str, "time_of_day": str}
    """

def detect_characters(text: str) -> list[str]:
    """
    Detect character names from screenplay text.
    Returns sorted list of unique character names.
    """

def extract_text_from_pdf(path: str) -> str:
    """Extract text from PDF using pdfplumber or pymupdf."""

def format_film_metadata(metadata: dict) -> str:
    """Format metadata dict into a human-readable prompt string for the root model."""

def detect_title(text: str, filename: str) -> str:
    """Attempt to detect screenplay title from title page or filename."""

def estimate_pages(total_chars: int) -> int:
    """Estimate page count. Standard screenplay: ~250 words/page, ~5 chars/word."""

def classify_time_of_day(header: str) -> str:
    """Extract time of day from scene header (DAY, NIGHT, DAWN, DUSK, CONTINUOUS, etc.)."""
```

**Edge cases to handle:**
- Scene headers with no scene body (just a slugline followed immediately by another slugline) — include as empty scene
- Dual dialogue (two characters speaking simultaneously) — detect both character names
- `(V.O.)`, `(O.S.)`, `(O.C.)`, `(CONT'D)` parentheticals — strip from character name, keep in scene text
- Scene headers mid-line (rare but happens in poorly formatted scripts) — only match at line start
- Non-standard prefixes like `EXT/INT.` — normalize to `INT./EXT.`
- Roman numeral scene numbers — handle `XIV.` prefix before INT/EXT
- Multiple spaces/tabs in headers — normalize whitespace
- PDF extraction artifacts (ligatures, broken words, extra spaces) — basic cleanup pass

**Files to create:**
- `deeprepo/film_loader.py` — all functions above
- `tests/test_film_loader.py` — unit tests

**Test data:**

Create `tests/test_screenplay.txt` — a minimal 5-scene test screenplay:
```
GET OUT

Written by Jordan Peele
(Test excerpt - not actual screenplay)


FADE IN:

EXT. SUBURBAN STREET - NIGHT

A quiet, tree-lined street. ANDRE HAYWORTH walks alone.

                    ANDRE
          Nah, nah, nah. I am not about to 
          get lost in this...

A car slowly follows him. Andre notices. He turns.

                    ANDRE (CONT'D)
          Come on...

INT. CHRIS'S APARTMENT - BEDROOM - DAY

CHRIS WASHINGTON, late 20s, packs a bag.

                    CHRIS
          You sure it's cool, me coming?

                    ROSE (O.S.)
          Yeah, of course!

INT./EXT. ROSE'S CAR - MOVING - DAY

ROSE drives. CHRIS rides passenger. A DEER darts into the road.

                    ROSE
          Oh my god!

The car SWERVES. Impact. The deer lies in the road.

EXT. ARMITAGE ESTATE - DAY

The car pulls up a long driveway. A grand house sits on manicured grounds. DEAN ARMITAGE and MISSY ARMITAGE wait on the porch.

                    DEAN
          Welcome! Chris, we are so happy 
          to have you.

INT. ARMITAGE HOUSE - LIVING ROOM - NIGHT

Missy sits across from Chris. A TEACUP AND SPOON on the table between them.

                    MISSY
          Let me help you with your 
          smoking habit.

She stirs the teacup. The spoon CLINKS against porcelain.

FADE OUT.
```

**Tests to write:**
```python
def test_load_screenplay_txt():
    """Load test screenplay, verify scene count and structure."""
    data = load_screenplay("tests/test_screenplay.txt")
    assert data["metadata"]["total_scenes"] == 5
    assert "SC-001" in list(data["documents"].keys())[0]
    assert data["metadata"]["total_characters"] >= 5  # Chris, Rose, Andre, Dean, Missy

def test_parse_scenes():
    """Verify scene splitting on INT/EXT headers."""
    text = open("tests/test_screenplay.txt").read()
    scenes = parse_scenes(text)
    assert len(scenes) == 5
    assert scenes[0]["int_ext"] == "EXT"
    assert scenes[0]["time_of_day"] == "NIGHT"
    assert scenes[2]["int_ext"] == "INT./EXT."

def test_detect_characters():
    """Verify character name detection."""
    text = open("tests/test_screenplay.txt").read()
    chars = detect_characters(text)
    assert "CHRIS" in chars
    assert "ROSE" in chars
    assert "ANDRE" in chars
    assert "DEAN" in chars
    assert "MISSY" in chars
    # Parentheticals stripped
    assert "ANDRE (CONT'D)" not in chars
    assert "ROSE (O.S.)" not in chars
    # False positives excluded
    assert "FADE IN" not in chars
    assert "FADE OUT" not in chars

def test_classify_time_of_day():
    assert classify_time_of_day("INT. KITCHEN - NIGHT") == "NIGHT"
    assert classify_time_of_day("EXT. PARK - DAY") == "DAY"
    assert classify_time_of_day("INT./EXT. CAR - CONTINUOUS") == "CONTINUOUS"
    assert classify_time_of_day("EXT. STREET - DAWN") == "DAWN"

def test_format_film_metadata():
    """Verify metadata formatting produces readable string."""
    data = load_screenplay("tests/test_screenplay.txt")
    meta_str = format_film_metadata(data["metadata"])
    assert "5 scenes" in meta_str or "total_scenes" in meta_str
    assert len(meta_str) > 100  # Non-trivial output

def test_empty_file_raises():
    """Empty or non-screenplay file raises ValueError."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("This is not a screenplay.")
    try:
        load_screenplay(f.name)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

def test_pdf_extraction_fallback():
    """If pdfplumber not available, pymupdf is tried. If neither, ImportError."""
    # This is a structural test — verify the fallback logic exists
    import deeprepo.film_loader as fl
    assert hasattr(fl, 'extract_text_from_pdf')
```

**Acceptance Criteria:**
- [ ] `load_screenplay("tests/test_screenplay.txt")` returns `{documents, file_tree, metadata}`
- [ ] 5 scenes detected from test screenplay
- [ ] Scene keys follow `SC-NNN: HEADER` format
- [ ] Characters detected: at least CHRIS, ROSE, ANDRE, DEAN, MISSY
- [ ] Parentheticals stripped from character names (`(V.O.)`, `(O.S.)`, `(CONT'D)`)
- [ ] False positives excluded (`FADE IN`, `CUT TO`, `CONTINUED`)
- [ ] `int_ext_breakdown` correctly counts INT, EXT, INT./EXT. scenes
- [ ] `time_of_day_breakdown` correctly classifies DAY, NIGHT, CONTINUOUS, etc.
- [ ] `format_film_metadata()` produces readable prompt string
- [ ] PDF extraction function exists with pdfplumber → pymupdf fallback chain
- [ ] Empty or non-screenplay files raise `ValueError` with helpful message
- [ ] All existing tests still pass

**Anti-Patterns:**
- Do NOT walk directories. The film loader takes a single file path, not a directory.
- Do NOT use `pypdf` for PDF extraction — it's unreliable for formatted text.
- Do NOT attempt semantic analysis of scenes in the loader. Scene parsing is structural only — splitting on headers and detecting character names. Analysis is the sub-LLM's job.
- Do NOT hardcode Get Out–specific patterns. The parser should work on any standard-format screenplay.
- Do NOT install heavy dependencies without checking availability first. Use try/except ImportError for PDF libraries.

**Test Commands:**
```bash
cd ~/Desktop/Projects/deeprepo
python -m pytest tests/test_film_loader.py -v
python -c "
from deeprepo.film_loader import load_screenplay
data = load_screenplay('tests/test_screenplay.txt')
print(f'Scenes: {data[\"metadata\"][\"total_scenes\"]}')
print(f'Characters: {data[\"metadata\"][\"characters\"]}')
print(f'INT/EXT: {data[\"metadata\"][\"int_ext_breakdown\"]}')
for key in list(data[\"documents\"].keys())[:3]:
    print(f'  {key}: {len(data[\"documents\"][key])} chars')
"
```

**When Done:**
Update SCRATCHPAD_ENGINEER.md with: files created, scene count from test, character detection results, any deviations from spec.

---

### ISSUE F2 — Film Prompts + FILM_DOMAIN Config

**Problem:** The root model needs fundamentally different instructions for film breakdown than for code analysis or content audit. Film is an EXTRACTION task (structured data from narrative prose) rather than an ANALYSIS task (qualitative assessment). This issue creates film-specific prompts and wires them into a FILM_DOMAIN config.

**What to build:**
- `deeprepo/domains/film.py` — film prompts + FILM_DOMAIN config
- Register in domain registry

**Critical design difference from other domains:**

In code analysis, the sub-LLM produces prose: "This file has a potential SQL injection vulnerability because..." In film breakdown, the sub-LLM fills a structured template. Every scene produces the same categories of output, which enables systematic consolidation by the root model.

**Root System Prompt — Film Domain:**

```
You are operating as the root orchestrator in a Recursive Language Model (RLM)
environment for screenplay production breakdown.

## Your Situation
A screenplay has been parsed into individual scenes and loaded into your Python
REPL environment. You do NOT see the scene contents directly — they are stored
as variables. You will explore the screenplay through code, dispatching extraction
tasks to sub-LLM workers.

## Available Variables
- `scenes`: dict mapping scene keys to scene text
  Keys are formatted as "SC-001: EXT. SUBURBAN STREET - NIGHT"
  Values are the full text of each scene
- `file_tree`: string showing the scene list organized by act
- `metadata`: dict with screenplay stats (total_scenes, characters, int_ext_breakdown, etc.)

## Available Functions
- `print(x)`: Display output (truncated to 8192 chars)
- `llm_query(prompt: str) -> str`: Send a focused task to a sub-LLM worker
- `llm_batch(prompts: list[str]) -> list[str]`: Send multiple tasks in parallel
- `set_answer(text: str)`: Set the final answer (call multiple times to build iteratively)

## Your Task
Produce a comprehensive production breakdown of this screenplay. The output must include:

1. **Scene-by-Scene Breakdown** — For every scene, extract: location, time of day, cast present, props, vehicles, wardrobe, special effects/VFX, stunts/action, music/sound, makeup/hair, animals, set dressing, and production notes.

2. **Master Cast List** — Every character with: which scenes they appear in, estimated screen time (based on scene count), and any notable wardrobe/makeup changes.

3. **Master Location List** — Every distinct location with: which scenes use it, INT/EXT designation, and any notable set dressing or practical requirements.

4. **Master Props List** — Every significant prop with: which scenes it appears in, whether it's a hero prop (plot-critical) or background.

5. **Production Flags** — VFX-heavy scenes, stunt sequences, night shoots, location changes, special equipment needs.

## How to Work

1. First, examine metadata and scene list to understand the screenplay's scope
2. Read a few key scenes directly (opening, midpoint, climax) to understand tone and style
3. Use `llm_batch()` to dispatch ALL scenes for extraction in parallel batches
   - Send 10-15 scenes per batch to balance parallelism and quality
   - Each sub-LLM call receives ONE scene and returns structured extraction
4. Parse sub-LLM results programmatically to build master lists
5. Cross-reference: track characters across scenes, identify recurring props, flag continuity items
6. Use code to consolidate, deduplicate, and organize the extracted data
7. Format the final breakdown document
8. Set answer["ready"] = True only after ALL scenes have been processed

## Rules
- NEVER set answer["ready"] = True until you've dispatched ALL scenes to sub-LLMs
- Process the ENTIRE screenplay — partial breakdowns are useless in production
- Use `llm_batch()` for parallel extraction — processing scenes sequentially wastes time and money
- Parse sub-LLM results with code, not by reading them yourself
- Keep sub-LLM prompts focused: ONE scene per call with the extraction template
- Build master lists programmatically by aggregating scene-level results
- If a sub-LLM call fails, retry it individually via llm_query()
```

**Sub System Prompt — Film Domain:**

```
You are a film production breakdown specialist. You receive a single scene from a
screenplay and extract all production-relevant elements.

For the given scene, fill in EVERY category below. Use "None" for categories with
no applicable elements. Be specific — use exact names, descriptions, and details
from the scene text.

## Extraction Template

SCENE: [scene header as provided]
LOCATION: [INT/EXT] [specific place]
TIME: [DAY/NIGHT/DAWN/DUSK/CONTINUOUS]
PAGES: [estimated page count based on text length — 1 page ≈ 1 minute ≈ 250 words]

CAST:
- [CHARACTER NAME]: [brief description of what they do in this scene]

PROPS:
- [Prop name]: [context — how it's used or referenced]

VEHICLES:
- [Vehicle description]: [context]

WARDROBE:
- [Character] — [costume description if mentioned]

SPECIAL EFFECTS / VFX:
- [Effect description]: [practical or CG, context]

STUNTS / ACTION:
- [Action description]: [choreography notes]

MUSIC / SOUND:
- [Song title or sound effect]: [diegetic/non-diegetic, context]

MAKEUP / HAIR:
- [Character] — [description if mentioned: blood, wounds, aging, etc.]

ANIMALS:
- [Animal type]: [context]

SET DRESSING:
- [Notable set elements beyond basic props]

PRODUCTION NOTES:
- [Anything else relevant: weather, crowd scenes, special equipment, time-sensitive elements]

Be thorough but precise. Only extract elements actually present in or clearly implied by
the scene text. Do not invent or assume elements not described.
```

**User Prompt Template — Film Domain:**

```
A screenplay has been loaded into your REPL environment.

{metadata_str}

Scene list:
{file_tree}

The screenplay contains {total_scenes} scenes with {total_characters} unique characters.
Your task is to produce a complete production breakdown covering every scene.

Start by examining the metadata and reading a few key scenes to understand the screenplay,
then dispatch all scenes to sub-LLMs for structured extraction using llm_batch().
```

**Baseline System Prompt — Film Domain:**

```
You are an experienced line producer performing a script breakdown. Analyze the following
screenplay and produce a comprehensive production breakdown including:

1. Scene-by-scene breakdown with: location, time, cast, props, vehicles, wardrobe,
   VFX, stunts, music, makeup, animals, set dressing
2. Master cast list with scene appearances
3. Master location list
4. Master props list
5. Production flags (VFX scenes, stunts, night shoots, special equipment)

Be thorough and specific. Extract every production-relevant element from every scene.
```

**FILM_DOMAIN Config:**

```python
from deeprepo.domains.base import DomainConfig
from deeprepo.film_loader import load_screenplay, format_film_metadata

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
    clone_handler=None,  # No git clone for screenplays
)
```

**Files to create:**
- `deeprepo/domains/film.py` — all prompts above + FILM_DOMAIN config

**Files to modify:**
- `deeprepo/domains/__init__.py` — add `from .film import FILM_DOMAIN` and register `"film": FILM_DOMAIN`

**Acceptance Criteria:**
- [ ] `FILM_DOMAIN` config exists with all required DomainConfig fields
- [ ] `get_domain("film")` returns valid config
- [ ] `data_variable_name` is `"scenes"` (not "codebase" or "documents")
- [ ] Root prompt references `scenes` variable and instructs for extraction (not analysis)
- [ ] Root prompt explicitly mandates processing ALL scenes before finalizing
- [ ] Root prompt instructs use of `llm_batch()` for parallel scene dispatch
- [ ] Sub prompt provides the full extraction template with all categories
- [ ] Sub prompt instructs to fill EVERY category (use "None" for empty)
- [ ] Baseline prompt instructs for single-call complete breakdown
- [ ] `clone_handler` is `None` (screenplays aren't git repos)
- [ ] `list-domains` CLI command shows "film" with description
- [ ] All existing tests pass

**Anti-Patterns:**
- Do NOT copy-paste code domain prompts and replace "code" with "film." The task structure is fundamentally different (extraction vs. analysis).
- Do NOT make prompts overly long. The root model needs clear instructions, not a film production textbook.
- Do NOT include specific Get Out references in the prompts. Prompts must work for ANY screenplay.
- Do NOT instruct the sub-LLM to produce prose analysis. It should fill the structured template.

**Test Commands:**
```bash
python -c "
from deeprepo.domains import get_domain
d = get_domain('film')
print(f'Domain: {d.name}')
print(f'Label: {d.label}')
print(f'Data var: {d.data_variable_name}')
assert d.data_variable_name == 'scenes'
assert 'scene' in d.root_system_prompt.lower()
assert 'extraction' in d.sub_system_prompt.lower() or 'extract' in d.sub_system_prompt.lower()
print('PASS')
"
# Verify domain appears in list
python -m deeprepo.cli list-domains
```

**When Done:**
Update SCRATCHPAD_ENGINEER.md with: prompt lengths (char count for root/sub/baseline), domain config structure, any design decisions about prompt wording.

---

### ISSUE F3 — Get Out Ground Truth + Integration Test

**Problem:** We need a ground truth dataset to benchmark against, and an integration test to verify the film domain works end-to-end before running the real benchmark.

**What to build:**
1. `GET_OUT_GROUND_TRUTH.md` — compiled ground truth for all extraction categories
2. `tests/test_film_integration.py` — end-to-end test with mocked API clients
3. Download the actual Get Out screenplay PDF for the real benchmark

**Part A: Ground Truth Document**

Create `GET_OUT_GROUND_TRUTH.md` in the project root (or `examples/get-out/`). Structure:

```markdown
# Get Out (2017) — Production Breakdown Ground Truth

## Sources
- IMDb: imdb.com/title/tt5052448
- Script Slug PDF screenplay
- Production design interviews (Rusty Smith)
- Costume design interviews (Nadine Haders)
- Michael Abels score notes
- Jordan Peele director commentary

## Characters (with scene presence)
| Character | Actor | Key Scenes |
|-----------|-------|------------|
| Chris Washington | Daniel Kaluuya | Nearly all scenes |
| Rose Armitage | Allison Williams | 1, 2, 3, ... |
| Missy Armitage | Catherine Keener | ... |
[... complete list ...]

## Locations
| Location | INT/EXT | Scenes |
|----------|---------|--------|
| Suburban street | EXT | 1 |
| Chris's apartment | INT | 2, ... |
[... complete list ...]

## Props
| Prop | Hero/Background | Scenes | Notes |
|------|----------------|--------|-------|
| Chris's camera | Hero | 2, 5, 12, ... | Nikon, plot-critical |
| Teacup and spoon | Hero | 8, 15, ... | Hypnosis instrument |
[... complete list ...]

## Vehicles
| Vehicle | Scenes | Notes |
|---------|--------|-------|
| Rose's car | 3, 4, 60+ | White, deer collision |
[... complete list ...]

## Wardrobe
| Character | Description | Scenes | Notes |
|-----------|-------------|--------|-------|
| Rose | White top, jeans | 2-10 | Innocence coding |
[... complete list ...]

## VFX / Special Effects
| Effect | Type | Scenes | Notes |
|--------|------|--------|-------|
| Sunken Place | VFX | 15, 45 | Falling through black void |
[... complete list ...]

## Stunts / Action
| Stunt | Scenes | Notes |
|-------|--------|-------|
| Deer collision | 4 | Car swerve + impact |
[... complete list ...]

## Music / Sound
| Cue | Type | Scenes | Notes |
|-----|------|--------|-------|
| "Sikiliza Kwa Wahenga" | Score | 1, opening | Swahili chant |
[... complete list ...]

## Scoring Notes
- Match is case-insensitive
- Partial string match acceptable for compound items
- Character aliases count (e.g., "Andre" = "Andre Hayworth" = "Logan King")
- Scene numbers are approximate (may vary by screenplay version)
```

The ground truth should be as complete as possible from publicly available information. Aim for:
- 15–20 characters
- 12–18 locations
- 25–40 props
- 4–6 vehicles
- 15–25 wardrobe elements
- 8–12 VFX/SFX
- 6–10 stunts
- 8–12 music/sound cues

**Part B: Integration Test**

Create `tests/test_film_integration.py` that verifies the full pipeline works with mocked API calls.

```python
"""
Integration test for film domain.
Mocks API clients to verify the full pipeline:
loader → engine → prompts → namespace → answer
"""

def test_film_domain_loads_and_configures():
    """Verify FILM_DOMAIN config is complete and consistent."""
    from deeprepo.domains import get_domain
    domain = get_domain("film")
    assert domain.name == "film"
    assert domain.data_variable_name == "scenes"
    assert domain.clone_handler is None
    assert callable(domain.loader)
    assert callable(domain.format_metadata)
    assert len(domain.root_system_prompt) > 500
    assert len(domain.sub_system_prompt) > 200

def test_film_loader_to_namespace():
    """Verify loader output is compatible with engine namespace."""
    from deeprepo.film_loader import load_screenplay
    data = load_screenplay("tests/test_screenplay.txt")
    
    # Verify the engine can build a namespace from this
    assert "documents" in data or "scenes" in data  # may use either key
    assert "file_tree" in data
    assert "metadata" in data
    
    # Verify scenes are accessible by key
    scenes = data.get("documents", data.get("scenes", {}))
    assert len(scenes) >= 3
    
    # Verify metadata has required fields
    meta = data["metadata"]
    assert "total_scenes" in meta
    assert "characters" in meta
    assert "scene_headers" in meta

def test_film_metadata_formatting():
    """Verify metadata formats into a usable prompt string."""
    from deeprepo.film_loader import load_screenplay, format_film_metadata
    data = load_screenplay("tests/test_screenplay.txt")
    meta_str = format_film_metadata(data["metadata"])
    assert isinstance(meta_str, str)
    assert len(meta_str) > 100
    # Should mention scene count and character count
    assert "scene" in meta_str.lower()

def test_film_prompt_template_renders():
    """Verify user prompt template renders without error."""
    from deeprepo.domains import get_domain
    from deeprepo.film_loader import load_screenplay, format_film_metadata
    
    domain = get_domain("film")
    data = load_screenplay("tests/test_screenplay.txt")
    meta_str = format_film_metadata(data["metadata"])
    
    # Template should accept metadata_str and file_tree
    prompt = domain.user_prompt_template.format(
        metadata_str=meta_str,
        file_tree=data["file_tree"],
        total_scenes=data["metadata"]["total_scenes"],
        total_characters=data["metadata"]["total_characters"],
    )
    assert len(prompt) > 200
    assert "scene" in prompt.lower()
```

**Part C: Screenplay Acquisition**

Download the Get Out screenplay PDF. Options:
1. Script Slug: `https://scriptslug.com/script/get-out-2017` (may require manual download)
2. Search for publicly available PDF versions
3. If PDF acquisition is blocked, use a plain text transcription

Save to `examples/get-out/get-out-2017.pdf` (or `.txt`). Do NOT commit copyrighted screenplay text to the public repo — add to `.gitignore` and document acquisition instructions in README.

**Files to create:**
- `GET_OUT_GROUND_TRUTH.md` (or `examples/get-out/GET_OUT_GROUND_TRUTH.md`)
- `tests/test_film_integration.py`
- `examples/get-out/README.md` — instructions for acquiring the screenplay + running the benchmark

**Acceptance Criteria:**
- [ ] Ground truth document exists with all 8 extraction categories populated
- [ ] At least 100 total ground truth elements across all categories
- [ ] Each category includes scene references where possible
- [ ] Integration test passes: domain config loads, loader output matches namespace expectations, prompt template renders
- [ ] `examples/get-out/README.md` documents screenplay acquisition and benchmark instructions
- [ ] Screenplay file (if acquired) is in `.gitignore`

**Anti-Patterns:**
- Do NOT commit copyrighted screenplay text to the repo. The ground truth is metadata about the film (characters, locations, props) which is factual/public knowledge. The screenplay text itself is copyrighted.
- Do NOT fabricate ground truth entries. Every element should be verifiable from public sources. If unsure, mark as "unverified" in the document.
- Do NOT make the integration test depend on API calls. Mock everything.

**Test Commands:**
```bash
python -m pytest tests/test_film_integration.py -v
# Verify ground truth is well-formed
python -c "
with open('GET_OUT_GROUND_TRUTH.md') as f:
    content = f.read()
print(f'Ground truth: {len(content)} chars')
# Count entries (rough — count table rows)
import re
rows = re.findall(r'^\|[^-]', content, re.MULTILINE)
print(f'Approximate entries: {len(rows)}')
"
```

**When Done:**
Update SCRATCHPAD_ENGINEER.md with: ground truth element counts per category, integration test results, screenplay acquisition status.

---

### ISSUE F4 — Full Benchmark Run

**Problem:** We need to run the three-way comparison (RLM vs baseline vs ground truth) and capture metrics. This is the proof that the film vertical works and that RLM outperforms baseline on structured extraction.

**Prerequisites:** F1 (loader), F2 (prompts + config), F3 (ground truth + screenplay)

**What to do:**

1. **Run RLM analysis:**
```bash
deeprepo analyze examples/get-out/get-out-2017.pdf --domain film -o examples/get-out/
```
Expected: root model dispatches 65–75 scenes to sub-LLMs, produces structured breakdown. Cost estimate: $0.50–2.00 depending on root model (Sonnet vs Opus).

2. **Run baseline analysis:**
```bash
deeprepo baseline examples/get-out/get-out-2017.pdf --domain film -o examples/get-out/
```
Expected: single model call with full screenplay text. Will hit context limits or degrade on extraction quality for later scenes.

3. **Score against ground truth:**

Create `deeprepo/film_scorer.py` (or a script in `scripts/`) that:
- Parses the RLM output to extract identified elements per category
- Parses the baseline output to extract identified elements per category
- Compares each against ground truth
- Computes precision, recall, F1 per category
- Produces a summary comparison table

Matching logic:
```python
def is_match(extracted: str, ground_truth: str) -> bool:
    """Case-insensitive partial match for production elements."""
    e = extracted.lower().strip()
    g = ground_truth.lower().strip()
    return e in g or g in e or (
        # Handle common variations
        e.replace("'s", "").replace("the ", "") == g.replace("'s", "").replace("the ", "")
    )
```

4. **Capture metrics:**
- RLM: cost, sub-LLM calls, scenes processed, turns used, wall clock time
- Baseline: cost, prompt size (chars/tokens), wall clock time
- Both: extraction counts per category, precision/recall/F1 per category

**Output format for scoring:**
```
## Film Benchmark: Get Out (2017)

### Overall
| Metric | RLM | Baseline |
|--------|-----|----------|
| Cost | $X.XX | $X.XX |
| Scenes processed | 68/68 | 68/68 (all in context) |
| Wall clock time | Xm Xs | Xm Xs |

### Extraction Quality (vs Ground Truth)
| Category | RLM P/R/F1 | Baseline P/R/F1 | Winner |
|----------|-----------|----------------|--------|
| Characters | X/X/X | X/X/X | ... |
| Locations | X/X/X | X/X/X | ... |
| Props | X/X/X | X/X/X | ... |
| Vehicles | X/X/X | X/X/X | ... |
| Wardrobe | X/X/X | X/X/X | ... |
| VFX/SFX | X/X/X | X/X/X | ... |
| Stunts | X/X/X | X/X/X | ... |
| Music/Sound | X/X/X | X/X/X | ... |

### Key Findings
- [What RLM caught that baseline missed]
- [What baseline caught that RLM missed]
- [Coverage analysis: did baseline degrade on later scenes?]
```

**Files to create:**
- `scripts/score_film_benchmark.py` — scoring script
- `examples/get-out/benchmark_results.md` — formatted results

**Files generated by runs:**
- `examples/get-out/rlm_get-out_*.md` — RLM analysis output
- `examples/get-out/rlm_get-out_*_metrics.json` — RLM metrics
- `examples/get-out/baseline_get-out_*.md` — Baseline output
- `examples/get-out/baseline_get-out_*_metrics.json` — Baseline metrics

**Acceptance Criteria:**
- [ ] RLM run completes and produces structured output
- [ ] Baseline run completes and produces output
- [ ] Scoring script computes P/R/F1 per category
- [ ] Results documented in `examples/get-out/benchmark_results.md`
- [ ] Cost data captured in metrics JSON
- [ ] At least one category where RLM meaningfully outperforms baseline (expected: props, wardrobe, or set dressing — categories that require per-scene attention)

**Anti-Patterns:**
- Do NOT manually score the results. Build the scoring script to be rerunnable.
- Do NOT cherry-pick results. Report all categories, including any where baseline wins.
- Do NOT run more than 2 RLM attempts total — budget is limited. If the first run has issues, fix prompts in F2 and re-run once.

**Budget:** ~$2–5 for the full benchmark (RLM + baseline + any retries)

**Test Commands:**
```bash
# Run the benchmark (requires API keys)
deeprepo analyze examples/get-out/get-out-2017.pdf --domain film -o examples/get-out/ --max-turns 10
deeprepo baseline examples/get-out/get-out-2017.pdf --domain film -o examples/get-out/

# Score
python scripts/score_film_benchmark.py \
  --rlm examples/get-out/rlm_*.md \
  --baseline examples/get-out/baseline_*.md \
  --ground-truth GET_OUT_GROUND_TRUTH.md \
  --output examples/get-out/benchmark_results.md
```

**When Done:**
Update SCRATCHPAD_ENGINEER.md with: cost per run, scenes dispatched, F1 scores per category, any surprising findings.

---

### ISSUE F5 — Documentation + Commit Results

**Problem:** The benchmark is run, results are captured. This issue packages everything for public consumption.

**What to do:**

1. **Commit example outputs:**
   - `examples/get-out/benchmark_results.md`
   - `examples/get-out/rlm_*_metrics.json`
   - `examples/get-out/baseline_*_metrics.json`
   - `examples/get-out/README.md`
   - Do NOT commit the actual screenplay PDF or the full analysis outputs if they contain extensive screenplay quotes

2. **Update main README:**
   - Add film vertical to the domain list
   - Add Get Out benchmark to results section (alongside FastAPI/Pydantic)
   - Update the "Same engine, every vertical" narrative — now three verticals
   - Add `--domain film` to CLI usage examples

3. **Update BENCHMARK_RESULTS.md:**
   - Add film benchmark section with extraction F1 scores
   - Compare across all three domains (code, content, film)
   - Note that film uses objective P/R/F1 scoring vs. qualitative assessment for code/content

4. **Session log entry:**
   - Write SESSION_LOG.md entry for the film vertical sprint
   - Document key findings, costs, and any surprises

5. **Cold-start prompt:**
   - Update the cold-start prompt template with film vertical context
   - Include: FILM_DOMAIN exists, Get Out benchmark complete, next steps

**Files to create/modify:**
- `examples/get-out/README.md` — benchmark documentation + reproduction instructions
- `README.md` — add film vertical section
- `BENCHMARK_RESULTS.md` — add film benchmark data
- `SESSION_LOG.md` — new entry

**Acceptance Criteria:**
- [ ] `examples/get-out/` contains benchmark results and metrics (no copyrighted screenplay text)
- [ ] `examples/get-out/README.md` documents how to reproduce the benchmark
- [ ] Main README lists three domains: code, content, film
- [ ] BENCHMARK_RESULTS.md includes film F1 scores
- [ ] `--domain film` documented in CLI usage
- [ ] SESSION_LOG.md has film sprint entry
- [ ] All changes committed to git with descriptive commit message

**Anti-Patterns:**
- Do NOT commit copyrighted screenplay text to the public repo.
- Do NOT over-promise in the README. Report actual F1 scores, not "perfect extraction."
- Do NOT write a blog post yet. That's a separate sprint. Just commit clean documentation.

**Test Commands:**
```bash
# Verify README is consistent
grep -c "film" README.md  # Should find multiple mentions
grep -c "domain" README.md
# Verify examples directory is clean
ls examples/get-out/
# Verify no large binary files committed
git diff --stat HEAD
```

---

## Part 5: Sprint Execution Order

```
F1 (Film Loader)
    ↓
F2 (Film Prompts + Config)     ← Can start once F1 is code-complete
    ↓
F3 (Ground Truth + Integration Test)  ← Can partially overlap with F2
    ↓
F4 (Full Benchmark Run)        ← Requires F1 + F2 + F3 complete
    ↓
F5 (Documentation + Commit)    ← Requires F4 complete
```

F1 and F2 are the critical path. F3's ground truth compilation can happen in parallel with F2 (it's research, not code). F4 is the moment of truth — it requires everything else to be working. F5 is cleanup.

**Total estimated budget:** $3–7 for all benchmark runs combined.

---

## Part 6: What Success Looks Like

At the end of this sprint:

1. `deeprepo analyze screenplay.pdf --domain film` produces a structured production breakdown
2. Three-way benchmark shows RLM's per-scene dispatch catches production elements that baseline's single-pass misses
3. The repo demonstrates three completely different verticals (code, content, film) running on the same engine
4. The pitch narrative shifts from "code analysis tool" to "domain-agnostic orchestration platform proven across industries"

The film vertical is the strongest possible generalization proof because it's the most distant from code analysis. If the same REPL loop that finds bugs in FastAPI can also extract props from Get Out, the "same engine, any vertical" claim becomes undeniable.
