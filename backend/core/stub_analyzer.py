"""
Stub Analyzer (v0)

Provides a deterministic, zero-cost analyzer used when QUOTECHECK_USE_OPENAI=0.

Why keep a stub?
- Lets the UI/demo, local development, and eval runs work with no API key and no
  OpenAI spend
- Acts as a baseline for future eval comparisons

The analyzer is selected once by configuration (QUOTECHECK_USE_OPENAI). This is
not an automatic fallback: an OpenAI-mode failure returns an error to the caller,
it does not silently switch to this stub.

This module returns a fully schema-valid QuoteCheckResult.

Keyword design (QC-3C)
----------------------
Four small, single-purpose keyword lists drive the deterministic behaviour. Each
one targets exactly one field and nothing else:

- AC_APPLIANCE_TERMS / HOME_MAINTENANCE_TERMS / "brake|tyre|tire"
  -> which coarse domain line item(s) to emit.
- GENERIC_CHARGE_TERMS
  -> whether a *line item* is `vague_or_confusing` (a genuinely vague charge label).
- DEFERRED_DETAIL_TERMS
  -> whether the *quote* has `missing_quote_context` (the quote's own words say
     material detail is omitted, deferred, provisional, or externalised).
- SAFETY_RISK_TERMS
  -> whether `needs_professional_confirmation` is set (a named safety-critical
     component or hazard is present).

`ambiguous_items_present` is derived, never asserted directly:
    ambiguous_items_present = any(item.vague_or_confusing for item in line_items)

Quote-level context gaps and line-level vagueness are kept separate: a deferred
quote-context phrase never marks a line item vague, and a vague charge label never
sets `missing_quote_context` on its own.
"""

from __future__ import annotations

import re
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

# Charge/line-level only. Purpose: recognise a genuinely vague charge *label*.
# These set a line item's `vague_or_confusing`; they never touch
# `missing_quote_context`. Bare "labour"/"labor" are deliberately NOT here -- they
# match every ordinary itemised labour line. Entries are charge-like phrases, not
# bare English words. Matched whole-word / whole-phrase (see `_matches_any`).
GENERIC_CHARGE_TERMS = [
    "misc",
    "miscellaneous",
    "service charge",
    "service handling",
    "handling charge",
    "shop supplies",
    "sundries",
    "site charge",
    "site charges",
    "materials as required",
    "materials extra",
    "labour adjustment",
    "labor adjustment",
    "labour extra",
    "lump sum",
    "consumables",
    "other charges",
    "unitemized charges",
    "gas top-up",
]

# Quote-level only. Purpose: the quote's own wording says material context is
# omitted, deferred, provisional, or externalised to a conversation/attachment.
# These set `missing_quote_context` and nothing else. Matched whole-word /
# whole-phrase, case-insensitive. "not included" was removed in QC-3C -- it
# matched benign "Not included, chargeable separately ..." exclusions lists.
DEFERRED_DETAIL_TERMS = [
    "no specific",
    "no measurements",
    "no parts",
    "follow-up estimate",
    "to be determined",
    "tbd",
    "approximate total",
    "as agreed",
    "as discussed",
    "discussed during",
    "attached estimate",
    "see attached",
    "depending on additional work",
    "additional work found",
    "consolidated figure",
    "consolidated figures",
    "diagnostic report available",
    "provisional",
    "subject to inspection",
    "site inspection",
    "to be assessed",
    "to be confirmed",
    "will be advised",
    "will be assessed",
    "will be revised",
    "estimate may vary",
    "indicative total",
    "indicative cost",
    "firm quote",
    "firm estimate",
    "as per work",
    "at actual",
    "at actuals",
]

# Named safety-critical components / hazards -- never a trade or domain name.
# Presence of one in the quote sets `needs_professional_confirmation`. Matched
# whole-word / whole-phrase (not naive substring); inflected forms are listed
# explicitly rather than relying on partial matches. Broad words such as
# "suspension", "automotive", "contractor" are deliberately excluded.
SAFETY_RISK_TERMS = [
    # structural / load-bearing
    "load bearing",
    "load-bearing",
    "structural",
    "lintel",
    "rsj",
    # mains-electrical safety components
    "consumer unit",
    "earth bonding",
    "earthing",
    "rcbo",
    "rcbos",
    "rcd",
    "residual current device",
    "distribution board",
    # sealed-refrigerant work
    "brazing",
    "system evacuation",
    "sealed system",
    "refrigerant recharge",
    "gas charging",
    "compressor replacement",
    # safety-critical mechanical components
    "brake",
    "brakes",
    "control arm",
    "control arms",
    "ball joint",
    "ball joints",
    "steering",
    "tie rod",
    "tie rods",
]

# Tiny set of on-line "this figure is not firm" tokens, used only alongside a
# monetary amount on the *same* source line to flag that priced line as vague.
APPROX_LINE_TOKENS = [
    "approx",
    "tbd",
    "to be confirmed",
    "range",
    "may vary",
    "may need",
]

_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d+)?|\b\d[\d,]{2,}\s*/-",
    re.IGNORECASE,
)
_SKIP_LINE_RE = re.compile(
    r"\b(total|subtotal|sub-total|grand total|tax|gst|vat)\b",
    re.IGNORECASE,
)
_MAX_EXTRACTED_ITEMS = 5


def _term_pattern(term: str) -> re.Pattern[str]:
    """Whole-word / whole-phrase, case-insensitive; internal spaces match any run
    of whitespace. `foo` does not match `foobar`; `a b` does not match `a bc`."""
    body = r"\s+".join(re.escape(part) for part in term.split())
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


_COMPILED: dict[str, re.Pattern[str]] = {}


def _matches_any(text: str, terms: list[str]) -> bool:
    for term in terms:
        pat = _COMPILED.get(term)
        if pat is None:
            pat = _COMPILED[term] = _term_pattern(term)
        if pat.search(text):
            return True
    return False


def _line_has_amount(line: str) -> bool:
    return bool(_AMOUNT_RE.search(line))


def _is_itemised_line(line: str) -> bool:
    """A line that reads like a priced quote line: a label plus a monetary amount,
    not a total/tax/subtotal line."""
    if _SKIP_LINE_RE.search(line):
        return False
    if not _line_has_amount(line):
        return False
    alpha = sum(ch.isalpha() for ch in line)
    return alpha >= 3


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
            "Can you itemize exactly what the misc/service/handling charge covers?",
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


def _generic_charge_item() -> LineItem:
    return LineItem(
        name_raw="Other/unspecified charges (from quote)",
        normalized_category=NormalizedCategory.unknown_needs_clarification,
        explanation=(
            "The quote mentions one or more generically named or un-itemized "
            "charges (e.g. misc, service charge, handling, shop supplies, "
            "sundries). This stub cannot know what they specifically cover "
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


def _no_detail_fallback_item() -> LineItem:
    return LineItem(
        name_raw="Unclear item(s) - needs clarification",
        normalized_category=NormalizedCategory.unknown_needs_clarification,
        explanation=(
            "The quote text lacks enough detail (e.g. part names, measurements, "
            "priced line items) for this stub to explain what the charge covers "
            "or why it might be recommended."
        ),
        vague_or_confusing=True,
        recommended_action=RecommendedAction.unknown,
        risk_level=RiskLevel.yellow,
        confidence=0.35,
        rationale_short="The quote text lacks enough detail to classify items reliably. Ask the vendor for an itemized breakdown.",
        price=None,
        evidence_needed=[
            "Itemized parts + labor list",
            "Reason for each recommendation",
        ],
    )


def _extracted_line_item(line: str, *, vague: bool) -> LineItem:
    name = line.strip()
    if len(name) > 120:
        name = name[:117].rstrip() + "..."
    return LineItem(
        name_raw=name or "Quote line (from quote)",
        normalized_category=NormalizedCategory.unknown_needs_clarification,
        explanation=(
            "This is a priced line taken from the quote as written. The Demo "
            "analyzer does not recognise the domain, so it cannot classify what "
            "the line covers or why it is recommended - the figure and label are "
            "reproduced from the quote for you to check with the vendor."
        ),
        vague_or_confusing=vague,
        recommended_action=RecommendedAction.consider,
        risk_level=RiskLevel.yellow,
        confidence=0.40,
        rationale_short=(
            "Charge label is generic or the figure is not firm; ask the vendor what it covers."
            if vague
            else "Line is itemised with an amount but not classified; confirm what it covers and why."
        ),
        price=None,
        evidence_needed=["Confirm what this line covers and why it is recommended"],
    )


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
    items: list[LineItem] = []

    vehicle_matched = "brake" in text_lower or "tyre" in text_lower or "tire" in text_lower
    ac_matched = any(term in text_lower for term in AC_APPLIANCE_TERMS)
    home_matched = any(term in text_lower for term in HOME_MAINTENANCE_TERMS)
    generic_charge_matched = _matches_any(text_lower, GENERIC_CHARGE_TERMS)
    domain_matched = vehicle_matched or ac_matched or home_matched

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
        items.append(_generic_charge_item())

    # Line-level scan. Never sets a quote-wide flag; only adds line items and
    # decides their own `vague_or_confusing`.
    lines = quote_text.splitlines()
    if not domain_matched and not generic_charge_matched:
        # Unrecognised domain: emit one item per priced line instead of a single
        # vague "needs clarification" fallback, when the quote actually has >= 2
        # priced lines.
        itemised = [ln for ln in lines if _is_itemised_line(ln)]
        if len(itemised) >= 2:
            for ln in itemised[:_MAX_EXTRACTED_ITEMS]:
                low = ln.lower()
                vague = _matches_any(low, GENERIC_CHARGE_TERMS) or (
                    _line_has_amount(ln) and _matches_any(low, APPROX_LINE_TOKENS)
                )
                items.append(_extracted_line_item(ln, vague=vague))
    else:
        # A domain/generic item already exists: still flag any individual priced
        # line whose own text says the figure is not firm.
        for ln in lines:
            if _SKIP_LINE_RE.search(ln):
                continue
            if _line_has_amount(ln) and _matches_any(ln.lower(), APPROX_LINE_TOKENS):
                items.append(_extracted_line_item(ln, vague=True))

    if not items:
        items.append(_no_detail_fallback_item())

    overall_summary = [
        "This report explains each line item in plain language, flags risk level, and lists questions to ask the vendor before approving.",
        "Any generically named, bundled, or unclear charges are marked as needing clarification; ask the vendor for an itemized breakdown.",
        "Price benchmarking is not implemented; no market price comparison is being made.",
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

    # --- Uncertainty markers -------------------------------------------------
    # ambiguous_items_present: a pure summary of the line-item analysis. Nothing
    # else sets it; it never disagrees with the items.
    ambiguous_items_present = any(li.vague_or_confusing for li in items)

    # missing_quote_context: quote-level only. True when the quote's own wording
    # defers/omits/externalises material detail (DEFERRED_DETAIL_TERMS), or when
    # the analysis resolved to nothing but unclear charges. Not set merely
    # because a domain was unrecognised, and not a mirror of the vague-charge
    # flag on a single line.
    deferred_detail_matched = _matches_any(text_lower, DEFERRED_DETAIL_TERMS)
    only_unclear_items = bool(items) and all(li.vague_or_confusing for li in items)
    missing_quote_context = deferred_detail_matched or only_unclear_items

    # needs_professional_confirmation: domain-neutral. True when a line item is
    # red risk or safety_critical, or the quote names a safety-critical component
    # or hazard (SAFETY_RISK_TERMS, whole-word). Never triggered by trade/domain
    # identity alone.
    needs_professional_confirmation = any(
        li.risk_level == RiskLevel.red
        or li.normalized_category == NormalizedCategory.safety_critical
        for li in items
    ) or _matches_any(text_lower, SAFETY_RISK_TERMS)

    return QuoteCheckResult(
        line_items=items,
        overall_summary=overall_summary,
        verification_questions=verification_questions,
        things_to_verify=things_to_verify,
        uncertainty_markers=UncertaintyMarkers(
            ambiguous_items_present=ambiguous_items_present,
            missing_quote_context=missing_quote_context,
            needs_professional_confirmation=needs_professional_confirmation,
        ),
        refusals=[],
        disclaimer=(
            "QuoteCheck results may be incomplete or wrong. This analysis is "
            "informational and should not replace professional advice, official "
            "estimates, warranty terms, or a second opinion for high-value or "
            f"safety-critical work — verify with a {professional}. QuoteCheck "
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
