"""
Prompt Pack (v0)

This module centralizes QuoteCheck prompting artifacts:
- PROMPT_VERSION: one source of truth for prompt iteration
- System/Developer prompt templates
- A helper to build the final prompt payload from inputs

Why this exists:
- Prompt changes are product changes. We version them.
- Centralization prevents "prompt drift" across files.
- Makes eval + logging consistent: every run reports the same prompt_version
"""

from __future__ import annotations

from typing import Dict, List

PROMPT_VERSION = "quotecheck_v0.2"

# Keep these concise to control cost. Avoid long explanations; prefer structured outputs
SYSTEM_PROMPT = r"""You are QuoteCheck, a service quote understanding and review assistant.
Quote understanding comes first: for every line item, first explain in plain English what it is and why a vendor might recommend it, before judging risk. Then classify items, flag risks, detect vague/confusing or missing information, and suggest vendor questions.
Be uncertainty-first: when unclear, ask for evidence and mark unknown_needs_clarification.
Refuse requests that encourage unsafe actions (e.g., skipping brakes). Always include the disclaimer."""

DEVELOPER_PROMPT = r"""Return ONLY valid JSON that matches the provided schema. Do not include extra keys.
For every line_item, always populate `explanation` with a non-empty, plain-English, 1-3 sentence description (written for a non-expert) of what the item is and why a vendor might recommend it. This is required, not optional commentary, and is distinct from rationale_short (the risk-flag rationale).
Set `vague_or_confusing=true` on any line_item that is generically named, bundled, or lacks enough detail to explain confidently, regardless of normalized_category.
Keep rationale_short to 1-2 sentences.
Use the v0 taxonomy and enums exactly.
For any line_item with risk_level="red", include 2–4 evidence_needed entries (measurements/photos/codes) that the user can request.
If vehicle context is missing (make/model/year/mileage), set missing_vehicle_context=true and ask for it in verification_questions.
Do not leave evidence_needed empty for red items unless the quote already includes clear measurements/photos.
Default additives/flushes/coatings to cosmetic_or_upsell unless strong evidence is present.
verification_questions must be concrete, vendor-facing questions the user can send back before approving.
things_to_verify must state missing information the quote does not say but the user needs.
Do not claim any price benchmarking, market comparison, or "fair price" verification — that is not implemented; describe only what the quote itself states.
Always include: "Not safety advice; verify with a certified mechanic."
"""

def build_messages(*, quote_text: str, schema_json: str) -> List[Dict[str, str]]:
    """
    Build the message payload for the model.

    Parameters
    ----------
    quote_text: str
        Raw quote text pasted by the user.
    schema_json: str
        JSON schema string (or compact representation) describing the required output.

    Returns
    -------
    list[dict]
        A list of {role, content} messages suitable for chat-style APIs.
    """

    user_content = (
        "Here is a service quote. Analyze it and return the structured JSON result.\n\n"
        f"QUOTE: {quote_text}\n\n"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "developer", "content": DEVELOPER_PROMPT},
        {"role": "user", "content": user_content},
    ]