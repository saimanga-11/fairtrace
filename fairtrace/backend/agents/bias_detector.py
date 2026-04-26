from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from tools.fairtrace_tools import detect_bias, detect_bias_tool, normalize_decision_record


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)


class BiasDetectorAgent:
    """ADK tool-backed agent that simulates protected-attribute bias."""

    name = "BiasDetectorAgent"

    def run(self, decision_record: Dict[str, Any], dataset_path: str | None = None, protected_columns=None, outcome_column=None) -> Dict[str, Any]:
        normalized = normalize_decision_record(decision_record)
        return detect_bias(
            normalized["features"],
            normalized["outcome"],
            dataset_path=dataset_path,
            protected_columns=protected_columns,
            outcome_column=outcome_column,
        )


def _build_agent_model() -> LiteLlm:
    model_name = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip()
    if "/" not in model_name:
        model_name = f"mistral/{model_name}"
    return LiteLlm(model=model_name)


def build_adk_agent() -> Agent:
    return Agent(
        name="BiasDetectorAgent",
        model=_build_agent_model(),
        description="Calculates approval-rate gaps across protected attributes.",
        instruction=(
            "Use the detect_bias tool on the decision features and dataset context, then summarize the approval-rate gap and verdict. "
            "Return the structured bias analysis."
        ),
        tools=[detect_bias_tool],
        output_key="bias_analysis",
    )


adk_agent = build_adk_agent()
