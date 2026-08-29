"""Deterministic (Layer A) graders for the QC-3B eval runner.

Every grader returns one or more ``CheckResult`` objects. A ``CheckResult`` is an
explicit, interpretable record: a reviewer must be able to see *why* a case failed
without reading this file. Storing only a boolean is not enough.

Scope, deliberately narrow — exactly the QC-3A vocabulary the 27 cases use:

    schema_valid       (global)  independent Pydantic re-validation
    metadata_complete  (global)  provenance + completeness, one result per sub-assertion
    forbidden_terms              shared termset, absolute | not_in_source
    uncertainty_marker           boolean read of result.uncertainty_markers
    line_items_where             count of line items matching a predicate

What these graders establish is mechanical only. A clean run says nothing about
faithfulness, hallucination, usefulness, or calibration — those are Layer B, scored
by a human against eval/rubric.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- #
# CheckResult
# --------------------------------------------------------------------------- #

@dataclass
class CheckResult:
    check: str
    passed: bool
    label: str
    expected: Any = None
    observed: Any = None
    message: str = ""
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "label": self.label,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "message": self.message,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------- #
# Whole-word / whole-phrase matching
# --------------------------------------------------------------------------- #

_WORD = r"\w"


def term_pattern(term: str) -> re.Pattern:
    """Case-insensitive whole-word / whole-phrase matcher.

    Internal whitespace in a phrase matches any run of whitespace. Word-boundary
    lookarounds mean 'tire' does not match 'entire', 'good deal' does not match
    'good dealer', and 'fair price' does not match 'guarantee fair pricing'.
    """
    tokens = [re.escape(tok) for tok in term.split()]
    body = r"\s+".join(tokens)
    return re.compile(rf"(?<!{_WORD}){body}(?!{_WORD})", re.IGNORECASE)


def find_term(term: str, text: str) -> bool:
    return term_pattern(term).search(text or "") is not None


# --------------------------------------------------------------------------- #
# Analysis-authored text extraction (the 'analysis_text' group, the only one)
# --------------------------------------------------------------------------- #

def analysis_text_segments(result) -> list[tuple[str, str]]:
    """Return (field_label, text) segments for the analysis-authored fields.

    name_raw is intentionally excluded — the schema defines it as text copied from
    the quote, so a term appearing there is quotation, not invention. metadata,
    request_id, model and refusals are never scanned.
    """
    segs: list[tuple[str, str]] = []
    for i, li in enumerate(result.line_items):
        segs.append((f"line_items[{i}].explanation", li.explanation or ""))
        segs.append((f"line_items[{i}].rationale_short", li.rationale_short or ""))
        for j, ev in enumerate(li.evidence_needed or []):
            segs.append((f"line_items[{i}].evidence_needed[{j}]", ev or ""))
    for j, s in enumerate(result.overall_summary or []):
        segs.append((f"overall_summary[{j}]", s or ""))
    for j, s in enumerate(result.verification_questions or []):
        segs.append((f"verification_questions[{j}]", s or ""))
    for j, s in enumerate(result.things_to_verify or []):
        segs.append((f"things_to_verify[{j}]", s or ""))
    segs.append(("disclaimer", result.disclaimer or ""))
    return segs


# --------------------------------------------------------------------------- #
# Global: schema validity (independent Pydantic re-validation)
# --------------------------------------------------------------------------- #

def grade_schema_valid(result, result_cls) -> CheckResult:
    """Re-run Pydantic validation against the serialized result object.

    Not a read of metadata.schema_valid — an independent round-trip.
    """
    try:
        payload = result.model_dump(mode="json")
    except Exception as e:  # pragma: no cover - result is already a model
        return CheckResult(
            check="schema_valid",
            passed=False,
            label="schema_valid",
            expected="serializable QuoteCheckResult",
            observed=f"{type(e).__name__}: {e}",
            message=f"could not serialize analyzer result: {type(e).__name__}: {e}",
        )
    try:
        result_cls.model_validate(payload)
    except Exception as e:
        return CheckResult(
            check="schema_valid",
            passed=False,
            label="schema_valid",
            expected="validates against QuoteCheckResult",
            observed=f"{type(e).__name__}",
            message=f"independent QuoteCheckResult validation failed: {e}",
        )
    return CheckResult(
        check="schema_valid",
        passed=True,
        label="schema_valid",
        expected="validates against QuoteCheckResult",
        observed="valid",
        message="response independently re-validates against QuoteCheckResult",
    )


def schema_valid_execution_failure(execution_error: str) -> CheckResult:
    return CheckResult(
        check="schema_valid",
        passed=False,
        label="schema_valid",
        expected="analyzer returns a QuoteCheckResult",
        observed="execution error",
        message=f"analyzer execution failed: {execution_error}",
    )


# --------------------------------------------------------------------------- #
# Global: metadata completeness + provenance
# --------------------------------------------------------------------------- #

def grade_metadata_complete(
    result, *, mode: str, expected_model: str, expected_prompt_version: str
) -> list[CheckResult]:
    """One CheckResult per sub-assertion so every failure is individually legible."""
    m = result.metadata
    out: list[CheckResult] = []

    def add(label: str, passed: bool, expected, observed, message: str) -> None:
        out.append(
            CheckResult(
                check="metadata_complete",
                passed=passed,
                label=f"metadata_complete:{label}",
                expected=expected,
                observed=observed,
                message=message,
            )
        )

    pv = getattr(m, "prompt_version", None)
    add(
        "prompt_version",
        bool(pv and str(pv).strip()),
        "non-empty",
        pv,
        f"metadata.prompt_version = {pv!r}",
    )
    mdl = getattr(m, "model", None)
    add("model", bool(mdl and str(mdl).strip()), "non-empty", mdl, f"metadata.model = {mdl!r}")
    rid = getattr(m, "request_id", None)
    add("request_id", bool(rid and str(rid).strip()), "non-empty", rid, f"metadata.request_id = {rid!r}")
    sv = getattr(m, "schema_valid", None)
    add("schema_valid", sv is True, True, sv, f"metadata.schema_valid = {sv!r}")

    lat = getattr(m, "latency_ms", None)
    lat_ok = isinstance(lat, int) and not isinstance(lat, bool) and lat >= 0
    add("latency", lat_ok, ">= 0", lat, f"metadata.latency_ms = {lat!r}")

    created = getattr(m, "created_at", None)
    add("created_at", created is not None, "present", str(created), f"metadata.created_at = {created!r}")

    add(
        "model_provenance",
        mdl == expected_model,
        expected_model,
        mdl,
        f"{mode} mode expects metadata.model == {expected_model!r}, observed {mdl!r}",
    )
    add(
        "prompt_version_match",
        pv == expected_prompt_version,
        expected_prompt_version,
        pv,
        f"metadata.prompt_version should equal backend PROMPT_VERSION "
        f"({expected_prompt_version!r}), observed {pv!r}",
    )
    return out


# --------------------------------------------------------------------------- #
# Case-level: forbidden_terms (shared termset only)
# --------------------------------------------------------------------------- #

def grade_forbidden_terms(chk: dict, result, quote_text: str, termsets: dict) -> CheckResult:
    name = chk["termset"]
    ts = termsets[name]
    mode = ts.mode
    label = f"forbidden_terms:{name}"

    segments = analysis_text_segments(result)
    violations: list[dict] = []

    for term in ts.terms:
        pat = term_pattern(term)
        for field_label, text in segments:
            mo = pat.search(text or "")
            if not mo:
                continue
            if mode == "not_in_source" and pat.search(quote_text or ""):
                # term is present in the customer's own quote -> sourced, not invented
                continue
            start = max(0, mo.start() - 30)
            end = min(len(text), mo.end() + 30)
            violations.append(
                {
                    "term": term,
                    "field": field_label,
                    "snippet": text[start:end].strip(),
                }
            )

    passed = not violations
    if mode == "not_in_source":
        why = (
            "a deterministic proxy for invented domain terminology, not proof of "
            "semantic hallucination"
        )
    else:
        why = "affirmative unsupported judgment phrase; forbidden on every case"

    if passed:
        message = f"no '{name}' terms ({mode}) found in analysis-authored text"
    else:
        hits = "; ".join(f"{v['term']!r} in {v['field']}" for v in violations)
        message = f"'{name}' ({mode}) violation — {hits}"

    return CheckResult(
        check="forbidden_terms",
        passed=passed,
        label=label,
        expected=f"no {name} terms in analysis_text ({mode})",
        observed=f"{len(violations)} violation(s)",
        message=message,
        detail={"termset": name, "mode": mode, "violations": violations, "note": why},
    )


# --------------------------------------------------------------------------- #
# Case-level: uncertainty_marker
# --------------------------------------------------------------------------- #

def grade_uncertainty_marker(chk: dict, result) -> CheckResult:
    marker = chk["marker"]
    expected = bool(chk["expected"])
    observed = getattr(result.uncertainty_markers, marker)
    passed = observed == expected
    return CheckResult(
        check="uncertainty_marker",
        passed=passed,
        label=f"uncertainty_marker:{marker}",
        expected=expected,
        observed=observed,
        message=f"{marker} expected {expected}, observed {observed}",
        detail={"marker": marker},
    )


# --------------------------------------------------------------------------- #
# Case-level: line_items_where
# --------------------------------------------------------------------------- #

def _line_item_matches(li, prop: str, value: bool) -> bool:
    if prop == "vague_or_confusing":
        return bool(li.vague_or_confusing) == value
    if prop == "evidence_needed_nonempty":
        return bool(li.evidence_needed) == value
    raise ValueError(f"unsupported line_items_where property: {prop!r}")


def grade_line_items_where(chk: dict, result) -> CheckResult:
    prop = chk["property"]
    value = bool(chk["value"])
    min_count = int(chk["min_count"])

    matching = [
        i for i, li in enumerate(result.line_items) if _line_item_matches(li, prop, value)
    ]
    count = len(matching)
    passed = count >= min_count
    return CheckResult(
        check="line_items_where",
        passed=passed,
        label=f"line_items_where:{prop}",
        expected=f">= {min_count} line items with {prop} == {value}",
        observed=count,
        message=(
            f"{count} line item(s) where {prop} == {value} "
            f"(need >= {min_count}); indices {matching}"
        ),
        detail={"property": prop, "value": value, "min_count": min_count, "indices": matching},
    )


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #

def grade_check(chk: dict, result, *, quote_text: str, termsets: dict) -> CheckResult:
    name = chk["check"]
    if name == "forbidden_terms":
        return grade_forbidden_terms(chk, result, quote_text, termsets)
    if name == "uncertainty_marker":
        return grade_uncertainty_marker(chk, result)
    if name == "line_items_where":
        return grade_line_items_where(chk, result)
    raise ValueError(f"unknown check type reached grader: {name!r}")  # pragma: no cover


# Global high-precision price guard, injected into every case's must_not.
PRICE_GUARD_CHECK: dict = {"check": "forbidden_terms", "termset": "price_judgment"}
