from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field


class FeatureScore(BaseModel):
    feature: str = Field(..., description="Feature name.")
    score: float = Field(..., ge=0, le=100, description="Relative feature importance score.")


class ExplainerOutput(BaseModel):
    reasoning_steps: Annotated[list[str], Field(min_length=5, max_length=5)]
    summary: str
    bias_explanation: str
    feature_importance: Annotated[list[FeatureScore], Field(min_length=3, max_length=3)]


class CounterfactualNarrative(BaseModel):
    explanation: str


class CounterfactualScenario(BaseModel):
    original_outcome: str
    flipped_attribute: str
    flipped_value: Any = None
    flipped_outcome: str
    would_change: bool
    bias_recheck: dict[str, Any] = Field(default_factory=dict)
    explanation: str


class CounterfactualOutput(BaseModel):
    original_outcome: str
    flipped_attribute: str | None = None
    flipped_outcome: str | None = None
    would_change: bool = False
    explanation: str = ""
    scenarios: Annotated[list[CounterfactualScenario], Field(min_length=1)]
