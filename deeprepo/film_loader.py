"""
Film loader for screenplay-style documents.

Parses a single screenplay file (.txt, .fountain, .pdf) into scene-level units
for the deeprepo RLM engine.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

SCENE_HEADER_PATTERN = re.compile(
    r"^[ \t]*"
    r"(?:\d+[\.\s]+)?"
    r"(INT\.|EXT\.|INT\./EXT\.|INT/EXT\.|EXT/INT\.|I/E\.)"
    r"[ \t]+"
    r"(.+?)$",
    re.MULTILINE | re.IGNORECASE,
)

CHARACTER_PATTERN = re.compile(
    r"^[ \t]{10,}([A-Z][A-Z\s\.\-\']+?)(?:\s*\(.*?\))?[ \t]*$",
    re.MULTILINE,
)

ACT_LINE_PATTERN = re.compile(
    r"^[ \t]*(ACT\b[^\n]*)$",
    re.MULTILINE | re.IGNORECASE,
)

FALSE_POSITIVE_NAMES = {
    "FADE IN",
    "FADE OUT",
    "CUT TO",
    "DISSOLVE TO",
    "CONTINUED",
    "THE END",
    "SMASH CUT",
    "MATCH CUT",
    "INTERCUT",
    "TITLE CARD",
    "SUPER",
    "FR FRAME",
}

TIME_OF_DAY_VALUES = [
    "MOMENTS LATER",
    "CONTINUOUS",
    "MORNING",
    "EVENING",
    "NIGHT",
    "DAWN",
    "DUSK",
    "LATER",
    "SAME",
    "DAY",
]


def load_screenplay(path: str) -> dict:
    """
    Load a screenplay from a local file path.

    Returns:
        {
            "scenes": {scene_key: full_scene_text, ...},
            "file_tree": "scene list string organized by act",
            "metadata": {...}
        }
    """
    screenplay_path = Path(path).resolve()
    text = _read_screenplay_text(screenplay_path)

    scenes = parse_scenes(text)
    if not scenes:
        raise ValueError(
            "No screenplay scenes detected. Expected sluglines like "
            "'INT. LOCATION - DAY' or 'EXT. LOCATION - NIGHT'."
        )

    scene_map: dict[str, str] = {}
    scene_lengths: list[tuple[str, int]] = []
    scene_headers: list[str] = []

    for scene in scenes:
        scene_key = f"SC-{scene['number']:03d}: {scene['header']}"
        scene_text = scene["header"] if not scene["body"] else f"{scene['header']}\n\n{scene['body']}"
        scene_map[scene_key] = scene_text
        scene_lengths.append((scene_key, len(scene_text)))
        scene_headers.append(scene["header"])

    total_chars = sum(len(content) for content in scene_map.values())
    total_words = sum(len(content.split()) for content in scene_map.values())

    characters = detect_characters(text)
    int_ext_counts = Counter(scene["int_ext"] for scene in scenes)
    time_of_day_counts = Counter(scene["time_of_day"] for scene in scenes)
    scene_lengths.sort(key=lambda item: item[1], reverse=True)

    metadata = {
        "title": detect_title(text, screenplay_path.name),
        "source_file": screenplay_path.name,
        "total_files": 1,
        "total_scenes": len(scenes),
        "total_pages_est": estimate_pages(total_chars),
        "total_chars": total_chars,
        "total_words": total_words,
        "characters": characters,
        "total_characters": len(characters),
        "scene_headers": scene_headers,
        "int_ext_breakdown": {
            "INT": int_ext_counts.get("INT", 0),
            "EXT": int_ext_counts.get("EXT", 0),
            "INT./EXT.": int_ext_counts.get("INT./EXT.", 0),
        },
        "time_of_day_breakdown": dict(
            sorted(time_of_day_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "avg_scene_length_chars": round(total_chars / len(scenes)),
        "longest_scenes": scene_lengths[:10],
    }

    scene_starts = [match.start() for match in SCENE_HEADER_PATTERN.finditer(text)]
    file_tree = _build_scene_tree(metadata["title"], list(scene_map.keys()), scene_starts, text)

    return {
        "scenes": scene_map,
        "file_tree": file_tree,
        "metadata": metadata,
    }


def parse_scenes(text: str) -> list[dict]:
    """
    Parse screenplay text into sequential scene records.

    Returns list[dict] where each dict includes:
      - number: 1-indexed scene number
      - header: full slugline
      - body: text between this header and next header
      - int_ext: normalized INT/EXT label
      - time_of_day: time bucket from classify_time_of_day()
    """
    matches = list(SCENE_HEADER_PATTERN.finditer(text))
    if not matches:
        return []

    scenes: list[dict] = []
    for idx, match in enumerate(matches):
        int_ext = _normalize_int_ext(match.group(1))
        header_rest = _normalize_whitespace(match.group(2))
        header = _normalize_whitespace(f"{_int_ext_to_prefix(int_ext)} {header_rest}")
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()

        scenes.append(
            {
                "number": idx + 1,
                "header": header,
                "body": body,
                "int_ext": int_ext,
                "time_of_day": classify_time_of_day(header),
            }
        )

    return scenes


def detect_characters(text: str) -> list[str]:
    """Detect centered ALL-CAPS character cues and return sorted unique names."""
    characters: set[str] = set()

    for match in CHARACTER_PATTERN.finditer(text):
        raw_name = match.group(1).strip()
        name = re.sub(r"\s*\(.*?\)\s*", "", raw_name).strip()
        name = _normalize_whitespace(name).upper()

        if not name:
            continue
        if name in FALSE_POSITIVE_NAMES:
            continue
        if not any(ch.isalpha() for ch in name):
            continue

        characters.add(name)

    return sorted(characters)


def classify_time_of_day(header: str) -> str:
    """Classify scene time-of-day from the final dash-separated header segment."""
    if "-" not in header:
        return "UNKNOWN"

    final_segment = header.rsplit("-", 1)[-1].strip().upper()
    for label in TIME_OF_DAY_VALUES:
        if final_segment == label:
            return label

    return "UNKNOWN"


def extract_text_from_pdf(path: str) -> str:
    """Extract text from a PDF using pdfplumber, then pymupdf fallback."""
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        try:
            import fitz  # pymupdf

            doc = fitz.open(path)
            try:
                return "\n".join(page.get_text() for page in doc)
            finally:
                doc.close()
        except ImportError as exc:
            raise ImportError(
                "PDF support requires pdfplumber or pymupdf. "
                "Install with: pip install pdfplumber"
            ) from exc


def detect_title(text: str, filename: str) -> str:
    """Detect title from title-page block; fallback to filename-derived title."""
    pre_scene_text = text
    first_scene = SCENE_HEADER_PATTERN.search(text)
    if first_scene:
        pre_scene_text = text[: first_scene.start()]

    for line in pre_scene_text.splitlines():
        candidate = _normalize_whitespace(line.strip())
        candidate_base = candidate.rstrip(":").strip().upper()
        if len(candidate) <= 2 or len(candidate) >= 60:
            continue
        if not _is_all_caps(candidate):
            continue
        if candidate_base in FALSE_POSITIVE_NAMES:
            continue
        return candidate.rstrip(":").strip()

    stem = Path(filename).stem.replace("-", " ").replace("_", " ").strip()
    return stem.title() if stem else "Untitled Screenplay"


def estimate_pages(total_chars: int) -> int:
    """Estimate screenplay page count (roughly 1250 chars/page)."""
    return max(1, round(total_chars / 1250))


def format_film_metadata(metadata: dict) -> str:
    """Format film metadata into a concise string for model context."""
    lines = [
        f"Title: {metadata['title']}",
        f"Source file: {metadata['source_file']}",
        f"Total scenes: {metadata['total_scenes']}",
        f"Estimated pages: {metadata['total_pages_est']}",
        f"Total characters (text): {metadata['total_chars']:,}",
        f"Total words: {metadata['total_words']:,}",
        "",
        f"Characters ({metadata['total_characters']}):",
    ]

    for name in metadata["characters"]:
        lines.append(f"  {name}")

    lines.append("")
    lines.append("INT/EXT breakdown:")
    for key, count in metadata["int_ext_breakdown"].items():
        lines.append(f"  {key}: {count}")

    lines.append("")
    lines.append("Time of day breakdown:")
    for key, count in metadata["time_of_day_breakdown"].items():
        lines.append(f"  {key}: {count}")

    lines.append("")
    lines.append("Top 10 longest scenes:")
    for scene_key, char_count in metadata["longest_scenes"][:10]:
        lines.append(f"  {scene_key}: {char_count:,} chars")

    return "\n".join(lines)


def _read_screenplay_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Screenplay file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(str(path))
    if suffix in {".txt", ".fountain"}:
        return path.read_text(encoding="utf-8", errors="replace")

    raise ValueError(
        f"Unsupported screenplay file type: {path.suffix or '(none)'}; "
        "expected .txt, .fountain, or .pdf"
    )


def _build_scene_tree(title: str, scene_keys: list[str], scene_starts: list[int], text: str) -> str:
    grouped_scenes = _group_scenes_by_act(scene_keys, scene_starts, text)
    lines = [title]
    for act_label, scenes in grouped_scenes.items():
        if not scenes:
            continue
        lines.append(f"  {act_label}")
        for scene_key in scenes:
            lines.append(f"    {scene_key}")
    return "\n".join(lines)


def _group_scenes_by_act(
    scene_keys: list[str], scene_starts: list[int], text: str
) -> dict[str, list[str]]:
    act_markers = [
        (match.start(), _normalize_whitespace(match.group(1)).upper())
        for match in ACT_LINE_PATTERN.finditer(text)
    ]

    if act_markers:
        grouped: dict[str, list[str]] = {}
        for idx, scene_key in enumerate(scene_keys):
            scene_start = scene_starts[idx]
            act_label = act_markers[0][1]
            for marker_start, marker_label in act_markers:
                if marker_start <= scene_start:
                    act_label = marker_label
                else:
                    break
            grouped.setdefault(act_label, []).append(scene_key)
        return grouped

    grouped = {"ACT 1": [], "ACT 2": [], "ACT 3": []}
    total_scenes = len(scene_keys)
    act1_end = max(1, round(total_scenes * 0.25))
    act2_end = min(total_scenes, max(act1_end, round(total_scenes * 0.75)))

    for idx, scene_key in enumerate(scene_keys, start=1):
        if idx <= act1_end:
            grouped["ACT 1"].append(scene_key)
        elif idx <= act2_end:
            grouped["ACT 2"].append(scene_key)
        else:
            grouped["ACT 3"].append(scene_key)

    return grouped


def _normalize_int_ext(value: str) -> str:
    token = value.upper().replace(" ", "")
    if token in {"INT.", "INT"}:
        return "INT"
    if token in {"EXT.", "EXT"}:
        return "EXT"
    if token in {
        "INT./EXT.",
        "INT/EXT.",
        "INT./EXT",
        "INT/EXT",
        "EXT/INT.",
        "EXT/INT",
        "EXT./INT.",
        "EXT./INT",
        "I/E.",
        "I/E",
    }:
        return "INT./EXT."
    return "INT./EXT."


def _int_ext_to_prefix(int_ext: str) -> str:
    if int_ext == "INT":
        return "INT."
    if int_ext == "EXT":
        return "EXT."
    return "INT./EXT."


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_all_caps(value: str) -> bool:
    letters = [char for char in value if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)

