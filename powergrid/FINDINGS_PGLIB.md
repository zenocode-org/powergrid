# PGLib Benchmark — Real-World Data

LLM benchmark for **economic dispatch** using **PGLib-UC** cases (RTS-GMLC, FERC).

Problems are generated from real grid data with 72+ generators per case, ramp constraints, and realistic cost curves.

---

## Results

From `pglib_benchmark_runs/scores.yaml`:

```yaml
runs:
- model: openai/gpt-5.4-pro
  run_name: openai_gpt-5.4-pro
  timestamp: 2026-03-15_20-38-30
  attempts_per_problem: 1
  by_difficulty:
    hard:
      passed: 9
      total: 10
      success_rate: 0.9
      avg_cost_gap_pct: -0.0
  overall:
    passed: 9
    total: 10
    success_rate: 0.9
```

---

## Summary

| Model         | Success | Problems |
| ------------- | ------- | -------- |
| GPT-5.4-pro   | 90%     | 10       |

PGLib problems are classified as **hard** (72 generators, ramp limits). GPT-5.4-pro reaches 90% success on real-world data, slightly below its 100% on synthetic calibration.

---

## Run

```bash
uv run python -m dispatch.benchmark --config benchmark_config.pglib_gpt54.yaml
```
