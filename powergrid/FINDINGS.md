# Powergrid Dispatch Benchmark

LLM benchmark for **constrained economic dispatch**

Two experiments:

| Run | Problems per difficulty | Tolerance |
|----|----|----|
| v1 | 5 | 5% |
| v2 | 15 | 1% |

Date: 2026-03-15

---

# Problem

We test whether LLMs can solve **economic dispatch**.

Goal:

Allocate generator outputs so:

- Total generation = demand
- Generator limits are respected
- Total cost is minimized

Each generator has:

- `min_mw`
- `max_mw`
- `cost`
- `prev_mw`
- `max_ramp`

The model outputs a dispatch schedule.

Example:

```json
{"GEN_A":120,"GEN_B":85,"GEN_C":40}
````

---

# Why This Is A Good Benchmark

Economic dispatch is useful for LLM evaluation because:

* The problem is **realistic**
* Verification is **fully deterministic**
* Optimal solutions can be computed with **linear programming**

A model must produce a schedule that is:

1. **Parseable**
2. **Feasible**
3. **Near-optimal**

---

# Difficulty Design

Problems are generated synthetically using generator templates.

| Difficulty | Generators | Must-run units | Ramp limits |
| ---------- | ---------- | -------------- | ----------- |
| Easy       | 3–5        | No             | No          |
| Medium     | 6–10       | Some           | No          |
| Hard       | 6–10       | All            | No          |
| Very hard  | 10         | All            | Yes         |

Key difficulty knob:

**`min_mw > 0`**

Models must keep generators running instead of simply turning expensive ones off.

---

# Verification

A candidate schedule must satisfy a set of **standard economic dispatch constraints** used in power-system optimization.

These checks correspond to the classical formulation described in  
Wood & Wollenberg — *Power Generation, Operation and Control*.

---

### 1. Demand balance

$$
\sum_i p_i = D
$$

Total generation must equal the system demand.

- \(p_i\): output of generator *i*
- \(D\): system demand

This is the **power balance constraint** used in economic dispatch.

---

### 2. Capacity limits

$$
min_i \le p_i \le max_i
$$

Each generator must operate within its feasible output range.

- \(min_i\): minimum stable generation
- \(max_i\): maximum generator capacity

These bounds represent **physical operating limits** of generators.

---

### 3. Ramp limits

$$
|p_i - p_i^{prev}| \le ramp_i
$$

Generators cannot change output arbitrarily fast between timesteps.

- \(p_i^{prev}\): previous output
- \(ramp_i\): maximum allowed change

Ramp constraints are common in **dynamic economic dispatch** models.

---

### Optimality check

If the schedule is feasible, we evaluate its cost:

$$
cost = \sum_i p_i \cdot c_i
$$

We compare it with the optimal cost computed via **linear programming**.

$$
gap = \frac{cost_{LLM} - cost_{opt}}{cost_{opt}}
$$

---

### Success criteria

A solution is considered correct if:

- all feasibility constraints are satisfied
- the cost gap is within tolerance

| Experiment | tolerance |
|---|---|
v1 | 5%
v2 | 1%

---

# Overall Results

## v1 (5% tolerance)

| Model         | Success |
| ------------- | ------- |
| GPT-5.4-pro   | 100%    |
| GPT-5-nano    | 85%     |
| Claude 4.6    | 70%     |
| Claude 4.5    | 50%     |
| GPT-4o        | 25%     |
| Mistral-large | 10%     |

---

# Overall Results

## v2 (1% tolerance)

| Model             | Success |
| ----------------- | ------- |
| GPT-5.4-pro       | 100%    |
| GPT-5-nano        | 88%     |
| Claude-opus-4.6   | 48%     |
| Claude-sonnet-4.6 | 42%     |
| Claude-sonnet-4.5 | 28%     |

Stricter tolerance confirms the v1 ranking.

---

# Key Findings

### 1. Must-run constraints drive difficulty

Models often apply merit order but fail when:

```
min_mw > 0
```

Generators cannot simply be shut off.

---

### 2. GPT-5.4-pro is fully reliable

* 100% success in v1 and v2
* Solves all difficulty levels

---

### 3. GPT-5-nano is strong for a small model

* 85% → 88%
* 100% success on **hard** in v2

---

### 4. Claude models are brittle

Observed pattern:

```
very_hard > hard
```

Performance drops when all generators have tight constraints.

---

# Benchmark Value

The benchmark measures **true constrained reasoning**, not just ranking generators by cost.

A model must:

* construct a feasible dispatch
* respect multiple constraints
* approximate the optimal cost

This exposes failures that normal QA benchmarks cannot detect.

---

# Conclusion

The benchmark successfully distinguishes model capability.

Results:

* **GPT-5.4-pro** — fully reliable
* **GPT-5-nano** — strong efficiency trade-off
* **Claude models** — unstable under tight constraints

Economic dispatch provides a clean and realistic test for **LLM constraint reasoning**.
