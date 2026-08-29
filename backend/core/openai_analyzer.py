"""
OpenAI Analyzer (v0 + QC-4 reliability hardening)

Returns a schema-validated QuoteCheckResult (not a raw dict) so app.py stays thin.

Failure handling (QC-4)
-----------------------
Every provider, model-output, or configuration failure on this path is raised as
a single classified ``QuoteCheckError``; a raw OpenAI SDK exception never
escapes this module.

QuoteCheck owns the one permitted automatic retry:
- the OpenAI SDK client is constructed with ``max_retries=0`` (no SDK retry, no
  SDK backoff);
- a small bounded loop here retries **once**, and only for clearly transient
  provider/transport failures (connection error, timeout, provider >= 500);
- the maximum number of provider calls for a single request is
  ``config.OPENAI_MAX_ATTEMPTS`` (2).

There is no fallback to the Demo analyzer. A successful HTTP response is not
assumed to contain a usable structured result — refusal, incomplete, empty, and
malformed responses are each classified explicitly. Final Pydantic validation
against ``QuoteCheckResult`` is mandatory and is never repaired with a second
call or invented defaults.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI

from backend.core.config import (
    MODEL,
    OPENAI_API_KEY,
    OPENAI_MAX_ATTEMPTS,
    OPENAI_TIMEOUT_DEFAULT_SECONDS,
    OPENAI_TIMEOUT_SECONDS_RAW,
)
from backend.core.errors import (
    FailureCategory,
    QuoteCheckError,
    classify_openai_exception,
    is_transient_openai_exception,
)
from backend.core.prompt import PROMPT_VERSION, build_messages
from backend.core.schema import QuoteCheckResult
from backend.core.schema_export import quotecheck_result_schema_obj


def resolve_openai_timeout_seconds() -> float:
    """Validate ``QUOTECHECK_OPENAI_TIMEOUT_SECONDS`` -> positive finite float.

    A malformed reliability setting fails here as an explicit
    ``configuration_error`` rather than later as an opaque httpx/OpenAI failure.
    """
    raw = OPENAI_TIMEOUT_SECONDS_RAW
    if raw is None or str(raw).strip() == "":
        return float(OPENAI_TIMEOUT_DEFAULT_SECONDS)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise QuoteCheckError(
            FailureCategory.CONFIGURATION_ERROR,
            detail="invalid QUOTECHECK_OPENAI_TIMEOUT_SECONDS (not a number)",
        )
    if not math.isfinite(value) or value <= 0:
        raise QuoteCheckError(
            FailureCategory.CONFIGURATION_ERROR,
            detail="invalid QUOTECHECK_OPENAI_TIMEOUT_SECONDS (must be finite and > 0)",
        )
    return value


def _refusal_text(resp: Any) -> Optional[str]:
    """Return the refusal string if the Responses output carries a refusal part."""
    for item in getattr(resp, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "refusal":
                return getattr(part, "refusal", "") or ""
    return None


def _extract_structured_payload(resp: Any) -> Dict[str, Any]:
    """Turn a Responses API result into a JSON object, or raise a classified error.

    A successful HTTP response does NOT imply a usable QuoteCheck result.
    """
    status = getattr(resp, "status", None)
    incomplete = getattr(resp, "incomplete_details", None)
    incomplete_reason = getattr(incomplete, "reason", None) if incomplete is not None else None

    # 1) Refusal: an explicit refusal content part, or a content-filter stop.
    refusal = _refusal_text(resp)
    if refusal is not None or incomplete_reason == "content_filter":
        raise QuoteCheckError(
            FailureCategory.PROVIDER_REFUSAL,
            response_status=status,
            incomplete_reason=incomplete_reason,
            detail="model declined to produce a result",
        )

    # 2) Incomplete / failed / errored generation.
    resp_error = getattr(resp, "error", None)
    if status in {"incomplete", "failed"} or incomplete is not None or resp_error is not None:
        raise QuoteCheckError(
            FailureCategory.PROVIDER_INCOMPLETE_RESPONSE,
            response_status=status,
            incomplete_reason=incomplete_reason,
            detail="provider returned an incomplete response",
        )

    # 3) Empty structured content.
    text = (getattr(resp, "output_text", "") or "").strip()
    if not text:
        raise QuoteCheckError(
            FailureCategory.INVALID_MODEL_OUTPUT,
            response_status=status,
            detail="empty structured output",
        )

    # 4) Must be a JSON object.
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QuoteCheckError(
            FailureCategory.INVALID_MODEL_OUTPUT,
            cause=exc,
            detail="structured output was not valid JSON",
        )
    if not isinstance(payload, dict):
        raise QuoteCheckError(
            FailureCategory.INVALID_MODEL_OUTPUT,
            detail="structured output was not a JSON object",
        )
    return payload


def analyze_quote_openai(
    *, quote_text: str, request_id: str
) -> Tuple[QuoteCheckResult, int, int]:
    """Run the OpenAI Responses path.

    Returns ``(result, latency_ms, provider_attempts)``. Raises ``QuoteCheckError``
    (and only ``QuoteCheckError``) on any failure.
    """
    timeout_seconds = resolve_openai_timeout_seconds()

    if not OPENAI_API_KEY:
        raise QuoteCheckError(
            FailureCategory.CONFIGURATION_ERROR,
            request_id=request_id,
            detail="OPENAI_API_KEY is not set",
        )

    # QuoteCheck owns retries: the SDK client makes exactly one HTTP attempt.
    client = OpenAI(api_key=OPENAI_API_KEY, timeout=timeout_seconds, max_retries=0)

    schema_obj = quotecheck_result_schema_obj()
    messages = build_messages(quote_text=quote_text)
    text_format = {
        "format": {
            "type": "json_schema",
            "name": "QuoteCheckResult",
            "strict": True,
            "schema": schema_obj,
        }
    }

    # -- bounded, no-backoff retry loop (QC-4) -------------------------------- #
    provider_attempts = 0
    resp = None
    t0 = time.perf_counter()
    while provider_attempts < OPENAI_MAX_ATTEMPTS:
        provider_attempts += 1
        try:
            resp = client.responses.create(model=MODEL, input=messages, text=text_format)
            break
        except QuoteCheckError:
            raise
        except Exception as exc:  # noqa: BLE001 - re-raised as a classified error
            can_retry = (
                is_transient_openai_exception(exc)
                and provider_attempts < OPENAI_MAX_ATTEMPTS
            )
            if can_retry:
                continue
            raise QuoteCheckError(
                classify_openai_exception(exc),
                request_id=request_id,
                cause=exc,
                provider_status=getattr(exc, "status_code", None),
                provider_request_id=getattr(exc, "request_id", None),
                provider_attempts=provider_attempts,
            )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # -- explicit response-state handling ----------------------------------- #
    try:
        payload = _extract_structured_payload(resp)
    except QuoteCheckError as err:
        err.request_id = err.request_id or request_id
        err.provider_attempts = provider_attempts
        raise

    # -- server-truth metadata (validity is derived, never asserted away) --- #
    payload["metadata"] = {
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "created_at": datetime.now(timezone.utc),
        "request_id": request_id,
        "latency_ms": latency_ms,
        "schema_valid": True,
    }

    # -- mandatory final Pydantic validation; no repair loop --------------- #
    try:
        result = QuoteCheckResult.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - pydantic.ValidationError and friends
        raise QuoteCheckError(
            FailureCategory.INVALID_MODEL_OUTPUT,
            request_id=request_id,
            cause=exc,
            provider_attempts=provider_attempts,
            detail="model output failed QuoteCheckResult validation",
        )

    return result, latency_ms, provider_attempts
