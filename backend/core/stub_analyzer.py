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

from backend.core.config import DEMO_ANALYZER_MODEL
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
                explanation=(
                    "Brake pads are the friction material that presses on the rotor "
                    "to slow the vehicle. A shop typically recommends replacement "
                    "when pad thickness drops below a safe threshold or the rotor "
                    "shows wear."
                ),
                vague_or_confusing=False,
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
                explanation=(
                    "Tyres are the vehicle's only contact with the road, so tread "
                    "depth and condition affect braking, handling, and grip. A shop "
                    "recommends replacement or rotation to keep wear even and "
                    "maintain safe tread depth."
                ),
                vague_or_confusing=False,
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

    generic_charge_terms = [
        "misc",
        "miscellaneous",
        "labour",
        "labor",
        "service charge",
        "gas top-up",
        "consumables",
        "other charges",
        "unitemized charges",
    ]
    if any(term in text_lower for term in generic_charge_terms):
        items.append(
            LineItem(
                name_raw="Other/unspecified charges (from quote)",
                normalized_category=NormalizedCategory.unknown_needs_clarification,
                explanation=(
                    "The quote mentions one or more generically named or "
                    "un-itemized charges (e.g. misc, labour, service charge, gas "
                    "top-up). This stub cannot know what they specifically cover "
                    "without an itemized breakdown from the vendor."
                ),
                vague_or_confusing=True,
                recommended_action=RecommendedAction.ask_for_evidence,
                risk_level=RiskLevel.yellow,
                confidence=0.40,
                rationale_short="Generic or bundled charges are unclear without an itemized breakdown; ask the vendor to itemize them.",
                price=None,
                evidence_needed=[
                    "Itemized breakdown of what this charge covers",
                    "Confirm whether this is a fixed fee or time-based labour charge",
                ],
            )
        )

    if not items:
        items.append(
            LineItem(
                name_raw="Unclear item(s) - needs clarification",
                normalized_category=NormalizedCategory.unknown_needs_clarification,
                explanation=(
                    "The quote text lacks enough detail (e.g. part names, "
                    "measurements) for this stub to explain what the charge covers "
                    "or why it might be recommended."
                ),
                vague_or_confusing=True,
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
            "This report explains each line item in plain language, flags risk level, and lists questions to ask the vendor before approving.",
            "Safety-critical items (like brakes/tyres) should be verified with evidence before approval.",
            "Any generically named or bundled charges are marked as needing clarification; ask the vendor for an itemized breakdown.",
            "Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made.",
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
        disclaimer=(
            "QuoteCheck is a v0 prototype; results may be incomplete or wrong. "
            "Not safety advice; verify with a certified mechanic. QuoteCheck "
            "explains quotes and suggests questions; it does not verify vendor "
            "claims, guarantee fair pricing, or perform price benchmarking."
        ),
        metadata=MetaData(
            prompt_version=PROMPT_VERSION,
            model=DEMO_ANALYZER_MODEL,
            created_at=datetime.now(timezone.utc),
            request_id=request_id,
            latency_ms=latency_ms,
            schema_valid=True,
        ),
    )