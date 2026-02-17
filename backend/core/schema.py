"""
QuoteCheck Schema (v0)

This module defines the schema-first "contract" for QuoteCheck outputs using
Pydantic models. The purpose is to make LLM outputs machine-reliable for:

- UI rendering (frontend can safely access expected fields)
- Evaluation (we can compute schema-valid pass rate automatically)
- Observability (logs can store consistent structured data)

In Block 2, we define:
- Request model: AnalyzeRequest
- Response model: QuoteCheckResult and its nested types

In later blocks:
- We'll validate model outputs against these models (Pydantic validation)
- We'll export JSON Schema from these models for documentation and guardrails
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class NormalizedCategory(str, Enum):
    """
    Controlled taxonomy for quote line items.

    This is intentionally small in v0 so behaviour is stable and explainable.
    """
    safety_critical = "safety_critical"
    preventive_maintenance = "preventive_maintenance"
    wear_and_tear = "wear_and_tear"
    cosmetic_or_upsell = "cosmetic_or_upsell"
    unknown_needs_clarification = "unknown_needs_clarification"


class RecommendedAction(str, Enum):
    """
    Suggested user action for a line item, based on risk + ambiguity.

    Note: This is not mechanical advice; it's a structured recommendation for
    what to do next (approve/ask/defer/inspect).
    """
    approve = "approve"
    consider = "consider"
    defer = "defer"
    ask_for_evidence = "ask_for_evidence"
    needs_inspection = "needs_inspection"
    unknown = "unknown"


class RiskLevel(str, Enum):
    """
    Risk flag for the next item.

    - green: low urgency / low risk
    - yellow: moderate / needs verification
    - red: potentially safety-critical / do not ignore
    """
    green = "green"
    yellow = "yellow"
    red = "red"


class Price(BaseModel):
    """Optional price information for line item."""
    amount: float = Field(..., ge=0)
    currency: str = Field(..., min_length=1, description="Currency code or symbol (e.g., INR, USD, ₹)")


class LineItem(BaseModel):
    """
    A single extracted line item from the quote.

    name_raw: original text as present in the quote.
    normalized_category: v0 taxonomy category.
    recommended_action: what the user should do next.
    risk_level: green/yellow/red
    confidence: 0..1 subjective confidence in the classification
    rationale_short: short explanation (1-2 sentences)
    """
    name_raw: str = Field(..., min_length=1)
    normalized_category: NormalizedCategory
    recommended_action: RecommendedAction
    risk_level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale_short: str = Field(..., min_length=1)

    price: Optional[Price] = None
    evidence_needed: List[str] = Field(default_factory=list, description="What evidence to ask for (photos, measurements, codes).")


class UncertaintyMarkers(BaseModel):
    """
    High-level uncertainty flags to encourage verification-first behaviour.

    These markers are useful for:
    - product UX ("we need more info")
    - eval tests ("did the system admit uncertainty when it should?")
    - logging and monitoring
    """
    ambigious_items_present: bool
    missing_vehicle_context: bool
    needs_mechanic_confirmation: bool


class RefusalType(str, Enum):
    """Types of refusals for risky or innappropriate requests."""
    unsafe_instruction = "unsafe_instruction"
    illegal = "illegal"
    medical_like_advice = "medical_like_advice"
    other = "other"


class Refusal(BaseModel):
    """A structured refusal explanation."""
    type: RefusalType
    message: str = Field(..., min_length=1)


class MetaData(BaseModel):
    """
    Per-run metadata for traceability and observability.

    prompt_version: internal prompt/version string (e.g., quotecheck_v0.1)
    model: model identifier used for generation
    created_at: ISO timestamp
    request_id: UUID string created per request
    latency_ms: wall-clock latency measured by server
    schema_valid: whether the response validated against this schema
    """
    prompt_version: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    created_at: datetime
    request_id: str = Field(..., min_length=1)
    latency_ms: int = Field(..., ge=0)
    schema_valid: bool


class QuoteCheckResult(BaseModel):
    """
    Top-level response schema returned by POST / analyze (on success).

    Disclaimer is mandatory to avoid misinterpretation as professional advice.
    """
    line_items: List[LineItem] = Field(..., min_length=1)
    overall_summary: List[str] = Field(..., min_length=3, max_length=5)
    verification_questions: List[str] = Field(..., min_length=3, max_length=8)
    things_to_verify: List[str] = Field(..., min_length=3)

    uncertainty_markers: UncertaintyMarkers = Field(
        default_factory=lambda: UncertaintyMarkers(
            ambigious_items_present=True,
            missing_vehicle_context=True,
            needs_mechanic_confirmation=True,
        )
    )
    refusals: List[Refusal] = Field(default_factory=list)
    disclaimer: str = Field(..., min_length=1)

    metadata: MetaData


class AnalyzeRequest(BaseModel):
    """
    Request payload for POST / analyze.
    Accepts either 'quote_text' (preferred) or 'quoteText' (frontend-friendly)

    quote_text: the raw quote content pasted by the user.
    """
    quote_text: str = Field(..., min_length=1, alias="quoteText", description="Raw service quote text pasted by the user.")

    model_config = {"populate_by_name": True, "extra": "forbid"}