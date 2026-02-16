"""
Baseline — Single-model codebase analysis for comparison with RLM approach.

This dumps the entire codebase into a single Opus call (or as much as fits).
Used to measure what RLM buys us over the naive approach.
"""

import time
from .llm_clients import RootModelClient, TokenUsage, create_root_client
from .codebase_loader import load_codebase, format_metadata_for_prompt


BASELINE_SYSTEM_PROMPT = """You are a senior software architect performing a codebase review. 
Analyze the provided codebase and produce a comprehensive report with:

1. **Architecture Overview** — entry points, module dependencies, data flow, design patterns
2. **Bug & Issue Audit** — security issues, logic errors, error handling gaps, edge cases
3. **Code Quality Assessment** — pattern consistency, test coverage, documentation, naming
4. **Prioritized Development Plan** — P0 (critical), P1 (important), P2 (nice-to-have), each with what/why/estimated complexity

Be thorough and specific. Reference actual file names and line-level issues where possible."""


def run_baseline(
    codebase_path: str,
    max_chars: int = 180_000,  # ~45k tokens, leaving room for response
    verbose: bool = True,
    root_model: str = "claude-opus-4-6",
) -> dict:
    """
    Run a single-model baseline analysis.

    Concatenates as much of the codebase as fits into one prompt
    and sends it to Opus in a single call.

    Args:
        codebase_path: Local path to the codebase (or git URL)
        max_chars: Maximum characters to include in prompt
        verbose: Print progress

    Returns:
        dict with analysis, usage, included_files, excluded_files
    """
    # Validate path for local directories
    actual_path = codebase_path
    if not codebase_path.startswith(("http://", "https://", "git@")):
        from pathlib import Path
        p = Path(codebase_path)
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {codebase_path}")
        if not p.is_dir():
            raise ValueError(f"Path is not a directory: {codebase_path}")

    # Handle git URLs
    if codebase_path.startswith(("http://", "https://", "git@")):
        from .codebase_loader import clone_repo
        if verbose:
            print(f"Cloning {codebase_path}...")
        actual_path = clone_repo(codebase_path)
        if verbose:
            print(f"Cloned to {actual_path}")

    # Load codebase
    data = load_codebase(actual_path)
    codebase = data["codebase"]
    metadata = data["metadata"]
    file_tree = data["file_tree"]

    if verbose:
        print(f"Loaded {metadata['total_files']} files, {metadata['total_chars']:,} chars")

    # Build the prompt by concatenating files until we hit the limit
    metadata_str = format_metadata_for_prompt(metadata)
    prompt_parts = [
        f"## Repository Metadata\n{metadata_str}\n",
        f"## File Tree\n{file_tree}\n",
        "## File Contents\n",
    ]
    current_chars = sum(len(p) for p in prompt_parts)

    included_files = []
    excluded_files = []

    # Sort files: entry points first, then by size (smallest first to include more)
    entry_set = set(metadata.get("entry_points", []))
    sorted_files = sorted(
        codebase.items(),
        key=lambda x: (x[0] not in entry_set, len(x[1])),
    )

    for filepath, content in sorted_files:
        file_block = f"\n### {filepath}\n```\n{content}\n```\n"
        if current_chars + len(file_block) > max_chars:
            excluded_files.append(filepath)
            continue
        prompt_parts.append(file_block)
        current_chars += len(file_block)
        included_files.append(filepath)

    prompt = "\n".join(prompt_parts)

    if excluded_files and verbose:
        print(f"⚠️ {len(excluded_files)} files excluded due to context limit")
        print(f"  Included: {len(included_files)} files ({current_chars:,} chars)")

    # Send to root model
    usage = TokenUsage()
    usage.set_root_pricing(root_model)
    client = create_root_client(usage=usage, model=root_model)

    if verbose:
        print(f"Sending to {usage.root_model_label} (single call)...")

    t0 = time.time()
    analysis = client.complete(
        messages=[{"role": "user", "content": prompt}],
        system=BASELINE_SYSTEM_PROMPT,
        max_tokens=16384,  # Allow longer response for baseline
    )
    elapsed = time.time() - t0

    if verbose:
        print(f"Response in {elapsed:.1f}s")
        print(usage.summary())

    return {
        "analysis": analysis,
        "usage": usage,
        "included_files": included_files,
        "excluded_files": excluded_files,
        "prompt_chars": current_chars,
        "elapsed_seconds": elapsed,
    }
