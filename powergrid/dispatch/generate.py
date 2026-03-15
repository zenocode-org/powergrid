"""Generate economic dispatch problems from PGLib-UC cases."""

import argparse
import json
import random
from pathlib import Path

import numpy as np
import requests
from scipy.optimize import linprog

from .types import DispatchProblem, Generator

PGLIB_BASE = "https://raw.githubusercontent.com/power-grid-lib/pglib-uc/master/"

RTS_CASES = [
    "rts_gmlc/2020-01-27.json",
    "rts_gmlc/2020-06-09.json",
    "rts_gmlc/2020-12-23.json",
]
FERC_CASES = [
    "ferc/2015-01-01_lw.json",
    "ferc/2015-06-01_lw.json",
]


def fetch_pglib_case(url: str) -> dict:
    """Fetch a PGLib-UC JSON case from GitHub."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_marginal_cost(piecewise: list[dict]) -> float:
    """Extract linear marginal cost ($/MWh) from piecewise production cost."""
    if len(piecewise) < 2:
        return piecewise[0]["cost"] / max(piecewise[0]["mw"], 0.01)
    mw_last = piecewise[-1]["mw"]
    mw_first = piecewise[0]["mw"]
    cost_last = piecewise[-1]["cost"]
    cost_first = piecewise[0]["cost"]
    if mw_last <= mw_first:
        return cost_first / max(mw_first, 0.01)
    return (cost_last - cost_first) / (mw_last - mw_first)


def build_generators(
    thermal: dict,
    gen_names: list[str],
    use_ramp: bool,
    prev_outputs: dict[str, float] | None = None,
) -> list[Generator]:
    """Build Generator list from PGLib thermal_generators subset."""
    prev = prev_outputs or {}
    out = []
    for name in gen_names:
        g = thermal[name]
        pmin = g["power_output_minimum"]
        pmax = g["power_output_maximum"]
        cost = extract_marginal_cost(g["piecewise_production"])
        ramp = g["ramp_up_limit"] if use_ramp else 1e9
        prev_p = prev.get(name, g.get("power_output_t0", 0.0))
        # When a generator is off in the base case and no explicit prev was supplied,
        # treat its previous output as 0. But if the caller supplied a value (e.g. a
        # ramp-constrained midpoint), honour it so the LP stays feasible.
        if g.get("unit_on_t0", 0) == 0 and name not in prev:
            prev_p = 0.0
        out.append(
            Generator(
                name=name,
                min_mw=pmin,
                max_mw=pmax,
                cost_per_mwh=cost,
                ramp_limit_mw=ramp,
                prev_output_mw=prev_p,
            )
        )
    return out


def solve_dispatch(
    generators: list[Generator],
    demand_mw: float,
) -> tuple[dict[str, float], float] | None:
    """
    Solve economic dispatch LP. Returns (schedule, cost) or None if infeasible.
    """
    n = len(generators)
    costs = np.array([g.cost_per_mwh for g in generators])
    A_eq = np.ones((1, n))
    b_eq = np.array([demand_mw])
    bounds = [(g.min_mw, g.max_mw) for g in generators]

    A_ub_list = []
    b_ub_list = []
    for i, g in enumerate(generators):
        if g.ramp_limit_mw < 1e8:
            row = np.zeros(n)
            row[i] = 1
            A_ub_list.append(row)
            b_ub_list.append(g.prev_output_mw + g.ramp_limit_mw)
            row2 = np.zeros(n)
            row2[i] = -1
            A_ub_list.append(row2)
            b_ub_list.append(-(g.prev_output_mw - g.ramp_limit_mw))

    if A_ub_list:
        A_ub = np.array(A_ub_list)
        b_ub = np.array(b_ub_list)
        res = linprog(costs, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds)
    else:
        res = linprog(costs, A_eq=A_eq, b_eq=b_eq, bounds=bounds)

    if not res.success:
        return None
    schedule = {g.name: float(res.x[i]) for i, g in enumerate(generators)}
    cost = float(np.dot(costs, res.x))
    return schedule, cost


# Synthetic generator type parameter ranges (pmin_lo, pmin_hi, pmax_lo, pmax_hi, cost_lo, cost_hi, ramp_fraction)
# ramp_fraction >= 0.5 ensures prev at midpoint can reach [pmin, pmax]
SYNTHETIC_TYPES = {
    "COAL_BASE": (100, 300, 300, 700, 20, 35, 1.0),
    "GAS_CC": (50, 150, 150, 400, 30, 55, 0.6),
    "GAS_PEAKER": (10, 30, 50, 150, 60, 120, 0.6),
}


def make_synthetic_problem(
    difficulty: str,
    n_gens: int,
    use_ramp: bool,
    problem_idx: int,
) -> DispatchProblem | None:
    """Generate a dispatch problem from synthetic generator parameters."""
    types = list(SYNTHETIC_TYPES.keys())
    generators: list[Generator] = []

    # Cost spread: easy = wide, medium = narrower, hard = tight
    cost_narrow = {"easy": 0.0, "medium": 0.3, "hard": 0.6}
    narrow = cost_narrow.get(difficulty, 0.3)

    for i in range(n_gens):
        t = random.choice(types)
        pmin_lo, pmin_hi, pmax_lo, pmax_hi, cost_lo, cost_hi, ramp_frac = SYNTHETIC_TYPES[t]
        pmin = random.uniform(pmin_lo, pmin_hi)
        pmax = random.uniform(max(pmax_lo, pmin + 10), pmax_hi)
        if pmax <= pmin:
            pmax = pmin + random.uniform(20, 100)

        # Round to integers to mimic PGLib real-world data (avoids prompt/verification mismatch)
        pmin = max(1, int(round(pmin)))
        pmax = max(pmin + 1, int(round(pmax)))

        # Narrow cost spread for harder difficulties
        cost_mid = (cost_lo + cost_hi) / 2
        cost_half = (cost_hi - cost_lo) / 2 * (1 - narrow)
        cost = random.uniform(cost_mid - cost_half, cost_mid + cost_half)
        cost = max(cost_lo, min(cost_hi, cost))

        ramp = 1e9
        prev = 0.0
        if use_ramp and ramp_frac < 1.0:
            ramp = (pmax - pmin) * ramp_frac
            ramp = max(10, int(round(ramp)))
            prev = int(round((pmin + pmax) / 2.0))

        name = f"{t}_{i + 1}"
        generators.append(
            Generator(
                name=name,
                min_mw=float(pmin),
                max_mw=float(pmax),
                cost_per_mwh=cost,
                ramp_limit_mw=ramp,
                prev_output_mw=float(prev),
            )
        )

    eff_min = sum(
        max(g.min_mw, g.prev_output_mw - g.ramp_limit_mw) for g in generators
    )
    eff_max = sum(
        min(g.max_mw, g.prev_output_mw + g.ramp_limit_mw) for g in generators
    )
    usable = eff_max - eff_min
    if usable < 1.0:
        return None

    frac_ranges = {"easy": (0.85, 1.0), "medium": (0.55, 0.80), "hard": (0.35, 0.60)}
    lo, hi = frac_ranges.get(difficulty, (0.55, 0.85))
    frac = random.uniform(lo, hi)
    demand = float(int(round(eff_min + frac * usable)))

    result = solve_dispatch(generators, demand)
    if result is None:
        return None
    schedule, cost = result

    problem_id = f"synthetic_{difficulty}_{problem_idx}_{random.randint(0, 9999)}"
    prompt = format_prompt(generators, demand)

    return DispatchProblem(
        problem_id=problem_id,
        source_case="synthetic",
        difficulty=difficulty,
        generators=generators,
        demand_mw=demand,
        prompt=prompt,
        optimal_schedule=schedule,
        optimal_cost=cost,
    )


def format_prompt(generators: list[Generator], demand_mw: float) -> str:
    """Format the dispatch problem as a markdown prompt for the LLM."""
    lines = [
        f"Demand: {demand_mw:.0f} MW",
        "",
        "| Generator | Min MW | Max MW | Cost $/MWh | Prev MW | Max Ramp MW |",
        "|-----------|--------|--------|-------------|---------|-------------|",
    ]
    for g in generators:
        ramp_str = f"{g.ramp_limit_mw:.0f}" if g.ramp_limit_mw < 1e8 else "inf"
        lines.append(
            f"| {g.name} | {g.min_mw:.0f} | {g.max_mw:.0f} | {g.cost_per_mwh:.2f} | {g.prev_output_mw:.0f} | {ramp_str} |"
        )
    lines.append("")
    example = "{" + ", ".join(f'"{g.name}": ...' for g in generators) + "}"
    lines.append(example)
    return "\n".join(lines)


def make_pglib_problem(
    data: dict,
    source_name: str,
    timestep: int,
    problem_idx: int,
) -> DispatchProblem | None:
    """Generate a dispatch problem using ALL non-must-run generators from PGLib."""
    thermal = data.get("thermal_generators", {})
    if not thermal:
        return None
    gen_names = [k for k in thermal.keys() if thermal[k].get("must_run", 0) == 0]
    if not gen_names:
        return None

    # Use actual prev_outputs from dataset
    prev_outputs = {}
    for n in gen_names:
        g = thermal[n]
        if g.get("unit_on_t0", 0) == 1:
            prev_outputs[n] = g.get("power_output_t0", g["power_output_minimum"])
        else:
            prev_outputs[n] = 0.0

    # Try with ramp first; fall back to no-ramp if LP infeasible (offline units
    # with min_mw > ramp cannot come online in one step).
    generators = build_generators(thermal, gen_names, use_ramp=True, prev_outputs=prev_outputs)
    total_min = sum(g.min_mw for g in generators)
    total_max = sum(g.max_mw for g in generators)
    demand_series = data.get("demand", [3000.0])
    demand = demand_series[timestep % len(demand_series)]
    demand = max(total_min, min(total_max, demand))
    demand = round(demand, 1)

    result = solve_dispatch(generators, demand)
    if result is None:
        generators = build_generators(thermal, gen_names, use_ramp=False, prev_outputs=None)
        result = solve_dispatch(generators, demand)
    if result is None:
        return None
    schedule, cost = result

    n = len(generators)
    difficulty = "easy" if n <= 10 else ("medium" if n <= 30 else "hard")

    problem_id = f"pglib_{source_name}_{timestep}_{problem_idx}_{random.randint(0, 9999)}"
    prompt = format_prompt(generators, demand)

    return DispatchProblem(
        problem_id=problem_id,
        source_case=source_name,
        difficulty=difficulty,
        generators=generators,
        demand_mw=demand,
        prompt=prompt,
        optimal_schedule=schedule,
        optimal_cost=cost,
    )


def generate_problem(
    data: dict,
    source_name: str,
    difficulty: str,
    n_gens: int,
    use_ramp: bool,
    timestep: int,
) -> DispatchProblem | None:
    """Generate a single dispatch problem from PGLib data (legacy, uses subset)."""
    thermal = data.get("thermal_generators", {})
    if not thermal:
        return None
    gen_names = [k for k in thermal.keys() if thermal[k].get("must_run", 0) == 0]
    if len(gen_names) < n_gens:
        return None
    selected = random.sample(gen_names, n_gens)

    prev_outputs = {}
    for n in selected:
        g = thermal[n]
        pmin, pmax = g["power_output_minimum"], g["power_output_maximum"]
        if use_ramp:
            # Seed at midpoint so each generator can ramp to anywhere in [pmin, pmax]
            # within one step (assuming ramp ≥ half the operating range, which holds
            # for all PGLib-RTS generators).
            prev_outputs[n] = (pmin + pmax) / 2.0
        elif g.get("unit_on_t0", 0) == 1:
            prev_outputs[n] = g.get("power_output_t0", pmin)
        else:
            prev_outputs[n] = 0.0

    generators = build_generators(thermal, selected, use_ramp, prev_outputs)

    # Compute the effective feasible range after ramp constraints so that the
    # sampled demand is always solvable by the LP.
    eff_min = sum(
        max(g.min_mw, g.prev_output_mw - g.ramp_limit_mw) for g in generators
    )
    eff_max = sum(
        min(g.max_mw, g.prev_output_mw + g.ramp_limit_mw) for g in generators
    )
    usable = eff_max - eff_min
    if usable < 1.0:
        return None

    # Sample demand as a fraction of effective usable capacity, keyed to difficulty.
    # Easy: 85–100% utilisation → generators near max → straightforward merit order.
    # Medium: 55–80% → meaningful load-sharing trade-offs.
    # Hard: 35–60% → LLM must decide which expensive generators to leave idle.
    frac_ranges = {"easy": (0.85, 1.0), "medium": (0.55, 0.80), "hard": (0.35, 0.60)}
    lo, hi = frac_ranges.get(difficulty, (0.55, 0.85))
    frac = random.uniform(lo, hi)
    demand = float(int(round(eff_min + frac * usable)))
    result = solve_dispatch(generators, demand)
    if result is None:
        return None
    schedule, cost = result

    problem_id = f"{source_name}_{difficulty}_{timestep}_{random.randint(0, 9999)}"
    prompt = format_prompt(generators, demand)

    return DispatchProblem(
        problem_id=problem_id,
        source_case=source_name,
        difficulty=difficulty,
        generators=generators,
        demand_mw=demand,
        prompt=prompt,
        optimal_schedule=schedule,
        optimal_cost=cost,
    )


def main():
    parser = argparse.ArgumentParser(description="Generate dispatch problems")
    parser.add_argument(
        "--output",
        type=str,
        default="problems.jsonl",
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--num-problems",
        type=int,
        default=8,
        help="Number of problems to generate",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["synthetic", "pglib"],
        default="synthetic",
        help="Problem source: synthetic (no network) or pglib (full grid from GitHub)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to output file instead of overwriting",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    args = parser.parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)

    problems: list[DispatchProblem] = []
    seen_ids: set[str] = set()

    if args.source == "synthetic":
        configs = [
            ("easy", 3, False),
            ("easy", 5, False),
            ("medium", 6, False),
            ("medium", 10, False),
            ("hard", 10, True),
            ("hard", 15, True),
        ]
        attempts = 0
        max_attempts = 500
        while len(problems) < args.num_problems and attempts < max_attempts:
            attempts += 1
            diff, n_gens, use_ramp = random.choice(configs)
            p = make_synthetic_problem(diff, n_gens, use_ramp, attempts)
            if p and p.problem_id not in seen_ids:
                problems.append(p)
                seen_ids.add(p.problem_id)

    else:  # pglib
        all_cases = [
            (f"{PGLIB_BASE}{p}", p.replace("/", "_").replace(".json", ""))
            for p in RTS_CASES + FERC_CASES
        ]
        case_data: list[tuple[dict, str]] = []
        for url, source_name in all_cases:
            try:
                data = fetch_pglib_case(url)
                case_data.append((data, source_name))
            except Exception as e:
                print(f"Warning: could not fetch {url}: {e}")

        attempts = 0
        max_attempts = 200
        while len(problems) < args.num_problems and attempts < max_attempts:
            attempts += 1
            if not case_data:
                break
            data, source_name = random.choice(case_data)
            t = random.randint(0, 47)
            p = make_pglib_problem(data, source_name, t, attempts)
            if p and p.problem_id not in seen_ids:
                problems.append(p)
                seen_ids.add(p.problem_id)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"
    existing_count = 0
    if args.append and out_path.exists():
        with open(out_path) as f:
            existing_count = sum(1 for line in f if line.strip())
    with open(out_path, mode) as f:
        for p in problems:
            f.write(p.model_dump_json() + "\n")
    total = existing_count + len(problems) if args.append else len(problems)
    print(f"Generated {len(problems)} problems to {args.output} (total: {total})")


if __name__ == "__main__":
    main()
