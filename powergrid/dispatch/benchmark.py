"""Benchmark: generate problems per run, store with timestamp, evaluate by difficulty."""

import argparse
import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()
from .generate import make_synthetic_problem, generate_pglib_problems
from .types import DispatchProblem, VerificationResult
from .evaluate import run_evaluation, setup_logging

logger = logging.getLogger(__name__)

DEFAULT_DIFFICULTIES = ["easy", "medium", "hard", "very_hard"]


def _model_to_run_name(model: str) -> str:
    """Derive a filesystem-safe run name from model string."""
    return model.replace("/", "_").replace(" ", "-")


def _timestamp() -> str:
    """ISO-like timestamp for filenames."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def load_config(path: str) -> dict:
    """Load benchmark config from YAML file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def generate_problems_for_benchmark(
    problems_per_difficulty: int,
    difficulties: list[str] | None = None,
    seed: int = 42,
    source: str = "synthetic",
    num_problems: int | None = None,
) -> list[DispatchProblem]:
    """Generate problems for benchmarking. source: 'synthetic' or 'pglib'."""
    import random
    import numpy as np

    if source == "pglib":
        n = num_problems or 10
        logger.info("Generating %d PGLib problems...", n)
        return generate_pglib_problems(n, seed=seed)

    random.seed(seed)
    np.random.seed(seed)
    difficulties = difficulties or DEFAULT_DIFFICULTIES
    problems: list[DispatchProblem] = []
    seen_ids: set[str] = set()

    for diff in difficulties:
        attempts = 0
        max_attempts = 200
        while len([p for p in problems if p.difficulty == diff]) < problems_per_difficulty:
            attempts += 1
            if attempts > max_attempts:
                logger.warning(
                    "Could not generate %d %s problems after %d attempts",
                    problems_per_difficulty,
                    diff,
                    max_attempts,
                )
                break
            p = make_synthetic_problem(diff, problem_idx=attempts)
            if p and p.problem_id not in seen_ids:
                problems.append(p)
                seen_ids.add(p.problem_id)

    return problems


def _run_single_model(
    problems: list[DispatchProblem],
    model: str,
    attempts: int,
    tolerance: float,
    use_async: bool,
    out_dir: Path,
    timestamp: str,
    run_name: str,
    difficulties: list[str],
) -> dict:
    """Run evaluation for one model and return results data."""
    results: list[VerificationResult] = asyncio.run(
        run_evaluation(problems, attempts, model, tolerance, use_async)
    )

    results_by_diff: dict[str, list[VerificationResult]] = defaultdict(list)
    for i, r in enumerate(results):
        problem_idx = i // attempts
        if problem_idx < len(problems):
            diff = problems[problem_idx].difficulty
            results_by_diff[diff].append(r)

    results_data = {
        "timestamp": timestamp,
        "run_name": run_name,
        "model": model,
        "attempts_per_problem": attempts,
        "by_difficulty": {
            diff: {
                "passed": sum(1 for r in res if r.success),
                "total": len(res),
                "success_rate": sum(1 for r in res if r.success) / len(res) if res else 0,
                "avg_cost_gap": (
                    sum(r.gap for r in res if r.gap is not None)
                    / len([r for r in res if r.gap is not None])
                    if any(r.gap is not None for r in res)
                    else None
                ),
            }
            for diff, res in results_by_diff.items()
        },
    }

    results_path = out_dir / f"{timestamp}_{run_name}_results.json"
    with open(results_path, "w") as f:
        json.dump(results_data, f, indent=2)
    logger.info("Saved results to %s", results_path)

    return results_data


def _write_scores_file(scores_file: str, all_scores: list[dict]) -> None:
    """Write aggregated scores to YAML file."""
    path = Path(scores_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    scores_data = {
        "runs": [
            {
                "model": r["model"],
                "run_name": r["run_name"],
                "timestamp": r["timestamp"],
                "attempts_per_problem": r["attempts_per_problem"],
                "by_difficulty": {
                    diff: {
                        "passed": d["passed"],
                        "total": d["total"],
                        "success_rate": round(d["success_rate"], 4),
                        "avg_cost_gap_pct": (
                            round(100 * d["avg_cost_gap"], 2) if d["avg_cost_gap"] is not None else None
                        ),
                    }
                    for diff, d in r["by_difficulty"].items()
                },
                "overall": {
                    "passed": sum(d["passed"] for d in r["by_difficulty"].values()),
                    "total": sum(d["total"] for d in r["by_difficulty"].values()),
                    "success_rate": (
                        sum(d["passed"] for d in r["by_difficulty"].values())
                        / sum(d["total"] for d in r["by_difficulty"].values())
                        if r["by_difficulty"]
                        else 0
                    ),
                },
            }
            for r in all_scores
        ]
    }

    with open(path, "w") as f:
        yaml.dump(scores_data, f, default_flow_style=False, sort_keys=False)
    logger.info("Saved scores to %s", path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark: generate problems, store with timestamp, evaluate by difficulty"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to YAML config file (overrides defaults; CLI overrides config)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=None,
        help="Number of attempts per problem",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="OpenRouter model (overrides config models if set)",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Run identifier (default: derived from model)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        choices=["synthetic", "pglib"],
        help="Problem source: synthetic or pglib (overrides config)",
    )
    parser.add_argument(
        "--num-problems",
        type=int,
        default=None,
        help="For pglib: total problems to generate (overrides config)",
    )
    parser.add_argument(
        "--problems-per-difficulty",
        type=int,
        default=None,
        help="Problems to generate per difficulty level (synthetic only)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for run outputs",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="Cost gap tolerance for success",
    )
    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Run attempts in parallel",
    )
    parser.add_argument(
        "--scores-file",
        type=str,
        default=None,
        help="Path to write scores YAML (default from config or benchmark_runs/scores.yaml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    args = parser.parse_args()

    # Load config
    cfg: dict = {}
    if args.config:
        cfg = load_config(args.config)
        logger.info("Loaded config from %s", args.config)

    # Merge: config defaults -> CLI overrides
    def _get(key: str, default: any, cli_val: any = None) -> any:
        if cli_val is not None:
            return cli_val
        return cfg.get(key, default)

    source = _get("source", "synthetic", args.source)
    num_problems = _get("num_problems", None, args.num_problems)
    difficulties = _get("difficulties", DEFAULT_DIFFICULTIES)
    problems_per_difficulty = _get("problems_per_difficulty", 2, args.problems_per_difficulty)
    attempts = _get("attempts", 5, args.attempts)
    tolerance = _get("tolerance", 0.05, args.tolerance)
    use_async = args.use_async or _get("use_async", False)
    output_dir = _get("output_dir", "benchmark_runs", args.output_dir)
    run_name_override = _get("run_name", None, args.run_name)
    seed = _get("seed", 42)
    # scores_file: from CLI overrides; config can set path or null to skip
    if args.scores_file is not None:
        scores_file = args.scores_file
    elif "scores_file" in cfg:
        scores_file = cfg["scores_file"]  # None = skip
    else:
        scores_file = str(Path(output_dir) / "scores.yaml")

    # Models: CLI --model overrides config; support single or list
    config_models = cfg.get("models") or cfg.get("model")
    if config_models and not isinstance(config_models, list):
        config_models = [config_models]
    models = [args.model] if args.model else (config_models or ["openai/gpt-4o"])

    setup_logging(args.verbose)
    timestamp = _timestamp()

    # Generate problems
    if source == "pglib":
        logger.info("Generating PGLib problems (num_problems=%s)...", num_problems or 10)
    else:
        logger.info(
            "Generating %d problems per difficulty (%s)...",
            problems_per_difficulty,
            ", ".join(difficulties),
        )
    problems = generate_problems_for_benchmark(
        problems_per_difficulty,
        difficulties=difficulties,
        seed=seed,
        source=source,
        num_problems=num_problems,
    )
    if not problems:
        logger.error("No problems generated")
        return 1

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Store problems (shared across models)
    base_run_name = run_name_override or _model_to_run_name(models[0])
    problems_path = out_dir / f"{timestamp}_{base_run_name}_problems.jsonl"
    with open(problems_path, "w") as f:
        for p in problems:
            f.write(p.model_dump_json() + "\n")
    logger.info("Saved %d problems to %s", len(problems), problems_path)

    all_scores: list[dict] = []

    for model in models:
        run_name = run_name_override or _model_to_run_name(model)
        logger.info(
            "Running evaluation: %d attempts per problem, model=%s", attempts, model
        )
        print(f"\n--- Model: {model} ---")

        # For pglib, derive difficulties from generated problems
        effective_diffs = (
            sorted(set(p.difficulty for p in problems))
            if source == "pglib"
            else difficulties
        )
        results_data = _run_single_model(
            problems, model, attempts, tolerance, use_async,
            out_dir, timestamp, run_name, effective_diffs,
        )
        all_scores.append(results_data)

        # Print summary
        for diff in effective_diffs:
            d = results_data["by_difficulty"].get(diff)
            if not d:
                continue
            passed, total = d["passed"], d["total"]
            rate = 100 * passed / total if total else 0
            gap_str = ""
            if d.get("avg_cost_gap") is not None:
                gap_str = f", avg cost gap: {100 * d['avg_cost_gap']:.2f}%"
            print(f"  {diff}: {passed}/{total} ({rate:.1f}%){gap_str}")

    # Write scores file
    if scores_file:
        _write_scores_file(scores_file, all_scores)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
