# benchmarks/ — SCALE-001 capacity harness

A local, zero-provider-cost harness for measuring how the **unmodified** QuoteCheck
backend behaves as concurrent requests and simulated provider latency increase.
The findings are in [`docs/scalability/SCALE-001_BASELINE.md`](../docs/scalability/SCALE-001_BASELINE.md)
(baseline) and [`docs/scalability/SCALE-002_SHARED_CLIENT.md`](../docs/scalability/SCALE-002_SHARED_CLIENT.md)
(shared OpenAI client, before/after).

Local results are comparative evidence about this code on one machine. They are
not production SLAs and say nothing about real OpenAI capacity.

## Safety properties

- Everything runs on `127.0.0.1`. The harness starts its own servers on
  ephemeral ports and has **no option** to target another host, so the public
  Vercel/Railway deployment can't be load-tested with it.
- **No real provider calls.** OpenAI-mode runs point the SDK's own
  `OPENAI_BASE_URL` at `benchmarks/fake_provider.py`. That URL is checked to be
  loopback before launch.
- The server env is built explicitly. Inherited `OPENAI_*`, `QUOTECHECK_*` and
  `*_PROXY` variables are stripped, and a sentinel key and a nonexistent model
  name are set. Explicit env beats `backend/.env` (`load_dotenv(override=False)`).
- Every fake-provider trial is reconciled: the fake's attempt count must equal
  the sum of `provider_attempts` in QuoteCheck's own run log.
- No runtime code is changed. The app's run log goes into the results
  directory, never to `logs/app_runs.jsonl`.

## Commands

From the repo root, with backend requirements installed (conda env `quotecheck`):

```bash
# ~20 s smoke test of the harness itself (not evidence)
python -m benchmarks.run_capacity --quick

# full SCALE-001 baseline (about 5–10 minutes)
python -m benchmarks.run_capacity --experiment all --run-id SCALE-001-baseline

# SCALE-002 before/after (--ticket only labels env.json "measurement_ticket")
python -m benchmarks.run_capacity --experiment fake retry --run-id SCALE-002-before --ticket SCALE-002
python -m benchmarks.run_capacity --experiment all --run-id SCALE-002-after --ticket SCALE-002

# a subset
python -m benchmarks.run_capacity --experiment demo --run-id my-demo-run
python -m benchmarks.run_capacity --experiment fake retry --run-id my-fake-run

# recompute the summary from raw evidence and compare it with summary.json
python -m benchmarks.stats benchmarks/results/SCALE-001-baseline --check

# harness tests (included in the normal suite)
python -m unittest eval.tests.test_benchmarks -v
```

The QuoteCheck server is launched exactly as:

```text
python -m uvicorn backend.app:app --host 127.0.0.1 --port <ephemeral> --loop asyncio --http h11
```

This is one process with no `--reload` and no `--workers`. `--loop asyncio --http h11` matches the
production install: plain `uvicorn` from `backend/requirements.txt` has no uvloop
or httptools, even though a local environment may have them.

## Files

| File | Role |
| --- | --- |
| `workloads.py` | The fixed `short` / `normal` / `near_max` quote texts, with their sha256 hashes recorded in results |
| `fake_provider.py` | Loopback fake of `POST /v1/responses`: deterministic latency, lock-guarded attempt and in-flight counters, `success` / `fail_first` / `fail_always` modes, `TCP_NODELAY` on accepted sockets, per-attempt monotonic timestamp log (SCALE-003) |
| `run_capacity.py` | Orchestration: env metadata, server lifecycle, closed-loop load client, `/proc` sampling, guards, reconciliation; SCALE-003 attempt join and `/health` probe runner |
| `stats.py` | Nearest-rank percentiles and per-point summaries, recomputable from raw files; SCALE-003 timeline helpers and health summary |
| `diag_client_construction.py` | SCALE-001 diagnostic: cost of per-request `OpenAI(...)` construction |
| `diag_keepalive.py` | SCALE-003 diagnostic: reused-connection latency with and without the fake's `TCP_NODELAY` |

## Output layout (`benchmarks/results/<run-id>/`)

| File | Contents |
| --- | --- |
| `env.json` | git commit and dirty flag, Python, OS/kernel/WSL, CPU, memory, package versions, server argv, plan, guards |
| `scenarios.jsonl` | One line per scenario: server argv, env overrides (no secrets), ladder planned and executed, stop reason |
| `trials.jsonl` | One line per measured trial: wall time, server CPU seconds, peak threads/RSS/fds, fake-provider counters, reconciliation, clock-skew (suspend) check |
| `requests.jsonl` | One line per measured request: timings, HTTP status, error code, request id, server-logged latency, provider attempts |
| `summary.json` | Per-point aggregates (`python -m benchmarks.stats` regenerates it) |
| `server/` | Per-scenario uvicorn stdout and QuoteCheck app run logs (diagnostic) |

Warm-up requests (sequential ones at server start, plus a burst of 2×C per
concurrency point) are never written to `requests.jsonl`. Quote text and
secrets are not stored in results.

## Method notes

- **Load model:** closed loop. C worker threads, each with one persistent
  HTTP/1.1 connection, issue requests back-to-back until N measured requests
  have been issued. This measures throughput and latency at a fixed
  concurrency; it doesn't model open arrivals, so queueing delay is
  under-represented.
- **Percentiles:** nearest-rank with no interpolation. p99 is reported only when
  the pooled n is at least 1000.
- **Stop guards:**
  - Host safety: server RSS above 1 GiB, or host MemAvailable below 1 GiB.
    These stop the run for machine safety and are **not** saturation evidence.
  - Escalation: any failure, or pooled p95 above 30 s at the previous point.
  - A trial whose wall-clock and monotonic elapsed times differ by more than
    1 s is flagged `suspend_suspected` (host sleep) and must be discarded.
- **Fake-provider keep-alive artifact: found in SCALE-002, repaired in SCALE-003.**
  - `fake_provider.py` writes the response headers and body in separate sends.
  - Before SCALE-003 it didn't set `TCP_NODELAY`. On a *reused* keep-alive
    connection, Nagle's algorithm and the client's delayed ACK then added about
    40 ms per request.
  - SCALE-003 sets `TCP_NODELAY` on every accepted socket.
  - `python -m benchmarks.diag_keepalive` measures the fake both ways
    (`tcp_nodelay=False` reproduces the old instrument, for this diagnostic only).
  - **SCALE-001 and SCALE-002 results were produced with the original fake, and
    SCALE-003 results with the corrected one.** Exact provider-loop latencies
    across those generations are therefore not directly interchangeable. SCALE-002
    after-run loop times carry about +40 ms per attempt that SCALE-003 times do not.
- `env.json` records `harness_origin` (the ticket that created this harness) and
  `measurement_ticket` (from `--ticket`; `null` if omitted). Since SCALE-003 it
  also records the clock implementations and sha256 hashes of the harness files.

## SCALE-003 experiments (saturation, `/health`, retry under saturation)

```bash
python -m benchmarks.run_capacity --experiment saturation health retry_sat \
    --run-id SCALE-003-saturation --ticket SCALE-003        # about 35–45 minutes
python -m benchmarks.run_capacity --quick --experiment saturation health retry_sat  # smoke
python -m benchmarks.diag_keepalive                         # fake repair evidence
```

`--experiment all` still means the SCALE-001 set (`demo fake retry`). The SCALE-003
experiments must be named explicitly.

| experiment | what it runs |
| --- | --- |
| `saturation` | success mode at 1 s (C = 1, 16, 32, 40, 48, 64), 3 s and 5 s (C = 16, 32, 40, 48, 64). 3 trials, N = max(4·C, 16). |
| `health` | per latency class (3 s, 5 s): 40 idle `/health` probes, then for C = 32, 40, 64 sustained closed-loop `/analyze` load plus 40 sequential probes |
| `retry_sat` | fail-first at 3 s, C = 32, 40, 64 (3 trials); fail-always at 3 s, C = 64, N = 128 |

- **Per-attempt timeline.**
  - Every SCALE-003 request body carries a unique `[bench-marker:…]`.
  - The fake logs each attempt's `{marker, t_start, t_end, status}` on
    `time.monotonic()` (`GET /__attempts`, cleared by `/__reset`).
  - On Linux that is the same system-wide `CLOCK_MONOTONIC` as the harness's
    `perf_counter`. The run refuses to start if the two differ.
  - The harness joins attempts to requests and stores, per request:
    - `pre_provider_s`: client send → first attempt start;
    - `provider_span_s`;
    - `post_provider_s`: last attempt end → client receive;
    - `inter_attempt_gap_s` (retries).
  - Per trial it stores `provider_mean_in_flight` and
    `provider_time_frac_in_flight_ge_40`.
  - `attempts_joined` is false, and a warning is printed, unless every request's
    fake attempt count equals QuoteCheck's logged `provider_attempts`.
  - Nothing is added to QuoteCheck itself.
- **Health design.**
  1. After an idle control, a background closed-loop load runs at C.
  2. The harness polls the **fake's** `/__stats` (a separate process, so this uses
     no QuoteCheck worker) until provider in-flight ≥ min(C, 40).
  3. It then waits one more provider period.
  4. It sends 40 sequential probes: fresh connection each, at most one outstanding,
     seeded 0.2–0.6 s gaps, 60 s timeout.
  5. Each probe is tagged post hoc with the exact provider in-flight count at
     send and receive, and with the analysis requests outstanding at the client.
     `health_summary.json` reports all probes and, separately, the probes sent
     while provider in-flight was exactly 40.
- **Extra outputs:**
  - `provider_attempts.jsonl` (raw attempt log);
  - `health_probes.jsonl`;
  - `health_load_requests.jsonl` (the analysis load behind the probes, never
    pooled into `summary.json`);
  - `health_summary.json`.
- `python -m benchmarks.stats <run> --check` also verifies `health_summary.json`.
