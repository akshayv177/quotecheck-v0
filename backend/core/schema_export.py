"""
Schema Export Utilities (v0)

Provides a stable way to export the QuoteCheckResult JSON schema.
This is useful for:
- embedding schema in prompts (Slice 3)
- documentation
- evaluation tooling
"""

from __future__ import annotations

import json
from backend.core.schema import QuoteCheckResult


def quotecheck_result_schema_json() -> str:
    """
    Returns the QuoteCheckResult JSON schema as a compact JSON string.
    """
    schema = QuoteCheckResult.model_json_schema()
    return json.dumps(schema, ensure_ascii=False)