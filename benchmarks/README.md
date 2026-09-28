# benchmarks/ — SCALE-001 capacity harness

A local, zero-provider-cost harness for measuring how the **unmodified** QuoteCheck
backend behaves as concurrent requests and simulated provider latency increase.
The findings are in [`docs/scalability/SCALE-001_BASELINE.md`](../docs/scalability/SCALE-001_BASELINE.md).

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
| `fake_provider.py` | Loopback fake of `POST /v1/responses`: deterministic latency, lock-guarded attempt and in-flight counters, `success` / `fail_first` / `fail_always` modes |
| `run_capacity.py` | Orchestration: env metadata, server lifecycle, closed-loop load client, `/proc` sampling, guards, reconciliation |
| `stats.py` | Nearest-rank percentiles and per-point summaries, recomputable from raw files |

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
