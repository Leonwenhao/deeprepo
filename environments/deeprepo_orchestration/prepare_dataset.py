#!/usr/bin/env python3
"""
Prepare the training dataset for the DeepRepo Orchestration environment.

Two modes:
  --local  (default) Load codebases and create dataset with synthetic ground truth.
                     No API keys required.
  --live             Run full DeepRepo analysis, capture sub-LLM cache and ground
                     truth findings. Requires ANTHROPIC_API_KEY and OPENROUTER_API_KEY.

Usage:
  # Local mode (no API calls)
  python prepare_dataset.py ./path/to/repo1 ./path/to/repo2

  # Include the DeepRepo repo itself
  python prepare_dataset.py .

  # Live mode with real analysis
  python prepare_dataset.py --live ./path/to/repo1 ./path/to/repo2

  # Custom output path
  python prepare_dataset.py -o dataset.json ./path/to/repo1
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Add the project root to sys.path so we can import deeprepo
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_codebase_data(repo_path: str) -> dict:
    """Load a codebase using deeprepo's loader and return structured data."""
    from deeprepo.codebase_loader import load_codebase

    data = load_codebase(repo_path)
    name = Path(repo_path).resolve().name

    return {
        "name": name,
        "codebase": data["codebase"],
        "file_tree": data["file_tree"],
        "metadata": data["metadata"],
    }


def prepare_local(repo_paths: list[str]) -> list[dict]:
    """Prepare dataset entries from local codebases without API calls.

    Ground truth findings are left empty (can be filled in manually or via
    --live mode later).
    """
    entries = []
    for path in repo_paths:
        print(f"Loading {path}...")
        try:
            entry = load_codebase_data(path)
        except Exception as e:
            print(f"  ERROR loading {path}: {e}", file=sys.stderr)
            continue

        meta = entry["metadata"]
        print(
            f"  Loaded: {meta['total_files']} files, "
            f"{meta['total_chars']:,} chars"
        )

        # Synthetic ground truth placeholder
        entry["ground_truth_dispatches"] = meta["total_files"]
        entry["ground_truth_findings"] = []
        entry["llm_cache"] = {}

        # Ensure metadata values are JSON-serializable
        # (largest_files contains tuples from load_codebase)
        if "largest_files" in meta:
            meta["largest_files"] = [list(t) for t in meta["largest_files"]]

        entries.append(entry)

    return entries


def prepare_live(repo_paths: list[str], root_model: str, sub_model: str) -> list[dict]:
    """Prepare dataset entries by running real DeepRepo analysis.

    Captures every sub-LLM prompt/response for caching, and extracts
    the final analysis findings as ground truth.
    """
    from deeprepo.llm_clients import (
        SubModelClient,
        TokenUsage,
        create_root_client,
    )
    from deeprepo.rlm_scaffold import RLMEngine
    from deeprepo.domains import get_domain

    domain = get_domain("code")
    entries = []

    for path in repo_paths:
        print(f"\n{'='*60}")
        print(f"Analyzing {path} (live mode)...")
        print(f"{'='*60}")

        try:
            entry = load_codebase_data(path)
        except Exception as e:
            print(f"  ERROR loading {path}: {e}", file=sys.stderr)
            continue

        meta = entry["metadata"]
        if "largest_files" in meta:
            meta["largest_files"] = [list(t) for t in meta["largest_files"]]

        # Set up clients
        usage = TokenUsage()
        usage.set_root_pricing(root_model)
        root_client = create_root_client(usage=usage, model=root_model)
        sub_client = SubModelClient(usage=usage, model=sub_model, use_cache=True)

        # Wrap sub_client to capture all prompts/responses
        call_log: list[tuple[str, str]] = []
        original_query = sub_client.query

        def logging_query(prompt, system="", max_tokens=4096):
            response = original_query(prompt, system=system, max_tokens=max_tokens)
            call_log.append((prompt, response))
            return response

        sub_client.query = logging_query

        # Run analysis
        engine = RLMEngine(
            root_client=root_client,
            sub_client=sub_client,
            usage=usage,
            max_turns=20,
            verbose=True,
        )

        try:
            result = engine.analyze(path, domain=domain)
        except Exception as e:
            print(f"  ANALYSIS ERROR: {e}", file=sys.stderr)
            entry["ground_truth_dispatches"] = len(call_log)
            entry["ground_truth_findings"] = []
            entry["llm_cache"] = _build_cache(call_log)
            entries.append(entry)
            continue

        # Extract findings from the analysis text
        findings = _extract_findings_from_analysis(result["analysis"])

        # Build cache
        cache = _build_cache(call_log)

        entry["ground_truth_dispatches"] = len(call_log)
        entry["ground_truth_findings"] = findings
        entry["llm_cache"] = cache

        print(f"\n  Result: {result['status']}, {result['turns']} turns")
        print(f"  Dispatches: {len(call_log)}")
        print(f"  Findings extracted: {len(findings)}")
        print(f"  Cost: {usage.summary()}")

        entries.append(entry)

    return entries


def _build_cache(call_log: list[tuple[str, str]]) -> dict:
    """Convert a list of (prompt, response) tuples to a hash-keyed cache."""
    cache = {}
    for prompt, response in call_log:
        key = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        cache[key] = response
    return cache


def _extract_findings_from_analysis(analysis: str) -> list[str]:
    """Extract bullet-point findings from an analysis document."""
    findings = []
    for line in analysis.split("\n"):
        line = line.strip()
        if line.startswith(("- ", "* ", "• ")):
            finding = line.lstrip("-*• ").strip()
            if len(finding) > 15:
                findings.append(finding)
    return findings[:50]  # cap at 50 findings


def main():
    parser = argparse.ArgumentParser(
        description="Prepare dataset for DeepRepo Orchestration environment"
    )
    parser.add_argument(
        "repos",
        nargs="*",
        default=[str(PROJECT_ROOT)],
        help="Paths to codebases to include (default: current DeepRepo repo)",
    )
    parser.add_argument(
        "-o", "--output",
        default=str(Path(__file__).parent / "dataset.json"),
        help="Output path for dataset JSON",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run real DeepRepo analysis (requires API keys)",
    )
    parser.add_argument(
        "--root-model",
        default="claude-sonnet-4-6",
        help="Root model for live analysis (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--sub-model",
        default="minimax/minimax-m2.5",
        help="Sub-LLM model for live analysis",
    )

    args = parser.parse_args()

    # Validate paths
    valid_paths = []
    for p in args.repos:
        path = Path(p).resolve()
        if path.is_dir():
            valid_paths.append(str(path))
        else:
            print(f"WARNING: Skipping {p} (not a directory)", file=sys.stderr)

    if not valid_paths:
        print("ERROR: No valid repository paths provided.", file=sys.stderr)
        sys.exit(1)

    print(f"Preparing dataset from {len(valid_paths)} codebase(s)...")
    print(f"Mode: {'live (real API calls)' if args.live else 'local (no API calls)'}")
    print(f"Output: {args.output}\n")

    if args.live:
        entries = prepare_live(valid_paths, args.root_model, args.sub_model)
    else:
        entries = prepare_local(valid_paths)

    if not entries:
        print("ERROR: No entries produced.", file=sys.stderr)
        sys.exit(1)

    # Save dataset
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(entries, f, indent=2, default=str)

    print(f"\nDataset saved: {output_path}")
    print(f"  Entries: {len(entries)}")
    for e in entries:
        n_files = e["metadata"]["total_files"]
        n_findings = len(e.get("ground_truth_findings", []))
        n_cache = len(e.get("llm_cache", {}))
        print(f"  - {e['name']}: {n_files} files, {n_findings} findings, {n_cache} cached responses")


if __name__ == "__main__":
    main()
