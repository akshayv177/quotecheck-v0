"""
Stub Analyzer (v0)

Provides a deterministic, zero-cost analyzer used when QUOTECHECK_USE_OPENAI=0.

Why keep a stub?
- Lets the UI/demo work without spending money
- Provides a deterministic fallback if OpenAI is unavailable
- Acts as a baseline for future eval comparisons

This module returns a fully schema-valid QuoteCheckResult.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.core.config import MODEL
from backend.core.prompt import PROMPT_VERSION
from backend.core.schema import (
    LineItem,
    MetaData,
    NormalizedCategory,
    Price,
    QuoteCheckResult,
    RecommendedAction,
    RiskLevel,
    UncertaintyMarkers,
)


def analyze_quote_stub(*, quote_text: str, request_id: str, latency_ms: int) -> QuoteCheckResult:
    """
    Analyze a quote using simple heuristics and return a schema-valid QuoteCheckResult.

    Parameters
    ----------
    quote_text : str
        Raw quote text pasted by the user.
    request_id : str
        Server-generated UUID for traceability.
    latency_ms : int
        Measured request latency from the caller (app.py). Included in metadata.

    Returns
    -------
    QuoteCheckResult
        Deterministic, schema-valid output.
    """
    text_lower = quote_text.lower()
    items = []

    if "brake" in text_lower:
        items.append(
            LineItem(
                name_raw="Brake service/ pads (from quote)",
                normalized_category=NormalizedCategory.safety_critical,
                recommended_action=RecommendedAction.needs_inspection,
                risk_level=RiskLevel.red,
                confidence=0.70,
                rationale_short="Braking components are safety-critical. Ask for pad thickness and rotor condition evidence.",
                price=None,
                evidence_needed=[
                    "Pad thickness measurement (mm)",
                    "Rotor condition photo",
                    "Reason for replacement",
                ],
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
                rationale_short="Tyres affect braking and handling. Ask for tread depth and sidewall condition details.",
                price=Price(amount=0.0, currency="INR"),
                evidence_needed=[
                    "Tread depth (mm)",
                    "Uneven wear explanation",
                    "Sidewall damage photo (if any)",
                ],
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
                price=None,
                evidence_needed=[
                    "Itemized parts + labor list",
                    "Reason for each recommendation",
                ],
            )
        )

    return QuoteCheckResult(
        line_items=items,
        overall_summary=[
            "This is a v0 stub response to validate the end-to-end contract.",
            "Safety-critical items (like brakes/tyres) should be verified with evidence before approval.",
            "Ask for measurements, photos, and the specific failure reason for any recommendation.",
        ],
        verification_questions=[
            "Can you share photos/measurements that justify each recommended item?",
            "Which items are safety-critical vs optional preventive maintenance?",
            "Confirm whether the recommendation is OEM-specified or shop-suggested.",
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
            model=MODEL,
            created_at=datetime.now(timezone.utc),
            request_id=request_id,
            latency_ms=latency_ms,
            schema_valid=True,
        ),
    )