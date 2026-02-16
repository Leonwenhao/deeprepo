"""Step 2: Test codebase loader against tests/test_small/."""

import json
from src.codebase_loader import load_codebase, format_metadata_for_prompt

TEST_PATH = "tests/test_small"

print("=" * 60)
print(f"Loading codebase from: {TEST_PATH}")
print("=" * 60)

result = load_codebase(TEST_PATH)

codebase = result["codebase"]
file_tree = result["file_tree"]
metadata = result["metadata"]

# ── Verify file count ──
print(f"\nTotal files loaded: {metadata['total_files']}")
print(f"Expected: 3")
assert metadata["total_files"] == 3, f"Expected 3 files, got {metadata['total_files']}"
print("  PASS")

# ── Verify file paths ──
print(f"\nFiles found:")
for fp in sorted(codebase.keys()):
    print(f"  {fp} ({len(codebase[fp])} chars)")

expected_files = {"app.py", "config.json", "utils.py"}
actual_files = set(codebase.keys())
assert actual_files == expected_files, f"Expected {expected_files}, got {actual_files}"
print("  PASS — all 3 files present")

# ── Verify metadata ──
print(f"\nMetadata:")
print(f"  repo_name:    {metadata['repo_name']}")
print(f"  total_chars:  {metadata['total_chars']:,}")
print(f"  total_lines:  {metadata['total_lines']:,}")
print(f"  file_types:   {metadata['file_types']}")
print(f"  entry_points: {metadata['entry_points']}")
print(f"  largest_files: {metadata['largest_files']}")

assert metadata["repo_name"] == "test_small"
assert ".py" in metadata["file_types"]
assert ".json" in metadata["file_types"]
assert metadata["file_types"][".py"] == 2
assert metadata["file_types"][".json"] == 1
print("  PASS — file types correct")

# Verify entry points detected
assert "app.py" in metadata["entry_points"], "app.py should be detected as entry point"
print("  PASS — entry points detected")

# ── Verify file tree ──
print(f"\nFile tree:")
print(file_tree)
assert "app.py" in file_tree
assert "utils.py" in file_tree
assert "config.json" in file_tree
print("  PASS — tree contains all files")

# ── Verify content loaded correctly ──
assert "Flask" in codebase["app.py"], "app.py should contain Flask"
assert "hashlib" in codebase["utils.py"], "utils.py should contain hashlib"
assert "database" in codebase["config.json"], "config.json should contain database"
print("  PASS — file contents loaded correctly")

# ── Test format_metadata_for_prompt ──
print(f"\nFormatted metadata for prompt:")
formatted = format_metadata_for_prompt(metadata)
print(formatted)
assert "test_small" in formatted
assert "3" in formatted  # total files
print("  PASS — metadata formats without error")

print("\n" + "=" * 60)
print("All codebase loader tests PASSED!")
print("=" * 60)
