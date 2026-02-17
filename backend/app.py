"""
QuoteCheck Backend - FastAPI app (v0)

This module defines the FastAPI application for QuoteCheck.

Block 1:
- Boot spine with a /health endpoint.

Block 1.5:
- Enable CORS so the local frontend (Vite dev server) can call the API.

Block 2:
- Add POST /analyze that returns a schema-valid *stub* QuoteCheckResult.
  This lets us lock down the contract (schema) and UI integration before
  introducing the OpenAi API call in Block 3.

Notes
-----
- The stub response is intentionally deterministic and simple.
- We include request_id + latency_ms for observability from day one.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.schema import (
    AnalyzeRequest,
    LineItem,
    MetaData,
    NormalizedCategory,
    Price,
    QuoteCheckResult,
    RecommendedAction,
    RiskLevel,
    UncertaintyMarkers,
)

from backend.core.run_logger import log_app_run

PROMPT_VERSION = "quotecheck_v0.1"
DEFAULT_MODEL = "gpt-5-mini"    # placeholder for now; becomes real in block 3
APP_RUN_LOG_PATH = "logs/app_runs.jsonl"

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

    Current behavior (Block 2 → Block 3 Slice 1)
    --------------------------------------------
    - Still returns a schema-valid *stub* payload (no OpenAI call yet).
    - Adds lightweight observability:
    - Generates a `request_id` per call
    - Measures `latency_ms`
    - Appends one JSONL log record to `logs/app_runs.jsonl` for every request
        (success or failure), including:
        - prompt_version, model
        - schema_valid flag
        - num_items and risk_counts
        - uncertainty markers (if available)
        - short error string (on failure)

    Why this step exists
    --------------------
    This locks in the "contract + traces" foundation before model integration, so
    we can debug and evaluate runs reliably once the OpenAI call is added.

    Parameters
    ----------
    req : AnalyzeRequest
        Request payload containing the raw quote text.

    Returns
    -------
    QuoteCheckResult
        A schema-valid structured response for UI rendering and evaluation.
    """

    t0 = time.perf_counter()
    request_id = str(uuid.uuid4())
    latency_ms = 0

    # Extremely simple heuristic stub: if the quote mentions brakes/tyres,
    # we include a red/yellow item. Othewise we return one unknown item.
    try:
        text_lower = req.quote_text.lower()
        items = []

        if "brake" in text_lower:
            items.append(
                LineItem(
                    name_raw="Brake service/ pads (from quote)",
                    normalized_category=NormalizedCategory.safety_critical,
                    recommended_action=RecommendedAction.needs_inspection,
                    risk_level=RiskLevel.red,
                    confidence=0.70,
                    rationale_short="Braking components are safety-critical. Ask for pad thickness and rotor condition evidence",
                    price=None,
                    evidence_needed=["Pad thickness measurement (mm)", "Rotor condition photo", "Reason for replacement"],
                )
            )

        if "tyre" in text_lower or "tire" in text_lower:
            items.append(
                LineItem(
                    name_raw="Tyre replacement (from quote)",
                    normalized_category=NormalizedCategory.safety_critical,
                    recommended_action=RecommendedAction.ask_for_evidence,
                    risk_level=RiskLevel.yellow,
                    confidence=0.65,
                    rationale_short="Tyres affect braking and handling. Ask for tread depth and sidewall condition details",
                    price=Price(amount=0.0, currency="INR"),
                    evidence_needed=["Tread depth (mm)", "Uneven wear explanation", "Sidewall damage photo (if any)"],
                )
            )
        
        if not items:
            items.append(
                LineItem(
                    name_raw="Unclear item(s) - needs clarification",
                    normalized_category=NormalizedCategory.unknown_needs_clarification,
                    recommended_action=RecommendedAction.unknown,
                    risk_level=RiskLevel.yellow,
                    confidence=0.35,
                    rationale_short="The quote text lacks enough detail to classify items reliably. Ask the service center for an itemized breakdown.",
                )
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        result = QuoteCheckResult(
            line_items=items,
            overall_summary=[
                "This is a v0 stub response to validate the end-to-end contract.",
                "Safety-critical items (like brakes/tyres) should be verified with evidence before approval.",
                "Ask for measurements, photos, and the specific failure reason for any recommendation.",
            ],
            verification_questions=[
                "Can you share photos/measurements that justify each recommended item?",
                "Which items are safety-critical vs optional preventive maintenance?",
                "Confirm whether the recommendation is OEM-specified or shop-suggested."
            ],
            things_to_verify=[
                "Request an itemized parts + labour breakdown for each line item.",
                "Ask for measurements (pad thickness, tread depth) where applicable.",
                "Confirm whether the recommendation is OEM-specified or shop-suggested.",
            ],
            uncertainty_markers=UncertaintyMarkers(
                ambiguous_items_present=True,
                missing_vehicle_context=True,
                needs_mechanic_confirmation=True,
            ),
            refusals=[],
            disclaimer="Not safety advice; verify with a certified mechanic.",
            metadata=MetaData(
                prompt_version=PROMPT_VERSION,
                model=DEFAULT_MODEL,
                created_at=datetime.now(timezone.utc),
                request_id=request_id,
                latency_ms=latency_ms,
                schema_valid=True,
            ),
        )

        # ---- logging on success ----
        risk_counts = {"red": 0, "yellow": 0, "green": 0}
        for it in result.line_items:
            rl = str(it.risk_level)
            if rl in risk_counts:
                risk_counts[rl] += 1

        log_app_run(
            log_path=APP_RUN_LOG_PATH,
            request_id=request_id,
            prompt_version=PROMPT_VERSION,
            model=DEFAULT_MODEL,
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
            model=DEFAULT_MODEL,
            latency_ms=latency_ms,
            schema_valid=False,
            num_items=0,
            risk_counts={"red": 0, "yellow": 0, "green": 0},
            uncertainty={},
            error=f"{type(e).__name__}: {e}",
        )
        raise