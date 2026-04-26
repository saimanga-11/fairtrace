from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

if TYPE_CHECKING:
    from pandas import DataFrame

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

from tools.excel_utils import find_header_row_index as _shared_find_header_row_index
from tools.excel_utils import select_xlsx_sheet_name
from tools.fairtrace_tools import profile_dataset_tool
from tools.mistral_tool import complete_json


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)


SYSTEM_PROMPT_TEMPLATE = """You are a data privacy and bias detection expert.
Given these CSV column names and sample values, classify each column into one of these categories:

- PROTECTED: columns related to gender, age, race, religion, nationality, disability, marital status, sexuality or any demographic attribute that could lead to discrimination
- IMPORTANT: These types of columns are NEVER proxies, classify them as IRRELEVANT:
- Annual_Income, Income, Salary, Earnings -> financial feature
- Credit_Score, FICO, Credit_Rating -> financial feature
- Loan_Amount, Loan_Amount_Requested, Requested_Amount -> financial feature
- GPA, Marks, Score, Grade -> performance feature
- Years_Experience, Experience -> performance feature
- Condition_Severity, Wait_Days -> medical/clinical feature, NOT a proxy
- Insurance_Type -> PROXY (reveals socioeconomic status which correlates with race/income)

A PROXY must be a non-financial, non-performance column that INDIRECTLY reveals a protected attribute.
Only these types qualify as PROXY:
- Geographic: zip, postcode, neighborhood, district, area
- Social: school_name, university, club, association
- Linguistic: surname, last_name, mother_tongue, language
- Occupational: employment_status, job_type, occupation, insurance_type

Employment_Status should be classified as PROXY because unemployment rates differ significantly across racial and socioeconomic groups.
Insurance_Type should be classified as PROXY because insurance coverage correlates strongly with race and income.

- OUTCOME: the target/result column (hired, approved, rejected, loan_granted, diagnosis, priority_level etc.)
- IDENTIFIER: name, id, email, phone, patient_id, applicant_id - ignore these
- IRRELEVANT: experience, salary, score, marks, condition_severity, wait_days - not sensitive, not an outcome

For display, clean the label into a readable name:
- Race_Ethnicity -> Race / Ethnicity
- Loan_Decision -> Loan Decision
- Employment_Status -> Employment Status
- Priority_Level -> Priority Level
- Insurance_Type -> Insurance Type

Return both original_column and display_name.

Column names: <<COLUMN_NAMES>>
Sample rows: <<SAMPLE_ROWS>>

Respond ONLY in this JSON format, no explanation:
{
  "classifications": [
    {
      "original_column": "column_name",
      "display_name": "Readable Name",
      "category": "PROTECTED/PROXY/OUTCOME/IDENTIFIER/IRRELEVANT",
      "reason": "one line why"
    }
  ]
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_value(value: Any) -> str:
    if value is None:
        return "missing"
    text = str(value).strip()
    return text if text else "missing"


def _display_name(column: str) -> str:
    column_text = str(column).strip()
    special = {
        "race_ethnicity": "Race / Ethnicity",
        "loan_decision": "Loan Decision",
        "employment_status": "Employment Status",
        "priority_level": "Priority Level",
        "insurance_type": "Insurance Type",
    }
    lowered = column_text.lower()
    if lowered in special:
        return special[lowered]
    text = column_text.replace("_", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.title() if text else str(column)


def _is_number(value: Any) -> bool:
    try:
        number = float(str(value).replace(",", "").strip())
        return math.isfinite(number)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Smart header detection — works for any dataset layout
# ---------------------------------------------------------------------------

def _find_header_row_index(path: Path) -> int:
    return _shared_find_header_row_index(path, select_xlsx_sheet_name(path))


def _clean_dataframe(df: DataFrame) -> DataFrame:
    """Remove rows where a cell value exactly matches its column name."""
    df = df.reset_index(drop=True)
    for col in df.columns:
        aliases = {str(col).lower(), str(col).lower().replace("_", " ")}
        df = df[~df[col].astype(str).str.strip().str.lower().isin(aliases)]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# File readers — all use smart header detection
# ---------------------------------------------------------------------------

def _read_csv_with_pandas(path: Path) -> Dict[str, Any]:
    if pd is None:
        raise RuntimeError("pandas is required to read CSV files.")
    dataframe = pd.read_csv(path, header=0)
    dataframe = _clean_dataframe(dataframe)
    rows = dataframe.to_dict(orient="records")
    return {"rows": rows, "fieldnames": list(dataframe.columns)}


def _read_xlsx_with_openpyxl(path: Path) -> Dict[str, Any]:
    if pd is None:
        raise RuntimeError("pandas is required to read .xlsx files.")
    sheet_name = select_xlsx_sheet_name(path)
    header_row = _find_header_row_index(path)
    dataframe = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    dataframe = _clean_dataframe(dataframe)
    rows = dataframe.to_dict(orient="records")
    return {"rows": rows, "fieldnames": list(dataframe.columns)}


def _read_xls_with_pandas(path: Path) -> Dict[str, Any]:
    if pd is None:
        raise RuntimeError("pandas and xlrd are required to read .xls files.")
    dataframe = pd.read_excel(path, header=0, engine="xlrd")
    dataframe = _clean_dataframe(dataframe)
    rows = dataframe.to_dict(orient="records")
    return {"rows": rows, "fieldnames": list(dataframe.columns)}


def _read_tabular_file(csv_path: str) -> Dict[str, Any]:
    path = Path(csv_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv_with_pandas(path)
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx_with_openpyxl(path)
    if suffix == ".xls":
        return _read_xls_with_pandas(path)
    raise RuntimeError(f"Unsupported file type: {suffix}")


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------

def _sample_rows(rows: List[Dict[str, Any]], fieldnames: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    sample: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        sample.append({field: _normalize_value(row.get(field)) for field in fieldnames})
    return sample


def _bucket_numeric(values: List[Any], field_name: str = "") -> Dict[str, float]:
    numeric_values = [float(str(v).replace(",", "").strip()) for v in values if _is_number(v)]
    if not numeric_values:
        return {}
    min_value = min(numeric_values)
    max_value = max(numeric_values)
    if math.isclose(min_value, max_value):
        return {f"{int(min_value)}": 100.0}
    field_lower = str(field_name).lower()
    if any(t in field_lower for t in ["age", "dob", "birth"]) and len({int(v) for v in numeric_values}) > 8:
        buckets = [
            ("Under 25", -math.inf, 25), ("25 - 34", 25, 35),
            ("35 - 44", 35, 45), ("45 - 54", 45, 55),
            ("55 - 64", 55, 65), ("65 and above", 65, math.inf),
        ]
    else:
        span = max_value - min_value
        step = max(span / 6.0, 1.0)
        edges = [min_value + step * i for i in range(6)]
        buckets = [(f"{math.floor(edges[i])} - {math.ceil(edges[i+1])-1}", edges[i], edges[i+1]) for i in range(5)]
        buckets.append((f"{math.floor(edges[5])}+", edges[5], math.inf))
    counts: Counter = Counter()
    for v in numeric_values:
        for label, lo, hi in buckets:
            if (lo == -math.inf and v < hi) or (hi == math.inf and v >= lo) or (lo <= v < hi):
                counts[label] += 1
                break
        else:
            counts[buckets[-1][0]] += 1
    total = sum(counts.values()) or 1
    return {k: round(c / total * 100, 2) for k, c in counts.items()}


def _build_numeric_buckets(values: List[Any], field_name: str = "") -> List[tuple]:
    numeric_values = [float(str(v).replace(",", "").strip()) for v in values if _is_number(v)]
    if not numeric_values:
        return []
    field_lower = str(field_name).lower()
    if any(t in field_lower for t in ["age", "dob", "birth"]) and len({int(v) for v in numeric_values}) > 8:
        return [
            ("Under 25", -math.inf, 25), ("25 - 34", 25, 35),
            ("35 - 44", 35, 45), ("45 - 54", 45, 55),
            ("55 - 64", 55, 65), ("65 and above", 65, math.inf),
        ]
    minimum, maximum = min(numeric_values), max(numeric_values)
    if math.isclose(minimum, maximum):
        return [(f"{minimum:g}", -math.inf, math.inf)]
    span = maximum - minimum
    step = max(span / 6.0, 1.0)
    edges = [minimum + step * i for i in range(6)]
    buckets = [(f"{math.floor(edges[i])} - {math.ceil(edges[i+1])-1}", edges[i], edges[i+1]) for i in range(5)]
    buckets.append((f"{math.floor(edges[5])}+", edges[5], math.inf))
    return buckets


def _label_numeric_value(value: Any, buckets: List[tuple]) -> str:
    if not _is_number(value) or not buckets:
        return "missing"
    v = float(str(value).replace(",", "").strip())
    for label, lo, hi in buckets:
        if (lo == -math.inf and v < hi) or (hi == math.inf and v >= lo) or (lo <= v < hi):
            return label
    return buckets[-1][0]


def _compress_distribution(distribution: Dict[str, float], max_bars: int = 8) -> Dict[str, float]:
    if len(distribution) <= max_bars:
        return distribution
    items = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
    kept = items[:max_bars - 1]
    other = round(sum(v for _, v in items[max_bars - 1:]), 2)
    result = dict(kept)
    if other > 0:
        result["Other"] = other
    return result


def _summarize_distribution(values: List[Any], prefer_numeric_buckets: bool = False, field_name: str = "") -> Dict[str, float]:
    cleaned = [_normalize_value(v) for v in values]
    cleaned = [v for v in cleaned if v.lower() != "missing"]
    if prefer_numeric_buckets:
        numeric_values = [v for v in values if _is_number(v)]
        if len({str(v).strip() for v in numeric_values}) > 8 and numeric_values:
            return _bucket_numeric(numeric_values, field_name=field_name)
    if not cleaned:
        return {}
    counts = Counter(cleaned)
    total = sum(counts.values()) or 1
    distribution = {k: round(c / total * 100, 2) for k, c in counts.most_common()}
    return _compress_distribution(distribution)


def _dominant_value(distribution: Dict[str, float]) -> Dict[str, Any]:
    if not distribution:
        return {"dominant_group": None, "dominant_percentage": 0}
    group, value = max(distribution.items(), key=lambda x: x[1])
    return {"dominant_group": group, "dominant_percentage": value}


def _detect_positive_label(values: List[Any]) -> str:
    normalized = [str(v).strip().lower() for v in values if str(v).strip()]
    # "high" first for medical datasets; "priority approved" before "approved"
    preferred = ["priority approved", "high", "approved", "yes", "hired", "accepted", "1", "true", "granted", "selected"]
    for label in preferred:
        if label in normalized:
            return label
    return normalized[0] if normalized else "approved"


# ---------------------------------------------------------------------------
# FIX: _approval_rate_for_group
# BUG 1+3: normalize case with lower().title() so MALE/male/Male all match "Male"
# BUG 2:   never skip groups — even tiny groups (n=2,3) with 0% approval are shown
# ---------------------------------------------------------------------------

def _approval_rate_for_group(
    rows: List[Dict[str, Any]],
    field: str,
    group_label: str,
    outcome_field: str,
    positive_label: str,
    buckets: Optional[List[tuple]] = None,
) -> float:
    group_rows = []
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        if buckets:
            current_label = _label_numeric_value(value, buckets)
        else:
            # NORMALIZE: lower().title() merges MALE + Male + male → "Male"
            raw = str(value).strip()
            if raw.lower() in {"missing", "unknown", "nan", "none", ""}:
                continue
            current_label = raw.lower().title()
        if current_label == group_label:
            group_rows.append(row)

    if not group_rows:
        return 0.0  # return 0% for tiny groups — don't skip them

    positive_values = {
        positive_label.lower(),
        "priority approved", "approved", "yes", "hired",
        "accepted", "1", "true", "granted", "high", "selected",
    }
    approved = sum(
        1 for row in group_rows
        if _normalize_value(row.get(outcome_field)).lower() in positive_values
    )
    return round((approved / len(group_rows)) * 100, 2)


def _normalize_category(value: str) -> str:
    value = str(value or "").strip().upper()
    if value not in {"PROTECTED", "PROXY", "OUTCOME", "IDENTIFIER", "IRRELEVANT"}:
        return "IRRELEVANT"
    return value


def _parse_classifications(raw: Dict[str, Any], fieldnames: List[str]) -> List[Dict[str, Any]]:
    items = raw.get("classifications", [])
    parsed: List[Dict[str, Any]] = []
    seen: set = set()
    field_lookup = {str(f).strip().lower(): f for f in fieldnames}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        original = str(item.get("original_column") or item.get("column") or "").strip()
        display = str(item.get("display_name") or _display_name(original)).strip()
        category = _normalize_category(item.get("category", "IRRELEVANT"))
        reason = str(item.get("reason", "")).strip()
        if not original:
            continue
        resolved = field_lookup.get(original.lower(), original)
        key = resolved.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed.append({"original_column": resolved, "display_name": display or _display_name(resolved), "category": category, "reason": reason})
    return parsed


def _classification_map(classifications: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {item["original_column"]: item for item in classifications}


def _fallback_classify_column(column: str) -> Dict[str, Any]:
    lowered = str(column).strip().lower()
    protected_tokens = ["gender", "sex", "age", "race", "ethnicity", "religion", "nationality", "marital", "disability", "sexuality"]
    proxy_tokens = ["zip", "zipcode", "postal", "postcode", "neighborhood", "district", "area", "school", "university", "club", "association", "surname", "last_name", "language", "mother_tongue", "employment_status", "job_type", "occupation", "insurance_type"]
    outcome_tokens = ["outcome", "decision", "result", "status", "priority", "target", "approved", "rejected", "hired", "selected"]
    identifier_tokens = ["id", "name", "email", "phone", "applicant", "patient"]

    if any(token in lowered for token in protected_tokens):
        return {"original_column": column, "display_name": _display_name(column), "category": "PROTECTED", "reason": "Column name suggests a protected attribute."}
    if any(token in lowered for token in proxy_tokens):
        return {"original_column": column, "display_name": _display_name(column), "category": "PROXY", "reason": "Column name suggests an indirect proxy for a protected attribute."}
    if any(token in lowered for token in outcome_tokens):
        return {"original_column": column, "display_name": _display_name(column), "category": "OUTCOME", "reason": "Column name suggests a target or decision outcome."}
    if any(token in lowered for token in identifier_tokens):
        return {"original_column": column, "display_name": _display_name(column), "category": "IDENTIFIER", "reason": "Column name looks like an identifier."}
    return {"original_column": column, "display_name": _display_name(column), "category": "IRRELEVANT", "reason": "Column does not look protected, proxy, or outcome related."}


def _fallback_classifications(fieldnames: List[str]) -> List[Dict[str, Any]]:
    return [_fallback_classify_column(field) for field in fieldnames]


def _risk_rank(value: str) -> int:
    mapping = {"LOW": 0, "LOW RISK": 0, "MEDIUM": 1, "MEDIUM RISK": 1, "HIGH": 2, "HIGH RISK": 2}
    return mapping.get(str(value or "").strip().upper(), 0)


def _proxy_risk(distribution: Dict[str, float]) -> str:
    dominant = _dominant_value(distribution)
    share = float(dominant.get("dominant_percentage") or 0)
    if share >= 80:
        return "HIGH RISK"
    if share >= 65:
        return "MEDIUM RISK"
    return "LOW RISK"


def _fallback_summary(protected_findings: List[Dict[str, Any]], proxy_findings: List[Dict[str, Any]]) -> str:
    if not protected_findings and not proxy_findings:
        return "No clear protected-column bias or proxy warning was detected in the uploaded dataset."
    parts: List[str] = []
    if protected_findings:
        parts.append(f"{len(protected_findings)} biased protected column{'s' if len(protected_findings) != 1 else ''}")
    if proxy_findings:
        parts.append(f"{len(proxy_findings)} proxy warning{'s' if len(proxy_findings) != 1 else ''}")
    return "Detected " + " and ".join(parts) + " that need review."


def _fallback_reason(finding: Dict[str, Any]) -> str:
    if finding.get("type") == "protected":
        return (
            f"{finding['biased_value']} has a {finding['gap']}% lower approval rate than "
            f"{finding['reference_value']} in {finding['display_name']}."
        )
    return (
        f"{finding['display_name']} can act as a proxy column, and {finding['biased_value']} appears in "
        f"{finding['biased_share']}% of rows."
    )


def _fallback_recommendation(finding: Dict[str, Any]) -> str:
    if finding.get("type") == "protected":
        return (
            f"Rebalance approved and rejected records for {finding['biased_value']}, review rules tied to "
            f"{finding['display_name']}, and drop this field from training if it is not required."
        )
    return (
        f"Reduce or remove {finding['display_name']} from model training, or group its values into broader "
        f"non-sensitive categories before using the uploaded data."
    )


def _build_dataset_findings(
    protected_columns: List[Dict[str, Any]],
    proxy_columns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    protected_findings: List[Dict[str, Any]] = []
    proxy_findings: List[Dict[str, Any]] = []

    for item in protected_columns:
        risk = str(item.get("bias_risk") or item.get("verdict") or "LOW RISK").upper()
        if _risk_rank(risk) <= 0:
            continue
        lowest_group = item.get("lowest_group")
        lowest_percentage = round(float(item.get("lowest_percentage") or 0), 2)
        highest_group = item.get("highest_group")
        highest_percentage = round(float(item.get("highest_percentage") or 0), 2)
        if lowest_group is None or highest_group is None:
            continue
        protected_findings.append(
            {
                "key": f"protected:{item.get('original_column')}:{lowest_group}",
                "type": "protected",
                "column": item.get("original_column") or item.get("column"),
                "display_name": item.get("display_name") or item.get("column"),
                "biased_value": str(lowest_group),
                "biased_rate": lowest_percentage,
                "reference_value": str(highest_group),
                "reference_rate": highest_percentage,
                "gap": round(float(item.get("gap") or 0), 2),
                "risk": risk,
                "reason": "",
                "recommendation": "",
            }
        )

    for item in proxy_columns:
        distribution = item.get("distribution") or {}
        dominant = _dominant_value(distribution)
        risk = _proxy_risk(distribution)
        proxy_findings.append(
            {
                "key": f"proxy:{item.get('original_column')}:{dominant.get('dominant_group')}",
                "type": "proxy",
                "column": item.get("original_column") or item.get("column"),
                "display_name": item.get("display_name") or item.get("column"),
                "biased_value": str(dominant.get("dominant_group") or "unknown"),
                "biased_share": round(float(dominant.get("dominant_percentage") or 0), 2),
                "risk": risk,
                "reason": "",
                "recommendation": "",
            }
        )

    return {"protected_findings": protected_findings, "proxy_findings": proxy_findings}


def _apply_llm_dataset_guidance(
    protected_findings: List[Dict[str, Any]],
    proxy_findings: List[Dict[str, Any]],
    outcome_column: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    fallback = {
        "summary": _fallback_summary(protected_findings, proxy_findings),
        "items": [
            {
                "key": finding["key"],
                "reason": _fallback_reason(finding),
                "recommendation": _fallback_recommendation(finding),
            }
            for finding in [*protected_findings, *proxy_findings]
        ],
    }
    if not protected_findings and not proxy_findings:
        return fallback

    payload = {
        "outcome_column": (outcome_column or {}).get("display_name") or (outcome_column or {}).get("column") or "Outcome",
        "protected_findings": [
            {
                "key": finding["key"],
                "column": finding["display_name"],
                "biased_value": finding["biased_value"],
                "biased_rate": finding["biased_rate"],
                "reference_value": finding["reference_value"],
                "reference_rate": finding["reference_rate"],
                "gap": finding["gap"],
                "risk": finding["risk"],
            }
            for finding in protected_findings
        ],
        "proxy_findings": [
            {
                "key": finding["key"],
                "column": finding["display_name"],
                "biased_value": finding["biased_value"],
                "biased_share": finding["biased_share"],
                "risk": finding["risk"],
            }
            for finding in proxy_findings
        ],
    }

    prompt = (
        "You are explaining dataset bias findings to a non-technical user. "
        "Using only the structured data below, return JSON with a short summary and one simple reason plus one simple recommendation for each item. "
        "Each reason must be under 28 words. Each recommendation must be under 32 words. "
        "Recommendations should say what to change in the uploaded data or model inputs to reduce the bias. "
        "Return only JSON in this format: "
        '{"summary":"text","items":[{"key":"id","reason":"text","recommendation":"text"}]}. '
        f"Structured findings: {json.dumps(payload, ensure_ascii=False)}"
    )

    try:
        response = complete_json(prompt, fallback=fallback)
    except Exception:
        response = fallback

    if not isinstance(response, dict):
        return fallback
    items = response.get("items")
    if not isinstance(items, list):
        response["items"] = fallback["items"]
    if not isinstance(response.get("summary"), str) or not response.get("summary", "").strip():
        response["summary"] = fallback["summary"]
    return response


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class DataProfilerAgent:
    name = "DataProfilerAgent"

    def run(self, csv_path: str) -> Dict[str, Any]:
        extracted = _read_tabular_file(csv_path)
        rows = extracted["rows"]
        fieldnames = extracted["fieldnames"]
        samples = _sample_rows(rows, fieldnames)

        prompt = (
            SYSTEM_PROMPT_TEMPLATE
            .replace("<<COLUMN_NAMES>>", json.dumps(fieldnames, ensure_ascii=False))
            .replace("<<SAMPLE_ROWS>>", json.dumps(samples, ensure_ascii=False))
        )
        try:
            response = complete_json(prompt)
            classifications = _parse_classifications(response, fieldnames)
        except Exception:
            response = {}
            classifications = _fallback_classifications(fieldnames)
        if not classifications:
            classifications = _fallback_classifications(fieldnames)
        classified = _classification_map(classifications)

        protected_columns: List[Dict[str, Any]] = []
        proxy_columns: List[Dict[str, Any]] = []
        skipped_columns: List[str] = []
        summary_columns: List[Dict[str, Any]] = []
        outcome_column: Optional[Dict[str, Any]] = None
        outcome_distribution: Dict[str, float] = {}

        for field in fieldnames:
            classification = classified.get(field)
            category = classification.get("category", "IRRELEVANT") if classification else "IRRELEVANT"
            reason = classification.get("reason", "") if classification else ""
            display_name = classification.get("display_name", _display_name(field)) if classification else _display_name(field)

            if category in {"IDENTIFIER", "IRRELEVANT"}:
                skipped_columns.append(field)
                continue

            raw_values = [row.get(field) for row in rows]
            is_numeric = any(_is_number(v) for v in raw_values)

            if category == "OUTCOME":
                distribution = _summarize_distribution(raw_values, prefer_numeric_buckets=False)
                outcome_column = {"original_column": field, "display_name": display_name, "column": display_name, "distribution": distribution, "reason": reason}
                outcome_distribution = distribution
                summary_columns.append({"original_column": field, "display_name": display_name, "column": display_name, "distribution": distribution, "imbalance_flag": False, "proxy_flag": False, "dominant_share": max(distribution.values()) if distribution else 0, "value_kind": "categorical", "category": category, "reason": reason})
                continue

            if category == "PROTECTED":
                numeric_buckets = _build_numeric_buckets(raw_values, field_name=field) if is_numeric else []

                # Resolve outcome field
                if outcome_column and outcome_column.get("original_column") in fieldnames:
                    outcome_field = outcome_column["original_column"]
                else:
                    outcome_field = fieldnames[-1]
                positive_label = _detect_positive_label([row.get(outcome_field) for row in rows])

                if numeric_buckets:
                    # Numeric column (Age): label each value into a bucket
                    field_label_values = [
                        _label_numeric_value(value, numeric_buckets)
                        for value in raw_values
                        if _normalize_value(value).lower() not in {"missing", "unknown", "nan", "none"}
                    ]
                else:
                    # FIX BUG 1: normalize lower().title() so MALE+Male+male → "Male"
                    field_label_values = [
                        str(value).strip().lower().title()
                        for value in raw_values
                        if value is not None
                        and str(value).strip().lower() not in {"missing", "unknown", "nan", "none", ""}
                    ]

                # FIX BUG 2: dedupe preserving order — tiny groups are NOT dropped
                group_labels = list(dict.fromkeys(field_label_values))
                group_counter = Counter(field_label_values)
                total_group_rows = sum(group_counter.values()) or 1

                distribution = {
                    group: _approval_rate_for_group(rows, field, group, outcome_field, positive_label, buckets=numeric_buckets)
                    for group in group_labels
                }
                population_share = {
                    group: round((count / total_group_rows) * 100, 2)
                    for group, count in group_counter.items()
                }

                dominant = _dominant_value(distribution)
                highest_group, highest_percentage = max(distribution.items(), key=lambda item: item[1]) if distribution else (None, 0)
                lowest_group, lowest_percentage = min(distribution.items(), key=lambda item: item[1]) if distribution else (None, 0)
                gap = round(max(distribution.values()) - min(distribution.values()), 2) if distribution else 0.0
                verdict = "LOW" if gap < 5 else "MEDIUM" if gap < 15 else "HIGH"
                imbalanced = verdict != "LOW"

                protected_columns.append({"original_column": field, "display_name": display_name, "column": display_name, "reason": reason, "distribution": distribution, "population_share": population_share, "imbalanced": imbalanced, "dominant_group": dominant["dominant_group"], "dominant_percentage": dominant["dominant_percentage"], "highest_group": highest_group, "highest_percentage": round(float(highest_percentage or 0), 2), "lowest_group": lowest_group, "lowest_percentage": round(float(lowest_percentage or 0), 2), "gap": gap, "verdict": verdict, "bias_risk": f"{verdict} RISK"})
                summary_columns.append({"original_column": field, "display_name": display_name, "column": display_name, "distribution": distribution, "imbalance_flag": imbalanced, "proxy_flag": False, "dominant_share": dominant["dominant_percentage"], "value_kind": "numeric" if is_numeric else "categorical", "category": category, "reason": reason})
                continue

            if category == "PROXY":
                distribution = _summarize_distribution(raw_values, prefer_numeric_buckets=is_numeric, field_name=field)
                proxy_dominant = _dominant_value(distribution)
                proxy_columns.append({"original_column": field, "display_name": display_name, "column": display_name, "reason": reason, "distribution": distribution, "imbalanced": max(distribution.values()) > 70.0 if distribution else False, "dominant_value": proxy_dominant.get("dominant_group"), "dominant_share": round(float(proxy_dominant.get("dominant_percentage") or 0), 2), "bias_risk": _proxy_risk(distribution)})
                summary_columns.append({"original_column": field, "display_name": display_name, "column": display_name, "distribution": distribution, "imbalance_flag": max(distribution.values()) > 70.0 if distribution else False, "proxy_flag": True, "dominant_share": max(distribution.values()) if distribution else 0, "value_kind": "numeric" if is_numeric else "categorical", "category": category, "reason": reason})
                continue

            skipped_columns.append(field)

        # Fallback outcome detection
        if outcome_column is None:
            for field in fieldnames:
                if field not in skipped_columns:
                    distribution = _summarize_distribution([row.get(field) for row in rows], prefer_numeric_buckets=False, field_name=field)
                    outcome_column = {"original_column": field, "display_name": _display_name(field), "column": _display_name(field), "distribution": distribution, "reason": ""}
                    outcome_distribution = distribution
                    break

        findings = _build_dataset_findings(protected_columns, proxy_columns)
        llm_guidance = _apply_llm_dataset_guidance(
            findings["protected_findings"],
            findings["proxy_findings"],
            outcome_column,
        )
        guidance_lookup = {
            str(item.get("key")): item
            for item in llm_guidance.get("items", [])
            if isinstance(item, dict) and item.get("key")
        }

        all_findings = [*findings["protected_findings"], *findings["proxy_findings"]]
        for item in all_findings:
            guidance = guidance_lookup.get(item["key"], {})
            item["reason"] = str(guidance.get("reason") or _fallback_reason(item))
            item["recommendation"] = str(guidance.get("recommendation") or _fallback_recommendation(item))

        overall_risk = "LOW RISK"
        if all_findings:
            overall_risk = max(all_findings, key=lambda item: _risk_rank(item.get("risk"))).get("risk", "LOW RISK")
        overall_recommendations = list(dict.fromkeys(item["recommendation"] for item in all_findings if item.get("recommendation")))

        return {
            "protected_columns": protected_columns,
            "proxy_columns": proxy_columns,
            "outcome_column": outcome_column,
            "outcome_distribution": outcome_distribution,
            "skipped_columns": skipped_columns,
            "detection_method": "AI-powered automatic detection",
            "columns": summary_columns,
            "bias_findings": findings["protected_findings"],
            "proxy_findings": findings["proxy_findings"],
            "dataset_summary": llm_guidance.get("summary") or _fallback_summary(findings["protected_findings"], findings["proxy_findings"]),
            "overall_risk": overall_risk,
            "overall_recommendations": overall_recommendations,
            "row_count": len(rows),
            "sample_rows": samples,
            "classifications": classifications,
        }


def _build_agent_model() -> LiteLlm:
    model_name = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip()
    if "/" not in model_name:
        model_name = f"mistral/{model_name}"
    return LiteLlm(model=model_name)


def build_adk_agent() -> Agent:
    return Agent(
        name="DataProfilerAgent",
        model=_build_agent_model(),
        description="Uses Mistral to classify columns into protected, proxy, outcome, identifier, and irrelevant categories.",
        instruction="Read the uploaded dataset, sample the first five rows, and use the Mistral tool call pattern to classify columns. Return only the meaningful column analysis.",
        tools=[profile_dataset_tool],
        output_key="dataset_profile",
    )

adk_agent = build_adk_agent()
