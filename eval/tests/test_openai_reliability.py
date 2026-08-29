"""QC-4 reliability suite for the OpenAI execution path.

No paid API calls: every test patches the OpenAI client boundary
(``backend.core.openai_analyzer.OpenAI``) with a fake whose ``responses.create``
raises a chosen ``openai`` exception or returns a fabricated ``Response``-shaped
object built from the installed SDK's type definitions (openai==2.24.0).

Run: ``python -m unittest discover -s eval/tests -p 'test_*.py' -v`` from repo root.
"""

from __future__ import annotations

import contextlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from backend.core import errors
from backend.core.config import OPENAI_MAX_ATTEMPTS, OPENAI_TIMEOUT_DEFAULT_SECONDS
from backend.core.errors import FailureCategory, QuoteCheckError
from backend.core.schema import QuoteCheckResult
from eval.tests.support import make_result

REPO_ROOT = Path(__file__).resolve().parents[2]
VALID_PAYLOAD_JSON = make_result().model_dump_json()


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

def _httpx_response(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers=headers or {},
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
    )


def openai_exc(kind: str) -> Exception:
    """Construct a real ``openai`` SDK exception instance for classification tests."""
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        InternalServerError,
        RateLimitError,
    )

    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    if kind == "timeout":
        return APITimeoutError(request=req)
    if kind == "connection":
        return APIConnectionError(message="connection reset", request=req)
    if kind == "rate_limit":
        return RateLimitError(
            "slow down",
            response=_httpx_response(429, {"x-request-id": "req_openai_rl"}),
            body=None,
        )
    if kind == "server":
        return InternalServerError("upstream boom", response=_httpx_response(503), body=None)
    if kind == "auth":
        return AuthenticationError("bad key", response=_httpx_response(401), body=None)
    if kind == "bad_request":
        return BadRequestError("bad request", response=_httpx_response(400), body=None)
    raise ValueError(kind)


def fake_response(*, status="completed", output_text="", output=None,
                  incomplete_details=None, error=None) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        output_text=output_text,
        output=output or [],
        incomplete_details=incomplete_details,
        error=error,
    )


def valid_response() -> SimpleNamespace:
    return fake_response(output_text=VALID_PAYLOAD_JSON)


def refusal_response() -> SimpleNamespace:
    part = SimpleNamespace(type="refusal", refusal="I can't help with that.")
    return fake_response(status="completed", output=[SimpleNamespace(content=[part])])


def incomplete_response() -> SimpleNamespace:
    return fake_response(
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )


@contextlib.contextmanager
def patched_openai(create_side_effect, *, api_key="sk-test-key", timeout_raw=None):
    """Patch the OpenAI client boundary; yield (create_mock, ctor_kwargs)."""
    ctor_kwargs: dict = {}
    create_mock = mock.MagicMock(side_effect=create_side_effect)

    def _factory(*_args, **kwargs):
        ctor_kwargs.clear()
        ctor_kwargs.update(kwargs)
        client = mock.MagicMock()
        client.responses.create = create_mock
        return client

    with mock.patch("backend.core.openai_analyzer.OpenAI", _factory), \
         mock.patch("backend.core.openai_analyzer.OPENAI_API_KEY", api_key), \
         mock.patch("backend.core.openai_analyzer.OPENAI_TIMEOUT_SECONDS_RAW", timeout_raw):
        yield create_mock, ctor_kwargs


@contextlib.contextmanager
def openai_mode_app(log_path=None):
    """Put ``backend.app`` into OpenAI mode; redirect the run log away from the
    real ``logs/app_runs.jsonl`` (to ``log_path`` if given, else a throwaway file)."""
    import backend.app as appmod

    with contextlib.ExitStack() as es:
        es.enter_context(mock.patch.object(appmod, "USE_OPENAI", True))
        es.enter_context(mock.patch.object(appmod, "ANALYZER_NAME", "openai"))
        if log_path is None:
            td = es.enter_context(tempfile.TemporaryDirectory())
            log_path = str(Path(td) / "runs.jsonl")
        es.enter_context(mock.patch.object(appmod, "APP_RUN_LOG_PATH", log_path))
        yield appmod


def last_log_record(path: str) -> dict:
    return json.loads(Path(path).read_text().splitlines()[-1])


# --------------------------------------------------------------------------- #
# 1-4, 5-8: classification of provider/transport and model-output failures
# --------------------------------------------------------------------------- #

class ClassificationTests(unittest.TestCase):
    def test_timeout(self):
        self.assertEqual(
            errors.classify_openai_exception(openai_exc("timeout")),
            FailureCategory.PROVIDER_TIMEOUT,
        )

    def test_connection_unavailable(self):
        self.assertEqual(
            errors.classify_openai_exception(openai_exc("connection")),
            FailureCategory.PROVIDER_UNAVAILABLE,
        )

    def test_server_5xx_unavailable(self):
        self.assertEqual(
            errors.classify_openai_exception(openai_exc("server")),
            FailureCategory.PROVIDER_UNAVAILABLE,
        )

    def test_rate_limited(self):
        self.assertEqual(
            errors.classify_openai_exception(openai_exc("rate_limit")),
            FailureCategory.PROVIDER_RATE_LIMITED,
        )

    def test_auth_is_configuration_error(self):
        self.assertEqual(
            errors.classify_openai_exception(openai_exc("auth")),
            FailureCategory.CONFIGURATION_ERROR,
        )

    def test_bad_request_is_configuration_error(self):
        self.assertEqual(
            errors.classify_openai_exception(openai_exc("bad_request")),
            FailureCategory.CONFIGURATION_ERROR,
        )

    def test_unknown_is_internal_error(self):
        self.assertEqual(
            errors.classify_openai_exception(RuntimeError("???")),
            FailureCategory.INTERNAL_ERROR,
        )

    def test_transient_set_is_exactly_connection_timeout_5xx(self):
        self.assertTrue(errors.is_transient_openai_exception(openai_exc("timeout")))
        self.assertTrue(errors.is_transient_openai_exception(openai_exc("connection")))
        self.assertTrue(errors.is_transient_openai_exception(openai_exc("server")))
        self.assertFalse(errors.is_transient_openai_exception(openai_exc("rate_limit")))
        self.assertFalse(errors.is_transient_openai_exception(openai_exc("auth")))
        self.assertFalse(errors.is_transient_openai_exception(openai_exc("bad_request")))
        self.assertFalse(errors.is_transient_openai_exception(RuntimeError("x")))


# --------------------------------------------------------------------------- #
# 5-8: response-state handling in the analyzer
# --------------------------------------------------------------------------- #

class ResponseStateTests(unittest.TestCase):
    def _run_expect_error(self, side_effect):
        from backend.core.openai_analyzer import analyze_quote_openai

        with patched_openai(side_effect) as (create_mock, _):
            with self.assertRaises(QuoteCheckError) as ctx:
                analyze_quote_openai(quote_text="a quote", request_id="rid-1")
        return ctx.exception, create_mock

    def test_refusal(self):
        err, cm = self._run_expect_error([refusal_response()])
        self.assertEqual(err.category, FailureCategory.PROVIDER_REFUSAL)
        self.assertFalse(err.retryable)
        self.assertEqual(err.http_status, 502)
        self.assertEqual(cm.call_count, 1)
        self.assertEqual(err.provider_attempts, 1)

    def test_content_filter_is_refusal(self):
        resp = fake_response(
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="content_filter"),
        )
        err, cm = self._run_expect_error([resp])
        self.assertEqual(err.category, FailureCategory.PROVIDER_REFUSAL)
        self.assertEqual(cm.call_count, 1)

    def test_incomplete_response(self):
        err, cm = self._run_expect_error([incomplete_response()])
        self.assertEqual(err.category, FailureCategory.PROVIDER_INCOMPLETE_RESPONSE)
        self.assertEqual(err.response_status, "incomplete")
        self.assertEqual(err.incomplete_reason, "max_output_tokens")
        self.assertEqual(cm.call_count, 1)

    def test_empty_output_is_invalid_model_output(self):
        err, cm = self._run_expect_error([fake_response(output_text="   ")])
        self.assertEqual(err.category, FailureCategory.INVALID_MODEL_OUTPUT)
        self.assertEqual(cm.call_count, 1)

    def test_non_json_output_is_invalid_model_output(self):
        err, cm = self._run_expect_error([fake_response(output_text="{not valid json")])
        self.assertEqual(err.category, FailureCategory.INVALID_MODEL_OUTPUT)
        self.assertEqual(cm.call_count, 1)

    def test_schema_violation_is_invalid_model_output(self):
        broken = json.loads(VALID_PAYLOAD_JSON)
        broken.pop("line_items")
        err, cm = self._run_expect_error([fake_response(output_text=json.dumps(broken))])
        self.assertEqual(err.category, FailureCategory.INVALID_MODEL_OUTPUT)
        self.assertEqual(cm.call_count, 1)


# --------------------------------------------------------------------------- #
# 9: configuration failures
# --------------------------------------------------------------------------- #

class ConfigurationTests(unittest.TestCase):
    def _expect_config_error(self, *, api_key="sk-test-key", timeout_raw=None):
        from backend.core.openai_analyzer import analyze_quote_openai

        with patched_openai([valid_response()], api_key=api_key, timeout_raw=timeout_raw) as (cm, _):
            with self.assertRaises(QuoteCheckError) as ctx:
                analyze_quote_openai(quote_text="a quote", request_id="rid-1")
            self.assertEqual(ctx.exception.category, FailureCategory.CONFIGURATION_ERROR)
            self.assertEqual(cm.call_count, 0, "no provider call may be made on a config error")

    def test_missing_api_key_none(self):
        self._expect_config_error(api_key=None)

    def test_missing_api_key_empty(self):
        self._expect_config_error(api_key="")

    def test_timeout_not_a_number(self):
        self._expect_config_error(timeout_raw="soon")

    def test_timeout_zero(self):
        self._expect_config_error(timeout_raw="0")

    def test_timeout_negative(self):
        self._expect_config_error(timeout_raw="-5")

    def test_timeout_nan(self):
        self._expect_config_error(timeout_raw="nan")

    def test_timeout_inf(self):
        self._expect_config_error(timeout_raw="inf")

    def test_valid_timeout_override_passes_through(self):
        from backend.core.openai_analyzer import analyze_quote_openai

        with patched_openai([valid_response()], timeout_raw="12.5") as (cm, ctor):
            analyze_quote_openai(quote_text="a quote", request_id="rid-1")
        self.assertEqual(ctor.get("timeout"), 12.5)
        self.assertEqual(cm.call_count, 1)


# --------------------------------------------------------------------------- #
# 10-13: retry ownership and bounds
# --------------------------------------------------------------------------- #

class RetryOwnershipTests(unittest.TestCase):
    def test_sdk_client_built_with_no_sdk_retry_and_explicit_timeout(self):
        from backend.core.openai_analyzer import analyze_quote_openai

        with patched_openai([valid_response()]) as (_cm, ctor):
            analyze_quote_openai(quote_text="a quote", request_id="rid-1")
        self.assertEqual(ctor.get("max_retries"), 0)
        self.assertEqual(ctor.get("timeout"), OPENAI_TIMEOUT_DEFAULT_SECONDS)

    def test_transient_failure_then_success_reports_two_attempts(self):
        from backend.core.openai_analyzer import analyze_quote_openai

        with patched_openai([openai_exc("timeout"), valid_response()]) as (cm, _):
            result, _latency, attempts = analyze_quote_openai(
                quote_text="a quote", request_id="rid-1"
            )
        self.assertIsInstance(result, QuoteCheckResult)
        self.assertEqual(cm.call_count, 2)
        self.assertEqual(attempts, 2)

    def test_two_transient_failures_stop_after_exactly_two(self):
        from backend.core.openai_analyzer import analyze_quote_openai

        side = [openai_exc("connection"), openai_exc("connection"), valid_response()]
        with patched_openai(side) as (cm, _):
            with self.assertRaises(QuoteCheckError) as ctx:
                analyze_quote_openai(quote_text="a quote", request_id="rid-1")
        self.assertEqual(cm.call_count, 2)
        self.assertEqual(ctx.exception.category, FailureCategory.PROVIDER_UNAVAILABLE)
        self.assertEqual(ctx.exception.provider_attempts, 2)

    def test_rate_limit_makes_exactly_one_call_and_is_not_retried(self):
        from backend.core.openai_analyzer import analyze_quote_openai

        with patched_openai([openai_exc("rate_limit"), valid_response()]) as (cm, _):
            with self.assertRaises(QuoteCheckError) as ctx:
                analyze_quote_openai(quote_text="a quote", request_id="rid-1")
        self.assertEqual(cm.call_count, 1)
        self.assertEqual(ctx.exception.category, FailureCategory.PROVIDER_RATE_LIMITED)
        self.assertEqual(ctx.exception.provider_status, 429)
        self.assertEqual(ctx.exception.provider_request_id, "req_openai_rl")
        self.assertEqual(ctx.exception.provider_attempts, 1)

    def test_terminal_failure_makes_exactly_one_call(self):
        from backend.core.openai_analyzer import analyze_quote_openai

        with patched_openai([openai_exc("auth"), valid_response()]) as (cm, _):
            with self.assertRaises(QuoteCheckError) as ctx:
                analyze_quote_openai(quote_text="a quote", request_id="rid-1")
        self.assertEqual(cm.call_count, 1)
        self.assertEqual(ctx.exception.category, FailureCategory.CONFIGURATION_ERROR)

    def test_refusal_incomplete_invalid_each_make_one_call(self):
        from backend.core.openai_analyzer import analyze_quote_openai

        for resp in (refusal_response(), incomplete_response(), fake_response(output_text="")):
            with patched_openai([resp, valid_response()]) as (cm, _):
                with self.assertRaises(QuoteCheckError):
                    analyze_quote_openai(quote_text="a quote", request_id="rid-1")
            self.assertEqual(cm.call_count, 1)

    def test_max_attempts_constant_is_two(self):
        self.assertEqual(OPENAI_MAX_ATTEMPTS, 2)


# --------------------------------------------------------------------------- #
# 14: fallback boundary
# --------------------------------------------------------------------------- #

class NoDemoFallbackTests(unittest.TestCase):
    def test_openai_failure_never_calls_stub_for_any_category(self):
        stub = mock.MagicMock()
        for category in FailureCategory:
            def _raise(*_a, **_k):
                raise QuoteCheckError(category)

            with openai_mode_app() as appmod, \
                 mock.patch.object(appmod, "analyze_quote_stub", stub), \
                 mock.patch.object(appmod, "analyze_quote_openai", _raise):
                TestClient(appmod.app).post("/analyze", json={"quote_text": "a quote"})
        stub.assert_not_called()

    def test_stub_not_called_when_provider_boundary_raises(self):
        stub = mock.MagicMock()
        with openai_mode_app() as appmod, \
             mock.patch.object(appmod, "analyze_quote_stub", stub), \
             patched_openai([openai_exc("timeout"), openai_exc("timeout")]):
            r = TestClient(appmod.app).post("/analyze", json={"quote_text": "a quote"})
        self.assertEqual(r.status_code, 504)
        stub.assert_not_called()


# --------------------------------------------------------------------------- #
# 15-17: route / API error contract
# --------------------------------------------------------------------------- #

_ROUTE_CASES = [
    (FailureCategory.PROVIDER_TIMEOUT, 504, True),
    (FailureCategory.PROVIDER_UNAVAILABLE, 503, True),
    (FailureCategory.PROVIDER_RATE_LIMITED, 429, True),
    (FailureCategory.PROVIDER_REFUSAL, 502, False),
    (FailureCategory.PROVIDER_INCOMPLETE_RESPONSE, 502, True),
    (FailureCategory.INVALID_MODEL_OUTPUT, 502, False),
    (FailureCategory.CONFIGURATION_ERROR, 503, False),
    (FailureCategory.INTERNAL_ERROR, 500, False),
]


class RouteErrorContractTests(unittest.TestCase):
    def _post_raising(self, exc):
        def _raise(*_a, **_k):
            raise exc

        with openai_mode_app() as appmod, \
             mock.patch.object(appmod, "analyze_quote_openai", _raise):
            return TestClient(appmod.app).post("/analyze", json={"quote_text": "a quote"})

    def test_category_maps_to_status_and_body_shape(self):
        for category, status, retryable in _ROUTE_CASES:
            with self.subTest(category=category):
                r = self._post_raising(QuoteCheckError(category))
                self.assertEqual(r.status_code, status)
                body = r.json()
                self.assertEqual(set(body), {"detail"})
                detail = body["detail"]
                self.assertEqual(set(detail), {"code", "message", "retryable", "request_id"})
                self.assertEqual(detail["code"], category.value)
                self.assertEqual(detail["retryable"], retryable)
                self.assertTrue(detail["message"])
                self.assertTrue(detail["request_id"])

    def test_unclassified_exception_becomes_internal_error_500(self):
        r = self._post_raising(RuntimeError("unexpected"))
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json()["detail"]["code"], "internal_error")

    def test_raw_exception_detail_not_exposed(self):
        secret = "sk-live-SECRET-abc123 stacktrace file /app/backend/x.py"
        r = self._post_raising(
            QuoteCheckError(FailureCategory.PROVIDER_UNAVAILABLE, cause=Exception(secret))
        )
        self.assertNotIn("SECRET", r.text)
        self.assertNotIn("stacktrace", r.text)
        self.assertNotIn("backend/x.py", r.text)
        self.assertEqual(r.json()["detail"]["message"],
                         QuoteCheckError(FailureCategory.PROVIDER_UNAVAILABLE).user_message)

    def test_request_id_preserved_when_error_has_none(self):
        r = self._post_raising(QuoteCheckError(FailureCategory.PROVIDER_TIMEOUT))
        self.assertRegex(r.json()["detail"]["request_id"], r"[0-9a-f-]{36}")


# --------------------------------------------------------------------------- #
# 18-19: failure logging
# --------------------------------------------------------------------------- #

class FailureLoggingTests(unittest.TestCase):
    def test_failed_run_records_sanitized_classification_fields(self):
        err = QuoteCheckError(
            FailureCategory.PROVIDER_TIMEOUT,
            cause=openai_exc("timeout"),
            provider_attempts=2,
        )

        def _raise(*_a, **_k):
            raise err

        with tempfile.TemporaryDirectory() as td:
            logp = str(Path(td) / "runs.jsonl")
            with openai_mode_app(log_path=logp) as appmod, \
                 mock.patch.object(appmod, "analyze_quote_openai", _raise):
                r = TestClient(appmod.app).post("/analyze", json={"quote_text": "a quote"})
            rec = last_log_record(logp)

        self.assertEqual(r.status_code, 504)
        self.assertIs(rec["success"], False)
        self.assertEqual(rec["analyzer"], "openai")
        self.assertEqual(rec["failure_category"], "provider_timeout")
        self.assertIs(rec["retryable"], True)
        self.assertEqual(rec["cause_type"], "APITimeoutError")
        self.assertEqual(rec["provider_attempts"], 2)
        self.assertIs(rec["schema_valid"], False)
        self.assertTrue(rec["request_id"])
        self.assertEqual(rec["request_id"], r.json()["detail"]["request_id"])
        # `error` is bounded + application-authored, never the raw exception text.
        self.assertTrue(rec["error"].startswith("provider_timeout"))
        self.assertNotIn("timed out", rec["error"].lower())

    def test_observed_provider_attempts_from_real_loop(self):
        with tempfile.TemporaryDirectory() as td:
            logp = str(Path(td) / "runs.jsonl")
            with openai_mode_app(log_path=logp) as appmod, \
                 patched_openai([openai_exc("timeout"), openai_exc("timeout")]):
                TestClient(appmod.app).post("/analyze", json={"quote_text": "a quote"})
            rec = last_log_record(logp)
        self.assertEqual(rec["failure_category"], "provider_timeout")
        self.assertEqual(rec["provider_attempts"], 2)

    def test_logging_failure_does_not_mask_analysis_failure(self):
        def _raise(*_a, **_k):
            raise QuoteCheckError(FailureCategory.PROVIDER_TIMEOUT)

        with openai_mode_app() as appmod, \
             mock.patch.object(appmod, "analyze_quote_openai", _raise), \
             mock.patch.object(appmod, "log_app_run", side_effect=OSError("disk full")):
            r = TestClient(appmod.app).post("/analyze", json={"quote_text": "a quote"})
        self.assertEqual(r.status_code, 504)
        self.assertEqual(r.json()["detail"]["code"], "provider_timeout")


# --------------------------------------------------------------------------- #
# 20-21: existing behaviour preserved
# --------------------------------------------------------------------------- #

class ExistingBehaviourTests(unittest.TestCase):
    def test_valid_fake_openai_response_still_yields_quotecheck_result(self):
        with tempfile.TemporaryDirectory() as td:
            logp = str(Path(td) / "runs.jsonl")
            with openai_mode_app(log_path=logp) as appmod, \
                 patched_openai([valid_response()]):
                r = TestClient(appmod.app).post("/analyze", json={"quote_text": "a quote"})
            rec = last_log_record(logp)
        self.assertEqual(r.status_code, 200)
        QuoteCheckResult.model_validate(r.json())
        self.assertIs(rec["success"], True)
        self.assertEqual(rec["analyzer"], "openai")
        self.assertEqual(rec["provider_attempts"], 1)
        self.assertIsNone(rec["failure_category"])

    def test_demo_mode_unchanged(self):
        import backend.app as appmod

        with tempfile.TemporaryDirectory() as td:
            logp = str(Path(td) / "runs.jsonl")
            with mock.patch.object(appmod, "USE_OPENAI", False), \
                 mock.patch.object(appmod, "ANALYZER_NAME", "demo"), \
                 mock.patch.object(appmod, "APP_RUN_LOG_PATH", logp):
                r = TestClient(appmod.app).post(
                    "/analyze",
                    json={"quote_text": "Brake pads replacement. Shop supplies / misc charge."},
                )
            rec = last_log_record(logp)
        self.assertEqual(r.status_code, 200)
        QuoteCheckResult.model_validate(r.json())
        self.assertEqual(rec["analyzer"], "demo")
        self.assertIs(rec["success"], True)
        self.assertIsNone(rec["provider_attempts"])
        self.assertIsNone(rec["failure_category"])

    def test_stub_analyzer_source_untouched_marker(self):
        # QC-4 must not change Demo semantics; this only guards the import path
        # the reliability work relies on, not stub behaviour (see test_stub_analyzer.py).
        from backend.core.stub_analyzer import analyze_quote_stub

        result = analyze_quote_stub(quote_text="A plain quote.", request_id="r", latency_ms=0)
        self.assertIsInstance(result, QuoteCheckResult)


# --------------------------------------------------------------------------- #
# Timeout budget alignment (frontend vs backend)
# --------------------------------------------------------------------------- #

class TimeoutBudgetTests(unittest.TestCase):
    def test_frontend_request_timeout_exceeds_backend_provider_budget(self):
        app_jsx = (REPO_ROOT / "frontend" / "src" / "App.jsx").read_text()
        m = re.search(r"REQUEST_TIMEOUT_MS\s*=\s*([\d_]+)", app_jsx)
        self.assertIsNotNone(m, "REQUEST_TIMEOUT_MS not found in App.jsx")
        frontend_ms = int(m.group(1).replace("_", ""))
        backend_budget_ms = 1000 * OPENAI_MAX_ATTEMPTS * OPENAI_TIMEOUT_DEFAULT_SECONDS
        self.assertGreater(
            frontend_ms,
            backend_budget_ms,
            "frontend abort must sit above the documented backend provider-call budget",
        )


if __name__ == "__main__":
    unittest.main()
