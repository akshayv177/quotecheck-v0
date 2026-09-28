"""SCALE-004 provider admission control: deterministic tests.

Concurrency is driven with explicit synchronization, never with sleeps or
latency thresholds. Requests run as concurrent tasks on one event loop through
``httpx.ASGITransport``; the fake provider blocks its worker thread on a
``threading.Event`` gate that the test opens. ``asyncio.wait_for(..., 10)`` is
only a deadlock guard, so a regression fails instead of hanging.

The key ordering argument: a rejected request's full response is awaited while
the admitted provider calls are still provably blocked on the closed gate, so
the rejection cannot have waited for them.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import anyio.to_thread
import httpx

from backend.core import admission as admission_mod
from backend.core.admission import ProviderAdmission
from backend.core.config import OPENAI_MAX_ATTEMPTS, OPENAI_MAX_CONCURRENT_ANALYSES
from backend.core.errors import FailureCategory, QuoteCheckError
from eval.tests.test_openai_reliability import (
    fake_response,
    incomplete_response,
    openai_exc,
    openai_mode_app,
    patched_openai,
    refusal_response,
    valid_response,
)

GUARD_S = 10.0
QUOTE = {"quote_text": "Replace brake pads: $240. Shop supplies: $35."}
REJECTION_KEYS = {"code", "message", "retryable", "request_id"}


class BlockingProvider:
    """Callable stand-in for ``client.responses.create``.

    Call ``n`` (1-based) first blocks on ``gate`` if ``n`` is in ``block``, then
    returns or raises ``script[n-1]`` (``valid_response()`` past the script's end).
    """

    def __init__(self, script=(), block=()):
        self.script = list(script)
        self.block = set(block)
        self.gate = threading.Event()
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, *_a, **_k):
        with self._lock:
            self.calls += 1
            n = self.calls
        if n in self.block:
            self.gate.wait(GUARD_S)
        outcome = self.script[n - 1] if n <= len(self.script) else valid_response()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def wait_calls(self, k: int) -> None:
        async def _poll():
            while self.calls < k:
                await asyncio.sleep(0.001)
        await asyncio.wait_for(_poll(), GUARD_S)


def log_records(path: str) -> list[dict]:
    p = Path(path)
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


class AdmissionRouteTestBase(unittest.IsolatedAsyncioTestCase):
    """OpenAI mode, a fresh ``ProviderAdmission(capacity)``, a temp run log."""

    @contextlib.contextmanager
    def openai_app(self, capacity: int, provider=None, **patch_kw):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)  # the log stays readable after the context exits
        self.log_path = str(Path(td.name) / "runs.jsonl")
        adm = ProviderAdmission(capacity)
        with contextlib.ExitStack() as es:
            appmod = es.enter_context(openai_mode_app(log_path=self.log_path))
            es.enter_context(mock.patch.object(appmod, "provider_admission", adm))
            create = None
            if provider is not None:
                create, _ = es.enter_context(patched_openai(provider, **patch_kw))
            if isinstance(provider, BlockingProvider):
                es.callback(provider.gate.set)  # never leave a worker thread parked
            self.appmod, self.adm = appmod, adm
            yield appmod, adm, create

    async def post(self):
        transport = httpx.ASGITransport(app=self.appmod.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://qc") as client:
            return await client.post("/analyze", json=QUOTE)

    def assert_rejection(self, r):
        self.assertEqual(r.status_code, 503)
        self.assertEqual(set(r.json()), {"detail"})
        d = r.json()["detail"]
        self.assertEqual(set(d), REJECTION_KEYS)
        self.assertEqual(d["code"], "capacity_exceeded")
        self.assertIs(d["retryable"], True)
        self.assertRegex(d["request_id"], r"^[0-9a-f-]{36}$")
        return d


# --------------------------------------------------------------------------- #
# Admission cap and fail-fast
# --------------------------------------------------------------------------- #

class AdmissionCapTests(AdmissionRouteTestBase):
    async def test_cap_rejects_excess_immediately_with_zero_provider_calls(self):
        prov = BlockingProvider(block={1, 2})
        with self.openai_app(2, prov):
            a = asyncio.create_task(self.post())
            b = asyncio.create_task(self.post())
            await prov.wait_calls(2)
            self.assertEqual(self.adm.in_flight, 2)

            # Fail-fast: the third response arrives while both admitted calls are
            # still parked on the closed gate.
            rc = await asyncio.wait_for(self.post(), GUARD_S)
            self.assertFalse(prov.gate.is_set())
            self.assert_rejection(rc)
            self.assertEqual(prov.calls, 2)  # the rejected request made no call

            prov.gate.set()
            ra, rb = await asyncio.wait_for(asyncio.gather(a, b), GUARD_S)
            self.assertEqual((ra.status_code, rb.status_code), (200, 200))
            self.assertEqual(self.adm.in_flight, 0)

            # Capacity is back: the next request is admitted and reaches the provider.
            rd = await asyncio.wait_for(self.post(), GUARD_S)
            self.assertEqual(rd.status_code, 200)
            self.assertEqual(prov.calls, 3)
            self.assertEqual(self.adm.in_flight, 0)

    async def test_rejection_needs_no_worker_token(self):
        """With the anyio default limiter fully borrowed, a rejection still completes,
        so neither the admission check nor the error handler uses the threadpool."""
        prov = BlockingProvider(block={1})
        with self.openai_app(1, prov):
            a = asyncio.create_task(self.post())
            await prov.wait_calls(1)
            limiter = anyio.to_thread.current_default_thread_limiter()
            original = limiter.total_tokens
            try:
                limiter.total_tokens = limiter.borrowed_tokens  # zero tokens available
                self.assertEqual(limiter.available_tokens, 0)
                rc = await asyncio.wait_for(self.post(), GUARD_S)
                self.assert_rejection(rc)
            finally:
                limiter.total_tokens = original
            self.assertEqual(anyio.to_thread.current_default_thread_limiter().total_tokens,
                             original)
            prov.gate.set()
            ra = await asyncio.wait_for(a, GUARD_S)
            self.assertEqual(ra.status_code, 200)
            self.assertEqual(self.adm.in_flight, 0)


# --------------------------------------------------------------------------- #
# Retry accounting
# --------------------------------------------------------------------------- #

class RetryInsideOneSlotTests(AdmissionRouteTestBase):
    async def test_transient_retry_stays_in_the_original_slot(self):
        prov = BlockingProvider(script=[openai_exc("connection"), valid_response()],
                                block={2})
        with self.openai_app(1, prov):
            a = asyncio.create_task(self.post())
            await prov.wait_calls(2)  # the first attempt failed; the retry is parked
            self.assertEqual(self.adm.in_flight, 1)

            rb = await asyncio.wait_for(self.post(), GUARD_S)
            self.assert_rejection(rb)
            self.assertEqual(prov.calls, 2)

            prov.gate.set()
            ra = await asyncio.wait_for(a, GUARD_S)
            self.assertEqual(ra.status_code, 200)
            self.assertEqual(self.adm.in_flight, 0)
        by_id = {r["request_id"]: r for r in log_records(self.log_path)}
        rec = by_id[ra.json()["metadata"]["request_id"]]
        self.assertEqual(rec["provider_attempts"], OPENAI_MAX_ATTEMPTS)
        self.assertEqual(by_id[rb.json()["detail"]["request_id"]]["provider_attempts"], 0)


# --------------------------------------------------------------------------- #
# Release on every terminal path
# --------------------------------------------------------------------------- #

_TERMINAL_CASES = [
    ("success", [valid_response()], {}, 200, None),
    ("timeout_x2", [openai_exc("timeout"), openai_exc("timeout")], {}, 504, "provider_timeout"),
    ("unavailable_x2", [openai_exc("connection"), openai_exc("server")], {}, 503,
     "provider_unavailable"),
    ("rate_limited", [openai_exc("rate_limit")], {}, 429, "provider_rate_limited"),
    ("auth_config", [openai_exc("auth")], {}, 503, "configuration_error"),
    ("refusal", [refusal_response()], {}, 502, "provider_refusal"),
    ("incomplete", [incomplete_response()], {}, 502, "provider_incomplete_response"),
    ("not_json", [fake_response(output_text="not json")], {}, 502, "invalid_model_output"),
    ("schema_invalid", [fake_response(output_text='{"x": 1}')], {}, 502,
     "invalid_model_output"),
    ("missing_key", [], {"api_key": None}, 503, "configuration_error"),
]


class ReleaseOnEveryPathTests(AdmissionRouteTestBase):
    async def test_every_terminal_path_releases_its_slot(self):
        for name, script, kw, status, code in _TERMINAL_CASES:
            with self.subTest(case=name):
                with self.openai_app(1, list(script) or [valid_response()], **kw) as (_, adm, create):
                    r = await asyncio.wait_for(self.post(), GUARD_S)
                    self.assertEqual(r.status_code, status)
                    if code:
                        self.assertEqual(r.json()["detail"]["code"], code)
                    self.assertEqual(adm.in_flight, 0)
                    # A leaked slot would make this capacity_exceeded (capacity 1).
                    create.side_effect = [valid_response()]
                    r2 = await asyncio.wait_for(self.post(), GUARD_S)
                    self.assertNotEqual(r2.json().get("detail", {}).get("code"),
                                        "capacity_exceeded")
                    self.assertEqual(adm.in_flight, 0)

    async def test_unexpected_exception_releases_its_slot(self):
        def _boom(*_a, **_k):
            raise RuntimeError("unexpected")

        with self.openai_app(1) as (appmod, adm, _):
            with mock.patch.object(appmod, "analyze_quote_openai", _boom):
                r = await asyncio.wait_for(self.post(), GUARD_S)
                self.assertEqual(r.status_code, 500)
                self.assertEqual(r.json()["detail"]["code"], "internal_error")
                self.assertEqual(adm.in_flight, 0)
                r2 = await asyncio.wait_for(self.post(), GUARD_S)
                self.assertEqual(r2.json()["detail"]["code"], "internal_error")
                self.assertEqual(adm.in_flight, 0)

    async def test_cancelled_request_holds_its_slot_until_the_thread_finishes(self):
        """A natively cancelled request task stops waiting, but the slot is only
        released once the provider call has actually returned."""
        prov = BlockingProvider(block={1})
        with self.openai_app(1, prov):
            a = asyncio.create_task(self.post())
            await prov.wait_calls(1)
            a.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(a, GUARD_S)
            self.assertEqual(self.adm.in_flight, 1)  # provider call still parked
            self.assert_rejection(await asyncio.wait_for(self.post(), GUARD_S))

            prov.gate.set()

            async def _released():
                while self.adm.in_flight:
                    await asyncio.sleep(0.001)
            await asyncio.wait_for(_released(), GUARD_S)
            r = await asyncio.wait_for(self.post(), GUARD_S)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(prov.calls, 2)


# --------------------------------------------------------------------------- #
# Demo isolation
# --------------------------------------------------------------------------- #

class DemoIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_demo_requests_never_touch_the_provider_budget(self):
        import backend.app as appmod
        from backend.core import openai_analyzer

        exhausted = ProviderAdmission(0)  # would reject every OpenAI-mode request
        ctor = mock.MagicMock()
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(appmod, "USE_OPENAI", False), \
             mock.patch.object(appmod, "ANALYZER_NAME", "demo"), \
             mock.patch.object(appmod, "APP_RUN_LOG_PATH", str(Path(td) / "runs.jsonl")), \
             mock.patch.object(appmod, "provider_admission", exhausted), \
             mock.patch.object(exhausted, "try_acquire", wraps=exhausted.try_acquire) as spy, \
             mock.patch.object(openai_analyzer, "OpenAI", ctor), \
             mock.patch.object(openai_analyzer, "_client", None):
            transport = httpx.ASGITransport(app=appmod.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://qc") as client:
                rs = await asyncio.wait_for(asyncio.gather(
                    *(client.post("/analyze", json=QUOTE) for _ in range(20))), GUARD_S)
            recs = log_records(str(Path(td) / "runs.jsonl"))
        self.assertTrue(all(r.status_code == 200 for r in rs))
        self.assertTrue(all(r.json()["metadata"]["model"] == "quotecheck-demo-analyzer"
                            for r in rs))
        spy.assert_not_called()
        ctor.assert_not_called()
        self.assertEqual(exhausted.in_flight, 0)
        self.assertEqual(len(recs), 20)
        self.assertTrue(all(r["analyzer"] == "demo" and r["success"] for r in recs))


# --------------------------------------------------------------------------- #
# API and log contract of a rejection
# --------------------------------------------------------------------------- #

class RejectionContractTests(AdmissionRouteTestBase):
    async def test_rejection_body_and_single_sanitized_log_record(self):
        with self.openai_app(0, [valid_response()]) as (_, adm, create):
            r = await asyncio.wait_for(self.post(), GUARD_S)
            create.assert_not_called()
        d = self.assert_rejection(r)
        self.assertEqual(d["message"], QuoteCheckError(FailureCategory.CAPACITY_EXCEEDED).user_message)
        # Distinct from both upstream conditions it could be confused with.
        for upstream in (FailureCategory.PROVIDER_RATE_LIMITED,
                         FailureCategory.PROVIDER_UNAVAILABLE):
            e = QuoteCheckError(upstream)
            self.assertNotEqual(d["code"], upstream.value)
            self.assertNotEqual(d["message"], e.user_message)
        self.assertNotEqual(r.status_code, QuoteCheckError(
            FailureCategory.PROVIDER_RATE_LIMITED).http_status)

        recs = log_records(self.log_path)
        self.assertEqual(len(recs), 1)
        rec = recs[0]
        self.assertEqual(rec["request_id"], d["request_id"])
        self.assertEqual(rec["analyzer"], "openai")
        self.assertIs(rec["success"], False)
        self.assertIs(rec["schema_valid"], False)
        self.assertEqual(rec["failure_category"], "capacity_exceeded")
        self.assertIs(rec["retryable"], True)
        self.assertEqual(rec["provider_attempts"], 0)
        for k in ("cause_type", "provider_status", "provider_request_id",
                  "response_status", "incomplete_reason"):
            self.assertIsNone(rec[k], k)
        self.assertEqual(rec["error"],
                         "capacity_exceeded: provider admission budget full (0/0 in flight)")
        self.assertNotIn(QUOTE["quote_text"], json.dumps(rec))
        self.assertNotIn("brake", json.dumps(rec))

    async def test_invalid_request_is_rejected_before_admission(self):
        with self.openai_app(1, [valid_response()]) as (_, adm, create):
            with mock.patch.object(adm, "try_acquire", wraps=adm.try_acquire) as spy:
                transport = httpx.ASGITransport(app=self.appmod.app)
                async with httpx.AsyncClient(transport=transport, base_url="http://qc") as c:
                    r = await c.post("/analyze", json={"nope": 1})
            self.assertEqual(r.status_code, 422)
            spy.assert_not_called()
            self.assertEqual(adm.in_flight, 0)


# --------------------------------------------------------------------------- #
# The primitive and the budget constant
# --------------------------------------------------------------------------- #

class ProviderAdmissionUnitTests(unittest.TestCase):
    def test_accounting_and_underflow(self):
        adm = ProviderAdmission(2)
        self.assertTrue(adm.try_acquire())
        self.assertTrue(adm.try_acquire())
        self.assertFalse(adm.try_acquire())
        self.assertEqual(adm.in_flight, 2)
        adm.release()
        self.assertTrue(adm.try_acquire())
        adm.release()
        adm.release()
        self.assertEqual(adm.in_flight, 0)
        with self.assertRaises(RuntimeError):
            adm.release()
        with self.assertRaises(ValueError):
            ProviderAdmission(-1)

    def test_concurrent_try_acquire_admits_exactly_capacity(self):
        adm = ProviderAdmission(8)
        n = 50
        barrier = threading.Barrier(n)
        wins = []
        lock = threading.Lock()

        def contend():
            barrier.wait()
            ok = adm.try_acquire()
            with lock:
                wins.append(ok)

        threads = [threading.Thread(target=contend) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(GUARD_S)
        self.assertEqual(sum(wins), 8)
        self.assertEqual(adm.in_flight, 8)

    def test_budget_constant_is_named_32_and_process_instance_uses_it(self):
        self.assertEqual(OPENAI_MAX_CONCURRENT_ANALYSES, 32)
        self.assertEqual(admission_mod.provider_admission.capacity,
                         OPENAI_MAX_CONCURRENT_ANALYSES)

    def test_budget_is_below_the_anyio_default_worker_limit(self):
        """Admitted provider-bound work must leave worker tokens for /health and
        other synchronous handlers; a budget >= the limiter would silently undo that."""
        async def tokens():
            return anyio.to_thread.current_default_thread_limiter().total_tokens

        self.assertLess(OPENAI_MAX_CONCURRENT_ANALYSES, anyio.run(tokens))
        self.assertGreaterEqual(OPENAI_MAX_CONCURRENT_ANALYSES, 1)


if __name__ == "__main__":
    unittest.main()
