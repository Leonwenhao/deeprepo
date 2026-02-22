#!/usr/bin/env python3
"""
Score film benchmark outputs against ground truth.

Reads RLM and baseline analysis outputs, extracts identified production
elements per category, and scores against the ground truth dataset.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from glob import glob


# Ground truth extraction categories and their section headers in GET_OUT_GROUND_TRUTH.md
CATEGORIES = {
    "characters": "Complete Cast",
    "props": "Complete Props Master List",
    "vehicles": "Vehicles",
    "locations": "Locations",
    "wardrobe": "Wardrobe Summary",
    "vfx": "Special Effects",
    "music": "Music / Sound",
    "stunts": None,  # Stunts are embedded in scene-level records, not a consolidated table
}


def parse_ground_truth(path: str) -> dict[str, list[str]]:
    """
    Parse GET_OUT_GROUND_TRUTH.md and extract ground truth items per category.

    Focuses on Part 3 (Consolidated Production Element Lists), with stunts
    additionally collected from scene-level records throughout the document.
    """
    text = Path(path).read_text(encoding="utf-8")
    part3 = _extract_part3(text)

    ground_truth = {}
    ground_truth["characters"] = _extract_table_column(
        part3,
        "3A: Complete Cast",
        col_index=0,
        stop_section="3B: Complete Props Master List",
    )
    ground_truth["props"] = _extract_numbered_items(
        part3,
        "3B: Complete Props Master List",
        stop_section="3C: Vehicles",
    )
    ground_truth["vehicles"] = _extract_table_column(
        part3,
        "3C: Vehicles",
        col_index=0,
        stop_section="3D: Locations",
    )
    ground_truth["locations"] = _extract_table_column(
        part3,
        "3D: Locations",
        col_index=0,
        stop_section="3E: Wardrobe Summary",
    )
    ground_truth["wardrobe"] = _extract_wardrobe_items(
        part3,
        "3E: Wardrobe Summary",
        stop_section="3F: Special Effects / VFX",
    )
    ground_truth["vfx"] = _extract_table_column(
        part3,
        "3F: Special Effects / VFX",
        col_index=0,
        stop_section="3G: Music / Sound Design",
    )
    ground_truth["music"] = _extract_table_column(
        part3,
        "3G: Music / Sound Design",
        col_index=0,
        stop_section=None,
    )
    ground_truth["stunts"] = _extract_stunt_items(text)

    for category, items in ground_truth.items():
        ground_truth[category] = _dedupe_preserve_order(items)

    return ground_truth


def _extract_part3(text: str) -> str:
    lines = text.splitlines()
    start = None
    end = len(lines)

    for idx, line in enumerate(lines):
        if line.strip().lower().startswith("## part 3:"):
            start = idx + 1
            break

    if start is None:
        return text

    for idx in range(start, len(lines)):
        if lines[idx].strip().lower().startswith("## part 4:"):
            end = idx
            break

    return "\n".join(lines[start:end])


def _extract_table_column(
    text: str,
    section_header: str,
    col_index: int = 0,
    stop_section: str | None = None,
) -> list[str]:
    """Extract values from a specific column of a markdown table under a section."""
    items: list[str] = []
    lines = text.splitlines()
    in_section = False
    in_table = False

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if not in_section and section_header.lower() in lower and stripped.startswith("###"):
            in_section = True
            continue

        if in_section and stop_section and stop_section.lower() in lower and stripped.startswith("###"):
            break

        if not in_section:
            continue

        if stripped.startswith("|"):
            in_table = True
            cols = [c.strip() for c in stripped.split("|") if c.strip()]
            if not cols:
                continue

            # Skip markdown separator rows like |---|---|
            if all(re.fullmatch(r"[:\- ]+", c) for c in cols):
                continue

            if len(cols) <= col_index:
                continue

            val = cols[col_index].strip()
            header_like = {
                "character",
                "actor",
                "vehicle",
                "owner/driver",
                "script location",
                "int/ext",
                "effect",
                "element",
            }
            if val.lower() in header_like:
                continue
            if val:
                items.append(val)
            continue

        # Exit table if we were in one and reached next section-like header.
        if in_table and stripped.startswith("###"):
            break

    return items


def _extract_numbered_items(text: str, start_section: str, stop_section: str) -> list[str]:
    """Extract numbered list items between two section headers."""
    items: list[str] = []
    in_section = False

    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()

        if not in_section and start_section.lower() in lower and stripped.startswith("###"):
            in_section = True
            continue

        if in_section and stop_section.lower() in lower and stripped.startswith("###"):
            break

        if not in_section:
            continue

        match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if not match:
            continue

        item = match.group(1).strip()
        item = re.split(r"\s+[—-]\s+", item, maxsplit=1)[0].strip()
        if item:
            items.append(item)

    return items


def _extract_wardrobe_items(text: str, start_section: str, stop_section: str) -> list[str]:
    """Extract wardrobe bullet items from the wardrobe summary section."""
    items: list[str] = []
    in_section = False

    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()

        if not in_section and start_section.lower() in lower and stripped.startswith("###"):
            in_section = True
            continue

        if in_section and stop_section.lower() in lower and stripped.startswith("###"):
            break

        if not in_section:
            continue

        if stripped.startswith("- "):
            item = stripped[2:].strip()
            item = re.sub(r"\s*\([^)]*\)\s*$", "", item).strip()
            if item:
                items.append(item)

    return items


def _extract_stunt_items(text: str) -> list[str]:
    """Extract stunt/action items from scene-level records throughout the document."""
    items: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not re.search(r"\bstunts\b", stripped, re.IGNORECASE):
            continue
        if ":" not in stripped:
            continue
        if stripped.startswith("|"):
            continue

        after_colon = stripped.split(":", 1)[1].strip()
        after_colon = re.sub(r"\*\*", "", after_colon)
        if not after_colon:
            continue

        parts = re.split(r"[;,]", after_colon)
        for part in parts:
            item = part.strip().strip("[]\"'")
            if item and len(item) > 3 and item.lower() != "none":
                items.append(item)

    return items


def extract_elements_from_output(text: str, category: str) -> list[str]:
    """
    Extract identified production elements from an RLM or baseline output.

    Looks for category headers and extracts items listed underneath.
    Handles markdown tables, bullet lists, and numbered lists.
    """
    items: list[str] = []

    category_patterns = {
        "characters": r"(?:\bcast\b|\bcharacter\b|\bcharacters\b)",
        "props": r"(?:\bprops\b|\bprop list\b|\bproperties\b)",
        "vehicles": r"(?:\bvehicles\b|\btransport\b|\bcars?\b)",
        "locations": r"(?:\blocations\b|\blocation list\b|\bsettings?\b)",
        "wardrobe": r"(?:\bwardrobe\b|\bcostumes?\b|\bclothing\b)",
        "vfx": r"(?:\bvfx\b|\bspecial effects?\b|\bvisual effects?\b)",
        "music": r"(?:\bmusic\b|\bsound\b|\baudio\b|\bscore\b)",
        "stunts": r"(?:\bstunts?\b|\baction\b|\bfight\b)",
    }
    pattern = category_patterns.get(category, re.escape(category))

    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        is_heading_like = (
            stripped.startswith("#")
            or stripped.startswith("**")
            or stripped.endswith(":")
        )

        if re.search(pattern, stripped, re.IGNORECASE) and is_heading_like:
            in_section = True
            continue

        if in_section and is_heading_like and not re.search(pattern, stripped, re.IGNORECASE):
            # New section-like line, stop this category block.
            in_section = False
            continue

        if not in_section:
            continue

        # Markdown table rows.
        if stripped.startswith("|"):
            cols = [c.strip() for c in stripped.split("|") if c.strip()]
            if cols and not all(re.fullmatch(r"[:\- ]+", c) for c in cols):
                val = cols[0]
                if val and len(val) > 2 and val.lower() not in {"character", "vehicle", "location", "effect", "element", "prop"}:
                    items.append(val)
            continue

        # Bulleted and numbered list items.
        bullet_match = re.match(r"^[\s]*[-*•]\s+(.+)$", line)
        if not bullet_match:
            bullet_match = re.match(r"^[\s]*\d+\.\s+(.+)$", line)
        if bullet_match:
            item = bullet_match.group(1).strip()
            item = re.split(r"\s*[—-:]\s*", item, maxsplit=1)[0].strip()
            if item and len(item) > 2 and item.lower() != "none":
                items.append(item)
            continue

        # Also accept inline "Key: value" lines in structured templates.
        if ":" in stripped and not stripped.startswith("```"):
            key, val = stripped.split(":", 1)
            if re.search(pattern, key, re.IGNORECASE):
                candidate = val.strip()
                if candidate and candidate.lower() != "none":
                    items.append(candidate)

    return _dedupe_preserve_order(items)


def is_match(extracted: str, ground_truth: str) -> bool:
    """Case-insensitive partial match for production elements."""
    e = extracted.lower().strip()
    g = ground_truth.lower().strip()

    if not e or not g:
        return False

    if e in g or g in e:
        return True

    def normalize(value: str) -> str:
        value = value.lower()
        value = value.replace("'s", "")
        value = re.sub(r"\b(the|a|an)\b", " ", value)
        value = re.sub(r"[^a-z0-9\s]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    e_norm = normalize(e)
    g_norm = normalize(g)
    return bool(e_norm and g_norm) and (e_norm == g_norm or e_norm in g_norm or g_norm in e_norm)


def score_category(extracted: list[str], ground_truth: list[str]) -> dict:
    """Compute precision, recall, F1 for a single category."""
    if not ground_truth:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "tp": 0,
            "fp": len(extracted),
            "fn": 0,
            "extracted_count": len(extracted),
            "gt_count": 0,
        }

    matched_gt: set[int] = set()
    tp = 0

    for item in extracted:
        found = False
        for idx, gt_item in enumerate(ground_truth):
            if idx in matched_gt:
                continue
            if is_match(item, gt_item):
                matched_gt.add(idx)
                tp += 1
                found = True
                break
        if found:
            continue

    fp = len(extracted) - tp
    fn = len(ground_truth) - tp

    precision = tp / len(extracted) if extracted else 0.0
    recall = tp / len(ground_truth) if ground_truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "extracted_count": len(extracted),
        "gt_count": len(ground_truth),
    }


def format_results(
    rlm_scores: dict,
    baseline_scores: dict,
    rlm_path: str,
    baseline_path: str,
) -> str:
    """Format scoring results into a markdown comparison table."""
    lines = [
        "# Film Benchmark: Get Out (2017)",
        "",
        f"**RLM output:** `{rlm_path}`",
        f"**Baseline output:** `{baseline_path}`",
        "",
        "## Extraction Quality (vs Ground Truth)",
        "",
        "| Category | GT Items | RLM Found | RLM P/R/F1 | Baseline Found | Baseline P/R/F1 | Winner |",
        "|----------|----------|-----------|------------|----------------|-----------------|--------|",
    ]

    categories = ["characters", "props", "vehicles", "locations", "wardrobe", "vfx", "music", "stunts"]
    rlm_total_f1 = 0.0
    baseline_total_f1 = 0.0

    for cat in categories:
        r = rlm_scores.get(cat, {})
        b = baseline_scores.get(cat, {})

        r = {
            "precision": r.get("precision", 0.0),
            "recall": r.get("recall", 0.0),
            "f1": r.get("f1", 0.0),
            "extracted_count": r.get("extracted_count", 0),
            "gt_count": r.get("gt_count", 0),
        }
        b = {
            "precision": b.get("precision", 0.0),
            "recall": b.get("recall", 0.0),
            "f1": b.get("f1", 0.0),
            "extracted_count": b.get("extracted_count", 0),
            "gt_count": b.get("gt_count", 0),
        }

        winner = "Tie"
        if r["f1"] > b["f1"] + 0.02:
            winner = "RLM"
        elif b["f1"] > r["f1"] + 0.02:
            winner = "Baseline"

        lines.append(
            f"| {cat.title()} | {r['gt_count']} | {r['extracted_count']} | "
            f"{r['precision']:.2f}/{r['recall']:.2f}/{r['f1']:.2f} | "
            f"{b['extracted_count']} | "
            f"{b['precision']:.2f}/{b['recall']:.2f}/{b['f1']:.2f} | {winner} |"
        )

        rlm_total_f1 += r["f1"]
        baseline_total_f1 += b["f1"]

    avg_rlm = rlm_total_f1 / len(categories) if categories else 0.0
    avg_baseline = baseline_total_f1 / len(categories) if categories else 0.0

    lines.extend(
        [
            "",
            f"**Average F1:** RLM = {avg_rlm:.3f}, Baseline = {avg_baseline:.3f}",
            "",
            "## Key",
            "- P = Precision (correct / total extracted)",
            "- R = Recall (correct / total ground truth)",
            "- F1 = Harmonic mean of P and R",
            "- Winner determined by F1 difference > 0.02",
        ]
    )

    return "\n".join(lines)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = re.sub(r"\s+", " ", item.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def _resolve_input_path(path_or_glob: str, label: str) -> Path:
    if any(ch in path_or_glob for ch in "*?[]"):
        matches = sorted(glob(path_or_glob))
        if not matches:
            raise FileNotFoundError(f"No files matched {label} pattern: {path_or_glob}")
        # Prefer the most recently modified file if multiple matches exist.
        return Path(max(matches, key=lambda p: Path(p).stat().st_mtime))

    path = Path(path_or_glob)
    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path_or_glob}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Score film benchmark outputs against ground truth")
    parser.add_argument("--rlm", required=True, help="Path or glob to RLM analysis output (.md)")
    parser.add_argument("--baseline", required=True, help="Path or glob to baseline analysis output (.md)")
    parser.add_argument("--ground-truth", required=True, help="Path to ground truth file")
    parser.add_argument("--output", default=None, help="Path to write results (default: stdout only)")
    args = parser.parse_args()

    try:
        gt = parse_ground_truth(args.ground_truth)
        print(f"Ground truth loaded: {sum(len(v) for v in gt.values())} total items")
        for cat, items in gt.items():
            print(f"  {cat}: {len(items)} items")

        rlm_path = _resolve_input_path(args.rlm, "RLM")
        baseline_path = _resolve_input_path(args.baseline, "Baseline")

        rlm_text = rlm_path.read_text(encoding="utf-8")
        baseline_text = baseline_path.read_text(encoding="utf-8")

        rlm_scores = {}
        baseline_scores = {}
        for category, gt_items in gt.items():
            rlm_elements = extract_elements_from_output(rlm_text, category)
            baseline_elements = extract_elements_from_output(baseline_text, category)
            rlm_scores[category] = score_category(rlm_elements, gt_items)
            baseline_scores[category] = score_category(baseline_elements, gt_items)

        results = format_results(rlm_scores, baseline_scores, str(rlm_path), str(baseline_path))
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(results, encoding="utf-8")
            print(f"\nResults written to {output_path}")

        print("\n" + results)

    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
