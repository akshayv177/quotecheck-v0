# SCALE-004 — Explicit Provider Admission Control: Before/After Evidence and Decision Gate D

Ticket: `docs/tickets/SCALE-004-provider-admission-control.md`

## Raw evidence

- `benchmarks/results/SCALE-004-before/` — the pre-SCALE-004 backend.
- `benchmarks/results/SCALE-004-after/` — the admission build.
- `SCALE-004-after/report_tables.py` recomputed every table below from the full raw files; its output is `report_tables.out`.
- `SCALE-004-after/diag_rejection_log.json` records event-loop costs, from `python -m benchmarks.diag_rejection_log`.
- Console logs are `run_console.log` in each directory.
- **Removed before commit:** the four `SCALE-004-after/server/` logs of the two zero-backoff scenarios (app-run JSONL and uvicorn access logs; 116 MB total). Nothing reads them to reproduce the report.
  - Their reconciliation outcome is in `trials.jsonl`: `log_records`, `log_provider_attempts`, `reconciled`.
  - Each request's logged `provider_attempts` (0 for all 116,648 zero-backoff rejections) was recorded in `requests.jsonl`.
  - Their sizes and sha256 prefixes are listed in the review bundle.

**What is in Git (evidence retention).** SCALE-004 was executed with full request-level and server evidence. That full evidence was used for report generation (`report_tables.py`), reconciliation, `stats --check` and Decision Gate D. Before branch publication, the generated bulk was omitted from Git:

- `requests.jsonl`, `health_load_requests.jsonl` and `server/`, in both `SCALE-004-before/` and `SCALE-004-after/`.
- Their sha256 hashes and byte sizes are in `benchmarks/results/SCALE-004_RAW_EVIDENCE_MANIFEST.txt`. The full raw evidence is retained outside the repository.

Git keeps the compact evidence: `env.json`, `scenarios.jsonl`, `trials.jsonl`, `summary.json`, `health_summary.json`, `health_probes.jsonl`, `provider_attempts.jsonl`, `run_console.log`, `diag_rejection_log.json`, `report_tables.py` / `report_tables.out`, plus the benchmark harness and workload definitions.

- A fresh clone reproduces the experiment by rerunning the harness (commands in `benchmarks/README.md`).
- Exact replay of *this* run from request-level events (`stats --check`, `report_tables.py`) requires the separately retained raw archive. The `stats --check` results below were verified against the full evidence before compaction; the compact committed bundle alone does not guarantee them.

## Scope of these numbers

- **Setup.** One local WSL2 host (32 logical CPUs, 7 GiB), loopback fake provider, one uvicorn process (`--loop asyncio --http h11`), and ₹0 provider spend.
- **Isolation.** The public deployment was never contacted, and no OpenAI credential was used.
- **What the numbers are not.** They are controlled observations of QuoteCheck's own overload behaviour. They are not production SLAs, and not Railway, OpenAI latency or OpenAI rate-limit figures.

## Instrument integrity

Both runs used byte-identical harness files:

| file | sha256 prefix |
|---|---|
| `run_capacity.py` | `484c1a9f…` |
| `stats.py` | `13f353e4…` |
| `fake_provider.py` | `9f35ae00…` (the corrected SCALE-003 fake) |
| `workloads.py` | `ef8e426a…` |

- The same workload, host and session were used for both runs.
- **before** ran from a detached worktree of `v1/scalability` @ `1e7f2ed`, with the new harness files copied in. The harness launches uvicorn from its own repository root, so the backend under test was the unmodified one (`git diff -- backend` empty there).
- **after** ran from the SCALE-004 working tree.
- The only difference between the two invocations is `--gate-cap`: 40 for before, 32 for after. It sets the provider in-flight level the health gate waits for. An enforced budget of 32 can never reach the old gate's 40.
- No trial was suspend-flagged, and no host-safety guard tripped.
- Every point reconciled, and the attempt join held for every point. For every rejected request, QuoteCheck logged `provider_attempts=0` **and** the fake saw no attempt carrying its marker.
- Before compaction, `stats --check` reproduced `summary.json` and `health_summary.json` for both runs from the full raw evidence, and still for SCALE-001, SCALE-002 and SCALE-003.
- Elapsed time: before 1548.5 s, after 1059.9 s.

---

## 0. What changed

This is a **coupled execution-shape change**, not only a budget. There are three parts:

1. **Pre-threadpool explicit admission.**
   - `POST /analyze` became an `async def` wrapper.
   - In OpenAI mode it calls `provider_admission.try_acquire()` on the event loop, after `AnalyzeRequest` validation and **before** any threadpool dispatch.
   - If no slot is free, it returns an immediate `capacity_exceeded`: HTTP 503, `retryable: true`, zero provider calls, and one JSONL record with `provider_attempts: 0`.
   - The budget is `OPENAI_MAX_CONCURRENT_ANALYSES = 32`, a fixed per-process code constant. A test enforces that it stays below anyio's 40 tokens.
   - 32 is a locally evidence-backed v1 per-process budget. It is **not** a claim about real OpenAI or Railway capacity. N processes or replicas would give N × 32.
2. **Narrow async route and error boundary.** Because the endpoint is now async, two worker-token uses disappear. Neither is caused by the budget:
   - FastAPI's `response_model` validation runs on the event loop (`serialize_response(is_coroutine=True)`), not in a second threadpool call.
   - The `QuoteCheckError` handler is `async` and no longer takes a worker token on failures. This is also what lets a rejection bypass the threadpool entirely.
3. **Unchanged synchronous provider body.** `_analyze_sync` still runs in `run_in_threadpool` and is unchanged: the analyzer, the ≤ 2-attempt retry loop, validation and logging. One admitted request holds one slot for its whole thread call, retry included.

**Slot release (implementation detail, corrected during implementation).**

- The admitted work runs in its own task behind `asyncio.shield`, and the slot is released in that task's `finally`.
- The planning checkpoint assumed that anyio's `abandon_on_cancel=False` would make a plain `try/finally` around `await run_in_threadpool(...)` safe. A direct check showed otherwise: a native asyncio `Task.cancel()` resumes the awaiting coroutine immediately, and its `finally` runs while the worker thread is still inside the provider call.
- In the installed stack, nothing cancels a request task on client disconnect. Uvicorn's graceful-shutdown timeout (`uvicorn/server.py:289`) does. The shield keeps the slot held until the thread has actually finished.
- `test_cancelled_request_holds_its_slot_until_the_thread_finishes` covers this.

**Still on anyio's 40-token worker pool:**

- admitted analysis bodies (≤ 32 in OpenAI mode);
- Demo analysis bodies (Demo takes no slot);
- `GET /health`;
- the `RequestValidationError` 422 handler.

---

## 1. Burst: one simultaneous wave of C requests (5 trials per point)

The table shows `ok` p95 and rejection latency in ms. "pre" and "post" are the pre-provider and post-provider phases (p95) of admitted requests.

| provider | C | build | admitted ok | rejected | ok p95 | rej p50 / p95 / max | pre p95 | post p95 | peak in-flight | rejections done before 1st provider end |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---|
| 3 s | 32 | before | 160 | 0 | 3179 | – | 140 | 47 | 32 | – |
| 3 s | 32 | after | 160 | 0 | 3170 | – | 136 | 42 | 32 | – |
| 3 s | 40 | before | 200 | 0 | 3217 | – | 166 | 56 | 40 | – |
| 3 s | 40 | after | 160 | 40 | 3270 | 61.7 / 175.0 / 177.3 | 227 | 50 | **32** | yes, 5/5 |
| 3 s | 64 | before | 320 | 0 | **6323** | – | **3306** | 121 | 40 | – |
| 3 s | 64 | after | 160 | 160 | 3211 | 64.4 / 141.6 / 191.1 | 198 | 23 | **32** | yes, 5/5 |
| 5 s | 64 | before | 320 | 0 | **10304** | – | **5291** | 123 | 40 | – |
| 5 s | 64 | after | 160 | 160 | 5272 | 98.6 / 171.8 / 176.3 | 252 | 30 | **32** | yes, 5/5 |

- **Before.** At C=64, 24 of every 64 requests wait a whole provider period in anyio's FIFO before their provider call starts.
- **After.** Exactly 32 are admitted and 32 are rejected. Every rejection completes before the *first* admitted provider call ends, in every trial.
- **Rejection latency in a burst** is tens of ms up to ~190 ms. The same order is seen in the burst *dispatch* cost that admitted requests pay in **both** builds (pre-provider p50 ~93–165 ms at C=32–64): one event loop is parsing, validating and dispatching a simultaneous wave. That is the relevant yardstick. It is not the provider period (3–5 s), which the before build made excess requests wait.

## 2. Sustained closed loop at 5 s (4 provider periods, 3 trials; rejected clients resend after 0.25 s)

| C | build | ok rps | ok p50 / p95 / max | rejected | rej p50 / p95 / max | pre p95 | post p95 | peak in-flight | server CPU ms/req |
|---|---|---:|---|---:|---|---:|---:|---:|---:|
| 32 | before | 6.23 | 5102 / 5252 / 5355 | 0 | – | 120 | 136 | 32 | 6.48 |
| 32 | after | 6.15 | 5159 / 5355 / 5460 | 0 | – | 168 | 193 | 32 | 8.57 |
| 40 | before | **7.73** | 5137 / 5299 / 5362 | 0 | – | 150 | 151 | 40 | 6.54 |
| 40 | after | 6.16 | 5144 / 5336 / 5421 | 1889 | 1.5 / 3.4 / 177.5 | 223 | 153 | **32** | 2.49 |
| 64 | before | 6.93 | **9678 / 10386 / 15379** | 0 | – | **5295** | **5120** | 40 | 5.58 |
| 64 | after | 6.21 | 5074 / 5312 / 5416 | 7667 | 1.4 / 10.7 / 179.9 | 191 | 129 | **32** | 1.29 |
| 64, zero backoff | before | 6.86 | 9615 / 10399 / 15429 | 0 | – | 5294 | 5111 | 40 | 5.68 |
| 64, zero backoff | after | 6.18 | 5178 / 5316 / 5339 | **116,648** | 15.1 / 17.8 / 216.6 | 198 | 122 | **32** | 0.51 |

CPU ms/req divides by all requests issued, rejections included.

- **Admitted latency** stops growing with excess demand. At C=64 the p50 goes from 9.7 s to 5.1 s, and the max from 15.4 s to 5.4 s.
- **Waiting outside the provider call** falls on both sides:
  - pre-provider p95 goes from 5295 to 191 ms;
  - post-provider p95 goes from 5120 to 129 ms.
- **Attribution of the post-provider change.** It comes from the coupled change, not the budget alone:
  - in the before build, post-provider waiting was the second worker-token acquisition for response validation, queued behind oversubscribed provider work;
  - the async endpoint removes that acquisition;
  - the 32-slot budget removes the oversubscription it queued behind.

  This experiment doesn't separate those two contributions, because the implementation couples them.
- **Throughput cost.** Completed throughput under saturation falls from 7.73 rps (before, C=40, the full 40 tokens busy) or 6.93 rps (before, C=64, oversubscribed) to about 6.2 rps. The ceiling is now 32 / provider latency (6.4 rps at 5 s) instead of 40 / latency.
  - This is the deliberate price of reserving 8 worker tokens.
  - At C=40 it is about 20% below the before build's best point.

## 3. `/health` under analysis load (40 sequential probes per point, in ms)

| scenario | C | before p50 / p95 / max | after p50 / p95 / max | after load: rejected (rej p95) |
|---|---|---|---|---|
| idle (3 s / 5 s runs) | 0 | 1.5 / 1.9 / 2.1 · 1.4 / 1.6 / 1.6 | 1.8 / 2.2 / 2.5 · 1.9 / 2.5 / 3.2 | – |
| 3 s | 32 | 1.6 / 3.9 / 7.4 | 1.9 / 3.6 / 15.2 | 0 |
| 3 s | 40 | 36.7 / **2160.9** / 2483.9 | 1.9 / 27.8 / 32.6 | 606 (6.3) |
| 3 s | 64 | 350.2 / **2683.8** / 2800.0 | 1.8 / 6.7 / 118.9 | 2306 (13.9) |
| 5 s | 32 | 1.4 / 1.8 / 16.8 | 1.9 / 4.3 / 17.4 | 0 |
| 5 s | 40 | 20.2 / **4582.2** / 4671.6 | 2.0 / 3.5 / 30.0 | 635 (2.8) |
| 5 s | 64 | 410.5 / **4645.8** / 4884.0 | 1.8 / 3.9 / 167.7 | 2556 (10.6) |
| 5 s, zero-backoff load | 64 | 222.3 / **4685.3** / 4775.2 | **70.8 / 155.4 / 222.1** | 39,377 (18.5) |

- All 800 probes (400 per build) returned 200.
- In the after build, probe-time provider in-flight never exceeded 32.
- With admission in place, `/health` no longer couples to provider latency at C ≥ 40:
  - p95 falls from 2.2–4.7 s to 3.5–27.8 ms;
  - max falls from 2.5–4.9 s to 30–168 ms.
- **Zero-backoff rejection storm** (clients resend a rejected request immediately):
  - the load generator drives about 1,500–1,950 rejections/s;
  - the server process runs at about **0.95 of a core** in the sustained trials and 0.80 over the health point, versus 0.04 before;
  - `/health` p50 rises to 71 ms and p95 to 155 ms. That is still prompt, but no longer idle-like.

## 4. Retry under saturation (3 s, C = 64)

| scenario | build | admitted outcome | rejected | admitted p95 | rej p95 | post p95 | peak in-flight | attempts / admitted |
|---|---|---|---:|---:|---:|---:|---:|---:|
| fail-first burst | before | 320 ok | 0 | **12279** | – | 126 | 40 | 2.00 |
| fail-first burst | after | 160 ok | 160 | 6304 | 235.1 | 30 | **32** | 2.00 |
| fail-first sustained | before | 288 ok, 5.24 rps | 0 | **12346** | – | **6006** | 40 | 2.00 |
| fail-first sustained | after | 193 ok, 4.61 rps | 4561 | 6415 | 10.8 | 165 | **32** | 2.00 |
| fail-always sustained | before | 291 × 503 `provider_unavailable`, p50 6400 | 0 | **12391** | – | **6004** | 40 | 2.00 |
| fail-always sustained | after | 195 × 503 `provider_unavailable`, p50 6141 | 4565 | 6442 | 7.4 | 216 | **32** | 2.00 |

- **Retries are contained.** Each admitted request makes exactly 2 attempts inside one slot. Aggregate provider in-flight never exceeds 32, even with every admitted request retrying.
- **Rejections stay clean.** Rejected requests make 0 attempts, confirmed by both QuoteCheck's log and the fake.
- **Outage behaviour.** A persistent outage now returns `provider_unavailable` after about two provider periods (p95 6.4 s), instead of up to four (12.4 s).
- **Overload is distinguishable from outage.** Excess work gets an immediate `capacity_exceeded` that can't be confused with the provider's 503. It has a different `code`, it has `provider_attempts: 0`, and there is no `cause_type` or `provider_status` in the log.

## 5. Event-loop cost of the new on-loop work (`diag_rejection_log.json`, n = 5000, in-process ASGI)

| item | mean | p50 | p95 | max |
|---|---:|---:|---:|---:|
| full rejection, with synchronous JSONL log | 367 µs | 333 µs | 558 µs | 42.3 ms (one outlier) |
| full rejection, log call replaced by a no-op | 295 µs | 268 µs | 506 µs | 1.6 ms |
| the log call alone (same record, same file) | 38 µs | 30 µs | 74 µs | 0.49 ms |
| `response_model` validation + serialization of one 3.6 KB `QuoteCheckResult` | 30 µs | 25 µs | 51 µs | 0.30 ms |

- **Synchronous rejection logging** is about 20% of an in-process rejection's cost.
  - At the storm's ~1,950 rejections/s that is about 0.07–0.14 s of loop time per second.
  - The rest of the ~0.95 core is HTTP/ASGI/JSON handling of the rejections themselves, plus client connection handling.
- **Response validation on the loop** is about 1 ms for a whole wave of 32 responses.

**Conclusion.** Neither is the cause of the rejection-latency tail. In the rejection storm, the event loop itself is the saturated resource.

**Rejection tail, unattributed.**
- About 1.2–1.5% of sustained-run rejections take more than 50 ms, with a max of 177–217 ms.
- About 60% of those overlap a provider attempt start or end, when up to 32 worker threads run SDK request/response work under the GIL. The rest are unattributed.
- Also possible, unmeasured: client-side GIL contention (up to 64 load threads in one Python process), WSL scheduling, and the single-process fake.

---

## Decision Gate D

### A. Does QuoteCheck now enforce an explicit provider concurrency bound?

**OBSERVED FACT**
- Peak provider in-flight is **32 in every after-run point**: burst, sustained, zero-backoff, health load, fail-first and fail-always retry. It was 40 in the before build at C ≥ 40.
- Attempts per admitted request are 1.00 (success) and 2.00 (retry scenarios).
- Every rejected request made zero attempts, according to both QuoteCheck's log and the fake's per-marker attempt log. The attempt join held for every point.
- Deterministic tests (`eval/tests/test_provider_admission.py`, 13 tests, no timing thresholds) prove:
  - the cap;
  - fail-fast ordering;
  - that a rejection needs no worker token;
  - retry inside one slot;
  - release on all 12 terminal paths;
  - that cancellation holds the slot until the thread ends;
  - Demo isolation;
  - the rejection body and log;
  - a 50-thread `Barrier` race on the primitive.
- Mutation checks showed that each of three regressions fails its designed test:
  - dropping the shield;
  - a sync error handler;
  - admission inside the worker thread.

**Scope of the bound.** It is **per process**. N uvicorn workers or replicas would give N × 32.

### B. Does excess demand become visible and bounded?

**OBSERVED FACT**
- Excess demand now gets `503 {"code": "capacity_exceeded", "retryable": true}` promptly:
  - sustained with backoff: p50 1.4–1.5 ms, p95 3–11 ms;
  - simultaneous bursts: p50 56–99 ms, p95 ≤ 181 ms (235 ms for the retry burst);
  - zero-backoff storm: p95 18 ms.
- The before build instead made that work wait silently up to a whole provider period (pre-provider p95 3.3 s / 5.3 s at C=64) before eventually returning 200.
- In bursts, every rejection completed before the first admitted provider call ended (all 25 trials with rejections).
- Each rejection writes one sanitized JSONL record with these fields:
  - `failure_category: "capacity_exceeded"`;
  - `provider_attempts: 0`;
  - `error: "capacity_exceeded: provider admission budget full (32/32 in flight)"`.
- That record is distinguishable from provider 429 and 5xx records by code, status and attempt count.

**SUPPORTED INFERENCE.** Burst rejection latency reflects event-loop dispatch of a simultaneous wave, which admitted requests pay equally in both builds. It is not waiting for capacity.

**Stop condition checked: not triggered.**
- Synchronous rejection logging costs about 38 µs per rejection (p95 74 µs), about 20% of a rejection, and fail-fast holds under the zero-backoff storm.
- No background logging was added.

### C. Does the chosen budget preserve service responsiveness?

**OBSERVED FACT**
- **With backoff.** While `/analyze` demand exceeds the budget (C=40/64, 3 s and 5 s):
  - `/health` p50 is 1.8–2.0 ms (idle 1.4–1.9);
  - p95 is 3.5–27.8 ms;
  - max is 30–168 ms;
  - before, p95 was 2.2–4.7 s.
- **Zero-backoff storm.** `/health` is p50 71 / p95 155 / max 222 ms, against 4.7 s p95 before. The server process runs at about 0.95 of a core.

**SUPPORTED INFERENCE**
- Keeping admitted provider-bound work below the 40-token limiter decouples `/health` from provider latency. Admission alone was sufficient; no `/health` architecture change was needed.
- The remaining degradation in the storm is event-loop CPU saturation by rejection traffic. It is not worker-token waiting: `/health` still gets a token, and a rejection needs none.

**Price.** Completed throughput under saturation is capped at 32 / provider latency: about 6.2 rps at 5 s, versus 7.7 rps with all 40 tokens busy before. That is about 20% lower peak completed throughput, traded for bounded latency, visible overload and a responsive health endpoint.

### D. Are retries safely contained inside the budget?

**OBSERVED FACT**
- Under fail-first and fail-always saturation at C=64, provider in-flight peaks at 32.
- Each admitted request makes exactly 2 attempts, and rejected requests make 0.
- Fail-first admitted p95 goes from 12.3 s to 6.3–6.4 s. A persistent outage returns `provider_unavailable` in about 6.1–6.4 s instead of up to 12.4 s.
- `/health` responsiveness during retry load wasn't separately probed. Retry points were not combined with health probes, for the same reason as SCALE-003.
- A retry halves admitted throughput (4.61 vs 6.2 rps), because a slot is held for two provider periods. This is the intended accounting: one slot per request across its whole attempt sequence.

### E. What remains unresolved for v1 scalability?

These are recommendations only; none of them is implemented in SCALE-004.

1. **Rejection-storm load on the event loop.**
   - A client that resends immediately can drive about 2k rejections/s and saturate the single event loop (/health p95 155 ms).
   - Public rate limiting, per-client backoff, or `Retry-After` guidance are the relevant levers. None was added, because there is no evidence-based value.
   - The current frontend never auto-resubmits.
2. **Budget configurability.** 32 is a fixed local measurement point. Real-provider latency distribution, OpenAI rate limits and Railway host characteristics are unmeasured, so a configurable budget (validated, and below the thread limiter) is a later decision.
3. **Observability and cost signals.**
   - Rejections are countable from JSONL: `failure_category == "capacity_exceeded"` and `provider_attempts == 0`.
   - There is no aggregate metric, admitted-in-flight gauge, or cost-per-analysis signal.
4. **Rejection-latency tail.** 1.2–1.5% of rejections take more than 50 ms (max ~220 ms). This is partly coincident with provider wave transitions (GIL contention from worker threads). It is otherwise unattributed.
5. **Unexplained 5 s / C=32 CPU difference.** The after build uses about +2.5 ms server CPU per request and about +40–60 ms pre-provider p50 at 5 s / C=32 (no rejections involved), consistently across 8 trials. It does not appear at 3 s, and it is not connection churn (one new connection per trial in both builds). It is unattributed.
6. **Other sync handlers.** The `RequestValidationError` 422 handler and `/health` still take worker tokens. A flood of invalid requests competes with `/health` for the 8 unreserved tokens. That flood was not measured.
7. **Final recharacterization.** Open-arrival load, a real-provider sanity check (only if approved and paid), and TLS/keep-alive behaviour under saturation (SCALE-003 finding 3) remain open.
8. **Multi-process topology.** The budget is per process; any change to workers or replicas multiplies aggregate provider concurrency.
