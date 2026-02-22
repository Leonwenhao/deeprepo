import inspect
from collections import Counter
from pathlib import Path

import pytest

from deeprepo.film_loader import (
    classify_time_of_day,
    extract_text_from_pdf,
    format_film_metadata,
    load_screenplay,
    parse_scenes,
)


TEST_SCREENPLAY_PATH = "tests/test_screenplay.txt"


def test_load_returns_required_keys():
    data = load_screenplay(TEST_SCREENPLAY_PATH)
    assert "scenes" in data
    assert "file_tree" in data
    assert "metadata" in data


def test_detects_five_scenes_with_expected_scene_keys():
    data = load_screenplay(TEST_SCREENPLAY_PATH)
    scene_keys = list(data["scenes"].keys())
    assert len(scene_keys) == 5
    assert scene_keys[0] == "SC-001: EXT. SUBURBAN STREET - NIGHT"
    assert scene_keys[-1] == "SC-005: INT. ARMITAGE HOUSE - LIVING ROOM - NIGHT"


def test_detect_characters_strips_parentheticals_and_false_positives():
    data = load_screenplay(TEST_SCREENPLAY_PATH)
    characters = set(data["metadata"]["characters"])
    assert {"CHRIS", "ROSE", "ANDRE", "DEAN", "MISSY"}.issubset(characters)
    assert "ANDRE (CONT'D)" not in characters
    assert "ROSE (O.S.)" not in characters
    assert "FADE IN" not in characters
    assert "FADE OUT" not in characters
    assert data["metadata"]["total_characters"] >= 5


def test_int_ext_breakdown_counts_are_correct():
    data = load_screenplay(TEST_SCREENPLAY_PATH)
    breakdown = data["metadata"]["int_ext_breakdown"]
    assert breakdown["INT"] == 2
    assert breakdown["EXT"] == 2
    assert breakdown["INT./EXT."] == 1

    text = Path(TEST_SCREENPLAY_PATH).read_text(encoding="utf-8")
    parsed = parse_scenes(text)
    first_four = Counter(scene["int_ext"] for scene in parsed[:4])
    assert first_four["INT"] == 1
    assert first_four["EXT"] == 2
    assert first_four["INT./EXT."] == 1


def test_time_of_day_breakdown_counts_are_correct():
    data = load_screenplay(TEST_SCREENPLAY_PATH)
    breakdown = data["metadata"]["time_of_day_breakdown"]
    assert breakdown["DAY"] == 3
    assert breakdown["NIGHT"] == 2


def test_classify_time_of_day_values():
    assert classify_time_of_day("INT. KITCHEN - NIGHT") == "NIGHT"
    assert classify_time_of_day("INT./EXT. CAR - CONTINUOUS") == "CONTINUOUS"
    assert classify_time_of_day("INT. BASEMENT") == "UNKNOWN"


def test_parse_scenes_normalizes_ext_int_headers_and_empty_scene_body():
    text = "EXT/INT. CAR - CONTINUOUS\nINT. HALLWAY - DAY\nAction."
    scenes = parse_scenes(text)
    assert len(scenes) == 2
    assert scenes[0]["int_ext"] == "INT./EXT."
    assert scenes[0]["header"].startswith("INT./EXT.")
    assert scenes[0]["body"] == ""
    assert scenes[1]["body"] == "Action."


def test_format_film_metadata_returns_rich_string():
    data = load_screenplay(TEST_SCREENPLAY_PATH)
    formatted = format_film_metadata(data["metadata"])
    assert isinstance(formatted, str)
    assert len(formatted) > 100
    assert "Total scenes: 5" in formatted


def test_extract_text_from_pdf_has_required_fallback_chain():
    source = inspect.getsource(extract_text_from_pdf)
    assert "pdfplumber" in source
    assert "fitz" in source
    assert "Install with: pip install pdfplumber" in source


def test_non_screenplay_or_empty_file_raises_value_error(tmp_path):
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="No screenplay scenes detected"):
        load_screenplay(str(empty_file))

    notes_file = tmp_path / "notes.txt"
    notes_file.write_text("This is not a screenplay.\nNo sluglines here.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No screenplay scenes detected"):
        load_screenplay(str(notes_file))
