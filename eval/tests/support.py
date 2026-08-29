"""Small builders for eval-harness tests.

These construct real ``QuoteCheckResult`` / ``Case`` objects with minimal valid
fields so grader tests do not depend on the analyzer or the filesystem.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.core.schema import (
    LineItem,
    MetaData,
    QuoteCheckResult,
    UncertaintyMarkers,
)

from eval.corpus import Case, Termset

# The real committed Demo disclaimer template (vehicle variant) — used to prove the
# high-precision price_judgment termset does not fire on honest boundary language.
REAL_DISCLAIMER = (
    "QuoteCheck results may be incomplete or wrong. This analysis is informational "
    "and should not replace professional advice, official estimates, warranty terms, "
    "or a second opinion for high-value or safety-critical work — verify with a "
    "certified mechanic. QuoteCheck explains quotes and suggests questions; it does "
    "not verify vendor claims, guarantee fair pricing, or perform price benchmarking."
)
REAL_SUMMARY_PRICE_LINE = (
    "Price benchmarking is not implemented; no market price comparison is being made."
)


def make_line_item(**over) -> LineItem:
    data = dict(
        name_raw="Sample line item",
        normalized_category="wear_and_tear",
        explanation="A plain explanation of the item.",
        vague_or_confusing=False,
        recommended_action="approve",
        risk_level="green",
        confidence=0.5,
        rationale_short="Low risk.",
        evidence_needed=[],
    )
    data.update(over)
    return LineItem(**data)


def make_metadata(**over) -> MetaData:
    data = dict(
        prompt_version="quotecheck_v0.4",
        model="quotecheck-demo-analyzer",
        created_at=datetime.now(timezone.utc),
        request_id="req-abc-123",
        latency_ms=0,
        schema_valid=True,
    )
    data.update(over)
    return MetaData(**data)


def make_result(**over) -> QuoteCheckResult:
    data = dict(
        line_items=[make_line_item()],
        overall_summary=["Summary one.", "Summary two.", "Summary three."],
        verification_questions=["Q1?", "Q2?", "Q3?"],
        things_to_verify=["Gap 1", "Gap 2", "Gap 3"],
        uncertainty_markers=UncertaintyMarkers(
            ambiguous_items_present=False,
            missing_quote_context=False,
            needs_professional_confirmation=False,
        ),
        disclaimer="Informational only.",
        metadata=make_metadata(),
    )
    data.update(over)
    return QuoteCheckResult(**data)


def make_case(**over) -> Case:
    from pathlib import Path

    data = dict(
        case_id="TEST-001",
        domain="automotive",
        categories=("price_present",),
        rationale="test case",
        quote_text="A plain quote with no domain vocabulary at all.",
        must=(),
        must_not=(),
        semantic_expectations={
            "should_identify": [],
            "should_preserve_uncertainty": [],
            "must_not_invent": [],
            "notes": "",
        },
        regression_origin=None,
        source_path=Path("TEST-001.json"),
        raw={},
    )
    data.update(over)
    return Case(**data)


TEST_TERMSETS = {
    "price_judgment": Termset(
        "price_judgment", "absolute", "analysis_text",
        ("quite high", "seems expensive", "good deal", "competitively priced"),
    ),
    "vehicle_domain": Termset(
        "vehicle_domain", "not_in_source", "analysis_text",
        ("mechanic", "vehicle", "car", "brake", "tyre", "tire"),
    ),
    "trade_domain": Termset(
        "trade_domain", "not_in_source", "analysis_text",
        ("plumber", "plumbing", "contractor", "renovation"),
    ),
}
