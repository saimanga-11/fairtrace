from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from mistralai import Mistral


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates.extend(fenced)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def complete_text(prompt: str, fallback: Optional[str] = None) -> str:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured.")

    try:
        client = Mistral(api_key=api_key)
        response = client.chat.complete(
            model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    except Exception:
        raise RuntimeError("Mistral request failed.") from None


def complete_json(prompt: str, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raw = complete_text(prompt)
    parsed = _extract_json(raw)
    if parsed:
        return parsed
    return fallback or {}
