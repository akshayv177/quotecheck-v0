"""
QuoteCheck reliability error model (QC-4).

One small, typed representation for a bounded set of failure categories so the
FastAPI route can present failures predictably and the JSONL run log can record
*why* a run failed without leaking raw provider diagnostics.

No framework, no exception hierarchy: one Enum + one spec table + one exception
class + a few helpers.

Two concepts are kept deliberately distinct:

- ``retryable`` (on the error / in the API body / in the log) means
  "a manual user retry may reasonably succeed".
- whether QuoteCheck *automatically* retried is a separate decision made by the
  analyzer's bounded retry loop (see ``is_transient_openai_exception`` and
  ``backend/core/openai_analyzer.py``). Only ``provider_timeout`` and
  ``provider_unavailable`` are ever retried automatically, and at most once.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class FailureCategory(str, Enum):
    """The complete set of ways an /analyze call can fail in QC-4."""

    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_REFUSAL = "provider_refusal"
    PROVIDER_INCOMPLETE_RESPONSE = "provider_incomplete_response"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class _CategorySpec:
    http_status: int
    retryable: bool  # == "a manual user retry may reasonably succeed"
    user_message: str


# Single source of truth for the failure-mapping table in the QC-4 review bundle.
_SPECS: Dict[FailureCategory, _CategorySpec] = {
    FailureCategory.PROVIDER_TIMEOUT: _CategorySpec(
        504,
        True,
        "The analysis service took too long to respond. Please try again.",
    ),
    FailureCategory.PROVIDER_UNAVAILABLE: _CategorySpec(
        503,
        True,
        "The analysis service is temporarily unavailable. Please try again shortly.",
    ),
    FailureCategory.PROVIDER_RATE_LIMITED: _CategorySpec(
        429,
        True,
        "The analysis service is busy right now. Please wait a moment and try again.",
    ),
    FailureCategory.PROVIDER_REFUSAL: _CategorySpec(
        502,
        False,
        "The analysis service could not complete this request.",
    ),
    FailureCategory.PROVIDER_INCOMPLETE_RESPONSE: _CategorySpec(
        502,
        True,
        "The analysis could not be completed reliably. Please try again.",
    ),
    FailureCategory.INVALID_MODEL_OUTPUT: _CategorySpec(
        502,
        False,
        "The analysis could not be completed reliably. Please try again.",
    ),
    FailureCategory.CONFIGURATION_ERROR: _CategorySpec(
        503,
        False,
        "AI analysis is temporarily unavailable.",
    ),
    FailureCategory.INTERNAL_ERROR: _CategorySpec(
        500,
        False,
        "Something went wrong while analyzing this quote. Please try again.",
    ),
}


class QuoteCheckError(Exception):
    """A classified, user-safe analysis failure.

    ``cause`` retains the original exception object for tests and debugging but
    is **never serialized**. Only ``cause_type`` (the class name) reaches the
    log. ``detail`` is a short, application-authored phrase supplied at the
    raise site — never ``str(cause)``, a traceback, a request body, or a
    provider payload.
    """

    def __init__(
        self,
        category: FailureCategory,
        *,
        request_id: Optional[str] = None,
        cause: Optional[BaseException] = None,
        detail: Optional[str] = None,
        provider_status: Optional[int] = None,
        provider_request_id: Optional[str] = None,
        response_status: Optional[str] = None,
        incomplete_reason: Optional[str] = None,
        provider_attempts: Optional[int] = None,
    ) -> None:
        spec = _SPECS[category]
        super().__init__(category.value if not detail else f"{category.value}: {detail}")
        self.category = category
        self.http_status = spec.http_status
        self.retryable = spec.retryable
        self.user_message = spec.user_message
        self.request_id = request_id
        self.cause = cause
        self.cause_type = type(cause).__name__ if cause is not None else None
        self.detail = detail
        self.provider_status = provider_status
        self.provider_request_id = provider_request_id
        self.response_status = response_status
        self.incomplete_reason = incomplete_reason
        self.provider_attempts = provider_attempts

    def log_error_field(self) -> str:
        """Bounded, application-authored value for the JSONL ``error`` field.

        Deliberately excludes ``str(cause)``, tracebacks, and provider payloads.
        """
        if self.detail:
            return f"{self.category.value}: {self.detail}"
        if self.cause_type:
            return f"{self.category.value} ({self.cause_type})"
        return self.category.value


def error_response_body(err: QuoteCheckError) -> Dict[str, Any]:
    """The entire response payload for a failed /analyze call. Nothing else.

    No stack trace, no API key, no provider payload, no internal filenames, no
    raw exception text.
    """
    return {
        "detail": {
            "code": err.category.value,
            "message": err.user_message,
            "retryable": err.retryable,
            "request_id": err.request_id,
        }
    }


def classify_openai_exception(exc: BaseException) -> FailureCategory:
    """Map a raw OpenAI SDK exception to a QuoteCheck failure category.

    Provider/transport, model-output, and configuration failures are kept
    conceptually separate. Anything unrecognised is ``internal_error``.
    """
    from openai import (
        APIConnectionError,
        APIResponseValidationError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        InternalServerError,
        NotFoundError,
        PermissionDeniedError,
        RateLimitError,
    )

    # Order matters: subclasses before their bases.
    if isinstance(exc, APITimeoutError):
        return FailureCategory.PROVIDER_TIMEOUT
    if isinstance(exc, APIConnectionError):
        return FailureCategory.PROVIDER_UNAVAILABLE
    if isinstance(exc, RateLimitError):
        return FailureCategory.PROVIDER_RATE_LIMITED
    if isinstance(exc, InternalServerError):
        return FailureCategory.PROVIDER_UNAVAILABLE
    if isinstance(exc, (AuthenticationError, PermissionDeniedError, NotFoundError, BadRequestError)):
        # These indicate our key/config/request is wrong, not a model failure.
        return FailureCategory.CONFIGURATION_ERROR
    if isinstance(exc, APIResponseValidationError):
        return FailureCategory.INVALID_MODEL_OUTPUT
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        if status is not None and status >= 500:
            return FailureCategory.PROVIDER_UNAVAILABLE
        if status == 429:
            return FailureCategory.PROVIDER_RATE_LIMITED
        return FailureCategory.CONFIGURATION_ERROR
    return FailureCategory.INTERNAL_ERROR


def is_transient_openai_exception(exc: BaseException) -> bool:
    """True only for provider/transport failures QC-4 will automatically retry.

    Explicitly excludes rate limiting (429): a retry there amplifies load and
    does not reliably help. 429 is surfaced as user-retryable instead.
    """
    from openai import APIConnectionError, APIStatusError, InternalServerError, RateLimitError

    if isinstance(exc, RateLimitError):
        return False
    if isinstance(exc, APIConnectionError):  # includes APITimeoutError
        return True
    if isinstance(exc, InternalServerError):
        return True
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        return status is not None and status >= 500
    return False
