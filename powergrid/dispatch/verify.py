"""Verify LLM dispatch schedule against constraints and optimal cost."""

import argparse
import json
import re
from typing import Optional

from .types import DispatchProblem, Generator, VerificationResult


def parse_schedule(
    llm_output: str,
    generator_names: list[str],
) -> Optional[dict[str, float]]:
    """
    Parse LLM output into a schedule dict. Returns None if unparseable.
    Tries: json.loads, regex JSON extraction, "Name: value MW" pattern.
    """
    text = llm_output.strip()
    schedule: dict[str, float] = {}

    def try_json(s: str) -> bool:
        nonlocal schedule
        try:
            obj = json.loads(s)
            if not isinstance(obj, dict):
                return False
            for k, v in obj.items():
                if isinstance(v, (int, float)):
                    schedule[str(k)] = float(v)
                elif isinstance(v, str) and v.replace(".", "").replace("-", "").isdigit():
                    schedule[str(k)] = float(v)
            return bool(schedule)
        except (json.JSONDecodeError, ValueError, TypeError):
            return False

    if try_json(text):
        pass
    else:
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match and try_json(match.group(0)):
            pass
        else:
            for line in text.split("\n"):
                for name in generator_names:
                    pat = rf"(?:^|\s){re.escape(name)}\s*[=:]\s*([0-9]+\.?[0-9]*)\s*(?:MW)?"
                    m = re.search(pat, line, re.IGNORECASE)
                    if m:
                        schedule[name] = float(m.group(1))
                        break

    if not schedule:
        return None
    for name in generator_names:
        if name not in schedule:
            return None
    return schedule


def check_feasibility(
    schedule: dict[str, float],
    generators: list[Generator],
    demand_mw: float,
    tol: float = 1.0,
) -> tuple[bool, list[str]]:
    """
    Check if schedule satisfies constraints.
    Returns (feasible, list of violation descriptions).
    """
    violations: list[str] = []
    gen_map = {g.name: g for g in generators}

    total = sum(schedule.get(name, 0) for name in gen_map)
    if abs(total - demand_mw) > tol:
        violations.append(f"Demand balance: total={total:.1f} MW, demand={demand_mw:.1f} MW")

    for name, p in schedule.items():
        if name not in gen_map:
            continue
        g = gen_map[name]
        if p < g.min_mw - 1e-6:
            violations.append(f"{name}: output {p:.1f} < min {g.min_mw:.1f} MW")
        if p > g.max_mw + 1e-6:
            violations.append(f"{name}: output {p:.1f} > max {g.max_mw:.1f} MW")
        if g.ramp_limit_mw < 1e8:
            delta = abs(p - g.prev_output_mw)
            if delta > g.ramp_limit_mw + 1e-6:
                violations.append(
                    f"{name}: ramp {delta:.1f} MW > limit {g.ramp_limit_mw:.1f} MW"
                )

    return len(violations) == 0, violations


def compute_cost(schedule: dict[str, float], generators: list[Generator]) -> float:
    """Compute total generation cost for a schedule."""
    gen_map = {g.name: g for g in generators}
    return sum(
        schedule.get(name, 0) * gen_map[name].cost_per_mwh
        for name in gen_map
        if name in schedule
    )


def verify(
    problem: DispatchProblem,
    llm_output: str,
    tolerance: float = 0.05,
) -> VerificationResult:
    """
    Verify LLM output against problem. Success = feasible AND cost gap <= tolerance.
    """
    gen_names = [g.name for g in problem.generators]
    schedule = parse_schedule(llm_output, gen_names)

    if schedule is None:
        return VerificationResult(
            success=False,
            feasible=False,
            violations=["Could not parse LLM output into a valid schedule"],
            optimal_cost=problem.optimal_cost,
        )

    feasible, violations = check_feasibility(
        schedule, problem.generators, problem.demand_mw
    )
    llm_cost = compute_cost(schedule, problem.generators)
    gap = (llm_cost - problem.optimal_cost) / problem.optimal_cost if problem.optimal_cost > 0 else 0.0
    success = feasible and gap <= tolerance

    return VerificationResult(
        success=success,
        feasible=feasible,
        violations=violations,
        llm_cost=llm_cost,
        optimal_cost=problem.optimal_cost,
        gap=gap,
    )


def main():
    parser = argparse.ArgumentParser(description="Verify LLM dispatch response")
    parser.add_argument("--problem-id", type=str, help="Problem ID from problems.jsonl")
    parser.add_argument("--response", type=str, help="LLM response text")
    parser.add_argument("--problems-file", type=str, default="problems.jsonl")
    parser.add_argument("--tolerance", type=float, default=0.05)
    args = parser.parse_args()

    if not args.problem_id or not args.response:
        parser.error("--problem-id and --response are required")

    problems = []
    with open(args.problems_file) as f:
        for line in f:
            if line.strip():
                problems.append(DispatchProblem.model_validate(json.loads(line)))

    problem = next((p for p in problems if p.problem_id == args.problem_id), None)
    if not problem:
        print(f"Problem {args.problem_id} not found")
        return 1

    result = verify(problem, args.response, args.tolerance)
    print(result.model_dump_json(indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
