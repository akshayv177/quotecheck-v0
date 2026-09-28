"""SCALE-001 benchmark-tooling tests.

Covers the harness's own correctness, not QuoteCheck capacity: percentile maths,
fail-closed environment construction, concurrency-safe fake-provider counters,
the deterministic retry-injection mode, and that the real openai SDK plus the
real ``/analyze`` path accept the fake provider's responses.

Everything is loopback-only; no provider cost, no public host.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.core.schema import MAX_QUOTE_TEXT_CHARS, QuoteCheckResult
from benchmarks import stats
from benchmarks.fake_provider import FakeProviderServer, FakeProviderState
from benchmarks.run_capacity import (
    SENTINEL_API_KEY,
    SENTINEL_MODEL,
    assert_loopback_url,
    build_child_env,
    run_load,
)
from benchmarks.workloads import WORKLOADS
from eval.tests.test_openai_reliability import last_log_record, openai_mode_app


@contextlib.contextmanager
def fake_server(**kw):
    srv = FakeProviderServer(0, **kw)
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


class PercentileTests(unittest.TestCase):
    def test_nearest_rank_on_1_to_100(self):
        vals = list(range(1, 101))
        self.assertEqual(stats.nearest_rank(vals, 50), 50)
        self.assertEqual(stats.nearest_rank(vals, 95), 95)
        self.assertEqual(stats.nearest_rank(vals, 100), 100)

    def test_nearest_rank_small_sample_returns_observed_value(self):
        vals = [0.1, 0.2, 0.3]
        self.assertEqual(stats.nearest_rank(vals, 50), 0.2)
        self.assertEqual(stats.nearest_rank(vals, 95), 0.3)

    def test_nearest_rank_rejects_empty_and_bad_p(self):
        with self.assertRaises(ValueError):
            stats.nearest_rank([], 50)
        with self.assertRaises(ValueError):
            stats.nearest_rank([1], 0)

    def test_p99_only_with_enough_samples(self):
        self.assertNotIn("p99_ms", stats.latency_summary([0.01] * (stats.P99_MIN_SAMPLES - 1)))
        self.assertIn("p99_ms", stats.latency_summary([0.01] * stats.P99_MIN_SAMPLES))

    def test_summarize_pools_trials_and_computes_throughput(self):
        key = {"experiment": "e", "scenario": "s", "workload_id": "w", "concurrency": 2}
        reqs, trials = [], []
        for trial in (1, 2):
            for i in range(4):
                reqs.append({**key, "trial": trial, "request_index": i,
                             "duration_s": 0.1 * (i + 1), "success": i != 3,
                             "http_status": 200 if i != 3 else 503})
            trials.append({**key, "trial": trial, "wall_s": 1.5, "requests_planned": 4})
        [row] = stats.summarize(reqs, trials)
        self.assertEqual(row["trials"], 2)
        self.assertEqual(row["requests_total"], 8)
        self.assertEqual(row["successes"], 6)
        self.assertEqual(row["failures"], 2)
        self.assertEqual(row["http_status_counts"], {"200": 6, "503": 2})
        self.assertEqual(row["throughput_rps_mean"], 2.0)  # 3 ok / 1.5 s
        self.assertEqual(row["pooled_latency"]["p50_ms"], 200.0)
        self.assertEqual(row["pooled_latency"]["max_ms"], 400.0)


class SafetyTests(unittest.TestCase):
    def test_loopback_guard(self):
        assert_loopback_url("http://127.0.0.1:1234/v1")
        assert_loopback_url("http://localhost:1234/v1")
        for bad in ("https://api.openai.com/v1",
                    "https://quotecheck-v0-production.up.railway.app",
                    "http://10.0.0.5/v1"):
            with self.assertRaises(RuntimeError):
                assert_loopback_url(bad)

    def test_child_env_strips_and_overrides(self):
        parent = {"PATH": "/bin", "OPENAI_API_KEY": "sk-real-looking", "OPENAI_ORG_ID": "org",
                  "HTTPS_PROXY": "http://proxy:1", "http_proxy": "http://proxy:2",
                  "QUOTECHECK_ALLOWED_ORIGINS": "https://x.app", "QUOTECHECK_USE_OPENAI": "1"}
        env = build_child_env(use_openai=True, log_path=Path("/tmp/x.jsonl"),
                              base_url="http://127.0.0.1:5555/v1", parent_env=parent)
        self.assertEqual(env["OPENAI_API_KEY"], SENTINEL_API_KEY)
        self.assertEqual(env["QUOTECHECK_MODEL"], SENTINEL_MODEL)
        self.assertEqual(env["OPENAI_BASE_URL"], "http://127.0.0.1:5555/v1")
        self.assertEqual(env["QUOTECHECK_LOG_PATH"], "/tmp/x.jsonl")
        self.assertNotIn("OPENAI_ORG_ID", env)
        self.assertNotIn("HTTPS_PROXY", env)
        self.assertNotIn("http_proxy", env)
        self.assertNotIn("QUOTECHECK_ALLOWED_ORIGINS", env)
        self.assertEqual(env["PATH"], "/bin")

    def test_child_env_demo_mode_and_refusals(self):
        env = build_child_env(use_openai=False, log_path=Path("/tmp/x.jsonl"), parent_env={})
        self.assertEqual(env["QUOTECHECK_USE_OPENAI"], "0")
        with self.assertRaises(RuntimeError):
            build_child_env(use_openai=True, log_path=Path("/tmp/x"), parent_env={})
        with self.assertRaises(RuntimeError):
            build_child_env(use_openai=True, log_path=Path("/tmp/x"), parent_env={},
                            base_url="https://api.openai.com/v1")


class WorkloadTests(unittest.TestCase):
    def test_workloads_are_fixed_and_within_limit(self):
        self.assertEqual(set(WORKLOADS), {"short", "normal", "near_max"})
        self.assertLess(WORKLOADS["short"].chars, WORKLOADS["normal"].chars)
        self.assertGreater(WORKLOADS["near_max"].chars, 0.9 * MAX_QUOTE_TEXT_CHARS)
        self.assertLessEqual(WORKLOADS["near_max"].chars, MAX_QUOTE_TEXT_CHARS)
        self.assertEqual(
            WORKLOADS["normal"].sha256,
            "513db206707c339d80e822a73466b45ed5cf923dc802af4166f951338bf1a5f4",
            "normal workload text changed; bump fixtures deliberately, never silently",
        )


class FakeProviderCounterTests(unittest.TestCase):
    def test_concurrent_begin_end_is_consistent(self):
        state = FakeProviderState(latency_s=0)
        n = 24
        barrier = threading.Barrier(n)

        def work():
            state.begin()
            barrier.wait()  # all n are in flight simultaneously here
            state.end()

        threads = [threading.Thread(target=work) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        snap = state.snapshot()
        self.assertEqual(snap["peak_in_flight"], n)
        self.assertEqual(snap["attempts_started"], n)
        self.assertEqual(snap["attempts_completed"], n)
        self.assertEqual(snap["in_flight"], 0)

    def test_fail_first_is_deterministic_per_marker(self):
        state = FakeProviderState(latency_s=0, mode="fail_first")
        self.assertTrue(state.should_fail("a"))
        self.assertFalse(state.should_fail("a"))
        self.assertTrue(state.should_fail("b"))
        self.assertFalse(state.should_fail(None))
        self.assertEqual(state.snapshot()["injected_failures"], 2)

    def test_fail_always_and_success(self):
        self.assertTrue(FakeProviderState(latency_s=0, mode="fail_always").should_fail("x"))
        self.assertFalse(FakeProviderState(latency_s=0, mode="success").should_fail("x"))
        with self.assertRaises(ValueError):
            FakeProviderState(latency_s=0, mode="nope")


class FakeProviderSdkTests(unittest.TestCase):
    """The real openai SDK (the one QuoteCheck uses) parses the fake's responses."""

    def test_sdk_parses_valid_quotecheck_result(self):
        from openai import OpenAI

        with fake_server(latency_s=0) as srv:
            client = OpenAI(api_key=SENTINEL_API_KEY, max_retries=0, timeout=5,
                            base_url=f"http://127.0.0.1:{srv.server_address[1]}/v1")
            resp = client.responses.create(model=SENTINEL_MODEL, input=[{"role": "user",
                                                                         "content": "q"}])
            QuoteCheckResult.model_validate(json.loads(resp.output_text))
            self.assertEqual(srv.state.snapshot()["attempts_started"], 1)

    def test_injected_failure_is_a_transient_sdk_error(self):
        from openai import OpenAI

        from backend.core.errors import is_transient_openai_exception

        with fake_server(latency_s=0, mode="fail_always") as srv:
            client = OpenAI(api_key=SENTINEL_API_KEY, max_retries=0, timeout=5,
                            base_url=f"http://127.0.0.1:{srv.server_address[1]}/v1")
            with self.assertRaises(Exception) as ctx:
                client.responses.create(model=SENTINEL_MODEL, input="q")
            self.assertTrue(is_transient_openai_exception(ctx.exception))


class AnalyzePathAgainstFakeTests(unittest.TestCase):
    """Real /analyze -> real analyzer -> real SDK -> loopback fake (in-process app)."""

    def _post(self, srv, text):
        base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
        with tempfile.TemporaryDirectory() as td:
            logp = str(Path(td) / "runs.jsonl")
            with mock.patch.dict(os.environ, {"OPENAI_BASE_URL": base}), \
                 openai_mode_app(log_path=logp), \
                 mock.patch("backend.core.openai_analyzer.OPENAI_API_KEY", SENTINEL_API_KEY):
                import backend.app as appmod

                r = TestClient(appmod.app).post("/analyze", json={"quote_text": text})
            return r, last_log_record(logp)

    def test_success_one_attempt(self):
        with fake_server(latency_s=0) as srv:
            r, rec = self._post(srv, WORKLOADS["normal"].text)
        self.assertEqual(r.status_code, 200)
        QuoteCheckResult.model_validate(r.json())
        self.assertEqual(rec["analyzer"], "openai")
        self.assertEqual(rec["provider_attempts"], 1)
        self.assertEqual(srv.state.snapshot()["attempts_started"], 1)

    def test_fail_first_retries_once_then_succeeds(self):
        with fake_server(latency_s=0, mode="fail_first") as srv:
            r, rec = self._post(srv, WORKLOADS["normal"].text + "\n[bench-marker:t1]")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(rec["provider_attempts"], 2)
        snap = srv.state.snapshot()
        self.assertEqual(snap["attempts_started"], 2)
        self.assertEqual(snap["injected_failures"], 1)

    def test_fail_always_stops_at_two_attempts(self):
        with fake_server(latency_s=0, mode="fail_always") as srv:
            r, rec = self._post(srv, WORKLOADS["normal"].text)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"]["code"], "provider_unavailable")
        self.assertEqual(rec["provider_attempts"], 2)
        self.assertEqual(srv.state.snapshot()["attempts_started"], 2)


class LoadClientTests(unittest.TestCase):
    def test_run_load_issues_exactly_n_and_records_timings(self):
        with fake_server(latency_s=0.02) as srv:
            port = srv.server_address[1]
            recs, wall = run_load(port, method="GET", path="/__stats", bodies=[None] * 12,
                                  concurrency=4)
        self.assertEqual(len(recs), 12)
        self.assertEqual(sorted(r["request_index"] for r in recs), list(range(12)))
        self.assertTrue(all(r["success"] and r["duration_s"] >= 0 for r in recs))
        self.assertGreaterEqual(wall, max(r["t_end_s"] for r in recs) - 1e-6)


if __name__ == "__main__":
    unittest.main()
