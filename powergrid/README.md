# Applied AI Engineer — Take-Home Exercise
## Power Grid Dispatch Implementation

### Task Overview

**Task (x):** Economic dispatch — given a power grid state (generators with cost curves, capacity limits, ramp constraints, and demand), produce a valid dispatch schedule that minimizes total generation cost.

**Model (y):** Configurable via OpenRouter SDK (e.g. `openai/gpt-4o`, `anthropic/claude-4.5-sonnet`). Requires `OPENROUTER_API_KEY`.

**Why 10–90% success rate:** Simple 3-generator cases are trivially greedy (rank by cost). With 10–15 generators and ramp limits from a previous state, the optimal solution is non-trivial — the LLM cannot simply sort by cost because some generators cannot ramp up fast enough.

### Data Generation Strategy

Two sources are supported via `--source`:

**Synthetic (default)** — no network calls, fully parameterized:

- **Generator types:** `COAL_BASE` (100–700 MW, $20–35/MWh), `GAS_CC` (50–400 MW, $30–55/MWh), `GAS_PEAKER` (10–150 MW, $60–120/MWh).
- **Difficulty:** Easy (3–5 gens, no ramp, wide cost spread), medium (6–10 gens, no ramp, narrower spread), hard (10–15 gens, ramp constraints, tight cost spread).
- **Output:** Each problem is a JSONL record with `prompt`, `optimal_schedule`, and `optimal_cost`.

**PGLib** — full grid from PGLib-UC (RTS-GMLC, FERC) fetched from GitHub:

- Uses **all** non-must-run generators (no truncation). Demand comes from the dataset time series.
- **Difficulty:** Labeled by generator count (≤10 easy, 10–30 medium, >30 hard).

### Verification

- Parse LLM output (JSON, regex fallback for "Name: value MW").
- Check feasibility: demand balance, capacity bounds, ramp constraints.
- Compute cost gap: `(llm_cost - optimal_cost) / optimal_cost`.
- **Success:** feasible AND gap ≤ 5% (configurable).

### Installation and Usage

```bash
# Install dependencies
uv sync

# Generate problems (default: synthetic, no network)
uv run python -m dispatch.generate --num-problems 8 --source synthetic --output problems.jsonl

# Add PGLib full-grid problems (requires network)
uv run python -m dispatch.generate --num-problems 3 --source pglib --output problems.jsonl --append

# Verify an LLM response manually
uv run python -m dispatch.verify --problem-id <id> --response '{"G1": 100, "G2": 50}' --problems-file problems.jsonl

# Evaluate model on problems (requires OPENROUTER_API_KEY)
uv run python -m dispatch.evaluate --problem-id <id> --attempts 10 --model openai/gpt-4o --tolerance 0.05

# Run attempts in parallel (faster)
uv run python -m dispatch.evaluate --problem-id <id> --attempts 10 --async
```

Set `OPENROUTER_API_KEY` for evaluation.
