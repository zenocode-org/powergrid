---
marp: true
theme: default
paginate: true
title: Powergrid Benchmark Findings
description: Benchmark findings for the Power Grid Dispatch project
---

# Powergrid Project
## Benchmark Findings Presentation

### Economic dispatch benchmark
### Two experiments: v1 and v2

- **v1:** `powergrid/v1_benchmark_runs/scores.yaml` (5 problems/diff, 5% tolerance)
- **v2:** `powergrid/v2_benchmark_runs/scores.yaml` (15 problems/diff, 1% tolerance)
- Project overview: `powergrid/README.md`
- Date: 2026-03-15

---

# Executive Summary

- The benchmark tests whether LLMs can solve constrained economic dispatch, not just rank generators by cost.
- The core difficulty knob is `min_mw > 0`: models often know the merit order, but still fail by turning expensive generators fully off when they are required to stay on.
- **GPT-5.4-pro** is fully reliable: 100% in both v1 (20/20) and v2 (60/60).
- **GPT-5-nano** is the strongest smaller model: 85% (v1) and 88% (v2); v2 confirms it reaches 100% on hard.
- **Claude models** show brittle behavior: v1 suggested Claude 4.6 was strong on medium; v2 (15 problems) revealed a 20% medium pass rate. Both Sonnet and Opus show very_hard > hard.
- v2 uses stricter tolerance (1%) and more problems; it confirms and refines v1 patterns.

---

# What Problem Are We Solving?

## Economic dispatch

- Goal: allocate generator outputs so total supply exactly matches demand at minimum total cost.
- Each generator has a feasible operating range: `min_mw <= output <= max_mw`.
- Some generators also have ramp constraints, limiting how much they can change from the previous timestep.
- The benchmark asks an LLM to output a dispatch schedule for a single grid state.

## Why this domain works well for benchmarking

- It is operationally realistic.
- It has deterministic verification.
- It has a clean optimal reference solution from linear programming.
- It exposes failure modes that simple "cheapest first" reasoning does not solve.

---

# Why This Is A Good LLM Benchmark

- Easy cases reward basic cost ordering.
- Medium and hard cases test constraint reasoning under `min_mw > 0`.
- Very hard adds temporal reasoning through ramp limits.
- The benchmark is fully programmatic: no human grading and no external annotation pipeline.

## Practical interpretation

- A model cannot pass by sounding plausible.
- It must produce a parseable, feasible, near-optimal schedule.

---

# What The Model Sees

- Demand in MW
- A table of generators with:
- `Min MW`
- `Max MW`
- `Cost $/MWh`
- `Prev MW`
- `Max Ramp MW`
- A required output format shaped like JSON

## Example task

```json
{"GEN_A": 120, "GEN_B": 85, "GEN_C": 40}
```

---

# How Problems Are Generated

## Synthetic benchmark design

- Problems are generated from synthetic generator templates representing base load, combined-cycle gas, and peaker units.
- Demand is sampled so every generated problem is solvable by the optimizer.
- The optimal dispatch and optimal cost are computed ahead of time with a linear program.

## Difficulty ladder

| Difficulty | Generators | Must-run units | Ramp limits |
|---|---:|---:|---:|
| Easy | 3 to 5 | None | No |
| Medium | 6 to 10 | 1 to 3 | No |
| Hard | 6 to 10 | All | No |
| Very hard | 10 | All | Yes |

---

# What Makes The Benchmark Hard

## Main failure mode

- Many models apply merit order correctly.
- They then set some expensive generators to `0 MW`.
- That is valid in `easy`, but invalid once a unit has `min_mw > 0`.

## Why this matters

- The benchmark distinguishes "cost ranking" from true constrained optimization.
- `hard` is especially revealing because every generator must remain within a non-zero feasible band.

---

# How We Verify Outputs

Once we have a schedule (generator name → MW), we check three mathematical conditions.

---

## Feasibility 1: Demand balance

$$\sum_{\text{gens}} p_i = D \quad \text{(within 1 MW)}$$

- Total generation must equal demand.
- Violation: under- or over-generation.

---

## Feasibility 2: Capacity bounds

$$\min_i \leq p_i \leq \max_i \quad \forall \text{ generators } i$$

- Each generator must stay within its operating range.
- Violation: output below min (e.g. 0 when must-run) or above max.

---

## Feasibility 3: Ramp limits (when applicable)

$$|p_i - p_i^{\text{prev}}| \leq \text{ramp}_i \quad \forall i \text{ with ramp}$$

- Output cannot change more than the ramp limit from the previous timestep.
- Violation: too large a step up or down.

---

## Optimality: Cost gap

$$\text{cost} = \sum_i p_i \cdot c_i \quad \text{where } c_i = \text{cost per MWh}$$

$$\text{gap} = \frac{\text{llm\_cost} - \text{optimal\_cost}}{\text{optimal\_cost}}$$

- **Success:** feasible (all three checks pass) and gap ≤ tolerance.
- **v1:** tolerance 5% | **v2:** tolerance 1%

---

## Sources

- **Standard formulation:** Wood & Wollenberg, *Power Generation, Operation and Control* (Wiley), Ch. 3 — economic dispatch with power balance, capacity bounds, and ramp constraints.
- **Implementation:** `powergrid/dispatch/verify.py` (feasibility, cost, gap) and `generate.py` (LP for optimal reference).

---

# Two Experiments

| | v1 | v2 |
|---|---|---|
| Problems per difficulty | 5 | 15 |
| Total tasks per model | 20 | 60 |
| Cost gap tolerance | 5% | 1% |
| Models | gpt-4o, gpt-5.4-pro, gpt-5-nano, claude 4.5, claude 4.6, mistral-large | gpt-5.4-pro, gpt-5-nano, claude 4.5, claude 4.6, claude-opus-4.6 |

## Why two runs?

- v1: initial calibration, broad model coverage.
- v2: larger sample, stricter tolerance, adds Claude Opus; drops gpt-4o and mistral-large.

---

# Important Scoring Detail

- The benchmark's `success_rate` is the primary score.
- `avg_cost_gap_pct` is useful, but it is averaged over all parseable attempts, including infeasible ones.
- That means negative average gaps do not imply a model beat the optimum.
- In practice, negative gaps usually mean the model produced an infeasible but artificially cheap schedule, such as under-generating or violating minimum output constraints.

## Takeaway

- Use pass rate to rank models.
- Use cost gap to diagnose the type of failure.

---

# Benchmark Setup

## Configs

| | v1 | v2 |
|---|---|---|
| Config file | `benchmark_config.v1.yaml` | `benchmark_config.v2.yaml` |
| Problems per difficulty | 5 | 15 |
| Attempts per problem | 1 | 1 |
| Tolerance | 5% | 1% |
| Seed | 1 | 1 |

## Models

- **v1:** gpt-4o, gpt-5.4-pro, gpt-5-nano, claude 4.5, claude 4.6, mistral-large
- **v2:** gpt-5.4-pro, gpt-5-nano, claude 4.5, claude 4.6, claude-opus-4.6

---

# Overall Results — v1 (5% tolerance, 20 tasks)

| Model | Passed | Total | Success Rate |
|---|---:|---:|---:|
| `openai/gpt-5.4-pro` | 20 | 20 | 100% |
| `openai/gpt-5-nano` | 17 | 20 | 85% |
| `anthropic/claude-sonnet-4.6` | 14 | 20 | 70% |
| `anthropic/claude-sonnet-4.5` | 10 | 20 | 50% |
| `openai/gpt-4o` | 5 | 20 | 25% |
| `mistralai/mistral-large-2512` | 2 | 20 | 10% |

---

# Overall Results — v2 (1% tolerance, 60 tasks)

| Model | Passed | Total | Success Rate |
|---|---:|---:|---:|
| `openai/gpt-5.4-pro` | 60 | 60 | 100% |
| `openai/gpt-5-nano` | 53 | 60 | 88% |
| `anthropic/claude-opus-4.6` | 29 | 60 | 48% |
| `anthropic/claude-sonnet-4.6` | 25 | 60 | 42% |
| `anthropic/claude-sonnet-4.5` | 17 | 60 | 28% |

## v2 insight

- Stricter tolerance (1%) and larger sample confirm GPT-5.4-pro as fully reliable and GPT-5-nano as strong.
- Claude models drop under stricter tolerance; v2 reveals Claude 4.6's medium weakness (20%) that v1's small sample masked (100%).

---

# Success Rate By Difficulty — v1

| Model | Easy | Medium | Hard | Very hard |
|---|---:|---:|---:|---:|
| `openai/gpt-4o` | 80% | 20% | 0% | 0% |
| `openai/gpt-5.4-pro` | 100% | 100% | 100% | 100% |
| `openai/gpt-5-nano` | 100% | 80% | 80% | 80% |
| `anthropic/claude-sonnet-4.5` | 80% | 80% | 0% | 40% |
| `anthropic/claude-sonnet-4.6` | 100% | 100% | 0% | 80% |
| `mistralai/mistral-large-2512` | 0% | 40% | 0% | 0% |

---

# Success Rate By Difficulty — v2

| Model | Easy | Medium | Hard | Very hard |
|---|---:|---:|---:|---:|
| `openai/gpt-5.4-pro` | 100% | 100% | 100% | 100% |
| `openai/gpt-5-nano` | 100% | 80% | **100%** | 73% |
| `anthropic/claude-opus-4.6` | 73% | 40% | 7% | **73%** |
| `anthropic/claude-sonnet-4.6` | 100% | **20%** | 7% | 40% |
| `anthropic/claude-sonnet-4.5` | 87% | 27% | 0% | 0% |

## Cross-experiment pattern

- **very_hard > hard** for Claude: confirmed in v2 (Sonnet 40% vs 7%; Opus 73% vs 7%).
- **GPT-5-nano on hard:** 100% in v2 (15/15) — more robust than v1's 80% suggested.

---

# Reading The Difficulty Curve

## Easy

- Mostly tests whether the model follows merit order.
- Most capable models handle this well.

## Medium

- Introduces a small number of must-run generators.
- This is where weaker models start making invalid "turn it off" decisions.

## Hard

- Every generator has `min_mw > 0`.
- This sharply increases reasoning difficulty because zero output is no longer a safe default.

## Very hard

- Adds ramp constraints on top of must-run structure.
- This tests both static and temporal feasibility.

---

# Key Finding 1

## `min_mw > 0` is the most important benchmark knob

- The step from `easy` to `medium` is not about more generators alone.
- It changes the nature of the reasoning task.
- Models must shift from "choose the cheap units" to "construct a globally feasible operating point."

## Evidence (v1 + v2)

- `gpt-4o` (v1): `80% -> 20%` from easy to medium
- `gpt-5-nano`: strong across both runs; v2 confirms 100% on hard
- `claude-sonnet-4.6`: v1 suggested 100% on medium; v2 (15 problems) reveals 20% — small samples can mask weakness

---

# Key Finding 2

## `openai/gpt-5.4-pro` is fully reliable on this benchmark

- **v1:** 100% (20/20) | **v2:** 100% (60/60)
- It achieved 100% at every difficulty level in both experiments.
- Holds under 5% and 1% tolerance.

## Why this matters

- The benchmark is not impossible.
- It meaningfully separates weaker models from stronger ones.

---

# Key Finding 3

## `openai/gpt-5-nano` is a strong efficiency-quality tradeoff

- **v1:** 85% (17/20) | **v2:** 88% (53/60)
- v2 confirms 100% on hard (15/15) — more robust than v1's 80% suggested.
- Weakest on very_hard (73% in v2).

## Interpretation

- Smaller models can still be useful for constrained optimization tasks if the benchmark is well structured.
- This makes the task interesting for cost-performance comparisons, not just absolute accuracy.

---

# Key Finding 4

## Claude models show a brittle transition at higher constraint density

- **very_hard > hard** in both runs: v1 Claude 4.6 (0% hard, 80% very_hard); v2 Sonnet (7% hard, 40% very_hard), Opus (7% hard, 73% very_hard).
- v2 reveals Claude 4.6's medium collapse: 20% (3/15) vs v1's 100% (5/5) — sample size matters.
- Different problem structure (ramp, fixed 10 gens) may make very_hard easier for Claude than hard.

## Interpretation

- These models can reason well in partially constrained settings.
- They are less reliable when the feasible region becomes tight and every unit matters.
- v2's larger sample gives a more accurate picture than v1 alone.

---

# Key Finding 5

## Weak models fail before optimization quality becomes the issue

- `gpt-4o` and `mistral-large-2512` (v1) do not mainly fail because they are slightly suboptimal.
- They fail because they often produce invalid schedules.
- v2's stricter tolerance (1%) further separates models that barely pass at 5%.

## Why this is important

- The benchmark measures constraint compliance first.
- This is valuable for real operational tasks where feasibility matters more than style or explanation quality.

---

# Average Cost Gap Diagnostic

## v1 (5% tolerance)

| Model | Easy | Medium | Hard | Very hard |
|---|---:|---:|---:|---:|
| `openai/gpt-4o` | -2.25% | 9.75% | -1.00% | 24.38% |
| `openai/gpt-5.4-pro` | 0.00% | 0.00% | 0.00% | 0.00% |
| `openai/gpt-5-nano` | 0.00% | 3.08% | 5.18% | 6.72% |
| `anthropic/claude-sonnet-4.5` | -3.91% | -8.89% | -6.22% | 7.90% |
| `anthropic/claude-sonnet-4.6` | 0.19% | 0.00% | -7.31% | 2.90% |
| `mistralai/mistral-large-2512` | -14.24% | 6.51% | 9.30% | 24.49% |

## v2 (1% tolerance) — models in common

| Model | Easy | Medium | Hard | Very hard |
|---|---:|---:|---:|---:|
| `openai/gpt-5.4-pro` | 0.00% | 0.00% | 0.00% | 0.00% |
| `openai/gpt-5-nano` | 0.00% | -0.25% | 0.00% | 4.34% |
| `anthropic/claude-sonnet-4.5` | -1.41% | -1.27% | -6.73% | 2.83% |
| `anthropic/claude-sonnet-4.6` | 0.06% | 0.34% | -5.38% | -2.69% |
| `anthropic/claude-opus-4.6` | -2.96% | -1.56% | -5.42% | -0.65% |

## How to interpret

- Zero means the model matched the LP optimum on average.
- Negative values usually reflect infeasible cheap schedules, not true outperformance.

---

# What The Results Say About The Benchmark

- v1 and v2 together show the benchmark is calibrated to separate models across a wide range.
- The difficulty progression is meaningful; v2's larger sample confirms v1 patterns (and corrects some).
- Defensible scoring story: parseability → feasibility → near-optimality.
- The benchmark reveals concrete reasoning failures rather than vague qualitative differences.

---

# Limitations Of This Run

## v1 (5 problems/difficulty, 5% tolerance)

- Small sample size made some patterns noisy (e.g. Claude 4.6 very_hard > hard).
- Single attempt per problem → no variance estimate.

## v2 (15 problems/difficulty, 1% tolerance)

- v2 improves sample size (60 tasks vs 20) and confirms many v1 patterns.
- Still only `1` attempt per problem → no consistency estimate across attempts.
- v2 uses stricter tolerance (1%); results are not directly comparable to v1.
- The benchmark uses synthetic problems only; no PGLib real-grid comparison yet.
- Average cost gap should not be over-interpreted without separating feasible from infeasible schedules.

## Practical implication

- v1 + v2 together give a more reliable picture than v1 alone.
- Multiple attempts per problem would further strengthen the analysis.

---

# Recommended Next Steps

- **Done:** Increased `problems_per_difficulty` to `15` in v2.
- Run multiple attempts per problem to measure consistency, not just best-effort performance.
- Split cost-gap reporting into feasible vs infeasible attempts.
- Add an error taxonomy dashboard: parse failure, demand mismatch, min/max violation, ramp violation.
- Compare synthetic and PGLib-backed problems in the same report.
- Run v1 and v2 with the same tolerance (e.g. 5%) to isolate sample-size vs tolerance effects.

---

# Final Takeaway

- This project demonstrates a strong benchmark design for constrained reasoning.
- The main insight is that must-run constraints, not just scale, are what expose model weakness.
- **GPT-5.4-pro** is fully reliable in both v1 and v2 (5% and 1% tolerance).
- **GPT-5-nano** is the best lightweight performer; v2 confirms 100% on hard.
- **Claude models** show brittle behavior; v2's larger sample reveals medium weakness and confirms very_hard > hard.
- Running two experiments (v1 + v2) strengthens the conclusions.

## Bottom line

- The benchmark successfully measures whether an LLM can produce a valid, cost-aware operating plan under realistic power dispatch constraints.
