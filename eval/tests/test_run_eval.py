"""Runner reporting / exit-semantics / cost-boundary tests (pure functions + main guard)."""

from __future__ import annotations

import contextlib
import io
import unittest

from backend.core.schema import AnalyzeRequest

from eval import run_eval
from eval.run_eval import (
    CaseResult,
    INTERPRETATION_BOUNDARY,
    aggregate_by_category,
    aggregate_by_domain,
    build_summary_md,
    format_execution_error,
    percentile,
    run_case,
    suite_exit_code,
)
from eval.graders import CheckResult
from eval.tests.support import make_case


def mk(case_id, domain, categories, *, ok=True, schema=True, exec_err=None):
    checks = []
    if not ok:
        checks.append(CheckResult(check="uncertainty_marker", passed=False,
                                  label="uncertainty_marker:x", message="boom"))
    return CaseResult(
        case_id=case_id,
        domain=domain,
        categories=tuple(categories),
        mode="demo",
        prompt_version="quotecheck_v0.4",
        model="quotecheck-demo-analyzer",
        schema_pass=schema,
        check_results=checks,
        latency_ms=0,
        execution_error=exec_err,
        rationale="r",
    )


class DeterministicPassTests(unittest.TestCase):
    def test_all_pass(self):
        self.assertTrue(mk("A", "automotive", ["price_present"]).deterministic_pass)

    def test_schema_fail_is_case_fail(self):
        self.assertFalse(mk("A", "automotive", ["price_present"], schema=False).deterministic_pass)

    def test_execution_error_is_case_fail(self):
        self.assertFalse(
            mk("A", "automotive", ["price_present"], exec_err="RuntimeError: x").deterministic_pass
        )

    def test_failed_check_is_case_fail(self):
        self.assertFalse(mk("A", "automotive", ["price_present"], ok=False).deterministic_pass)


class ExitCodeTests(unittest.TestCase):
    def test_all_pass_zero(self):
        self.assertEqual(suite_exit_code([mk("A", "automotive", ["x"]), mk("B", "hvac_appliance", ["y"])]), 0)

    def test_any_fail_nonzero(self):
        self.assertEqual(
            suite_exit_code([mk("A", "automotive", ["x"]), mk("B", "hvac_appliance", ["y"], ok=False)]), 1
        )

    def test_empty_nonzero(self):
        self.assertEqual(suite_exit_code([]), 1)


class AggregationTests(unittest.TestCase):
    def setUp(self):
        self.results = [
            mk("A", "automotive", ["price_present", "clean_itemized"]),
            mk("B", "automotive", ["price_present"], ok=False),
            mk("C", "hvac_appliance", ["clean_itemized"], ok=False),
        ]

    def test_by_domain(self):
        rows = {r["key"]: r for r in aggregate_by_domain(self.results)}
        self.assertEqual(rows["automotive"], {"key": "automotive", "cases": 2, "passed": 1, "failed": 1})
        self.assertEqual(rows["hvac_appliance"], {"key": "hvac_appliance", "cases": 1, "passed": 0, "failed": 1})

    def test_by_category_counts_multi_category_in_each(self):
        rows = {r["key"]: r for r in aggregate_by_category(self.results)}
        self.assertEqual(rows["price_present"], {"key": "price_present", "cases": 2, "passed": 1, "failed": 1})
        self.assertEqual(rows["clean_itemized"], {"key": "clean_itemized", "cases": 2, "passed": 1, "failed": 1})


class PercentileTests(unittest.TestCase):
    def test_nearest_rank(self):
        self.assertEqual(percentile([10, 20, 30, 40], 50), 20.0)
        self.assertEqual(percentile(list(range(1, 11)), 95), 10.0)
        self.assertEqual(percentile([10, 20, 30, 40], 100), 40.0)

    def test_single_and_empty(self):
        self.assertEqual(percentile([5], 50), 5.0)
        self.assertIsNone(percentile([], 50))


class SummaryTests(unittest.TestCase):
    def test_summary_has_all_sections_and_reg_rows(self):
        results = [
            mk("AUTO-001", "automotive", ["clean_itemized"], ok=False),
            mk("REG-001", "hvac_appliance", ["cross_domain_trap"], ok=False),
            mk("REG-002", "hvac_appliance", ["price_present"]),
        ]
        md = build_summary_md(
            results,
            run_timestamp="20260101T000000Z",
            mode="demo",
            model="quotecheck-demo-analyzer",
            prompt_version="quotecheck_v0.4",
            selected_case_ids=[r.case_id for r in results],
            total_corpus=27,
            jsonl_name="run_20260101T000000Z.jsonl",
        )
        for heading in [
            "## Run metadata",
            "## Overall results",
            "## Failures by domain",
            "## Failures by category",
            "## Failed cases",
            "## Historical regressions",
            "## Latency",
            "## Human review",
            "## Interpretation boundary",
        ]:
            self.assertIn(heading, md)
        self.assertIn("**REG-001**: FAIL", md)
        self.assertIn("**REG-002**: PASS", md)
        self.assertIn(INTERPRETATION_BOUNDARY, md)
        self.assertIn("not reviewed in this automated run", md)


class ExecutionErrorWrappingTests(unittest.TestCase):
    def test_http_exception_becomes_readable_execution_error(self):
        from fastapi import HTTPException

        def boom(_req):
            raise HTTPException(status_code=500, detail="analyzer blew up")

        cr = run_case(
            boom, AnalyzeRequest, None, make_case(),
            mode="demo", expected_model="quotecheck-demo-analyzer",
            expected_prompt_version="quotecheck_v0.4", termsets={},
        )
        self.assertFalse(cr.deterministic_pass)
        self.assertIsNotNone(cr.execution_error)
        self.assertIn("status_code=500", cr.execution_error)
        self.assertIn("analyzer blew up", cr.execution_error)
        self.assertEqual(cr.failed_checks, ["schema_valid"])

    def test_plain_exception_becomes_readable_execution_error(self):
        def boom(_req):
            raise RuntimeError("no api key")

        cr = run_case(
            boom, AnalyzeRequest, None, make_case(),
            mode="demo", expected_model="quotecheck-demo-analyzer",
            expected_prompt_version="quotecheck_v0.4", termsets={},
        )
        self.assertFalse(cr.deterministic_pass)
        self.assertIn("RuntimeError: no api key", cr.execution_error)

    def test_format_execution_error_plain(self):
        self.assertEqual(format_execution_error(ValueError("x")), "ValueError: x")


class PaidModeGuardTests(unittest.TestCase):
    def test_openai_without_allow_paid_never_reaches_analysis_path(self):
        calls = []
        original = run_eval.run_suite
        run_eval.run_suite = lambda args: calls.append("ran") or 0
        try:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = run_eval.main(["--mode", "openai"])
        finally:
            run_eval.run_suite = original
        self.assertEqual(code, 2)
        self.assertEqual(calls, [], "run_suite (the only path that imports the analyzer) must not run")
        self.assertIn("No API call was made", err.getvalue())

    def test_demo_mode_reaches_run_suite(self):
        calls = []
        original = run_eval.run_suite
        run_eval.run_suite = lambda args: calls.append("ran") or 0
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                code = run_eval.main(["--mode", "demo"])
        finally:
            run_eval.run_suite = original
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["ran"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
