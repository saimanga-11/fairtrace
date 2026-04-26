import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "database" / "audit.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                input_features TEXT NOT NULL,
                original_outcome TEXT NOT NULL DEFAULT 'unknown',
                decision_outcome TEXT NOT NULL,
                corrected_outcome TEXT,
                bias_analysis TEXT,
                reasoning_chain TEXT NOT NULL,
                bias_verdict TEXT NOT NULL,
                counterfactual_result TEXT NOT NULL,
                flagged INTEGER NOT NULL DEFAULT 0,
                corrected INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()
    _ensure_columns()


def _ensure_columns() -> None:
    with _connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()}
        if "original_outcome" not in columns:
            conn.execute("ALTER TABLE decisions ADD COLUMN original_outcome TEXT NOT NULL DEFAULT 'unknown'")
        if "corrected_outcome" not in columns:
            conn.execute("ALTER TABLE decisions ADD COLUMN corrected_outcome TEXT")
        if "bias_analysis" not in columns:
            conn.execute("ALTER TABLE decisions ADD COLUMN bias_analysis TEXT")
        conn.commit()


def _parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "input_features": _parse_json(row["input_features"]),
        "original_outcome": row["original_outcome"] if "original_outcome" in row.keys() else row["decision_outcome"],
        "decision_outcome": row["decision_outcome"],
        "corrected_outcome": row["corrected_outcome"] if "corrected_outcome" in row.keys() else None,
        "bias_analysis": _parse_json(row["bias_analysis"]) if "bias_analysis" in row.keys() else None,
        "reasoning_chain": _parse_json(row["reasoning_chain"]),
        "bias_verdict": row["bias_verdict"],
        "counterfactual_result": _parse_json(row["counterfactual_result"]),
        "flagged": bool(row["flagged"]),
        "corrected": bool(row["corrected"]),
    }


def _json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def save_decision(record: Dict[str, Any]) -> int:
    _ensure_schema()
    decision_outcome = record.get("decision_outcome", "unknown")
    payload = {
        "timestamp": record.get("timestamp")
        or datetime.now(timezone.utc).isoformat(),
        "input_features": _json(record.get("input_features", {})),
        "original_outcome": record.get("original_outcome", decision_outcome),
        "decision_outcome": decision_outcome,
        "corrected_outcome": record.get("corrected_outcome"),
        "bias_analysis": _json(record.get("bias_analysis", {})),
        "reasoning_chain": _json(record.get("reasoning_chain", {})),
        "bias_verdict": record.get("bias_verdict", "UNKNOWN"),
        "counterfactual_result": _json(record.get("counterfactual_result", {})),
        "flagged": int(bool(record.get("flagged", False))),
        "corrected": int(bool(record.get("corrected", False))),
    }
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO decisions (
                timestamp, input_features, original_outcome, decision_outcome, corrected_outcome, bias_analysis, reasoning_chain,
                bias_verdict, counterfactual_result, flagged, corrected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["timestamp"],
                payload["input_features"],
                payload["original_outcome"],
                payload["decision_outcome"],
                payload["corrected_outcome"],
                payload["bias_analysis"],
                payload["reasoning_chain"],
                payload["bias_verdict"],
                payload["counterfactual_result"],
                payload["flagged"],
                payload["corrected"],
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_all_decisions() -> List[Dict[str, Any]]:
    _ensure_schema()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY datetime(timestamp) DESC, id DESC"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_decision(decision_id: int) -> Optional[Dict[str, Any]]:
    _ensure_schema()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    return _row_to_dict(row) if row else None


def flag_decision(decision_id: int) -> Optional[Dict[str, Any]]:
    _ensure_schema()
    with _connect() as conn:
        conn.execute("UPDATE decisions SET flagged = 1 WHERE id = ?", (decision_id,))
        conn.commit()
    return get_decision(decision_id)


def correct_decision(decision_id: int, new_outcome: str) -> Optional[Dict[str, Any]]:
    _ensure_schema()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE decisions
            SET original_outcome = COALESCE(original_outcome, decision_outcome),
                decision_outcome = ?,
                corrected_outcome = ?,
                corrected = 1
            WHERE id = ?
            """,
            (new_outcome, new_outcome, decision_id),
        )
        conn.commit()
    return get_decision(decision_id)

