"""
Content Loader for deeprepo.

Loads a content corpus from a local path into a structured format:
- file_tree: visual directory structure
- metadata: stats about the corpus
- documents: dict mapping filepath -> content (stored in REPL, NOT in model context)
"""

import os
import re
from collections import Counter
from pathlib import Path

# File extensions to include in content analysis
CONTENT_EXTENSIONS = {
    # Primary content
    ".md", ".txt", ".html", ".htm",
    # Data files (analytics exports, CMS configs)
    ".csv", ".json", ".yaml", ".yml",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".tox", ".pytest_cache", ".mypy_cache", "dist", "build",
    ".next", ".nuxt", "vendor", "target",
    "coverage", ".coverage", "htmlcov",
}

# Max file size to include (500KB - skip very large files)
MAX_FILE_SIZE = 500_000

_FILENAME_DATE_PATTERN = re.compile(r"(\d{4}-\d{2})(?:-\d{2})?")
_FRONT_MATTER_DATE_PATTERN = re.compile(
    r"^\s*date\s*:\s*['\"]?(\d{4}-\d{2})(?:-\d{2})?['\"]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def load_content(path: str) -> dict:
    """
    Load a content corpus from a local path.

    Returns:
        {
            "documents": {filepath: content, ...},
            "file_tree": "visual tree string",
            "metadata": {
                "corpus_name": str,
                "total_files": int,
                "total_documents": int,
                "total_chars": int,
                "total_words": int,
                "document_types": {".md": count, ...},
                "largest_documents": [(path, chars), ...],
                "content_categories": [category names...],
                "date_range": {"earliest": "YYYY-MM", "latest": "YYYY-MM"} | None,
            }
        }
    """
    root = Path(path).resolve()
    documents: dict[str, str] = {}
    document_types = Counter()
    document_sizes: list[tuple[str, int]] = []
    content_categories: set[str] = set()
    detected_months: set[str] = set()
    total_words = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip excluded directories (modifies in-place to prevent recursion)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in sorted(filenames):
            filepath = Path(dirpath) / filename
            ext = filepath.suffix.lower()

            if ext not in CONTENT_EXTENSIONS:
                continue

            rel_path = str(filepath.relative_to(root))
            parts = Path(rel_path).parts
            if len(parts) > 1:
                content_categories.add(parts[0])

            # Detect dates from filename (YYYY-MM-DD or YYYY-MM)
            detected_months.update(_extract_months(filename))

            try:
                size = filepath.stat().st_size
                if size > MAX_FILE_SIZE:
                    documents[rel_path] = f"[FILE TOO LARGE: {size:,} bytes, skipped]"
                    continue

                content = filepath.read_text(encoding="utf-8", errors="replace")
                documents[rel_path] = content
                document_types[ext] += 1
                document_sizes.append((rel_path, len(content)))
                total_words += len(content.split())

                # Check markdown front matter (first 20 lines) for date
                if ext == ".md":
                    header = "\n".join(content.splitlines()[:20])
                    detected_months.update(_extract_front_matter_months(header))
            except (OSError, UnicodeDecodeError) as e:
                documents[rel_path] = f"[READ ERROR: {e}]"

    if not documents:
        raise ValueError(
            f"No supported content files found in {root}. "
            f"Check the path and ensure it contains content documents."
        )

    file_tree = _build_tree(root, documents.keys())
    document_sizes.sort(key=lambda x: x[1], reverse=True)

    categories = sorted(content_categories) if content_categories else ["uncategorized"]

    date_range = None
    if detected_months:
        sorted_months = sorted(detected_months)
        date_range = {
            "earliest": sorted_months[0],
            "latest": sorted_months[-1],
        }

    metadata = {
        "corpus_name": root.name,
        "total_files": len(documents),
        "total_documents": len(documents),
        "total_chars": sum(len(v) for v in documents.values()),
        "total_words": total_words,
        "document_types": dict(document_types.most_common()),
        "largest_documents": document_sizes[:15],
        "content_categories": categories,
        "date_range": date_range,
    }

    return {
        "documents": documents,
        "file_tree": file_tree,
        "metadata": metadata,
    }


def _extract_months(text: str) -> set[str]:
    """Extract YYYY-MM values from text containing YYYY-MM or YYYY-MM-DD."""
    return {match.group(1) for match in _FILENAME_DATE_PATTERN.finditer(text)}


def _extract_front_matter_months(text: str) -> set[str]:
    """Extract YYYY-MM values from markdown front matter date lines."""
    return {match.group(1) for match in _FRONT_MATTER_DATE_PATTERN.finditer(text)}


def _build_tree(root: Path, filepaths, max_depth: int = 4) -> str:
    """Build a visual directory tree string."""
    lines = [f"{root.name}/"]
    dirs_seen = set()

    sorted_paths = sorted(filepaths)
    for filepath in sorted_paths:
        parts = Path(filepath).parts
        depth = len(parts) - 1

        if depth > max_depth:
            # Show truncated path
            dir_key = "/".join(parts[:max_depth])
            if dir_key not in dirs_seen:
                dirs_seen.add(dir_key)
                indent = "  " * max_depth
                lines.append(f"{indent}... ({filepath})")
            continue

        # Add directory entries
        for i in range(depth):
            dir_key = "/".join(parts[: i + 1])
            if dir_key not in dirs_seen:
                dirs_seen.add(dir_key)
                indent = "  " * (i + 1)
                lines.append(f"{indent}{parts[i]}/")

        # Add file entry
        indent = "  " * len(parts)
        lines.append(f"{indent}{parts[-1]}")

    return "\n".join(lines)


def format_content_metadata(metadata: dict) -> str:
    """Format content metadata into a concise string for the root model's context."""
    lines = [
        f"Corpus: {metadata['corpus_name']}",
        f"Total documents: {metadata['total_documents']}",
        f"Total characters: {metadata['total_chars']:,}",
        f"Total words: {metadata['total_words']:,}",
        "",
        "Document types:",
    ]
    for ext, count in metadata["document_types"].items():
        lines.append(f"  {ext}: {count} files")

    lines.append("")
    lines.append("Content categories:")
    for category in metadata["content_categories"]:
        lines.append(f"  {category}")

    if metadata.get("date_range"):
        date_range = metadata["date_range"]
        lines.append("")
        lines.append(f"Date range: {date_range['earliest']} to {date_range['latest']}")

    lines.append("")
    lines.append("Largest documents:")
    for path, chars in metadata["largest_documents"][:10]:
        lines.append(f"  {path}: {chars:,} chars")

    return "\n".join(lines)
