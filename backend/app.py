"""
QuoteCheck Backend (v0) — FastAPI service

This module defines the QuoteCheck API server and wires together:
- the schema-first contract (Pydantic models),
- the analysis pipeline (stub mode vs OpenAI mode),
- and lightweight observability (JSONL run logs).

Key endpoints
-------------
GET /health
    Simple health check used to verify the server is running.

POST /analyze
    Accepts raw quote text and returns a structured QuoteCheckResult.

Runtime modes (feature-flagged)
-------------------------------
The analyzer supports two modes controlled by environment/config:

1) Stub mode (default)
   - Returns a deterministic, schema-valid stub result based on simple heuristics.
   - Useful for development, UI work, and zero-cost demos.

2) OpenAI mode
   - Enabled when QUOTECHECK_USE_OPENAI=1 (loaded via backend/.env).
   - Calls the OpenAI Responses API requesting strict JSON Schema structured output.
   - Validates the model JSON against the QuoteCheckResult Pydantic contract.
   - Overrides metadata fields with server-truth (request_id, model, prompt_version, latency).

Observability
-------------
Each /analyze request produces exactly one JSONL log record appended to:
- logs/app_runs.jsonl

Log records include:
- request_id, created_at
- prompt_version, model, latency_ms
- schema_valid, num_items, risk_counts
- uncertainty markers and a short error string on failure

Configuration and secrets
-------------------------
- Local development uses an untracked backend/.env file loaded via python-dotenv.
- backend/.env.example is committed as a template (no secrets).
- OPENAI_API_KEY must never be committed to git.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv("backend/.env")

import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from backend.core.schema import AnalyzeRequest, QuoteCheckResult
from backend.core.run_logger import log_app_run
from backend.core.prompt import PROMPT_VERSION
from backend.core.config import APP_RUN_LOG_PATH, USE_OPENAI, MODEL
from backend.core.openai_analyzer import analyze_quote_openai
from backend.core.stub_analyzer import analyze_quote_stub


app = FastAPI(title="QuoteCheck API", version="0.1.0")

# Local development CORS policy.
# Vite dev server typically runs on http://localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """
    Health check endpoint.

    Returns
    -------
    dict
        A small JSON payload indicating the server is alive.
    """
    return {"status": "ok"}


@app.post("/analyze", response_model=QuoteCheckResult)
def analyze(req: AnalyzeRequest):
    """
    Analyze a service quote and return a structured QuoteCheckResult.

    Routing
    -------
    - If USE_OPENAI is enabled: call OpenAI analyzer (Responses API, strict schema)
    - Otherwise: call deterministic stub analyzer

    Observability
    -------------
    Always logs exactly one JSONL record to logs/app_runs.jsonl per request
    (success or failure), including risk_counts and uncertainty markers.
    """
    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())

    try:
        # Analyzer selection (keeps app.py thin)
        if USE_OPENAI:
            result, latency_ms = analyze_quote_openai(quote_text=req.quote_text, request_id=request_id)
        else:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            result = analyze_quote_stub(quote_text=req.quote_text, request_id=request_id, latency_ms=latency_ms)

        # Common: compute risk_counts for logs
        risk_counts = {"red": 0, "yellow": 0, "green": 0}
        for it in result.line_items:
            rl = it.risk_level.value if hasattr(it.risk_level, "value") else str(it.risk_level).lower()
            if rl in risk_counts:
                risk_counts[rl] += 1

        # Common: success logging
        log_app_run(
            log_path=APP_RUN_LOG_PATH,
            request_id=request_id,
            prompt_version=result.metadata.prompt_version,
            model=result.metadata.model,
            latency_ms=latency_ms,
            schema_valid=True,
            num_items=len(result.line_items),
            risk_counts=risk_counts,
            uncertainty=result.uncertainty_markers.model_dump(),
            error=None,
        )
        return result

    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        log_app_run(
            log_path=APP_RUN_LOG_PATH,
            request_id=request_id,
            prompt_version=PROMPT_VERSION,
            model=MODEL,
            latency_ms=latency_ms,
            schema_valid=False,
            num_items=0,
            risk_counts={"red": 0, "yellow": 0, "green": 0},
            uncertainty={},
            error=f"{type(e).__name__}: {e}",
        )
        raise