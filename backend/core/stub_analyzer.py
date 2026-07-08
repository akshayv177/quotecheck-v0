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

AC_APPLIANCE_TERMS = [
    "air conditioning",
    "air conditioner",
    "compressor",
    "refrigerant",
    "hvac",
    "appliance",
]

HOME_MAINTENANCE_TERMS = [
    "plumbing",
    "electrical",
    "contractor",
    "handyman",
    "renovation",
]

GENERIC_CHARGE_TERMS = [
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


def _verifying_professional(*, vehicle_matched: bool, ac_matched: bool, home_matched: bool) -> str:
    """Pick domain-appropriate wording for who the user should verify with."""
    if vehicle_matched:
        return "certified mechanic"
    if ac_matched:
        return "certified technician"
    if home_matched:
        return "licensed contractor"
    return "qualified professional"


def _domain_questions_and_verification(
    *, vehicle_matched: bool, ac_matched: bool, home_matched: bool, generic_charge_matched: bool
) -> tuple[list[str], list[str]]:
    """
    Build domain-aware `verification_questions` (vendor-facing questions) and
    `things_to_verify` (user-facing checklist) from which quote-type keyword blocks
    matched. Deterministic: no LLM/web calls, just static text keyed off the same
    booleans used to build line items above. Domains combine (e.g. a vehicle quote
    that also has a generic bundled charge gets both chunks); when nothing
    domain-specific matched, both lists fall back to plain clarifying questions
    rather than pretending to know quote-specific details.
    """
    questions: list[str] = []
    verify: list[str] = []

    if vehicle_matched:
        questions += [
            "Can you share photos or measurements (pad thickness, tread depth) that support the brake/tyre recommendation?",
            "Is this brake/tyre work needed immediately, or can it wait until after a second opinion?",
            "Are the replacement parts OEM or aftermarket, and what warranty do they carry?",
        ]
        verify += [
            "Confirm current pad thickness and tread depth measurements before approving replacement.",
            "Check whether the vehicle is still under a manufacturer or extended warranty that could cover this work.",
            "Get a second opinion from an independent mechanic for safety-critical work before approving.",
        ]

    if ac_matched:
        questions += [
            "What diagnostic fault code or symptom led to the compressor/refrigerant recommendation?",
            "Is the unit still under manufacturer or extended warranty?",
            "What refrigerant type and quantity does the job require, and is that reflected in the price?",
        ]
        verify += [
            "Get the unit's model/serial number and confirm its warranty status before approving.",
            "Confirm a refrigerant leak was actually located, not just assumed from low pressure.",
            "Ask whether a full system replacement was considered instead of a compressor repair, and why.",
        ]

    if home_matched:
        questions += [
            "Can you provide a written scope of work broken down by task (plumbing, electrical, etc.)?",
            "What is the estimated labor-hours and materials cost for each task?",
            "Are permits required for any of this work, and who is responsible for obtaining them?",
        ]
        verify += [
            "Request an itemized scope-of-work document before work begins.",
            "Confirm whether permits are required for any electrical or plumbing work.",
            "Check the contractor's license and insurance before approving work on your property.",
        ]

    if generic_charge_matched:
        questions += [
            "Can you itemize exactly what the misc/labour/service charge covers?",
            "Is this a fixed fee or a time-based labour charge, and what's the hourly rate if applicable?",
            "Does this charge overlap with cost already included in another line item on the quote?",
        ]
        verify += [
            "Request a line-by-line breakdown of any bundled or generically named charges.",
            "Confirm this charge isn't duplicating cost already included in another line item.",
            "Ask whether this charge is negotiable or waivable if you decline related work.",
        ]

    if not questions:
        questions = [
            "Can you resend the quote with itemized parts, labour, and a reason for each recommendation?",
            "What specific work is being proposed, and what problem is it meant to fix?",
            "Is this work urgent, or can it wait until you get a second quote?",
        ]
        verify = [
            "Ask for a fully itemized breakdown before evaluating this quote further.",
            "Confirm what underlying problem or symptom prompted this quote.",
            "Get the vendor's contact info and a written copy of the quote for your records.",
        ]

    return questions, verify


def analyze_quote_stub(*, quote_text: str, request_id: str, latency_ms: int) -> QuoteCheckResult:
    """
    Analyze a quote using simple keyword heuristics and return a schema-valid
    QuoteCheckResult.

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

    vehicle_matched = "brake" in text_lower or "tyre" in text_lower or "tire" in text_lower
    ac_matched = any(term in text_lower for term in AC_APPLIANCE_TERMS)
    home_matched = any(term in text_lower for term in HOME_MAINTENANCE_TERMS)
    generic_charge_matched = any(term in text_lower for term in GENERIC_CHARGE_TERMS)

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

    if ac_matched:
        items.append(
            LineItem(
                name_raw="AC/appliance repair (from quote)",
                normalized_category=NormalizedCategory.wear_and_tear,
                explanation=(
                    "An AC compressor or refrigerant charge is part of an appliance's "
                    "cooling system. A technician typically recommends this when "
                    "cooling output drops, the system is losing refrigerant, or a "
                    "diagnostic points to a failing component."
                ),
                vague_or_confusing=False,
                recommended_action=RecommendedAction.ask_for_evidence,
                risk_level=RiskLevel.yellow,
                confidence=0.55,
                rationale_short="Appliance/HVAC repair scope varies widely; ask for a diagnostic report before approving.",
                price=None,
                evidence_needed=[
                    "Diagnostic report or fault code",
                    "Unit model/serial number and warranty status",
                    "Refrigerant type and quantity used (if applicable)",
                ],
            )
        )

    if home_matched:
        items.append(
            LineItem(
                name_raw="Home maintenance/contractor work (from quote)",
                normalized_category=NormalizedCategory.preventive_maintenance,
                explanation=(
                    "General home maintenance or contractor work (e.g. plumbing, "
                    "electrical, or handyman tasks) covers a wide range of possible "
                    "scope. A contractor typically recommends it based on a site "
                    "visit or inspection rather than a fixed catalog part."
                ),
                vague_or_confusing=False,
                recommended_action=RecommendedAction.consider,
                risk_level=RiskLevel.green,
                confidence=0.50,
                rationale_short="Home maintenance scope varies by property; ask for a written scope of work before approving.",
                price=None,
                evidence_needed=[
                    "Scope-of-work breakdown by task",
                    "Materials list with quantities",
                    "Labor hours estimate",
                ],
            )
        )

    if generic_charge_matched:
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

    overall_summary = [
        "This report explains each line item in plain language, flags risk level, and lists questions to ask the vendor before approving.",
        "Any generically named, bundled, or unclear charges are marked as needing clarification; ask the vendor for an itemized breakdown.",
        "Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made.",
    ]
    if vehicle_matched:
        overall_summary.insert(
            1,
            "Safety-critical items (like brakes/tyres) should be verified with evidence before approval.",
        )

    professional = _verifying_professional(
        vehicle_matched=vehicle_matched, ac_matched=ac_matched, home_matched=home_matched
    )
    verification_questions, things_to_verify = _domain_questions_and_verification(
        vehicle_matched=vehicle_matched,
        ac_matched=ac_matched,
        home_matched=home_matched,
        generic_charge_matched=generic_charge_matched,
    )

    return QuoteCheckResult(
        line_items=items,
        overall_summary=overall_summary,
        verification_questions=verification_questions,
        things_to_verify=things_to_verify,
        uncertainty_markers=UncertaintyMarkers(
            ambiguous_items_present=True,
            missing_vehicle_context=True,
            needs_mechanic_confirmation=True,
        ),
        refusals=[],
        disclaimer=(
            "QuoteCheck is a v0 prototype; results may be incomplete or wrong. "
            f"Not safety advice; verify with a {professional}. QuoteCheck "
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
