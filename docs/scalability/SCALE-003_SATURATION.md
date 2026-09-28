# SCALE-003 — Saturation, Queueing & Health: Characterization and Decision Gate C

Ticket: `docs/tickets/SCALE-003-saturation-health-characterization.md`

Raw evidence: `benchmarks/results/SCALE-003-saturation/`
- the harness's own files;
- `diag_keepalive.json`;
- `report_tables.py` and `report_tables.out` (every table below is recomputed from raw files by that script);
- `run_console.log`.

SCALE-001 and SCALE-002 results are untouched.

> **Scope of these numbers.** One local WSL2 host (32 logical CPUs, 7 GiB),
> a loopback fake provider, zero provider spend. The public deployment was never
> contacted, and no OpenAI credential was used. These are controlled observations
> of QuoteCheck's saturation behaviour. They are **not** production SLAs, Railway
> capacity figures, or OpenAI latency or capacity claims.
>
> **Instrument generation.** SCALE-001/002 used the original fake provider. SCALE-003
> uses the corrected one (`TCP_NODELAY`, below). Exact provider-loop latencies across
> those generations are **not directly interchangeable**: SCALE-002 after-run loop
> times carry about +40 ms per attempt that SCALE-003 times do not.

---

## 0. What SCALE-003 changed (benchmark tooling only)

- **Fake repair:**
  - `benchmarks/fake_provider.py` sets `TCP_NODELAY` on every accepted socket, in its existing `get_request` hook.
  - `tcp_nodelay=False` exists only so `benchmarks/diag_keepalive.py` can reproduce the old instrument.
- **Per-attempt timeline:**
  - The fake logs `{marker, t_start, t_end, status}` for every attempt on `time.monotonic()` (`GET /__attempts`).
  - The harness's `perf_counter` is the same clock. `env.json` records both as `clock_gettime(CLOCK_MONOTONIC)`, and the run refuses to start otherwise.
  - Every SCALE-003 request carries a unique marker, so each request is split into:
    - **pre-provider**: client send → first attempt start;
    - **provider span**;
    - **post-provider**: last attempt end → client receive.
  - Nothing was added to QuoteCheck.
- **New experiments:** `saturation`, `health` and `retry_sat` in `run_capacity.py`, plus summary helpers in `stats.py`.
- **Runtime:** `git diff v1/scalability -- backend/ frontend/` is empty.

## 1. The execution path being saturated (traced from installed source)

Versions: fastapi 0.128.6, starlette 0.52.1, anyio 4.12.1, uvicorn 0.40.0 (`--loop asyncio --http h11`, one process).

| step | where | uses a worker token? |
|---|---|---|
| accept, HTTP parse, `AnalyzeRequest` body validation | asyncio event loop | no |
| `def analyze` endpoint: messages/schema, blocking `responses.create` (≤ 2 attempts), result validation, JSONL log | `run_in_threadpool` → `anyio.to_thread.run_sync` | **token #1**, held for the whole provider time |
| `response_model=QuoteCheckResult` response validation | `fastapi/routing.py:281`: `run_in_threadpool(field.validate, …)` for sync endpoints | **token #2**, re-acquired after the endpoint returns |
| `_quotecheck_error_handler` (failure path) | a sync `def`; starlette `_exception_handler.py:61` uses `run_in_threadpool` | **token #2** on the failure path |
| `def health` | `run_in_threadpool` | **one token** |

- All of these share **one process-wide anyio default `CapacityLimiter(40)`**.
- Its waiters are woken in **FIFO** order (`_wait_queue.popitem(last=False)`).
- QuoteCheck sets no limit of its own. The 40 is a framework default, not a QuoteCheck capacity budget.

## 2. Fake-provider repair evidence

**Unit tests (deterministic, no latency thresholds):**
- `TCP_NODELAY` is non-zero on an accepted socket, and zero only with `tcp_nodelay=False`;
- one persistent connection serves 5 attempts with `connections_accepted == 1`;
- the attempt log records the marker, times and status, and `reset` clears it;
- the fail-first HTTP sequence is 503 → 200 → 503 per marker.

The existing counter, fail-first, fail-always, SDK and `/analyze`-path tests pass unchanged.

**Runtime diagnostic** (`python -m benchmarks.diag_keepalive`): 35 sequential attempts, 0 ms injected latency, in-process fake. Output is in `diag_keepalive.json`.

| case | fake `TCP_NODELAY` | connections | p50 ms | p95 ms |
|---|---|---:|---:|---:|
| real SDK, one shared client (QuoteCheck's SCALE-002 shape) | off (old) | 1 | **43.98** | 44.91 |
| real SDK, one shared client | **on** | 1 | **1.00** | 1.48 |
| real SDK, new client per attempt | off | 35 | 1.93 | 9.22 |
| real SDK, new client per attempt | on | 35 | 1.84 | 7.56 |
| raw `http.client` keep-alive | off | 1 | 44.01 | 44.17 |
| raw `http.client` keep-alive | on | 1 | 0.37 | 0.61 |

**Runtime continuity at 1 s, C=1** (provider-loop p50 / client p50):

| run | provider-loop p50 | client p50 |
|---|---:|---:|
| SCALE-001 (fresh connections) | 1007 | 1028 ms |
| SCALE-002-after (reused, old fake) | 1052 | 1056 ms |
| **SCALE-003 (reused, repaired fake)** | **1013** | **1017 ms** |

**OBSERVED FACT:** the ~40 ms reused-connection penalty is gone. Connection reuse is preserved: one connection is accepted per trial, and that one is the harness's own stats call.

## 3. Method

- **Runs:**
  - one run, `SCALE-003-saturation`, started 2026-09-28 07:48 UTC, 1784 s;
  - `git_commit e8bdce7` with `git_dirty: true` (uncommitted tooling);
  - `env.json` records the sha256 of each harness file.
- **Load and statistics:** the unchanged SCALE-001 load model:
  - a closed loop with C persistent connections;
  - N = max(4·C, 16) and 3 trials per point for `saturation` / `retry_sat`;
  - a burst warm-up of 2·C, excluded;
  - nearest-rank percentiles;
  - per-trial reconciliation of fake attempts against QuoteCheck's logged `provider_attempts`.
  - Every trial **reconciled**, and every trial's attempts **joined** (per-request fake attempts == logged `provider_attempts`).
- **Excluded trials:** three trials were flagged `suspend_suspected` and are excluded, per the harness rule:
  - 3 s C=32 trial 1 (wall-vs-monotonic skew +933 s);
  - 3 s C=40 trial 3 (+3339 s);
  - fail-first C=64 trial 3 (−1.1 s).

  Large positive skews mean wall-clock time advanced far beyond the monotonic clock, i.e. the host/WSL VM was suspended. The excluded trials' numbers match their siblings (e.g. 10.16 vs 10.23 rps), so the exclusion changes nothing material. `summary.json` still contains them, as `stats --check` requires.
- **Guards:** no host-safety or escalation guard fired. Peak RSS was 96 MB, host memory stayed ample, and the maximum pooled p95 was 12.4 s against the 30 s guard.
- **Derived columns:**
  - "loop" is QuoteCheck's own logged `latency_ms`: the provider retry-loop time on success, the whole handler body on failure;
  - "pre" and "post" are the timeline phases above;
  - "mean in-flight" is the time-averaged number of provider attempts in flight over the trial;
  - "time ≥ 40" is the fraction of trial wall time with provider in-flight ≥ 40;
  - "CPU ms/req" is Σ server CPU s / Σ requests.

## 4. Experiment A — slow-provider saturation

| lat | C | ok/fail | rps | e2e p50 | e2e p95 | e2e max | loop p50 | pre p95 | post p95 | mean in-flight | time ≥ 40 | CPU ms/req | peak thr | RSS MB | fds |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 s | 1 | 48/0 | 0.98 | 1017 | 1026 | 1028 | 1013 | 4 | 3 | 1.0 | 0 | 6.3 | 2 | 75 | 9 |
| 1 s | 16 | 192/0 | 15.19 | 1040 | 1098 | 1110 | 1025 | 47 | 49 | 15.2 | 0 | 5.0 | 17 | 78 | 40 |
| 1 s | 32 | 384/0 | 28.60 | 1096 | 1199 | 1251 | 1075 | 106 | 103 | 28.7 | 0 | 5.3 | 33 | 84 | 72 |
| 1 s | 40 | 480/0 | **34.46** | 1132 | 1262 | 1342 | 1108 | 142 | 138 | 34.5 | 0.72 | 5.6 | 41 | 88 | 88 |
| 1 s | 48 | 576/0 | 33.83 | 1171 | 2183 | 3048 | 1086 | 917 | 720 | 33.9 | 0.67 | 5.3 | 41 | 89 | 96 |
| 1 s | 64 | 768/0 | 33.66 | 1615 | 2366 | 3441 | 1070 | 1275 | 1089 | 33.7 | 0.72 | 5.2 | 41 | 91 | 113 |
| 3 s | 16 | 192/0 | 5.25 | 3036 | 3094 | 3107 | 3021 | 45 | 39 | 15.8 | 0 | 4.9 | 17 | 78 | 39 |
| 3 s | 32 | 256/0 | 10.20 | 3119 | 3218 | 3272 | 3097 | 129 | 120 | 30.6 | 0 | 6.0 | 33 | 84 | 72 |
| 3 s | 40 | 320/0 | **12.61** | 3127 | 3284 | 3341 | 3106 | 141 | 150 | 37.9 | 0.89 | 6.1 | 41 | 88 | 88 |
| 3 s | 48 | 576/0 | 12.27 | 3161 | 6150 | 6398 | 3074 | 2861 | 2715 | 36.8 | 0.75 | 5.7 | 42 | 90 | 97 |
| 3 s | 64 | 768/0 | 11.90 | 5618 | 6366 | 9410 | 3063 | 3286 | 3023 | 35.7 | 0.81 | 5.3 | 41 | 92 | 113 |
| 5 s | 16 | 192/0 | 3.17 | 5038 | 5111 | 5128 | 5023 | 51 | 46 | 15.8 | 0 | 5.6 | 17 | 78 | 41 |
| 5 s | 32 | 384/0 | 6.23 | 5101 | 5230 | 5272 | 5078 | 117 | 114 | 31.2 | 0 | 6.3 | 33 | 82 | 72 |
| 5 s | 40 | 480/0 | **7.75** | 5124 | 5286 | 5328 | 5099 | 153 | 148 | 38.8 | 0.94 | 6.0 | 41 | 87 | 88 |
| 5 s | 48 | 576/0 | 7.47 | 5177 | 10172 | 15124 | 5096 | 4940 | 4739 | 37.4 | 0.77 | 5.8 | 43 | 90 | 97 |
| 5 s | 64 | 768/0 | 7.24 | 9731 | 10336 | 15303 | 5025 | 5250 | 4939 | 36.2 | 0.83 | 5.0 | 41 | 91 | 113 |

Per-trial throughput is tight: every point's three trials are within ±1% of each other. Attempts are exactly 1.00 per request everywhere, and peak provider in-flight is exactly 40 at every C ≥ 40.

**Where the non-provider time sits** (fraction of requests waiting more than half a provider period, L/2):

| lat | C | mean non-provider ms | pre > L/2 | post > L/2 | both | neither |
|---|---:|---:|---:|---:|---:|---:|
| 1 s | 40 | 133 | 0 | 0 | 0 | 1.00 |
| 1 s | 48 | 303 | 0.115 | 0.050 | 0.002 | 0.837 |
| 1 s | 64 | 700 | 0.341 | 0.199 | 0.030 | 0.490 |
| 3 s | 40 | 135 | 0 | 0 | 0 | 1.00 |
| 3 s | 48 | 625 | 0.108 | 0.059 | 0 | 0.833 |
| 3 s | 64 | 1813 | 0.359 | 0.203 | 0.022 | 0.460 |
| 5 s | 40 | 126 | 0 | 0 | 0 | 1.00 |
| 5 s | 48 | 975 | 0.102 | 0.064 | 0.002 | 0.835 |
| 5 s | 64 | 2901 | 0.358 | 0.204 | 0.007 | 0.444 |

**OBSERVED FACT:**

1. **Throughput plateaus at C=40 and declines slightly above it.**
   - 1 s: 34.5 → 33.7 rps. 3 s: 12.6 → 11.9. 5 s: 7.75 → 7.24 rps (C=40 → C=64).
   - The plateau scales as 1 / provider latency. C=40 throughput × loop p50 = 38.2 (1 s), 39.2 (3 s), 39.5 (5 s) calls in flight on average.
2. **Up to C=40 there is no hidden queue.** Non-provider time is 126–135 ms on average at every latency, and no request waits more than L/2 before or after its provider call.
3. **Above 40, latency grows in whole provider periods, not gradually.**
   - At C=64, e2e p50 is 1.6 s (1 s), 5.6 s (3 s) and 9.7 s (5 s), versus a loop p50 of 1.07 / 3.06 / 5.03 s.
   - e2e max reaches about 3× the provider latency (15.3 s at 5 s).
   - Mean waiting outside provider execution at C=64: 0.70 s, 1.81 s, 2.90 s. It grows proportionally with provider latency.
4. **Waiting happens on both sides of the provider call.** At C=64:
   - about 35% of requests wait more than half a provider period **before** their first attempt (for token #1);
   - about **20% wait more than half a provider period *after* their provider call has already finished**, with a completed, validated result in hand, before the response is sent;
   - post-provider p95 is 1.09 s, 3.02 s and 4.94 s — about one full provider period.
5. **No failures.**
   - 0 of 6,960 measured saturation requests failed (and 0 of the 3,172 requests behind the health probes). No timeouts and no errors.
   - The overload signal is latency alone.
6. **Resources stay small and flat.**
   - CPU is 4.9–6.3 ms per request, and the process never exceeds 0.19 cores.
   - RSS ≤ 92 MB, fds ≤ 113.
   - Threads are 41 at every C ≥ 40, with transient 42–43 at C=48.
7. **New provider connections appear at 5 s latency with C ≥ 48** (6–24 new per trial), and in `retry_sat` at 3 s, C=64 (21–31 new per trial). At C ≤ 40, and at every 1 s and 3 s success point, there are none. New = `connections_accepted` − 1 harness stats call.
8. **The provider-loop latency rise under concurrency persists after the Nagle repair.** At C ≥ 32 the loop p50 is about 60–95 ms above the C=1/16 value at 1 s, and about 55–75 ms at 3 s and 5 s.

**SUPPORTED INFERENCE:**

- **Token #1 is the bound: the anyio limiter.** Evidence: in-flight is pinned at 40, thread count is 41, CPU is idle, and there are no errors. Throughput above 40 is capped at about 40 / provider latency per process.
- **Post-provider waiting comes from token #2.** The response-model validation step re-queues behind waiting new requests in the same FIFO limiter. With synchronized closed-loop waves, a finished request can then sit for most of a provider period. Evidence:
  - the waiting sits after the provider call has ended;
  - it appears only when waiters exist (C > 40);
  - it is about one provider period at p95;
  - the code path (§1) shows exactly one more `run_in_threadpool` on that side.
- **Why throughput dips above C=40.** Freed tokens are handed first to waiting validation jobs and new requests. That small reordering, plus the closed-loop drain tail, lowers mean provider occupancy from about 38–39 to about 36 (time ≥ 40: 0.83 vs 0.94 at 5 s).
  - The effect is small (−2 to −6%), but it means oversubscription **reduces** completed work rather than merely delaying it.
- **The new connections are httpx keep-alive expiry.**
  - Pooled connections sat idle for more than `keepalive_expiry = 5.0 s` (httpx default) while their threads' next provider call waited for a token, and were replaced.
  - This only happens once waits exceed 5 s: at 5 s latency, or with a 2 × 3 s retry.
  - Locally it costs nothing. On the real TLS path it would mean occasional reconnects under saturation.

**REMAINING HYPOTHESIS:**

- The cause of the roughly 60–95 ms loop rise at C ≥ 32. It is no longer Nagle. Candidates: the fake's single-process `ThreadingHTTPServer`, GIL contention while parsing 40 concurrent responses, or three processes sharing one host.
- The transient 42–43 peak thread count at C=48 is plausibly anyio's idle-worker turnover (`MAX_IDLE_TIME = 10 s`). It was not investigated.
- The closed-loop generator synchronizes requests into waves. Under open arrivals the *distribution* of pre/post waits would differ. The *mechanism* (FIFO re-queue for token #2) would not.

## 5. Experiment B — `/health` under active saturation

**Design** (`Run.health`):
- For each latency class, a fresh server; 40 idle probes; then for each C, sustained closed-loop `/analyze` load at C.
- **Saturation confirmation:**
  1. Poll the **fake's** `/__stats` (a separate process, so this uses no QuoteCheck token) until provider in-flight ≥ min(C, 40). The gate was reached at every point.
  2. Wait one further provider period.
  3. Send 40 sequential probes: fresh connection each, at most one outstanding, seeded 0.2–0.6 s gaps, 60 s timeout.
- **Post hoc tagging:** each probe gets the **exact** provider in-flight count at its send instant (from the fake's attempt intervals) and the number of analysis requests outstanding at the client.
- Every probe at C ≥ 32 was sent with exactly C analysis requests outstanding (`analysis_outstanding_at_send_min` = C), so no probe landed in a load gap.

| lat | C | probes | status | p50 ms | p95 ms | max ms | timeouts | provider in-flight at send |
|---|---:|---:|---|---:|---:|---:|---:|---|
| 3 s | idle | 40 | 200 × 40 | 1.9 | 3.0 | 3.2 | 0 | 0 × 40 |
| 3 s | 32 | 40 | 200 × 40 | 1.6 | 3.2 | 7.1 | 0 | 32 × 37, 31 × 2, 8 × 1 |
| 3 s | 40 | 40 | 200 × 40 | 30.5 | **2426** | 2609 | 0 | 40 × 24, 39 × 9, 38 × 5, 29, 18 |
| 3 s | 64 | 40 | 200 × 40 | 454.7 | **2768** | 2866 | 0 | 40 × 17, 39 × 17, 36–38 × 4, 12, 6 |
| 5 s | idle | 40 | 200 × 40 | 1.8 | 3.0 | 3.1 | 0 | 0 × 40 |
| 5 s | 32 | 40 | 200 × 40 | 2.2 | 3.1 | 10.8 | 0 | 32 × 38, 26, 22 |
| 5 s | 40 | 40 | 200 × 40 | 43.2 | **4379** | 4549 | 0 | 40 × 24, 39 × 11, 38 × 3, 21, 2 |
| 5 s | 64 | 40 | 200 × 40 | 295.4 | **4696** | 4885 | 0 | 40 × 18, 39 × 18, 35, 38, 6, 1 |

**Probes sent while provider in-flight was exactly 40 (the provider-saturated-confirmed subset):**

| lat | C | n | p50 ms | p95 ms | max ms | probe latency − time to next provider completion (min / median / max ms) |
|---|---:|---:|---:|---:|---:|---|
| 3 s | 40 | 24 | 2007 | 2468 | 2609 | 1 / 2 / 3 |
| 3 s | 64 | 17 | 2401 | 2866 | 2866 | 119 / 504 / 617 |
| 5 s | 40 | 24 | 3853 | 4491 | 4549 | 1 / 3 / 18 |
| 5 s | 64 | 18 | 4483 | 4885 | 4885 | 106 / 352 / 4549 |

The analysis load behind the probes (`health_load_requests.jsonl`) had zero failures. Peak threads were 41 and peak provider in-flight 40 at C=40/64.

**OBSERVED FACT:**

1. **The C=32 control:** heavy analysis load alone does not slow `/health`. With 8 tokens free, p95 is 3.1–3.2 ms, the same as idle.
2. **At C=40 and C=64:**
   - every probe returned **HTTP 200**, with no timeouts;
   - the p95 reached **2.4–2.8 s at 3 s provider latency and 4.4–4.7 s at 5 s**, i.e. 0.8–0.94 × the provider latency;
   - no probe exceeded one provider period.
3. **In the at-40 subset,** probe latency at C=40 equals the time until the next provider call finished, plus 1–18 ms. At C=64 the probe finished 0.1–0.6 s after that completion (4.5 s in one 5 s case).
4. **The low "all probes" p50 at C=40** (31–43 ms) comes from probes sent while in-flight was 38–39. Those are the brief gaps between waves where a token was momentarily free.

**SUPPORTED INFERENCE:**
- The link between probe latency and provider completions shows that `/health` is waiting for **a worker token**, not for the event loop or for CPU. A health check runs only when an analysis frees a token.
- At C=40 it gets the very next free token.
- At C > 40 the FIFO limiter also serves analysis requests and response-validation jobs that queued ahead of it.

**Provider-saturated vs threadpool-saturated.**
- "Provider in-flight == 40" is a *confirmed* observation: it comes from the fake's timeline.
- "All 40 worker tokens held" is an *inference*. It rests on:
  - the limiter being 40 (framework default, §1);
  - server threads = 41;
  - the timing link above.

  Tokens are not observed directly. At C=64, the probes sent at provider in-flight 1–12 took 44–69 ms rather than about 2 ms. The limiter was still serving queued non-provider work (validation jobs, requests starting their calls), so provider in-flight alone underestimates threadpool occupancy.

**Operational interpretation (no policy judgment).**
- `/health` stays *correct*: every probe returned 200.
- It is *not independent* of analysis load. Its latency tracks provider latency once analysis concurrency reaches 40.
- Under slow-provider saturation, a health check with a timeout below the provider latency would plausibly time out while the process is otherwise healthy.
- **REMAINING HYPOTHESIS:** whether that matters in production depends on the host's health-check timeout and whether health checks run after deploy only or continuously. Neither was measured or configured here.

## 6. Experiment C — retry under saturation (3 s provider, fail-first vs success)

| C | mode | ok/fail | rps | vs success | e2e p50 | e2e p95 | e2e max | loop p50 | attempts/req | retry gap p50 | mean in-flight | pre > L/2 | post > L/2 | new conns |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 32 | success | 256/0 | 10.20 | – | 3119 | 3218 | 3272 | 3097 | 1.00 | – | 30.6 | 0 | 0 | 0 |
| 32 | fail-first | 384/0 | 5.23 | **0.51×** | 6070 | 6225 | 6285 | 6057 | 2.00 | 6 ms | 31.4 | 0 | 0 | 0 |
| 40 | success | 320/0 | 12.61 | – | 3127 | 3284 | 3341 | 3106 | 1.00 | – | 37.9 | 0 | 0 | 0 |
| 40 | fail-first | 480/0 | 6.51 | **0.52×** | 6082 | 6286 | 6348 | 6070 | 2.00 | 4 ms | 39.1 | 0 | 0 | 0 |
| 64 | success | 768/0 | 11.90 | – | 5618 | 6366 | 9410 | 3063 | 1.00 | – | 35.7 | 0.359 | 0.203 | 0 |
| 64 | fail-first | 512/0 | 6.04 | **0.51×** | 11710 | 12345 | 18256 | 6022 | 2.00 | 2 ms | 36.3 | 0.344 | 0.219 | 23–28 |
| 64 | **fail-always** | 0/384 | 0 (5.3 × 503/s) | – | 11773 | 12374 | 18230 | 6041 | 2.00 | 5 ms | 31.8 | 0.391 | 0.151 | 30–31 |

(New connections = `connections_accepted` − 1 harness stats call.)

**OBSERVED FACT:**

- **Throughput halves.** Fail-first halves completed throughput at every C (0.51–0.52×).
- **Latency doubles.** e2e p50 is about 6.07 s below the cap and 11.7 s at C=64 (vs 5.6 s success). e2e max is 18.3 s, about 6 provider periods.
- **Retry mechanics are unchanged:**
  - attempts per request are exactly **2.00**, and there was never a third attempt;
  - the gap between attempts is 2–6 ms (no backoff);
  - the whole 2 × 3 s retry runs while holding the same worker token (loop p50 ≈ 6.05 s).
- **Fail-always spot check (C=64, 384 requests):**
  - every request got HTTP **503** `provider_unavailable` after exactly 2 attempts;
  - users waited e2e p50 **11.8 s** (max 18.2 s) for the error;
  - the process spent the same token time as fail-first (loop ≈ 6.04 s) and produced **zero** successes;
  - 503s were emitted at 5.3/s.
- **Post-provider waiting on the failure path.** The fail-always post-provider p95 is 5.9 s, the same shape as success. The sync exception handler re-queues for a token just as response validation does.

**SUPPORTED INFERENCE:**
- Under saturation, a transient-failure retry costs **one full extra provider period of worker-token time**. It is therefore a **2× reduction in per-process analysis capacity** for as long as failures persist.
- The capacity loss is in addition to the 2× provider attempts (and potential 2× cost on a billed path).
- A persistent provider outage at C > 40 turns the process into a 12-second 503 generator that holds all 40 tokens. For that whole period `/health` behaves as in §5, with waits governed by the 6 s token-hold time.
- **REMAINING HYPOTHESIS:** the `/health` behaviour during a provider outage was not probed directly. The mechanism predicts health waits up to about 6 s.

---

## Decision Gate C

### A. What happens when demand exceeds current synchronous execution capacity?

**Measured, for C ≤ 64 at 1/3/5 s provider latency:**

- **Throughput** plateaus at about 40 / provider latency: 34.5 / 12.6 / 7.75 rps at C=40. It declines 2–6% as demand rises further (33.7 / 11.9 / 7.24 at C=64).
- **Excess demand becomes waiting, never failure.**
  - Waiting outside provider execution averages 0.70 / 1.81 / 2.90 s at C=64 (vs about 0.13 s at C ≤ 40).
  - It arrives in whole provider periods: e2e p50 9.7 s and max 15.3 s at 5 s latency.
  - It **scales linearly with provider latency**. A slower provider does not just lower throughput; it multiplies every waiter's delay.
- **The waiting sits on both sides of the provider call.** About 35% of requests wait before it. About 20% wait more than half a provider period *after* their result is ready, re-queuing for the response-validation token.
- **Nothing tells a client this is happening.** No 503 or 429 is returned, no log field records it, and every request eventually gets 200. CPU (≤ 6.3 ms/request, ≤ 0.19 cores), memory (≤ 96 MB) and fds (≤ 113) stay far from any limit.

### B. Does saturation interfere with `/health`?

**Yes, measurably, once analysis concurrency reaches the 40-token limit. Not below it.**

- **Status:** HTTP 200 on all 320 probes; no timeouts at a 60 s client timeout.
- **Latency:**
  - idle 1.8–1.9 ms p50 and 3.0 ms p95;
  - C=32 control unchanged (p95 ≤ 3.2 ms);
  - at C=40/64, p95 2.4–2.8 s (3 s provider) and 4.4–4.7 s (5 s provider);
  - in the provider-at-40 subset, p50 2.0–2.4 s and 3.9–4.5 s.
- **Mechanism (supported inference):** `/health` shares the FIFO worker-token limiter with provider-bound analysis. It waits for the next analysis to free a token, and behind queued analysis work when C > 40.
- **Interpretation:** liveness answers stay correct but become as slow as the provider. Whether that breaks a platform health check depends on unmeasured platform settings.
- **This is separable from the analysis-capacity question.** It exists because `/health` is a sync route sharing the limiter, not because of any analysis policy. It is a candidate for a separate small correction, to be decided at Gate C.

### C. What is the capacity effect of the existing retry?

With a transient first-attempt failure at 3 s provider latency:
- each request holds its worker token for 2 provider periods;
- throughput is 0.51–0.52× of success at every C;
- latency is 2×, with e2e p50 11.7 s at C=64.

A persistent outage gives the same token cost with zero successes: 11.8 s-p50 503s. The retry bound itself is correct: exactly 2 attempts and no third.

Under saturation, the retry is primarily a **capacity multiplier**. Its cost is paid by every other waiting request, not only by the request that retries.

### D. What is the smallest next intervention justified?

These are requirements derived from the measured failure mode. No mechanism is chosen here, and none is implemented.

1. **Evidence now supports a QuoteCheck-owned, explicit bound on concurrent provider work.**
   - The measured failure mode is *unbounded silent waiting whose duration is a multiple of provider latency*, with no overload signal and a slight throughput *loss* under oversubscription.
   - A mechanism must satisfy:
     - **(a)** an explicit, named provider-concurrency budget, decoupled from the framework's 40-token default and sized with provider rate limits and cost in view;
     - **(b)** a *bounded, observable* overload behaviour for demand above it. That could be a bounded wait with a deadline, or immediate controlled rejection. The evidence does not prefer one: waiting preserves eventual success but at 2–3 provider periods of latency; rejection gives fast feedback but turns load into errors;
     - **(c)** accounting of the retry's second attempt against the same budget. A retrying request consumes 2× budget-time, so the policy must be sized or deadline-checked with that in mind;
     - **(d)** a log/metric field that records waiting or rejection, which does not exist today.
2. **`/health` isolation is a separate, smaller correction candidate.**
   - The evidence shows `/health` latency coupled to provider latency solely through the shared limiter. The C=32 control rules out event-loop or CPU contention.
   - Any analysis budget smaller than the limiter would also relieve it, but only incidentally. Making it independent of analysis load is a distinct decision.
3. **Response-path token re-acquisition is an observed contributor, not yet a candidate by itself.**
   - `response_model` validation and the sync exception handler each re-enter the same limiter, which produces the post-provider waits.
   - A concurrency budget enforced around provider calls would not by itself remove this re-queue, if the endpoint stays a sync route under the same limiter. Whatever mechanism is chosen should be evaluated against this pre/post split using this same harness and workload.
4. **Not justified by this evidence:**
   - raising the anyio limit: it would move an unchosen bound and raise aggregate provider demand and cost, with no overload policy;
   - adding workers or replicas;
   - async conversion;
   - queues, Redis or worker services.

   CPU, memory, fds and the connection pool are nowhere near limits. The problem is the absence of an owned policy, not a lack of raw capacity.

**Unproven, and needed before sizing any budget:**
- real OpenAI latency distribution and its rate limits / 429 behaviour at 40-way concurrency;
- Railway vCPU and health-check timeout settings;
- open-arrival traffic shape;
- TLS reconnect cost when keep-alive expires under saturation;
- the ~60–95 ms loop inflation at C ≥ 32.
