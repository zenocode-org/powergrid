"""Tests for benchmark module."""

import tempfile
from pathlib import Path

import yaml

from dispatch.benchmark import (
    generate_problems_for_benchmark,
    load_config,
    _write_scores_file,
)
from dispatch.types import DispatchProblem


def test_generate_problems_for_benchmark():
    """generate_problems_for_benchmark produces 2 per difficulty, all valid."""
    problems = generate_problems_for_benchmark(2, seed=42)
    assert len(problems) == 8
    difficulties = ["easy", "medium", "hard", "very_hard"]
    for diff in difficulties:
        count = sum(1 for p in problems if p.difficulty == diff)
        assert count == 2, f"Expected 2 {diff} problems, got {count}"
    for p in problems:
        DispatchProblem.model_validate(p.model_dump())


def test_load_config():
    """load_config reads YAML and returns dict."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("difficulties:\n  - easy\n  - medium\n")
        path = f.name
    try:
        cfg = load_config(path)
        assert cfg["difficulties"] == ["easy", "medium"]
    finally:
        Path(path).unlink(missing_ok=True)


def test_write_scores_file():
    """_write_scores_file creates YAML with runs and by_difficulty."""
    all_scores = [
        {
            "model": "openai/gpt-4o",
            "run_name": "openai_gpt-4o",
            "timestamp": "2026-03-15_12-00-00",
            "attempts_per_problem": 3,
            "by_difficulty": {
                "easy": {"passed": 6, "total": 6, "success_rate": 1.0, "avg_cost_gap": 0.0},
                "medium": {"passed": 0, "total": 6, "success_rate": 0.0, "avg_cost_gap": 0.1},
            },
        }
    ]
    with tempfile.TemporaryDirectory() as tmp:
        scores_path = Path(tmp) / "scores.yaml"
        _write_scores_file(str(scores_path), all_scores)
        assert scores_path.exists()
        with open(scores_path) as f:
            data = yaml.safe_load(f)
        assert "runs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["model"] == "openai/gpt-4o"
        assert "by_difficulty" in data["runs"][0]
        assert data["runs"][0]["by_difficulty"]["easy"]["success_rate"] == 1.0
