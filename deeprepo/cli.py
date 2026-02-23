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
from . import cli_commands
try:
    from .llm_clients import DEFAULT_SUB_MODEL
except Exception:  # pragma: no cover - environment-specific import issue
    # Fallback keeps CLI help and domain listing usable in environments where
    # llm_clients cannot import due dependency/runtime issues.
    DEFAULT_SUB_MODEL = "minimax/minimax-m2.5"

# Map short names to model strings
ROOT_MODEL_MAP = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-5-20250929",
    "minimax": "minimax/minimax-m2.5",
}


def cmd_analyze(args):
    """Run RLM analysis."""
    from .domains import get_domain

    get_domain(args.domain)  # Validate domain before deeper runtime imports/calls.
    from .rlm_scaffold import run_analysis

    root_model = ROOT_MODEL_MAP.get(args.root_model, args.root_model)

    result = run_analysis(
        codebase_path=args.path,
        verbose=not args.quiet,
        max_turns=args.max_turns,
        root_model=root_model,
        sub_model=args.sub_model,
        use_cache=not args.no_cache,
        domain=args.domain,
    )

    # Save output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    repo_name = Path(args.path).name if not args.path.startswith("http") else args.path.split("/")[-1]
    domain_prefix = f"deeprepo_{args.domain}" if args.domain != "code" else "deeprepo"

    # Save analysis
    analysis_path = output_dir / f"{domain_prefix}_{repo_name}_{timestamp}.md"
    analysis_path.write_text(result["analysis"])
    print(f"\n📄 Analysis saved to: {analysis_path}")

    # Save metrics
    metrics = {
        "mode": "rlm",
        "domain": args.domain,
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
    metrics_path = output_dir / f"{domain_prefix}_{repo_name}_{timestamp}_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"📊 Metrics saved to: {metrics_path}")
    print(f"\n{result['usage'].summary()}")


def cmd_baseline(args):
    """Run single-model baseline analysis."""
    from .domains import get_domain

    get_domain(args.domain)  # Validate domain before deeper runtime imports/calls.
    from .baseline import run_baseline

    root_model = ROOT_MODEL_MAP.get(args.root_model, args.root_model)

    result = run_baseline(
        codebase_path=args.path,
        verbose=not args.quiet,
        root_model=root_model,
        domain=args.domain,
    )

    # Save output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    repo_name = Path(args.path).name
    domain_prefix = f"baseline_{args.domain}" if args.domain != "code" else "baseline"

    analysis_path = output_dir / f"{domain_prefix}_{repo_name}_{timestamp}.md"
    analysis_path.write_text(result["analysis"])
    print(f"\n📄 Baseline analysis saved to: {analysis_path}")

    metrics = {
        "mode": "baseline",
        "domain": args.domain,
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
    metrics_path = output_dir / f"{domain_prefix}_{repo_name}_{timestamp}_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"📊 Metrics saved to: {metrics_path}")
    print(f"\n{result['usage'].summary()}")


def cmd_compare(args):
    """Run both RLM and baseline, then compare."""
    from .domains import get_domain

    domain_config = get_domain(args.domain)
    from .rlm_scaffold import run_analysis
    from .baseline import run_baseline

    rlm_model = ROOT_MODEL_MAP.get(args.root_model, args.root_model)
    baseline_model = ROOT_MODEL_MAP.get(args.baseline_model, args.baseline_model)

    # Clone once if git URL, reuse for both runs
    actual_path = args.path
    is_temp = False
    if args.path.startswith(("http://", "https://", "git@")):
        if domain_config.clone_handler is None:
            raise ValueError(
                f"Domain '{args.domain}' does not support URL inputs. Provide a local directory path."
            )
        print(f"Cloning {args.path}...")
        actual_path = domain_config.clone_handler(args.path)
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
            domain=args.domain,
        )

        print(f"\n\nRunning baseline analysis (root: {baseline_model})...")
        print("=" * 60)

        baseline_result = run_baseline(
            codebase_path=actual_path,
            verbose=not args.quiet,
            root_model=baseline_model,
            domain=args.domain,
        )
    finally:
        if is_temp:
            shutil.rmtree(actual_path, ignore_errors=True)

    # Save both
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    repo_name = Path(args.path).name
    rlm_prefix = f"deeprepo_{args.domain}" if args.domain != "code" else "deeprepo"
    baseline_prefix = f"baseline_{args.domain}" if args.domain != "code" else "baseline"

    (output_dir / f"{rlm_prefix}_{repo_name}_{timestamp}.md").write_text(rlm_result["analysis"])
    (output_dir / f"{baseline_prefix}_{repo_name}_{timestamp}.md").write_text(
        baseline_result["analysis"]
    )

    # Save metrics JSON for both sides
    rlm_metrics = {
        "mode": "rlm",
        "domain": args.domain,
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
        "domain": args.domain,
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
    (output_dir / f"{rlm_prefix}_{repo_name}_{timestamp}_metrics.json").write_text(
        json.dumps(rlm_metrics, indent=2)
    )
    (output_dir / f"{baseline_prefix}_{repo_name}_{timestamp}_metrics.json").write_text(
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


def cmd_list_domains(args):
    """List available analysis domains."""
    from .domains import DOMAIN_REGISTRY, DEFAULT_DOMAIN

    print("Available analysis domains:\n")
    for name, config in DOMAIN_REGISTRY.items():
        default_marker = " (default)" if name == DEFAULT_DOMAIN else ""
        print(f"  {name}{default_marker}")
        print(f"    {config.description}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="deeprepo — Deep intelligence powered by recursive multi-model orchestration"
    )
    parser.add_argument(
        "--version", action="version", version=f"deeprepo {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Common arguments
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("path", help="Path to data directory or git URL")
    common.add_argument("-o", "--output-dir", default="outputs", help="Output directory")
    common.add_argument("-q", "--quiet", action="store_true", help="Suppress verbose output")
    common.add_argument(
        "--domain",
        default="code",
        help="Analysis domain (default: code). Use 'list-domains' to see options.",
    )
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

    # list-domains command
    p_list_domains = subparsers.add_parser("list-domains", help="List available analysis domains")
    p_list_domains.set_defaults(func=cmd_list_domains)

    # teams command
    p_teams = subparsers.add_parser("teams", help="List available teams")
    p_teams.set_defaults(func=cli_commands.cmd_list_teams)

    # new command
    p_new = subparsers.add_parser("new", help="Create a new project with AI scaffolding")
    p_new.add_argument("--description", "-d", default=None, help="Project description")
    p_new.add_argument("--stack", "-s", default=None, help="Stack (e.g. python-fastapi)")
    p_new.add_argument("--name", "-n", default=None, help="Project name")
    p_new.add_argument("--team", default="analyst", help="Team to use (default: analyst)")
    p_new.add_argument("--output", "-o", default=".", help="Output directory (default: current)")
    p_new.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_new.set_defaults(func=cli_commands.cmd_new)

    # init command
    p_init = subparsers.add_parser("init", help="Initialize .deeprepo/ project context")
    p_init.add_argument("path", nargs="?", default=".", help="Project path (default: current directory)")
    p_init.add_argument("--team", default="analyst", help="Team to use (default: analyst)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing .deeprepo/")
    p_init.add_argument("-q", "--quiet", action="store_true", help="Suppress verbose output")
    p_init.add_argument("--root-model", default=None, help="Root model override")
    p_init.add_argument("--sub-model", default=None, help="Sub-LLM model override")
    p_init.add_argument("--max-turns", type=int, default=None, help="Max REPL turns")
    p_init.set_defaults(func=cli_commands.cmd_init)

    # context command
    p_context = subparsers.add_parser("context", help="Output cold-start prompt")
    p_context.add_argument("--path", default=".", help="Project path (default: current directory)")
    p_context.add_argument("--copy", action="store_true", help="Copy to clipboard")
    p_context.set_defaults(func=cli_commands.cmd_context)

    # refresh command
    p_refresh = subparsers.add_parser("refresh", help="Update project context")
    p_refresh.add_argument("--path", default=".", help="Project path")
    p_refresh.add_argument(
        "--full", action="store_true", help="Full re-analysis (ignore diff)"
    )
    p_refresh.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress verbose output"
    )
    p_refresh.set_defaults(func=cli_commands.cmd_refresh)

    # log command
    p_log = subparsers.add_parser("log", help="Record or view session activity")
    p_log.add_argument(
        "action",
        nargs="?",
        default=None,
        help="'show' to view entries, or omit to log a message",
    )
    p_log.add_argument(
        "message",
        nargs="?",
        default=None,
        help="Message to log (when not using 'show')",
    )
    p_log.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of entries to show (with 'show')",
    )
    p_log.add_argument("--path", default=".", help="Project path")
    p_log.set_defaults(func=cli_commands.cmd_log)

    # status command
    p_status = subparsers.add_parser("status", help="Show context health")
    p_status.add_argument("--path", default=".", help="Project path")
    p_status.set_defaults(func=cli_commands.cmd_status)

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
