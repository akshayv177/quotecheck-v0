"""SCALE-001 benchmark-tooling tests (extended in SCALE-003).

Covers the harness's own correctness, not QuoteCheck capacity: percentile maths,
fail-closed environment construction, concurrency-safe fake-provider counters,
the deterministic retry-injection mode, and that the real openai SDK plus the
real ``/analyze`` path accept the fake provider's responses.

Everything is loopback-only; no provider cost, no public host.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.core.config import OPENAI_TIMEOUT_DEFAULT_SECONDS
from backend.core.schema import MAX_QUOTE_TEXT_CHARS, QuoteCheckResult
from benchmarks import stats
from benchmarks.fake_provider import FakeProviderServer, FakeProviderState
from benchmarks.run_capacity import (
    SENTINEL_API_KEY,
    SENTINEL_MODEL,
    LazyBodies,
    assert_loopback_url,
    build_child_env,
    clocks_shared,
    run_load,
)
from benchmarks.workloads import WORKLOADS
from eval.tests.test_openai_reliability import isolated_shared_client, openai_mode_app


def _post_responses(conn: http.client.HTTPConnection, text: str) -> int:
    body = json.dumps({"model": SENTINEL_MODEL, "input": text}).encode()
    conn.request("POST", "/v1/responses", body=body, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp.read()
    return resp.status


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

    def _post_many(self, srv, texts, *, inspect_client=None):
        """POST each text in one cold shared-client context (SCALE-002); return
        ([responses], [log records]). The real SDK client built here is closed
        explicitly on exit by ``isolated_shared_client``."""
        base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
        with tempfile.TemporaryDirectory() as td:
            logp = str(Path(td) / "runs.jsonl")
            with isolated_shared_client() as analyzer, \
                 mock.patch.dict(os.environ, {"OPENAI_BASE_URL": base}), \
                 openai_mode_app(log_path=logp), \
                 mock.patch("backend.core.openai_analyzer.OPENAI_API_KEY", SENTINEL_API_KEY):
                import backend.app as appmod

                client = TestClient(appmod.app)
                rs = [client.post("/analyze", json={"quote_text": t}) for t in texts]
                if inspect_client is not None:
                    inspect_client(analyzer._client)
            recs = [json.loads(line) for line in Path(logp).read_text().splitlines()]
            return rs, recs

    def _post(self, srv, text):
        rs, recs = self._post_many(srv, [text])
        return rs[0], recs[-1]

    def test_shared_client_reuses_one_connection_across_requests(self):
        seen = {}

        def inspect(client):
            seen["client"] = client
            seen["max_retries"] = client.max_retries
            seen["timeout"] = client.timeout

        with fake_server(latency_s=0) as srv:
            rs, recs = self._post_many(srv, [WORKLOADS["normal"].text] * 3,
                                       inspect_client=inspect)
            snap = srv.state.snapshot()
        self.assertEqual([r.status_code for r in rs], [200, 200, 200])
        self.assertEqual([rec["provider_attempts"] for rec in recs], [1, 1, 1])
        self.assertEqual(snap["attempts_started"], 3)
        # One process-wide client -> one pooled keep-alive connection, not one per request.
        self.assertEqual(snap["connections_accepted"], 1)
        self.assertEqual(seen["max_retries"], 0)
        self.assertEqual(seen["timeout"], OPENAI_TIMEOUT_DEFAULT_SECONDS)
        self.assertTrue(seen["client"].is_closed(), "test cleanup must close the real client")

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


class FakeProviderTransportTests(unittest.TestCase):
    """SCALE-003 repair of the reused-connection Nagle artifact. Deterministic
    socket-option and reuse checks only; the latency effect is runtime evidence
    (``python -m benchmarks.diag_keepalive``), not a unit-test threshold."""

    def _accepted_nodelay(self, **kw) -> int:
        srv = FakeProviderServer(0, latency_s=0, output_text="{}", **kw)
        try:
            with socket.create_connection(srv.server_address, timeout=5):
                conn, _ = srv.get_request()
                try:
                    return conn.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
                finally:
                    conn.close()
        finally:
            srv.server_close()

    def test_accepted_sockets_have_tcp_nodelay(self):
        self.assertNotEqual(self._accepted_nodelay(), 0)

    def test_tcp_nodelay_can_be_disabled_for_the_diagnostic_only(self):
        self.assertEqual(self._accepted_nodelay(tcp_nodelay=False), 0)

    def test_persistent_connection_is_reused(self):
        with fake_server(latency_s=0) as srv:
            conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
            try:
                codes = [_post_responses(conn, f"q{i}") for i in range(5)]
            finally:
                conn.close()
            snap = srv.state.snapshot()
        self.assertEqual(codes, [200] * 5)
        self.assertEqual(snap["connections_accepted"], 1)
        self.assertEqual((snap["attempts_started"], snap["attempts_completed"]), (5, 5))


class FakeProviderAttemptLogTests(unittest.TestCase):
    def test_state_logs_marker_times_and_status(self):
        state = FakeProviderState(latency_s=0)
        seq = state.begin("m1")
        state.end(seq, 200)
        state.begin()          # SCALE-001 call shape still works
        state.end()
        a, b = state.attempts()
        self.assertEqual((a["seq"], a["marker"], a["status"]), (1, "m1", 200))
        self.assertLessEqual(a["t_start"], a["t_end"])
        self.assertEqual((b["marker"], b["t_end"]), (None, None))
        self.assertEqual(state.snapshot()["attempts_completed"], 2)
        state.reset()
        self.assertEqual(state.attempts(), [])

    def test_http_fail_first_attempts_are_logged_per_marker(self):
        with fake_server(latency_s=0, mode="fail_first") as srv:
            conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
            try:
                codes = [_post_responses(conn, "x [bench-marker:r1]"),
                         _post_responses(conn, "x [bench-marker:r1]"),
                         _post_responses(conn, "x [bench-marker:r2]")]
                conn.request("GET", "/__attempts")
                atts = json.loads(conn.getresponse().read())["attempts"]
            finally:
                conn.close()
            snap = srv.state.snapshot()
        self.assertEqual(codes, [503, 200, 503])
        self.assertEqual([(a["marker"], a["status"]) for a in atts],
                         [("r1", 503), ("r1", 200), ("r2", 503)])
        self.assertTrue(all(a["t_start"] <= a["t_end"] for a in atts))
        self.assertEqual(snap["injected_failures"], 2)
        self.assertEqual(snap["attempts_started"], len(atts))

    def test_clock_used_by_the_fake_is_the_harness_clock(self):
        # Linux: perf_counter and monotonic are both CLOCK_MONOTONIC.
        if not clocks_shared():
            self.skipTest("perf_counter/monotonic differ on this platform")
        self.assertTrue(clocks_shared())


class TimelineStatsTests(unittest.TestCase):
    IV = [(0.0, 2.0), (1.0, 3.0), (1.5, 2.5)]

    def test_in_flight_at_is_half_open(self):
        self.assertEqual(stats.in_flight_at(self.IV, 0.0), 1)
        self.assertEqual(stats.in_flight_at(self.IV, 1.75), 3)
        self.assertEqual(stats.in_flight_at(self.IV, 2.0), 2)
        self.assertEqual(stats.in_flight_at(self.IV, 3.0), 0)

    def test_mean_in_flight_and_time_at_level(self):
        # busy time 2 + 2 + 1 = 5 over [0, 4]
        self.assertAlmostEqual(stats.mean_in_flight(self.IV, 0.0, 4.0), 1.25)
        # >= 2 during [1, 2.5] -> 1.5 of 4; >= 3 during [1.5, 2] -> 0.5 of 4
        self.assertAlmostEqual(stats.time_frac_at_least(self.IV, 2, 0.0, 4.0), 0.375)
        self.assertAlmostEqual(stats.time_frac_at_least(self.IV, 3, 0.0, 4.0), 0.125)
        self.assertEqual(stats.time_frac_at_least(self.IV, 1, 5.0, 5.0), 0.0)

    def test_decompose_request_with_retry(self):
        atts = [{"t_start": 13.5, "t_end": 16.5}, {"t_start": 10.2, "t_end": 13.2}]
        d = stats.decompose_request(10.0, 17.0, atts)
        self.assertEqual(d["fake_attempts"], 2)
        self.assertAlmostEqual(d["pre_provider_s"], 0.2)
        self.assertAlmostEqual(d["provider_span_s"], 6.3)
        self.assertAlmostEqual(d["post_provider_s"], 0.5)
        self.assertAlmostEqual(d["inter_attempt_gap_s"], 0.3)
        self.assertEqual(stats.decompose_request(0, 1, []), {})
        self.assertEqual(stats.decompose_request(0, 1, [{"t_start": 0.1, "t_end": None}]), {})

    def test_summarize_health_reports_all_and_exact_saturated_subset(self):
        probes = [{"scenario": "h", "concurrency": 64, "probe_index": i,
                   "duration_s": d, "http_status": 200, "error_code": None,
                   "provider_in_flight_at_send": f, "analysis_outstanding_at_send": 64}
                  for i, (d, f) in enumerate([(1.0, 40), (2.0, 39), (3.0, 40)])]
        probes.append({"scenario": "h", "concurrency": 64, "probe_index": 3, "duration_s": 60.0,
                       "http_status": None, "error_code": "client_exception:TimeoutError",
                       "provider_in_flight_at_send": 40, "analysis_outstanding_at_send": 64})
        (row,) = stats.summarize_health(probes, 40)
        self.assertEqual(row["all_probes"]["n"], 4)
        sat = row["probes_sent_at_provider_in_flight_eq_40"]
        self.assertEqual(sat["n"], 3)
        self.assertEqual(sat["timeouts"], 1)
        self.assertEqual(sat["status_counts"], {"200": 2, "client_exception:TimeoutError": 1})
        self.assertEqual(row["provider_in_flight_at_send_counts"], {"39": 1, "40": 3})

    def test_phase_fields_only_appear_when_raw_records_carry_them(self):
        key = {"experiment": "e", "scenario": "s", "workload_id": "w", "concurrency": 1}
        trials = [{**key, "trial": 1, "wall_s": 1.0, "requests_planned": 1}]
        plain = [{**key, "trial": 1, "duration_s": 0.5, "success": True, "http_status": 200}]
        self.assertNotIn("phase_latency", stats.summarize(plain, trials)[0])
        phased = [{**plain[0], "pre_provider_s": 0.1, "provider_span_s": 0.3,
                   "post_provider_s": 0.1}]
        row = stats.summarize(phased, trials)[0]
        self.assertEqual(row["phase_latency"]["pre_provider"]["p50_ms"], 100.0)


class AdmissionStatsTests(unittest.TestCase):
    """SCALE-004: rejection-aware summary fields, absent for older raw records."""

    KEY = {"experiment": "admission", "scenario": "s", "workload_id": "w", "concurrency": 3}

    def _reqs(self):
        return [
            {**self.KEY, "trial": 1, "duration_s": 3.0, "success": True, "http_status": 200,
             "error_code": None, "provider_attempts": 1, "fake_attempts": 1},
            {**self.KEY, "trial": 1, "duration_s": 0.004, "success": False,
             "http_status": 503, "error_code": "capacity_exceeded", "provider_attempts": 0},
            {**self.KEY, "trial": 1, "duration_s": 6.0, "success": False, "http_status": 503,
             "error_code": "provider_unavailable", "provider_attempts": 2, "fake_attempts": 2},
        ]

    def test_admission_block_separates_rejections_from_failures(self):
        trials = [{**self.KEY, "trial": 1, "wall_s": 6.0, "requests_planned": 3,
                   "rejection_aware": True, "rejected": 1,
                   "rejections_done_before_first_provider_end": True}]
        row = stats.summarize(self._reqs(), trials)[0]
        adm = row["admission"]
        self.assertEqual(adm["rejected"], 1)
        self.assertEqual(adm["admitted"], 2)
        self.assertEqual(adm["non_rejection_failures"], 1)
        self.assertEqual(adm["failure_code_counts"],
                         {"capacity_exceeded": 1, "provider_unavailable": 1})
        self.assertEqual(adm["rejection_http_status_counts"], {"503": 1})
        self.assertEqual(adm["rejected_with_provider_attempts"], 0)
        self.assertEqual(adm["rejection_latency"]["max_ms"], 4.0)
        self.assertEqual(adm["success_latency"]["n"], 1)
        self.assertIs(adm["all_rejections_done_before_first_provider_end"], True)
        self.assertEqual(row["per_trial"][0]["rejected"], 1)
        # Existing fields keep their meaning: every non-200 is still a failure.
        self.assertEqual(row["failures"], 2)

    def test_admission_fields_absent_without_rejection_aware_trials(self):
        trials = [{**self.KEY, "trial": 1, "wall_s": 6.0, "requests_planned": 3}]
        row = stats.summarize(self._reqs(), trials)[0]
        self.assertNotIn("admission", row)
        self.assertNotIn("rejected", row["per_trial"][0])

    def test_lazy_bodies_builds_on_demand(self):
        seen = []
        bodies = LazyBodies(3, lambda tag: seen.append(tag) or tag.encode(), "p-")
        self.assertEqual(len(bodies), 3)
        self.assertEqual(bodies[2], b"p-2")
        self.assertEqual(seen, ["p-2"])
        with self.assertRaises(IndexError):
            bodies[3]


if __name__ == "__main__":
    unittest.main()
