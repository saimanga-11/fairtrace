from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from agents.bias_detector import BiasDetectorAgent
from agents.bias_detector import adk_agent as bias_detector_adk_agent
from agents.counterfactual import CounterfactualAgent
from agents.counterfactual import adk_agent as counterfactual_adk_agent
from agents.data_profiler import DataProfilerAgent
from agents.data_profiler import adk_agent as data_profiler_adk_agent
from agents.explainer import ExplainerAgent
from agents.explainer import adk_agent as explainer_adk_agent
from tools.fairtrace_tools import (
    detect_bias_tool,
    feature_importance_tool,
    profile_dataset_tool,
    simulate_counterfactual_tool,
)
from google.adk.agents import SequentialAgent


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)
APP_NAME = os.getenv("APP_NAME", "FairTrace")


class FairTraceOrchestrator:
    name = "FairTraceOrchestrator"

    def __init__(self) -> None:
        self.data_profiler = DataProfilerAgent()
        self.bias_detector = BiasDetectorAgent()
        self.explainer = ExplainerAgent()
        self.counterfactual = CounterfactualAgent()
        self.tools = {
            "profile_dataset": profile_dataset_tool,
            "detect_bias": detect_bias_tool,
            "feature_importance": feature_importance_tool,
            "simulate_counterfactual": simulate_counterfactual_tool,
        }

    def run(self, decision_record: Dict[str, Any], dataset_path: Optional[str] = None) -> Dict[str, Any]:
        default_dataset = BACKEND_DIR / "sample_data" / "hiring_dataset.csv"
        selected_dataset = Path(dataset_path) if dataset_path else default_dataset

        dataset_profile = None
        if selected_dataset.exists():
            dataset_profile = self.data_profiler.run(str(selected_dataset))

        bias_output = self.bias_detector.run(
            decision_record,
            dataset_path=str(selected_dataset) if selected_dataset.exists() else None,
            protected_columns=(dataset_profile or {}).get("protected_columns") if isinstance(dataset_profile, dict) else None,
            outcome_column=(dataset_profile or {}).get("outcome_column") if isinstance(dataset_profile, dict) else None,
        )
        explanation_output = self.explainer.run(decision_record, bias_output)
        counterfactual_output = self.counterfactual.run(decision_record, bias_output)

        return {
            "dataset_profile": dataset_profile,
            "original_outcome": decision_record.get("outcome") or decision_record.get("decision_outcome", "unknown"),
            "decision_outcome": decision_record.get("outcome") or decision_record.get("decision_outcome", "unknown"),
            "input_features": decision_record.get("features", decision_record),
            "bias_analysis": bias_output,
            "reasoning_chain": explanation_output,
            "counterfactual_result": counterfactual_output,
            "bias_verdict": bias_output.get("overall_verdict", "UNKNOWN"),
            "flagged": bias_output.get("overall_verdict") != "LOW RISK",
        }


def build_root_agent():
    """Build the ADK sequential workflow for FairTrace."""
    sub_agents = [
        agent
        for agent in [
            data_profiler_adk_agent,
            bias_detector_adk_agent,
            explainer_adk_agent,
            counterfactual_adk_agent,
        ]
    ]
    return SequentialAgent(
        name=APP_NAME,
        description="Sequential ADK workflow for dataset profiling, bias detection, explanation, and counterfactual analysis.",
        sub_agents=sub_agents,
    )


root_agent = build_root_agent()
