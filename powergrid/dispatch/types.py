"""Pydantic models for power grid dispatch problems."""

from typing import Optional

from pydantic import BaseModel, Field


class Generator(BaseModel):
    """A single thermal generator with capacity and cost parameters."""

    name: str = Field(..., description="Generator identifier")
    min_mw: float = Field(..., description="Minimum output (MW)")
    max_mw: float = Field(..., description="Maximum output (MW)")
    cost_per_mwh: float = Field(..., description="Marginal cost ($/MWh)")
    ramp_limit_mw: float = Field(
        default=1e9,
        description="Max change from prev_output per timestep (MW); 1e9 = no limit",
    )
    prev_output_mw: float = Field(
        default=0.0,
        description="Output at previous timestep (MW)",
    )


class DispatchProblem(BaseModel):
    """A single economic dispatch problem instance."""

    problem_id: str = Field(..., description="Unique problem identifier")
    source_case: str = Field(
        ...,
        description="Source: 'synthetic' or PGLib-UC case name (e.g. rts_gmlc_2020-01-27)",
    )
    difficulty: str = Field(
        ...,
        description="Difficulty level: easy, medium, or hard",
    )
    generators: list[Generator] = Field(
        ...,
        description="List of generators to dispatch",
    )
    demand_mw: float = Field(..., description="Total demand to meet (MW)")
    prompt: str = Field(..., description="Pre-formatted text sent to the LLM")
    optimal_schedule: dict[str, float] = Field(
        ...,
        description="Golden label: MW output per generator",
    )
    optimal_cost: float = Field(
        ...,
        description="Total cost of optimal schedule ($)",
    )


class VerificationResult(BaseModel):
    """Result of verifying an LLM's dispatch schedule."""

    success: bool = Field(
        ...,
        description="True if feasible and within cost tolerance",
    )
    feasible: bool = Field(
        ...,
        description="True if schedule satisfies all constraints",
    )
    violations: list[str] = Field(
        default_factory=list,
        description="List of constraint violation descriptions",
    )
    llm_cost: Optional[float] = Field(
        default=None,
        description="Total cost of LLM schedule ($)",
    )
    optimal_cost: float = Field(
        ...,
        description="Optimal cost for comparison ($)",
    )
    gap: Optional[float] = Field(
        default=None,
        description="(llm_cost - optimal_cost) / optimal_cost",
    )
