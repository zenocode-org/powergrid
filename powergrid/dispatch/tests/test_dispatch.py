"""Tests for dispatch module."""

import json

from dispatch.types import DispatchProblem, Generator
from dispatch.verify import parse_schedule, verify, check_feasibility, compute_cost
from dispatch.generate import solve_dispatch, format_prompt


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
