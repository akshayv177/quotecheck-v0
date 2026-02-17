"""
Run Logger (v0)

This module implements lightweight JSONL logging for QuoteCheck runs.

Why JSONL?
- Append-only, easy to inspect with grep/jq
- Easy to batch-analyze later (eval, dashboards)
- Friendly for "run traces" without needing a DB in v0

Each call to the API should write exactly one log line to:
- logs/app_runs.jsonl

This logger is intentionally dependency-light and synchronous for v0.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_parent_dir(path:str) -> None:
    """Ensure parent directory exists for a file path"""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    """
    Append a single JSON object as one line in a JSONL fine.

    Parameters
    ----------
    path: str
        File path to append to.
    obj: dict
        JSON-serializable dictionary.
    """
    ensure_parent_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def log_app_run(
        *,
        log_path: str,
        request_id: str,
        prompt_version: str,
        model: str,
        latency_ms: int,
        schema_valid: bool,
        num_items: int,
        risk_counts: Dict[str, int],
        uncertainty: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
) -> None:
    """
    Write one structured log record for an interactive /analyze run.

    This is the minimal observability spine for v0.

    Notes
    -----
    - 'schema_valid' refers to whether the response validated against the 
       QuoteCheckResult schema.
    - 'error' should be a short string (no giant stack traces) 
    """
    record = {
        "event": "quotecheck_analyze",
        "created_at": utc_now_iso(),
        "request_id": request_id,
        "prompt_version": prompt_version,
        "model": model,
        "latency_ms": latency_ms,
        "schema_valid": schema_valid,
        "num_items": num_items,
        "risk_counts": risk_counts,
        "uncertainty": uncertainty,
        "error": error,
    }
    append_jsonl(log_path, record)