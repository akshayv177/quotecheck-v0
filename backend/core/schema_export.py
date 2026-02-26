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
from typing import Any, Dict, List

from backend.core.schema import QuoteCheckResult


def _normalize_for_openai_strict(schema: Any) -> Any:
    """
    Normalize a Pydantic-generated JSON schema to satisfy OpenAI strict Structured Outputs.

    Requirements enforced:
    - For every object: additionalProperties must be false.
    - For every object: required must include *all* keys in properties.
    - For fields that were optional in the original schema, make them nullable by
      allowing 'null' in their schema.

    This keeps the API happy while allowing "optional in practice" fields to be null.
    """
    if isinstance(schema, dict):
        # Recurse first so children are normalized.
        for k, v in list(schema.items()):
            schema[k] = _normalize_for_openai_strict(v)

        # If this node is an object schema, enforce strict object rules.
        if schema.get("type") == "object" and "properties" in schema:
            props = schema.get("properties", {})
            schema["additionalProperties"] = False

            # Ensure required contains every property key
            schema["required"] = list(props.keys())

            # Make properties nullable if they look optional.
            # Heuristic: if property schema contains "default": None, or is missing from required
            # in the original schema (we can't see original after overwrite), we allow null for a few known fields.
            for pname, pschema in props.items():
                if pname in {"price"}:
                    # Allow null for price
                    props[pname] = _make_nullable(pschema)

        return schema

    if isinstance(schema, list):
        return [_normalize_for_openai_strict(x) for x in schema]

    return schema


def _make_nullable(pschema: Any) -> Any:
    """Wrap a schema to allow null values."""
    if not isinstance(pschema, dict):
        return {"anyOf": [pschema, {"type": "null"}]}

    # If it already allows null, keep it.
    if pschema.get("type") == "null":
        return pschema
    if "anyOf" in pschema:
        anyof = pschema["anyOf"]
        if isinstance(anyof, list) and any(x.get("type") == "null" for x in anyof if isinstance(x, dict)):
            return pschema
        return {"anyOf": anyof + [{"type": "null"}]}
    if "oneOf" in pschema:
        return {"oneOf": pschema["oneOf"] + [{"type": "null"}]}

    # If type is present, turn it into a union with null.
    if "type" in pschema:
        t = pschema["type"]
        if isinstance(t, list):
            if "null" not in t:
                pschema["type"] = t + ["null"]
            return pschema
        return {"type": [t, "null"], **{k: v for k, v in pschema.items() if k != "type"}}

    # Otherwise wrap with anyOf
    return {"anyOf": [pschema, {"type": "null"}]}


def quotecheck_result_schema_obj() -> Dict[str, Any]:
    """
    Return the QuoteCheckResult JSON schema as a dict, post-processed to satisfy
    OpenAI Structured Outputs strict JSON schema requirements.
    """
    schema = QuoteCheckResult.model_json_schema()
    schema = _normalize_for_openai_strict(schema)
    return schema


def quotecheck_result_schema_json() -> str:
    """Return the QuoteCheckResult JSON schema as a JSON string."""
    return json.dumps(quotecheck_result_schema_obj(), ensure_ascii=False)