"""
OpenAI Analyzer (v0)

Returns a schema-validated QuoteCheckResult (not raw dict) so app.py stays thin.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Tuple

from openai import OpenAI

from backend.core.config import MODEL, OPENAI_API_KEY
from backend.core.prompt import PROMPT_VERSION, build_messages
from backend.core.schema import QuoteCheckResult
from backend.core.schema_export import quotecheck_result_schema_json


def analyze_quote_openai(*, quote_text: str, request_id: str) -> Tuple[QuoteCheckResult, int]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to backend/.env (untracked).")

    client = OpenAI(api_key=OPENAI_API_KEY)

    schema_str = quotecheck_result_schema_json()
    schema_obj = json.loads(schema_str)
    messages = build_messages(quote_text=quote_text, schema_json=schema_str)

    t0 = time.perf_counter()
    resp = client.responses.create(
        model=MODEL,
        input=messages,
        text={"format": {"type": "json_schema", "strict": True, "schema": schema_obj}},
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    payload = json.loads(resp.output_text.strip())

    # Override metadata with server-truth
    payload["metadata"] = {
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "created_at": datetime.now(timezone.utc),
        "request_id": request_id,
        "latency_ms": latency_ms,
        "schema_valid": True,
    }

    result = QuoteCheckResult.model_validate(payload)
    return result, latency_ms