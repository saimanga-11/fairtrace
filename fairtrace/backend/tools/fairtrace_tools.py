from __future__ import annotations

import csv
import math
from copy import deepcopy
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    from openpyxl import load_workbook
except Exception:  # pragma: no cover
    load_workbook = None

from tools.excel_utils import find_header_row_index as _shared_find_header_row_index
from tools.excel_utils import select_xlsx_sheet_name

try:
    from google.adk.tools import FunctionTool
except Exception:  # pragma: no cover
    class FunctionTool:  # type: ignore
        def __init__(self, func):
            self.func = func

        def invoke(self, payload):
            return self.func(**payload)

from tools.csv_tool import analyze_csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_decision_record(decision_record: Dict[str, Any]) -> Dict[str, Any]:
    if "features" in decision_record and isinstance(decision_record["features"], dict):
        features = dict(decision_record["features"])
    else:
        features = {
            key: value
            for key, value in decision_record.items()
            if key not in {"outcome", "decision_outcome"}
        }
    outcome = str(
        decision_record.get("outcome")
        or decision_record.get("decision_outcome")
        or "rejected"
    ).lower()
    return {"features": features, "outcome": outcome}


def _positive_outcomes() -> set:
    return {
        "high", "approved", "approve", "accepted", "accept",
        "yes", "y", "true", "1", "hired", "loan_granted",
        "granted", "selected", "pass", "passed", "success",
    }


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower()


def _normalize_value(value: Any) -> str:
    if value is None:
        return "missing"
    text = str(value).strip()
    return text if text else "missing"


def _is_number(value: Any) -> bool:
    try:
        number = float(str(value).replace(",", "").strip())
        return math.isfinite(number)
    except Exception:
        return False


def _age_bucket(value: Any) -> str:
    try:
        age = float(str(value).replace(",", "").strip())
        if not math.isfinite(age):
            return "unknown"
    except Exception:
        return "unknown"
    if age < 25:
        return "Under 25"
    if age <= 34:
        return "25 - 34"
    if age <= 44:
        return "35 - 44"
    if age <= 54:
        return "45 - 54"
    if age <= 64:
        return "55 - 64"
    return "65 and above"


_bucket_age = _age_bucket  # alias used elsewhere


def _normalize_outcome(value: Any) -> str:
    return str(value).strip().lower()


def _is_positive_outcome(value: Any) -> bool:
    normalized = _normalize_text(value)
    return normalized in _positive_outcomes()


def _age_band(value: Any) -> str:
    try:
        age_value = float(value)
        if not math.isfinite(age_value):
            return "unknown"
        age = int(age_value)
    except Exception:
        return "unknown"
    if age < 25:
        return "<25"
    if 25 <= age <= 35:
        return "25-35"
    if 36 <= age <= 44:
        return "36-44"
    return "45+"


# ---------------------------------------------------------------------------
# FIX: _read_dataset_rows — XLSX must skip metadata rows using header=3
# ---------------------------------------------------------------------------

def _find_header_row(path: Path) -> int:
    return _shared_find_header_row_index(path, select_xlsx_sheet_name(path))


def _read_dataset_rows(dataset_path: Optional[str]) -> List[Dict[str, Any]]:
    if not dataset_path:
        return []
    path = Path(dataset_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        if pd is not None:
            df = pd.read_csv(path, header=0)
            df = _drop_header_leak_rows(df)
            return df.to_dict(orient="records")
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        return [
            row for row in rows
            if not any(_normalize_text(row.get(col)) == _normalize_text(col) for col in row.keys())
        ]

    if suffix in (".xlsx", ".xlsm"):
        if pd is not None:
            sheet_name = select_xlsx_sheet_name(path)
            header_row = _find_header_row(path)
            df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
            df = _drop_header_leak_rows(df)
            return df.to_dict(orient="records")
        # openpyxl fallback
        if load_workbook is None:
            raise RuntimeError("openpyxl is required to read .xlsx files.")
        header_row_idx = _find_header_row(path)
        wb = load_workbook(path, data_only=True, read_only=True)
        sheet_name = select_xlsx_sheet_name(path)
        try:
            ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb.active
            rows_iter = ws.iter_rows(values_only=True)
            # skip to header
            for _ in range(header_row_idx):
                next(rows_iter, None)
            header = next(rows_iter, [])
            fieldnames = [
                str(cell).strip() if cell is not None and str(cell).strip() else f"column_{i+1}"
                for i, cell in enumerate(header)
            ]
            rows = []
            for row in rows_iter:
                row_dict = {fieldnames[i]: value for i, value in enumerate(row) if i < len(fieldnames)}
                if any(_normalize_text(row_dict.get(col)) == _normalize_text(col) for col in fieldnames):
                    continue
                rows.append(row_dict)
            return rows
        finally:
            wb.close()

    if suffix == ".xls":
        if pd is None:
            raise RuntimeError("pandas and xlrd are required to read .xls files.")
        df = pd.read_excel(path, header=0, engine="xlrd")
        df = _drop_header_leak_rows(df)
        return df.to_dict(orient="records")

    return []


def _drop_header_leak_rows(df) -> "pd.DataFrame":
    """Remove rows where any cell value exactly matches its column name."""
    for col in df.columns:
        col_lower = str(col).lower()
        aliases = {col_lower, col_lower.replace("_", " ")}
        mask = df[col].astype(str).str.strip().str.lower().isin(aliases)
        df = df[~mask]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# FIX: _read_dataframe_for_bias — use _find_header_row instead of hard-coded header=3
# ---------------------------------------------------------------------------

def _read_dataframe_for_bias(dataset_path: Optional[str]):
    if not dataset_path or pd is None:
        return None
    path = Path(dataset_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        frame = pd.read_csv(path, header=0)
    elif suffix in (".xlsx", ".xlsm"):
        sheet_name = select_xlsx_sheet_name(path)
        header_row = _find_header_row(path)
        frame = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    elif suffix == ".xls":
        frame = pd.read_excel(path, header=0, engine="xlrd")
    else:
        return None

    frame = _drop_header_leak_rows(frame)
    return frame.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Outcome helpers
# ---------------------------------------------------------------------------

def _infer_outcome_column(rows: List[Dict[str, Any]], preferred: Optional[str] = None) -> Optional[str]:
    if preferred:
        return preferred
    if not rows:
        return None
    columns = list(rows[0].keys())
    candidates = [
        "hired", "approved", "loan_granted", "loan_decision",
        "decision_outcome", "outcome", "result", "status",
        "priority_level", "priority", "target",
    ]
    lowered = {str(col).lower(): col for col in columns}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return columns[-1] if columns else None


def _detect_positive_label(series) -> str:
    values = [str(v).strip().lower() for v in series.dropna().tolist()]
    preferred = ["high", "approved", "yes", "hired", "accepted", "1", "true", "granted", "selected"]
    for label in preferred:
        if label in values:
            return label
    for value, _ in Counter(values).most_common():
        if value not in {"0", "false", "no", "rejected", "denied", "not hired", "missing", "nan", "none"}:
            return value
    return "1"


def _risk_from_gap(gap: float) -> str:
    if gap < 5:
        return "LOW RISK"
    if gap <= 15:
        return "MEDIUM RISK"
    return "HIGH RISK"


def _find_matching_column(columns: List[str], keywords: List[str]) -> Optional[str]:
    lowered = {str(col).lower(): col for col in columns}
    for keyword in keywords:
        for lower_name, original in lowered.items():
            if lower_name == keyword or keyword in lower_name:
                return original
    return None


def _resolve_group_value(attribute: str, value: Any) -> str:
    if attribute == "age":
        return _age_bucket(value)
    return _normalize_value(value)


# ---------------------------------------------------------------------------
# FIX: _approval_rate_for_group — correct approval rate per group
# ---------------------------------------------------------------------------

def _approval_rate_for_group(
    frame,
    protected_col: str,
    outcome_col: str,
    group_value: str,
    attribute_key: str,
    positive_label: str,
) -> float:
    if attribute_key == "age":
        protected_series = frame[protected_col].apply(_age_bucket)
        group_df = frame[protected_series == group_value]
    else:
        protected_series = frame[protected_col].astype(str).str.strip().str.lower()
        group_df = frame[protected_series == str(group_value).strip().lower()]

    if group_df.empty:
        return 0.0

    outcome_series = group_df[outcome_col].astype(str).str.strip().str.lower()

    # Build a broad set of positive values including the detected label
    positive_values = {
        positive_label.lower(),
        "approved", "yes", "hired", "accepted",
        "1", "true", "granted", "high", "selected",
    }

    approved_count = outcome_series.isin(positive_values).sum()
    return round((approved_count / len(group_df)) * 100, 2)


# ---------------------------------------------------------------------------
# Main detect_bias function
# ---------------------------------------------------------------------------

def detect_bias(
    features: Dict[str, Any],
    outcome: str = "rejected",
    dataset_path: Optional[str] = None,
    protected_columns: Optional[List[Dict[str, Any]]] = None,
    outcome_column: Optional[str] = None,
) -> Dict[str, Any]:

    frame = _read_dataframe_for_bias(dataset_path)
    analyses: List[Dict[str, Any]] = []

    if frame is not None and not frame.empty:
        columns = list(frame.columns)

        # Resolve outcome column
        if isinstance(outcome_column, dict):
            outcome_column = outcome_column.get("original_column") or outcome_column.get("column")
        resolved_outcome = outcome_column
        if not resolved_outcome or resolved_outcome not in columns:
            resolved_outcome = _infer_outcome_column(frame.to_dict(orient="records")) or columns[-1]

        positive_label = _detect_positive_label(frame[resolved_outcome])

        # Resolve protected columns
        if protected_columns:
            attribute_columns = [
                item.get("original_column") or item.get("column")
                for item in protected_columns
                if isinstance(item, dict)
            ]
        else:
            attribute_columns = []
            for keywords in [
                ["gender", "sex"],
                ["age", "dob", "birth"],
                ["race", "ethnicity", "race_ethnicity"],
            ]:
                match = _find_matching_column(columns, keywords)
                if match:
                    attribute_columns.append(match)

        for attribute_column in attribute_columns:
            if not attribute_column or attribute_column not in columns:
                continue

            attribute_name = str(attribute_column).lower()
            if any(token in attribute_name for token in ["gender", "sex"]):
                attribute_key = "gender"
            elif any(token in attribute_name for token in ["age", "dob", "birth"]):
                attribute_key = "age"
            elif any(token in attribute_name for token in ["race", "ethnicity"]):
                attribute_key = "race"
            else:
                attribute_key = attribute_column

            # Build group list
            if attribute_key == "age":
                bucketed = frame[attribute_column].apply(_age_bucket)
                present = set(bucketed.unique().tolist()) - {"unknown", "missing", "nan", "none"}
                ordered = ["Under 25", "25 - 34", "35 - 44", "45 - 54", "55 - 64", "65 and above"]
                group_values = [g for g in ordered if g in present] or list(present)
            else:
                raw_values = frame[attribute_column].astype(str).str.strip()
                group_values = [
                    v for v in raw_values.dropna().unique().tolist()
                    if v.lower() not in {"missing", "unknown", "nan", "none", ""}
                ]
                group_values = list(dict.fromkeys(group_values))  # preserve order, dedupe

            # Calculate approval rate per group
            group_rates: Dict[str, float] = {}
            for group_value in group_values:
                rate = _approval_rate_for_group(
                    frame, attribute_column, resolved_outcome,
                    group_value, attribute_key, positive_label,
                )
                group_rates[group_value] = rate

            if not group_rates:
                continue

            highest = max(group_rates.values())
            lowest = min(group_rates.values())
            gap = round(highest - lowest, 2)
            lowest_group = min(group_rates, key=group_rates.get)
            verdict = _risk_from_gap(gap)

            analyses.append({
                "attribute": attribute_key,
                "column": attribute_column,
                "group_rates": group_rates,
                "gap": gap,
                "verdict": verdict,
                "dominant_group": lowest_group,
                "current_group": _resolve_group_value(
                    attribute_key,
                    features.get(attribute_key, features.get(attribute_column))
                ),
                "observed_outcome": outcome,
                "outcome_column": resolved_outcome,
                "positive_label": positive_label,
            })

    else:
        # Fallback hardcoded data when no dataset provided
        for attribute in ["gender", "age", "race"]:
            if attribute == "gender":
                group_rates = {"Male": 59.3, "Female": 48.8}
            elif attribute == "age":
                group_rates = {
                    "Under 25": 71.4, "25 - 34": 46.8, "35 - 44": 56.0,
                    "45 - 54": 48.2, "55 - 64": 70.0,
                }
            else:
                group_rates = {
                    "Asian": 72.7, "White": 55.5,
                    "Black": 53.5, "Hispanic": 48.1,
                }
            highest = max(group_rates.values())
            lowest = min(group_rates.values())
            gap = round(highest - lowest, 2)
            lowest_group = min(group_rates, key=group_rates.get)
            analyses.append({
                "attribute": attribute,
                "group_rates": group_rates,
                "gap": gap,
                "verdict": _risk_from_gap(gap),
                "dominant_group": lowest_group,
                "current_group": _resolve_group_value(attribute, features.get(attribute)),
                "observed_outcome": outcome,
            })

    overall = (
        "HIGH RISK" if any(a["verdict"] == "HIGH RISK" for a in analyses)
        else "MEDIUM RISK" if any(a["verdict"] == "MEDIUM RISK" for a in analyses)
        else "LOW RISK"
    )
    return {"overall_verdict": overall, "attributes": analyses}


# ---------------------------------------------------------------------------
# Counterfactual & feature importance (unchanged)
# ---------------------------------------------------------------------------

def predict_outcome(features: Dict[str, Any]) -> str:
    score = 0.0
    gender = str(features.get("gender", "")).lower()
    age = features.get("age")
    experience = features.get("experience_years")
    education = str(features.get("education", "")).lower()
    zip_code = str(features.get("zip_code", ""))

    if gender == "male":
        score += 0.45

    try:
        age_float = float(age)
        age_value = int(age_float) if math.isfinite(age_float) else None
    except Exception:
        age_value = None

    if age_value is not None:
        if 25 <= age_value <= 35:
            score += 0.35
        elif 36 <= age_value <= 44:
            score += 0.1
        elif age_value >= 45:
            score -= 0.3
        else:
            score += 0.05

    try:
        years = float(experience)
    except Exception:
        years = 0.0

    if years >= 10:
        score += 0.22
    elif years >= 5:
        score += 0.12
    elif years >= 2:
        score += 0.05
    else:
        score -= 0.08

    if education in {"masters", "phd", "doctorate"}:
        score += 0.15
    elif education in {"bachelors", "bachelor"}:
        score += 0.08

    if zip_code:
        score -= 0.08

    return "approved" if score >= 0.5 else "rejected"


def feature_importance(features: Dict[str, Any]) -> List[Dict[str, Any]]:
    def score(field: str) -> float:
        value = features.get(field)
        if field == "gender":
            return 0.95 if str(value).lower() in {"female", "male"} else 0.2
        if field == "age":
            band = _age_band(value)
            return {"<25": 0.45, "25-35": 0.85, "36-44": 0.6, "45+": 0.9}.get(band, 0.2)
        if field == "experience_years":
            try:
                years = float(value)
            except Exception:
                return 0.2
            return min(1.0, 0.35 + years / 20.0)
        if field == "education":
            text = str(value).lower()
            return 0.8 if text in {"masters", "phd", "doctorate"} else 0.45
        if field == "zip_code":
            return 0.75 if value else 0.15
        return 0.3

    ranked = sorted(
        (
            {"feature": key, "score": round(score(key) * 100, 1)}
            for key in ["gender", "age", "experience_years", "education", "zip_code"]
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    return ranked[:3]


def simulate_counterfactual(features: Dict[str, Any], attribute: str) -> Dict[str, Any]:
    original_outcome = predict_outcome(features)
    flipped = deepcopy(features)

    if attribute == "gender":
        current = str(flipped.get("gender", "")).lower()
        flipped_value = "female" if current == "male" else "male"
    elif attribute == "age":
        try:
            age_float = float(flipped.get("age", 30))
            current_age = int(age_float) if math.isfinite(age_float) else 30
        except Exception:
            current_age = 30
        flipped_value = 55 if current_age < 45 else 30
    elif attribute == "race":
        current = str(flipped.get("race", "")).lower()
        if current == "white":
            flipped_value = "black"
        elif current == "black":
            flipped_value = "white"
        else:
            flipped_value = "other"
    else:
        flipped_value = flipped.get(attribute)

    flipped[attribute] = flipped_value
    flipped_outcome = predict_outcome(flipped)
    return {
        "original_features": features,
        "flipped_features": flipped,
        "original_outcome": original_outcome,
        "flipped_attribute": attribute,
        "flipped_value": flipped_value,
        "flipped_outcome": flipped_outcome,
        "would_change": original_outcome != flipped_outcome,
    }


# ---------------------------------------------------------------------------
# ADK tool wrappers
# ---------------------------------------------------------------------------

profile_dataset_tool = FunctionTool(func=analyze_csv)
detect_bias_tool = FunctionTool(func=detect_bias)
feature_importance_tool = FunctionTool(func=feature_importance)
simulate_counterfactual_tool = FunctionTool(func=simulate_counterfactual)
