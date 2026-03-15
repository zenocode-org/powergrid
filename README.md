# Applied AI Engineer — Take-Home Exercise
## Power Grid Dispatch Implementation

### Quick Start

```bash
uv sync
uv run python -m dispatch.generate --num-problems 8 --output problems.jsonl
uv run python -m dispatch.evaluate --attempts 2 --model anthropic/claude-sonnet-4.6
```

Set `OPENROUTER_API_KEY` for evaluation.

**Findings:** See [FINDINGS.md](powergrid/FINDINGS.md) for full analysis. Summary: GPT-5.4-pro reaches 100% success; GPT-5-nano is strong for a small model; Claude models are brittle under tight must-run constraints (`min_mw > 0`).

---

### Why This Task?

I explored an alternative: [Werewolf](../werewolf/README.md) — social deduction (manipulation + detection) with LLM-vs-LLM transcripts. It was abandoned because (1) template-based dialogue was stilted and prone to generation artifacts; (2) the Kaggle extraction approach added external dataset complexity and scope creep. Economic dispatch was chosen instead: fully programmatic generation (no external data), deterministic verification (LP ground truth), and clear failure modes (`min_mw > 0`, ramp) that calibrate across models from weaker to frontier.

---

### Iteration Notes / Calibration

**Calibration results:**

- **GPT-4o**: Fails on easy (due to rounding numbers)
- **Claude 4.6**: Passes easy but fails medium (due to min/max violation)

**Implication:** Introduced granular difficulty using `min_mw` as the primary knob to test the full range of models (from weaker to frontier).

**Medium failure mode:** LLMs correctly apply merit order but set expensive units to 0 ("off"). When generators have `min_mw > 0`, they must run at least at min—output 0 violates constraints. The model assumes "off" = 0 is valid.

**Success rates (5 problems × 1 attempt per difficulty, v1; see [FINDINGS.md](powergrid/FINDINGS.md) for v1/v2 analysis and [v1_benchmark_runs/scores.yaml](v1_benchmark_runs/scores.yaml) for raw data):**

| Model           | Easy | Medium | Hard | Very hard |
|-----------------|------|--------|------|-----------|
| GPT-4o          | 80%  | 20%    | 0%   | 0%        |
| GPT-5.4-pro     | 100% | 100%   | 100% | 100%      |
| GPT-5-nano      | 100% | 80%    | 80%  | 80%       |
| Claude Sonnet 4.5 | 80% | 80%    | 0%   | 40%       |
| Claude Sonnet 4.6 | 100% | 100%  | 0%   | 80%       |
| Mistral Large   | 0%   | 40%    | 0%   | 0%        |

**Calibration workflow:** Run `uv run python -m dispatch.benchmark --config benchmark_config.v1.yaml` to reproduce. Results are written to `v1_benchmark_runs/scores.yaml`.

**PGLib:** Tried full-grid problems from PGLib-UC (RTS-GMLC, FERC cases). It was too much—realistic grids have many more generators and network constraints, making the benchmark harder to interpret and slower to run. Kept synthetic problems as the primary calibration; PGLib is available for a dedicated run (e.g. GPT-5.4-pro at 100% on synthetic) via `benchmark_config.pglib_gpt54.yaml`.

---

### Domain Primer

**What is economic dispatch?** Balance supply and demand at minimum cost. Given generators with capacity limits and costs, assign each generator an output (MW) so that total generation equals demand and total cost is minimized.

**Key terms:**

- **MW (megawatt)**: Unit of power; demand and generator output are in MW
- **Min MW / Max MW**: Each generator has a feasible output range; output must be within [min, max]
- **Ramp limit**: Max change in MW from previous timestep; constrains how fast a unit can adjust
- **Marginal cost ($/MWh)**: Cost per unit of energy; cheaper units are dispatched first (merit order)

**Why it matters:** Real grid operators solve this continuously. Benchmark results vary by model—see [FINDINGS.md](powergrid/FINDINGS.md).

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
| `benchmark_config.v1.yaml` | Config used for shared calibration runs |
| `v1_benchmark_runs/benchmark_analysis.ipynb` | Jupyter notebook for visualizing benchmark results |
| `powergrid/FINDINGS.md` | Full benchmark analysis and key findings |
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

# Benchmark with generated problems (creates v1_benchmark_runs/ or output_dir from config)
uv run python -m dispatch.benchmark --attempts 5 --model anthropic/claude-sonnet-4.6 --run-name my-calibration

# Benchmark with YAML config (customize difficulties, models, attempts, etc.)
uv run python -m dispatch.benchmark --config benchmark_config.v1.yaml

# PGLib benchmark (GPT-5.4-pro only; requires network to fetch PGLib cases)
uv run python -m dispatch.benchmark --config benchmark_config.pglib_gpt54.yaml

# Scores are written to v1_benchmark_runs/scores.yaml (or path in config)
```

Set `OPENROUTER_API_KEY` for evaluation.

### Benchmark Config (YAML)

Use `--config benchmark_config.v1.yaml` for the shared calibration run, or `benchmark_config.example.yaml` for a template. See the config files for all options:

- **source**: `synthetic` (default) or `pglib` (full-grid from GitHub)
- **num_problems**: For pglib only; total problems to generate
- **difficulties**: List of levels (easy, medium, hard, very_hard)
- **problems_per_difficulty**: Problems to generate per level (synthetic only)
- **attempts**: LLM attempts per problem
- **models**: List of OpenRouter models to evaluate (runs benchmark for each)
- **tolerance**, **use_async**, **output_dir**, **seed**, **scores_file**

CLI arguments override config values.
