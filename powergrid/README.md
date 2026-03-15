# Applied AI Engineer — Take-Home Exercise
## Power Grid Dispatch Implementation

### Quick Start

```bash
uv sync
uv run python -m dispatch.generate --num-problems 8 --output problems.jsonl
uv run python -m dispatch.evaluate --attempts 2 --model anthropic/claude-sonnet-4.6
```

Set `OPENROUTER_API_KEY` for evaluation.

---

### Iteration Notes / Calibration

**Calibration results:**

- **GPT-4o**: Fails on easy (due to rounding numbers)
- **Claude 4.6**: Passes easy but fails medium (due to min/max violation)

**Implication:** Introduced granular difficulty using `min_mw` as the primary knob to test the full range of models (from weaker to frontier).

**Medium failure mode:** LLMs correctly apply merit order but set expensive units to 0 ("off"). When generators have `min_mw > 0`, they must run at least at min—output 0 violates constraints. The model assumes "off" = 0 is valid.

---

### Domain Primer

**What is economic dispatch?** Balance supply and demand at minimum cost. Given generators with capacity limits and costs, assign each generator an output (MW) so that total generation equals demand and total cost is minimized.

**Key terms:**

- **MW (megawatt)**: Unit of power; demand and generator output are in MW
- **Min MW / Max MW**: Each generator has a feasible output range; output must be within [min, max]
- **Ramp limit**: Max change in MW from previous timestep; constrains how fast a unit can adjust
- **Marginal cost ($/MWh)**: Cost per unit of energy; cheaper units are dispatched first (merit order)

**Why it matters:** Real grid operators solve this continuously. LLMs struggle when `min_mw > 0` (must-run) or ramp constraints apply—simple "greedy by cost" fails.

---

### Difficulty Definition

| Level | Generators | min_mw > 0 | Ramp |
|-------|------------|------------|------|
| **Easy** | 3–5 | None (all can be off) | No |
| **Medium** | 6–10 | 1–3 must run | No |
| **Hard** | 6–10 | All must run | No |
| **Very hard** | 10 | All must run | Yes |

- **Easy**: All `min_mw = 0` — any generator can be off. Merit order suffices.
- **Medium**: 1–3 generators must run; rest can be off. LLM must learn that some units cannot be set to 0.
- **Hard**: All generators must run. Same count as medium; complexity from min/max.
- **Very hard**: All must run + ramp constraints.

---

### Task Overview

**Task:** Economic dispatch — given a power grid state (generators with cost curves, capacity limits, ramp constraints, and demand), produce a valid dispatch schedule that minimizes total generation cost.

**Model:** Configurable via OpenRouter SDK (e.g. `openai/gpt-4o`, `anthropic/claude-sonnet-4.6`). Requires `OPENROUTER_API_KEY`.

### Verification

- Parse LLM output (JSON, regex fallback for "Name: value MW").
- Check feasibility: demand balance, capacity bounds, ramp constraints.
- Compute cost gap: `(llm_cost - optimal_cost) / optimal_cost`.
- **Success:** feasible AND gap ≤ 5% (configurable).

### Interpreting Results

- **PASS**: Schedule is feasible AND cost gap ≤ tolerance (default 5%).
- **FAIL**: Violations (e.g. demand mismatch, min/max violation) or cost gap too high.
- **Success rate**: Fraction of attempts that pass.
- **Cost gap**: How much more expensive the LLM schedule is vs optimal.

---

### Project Structure

| Module | Purpose |
|--------|---------|
| `dispatch/generate.py` | Generate synthetic problems by difficulty |
| `dispatch/verify.py` | Verify LLM output against constraints |
| `dispatch/evaluate.py` | Run LLM on problems via OpenRouter |
| `dispatch/benchmark.py` | Generate and evaluate with run history |
| `benchmark_config.example.yaml` | Example YAML config for benchmark |
| `dispatch/types.py` | Pydantic models |

---

### Installation and Usage

```bash
# Install dependencies
uv sync

# Generate problems (default: synthetic, no network)
uv run python -m dispatch.generate --num-problems 8 --source synthetic --output problems.jsonl

# Generate specific difficulty
uv run python -m dispatch.generate --num-problems 4 --difficulty easy --output problems.jsonl

# Add PGLib full-grid problems (requires network)
uv run python -m dispatch.generate --num-problems 3 --source pglib --output problems.jsonl --append

# Verify an LLM response manually
uv run python -m dispatch.verify --problem-id <id> --response '{"G1": 100, "G2": 50}' --problems-file problems.jsonl

# Evaluate model on problems (requires OPENROUTER_API_KEY)
uv run python -m dispatch.evaluate --attempts 10 --model openai/gpt-4o --tolerance 0.05

# Evaluate single problem
uv run python -m dispatch.evaluate --problem-id <id> --attempts 5 --model anthropic/claude-sonnet-4.6

# Run attempts in parallel (faster)
uv run python -m dispatch.evaluate --attempts 10 --async

# Benchmark with generated problems (creates benchmark_runs/<timestamp>_<run_name>_problems.jsonl)
uv run python -m dispatch.benchmark --attempts 5 --model anthropic/claude-sonnet-4.6 --run-name my-calibration

# Benchmark with YAML config (customize difficulties, models, attempts, etc.)
uv run python -m dispatch.benchmark --config benchmark_config.yaml

# Scores are written to benchmark_runs/scores.yaml by default (or path in config)
```

Set `OPENROUTER_API_KEY` for evaluation.

### Benchmark Config (YAML)

Use `--config benchmark_config.yaml` to customize the benchmark. See `benchmark_config.example.yaml` for all options:

- **difficulties**: List of levels (easy, medium, hard, very_hard)
- **problems_per_difficulty**: Problems to generate per level
- **attempts**: LLM attempts per problem
- **models**: List of OpenRouter models to evaluate (runs benchmark for each)
- **tolerance**, **use_async**, **output_dir**, **seed**, **scores_file**

CLI arguments override config values.
