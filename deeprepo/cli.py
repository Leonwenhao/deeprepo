"""
CLI for deeprepo.

Usage:
    deeprepo analyze /path/to/repo
    deeprepo analyze https://github.com/user/repo
    deeprepo baseline /path/to/repo
    deeprepo compare /path/to/repo
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from . import __version__
from .llm_clients import DEFAULT_SUB_MODEL

# Map short names to model strings
ROOT_MODEL_MAP = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-5-20250929",
    "minimax": "minimax/minimax-m2.5",
}


def cmd_analyze(args):
    """Run RLM analysis on a codebase."""
    from .rlm_scaffold import run_analysis

    root_model = ROOT_MODEL_MAP.get(args.root_model, args.root_model)

    result = run_analysis(
        codebase_path=args.path,
        verbose=not args.quiet,
        max_turns=args.max_turns,
        root_model=root_model,
        sub_model=args.sub_model,
        use_cache=not args.no_cache,
    )

    # Save output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    repo_name = Path(args.path).name if not args.path.startswith("http") else args.path.split("/")[-1]

    # Save analysis
    analysis_path = output_dir / f"deeprepo_{repo_name}_{timestamp}.md"
    analysis_path.write_text(result["analysis"])
    print(f"\n📄 Analysis saved to: {analysis_path}")

    # Save metrics
    metrics = {
        "mode": "rlm",
        "root_model": root_model,
        "sub_model": args.sub_model,
        "repo": args.path,
        "turns": result["turns"],
        "root_calls": result["usage"].root_calls,
        "sub_calls": result["usage"].sub_calls,
        "root_input_tokens": result["usage"].root_input_tokens,
        "root_output_tokens": result["usage"].root_output_tokens,
        "sub_input_tokens": result["usage"].sub_input_tokens,
        "sub_output_tokens": result["usage"].sub_output_tokens,
        "root_cost": result["usage"].root_cost,
        "sub_cost": result["usage"].sub_cost,
        "total_cost": result["usage"].total_cost,
    }
    metrics_path = output_dir / f"deeprepo_{repo_name}_{timestamp}_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"📊 Metrics saved to: {metrics_path}")
    print(f"\n{result['usage'].summary()}")


def cmd_baseline(args):
    """Run single-model baseline analysis."""
    from .baseline import run_baseline

    root_model = ROOT_MODEL_MAP.get(args.root_model, args.root_model)

    result = run_baseline(
        codebase_path=args.path,
        verbose=not args.quiet,
        root_model=root_model,
    )

    # Save output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    repo_name = Path(args.path).name

    analysis_path = output_dir / f"baseline_{repo_name}_{timestamp}.md"
    analysis_path.write_text(result["analysis"])
    print(f"\n📄 Baseline analysis saved to: {analysis_path}")

    metrics = {
        "mode": "baseline",
        "repo": args.path,
        "included_files": len(result["included_files"]),
        "excluded_files": len(result["excluded_files"]),
        "prompt_chars": result["prompt_chars"],
        "elapsed_seconds": result["elapsed_seconds"],
        "root_input_tokens": result["usage"].root_input_tokens,
        "root_output_tokens": result["usage"].root_output_tokens,
        "root_cost": result["usage"].root_cost,
        "total_cost": result["usage"].total_cost,
    }
    metrics_path = output_dir / f"baseline_{repo_name}_{timestamp}_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"📊 Metrics saved to: {metrics_path}")
    print(f"\n{result['usage'].summary()}")


def cmd_compare(args):
    """Run both RLM and baseline, then compare."""
    from .rlm_scaffold import run_analysis
    from .baseline import run_baseline

    rlm_model = ROOT_MODEL_MAP.get(args.root_model, args.root_model)
    baseline_model = ROOT_MODEL_MAP.get(args.baseline_model, args.baseline_model)

    # Clone once if git URL, reuse for both runs
    actual_path = args.path
    is_temp = False
    if args.path.startswith(("http://", "https://", "git@")):
        from .codebase_loader import clone_repo
        print(f"Cloning {args.path}...")
        actual_path = clone_repo(args.path)
        is_temp = True
        print(f"Cloned to {actual_path}")

    try:
        print(f"\nRunning RLM analysis (root: {rlm_model})...")
        print("=" * 60)

        rlm_result = run_analysis(
            codebase_path=actual_path,
            verbose=not args.quiet,
            max_turns=args.max_turns,
            root_model=rlm_model,
            sub_model=args.sub_model,
            use_cache=not args.no_cache,
        )

        print(f"\n\nRunning baseline analysis (root: {baseline_model})...")
        print("=" * 60)

        baseline_result = run_baseline(
            codebase_path=actual_path,
            verbose=not args.quiet,
            root_model=baseline_model,
        )
    finally:
        if is_temp:
            shutil.rmtree(actual_path, ignore_errors=True)

    # Save both
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    repo_name = Path(args.path).name

    (output_dir / f"deeprepo_{repo_name}_{timestamp}.md").write_text(rlm_result["analysis"])
    (output_dir / f"baseline_{repo_name}_{timestamp}.md").write_text(baseline_result["analysis"])

    # Save metrics JSON for both sides
    rlm_metrics = {
        "mode": "rlm",
        "root_model": rlm_model,
        "sub_model": args.sub_model,
        "repo": args.path,
        "turns": rlm_result["turns"],
        "root_calls": rlm_result["usage"].root_calls,
        "sub_calls": rlm_result["usage"].sub_calls,
        "root_input_tokens": rlm_result["usage"].root_input_tokens,
        "root_output_tokens": rlm_result["usage"].root_output_tokens,
        "sub_input_tokens": rlm_result["usage"].sub_input_tokens,
        "sub_output_tokens": rlm_result["usage"].sub_output_tokens,
        "root_cost": rlm_result["usage"].root_cost,
        "sub_cost": rlm_result["usage"].sub_cost,
        "total_cost": rlm_result["usage"].total_cost,
        "analysis_chars": len(rlm_result["analysis"]),
    }
    baseline_metrics = {
        "mode": "baseline",
        "root_model": baseline_model,
        "repo": args.path,
        "root_calls": baseline_result["usage"].root_calls,
        "root_input_tokens": baseline_result["usage"].root_input_tokens,
        "root_output_tokens": baseline_result["usage"].root_output_tokens,
        "root_cost": baseline_result["usage"].root_cost,
        "total_cost": baseline_result["usage"].total_cost,
        "included_files": len(baseline_result["included_files"]),
        "excluded_files": len(baseline_result["excluded_files"]),
        "prompt_chars": baseline_result["prompt_chars"],
        "elapsed_seconds": baseline_result["elapsed_seconds"],
        "analysis_chars": len(baseline_result["analysis"]),
    }
    (output_dir / f"deeprepo_{repo_name}_{timestamp}_metrics.json").write_text(
        json.dumps(rlm_metrics, indent=2)
    )
    (output_dir / f"baseline_{repo_name}_{timestamp}_metrics.json").write_text(
        json.dumps(baseline_metrics, indent=2)
    )

    # Print comparison
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print(f"\n{'Metric':<30} {'RLM':<25} {'Baseline':<25}")
    print("-" * 80)
    print(f"{'Root model':<30} {rlm_result['usage'].root_model_label:<25} {baseline_result['usage'].root_model_label:<25}")
    print(f"{'Total cost':<30} ${rlm_result['usage'].total_cost:<24.4f} ${baseline_result['usage'].total_cost:<24.4f}")
    print(f"{'Root cost':<30} ${rlm_result['usage'].root_cost:<24.4f} ${baseline_result['usage'].root_cost:<24.4f}")
    print(f"{'Sub-LLM cost':<30} ${rlm_result['usage'].sub_cost:<24.4f} {'N/A':<25}")
    print(f"{'Root tokens (in/out)':<30} {rlm_result['usage'].root_input_tokens:,}/{rlm_result['usage'].root_output_tokens:,} {'':<5} {baseline_result['usage'].root_input_tokens:,}/{baseline_result['usage'].root_output_tokens:,}")
    print(f"{'Sub-LLM calls':<30} {rlm_result['usage'].sub_calls:<25} {'N/A':<25}")
    print(f"{'Sub tokens (in/out)':<30} {rlm_result['usage'].sub_input_tokens:,}/{rlm_result['usage'].sub_output_tokens:,} {'':<5} {'N/A':<25}")
    print(f"{'REPL turns':<30} {rlm_result['turns']:<25} {'1':<25}")
    print(f"{'Analysis length (chars)':<30} {len(rlm_result['analysis']):,}{'':<19} {len(baseline_result['analysis']):,}")

    if baseline_result.get("excluded_files"):
        print(f"{'Files excluded (context limit)':<30} {'0':<25} {len(baseline_result['excluded_files']):<25}")

    print(f"\nOutputs saved to: {output_dir}/")


def cmd_list_models(args):
    """List built-in sub-LLM model pricing options."""
    from .llm_clients import DEFAULT_SUB_MODEL, SUB_MODEL_PRICING

    print("Available sub-LLM models (for --sub-model flag):\n")
    print(f"  {'Model':<45} {'Input $/M':>10} {'Output $/M':>11}")
    print(f"  {'-' * 45} {'-' * 10} {'-' * 11}")
    for model, pricing in SUB_MODEL_PRICING.items():
        default_marker = " (default)" if model == DEFAULT_SUB_MODEL else ""
        print(
            f"  {model:<45} ${pricing['input']:>8.2f}  ${pricing['output']:>9.2f}{default_marker}"
        )
    print("\n  Any OpenRouter model string is accepted. Unknown models use $1.00/$1.00 fallback pricing.")


def cmd_cache(args):
    """Manage the sub-LLM result cache."""
    from .cache import cache_stats, clear_cache

    if args.cache_action == "stats":
        stats = cache_stats()
        print("Cache directory: ~/.cache/deeprepo/")
        print(f"Entries: {stats['entries']}")
        print(f"Size: {stats['size_mb']} MB")
    elif args.cache_action == "clear":
        deleted = clear_cache()
        print(f"Cleared {deleted} cached entries.")


def main():
    parser = argparse.ArgumentParser(
        description="deeprepo — Deep codebase intelligence powered by recursive multi-model orchestration"
    )
    parser.add_argument(
        "--version", action="version", version=f"deeprepo {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Common arguments
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("path", help="Path to codebase or git URL")
    common.add_argument("-o", "--output-dir", default="outputs", help="Output directory")
    common.add_argument("-q", "--quiet", action="store_true", help="Suppress verbose output")
    common.add_argument(
        "--root-model",
        default="sonnet",
        help="Root model: opus, sonnet (default), minimax, or a full model string like claude-opus-4-6",
    )
    common.add_argument(
        "--sub-model",
        default=DEFAULT_SUB_MODEL,
        help=f"Sub-LLM model for file analysis (default: {DEFAULT_SUB_MODEL}). Any OpenRouter model string.",
    )
    common.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass sub-LLM result cache (forces fresh API calls)",
    )

    # analyze command
    p_analyze = subparsers.add_parser("analyze", parents=[common], help="Run RLM analysis")
    p_analyze.add_argument("--max-turns", type=int, default=15, help="Max REPL turns")
    p_analyze.set_defaults(func=cmd_analyze)

    # baseline command
    p_baseline = subparsers.add_parser("baseline", parents=[common], help="Run single-model baseline")
    p_baseline.set_defaults(func=cmd_baseline)

    # compare command
    p_compare = subparsers.add_parser("compare", parents=[common], help="Run both and compare")
    p_compare.add_argument("--max-turns", type=int, default=15, help="Max REPL turns for RLM")
    p_compare.add_argument(
        "--baseline-model",
        default="opus",
        help="Root model for baseline side: opus (default), sonnet, or a full model string",
    )
    p_compare.set_defaults(func=cmd_compare)

    # list-models command
    p_list = subparsers.add_parser("list-models", help="List available sub-LLM models and pricing")
    p_list.set_defaults(func=cmd_list_models)

    # cache command
    p_cache = subparsers.add_parser("cache", help="Manage sub-LLM result cache")
    cache_sub = p_cache.add_subparsers(dest="cache_action")
    cache_sub.add_parser("stats", help="Show cache statistics")
    cache_sub.add_parser("clear", help="Clear all cached results")
    p_cache.set_defaults(func=cmd_cache)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except EnvironmentError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
