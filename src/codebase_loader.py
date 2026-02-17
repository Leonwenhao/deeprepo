"""
Codebase Loader for deeprepo.

Loads a codebase (from local path or git URL) into a structured format:
- file_tree: visual directory structure
- metadata: stats about the repo
- codebase: dict mapping filepath → content (stored in REPL, NOT in model context)
"""

import os
import subprocess
import tempfile
from pathlib import Path
from collections import Counter

# File extensions to include in analysis
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".php", ".swift", ".kt",
    ".sql", ".html", ".css", ".scss", ".vue", ".svelte",
    # Shell
    ".sh", ".bash", ".zsh",
    # Languages
    ".lua", ".r", ".R", ".scala", ".zig", ".dart", ".ex", ".exs",
}

CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".xml", ".conf",
    # Data/schema
    ".proto", ".graphql", ".prisma",
    # Infrastructure
    ".tf", ".hcl", ".dockerfile",
}

DOC_EXTENSIONS = {
    ".md", ".txt", ".rst", ".adoc",
}

ALL_EXTENSIONS = CODE_EXTENSIONS | CONFIG_EXTENSIONS | DOC_EXTENSIONS

# Extensionless files to include by exact filename
EXTENSIONLESS_FILES = {
    "Makefile", "Dockerfile", "Jenkinsfile", "Procfile",
}

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".tox", ".pytest_cache", ".mypy_cache", "dist", "build",
    ".next", ".nuxt", "vendor", "target", ".cargo",
    "coverage", ".coverage", "htmlcov",
}

# Max file size to include (500KB — skip giant generated files)
MAX_FILE_SIZE = 500_000


def clone_repo(url: str, target_dir: str | None = None) -> str:
    """Clone a git repo and return the path."""
    if target_dir is None:
        target_dir = tempfile.mkdtemp(prefix="rlm_repo_")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, target_dir],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace").strip() if e.stderr else "unknown error"
        raise RuntimeError(f"Failed to clone {url}: {stderr}") from e
    return target_dir


def load_codebase(path: str) -> dict:
    """
    Load a codebase from a local path.
    
    Returns:
        {
            "codebase": {filepath: content, ...},
            "file_tree": "visual tree string",
            "metadata": {
                "total_files": int,
                "total_chars": int,
                "total_lines": int,
                "file_types": {".py": count, ...},
                "largest_files": [(path, chars), ...],
                "entry_points": [paths...],
            }
        }
    """
    root = Path(path).resolve()
    codebase = {}
    file_types = Counter()
    file_sizes = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip excluded directories (modifies in-place to prevent recursion)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in sorted(filenames):
            filepath = Path(dirpath) / filename
            ext = filepath.suffix.lower()

            if ext not in ALL_EXTENSIONS and filename not in EXTENSIONLESS_FILES:
                continue

            rel_path = str(filepath.relative_to(root))

            try:
                size = filepath.stat().st_size
                if size > MAX_FILE_SIZE:
                    codebase[rel_path] = f"[FILE TOO LARGE: {size:,} bytes, skipped]"
                    continue

                content = filepath.read_text(encoding="utf-8", errors="replace")
                codebase[rel_path] = content
                file_types[ext] += 1
                file_sizes.append((rel_path, len(content)))
            except (OSError, UnicodeDecodeError) as e:
                codebase[rel_path] = f"[READ ERROR: {e}]"

    if not codebase:
        raise ValueError(
            f"No supported files found in {root}. "
            f"Check the path and ensure it contains source code files."
        )

    # Build file tree
    file_tree = _build_tree(root, codebase.keys())

    # Identify likely entry points
    entry_points = _find_entry_points(codebase)

    # Sort largest files
    file_sizes.sort(key=lambda x: x[1], reverse=True)

    metadata = {
        "repo_name": root.name,
        "total_files": len(codebase),
        "total_chars": sum(len(v) for v in codebase.values()),
        "total_lines": sum(v.count("\n") for v in codebase.values()),
        "file_types": dict(file_types.most_common()),
        "largest_files": file_sizes[:15],
        "entry_points": entry_points,
    }

    return {
        "codebase": codebase,
        "file_tree": file_tree,
        "metadata": metadata,
    }


def _build_tree(root: Path, filepaths: list[str], max_depth: int = 4) -> str:
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


def _find_entry_points(codebase: dict) -> list[str]:
    """Identify likely entry points in the codebase."""
    entry_patterns = [
        "main.py", "app.py", "index.py", "server.py", "run.py",
        "index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts",
        "main.go", "main.rs", "Main.java",
        "manage.py", "wsgi.py", "asgi.py",
        "setup.py", "pyproject.toml", "package.json",
        "Dockerfile", "docker-compose.yml",
        "README.md",
    ]

    found = []
    for filepath in codebase:
        basename = Path(filepath).name
        if basename in entry_patterns:
            found.append(filepath)

    # Also look for files with if __name__ == "__main__"
    for filepath, content in codebase.items():
        if filepath.endswith(".py") and '__name__' in content and '__main__' in content:
            if filepath not in found:
                found.append(filepath)

    return sorted(found)


def format_metadata_for_prompt(metadata: dict) -> str:
    """Format metadata into a concise string for the root model's context."""
    lines = [
        f"Repository: {metadata['repo_name']}",
        f"Total files: {metadata['total_files']}",
        f"Total characters: {metadata['total_chars']:,}",
        f"Total lines: {metadata['total_lines']:,}",
        "",
        "File types:",
    ]
    for ext, count in metadata["file_types"].items():
        lines.append(f"  {ext}: {count} files")

    lines.append("")
    lines.append("Largest files:")
    for path, chars in metadata["largest_files"][:10]:
        lines.append(f"  {path}: {chars:,} chars")

    if metadata["entry_points"]:
        lines.append("")
        lines.append("Likely entry points:")
        for ep in metadata["entry_points"]:
            lines.append(f"  {ep}")

    return "\n".join(lines)
