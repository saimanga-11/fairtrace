from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

load_dotenv(BACKEND_DIR / ".env", override=False)

from agents.orchestrator import FairTraceOrchestrator
from tools.report_export import REPORT_DIR, create_analysis_workbook
from tools.sqlite_tool import correct_decision, flag_decision, get_all_decisions, get_decision, save_decision


APP_NAME = os.getenv("APP_NAME", "FairTrace")

app = FastAPI(title=APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = FairTraceOrchestrator()


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    features = dict(payload)
    outcome = features.pop("outcome", features.pop("decision_outcome", None))
    if "features" in features and isinstance(features["features"], dict):
        nested = features.pop("features")
        features.update(nested)
    if outcome is None:
        outcome = "rejected"
    return {"features": features, "outcome": str(outcome)}


@app.get("/")
def root() -> Dict[str, Any]:
    return {"app": APP_NAME, "status": "ok"}


@app.post("/submit")
def submit_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    decision_record = _normalize_payload(payload)
    try:
        report = orchestrator.run(decision_record)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    decision_id = save_decision(
        {
            "original_outcome": report.get("original_outcome", report["decision_outcome"]),
            "input_features": report["input_features"],
            "decision_outcome": report["decision_outcome"],
            "corrected_outcome": report.get("corrected_outcome"),
            "bias_analysis": report.get("bias_analysis", {}),
            "reasoning_chain": report["reasoning_chain"],
            "bias_verdict": report["bias_verdict"],
            "counterfactual_result": report["counterfactual_result"],
            "flagged": report["flagged"],
        }
    )
    return {"id": decision_id, **report}


@app.get("/decisions")
def list_decisions() -> Dict[str, Any]:
    return {"decisions": get_all_decisions()}


@app.get("/decisions/{decision_id}")
def read_decision(decision_id: int) -> Dict[str, Any]:
    decision = get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@app.post("/flag/{decision_id}")
def mark_flagged(decision_id: int) -> Dict[str, Any]:
    decision = flag_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@app.post("/correct/{decision_id}")
def correct(decision_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    new_outcome = payload.get("new_outcome")
    if not new_outcome:
        raise HTTPException(status_code=400, detail="new_outcome is required")
    decision = correct_decision(decision_id, str(new_outcome))
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@app.post("/analyze-dataset")
async def analyze_dataset(file: UploadFile = File(...)) -> Dict[str, Any]:
    suffix = Path(file.filename or "upload.csv").suffix.lower() or ".csv"
    if suffix not in {".csv", ".xlsx", ".xls"}:
        suffix = ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        try:
            analysis = orchestrator.data_profiler.run(str(tmp_path))
            export_meta = create_analysis_workbook(str(tmp_path), file.filename or f"dataset{suffix}", analysis)
            return {
                **analysis,
                "download_filename": export_meta["filename"],
                "download_url": f"/download-report/{export_meta['filename']}",
            }
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Dataset analysis failed: {exc}")
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.get("/download-report/{filename}")
def download_report(filename: str):
    target = (REPORT_DIR / filename).resolve()
    report_root = REPORT_DIR.resolve()
    if report_root not in target.parents or not target.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
