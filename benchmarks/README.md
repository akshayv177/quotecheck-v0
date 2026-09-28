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
| `run_capacity.py` | Orchestration: env metadata, server lifecycle, closed-loop load client, `/proc` sampling, guards, reconciliation; SCALE-003 attempt join and `/health` probe runner; SCALE-004 rejection-aware `admission` experiment |
| `stats.py` | Nearest-rank percentiles and per-point summaries, recomputable from raw files; SCALE-003 timeline helpers and health summary; SCALE-004 admission block |
| `diag_client_construction.py` | SCALE-001 diagnostic: cost of per-request `OpenAI(...)` construction |
| `diag_keepalive.py` | SCALE-003 diagnostic: reused-connection latency with and without the fake's `TCP_NODELAY` |
| `diag_rejection_log.py` | SCALE-004 diagnostic: in-process event-loop cost of an admission rejection with/without its synchronous JSONL log, and of `response_model` validation |

## Output layout (`benchmarks/results/<run-id>/`)

| File | Contents |
| --- | --- |
| `env.json` | git commit and dirty flag, Python, OS/kernel/WSL, CPU, memory, package versions, server argv, plan, guards |
| `scenarios.jsonl` | One line per scenario: server argv, env overrides (no secrets), ladder planned and executed, stop reason |
| `trials.jsonl` | One line per measured trial: wall time, server CPU seconds, peak threads/RSS/fds, fake-provider counters, reconciliation, clock-skew (suspend) check |
| `requests.jsonl` | One line per measured request: timings, HTTP status, error code, request id, server-logged latency, provider attempts (generated bulk; not committed since SCALE-004, see "Evidence retention") |
| `summary.json` | Per-point aggregates (`python -m benchmarks.stats` regenerates it) |
| `server/` | Per-scenario uvicorn stdout and QuoteCheck app run logs (diagnostic; generated bulk, not committed since SCALE-004) |

Warm-up requests (sequential ones at server start, plus a burst of 2×C per
concurrency point) are never written to `requests.jsonl`. Quote text and
secrets are not stored in results.

## Evidence retention

The harness plus the fixed workload definitions are the primary reproducibility
mechanism: a fresh clone reproduces an experiment by rerunning it.

- **Committed:** compact summaries, provenance, trial records and decision-critical
  diagnostics — `env.json`, `scenarios.jsonl`, `trials.jsonl`, `summary.json`,
  `health_summary.json`, `health_probes.jsonl`, `provider_attempts.jsonl`,
  `run_console.log`, and any report scripts/outputs or diagnostics a report cites.
- **Not committed by default:** generated request-level traces and server logs —
  `requests.jsonl`, `health_load_requests.jsonl` and `server/`. `.gitignore`
  excludes them under `benchmarks/results/*/`.
- **Exact replay:** `python -m benchmarks.stats <run> --check` and report scripts
  read the request-level files. Where exact replay matters, keep the full raw
  evidence outside Git and commit a manifest of the omitted files' sha256 hashes and
  sizes (for example `results/SCALE-004_RAW_EVIDENCE_MANIFEST.txt`). Any `--check`
  result recorded in a report is then a verification made before compaction.
- Git LFS is not used.
- SCALE-001–003 predate this policy; their raw files remain committed and
  `--check` still runs on them from a fresh clone. SCALE-004's bulk was omitted
  before publication (see `docs/scalability/SCALE-004_ADMISSION.md`).

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

## SCALE-004 experiment (provider admission, before/after)

```bash
# after: the working tree, which enforces a 32-slot provider admission budget
python -m benchmarks.run_capacity --experiment admission --gate-cap 32 \
    --run-id SCALE-004-after --ticket SCALE-004              # about 25–30 minutes
# before: the same harness files run from a checkout of the pre-SCALE-004 backend
python -m benchmarks.run_capacity --experiment admission --gate-cap 40 \
    --run-id SCALE-004-before --ticket SCALE-004
python -m benchmarks.run_capacity --quick --experiment admission --gate-cap 32   # smoke
```

The workload is the same for both builds. `--gate-cap` is the only difference: the
health gate waits for provider in-flight ≥ min(C, cap). An enforced budget of 32
can never reach the 40 that the old gate waited for.

| scenario | what it runs |
| --- | --- |
| `adm_burst_lat3s` / `adm_burst_lat5s` | one simultaneous wave of N = C requests, C = 32, 40, 64, 5 trials |
| `adm_sustained_5000ms` | closed loop at 5 s for 4 provider periods (20 s, duration-bounded), C = 32, 40, 64, 3 trials. A client whose request was rejected waits 0.25 s before resending. |
| `adm_sustained_5000ms_nobackoff` | the same at C = 64, but a rejected client resends immediately. This is the worst case for the event loop, including synchronous rejection logging. |
| `adm_health_lat3s` / `adm_health_lat5s` | the SCALE-003 health design at C = 32, 40, 64, with the load resending after rejection with a 0.25 s backoff |
| `adm_health_5000ms_nobackoff` | health at 5 s, C = 64, zero-backoff load |
| `adm_retry_*` | 3 s, C = 64: fail-first as a burst (5 trials) and sustained (12 s); fail-always sustained |

**Rejection-aware accounting.** This applies only to trials marked `rejection_aware`,
so older result directories recompute unchanged.

- A `capacity_exceeded` response is an **admission rejection**. It is not counted as
  an escalation failure.
- Reconciliation expects:
  - `expected_attempts × admitted` provider attempts;
  - `provider_attempts == 0` in QuoteCheck's log for every rejected request.
- The attempt join additionally requires that the fake saw **no** attempt carrying a
  rejected request's marker.
- `summary.json` rows gain an `admission` block with:
  - rejected / admitted / non-rejection-failure counts;
  - failure codes;
  - rejection and success latency;
  - for bursts, whether every rejection completed before the first admitted provider
    attempt ended (`all_rejections_done_before_first_provider_end`).
- Health points in `scenarios.jsonl` gain `load_rejected`, `load_successes` and
  `load_rejection_latency`.

**Against a SCALE-004 build**, the SCALE-003 `saturation` / `retry_sat` experiments
now see `capacity_exceeded` rejections at C > 32. Those are rejection-aware in
reconciliation and in the join, but they are not summarized separately. The SCALE-003
`health` experiment gates on in-flight ≥ min(C, 40), which a 32-slot build never
reaches, so its C ≥ 40 points report `gate_failed`. Use `--experiment admission`
for such builds.

Duration-bounded points build request bodies lazily (`LazyBodies`) and record
`issue_duration_s` instead of `requests_planned`. Throughput is still
successes / trial wall time, where the wall time includes draining in-flight work
after issuing stops.
