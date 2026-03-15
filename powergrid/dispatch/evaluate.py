"""Evaluate LLM on dispatch problems via OpenRouter SDK."""

import argparse
import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from openrouter import OpenRouter

load_dotenv()
from .types import DispatchProblem, VerificationResult
from .verify import verify

SYSTEM_PROMPT = """You are a power grid operator. Given a dispatch problem, respond with a JSON object mapping each generator name to its output in MW. Ensure:
1. Total generation exactly equals demand
2. Each generator's output is between its Min MW and Max MW
3. Each generator's change from Prev MW does not exceed Max Ramp MW

Respond ONLY with the JSON object, no other text."""

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    if verbose:
        for name in ("httpx", "httpcore", "openrouter"):
            logging.getLogger(name).setLevel(logging.WARNING)


def load_problems(problems_file: str, problem_id: str | None) -> list[DispatchProblem]:
    with open(problems_file) as f:
        problems = [
            DispatchProblem.model_validate(json.loads(line))
            for line in f
            if line.strip()
        ]
    if problem_id:
        problems = [p for p in problems if p.problem_id == problem_id]
    return problems


async def call_llm_async(client: OpenRouter, model: str, prompt: str) -> str:
    """Call LLM via OpenRouter SDK (async)."""
    response = await client.chat.send_async(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


async def run_attempt(
    client: OpenRouter,
    problem: DispatchProblem,
    attempt: int,
    model: str,
    tolerance: float,
) -> VerificationResult:
    try:
        logger.debug(f"[{problem.problem_id}] attempt {attempt + 1}: Calling LLM...")
        response = await call_llm_async(client, model, problem.prompt)

        logger.debug(
            f"\n--- [{problem.problem_id}] attempt {attempt + 1} PROMPT ---\n{problem.prompt}\n---"
        )
        logger.debug(
            f"\n--- [{problem.problem_id}] attempt {attempt + 1} OUTPUT ---\n{response}\n---"
        )
        logger.info(
            f"[{problem.problem_id}] attempt {attempt + 1}: Verifying response..."
        )
        result = verify(problem, response, tolerance)
        status = "PASS" if result.success else "FAIL"
        logger.info(f"[{problem.problem_id}] attempt {attempt + 1}: {status}")
        if not result.success and result.violations:
            logger.info(f"  Violations: {result.violations}")
        if result.gap is not None:
            logger.info(f"  Cost gap: {100 * result.gap:.2f}%")
        return result
    except Exception as e:
        logger.exception(f"[{problem.problem_id}] attempt {attempt + 1}: ERROR - {e}")
        return VerificationResult(
            success=False,
            feasible=False,
            violations=[str(e)],
            optimal_cost=problem.optimal_cost,
        )


async def run_evaluation(
    problems: list[DispatchProblem],
    attempts: int,
    model: str,
    tolerance: float,
    use_async: bool,
) -> list[VerificationResult]:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    logger.debug(f"Connecting to OpenRouter (api_key present: {bool(api_key)})")
    async with OpenRouter(api_key=api_key) as client:
        tasks = [(p, a) for p in problems for a in range(attempts)]
        if use_async:
            return list(
                await asyncio.gather(
                    *[
                        run_attempt(client, p, a, model, tolerance)
                        for p, a in tasks
                    ],
                    return_exceptions=False,
                )
            )
        return [
            await run_attempt(client, p, a, model, tolerance) for p, a in tasks
        ]


def log_summary(results: list[VerificationResult]) -> float:
    passed = sum(1 for r in results if r.success)
    total = len(results)
    success_rate = passed / total if total else 0.0
    gaps = [r.gap for r in results if r.gap is not None]
    avg_gap = sum(gaps) / len(gaps) if gaps else None
    logger.info("--- Summary ---")
    logger.info(f"Success rate: {passed}/{total} ({100 * success_rate:.1f}%)")
    if avg_gap is not None:
        logger.info(f"Average cost gap: {100 * avg_gap:.2f}%")
    return success_rate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate LLM on dispatch problems")
    parser.add_argument(
        "--problem-id", type=str, help="Evaluate a single problem by ID"
    )
    parser.add_argument(
        "--attempts", type=int, default=10, help="Number of attempts per problem"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="openai/gpt-4o",
        help="OpenRouter model (e.g. openai/gpt-4o, anthropic/claude-4.5-sonnet)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Cost gap tolerance for success (default 5%%)",
    )
    parser.add_argument(
        "--problems-file",
        type=str,
        default="problems.jsonl",
        help="Path to problems.jsonl",
    )
    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Run attempts in parallel (faster)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show LLM outputs and debug logs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    logger.info(f"Loading problems from {args.problems_file}")
    problems = load_problems(args.problems_file, args.problem_id)
    if args.problem_id and not problems:
        logger.error(f"Problem {args.problem_id} not found")
        return 1
    if args.problem_id:
        logger.info(f"Filtered to problem(s): {[p.problem_id for p in problems]}")

    logger.info(f"Running {args.attempts} attempts per problem, model={args.model}")
    results = asyncio.run(
        run_evaluation(
            problems,
            args.attempts,
            args.model,
            args.tolerance,
            args.use_async,
        )
    )

    success_rate = log_summary(results)
    return 0 if success_rate >= 0.1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
