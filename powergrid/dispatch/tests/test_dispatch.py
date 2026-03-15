"""Tests for dispatch module."""

import json
import random
import tempfile
from pathlib import Path

import numpy as np

from dispatch.types import DispatchProblem, Generator
from dispatch.verify import parse_schedule, verify, check_feasibility, compute_cost
from dispatch.generate import solve_dispatch, format_prompt, make_synthetic_problem
from dispatch.evaluate import SYSTEM_PROMPT, load_problems


def test_parse_schedule_json():
    """Parse valid JSON schedule."""
    gen_names = ["G1", "G2", "G3"]
    out = parse_schedule('{"G1": 100, "G2": 50, "G3": 0}', gen_names)
    assert out == {"G1": 100.0, "G2": 50.0, "G3": 0.0}


def test_parse_schedule_with_text():
    """Extract JSON from response with surrounding text."""
    gen_names = ["G1", "G2"]
    out = parse_schedule('Here is the schedule:\n{"G1": 80, "G2": 20}', gen_names)
    assert out == {"G1": 80.0, "G2": 20.0}


def test_parse_schedule_incomplete_returns_none():
    """Missing generator returns None."""
    gen_names = ["G1", "G2", "G3"]
    out = parse_schedule('{"G1": 100, "G2": 50}', gen_names)
    assert out is None


def test_check_feasibility_valid():
    """Valid schedule passes feasibility."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=1e9),
        Generator(name="G2", min_mw=0, max_mw=100, cost_per_mwh=20, ramp_limit_mw=1e9),
    ]
    schedule = {"G1": 60.0, "G2": 40.0}
    feasible, violations = check_feasibility(schedule, gens, 100.0)
    assert feasible
    assert len(violations) == 0


def test_check_feasibility_demand_mismatch():
    """Demand mismatch fails feasibility."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=1e9),
    ]
    schedule = {"G1": 80.0}
    feasible, violations = check_feasibility(schedule, gens, 100.0)
    assert not feasible
    assert any("Demand" in v for v in violations)


def test_solve_dispatch_simple():
    """LP solver finds optimal for simple case."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=1e9),
        Generator(name="G2", min_mw=0, max_mw=100, cost_per_mwh=20, ramp_limit_mw=1e9),
    ]
    result = solve_dispatch(gens, 150.0)
    assert result is not None
    schedule, cost = result
    assert abs(schedule["G1"] + schedule["G2"] - 150) < 0.01
    assert schedule["G1"] >= 99
    assert schedule["G2"] <= 51
    assert abs(cost - (100 * 10 + 50 * 20)) < 1.0


def test_solve_dispatch_with_ramp():
    """LP solver respects ramp constraints (prev at midpoint, ramp = 50)."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=50, prev_output_mw=50),
        Generator(name="G2", min_mw=0, max_mw=100, cost_per_mwh=20, ramp_limit_mw=50, prev_output_mw=50),
    ]
    result = solve_dispatch(gens, 150.0)
    assert result is not None
    schedule, cost = result
    assert abs(schedule["G1"] + schedule["G2"] - 150) < 0.01
    assert abs(schedule["G1"] - 50) <= 50.01
    assert abs(schedule["G2"] - 50) <= 50.01


def test_verify_optimal_passes():
    """Optimal schedule passes verification."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=1e9),
        Generator(name="G2", min_mw=0, max_mw=100, cost_per_mwh=20, ramp_limit_mw=1e9),
    ]
    optimal = {"G1": 100.0, "G2": 50.0}
    problem = DispatchProblem(
        problem_id="test",
        source_case="test",
        difficulty="easy",
        generators=gens,
        demand_mw=150.0,
        prompt="test",
        optimal_schedule=optimal,
        optimal_cost=2000.0,
    )
    result = verify(problem, json.dumps(optimal), tolerance=0.05)
    assert result.success
    assert result.feasible
    assert result.gap is not None and result.gap <= 0.05


def test_verify_infeasible_fails():
    """Infeasible schedule fails verification."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=1e9),
    ]
    problem = DispatchProblem(
        problem_id="test",
        source_case="test",
        difficulty="easy",
        generators=gens,
        demand_mw=100.0,
        prompt="test",
        optimal_schedule={"G1": 100.0},
        optimal_cost=1000.0,
    )
    result = verify(problem, '{"G1": 50}', tolerance=0.05)
    assert not result.success
    assert not result.feasible


def test_format_prompt_output():
    """Final prompt from generated problem has demand, table, and example JSON."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=1e9),
        Generator(name="G2", min_mw=0, max_mw=100, cost_per_mwh=20, ramp_limit_mw=50, prev_output_mw=25),
    ]
    prompt = format_prompt(gens, 150.0)
    assert "Demand: 150 MW" in prompt
    assert "| Generator | Min MW | Max MW | Cost $/MWh | Prev MW | Max Ramp MW |" in prompt
    assert "| G1 |" in prompt
    assert "| G2 |" in prompt
    assert '{"G1": ..., "G2": ...}' in prompt


def test_evaluate_system_prompt():
    """Evaluate system prompt instructs power grid operator with constraints."""
    assert "power grid operator" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT
    assert "demand" in SYSTEM_PROMPT.lower()
    assert "Min MW" in SYSTEM_PROMPT or "min" in SYSTEM_PROMPT.lower()
    assert "Max Ramp" in SYSTEM_PROMPT or "ramp" in SYSTEM_PROMPT.lower()


def test_evaluate_user_message_contains_demand():
    """User message (problem.prompt) contains the demand."""
    gens = [
        Generator(name="G1", min_mw=0, max_mw=100, cost_per_mwh=10, ramp_limit_mw=1e9),
        Generator(name="G2", min_mw=0, max_mw=100, cost_per_mwh=20, ramp_limit_mw=1e9),
    ]
    problem = DispatchProblem(
        problem_id="prompt_test",
        source_case="test",
        difficulty="easy",
        generators=gens,
        demand_mw=237.0,
        prompt=format_prompt(gens, 237.0),
        optimal_schedule={"G1": 100.0, "G2": 137.0},
        optimal_cost=3740.0,
    )
    user_message = problem.prompt
    assert "Demand: 237 MW" in user_message


def test_load_problems_filters_by_problem_id():
    """load_problems filters to single problem when problem_id is given."""
    problems = [
        DispatchProblem(
            problem_id="p1",
            source_case="test",
            difficulty="easy",
            generators=[],
            demand_mw=100,
            prompt="",
            optimal_schedule={},
            optimal_cost=0,
        ),
        DispatchProblem(
            problem_id="p2",
            source_case="test",
            difficulty="easy",
            generators=[],
            demand_mw=200,
            prompt="",
            optimal_schedule={},
            optimal_cost=0,
        ),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for p in problems:
            f.write(p.model_dump_json() + "\n")
        path = f.name
    try:
        loaded = load_problems(path, problem_id="p2")
        assert len(loaded) == 1
        assert loaded[0].problem_id == "p2"
        assert loaded[0].demand_mw == 200
        loaded_all = load_problems(path, problem_id=None)
        assert len(loaded_all) == 2
    finally:
        Path(path).unlink(missing_ok=True)


def test_difficulty_easy_all_min_zero():
    """Easy problems have all generators with min_mw=0."""
    random.seed(42)
    np.random.seed(42)
    for _ in range(5):
        p = make_synthetic_problem("easy", problem_idx=hash(str(_)) % 100000)
        assert p is not None
        for g in p.generators:
            assert g.min_mw == 0, f"Easy problem has generator with min_mw={g.min_mw}"


def test_difficulty_medium_one_to_three_must_run():
    """Medium problems have 1-3 generators with min_mw>0."""
    random.seed(43)
    np.random.seed(43)
    for _ in range(10):
        p = make_synthetic_problem("medium", problem_idx=hash(str(_)) % 100000)
        if p is None:
            continue
        n_must_run = sum(1 for g in p.generators if g.min_mw > 0)
        assert 1 <= n_must_run <= 3, f"Medium has {n_must_run} must-run, expected 1-3"


def test_difficulty_hard_all_must_run():
    """Hard problems have all generators with min_mw>0."""
    random.seed(44)
    np.random.seed(44)
    for _ in range(5):
        p = make_synthetic_problem("hard", problem_idx=hash(str(_)) % 100000)
        assert p is not None
        for g in p.generators:
            assert g.min_mw > 0, f"Hard problem has generator with min_mw=0"


def test_difficulty_very_hard_all_must_run_and_has_ramp():
    """Very hard problems have all min_mw>0 and ramp constraints."""
    random.seed(45)
    np.random.seed(45)
    for _ in range(5):
        p = make_synthetic_problem("very_hard", problem_idx=hash(str(_)) % 100000)
        assert p is not None
        for g in p.generators:
            assert g.min_mw > 0
        n_with_ramp = sum(1 for g in p.generators if g.ramp_limit_mw < 1e8)
        assert n_with_ramp > 0, "Very hard should have ramp constraints"
