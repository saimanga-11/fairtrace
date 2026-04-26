from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from pydantic import ValidationError

from agents.schemas import CounterfactualNarrative, CounterfactualOutput
from tools.fairtrace_tools import (
    detect_bias,
    detect_bias_tool,
    normalize_decision_record,
    predict_outcome,
    simulate_counterfactual_tool,
)
from tools.mistral_tool import complete_json


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)


SYSTEM_PROMPT = """You are FairTrace's CounterfactualAgent.
You explain how protected-attribute flips affect a single decision record.
You must:
- use the simulated scenario data supplied to you
- describe whether the outcome changes and why
- be concise and concrete
- return only valid JSON with an explanation string
"""


class CounterfactualAgent:
    name = "CounterfactualAgent"

    def run(self, decision_record: Dict[str, Any], bias_output: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized = normalize_decision_record(decision_record)
        features = normalized["features"]
        scenarios: List[Dict[str, Any]] = []

        for attribute in ["gender", "age", "race"]:
            flipped = deepcopy(features)
            if attribute == "gender":
                current = str(flipped.get("gender", "")).lower()
                flipped_value = "female" if current == "male" else "male"
            elif attribute == "age":
                try:
                    current_age = int(float(flipped.get("age", 30)))
                except Exception:
                    current_age = 30
                flipped_value = 55 if current_age < 45 else 30
            else:
                current = str(flipped.get("race", "")).lower()
                if current == "white":
                    flipped_value = "black"
                elif current == "black":
                    flipped_value = "white"
                else:
                    flipped_value = "other"

            flipped[attribute] = flipped_value
            scenario = {
                "original_outcome": predict_outcome(features),
                "flipped_attribute": attribute,
                "flipped_value": flipped_value,
                "flipped_outcome": predict_outcome(flipped),
                "would_change": predict_outcome(features) != predict_outcome(flipped),
            }
            bias_recheck = detect_bias(flipped, outcome=scenario["flipped_outcome"])
            prompt = f"""{SYSTEM_PROMPT}

Original record:
{normalized}

Scenario:
{scenario}

Bias recheck:
{bias_recheck}

Return JSON with one key:
- explanation
"""
            completion = complete_json(prompt)
            try:
                narrative = CounterfactualNarrative.model_validate(completion)
            except ValidationError as exc:
                raise RuntimeError(f"Mistral returned invalid counterfactual output: {exc}") from None
            scenarios.append(
                {
                    **scenario,
                    "bias_recheck": bias_recheck,
                    "explanation": narrative.explanation,
                }
            )

        primary = next((item for item in scenarios if item["would_change"]), scenarios[0] if scenarios else {})
        result = {
            "original_outcome": primary.get("original_outcome", normalized["outcome"]),
            "flipped_attribute": primary.get("flipped_attribute"),
            "flipped_outcome": primary.get("flipped_outcome"),
            "would_change": primary.get("would_change", False),
            "explanation": primary.get("explanation", ""),
            "scenarios": scenarios,
        }
        try:
            validated = CounterfactualOutput.model_validate(result)
        except ValidationError as exc:
            raise RuntimeError(f"Counterfactual result failed validation: {exc}") from None
        return validated.model_dump()


def _build_agent_model() -> LiteLlm:
    model_name = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip()
    if "/" not in model_name:
        model_name = f"mistral/{model_name}"
    return LiteLlm(model=model_name)


def build_adk_agent() -> Agent:
    return Agent(
        name="CounterfactualAgent",
        model=_build_agent_model(),
        description="Simulates protected-attribute flips and explains outcome changes.",
        instruction=(
            "Use the simulate_counterfactual and detect_bias style logic on protected attributes. "
            "Explain whether the outcome changes and why, returning a structured explanation."
        ),
        tools=[simulate_counterfactual_tool, detect_bias_tool],
        output_key="counterfactual_result",
    )


adk_agent = build_adk_agent()
