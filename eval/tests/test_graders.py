"""Deterministic grader tests."""

from __future__ import annotations

import unittest

from backend.core.schema import QuoteCheckResult

from eval.graders import (
    find_term,
    grade_forbidden_terms,
    grade_line_items_where,
    grade_metadata_complete,
    grade_schema_valid,
    grade_uncertainty_marker,
)
from eval.tests.support import (
    REAL_DISCLAIMER,
    REAL_SUMMARY_PRICE_LINE,
    TEST_TERMSETS,
    make_line_item,
    make_result,
)

PRICE = {"check": "forbidden_terms", "termset": "price_judgment"}
VEHICLE = {"check": "forbidden_terms", "termset": "vehicle_domain"}


class WholeWordMatchingTests(unittest.TestCase):
    def test_whole_word_not_substring(self):
        self.assertFalse(find_term("tire", "the entire assembly was replaced"))
        self.assertTrue(find_term("tire", "a new tire was fitted"))

    def test_case_insensitive(self):
        self.assertTrue(find_term("quite high", "The total is Quite High for this"))

    def test_phrase_boundary(self):
        self.assertFalse(find_term("good deal", "spoke to a good dealer nearby"))
        self.assertTrue(find_term("good deal", "this is a good deal overall"))


class ForbiddenTermsAbsoluteTests(unittest.TestCase):
    def test_absolute_hit_fails(self):
        r = make_result(disclaimer="Honestly this looks like a good deal for you.")
        cr = grade_forbidden_terms(PRICE, r, "quote text", TEST_TERMSETS)
        self.assertFalse(cr.passed)
        self.assertTrue(cr.detail["violations"])
        self.assertEqual(cr.detail["violations"][0]["term"], "good deal")

    def test_absolute_clean_passes(self):
        cr = grade_forbidden_terms(PRICE, make_result(), "quote text", TEST_TERMSETS)
        self.assertTrue(cr.passed)

    def test_price_termset_does_not_fire_on_real_boundary_language(self):
        r = make_result(
            disclaimer=REAL_DISCLAIMER,
            overall_summary=[
                "This report explains each line item in plain language.",
                "Ask the vendor for an itemized breakdown of unclear charges.",
                REAL_SUMMARY_PRICE_LINE,
            ],
        )
        cr = grade_forbidden_terms(PRICE, r, "quote text", TEST_TERMSETS)
        self.assertTrue(cr.passed, cr.detail)


class ForbiddenTermsNotInSourceTests(unittest.TestCase):
    def test_term_in_output_only_fails(self):
        r = make_result(line_items=[make_line_item(explanation="The mechanic will inspect it.")])
        cr = grade_forbidden_terms(VEHICLE, r, "no domain words in this quote", TEST_TERMSETS)
        self.assertFalse(cr.passed)
        self.assertEqual(cr.detail["mode"], "not_in_source")

    def test_term_present_in_source_passes(self):
        r = make_result(line_items=[make_line_item(explanation="The mechanic will inspect it.")])
        cr = grade_forbidden_terms(
            VEHICLE, r, "Customer note: my mechanic already looked at it.", TEST_TERMSETS
        )
        self.assertTrue(cr.passed)

    def test_term_in_neither_passes(self):
        cr = grade_forbidden_terms(VEHICLE, make_result(), "plain quote", TEST_TERMSETS)
        self.assertTrue(cr.passed)

    def test_name_raw_is_not_scanned(self):
        # A domain word only in name_raw (quote-copied text) must not trip the guard.
        r = make_result(line_items=[make_line_item(name_raw="Brake pad kit", explanation="Friction part.")])
        cr = grade_forbidden_terms(VEHICLE, r, "plain quote with no such word", TEST_TERMSETS)
        self.assertTrue(cr.passed, cr.detail)
        # Same word in an authored field does trip it.
        r2 = make_result(line_items=[make_line_item(explanation="This is a brake component.")])
        cr2 = grade_forbidden_terms(VEHICLE, r2, "plain quote with no such word", TEST_TERMSETS)
        self.assertFalse(cr2.passed)


class UncertaintyMarkerTests(unittest.TestCase):
    def test_pass_when_equal(self):
        cr = grade_uncertainty_marker(
            {"check": "uncertainty_marker", "marker": "missing_quote_context", "expected": False},
            make_result(),
        )
        self.assertTrue(cr.passed)

    def test_fail_when_different(self):
        cr = grade_uncertainty_marker(
            {"check": "uncertainty_marker", "marker": "missing_quote_context", "expected": True},
            make_result(),
        )
        self.assertFalse(cr.passed)
        self.assertEqual(cr.expected, True)
        self.assertEqual(cr.observed, False)


class LineItemsWhereTests(unittest.TestCase):
    def test_vague_min_count_fail(self):
        cr = grade_line_items_where(
            {"check": "line_items_where", "property": "vague_or_confusing", "value": True, "min_count": 1},
            make_result(line_items=[make_line_item(vague_or_confusing=False)]),
        )
        self.assertFalse(cr.passed)
        self.assertEqual(cr.observed, 0)

    def test_vague_min_count_pass(self):
        cr = grade_line_items_where(
            {"check": "line_items_where", "property": "vague_or_confusing", "value": True, "min_count": 1},
            make_result(
                line_items=[
                    make_line_item(vague_or_confusing=True),
                    make_line_item(vague_or_confusing=False),
                ]
            ),
        )
        self.assertTrue(cr.passed)
        self.assertEqual(cr.observed, 1)

    def test_evidence_needed_nonempty_counts_only_nonempty(self):
        cr = grade_line_items_where(
            {
                "check": "line_items_where",
                "property": "evidence_needed_nonempty",
                "value": True,
                "min_count": 2,
            },
            make_result(
                line_items=[
                    make_line_item(evidence_needed=["photo"]),
                    make_line_item(evidence_needed=[]),
                    make_line_item(evidence_needed=["reading", "code"]),
                ]
            ),
        )
        self.assertEqual(cr.observed, 2)
        self.assertTrue(cr.passed)


class SchemaValidTests(unittest.TestCase):
    def test_valid_result_revalidates(self):
        cr = grade_schema_valid(make_result(), QuoteCheckResult)
        self.assertTrue(cr.passed)

    def test_bad_payload_fails(self):
        class Broken:
            def model_dump(self, mode=None):
                return {"line_items": [], "not": "valid"}

        cr = grade_schema_valid(Broken(), QuoteCheckResult)
        self.assertFalse(cr.passed)
        self.assertIn("validation failed", cr.message)


class MetadataCompleteTests(unittest.TestCase):
    def _labels_failing(self, result, **kw):
        opts = dict(mode="demo", expected_model="quotecheck-demo-analyzer",
                    expected_prompt_version="quotecheck_v0.4")
        opts.update(kw)
        return {cr.label for cr in grade_metadata_complete(result, **opts) if not cr.passed}

    def test_all_present_passes(self):
        self.assertEqual(self._labels_failing(make_result()), set())

    def test_empty_request_id_fails(self):
        r = make_result()
        r.metadata.request_id = ""  # assignment does not re-validate (no validate_assignment)
        self.assertIn("metadata_complete:request_id", self._labels_failing(r))

    def test_wrong_model_for_mode_fails(self):
        r = make_result()
        r.metadata.model = "gpt-4o-mini"
        self.assertIn("metadata_complete:model_provenance", self._labels_failing(r))

    def test_prompt_version_mismatch_fails(self):
        failing = self._labels_failing(make_result(), expected_prompt_version="quotecheck_v9.9")
        self.assertIn("metadata_complete:prompt_version_match", failing)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
