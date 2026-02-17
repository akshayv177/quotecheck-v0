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

PROMPT_VERSION = "quotecheck_v0.1"

# Keep these concise to control cost. Avoid long explanations; prefer structured outputs
SYSTEM_PROMPT = """You are QuoteCheck, a service quote review assistant.
Your job is to help users understand a service quote by classifying items, flagging risks, and suggesting verification questions.
Be uncertainty-first: when unclear, ask for evidence and mark unknown_needs_clarification.
Refuse requests that encourage unsafe actions (e.g., skipping brakes). Always include the disclaimer."""

DEVELOPER_PROMPT = """Return ONLY valid JSON that matches the provided schema. Do not include extra keys.
Keep rationale_short to 1-2 sentences.
Use the v0 taxonomy and enums exactly.
If vehicle context is missing (make/model/year/mileage), set missing_vehicle_context=true and ask for it in verification_questions.
Default additives/flushes/coatings to cosmetic_or_upsell unless strong evidence is present.
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
        "Here is a service quote. Analyze it and return the structured JSON result. \n\n"
        f"QUOTE: \N{quote_text}\n\n"
        "OUTPUT JSON SCHEMA: \n"
        f"{schema_json}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "developer", "content": DEVELOPER_PROMPT},
        {"role": "user", "content": user_content},
    ]