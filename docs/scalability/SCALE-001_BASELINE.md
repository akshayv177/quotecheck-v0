# SCALE-001 — Current-System Capacity Baseline

Ticket: `docs/tickets/SCALE-001-capacity-characterization.md`
Raw evidence: `benchmarks/results/SCALE-001-baseline/` (`requests.jsonl`, `trials.jsonl`,
`scenarios.jsonl`, `env.json`, `summary.json`, `diag_client_construction.json`)
Harness: `benchmarks/` (see `benchmarks/README.md`)

> **Scope of these numbers.** Everything here was measured on one local WSL2
> machine, against a loopback fake provider. These are comparative system
> evidence about current QuoteCheck code. They are **not** production SLAs,
> Railway capacity figures, or OpenAI capacity claims. No real provider was
> called, and the public deployment was never contacted.

---

## Environment

| Item | Value |
| --- | --- |
| Git | `task/SCALE-001-capacity-characterization` @ `484720d` (runtime unmodified; only new benchmark files uncommitted, `git_dirty: true`) |
| Run | `SCALE-001-baseline`, 2026-09-24 07:35 UTC, 434.5 s total (monotonic) |
| Host | Linux 6.6.87.2-microsoft-standard-WSL2, AMD Ryzen 9 8940HX, 32 logical CPUs, 7.7 GB RAM (6.7 GB available at start) |
| Python | 3.11.14 (conda env `quotecheck`) |
| Packages | fastapi 0.128.6, starlette 0.52.1, uvicorn 0.40.0, anyio 4.12.1, h11 0.16.0, openai 2.24.0, httpx 0.28.1, pydantic 2.12.5; OpenSSL 3.0.19 |
| Server | `python -m uvicorn backend.app:app --host 127.0.0.1 --port <ephemeral> --loop asyncio --http h11`: 1 process, 1 worker, no `--reload`, access log on |
| Loop/HTTP | asyncio + h11 chosen explicitly to match the production install (plain `uvicorn`, no uvloop/httptools). The local env *has* uvloop 0.22.1 and httptools 0.7.1, which uvicorn would otherwise auto-select. |

## Methodology

**Topology:** three OS processes on 127.0.0.1.

- **Load client** (`benchmarks/run_capacity.py`): closed loop. C threads, each
  with one persistent HTTP/1.1 connection, issue requests back-to-back until
  N measured requests have been issued.
- **QuoteCheck:** one uvicorn process, unmodified code.
- **Fake provider** (`benchmarks/fake_provider.py`, Experiment B only).

**Provider boundary:** QuoteCheck runs in real OpenAI mode
(`QUOTECHECK_USE_OPENAI=1`). The openai SDK's own `OPENAI_BASE_URL` env var
points at the loopback fake. The uvicorn/h11 boundary, anyio threadpool,
per-request `OpenAI(...)` construction, SDK/httpx request, QuoteCheck's
retry loop, classification, Pydantic validation and JSONL logging all run for
real. Only the remote endpoint is replaced. The fake replies with a
Responses-API body whose `output_text` is a schema-valid `QuoteCheckResult`
(3,625 chars, the Demo analyzer's output for `normal`).

**Safety:**

- The server env is built explicitly: inherited `OPENAI_*`, `QUOTECHECK_*` and
  `*_PROXY` variables are stripped, and a sentinel key
  (`quotecheck-benchmark-fake-key`), a sentinel model
  (`quotecheck-bench-fake-model`) and a loopback-asserted base URL are set.
  `backend/.env` can't override these (`override=False`).
- Warm-up must register fake-provider attempts, or the run aborts.
- In every fake-provider trial, the fake's attempt count must equal the sum of
  `provider_attempts` in QuoteCheck's run log. **All 60 fake/retry trials
  reconciled.**

**Warm-up (excluded from statistics):** 20 sequential requests after server
start (5 for fake/retry), then a burst of 2×C requests before each
concurrency point. Warm-up is never written to `requests.jsonl`. Each scenario
gets a fresh server process and climbs its ladder in ascending order.

**Trials:** 3 measured trials per concurrency point, everywhere.

- Demo: N = 200 per trial.
- Fake/retry: N = max(4·C, 16) per trial. That is a bounded plan that keeps
  1 s scenarios short while giving every worker at least 4 sequential requests.

**Metrics:**

- **Per request:** client-side duration, HTTP status, error code, request id,
  plus QuoteCheck's own logged `latency_ms` and `provider_attempts` (joined by
  request id).
- **Per trial:**
  - wall time and throughput (successes / wall)
  - server CPU seconds (`/proc/<pid>/stat` delta)
  - peak server threads, RSS and open fds (sampled every 100 ms)
  - fake-provider counters: attempts started/completed, peak in flight,
    injected failures, TCP connections accepted
  - a wall-clock vs monotonic skew check that flags host suspension

**Percentiles:** nearest-rank on the pooled 3-trial sample, with no
interpolation. p99 is omitted because every pooled sample is below 1,000
(the largest is 768).

**Stop guards:**

- Host safety: server RSS above 1 GiB, or host MemAvailable below 1 GiB.
  These are not saturation evidence.
- Escalation: any failure, or p95 above 30 s, at the previous point.
- Suspend detection: skew above 1 s.

**None fired.** Every planned ladder ran to completion, and the maximum
observed skew was 0.83 s (WSL clock adjustment; the durations themselves use
the monotonic `perf_counter`).

**Commands:**

```bash
python -m benchmarks.run_capacity --experiment all --run-id SCALE-001-baseline
python -m benchmarks.diag_client_construction --out benchmarks/results/SCALE-001-baseline/diag_client_construction.json
python -m benchmarks.stats benchmarks/results/SCALE-001-baseline --check   # "summary.json matches recomputation: True"
```

## Workloads

Committed in `benchmarks/workloads.py`. The sha256 of each is recorded in `env.json`.

| id | chars | purpose |
| --- | ---: | --- |
| `short` | 85 | one-line informal quote |
| `normal` | 641 | representative itemised HVAC quote: clear, vague and conditional items, total, approval language |
| `near_max` | 11,465 | deterministic single-trade (HVAC) itemised quote near the 12,000-char limit, for length scaling |

`near_max` is deliberately single-trade. The first multi-trade version made
the Demo analyzer return HTTP 500 on every request, a pre-existing defect
described below. The Demo analyzer's output is about 3.6 KB for both `normal`
and `near_max`, so `near_max` stresses input-side cost only.

Fake-provider and retry scenarios use `normal`. For per-request retry
determinism, retry scenarios append a `[bench-marker:<id>]` token that the fake
reads from the forwarded prompt.

---

## Demo HTTP results

### GET /health (framework + HTTP + client floor)

| C | trials × req | ok / fail | throughput rps mean (min–max) | p50 ms | p95 ms | max ms | server CPU ms/req | cores busy | peak threads |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 3 × 200 | 600 / 0 | 1866 (1835–1884) | 0.5 | 0.8 | 1.2 | 0.45 | 0.84 | 2 |
| 2 | 3 × 200 | 600 / 0 | 2391 (2364–2425) | 0.8 | 1.2 | 1.9 | 0.45 | 1.08 | 3 |
| 4 | 3 × 200 | 600 / 0 | 2391 (2373–2412) | 1.6 | 2.2 | 2.9 | 0.47 | 1.12 | 5 |
| 8 | 3 × 200 | 600 / 0 | 2640 (2606–2659) | 2.8 | 4.0 | 7.6 | 0.42 | 1.10 | 9 |
| 16 | 3 × 200 | 600 / 0 | 2594 (2492–2666) | 5.8 | 8.3 | 11.2 | 0.42 | 1.08 | 17 |
| 32 | 3 × 200 | 600 / 0 | 2286 (1966–2487) | 11.9 | 30.2 | 36.8 | 0.47 | 1.06 | 33 |
| 64 | 3 × 200 | 600 / 0 | 2250 (2214–2282) | 23.1 | 38.2 | 47.3 | 0.45 | 1.01 | 39 |

### POST /analyze — `short` (85 chars)

| C | trials × req | ok / fail | throughput rps mean (min–max) | p50 ms | p95 ms | max ms | server CPU ms/req | cores busy | peak threads |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 3 × 200 | 600 / 0 | 949 (939–960) | 1.0 | 1.5 | 2.0 | 0.95 | 0.90 | 2 |
| 2 | 3 × 200 | 600 / 0 | 958 (952–968) | 2.0 | 2.8 | 3.3 | 1.17 | 1.12 | 3 |
| 4 | 3 × 200 | 600 / 0 | 835 (826–846) | 4.7 | 6.4 | 8.0 | 1.47 | 1.22 | 5 |
| 8 | 3 × 200 | 600 / 0 | 811 (799–817) | 9.7 | 12.6 | 15.2 | 1.57 | 1.27 | 9 |
| 16 | 3 × 200 | 600 / 0 | 798 (728–838) | 18.9 | 24.3 | 60.0 | 1.60 | 1.27 | 17 |
| 32 | 3 × 200 | 600 / 0 | 849 (839–862) | 36.1 | 48.1 | 52.5 | 1.52 | 1.29 | 33 |
| 64 | 3 × 200 | 600 / 0 | 795 (764–817) | 74.0 | 102.5 | 120.3 | 1.58 | 1.26 | 49 |

### POST /analyze — `normal` (641 chars)

| C | trials × req | ok / fail | throughput rps mean (min–max) | p50 ms | p95 ms | max ms | server CPU ms/req | cores busy | peak threads |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 3 × 200 | 600 / 0 | 653 (638–680) | 1.5 | 2.0 | 2.6 | 1.45 | 0.95 | 2 |
| 2 | 3 × 200 | 600 / 0 | 661 (643–679) | 3.0 | 4.0 | 5.7 | 1.63 | 1.08 | 3 |
| 4 | 3 × 200 | 600 / 0 | 599 (586–607) | 6.5 | 8.9 | 10.9 | 1.93 | 1.16 | 5 |
| 8 | 3 × 200 | 600 / 0 | 602 (599–609) | 13.0 | 16.3 | 24.5 | 2.00 | 1.20 | 9 |
| 16 | 3 × 200 | 600 / 0 | 590 (566–604) | 26.0 | 34.4 | 74.3 | 2.05 | 1.21 | 17 |
| 32 | 3 × 200 | 600 / 0 | 614 (602–621) | 50.7 | 61.2 | 90.3 | 1.97 | 1.21 | 33 |
| 64 | 3 × 200 | 600 / 0 | 556 (541–581) | 109.1 | 148.0 | 186.0 | 2.13 | 1.19 | 45 |

### POST /analyze — `near_max` (11,465 chars)

| C | trials × req | ok / fail | throughput rps mean (min–max) | p50 ms | p95 ms | max ms | server CPU ms/req | cores busy | peak threads |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 3 × 200 | 600 / 0 | 103 (101–106) | 9.7 | 10.7 | 11.8 | 8.97 | 0.92 | 2 |
| 2 | 3 × 200 | 600 / 0 | 107 (105–108) | 18.6 | 20.8 | 30.1 | 9.32 | 0.99 | 3 |
| 4 | 3 × 200 | 600 / 0 | 103 (101–105) | 38.6 | 51.8 | 67.3 | 9.95 | 1.02 | 5 |
| 8 | 3 × 200 | 600 / 0 | 105 (102–107) | 75.3 | 94.6 | 133.3 | 9.90 | 1.04 | 9 |
| 16 | 3 × 200 | 600 / 0 | 104 (103–105) | 152.7 | 183.9 | 281.1 | 9.97 | 1.04 | 17 |
| 32 | 3 × 200 | 600 / 0 | 106 (105–107) | 301.8 | 386.0 | 568.3 | 10.05 | 1.06 | 33 |
| 64 | 3 × 200 | 600 / 0 | 103 (102–104) | 622.1 | 749.5 | 827.0 | 10.30 | 1.06 | 44 |

**HTTP status:** all 16,800 Demo-experiment measured requests (12,600
`/analyze` and 4,200 `/health`) returned 200. There were no client exceptions.
All 4,320 fake-provider success-scenario requests also returned 200.

**Server-reported latency:** in Demo mode, `latency_ms` is computed *before*
`analyze_quote_stub` runs (`backend/app.py:193`), so it's ~0 by construction
and can't be correlated with the client latency above. Out-of-scope finding 2
records this.

## Fake-provider results

### ~250 ms simulated provider latency

| C | trials × req | ok / fail | rps mean (min–max) | client p50 ms | client p95 ms | client max ms | server-logged provider-loop p50 / p95 ms | provider attempts | peak provider in flight | server CPU ms/req | cores busy | peak threads | reconciled |
|---:|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| 1 | 3 × 16 | 48 / 0 | 3.65 (3.65–3.65) | 274 | 278 | 288 | 256 / 258 | 48 | 1 | 20 | 0.07 | 2 | True |
| 2 | 3 × 16 | 48 / 0 | 7.21 (7.17–7.26) | 276 | 287 | 292 | 257 / 261 | 48 | 2 | 21 | 0.15 | 3 | True |
| 4 | 3 × 16 | 48 / 0 | 13.14 (12.92–13.39) | 306 | 314 | 320 | 257 / 266 | 48 | 4 | 40 | 0.52 | 5 | True |
| 8 | 3 × 32 | 96 / 0 | 21.91 (20.83–22.68) | 353 | 439 | 443 | 258 / 277 | 96 | 8 | 75 | 1.65 | 9 | True |
| 16 | 3 × 64 | 192 / 0 | 35.16 (32.79–37.15) | 348 | 698 | 702 | 256 / 275 | 192 | 16 | 150 | 5.25 | 17 | True |
| 32 | 3 × 128 | 384 / 0 | 36.48 (35.28–37.93) | 933 | 1144 | 1251 | 277 / 359 | 384 | 32 | 472 | 17.22 | 33 | True |
| 48 | 3 × 192 | 576 / 0 | 38.38 (37.63–39.71) | 1177 | 1501 | 2340 | 267 / 371 | 576 | 40 | 580 | 22.26 | 43 | True |
| 64 | 3 × 256 | 768 / 0 | 40.86 (38.95–42.32) | 1315 | 2275 | 2678 | 259 / 382 | 768 | 40 | 576 | 23.51 | 46 | True |

### ~1 s simulated provider latency

| C | trials × req | ok / fail | rps mean (min–max) | client p50 ms | client p95 ms | client max ms | server-logged provider-loop p50 / p95 ms | provider attempts | peak provider in flight | server CPU ms/req | cores busy | peak threads | reconciled |
|---:|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| 1 | 3 × 16 | 48 / 0 | 0.97 (0.97–0.97) | 1028 | 1041 | 1044 | 1007 / 1021 | 48 | 1 | 22 | 0.02 | 2 | True |
| 2 | 3 × 16 | 48 / 0 | 1.94 (1.93–1.94) | 1027 | 1046 | 1058 | 1007 / 1024 | 48 | 2 | 22 | 0.04 | 3 | True |
| 4 | 3 × 16 | 48 / 0 | 3.78 (3.76–3.81) | 1045 | 1110 | 1112 | 1012 / 1056 | 48 | 4 | 30 | 0.11 | 5 | True |
| 8 | 3 × 32 | 96 / 0 | 7.32 (7.24–7.36) | 1070 | 1155 | 1164 | 1010 / 1025 | 96 | 8 | 57 | 0.41 | 9 | True |
| 16 | 3 × 64 | 192 / 0 | 12.85 (12.75–12.99) | 1117 | 1460 | 1487 | 1010 / 1045 | 192 | 16 | 167 | 2.15 | 17 | True |
| 32 | 3 × 128 | 384 / 0 | 21.54 (21.25–21.78) | 1300 | 1820 | 1907 | 1011 / 1053 | 384 | 32 | 284 | 6.13 | 33 | True |
| 48 | 3 × 192 | 576 / 0 | 26.76 (25.19–27.90) | 1611 | 2153 | 2855 | 1008 / 1053 | 576 | 40 | 308 | 8.23 | 44 | True |
| 64 | 3 × 256 | 768 / 0 | 28.66 (25.56–30.68) | 1939 | 3556 | 3829 | 1008 / 1073 | 768 | 40 | 253 | 7.22 | 49 | True |

"Server-logged provider-loop" is QuoteCheck's own `latency_ms` in OpenAI mode.
It times only the attempt loop (`openai_analyzer.py:177–200`): SDK request,
fake latency, response parse. Client construction, schema/message building,
threadpool queueing, validation and logging all sit outside it.

### Retry amplification spot checks (250 ms per attempt)

Transient 503 → retry → success:

| C | trials × req | ok / fail | rps mean (min–max) | client p50 ms | client p95 ms | client max ms | server-logged provider-loop p50 / p95 ms | provider attempts | peak provider in flight | server CPU ms/req | cores busy | peak threads | reconciled |
|---:|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| 1 | 3 × 16 | 48 / 0 | 1.74 (1.74–1.75) | 572 | 582 | 595 | 553 / 561 | 96 | 1 | 24 | 0.04 | 2 | True |
| 8 | 3 × 32 | 96 / 0 | 12.36 (12.16–12.56) | 619 | 722 | 732 | 555 / 572 | 192 | 8 | 70 | 0.87 | 9 | True |
| 32 | 3 × 128 | 384 / 0 | 31.01 (30.45–32.01) | 988 | 1355 | 1459 | 557 / 637 | 768 | 32 | 368 | 11.42 | 33 | True |

503 on every attempt (the two-attempt bound):

| C | trials × req | ok / fail | client p50 ms | client p95 ms | client max ms | server-logged p50 / p95 ms | provider attempts | peak in flight | reconciled |
|---:|---|---|---:|---:|---:|---|---:|---:|---|
| 4 | 3 × 16 | 0 / 48 (all HTTP 503 `provider_unavailable`) | 601 | 619 | 621 | 597 / 611 | 96 | 4 | True |

Every fail-first request logged `provider_attempts = 2` and returned 200.
Every fail-always request logged exactly 2 attempts and returned 503. There
was no third attempt in any of the 576 retry-scenario requests.

### Focused diagnostic: per-request client construction

This diagnostic was added only after the main evidence showed server CPU per
request rising about 25× with concurrency while the provider-loop latency
stayed flat. `python -m benchmarks.diag_client_construction` runs in one
process with no network access. It reproduced identically in an earlier
scratch run.

| operation | threads | ops/s (process) | CPU ms/op | cores busy |
|---|---:|---:|---:|---:|
| `OpenAI(api_key, timeout=30.0, max_retries=0)` (the analyzer's exact call) | 1 | 48.0 | 20.31 | 0.98 |
| same | 8 | 65.6 | 116.65 | 7.65 |
| same | 32 | 40.4 | 755.36 | 30.54 |
| `httpx.Client()` | 1 / 8 / 32 | 48.8 / 67.1 / 39.6 | 19.9 / 114.2 / 767.5 | 0.97 / 7.66 / 30.38 |
| `ssl.create_default_context(cafile=certifi.where())` | 1 / 8 / 32 | 49.0 / 71.2 / 39.7 | 19.8 / 107.5 / 766.3 | 0.97 / 7.66 / 30.41 |
| `quotecheck_result_schema_obj()` + `build_messages()` | 1 / 8 / 32 | 508 / 487 / 437 | 1.9 / 1.9 / 2.4 | ~1 |

---

## Capacity curve

**Demo path (application spine, no inference):**

- Throughput is flat from C=1 to C=64: about 950 rps for `short`, about
  600–650 for `normal`, and about 105 for `near_max`.
- Latency rises almost exactly linearly with C (Little's law: p50 ≈ C /
  throughput).
- Server CPU stays at about 1.0–1.3 cores throughout.
- There are no failures at any level.
- Peak thread count follows C up to the pool size.

**OpenAI path with the fake provider:**

- At low C, client latency ≈ provider latency + about 20 ms, and throughput
  scales with C.
- Then three things happen together:
  1. Throughput stops scaling well below the provider-latency ideal. At
     250 ms: 13.1 rps at C=4 (ideal 16), 21.9 at C=8 (32), 35.2 at C=16 (64),
     then a plateau of 36–41 rps for C=32–64.
  2. Server CPU per request grows from 20 ms to about 580 ms, and the one
     process burns up to 23.5 cores.
  3. The provider-loop latency stays flat (p50 256–277 ms), so all of the
     extra time is spent outside the provider call.
- Peak provider calls in flight equal C up to 32. They then pin at **40** for
  C=48 and C=64 (one C=64 trial peaked at 38), and peak server threads reach
  43–49.
- There are no failures at any level. Requests beyond capacity simply wait
  longer (p95 2.3 s at C=64/250 ms, 3.6 s at C=64/1 s).

## Saturation finding

**A clear saturation knee was observed** in both paths, consistently across 3
trials per point:

- **Demo:** throughput is already at its ceiling at C=1–2, and every further
  increase in C converts directly into latency. The knee is a single-core
  CPU ceiling, and its height depends on input length.
- **OpenAI path (fake provider, 250 ms):** the knee is between C=16 and C=32,
  at about 35–41 rps.
- **OpenAI path (1 s):** scaling degrades from C=16, and throughput reaches
  only 28.7 rps at C=64. That is below the 40 rps that 40 concurrent 1 s calls
  would allow.

## Bottleneck assessment

### Observed fact

1. **Demo:**
   - The Demo path serves `/analyze` at about 950 / 600–650 / 105 rps
     (short / normal / near_max) at about 1 core of CPU, flat from C=1–2 up to
     C=64, with zero failures.
   - The `/health` floor on the same stack is about 1,900–2,600 rps.
2. **OpenAI path, provider loop and throughput:**
   - QuoteCheck's own logged provider-loop latency stays within about 30 ms of
     the configured fake latency at p50 for every C.
   - Client latency and server CPU per request grow sharply with C, and
     throughput plateaus at about 36–41 rps (250 ms) and about 29 rps (1 s).
3. **Peak provider calls in flight** = C for C ≤ 32, and 40 (38 in one trial)
   for C = 48 and 64. There were 768 attempts for 768 requests (success
   scenarios); every trial reconciled.
4. **Per-request client construction, measured in isolation:**
   - A single `OpenAI(...)` construction costs about 20 ms CPU, the same as a
     bare `httpx.Client()` or an SSL context with the certifi CA bundle loaded.
   - With 8 or 32 threads constructing concurrently, process-wide throughput
     is only 40–71 constructions/s while CPU per construction rises to about
     110–770 ms, burning up to about 30 cores.
   - Schema and message building costs about 2 ms and stays flat.
5. **One new TCP connection per request:** the fake accepted one new
   connection per successful request (for example 128 attempts, 129
   connections including the harness's single stats call), so there is no
   connection reuse across requests. A retry reuses its request's connection:
   256 attempts over 129 connections.
6. **Retries:**
   - Retries are strictly sequential within a request and never exceeded 2
     attempts.
   - Transient-then-success doubles provider attempts (768 for 384 requests at
     C=32) and roughly doubles per-request provider time (about 555 ms vs
     about 257 ms).
   - Peak in flight still tracks C, not 2×C.
7. **Resources:** server RSS peaked at about 390 MB and open fds at about 360
   (C=64). No guard fired, and no request failed except the deliberate
   fail-always scenario.

### Supported inference

1. **The first meaningful capacity constraint on the OpenAI path is
   per-request `OpenAI` client construction.** Its cost is essentially creating
   an SSL context and loading the CA bundle inside `httpx.Client`.
   - It costs about 20 ms CPU serially, and it degrades under thread
     concurrency in native code (OpenSSL 3.0.19) rather than being limited by
     the GIL.
   - Evidence: the extra CPU and time appear only outside the timed provider
     loop, and client construction is the analyzer's main pre-loop step
     (`openai_analyzer.py:161`). The isolated diagnostic reproduces the same
     shape: about 40 constructions/s at 32 threads with about 30 cores busy,
     against about 36 rps with 17 cores busy in-server at C=32.
   - The remaining per-request work (schema, messages, validation, logging) is
     small and flat. Demo costs about 1.5–2 ms CPU per request with the same
     logging and response serialization.
2. **Synchronous JSONL logging is not a first-order constraint at the rates
   reached.** Demo writes one log line per request at 600–950 rps with total
   server CPU at about 1–2 ms/request, flat across C. The logging A/B
   diagnostic was therefore **not** run.
3. **Aggregate provider concurrency is capped only implicitly, by anyio's
   default 40-token threadpool limiter, not by any QuoteCheck decision.**
   Beyond 40 concurrent requests, the extra requests wait invisibly inside
   the process: there is no rejection and no admission signal. At 1 s latency
   this cap and the construction cost interact, so throughput stays below
   40 rps.
4. **Per-request retry bounds do not bound aggregate provider demand.**
   Aggregate attempts = requests × attempts per request, and the only limit on
   simultaneous calls is the same implicit 40-thread cap. A retry also holds
   its worker thread for both attempts, doubling thread-time per request.
5. **The Demo-path ceiling is single-process Python CPU (GIL).** The stub's
   cost grows with input length (about 1 ms at 85 chars, about 9–10 ms at
   11.5k chars). This is a different constraint from the OpenAI path and
   irrelevant to model-execution capacity.

### Remaining hypothesis

1. **Production magnitude is unknown.** Railway's vCPU count, CPU model and
   the OpenSSL build in the Railpack Python 3.11 image weren't measured. The
   ~20 ms serial cost and the contention shape could differ there. With few
   vCPUs there would be less parallel spinning, but the serial cost remains.
2. **Real OpenAI traffic adds costs the loopback fake cannot show:** a full TLS
   handshake on each request's new connection, DNS lookups, and real provider
   latency. Structured-output responses are likely multiple seconds, far
   above 1 s. At multi-second latency, the 40-thread cap probably becomes the
   binding limit (Little's law: 40 / latency), but that is unmeasured.
3. **Provider-side limits and cost were not exercised:** OpenAI rate limits,
   429 behaviour under concurrency, token cost per analysis, and the cost of
   amplification under real transient failures.
4. **`/health` shares the saturated threadpool.** `/health` is also a sync
   `def` route. When 40+ slow analyses hold every worker thread, health checks
   may queue behind them. The health ladder here ran on an idle server, so
   this effect is untested.
5. **fd growth from unclosed clients:** per-request `OpenAI` clients are never
   explicitly closed. Open fds scaled with C (about 360 at C=64) and stayed
   bounded in these short runs, but long-run behaviour is untested.
6. **Measurement confounders:**
   - The load client and fake provider share the host (32 vCPUs) and the
     QuoteCheck process can burn up to 23 cores, so some host contention
     plausibly inflates the high-C numbers.
   - The closed-loop generator under-represents open-arrival queueing.
   - WSL2 virtualization, and the ascending-ladder order in a warm process.

## Decision Gate A

> **What, if anything, does SCALE-001 evidence justify changing next?**

**First meaningful capacity constraint:** on the OpenAI execution path,
per-request `OpenAI` client construction (SSL context and CA bundle load)
is a major local throughput constraint under concurrency. With the 250 ms fake provider, throughput plateaued at about 35–41 analyses/s despite additional concurrency. CPU cost per request rose sharply under thread contention.
The implicit anyio 40-thread limit, which also acts as the only aggregate
provider-concurrency bound, is the second constraint. It binds once C > 40,
and it will dominate at realistic multi-second provider latencies.

**Evidence:** Observed fact items 2, 3 and 4, read together:

- flat provider-loop latency, with extra time only outside the loop;
- CPU per request growing about 25×;
- the isolated construction diagnostic reproducing the same throughput
  ceiling and core burn;
- peak in flight pinned at 40.

**Still unproven:**

- whether the magnitude holds on Railway's hardware and OpenSSL;
- real TLS, DNS and provider latency;
- OpenAI rate-limit and cost behaviour;
- `/health` starvation under saturation;
- long-run fd behaviour.

**Smallest next scalability change worth considering (candidate, not
implemented):**

- Construct the OpenAI client **once per process and reuse it**, keeping
  exactly the current timeout, `max_retries=0` and retry loop. The client is
  thread-safe.
- Then rerun this same harness and workloads for a before/after comparison.
- CLAUDE.md lists this as a SCALE-001 non-goal, so it needs its own ticket.
- That ticket must reason explicitly about the httpx connection-pool limits a
  shared client introduces. Those limits become a *new* implicit concurrency
  bound, and they interact with the anyio cap.

**Not yet justified:**

- An explicit provider-concurrency limiter or admission/overload policy should
  be decided only *after* client reuse, measured with the harness extended to
  multi-second fake latencies. Today its effect would be masked by the
  construction ceiling.
- Queues, workers, Redis, replicas, and async rewrites have no supporting
  evidence at this stage.
