"""Corpus-validation tests — the permanent structural checks.

These drive the pure ``validate_corpus(cases, termsets)`` with in-memory dicts, so
no filesystem is touched, plus one smoke test that the real 27-case corpus loads.
"""

from __future__ import annotations

import unittest

from eval.corpus import (
    CASES_DIR,
    TERMSETS_PATH,
    Termset,
    load_corpus,
    validate_corpus,
)

TERMSETS = {
    "price_judgment": Termset("price_judgment", "absolute", "analysis_text", ("quite high", "good deal")),
    "vehicle_domain": Termset("vehicle_domain", "not_in_source", "analysis_text", ("mechanic", "car")),
    "trade_domain": Termset("trade_domain", "not_in_source", "analysis_text", ("plumber",)),
}


def _filler(i: int) -> dict:
    return {
        "case_id": f"F-{i:03d}",
        "domain": "generic_service",
        "categories": ["price_present"],
        "rationale": "filler",
        "quote_text": f"filler quote number {i} with unique words {i}{i}{i}",
        "deterministic_expectations": {"must": [], "must_not": []},
        "semantic_expectations": {
            "should_identify": [],
            "should_preserve_uncertainty": [],
            "must_not_invent": [],
            "notes": "",
        },
    }


def _reg(cid: str) -> dict:
    d = _filler(0)
    d["case_id"] = cid
    d["quote_text"] = f"regression quote for {cid}"
    d["categories"] = ["price_present"]
    d["regression_origin"] = f"origin note for {cid}"
    return d


def valid_corpus(n_filler: int = 25) -> list[dict]:
    cases = [_filler(i) for i in range(n_filler)]
    cases.append(_reg("REG-001"))
    cases.append(_reg("REG-002"))
    return cases


class ValidCorpusTests(unittest.TestCase):
    def test_real_corpus_loads_and_validates(self):
        corpus = load_corpus(CASES_DIR, TERMSETS_PATH)
        self.assertEqual(len(corpus.cases), 27)
        self.assertEqual(sum(c.case_id == "REG-001" for c in corpus.cases), 1)
        self.assertEqual(sum(c.case_id == "REG-002" for c in corpus.cases), 1)

    def test_synthetic_valid_corpus_has_no_errors(self):
        self.assertEqual(validate_corpus(valid_corpus(), TERMSETS), [])


class StructuralRejectionTests(unittest.TestCase):
    def _errs(self, cases):
        return validate_corpus(cases, TERMSETS)

    def test_duplicate_case_id_rejected(self):
        cases = valid_corpus()
        cases[1]["case_id"] = cases[0]["case_id"]
        errs = self._errs(cases)
        self.assertTrue(any("appears 2 times" in e for e in errs), errs)

    def test_unknown_check_type_rejected(self):
        cases = valid_corpus()
        cases[0]["deterministic_expectations"]["must"].append(
            {"check": "topic_present", "any_of": ["x"], "in": "analysis_text"}
        )
        errs = self._errs(cases)
        self.assertTrue(any("unknown check type" in e for e in errs), errs)

    def test_unknown_termset_rejected(self):
        cases = valid_corpus()
        cases[0]["deterministic_expectations"]["must_not"].append(
            {"check": "forbidden_terms", "termset": "no_such_set"}
        )
        errs = self._errs(cases)
        self.assertTrue(any("does not resolve" in e for e in errs), errs)

    def test_unknown_marker_rejected(self):
        cases = valid_corpus()
        cases[0]["deterministic_expectations"]["must"].append(
            {"check": "uncertainty_marker", "marker": "banana", "expected": True}
        )
        errs = self._errs(cases)
        self.assertTrue(any("marker 'banana'" in e for e in errs), errs)

    def test_line_items_where_risk_level_property_rejected(self):
        cases = valid_corpus()
        cases[0]["deterministic_expectations"]["must"].append(
            {"check": "line_items_where", "property": "risk_level", "value": "red", "min_count": 1}
        )
        errs = self._errs(cases)
        self.assertTrue(any("line_items_where property 'risk_level'" in e for e in errs), errs)

    def test_line_items_where_max_count_rejected(self):
        cases = valid_corpus()
        cases[0]["deterministic_expectations"]["must"].append(
            {
                "check": "line_items_where",
                "property": "vague_or_confusing",
                "value": True,
                "min_count": 1,
                "max_count": 3,
            }
        )
        errs = self._errs(cases)
        self.assertTrue(any("max_count" in e for e in errs), errs)

    def test_inline_forbidden_terms_rejected(self):
        cases = valid_corpus()
        cases[0]["deterministic_expectations"]["must_not"].append(
            {"check": "forbidden_terms", "terms": ["foo"], "mode": "absolute"}
        )
        errs = self._errs(cases)
        self.assertTrue(any("unsupported keys" in e and "forbidden_terms" in e for e in errs), errs)

    def test_per_case_termset_mode_override_rejected(self):
        cases = valid_corpus()
        cases[0]["deterministic_expectations"]["must_not"].append(
            {"check": "forbidden_terms", "termset": "vehicle_domain", "mode": "absolute"}
        )
        errs = self._errs(cases)
        self.assertTrue(any("unsupported keys" in e for e in errs), errs)

    def test_duplicate_quote_text_rejected(self):
        cases = valid_corpus()
        cases[2]["quote_text"] = cases[1]["quote_text"]
        errs = self._errs(cases)
        self.assertTrue(any("duplicate quote_text" in e for e in errs), errs)

    def test_corpus_too_small_rejected(self):
        errs = self._errs(valid_corpus(n_filler=21))  # 23 total
        self.assertTrue(any("outside the required range" in e for e in errs), errs)

    def test_corpus_too_large_rejected(self):
        errs = self._errs(valid_corpus(n_filler=29))  # 31 total
        self.assertTrue(any("outside the required range" in e for e in errs), errs)

    def test_corpus_boundary_sizes_accepted(self):
        self.assertEqual(self._errs(valid_corpus(n_filler=22)), [])  # 24
        self.assertEqual(self._errs(valid_corpus(n_filler=28)), [])  # 30

    def test_missing_reg_case_rejected(self):
        cases = [c for c in valid_corpus() if c["case_id"] != "REG-002"]
        cases.append(_filler(99))
        errs = self._errs(cases)
        self.assertTrue(any("REG-002 must appear exactly once" in e for e in errs), errs)

    def test_doubled_reg_case_rejected(self):
        cases = valid_corpus()
        cases[0] = _reg("REG-001")
        cases[0]["quote_text"] = "another reg-001 quote variant"
        errs = self._errs(cases)
        self.assertTrue(any("REG-001 must appear exactly once" in e for e in errs), errs)

    def test_regression_origin_on_non_reg_case_rejected(self):
        cases = valid_corpus()
        cases[0]["regression_origin"] = "sneaky"
        errs = self._errs(cases)
        self.assertTrue(any("only allowed on" in e for e in errs), errs)


class CategoryConsistencyTests(unittest.TestCase):
    def _errs(self, cases):
        return validate_corpus(cases, TERMSETS)

    def test_clean_itemized_requires_both_markers(self):
        cases = valid_corpus()
        cases[0]["categories"] = ["clean_itemized"]
        cases[0]["deterministic_expectations"]["must"] = [
            {"check": "uncertainty_marker", "marker": "ambiguous_items_present", "expected": False}
        ]  # missing missing_quote_context == false
        errs = self._errs(cases)
        self.assertTrue(any("missing_quote_context == false" in e for e in errs), errs)

    def test_clean_itemized_satisfied(self):
        cases = valid_corpus()
        cases[0]["categories"] = ["clean_itemized"]
        cases[0]["deterministic_expectations"]["must"] = [
            {"check": "uncertainty_marker", "marker": "ambiguous_items_present", "expected": False},
            {"check": "uncertainty_marker", "marker": "missing_quote_context", "expected": False},
        ]
        self.assertEqual(self._errs(cases), [])

    def test_professional_confirmation_expected_requires_marker(self):
        cases = valid_corpus()
        cases[0]["categories"] = ["professional_confirmation_expected"]
        errs = self._errs(cases)
        self.assertTrue(any("needs_professional_confirmation == true" in e for e in errs), errs)

    def test_cross_domain_trap_requires_domain_leakage_guard(self):
        cases = valid_corpus()
        cases[0]["categories"] = ["cross_domain_trap"]
        # only an absolute price guard — not a domain-leakage guard
        cases[0]["deterministic_expectations"]["must_not"] = [
            {"check": "forbidden_terms", "termset": "price_judgment"}
        ]
        errs = self._errs(cases)
        self.assertTrue(any("cross_domain_trap requires must_not" in e for e in errs), errs)

    def test_cross_domain_trap_satisfied_by_vehicle_domain(self):
        cases = valid_corpus()
        cases[0]["categories"] = ["cross_domain_trap"]
        cases[0]["deterministic_expectations"]["must_not"] = [
            {"check": "forbidden_terms", "termset": "price_judgment"},
            {"check": "forbidden_terms", "termset": "vehicle_domain"},
        ]
        self.assertEqual(self._errs(cases), [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
