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

from pathlib import Path

from dotenv import load_dotenv
# Resolve backend/.env relative to this file, not the process CWD, so a hosted
# deployment that launches uvicorn from any directory behaves the same as local
# dev. override=False (the default) keeps real environment variables — e.g. the
# eval runner's QUOTECHECK_USE_OPENAI — authoritative over the file.
load_dotenv(Path(__file__).resolve().parent / ".env")

import asyncio
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool


from backend.core.schema import AnalyzeRequest, MAX_QUOTE_TEXT_CHARS, QuoteCheckResult
from backend.core.run_logger import log_app_run
from backend.core.prompt import PROMPT_VERSION
from backend.core.config import (
    ALLOWED_ORIGINS,
    APP_RUN_LOG_PATH,
    DEMO_ANALYZER_MODEL,
    MODEL,
    USE_OPENAI,
)
from backend.core.admission import provider_admission
from backend.core.errors import FailureCategory, QuoteCheckError, error_response_body
from backend.core.openai_analyzer import analyze_quote_openai
from backend.core.stub_analyzer import analyze_quote_stub


app = FastAPI(title="QuoteCheck API", version="0.1.0")

# Provenance label for logs — stays mode-accurate on success and failure paths.
ANALYZER_NAME = "openai" if USE_OPENAI else "demo"


@app.exception_handler(QuoteCheckError)
async def _quotecheck_error_handler(request: Request, exc: QuoteCheckError) -> JSONResponse:
    """Render a classified failure as a small, user-safe JSON body.

    Never exposes stack traces, API keys, raw provider payloads, or internal
    filenames — only ``code``, ``message``, ``retryable``, ``request_id``.

    ``async`` since SCALE-004: it is pure rendering, and as a sync handler
    Starlette would dispatch it to the worker threadpool, so a
    ``capacity_exceeded`` rejection would have to queue for a worker token.
    """
    return JSONResponse(status_code=exc.http_status, content=error_response_body(exc))


@app.exception_handler(RequestValidationError)
def _request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render request-shape failures in the same small body as classified errors.

    FastAPI's default 422 is a list of Pydantic error dicts (field names, internal
    types). A stranger should instead get one product-safe sentence. ``code`` here
    is a response string, not a FailureCategory — the QC-4 taxonomy is unchanged.
    Covers oversized quote text, malformed JSON, and a missing/!invalid body.
    """
    request_id = str(uuid.uuid4())
    too_long = any(err.get("type") == "string_too_long" for err in exc.errors())
    if too_long:
        message = (
            f"That quote is too long. Please shorten it to {MAX_QUOTE_TEXT_CHARS:,} "
            "characters or fewer and try again."
        )
    else:
        message = "That request wasn't valid. Paste the quote text and try again."
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "invalid_request",
                "message": message,
                "retryable": False,
                "request_id": request_id,
            }
        },
    )


def _safe_log(**fields) -> None:
    """Write one run-log record; a logging failure must not mask the analysis outcome."""
    try:
        log_app_run(**fields)
    except Exception:  # noqa: BLE001 - observability is best-effort, never fatal
        pass

# Allowed browser origins come from QUOTECHECK_ALLOWED_ORIGINS (see
# backend/core/config.py). Unset -> the local Vite dev server; for a public
# deployment it must be the exact frontend origin(s). Never "*", and credentials
# stay disabled so a broad origin can never carry cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
async def analyze(req: AnalyzeRequest):
    """
    Analyze a service quote and return a structured QuoteCheckResult.

    Routing
    -------
    - If USE_OPENAI is enabled: call OpenAI analyzer (Responses API, strict schema)
    - Otherwise: call deterministic stub analyzer

    Provider admission (SCALE-004)
    ------------------------------
    This coroutine is a narrow wrapper; the analysis itself (and the blocking
    provider call) stays synchronous in ``_analyze_sync`` on the worker
    threadpool. In OpenAI mode a slot is taken *here*, on the event loop,
    before anything is dispatched to the threadpool, so admission is decided
    before anyio's worker queue can become the admission mechanism. No free
    slot -> an immediate ``capacity_exceeded`` (503) with zero provider calls.

    The slot covers the whole threadpool call, including the retry, and is
    released exactly once, when that call has finished. The admitted work runs
    in its own task behind ``asyncio.shield``: if this request's task is
    cancelled (e.g. uvicorn's graceful-shutdown timeout), the caller stops
    waiting but the slot stays held until the worker thread - and so the
    provider call - is actually done. (anyio's shielded ``run_sync`` does not
    stop a native asyncio ``Task.cancel()`` from resuming the awaiting
    coroutine early, so releasing after a plain ``await`` could free a slot
    while its provider call is still running.) Demo mode takes no slot.

    Observability
    -------------
    Always logs exactly one JSONL record to logs/app_runs.jsonl per request
    (success, failure, or admission rejection).
    """
    t_entry = time.perf_counter()
    request_id = str(uuid.uuid4())
    if not USE_OPENAI:
        return await run_in_threadpool(_analyze_sync, req, request_id)

    if not provider_admission.try_acquire():
        err = QuoteCheckError(
            FailureCategory.CAPACITY_EXCEEDED,
            request_id=request_id,
            provider_attempts=0,
            detail=(
                f"provider admission budget full "
                f"({provider_admission.in_flight}/{provider_admission.capacity} in flight)"
            ),
        )
        # Synchronous JSONL append on the event loop: its cost is part of the
        # measured rejection latency (SCALE-004 evidence), not hidden elsewhere.
        _safe_log(
            log_path=APP_RUN_LOG_PATH,
            request_id=request_id,
            prompt_version=PROMPT_VERSION,
            model=MODEL,
            latency_ms=int((time.perf_counter() - t_entry) * 1000),
            schema_valid=False,
            num_items=0,
            risk_counts={"red": 0, "yellow": 0, "green": 0},
            uncertainty={},
            error=err.log_error_field(),
            analyzer=ANALYZER_NAME,
            success=False,
            failure_category=err.category.value,
            retryable=err.retryable,
            provider_attempts=0,
        )
        raise err

    admitted = asyncio.get_running_loop().create_task(_run_admitted(req, request_id))
    admitted.add_done_callback(_consume_task_outcome)
    return await asyncio.shield(admitted)


async def _run_admitted(req: AnalyzeRequest, request_id: str):
    """Run one admitted OpenAI-mode analysis; release its slot exactly once, after
    the worker thread has returned (success or any failure)."""
    try:
        return await run_in_threadpool(_analyze_sync, req, request_id)
    finally:
        provider_admission.release()


def _consume_task_outcome(task: "asyncio.Task") -> None:
    """Retrieve an abandoned admitted task's exception (its caller was cancelled),
    so asyncio doesn't report it as never retrieved. The run log already has it."""
    if not task.cancelled():
        task.exception()


def _analyze_sync(req: AnalyzeRequest, request_id: str):
    """The synchronous analysis body (unchanged by SCALE-004), run on a worker thread."""
    t0 = time.perf_counter()
    # Provenance must stay mode-accurate on every path: a Demo-mode failure
    # never called OpenAI, so it must not log an OpenAI model id.
    failure_model = MODEL if USE_OPENAI else DEMO_ANALYZER_MODEL

    try:
        # Analyzer selection (keeps app.py thin)
        if USE_OPENAI:
            result, latency_ms, provider_attempts = analyze_quote_openai(
                quote_text=req.quote_text, request_id=request_id
            )
        else:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            provider_attempts = None
            result = analyze_quote_stub(quote_text=req.quote_text, request_id=request_id, latency_ms=latency_ms)

        # Common: compute risk_counts for logs
        risk_counts = {"red": 0, "yellow": 0, "green": 0}
        for it in result.line_items:
            rl = it.risk_level.value if hasattr(it.risk_level, "value") else str(it.risk_level).lower()
            if rl in risk_counts:
                risk_counts[rl] += 1

        # Common: success logging
        _safe_log(
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
            analyzer=ANALYZER_NAME,
            success=True,
            provider_attempts=provider_attempts,
        )
        return result

    except QuoteCheckError as e:
        if e.request_id is None:
            e.request_id = request_id
        latency_ms = int((time.perf_counter() - t0) * 1000)
        _safe_log(
            log_path=APP_RUN_LOG_PATH,
            request_id=request_id,
            prompt_version=PROMPT_VERSION,
            model=failure_model,
            latency_ms=latency_ms,
            schema_valid=False,
            num_items=0,
            risk_counts={"red": 0, "yellow": 0, "green": 0},
            uncertainty={},
            error=e.log_error_field(),
            analyzer=ANALYZER_NAME,
            success=False,
            failure_category=e.category.value,
            retryable=e.retryable,
            cause_type=e.cause_type,
            provider_status=e.provider_status,
            provider_request_id=e.provider_request_id,
            response_status=e.response_status,
            incomplete_reason=e.incomplete_reason,
            provider_attempts=e.provider_attempts,
        )
        raise

    except Exception as e:
        # Any unclassified failure becomes an explicit internal_error — the raw
        # exception is kept only as `cause` (class name logged, never its text).
        wrapped = QuoteCheckError(FailureCategory.INTERNAL_ERROR, request_id=request_id, cause=e)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        _safe_log(
            log_path=APP_RUN_LOG_PATH,
            request_id=request_id,
            prompt_version=PROMPT_VERSION,
            model=failure_model,
            latency_ms=latency_ms,
            schema_valid=False,
            num_items=0,
            risk_counts={"red": 0, "yellow": 0, "green": 0},
            uncertainty={},
            error=wrapped.log_error_field(),
            analyzer=ANALYZER_NAME,
            success=False,
            failure_category=wrapped.category.value,
            retryable=wrapped.retryable,
            cause_type=wrapped.cause_type,
            provider_attempts=None,
        )
        raise wrapped