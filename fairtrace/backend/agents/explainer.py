from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from pydantic import ValidationError

from agents.schemas import ExplainerOutput
from tools.fairtrace_tools import feature_importance, feature_importance_tool, normalize_decision_record
from tools.mistral_tool import complete_json


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)


SYSTEM_PROMPT = """You are FairTrace's ExplainerAgent.
You explain automated decisions for an audit report.
You must:
- stay grounded in the provided decision record and bias analysis
- use the bias verdict from the audit data, not your own guess
- produce exactly five reasoning steps
- summarize the top three features in plain English
- return only valid JSON matching the requested keys
"""


class ExplainerAgent:
    name = "ExplainerAgent"

    def run(self, decision_record: Dict[str, Any], bias_output: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_decision_record(decision_record)
        features = normalized["features"]
        ranked = feature_importance(features)
        bias_summary = ", ".join(
            f"{item['attribute']} gap {item['gap']}% ({item['verdict']})"
            for item in bias_output.get("attributes", [])
        )
        prompt = f"""{SYSTEM_PROMPT}

Decision record:
{normalized}

Bias analysis:
{bias_output}

Tool-derived feature ranking:
{ranked}

Bias summary:
{bias_summary or bias_output.get('overall_verdict', 'UNKNOWN')}

Return JSON with keys:
- reasoning_steps (5 strings)
- summary (string)
- bias_explanation (string)
- feature_importance (3 objects with feature and score)
"""
        result = complete_json(prompt)
        if not result:
            raise RuntimeError("Mistral did not return structured explainer output.")
        try:
            validated = ExplainerOutput.model_validate(result)
        except ValidationError as exc:
            raise RuntimeError(f"Mistral returned invalid explainer output: {exc}") from None
        return validated.model_dump()


def _build_agent_model() -> LiteLlm:
    model_name = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip()
    if "/" not in model_name:
        model_name = f"mistral/{model_name}"
    return LiteLlm(model=model_name)


def build_adk_agent() -> Agent:
    return Agent(
        name="ExplainerAgent",
        model=_build_agent_model(),
        description="Generates the reasoning chain and feature importance summary for an audited decision.",
        instruction=(
            "Use the feature_importance tool to identify the top three drivers, then explain the decision in five steps. "
            "Return structured JSON containing reasoning_steps, summary, bias_explanation, and feature_importance."
        ),
        tools=[feature_importance_tool],
        output_key="reasoning_chain",
    )


adk_agent = build_adk_agent()
