# SCALE-002 — Shared OpenAI Client: Recharacterization and Decision Gate B

Ticket: `docs/tickets/SCALE-002-shared-openai-client.md`

Raw evidence:
- `benchmarks/results/SCALE-002-before/` (fake + retry, pre-change code)
- `benchmarks/results/SCALE-002-after/` (all experiments, post-change code)
- `benchmarks/results/SCALE-001-baseline/` (untouched)

Harness: the unchanged SCALE-001 harness (`benchmarks/`). The only change to it is metadata, described below.

> **Scope of these numbers.** One local WSL2 machine, a loopback fake provider,
> zero provider spend. The public deployment was never contacted. These are
> comparative results about QuoteCheck code. They are **not** production SLAs,
> Railway capacity figures, or OpenAI capacity claims.

---

## What changed

`backend/core/openai_analyzer.py` now holds **one process-wide synchronous `OpenAI` client**. The previous behaviour built a new client for every request.

**How the client is built:**
- `_get_client()` builds it lazily, on the first OpenAI-mode request that passes configuration validation.
- A double-checked `threading.Lock` makes simultaneous cold requests build exactly one client.
- The constructor arguments are identical to before: `api_key`, the validated per-attempt `timeout`, and `max_retries=0`.

**What is unchanged:**
- the retry loop, classification and `provider_attempts`;
- validation, prompt, schema, API, logging;
- `app.py`, `config.py`.

There is no shutdown hook. The client lives for the whole process.

**Benchmark provenance (metadata only):**
- `env.json` no longer carries `"ticket": "SCALE-001"`. It now records `"harness_origin": "SCALE-001"` and `"measurement_ticket": "SCALE-002"`, the latter via a new `--ticket` flag.
- Workloads, ladders, request counts, statistics, guards and topology are byte-for-byte unchanged.
- Both SCALE-002 runs used this same harness code.

## Method

- **Topology and settings:** identical to SCALE-001.
  - One `uvicorn backend.app:app --loop asyncio --http h11` process, fresh per scenario.
  - Closed-loop load client with C persistent connections.
  - Loopback fake Responses endpoint reached via the SDK's `OPENAI_BASE_URL`, with a sentinel key and model.
  - 3 trials per point, N = 200 (Demo) or max(4·C, 16) (fake/retry).
  - Nearest-rank percentiles on the pooled sample.
  - Warm-up excluded; per-trial reconciliation of fake attempts against QuoteCheck's logged `provider_attempts`.
- **Runs, same host, same session, 2026-09-28:**

  | run | code | experiments | start (UTC) | elapsed |
  |---|---|---|---|---|
  | `SCALE-002-before` | analyzer = committed `4e33bfc` (sha256 `b30f47a3…`) | fake + retry | 06:56:30 | 362.3 s |
  | `SCALE-002-after` | analyzer with shared client (sha256 `a0d29296…`) | demo + fake + retry | 07:03:20 | 378.6 s |

  Both runs record `git_commit 4e33bfc` with `git_dirty: true`. `git_commit` therefore can't tell them apart, so the analyzer hash is recorded here instead. The data also shows which code each run exercised: *before* shows about 20 ms CPU/request and one new provider connection per request, which is per-request construction. *After* shows about 5 ms and zero new connections.
- **Comparison:** the primary comparison is **fresh before (B) vs after (A)**, which removes host/day drift. SCALE-001 (S1) is shown as a sanity check; B reproduces S1 closely.
- **Guards and reconciliation:**
  - No stop guard fired in any run.
  - Every fake/retry trial reconciled in both runs.
- **Discarded trials:** two *before* trials were flagged `suspend_suspected`, with wall-vs-monotonic skew of −1.004 s and −1.097 s (WSL wall-clock steps):
  - `fake_lat1s` C=48 trial 1;
  - `retry_fail_first_250ms` C=1 trial 2.

  Following the harness rule, they are **excluded** from the tables below: those two B points use 2 trials. Their numbers were indistinguishable from the sibling trials (e.g. 28.26 vs 28.31 / 28.57 rps; 1.75 vs 1.75 rps), so the exclusion changes nothing material. `summary.json` itself still contains them, as `stats --check` requires.
- **How the tables were built:** a small script recomputes every point with the harness's own `benchmarks.stats.summarize` from raw `requests.jsonl` / `trials.jsonl`. The script source is in the review bundle.
- **Column definitions:**
  - "new conns/req" = (fake `connections_accepted` − 1 harness stats call) / requests.
  - "CPU ms/req" = Σ server CPU s / Σ requests.
  - "cores busy" = Σ server CPU s / Σ wall s.

---

## Headline comparison (fake provider, `normal` workload)

| scenario | C | rps B → A | p50 ms B → A | p95 ms B → A | CPU ms/req B → A | cores busy B → A | peak in-flight B → A | peak RSS MB B → A | peak fds B → A |
|---|---:|---|---|---|---|---|---|---|---|
| 250 ms | 1 | 3.65 → 3.33 | 274 → 300 | 279 → 303 | 19.4 → 5.2 | 0.07 → 0.02 | 1 → 1 | 86 → 75 | 22 → 9 |
| 250 ms | 16 | 34.59 → **50.69** | 359 → 302 | 661 → 361 | 148.7 → 5.3 | 5.14 → 0.27 | 16 → 16 | 187 → 79 | 146 → 40 |
| 250 ms | 32 | 39.38 → **83.78** | 863 → 359 | 1069 → 451 | 422.6 → 5.5 | 16.63 → 0.46 | 32 → 32 | 300 → 86 | 283 → 72 |
| 250 ms | 64 | 46.56 → **102.09** | 1116 → 514 | 2147 → 863 | 468.9 → 5.7 | 21.83 → 0.58 | 40 → 40 | 381 → 92 | 336 → 112 |
| 1 s | 32 | 21.07 → **28.21** | 1464 → 1103 | 1803 → 1228 | 334.4 → 5.9 | 7.04 → 0.17 | 32 → 32 | 332 → 84 | 323 → 72 |
| 1 s | 64 | 29.86 → **32.89** | 1853 → 1738 | 3385 → 2374 | 215.5 → 5.9 | 6.42 → 0.19 | 40 → 40 | 398 → 91 | 365 → 112 |
| retry fail-first 250 ms | 32 | 31.60 → **48.42** | 995 → 614 | 1284 → 781 | 333.7 → 7.1 | 10.54 → 0.34 | 32 → 32 | 257 → 90 | 246 → 72 |

**Failures:** zero in every success-scenario point, before and after. Fail-always stayed at 0/48 in both runs, all HTTP 503 `provider_unavailable`, exactly 2 attempts each.

**Attempts:** 1 per request in every success scenario and exactly 2 per request in every retry scenario, before and after. There was never a third attempt.

---

## A finding the fresh control exposed: a +40 ms keep-alive artifact in the fake provider

**Observed fact:**
- After the change, per-attempt provider-loop latency at low C rose by about 40 ms:
  - 250 ms: p50 255 → 296 ms;
  - 1 s: 1005 → 1052 ms.
- Client latency at C=1 rose correspondingly, and C=1 throughput fell by about 9%.
- Retry arithmetic pins this to **reused connections**. Before, only a retry's second attempt reused its connection (2×255 + 40 ≈ 553 ms observed). After, both attempts do (2×(255 + 40) ≈ 592 ms observed).

**Focused diagnostic** (scratch script, source and output in the review bundle): real SDK, in-process fake with 0 ms latency, 35 sequential requests.

| case | p50 ms | connections |
|---|---:|---:|
| fresh client per request (pre-SCALE-002 shape) | 1.6 | 40 |
| shared client (SCALE-002 shape) | **44.0** | 1 |
| shared client + `TCP_NODELAY` on the **fake server** socket | 1.1 | 1 |
| shared client + `TCP_NODELAY` on the **SDK client** socket | 44.0 | 1 |
| shared client + `TCP_NODELAY` both sides | 1.0 | 1 |

**Supported inference:**
- The ~40 ms comes from Nagle's algorithm on the **fake provider's** socket interacting with the client's delayed ACK. It is not a QuoteCheck or httpx cost.
- The cause: `http.server` sends the response headers and body in two writes, with no `TCP_NODELAY`.
- It never appeared in SCALE-001 because every request used a fresh connection, and Linux quick-ACKs at connection start.
- It is a **benchmark artifact that penalises only the after run**. Every *after* improvement below is therefore **understated**, not inflated.
- Per the SCALE-002 constraint, the fake was **not** changed. Fixing it is recorded as a prerequisite for the next measurement ticket.

**Remaining hypothesis:** whether the real OpenAI edge has a similar server-side write pattern is unknown. Setting `TCP_NODELAY` on the client would not help in any case, as the diagnostic shows.

---

## Connection-pool facts (pinned `openai==2.24.0`, `httpx==0.28.1`)

**Relevant defaults, read from installed source:**
- The SDK builds `SyncHttpxClientWrapper` with `DEFAULT_CONNECTION_LIMITS = httpx.Limits(max_connections=1000, max_keepalive_connections=100)` (`openai/_constants.py:11`), plus `follow_redirects=True`.
- httpx's `keepalive_expiry` defaults to **5.0 s**.
- QuoteCheck's float `timeout=30.0` becomes `httpx.Timeout(30.0)`, so connect, read, write **and pool-acquire** are each 30 s per attempt. This is unchanged from before, because the SDK applies the client's timeout per request.
- Before reusing an idle connection, httpcore discards it if the keep-alive time has expired or if the socket is readable (a server-initiated close) (`httpcore/_sync/http11.py:274-286`).
- The wrapper's `__del__` closes the pool. There is no explicit production close.

**Observed:**
- *Before:* every measured trial accepted `attempts + 1` connections for success scenarios (e.g. 257 for 256 attempts at C=64), and `requests + 1` for fail-first (a retry reused its request's connection).
- *After:* every measured trial in every fake/retry scenario accepted **exactly 1** connection, and that one is the harness's own stats call. QuoteCheck opened **zero** new provider connections during measurement. Its pooled keep-alive connections, up to 40, were established during warm-up and reused across requests and trials.
- Peak open fds at C=64 fell from 336 to 112.

**Supported inference:**
- The pool is **not** a bound at this scale: at most 40 connections are in use (one per worker thread), against a limit of 1,000.
- All in-use connections fit under `max_keepalive_connections=100`, so none were churned.
- No pool-acquire wait or `PoolTimeout` can occur below 1,000 concurrent attempts, and the 40-thread limiter caps attempts well below that.
- Nothing was tuned.

**Hypotheses for production (unmeasured):**
- A server-closed idle keep-alive connection can race a new request. That would surface as `APIConnectionError`, which is transient and would consume the request's single retry.
- httpcore's readability check narrows this window but cannot close it.
- The loopback fake never closes idle connections, so this path was not exercised.

---

## Capacity curve after the change

**Observed fact:**

1. **CPU per request is flat in C.** On every fake/retry scenario it holds at 4.4–7.9 ms per request from C=1 to C=64. Before, it grew from about 20 ms to about 470 ms at 250 ms / C=64. The QuoteCheck process now burns at most 0.58 cores; before, it burned up to 21.8.
2. **Scaling is near-ideal up to the thread cap.** At 250 ms, throughput tracks C / latency:
   - C=16: 50.7 rps against 16 / 0.302 s ≈ 53;
   - C=32: 83.8 against 32 / 0.359 ≈ 89.

   At 1 s:
   - C=16: 14.9 rps against 16 / 1.056 ≈ 15.2;
   - C=32: 28.2 against 32 / 1.103 ≈ 29.
3. **Peak provider calls in flight pin at exactly 40** at C=48 and C=64, in every trial of both runs. Peak server threads *after* are exactly 41 (40 workers + the event-loop thread) at C ≥ 48.
4. **Above 40, the extra requests queue invisibly in-process.** At 250 ms / C=64:
   - client p50 is 514 ms, while the server-logged provider loop is 340 ms;
   - the difference is time spent waiting for a worker thread;
   - there are no rejections or errors, only latency.
5. **Provider-loop latency rises modestly at C ≥ 32.** At 250 ms: p50 about 296 → 336–343 ms, p95 up to 478 ms. At 1 s: about 1048 → 1081–1085 ms.
6. **Resource use:**
   - peak RSS at C=64 fell from about 380–400 MB to about 91 MB;
   - peak fds from about 340–365 to 112;
   - peak threads from about 48 to 41.

**Supported inference:**

- **Above C=40, throughput is set by the anyio worker-thread limiter.** Throughput × provider-loop p50 gives the average provider calls in flight:
  - 102.1 × 0.340 ≈ 35 (250 ms, C=64);
  - 32.9 × 1.081 ≈ 36 (1 s, C=64).

  Both sit just under the hard 40 cap, with CPU near idle. The remaining headroom is plausibly closed-loop end-of-trial drain plus the small per-request work outside the provider loop.
- **At realistic provider latency this cap is the binding constraint.** Little's law gives a ceiling of about **40 / provider latency** analyses per second per process: about 40 rps at 1 s, about 8 rps at 5 s, about 4 rps at 10 s.

**Remaining hypothesis:**

- The loop-latency rise at C ≥ 32 (fact 5) is unattributed. Candidates:
  - the fake provider's single Python `ThreadingHTTPServer` serving about 40 keep-alive connections, with one JSON encode per response;
  - GIL contention among 40 QuoteCheck worker threads parsing responses;
  - the load client, fake and server sharing one host.

  It is small next to the thread cap and doesn't change the conclusion.

## Demo control (application spine, no provider)

Demo code is untouched by SCALE-002. The *after* Demo numbers match or slightly exceed SCALE-001 at every point:
- `short`: 841–1103 rps vs 795–958;
- `normal`: 599–755 vs 556–661;
- `near_max`: 107–114 vs 103–107;
- `/health`: 2104–2643 vs 1866–2640.

Across all 16,800 measured Demo requests there were zero failures.

There was no same-session *before* Demo run; the approved plan limited the control to fake + retry. The small uplift is therefore attributed to host/day drift and is **not** claimed as a SCALE-002 effect. The QC-HOTFIX stub change is the only Demo-path code difference since SCALE-001, and it affects only quotes that match three or more keyword blocks, which none of the workloads do. The control shows **no regression**.

---

## Decision Gate B

### A. Did process-level client reuse remove the SCALE-001 construction bottleneck?

**Yes.** The fresh control (B) and the after run (A) used the same host, session and harness.

**Observed fact:**

| measure | 250 ms, C=64 | 250 ms, C=32 | 1 s, C=32 | 1 s, C=64 |
|---|---|---|---|---|
| server CPU per request | 468.9 → 5.7 ms (≈ 82× less) | 422.6 → 5.5 ms | 334.4 → 5.9 ms | 215.5 → 5.9 ms |
| cores busy | 21.83 → 0.58 | 16.63 → 0.46 | | |
| throughput | 46.6 → 102.1 rps (2.19×) | 39.4 → 83.8 rps (2.13×) | 21.1 → 28.2 rps (+34%) | 29.9 → 32.9 rps (+10%) |
| p95 latency | 2147 → 863 ms | | 1803 → 1228 ms | 3385 → 2374 ms |

- The 250 ms plateau (about 35–47 rps from C=16 to C=64 in the fresh control) is gone.
- Retry fail-first at C=32: 31.6 → 48.4 rps.
- New provider connections per request: 1.00 → 0.00.
- Peak RSS at C=64: about 381 → 92 MB.

These gains are measured *despite* a +40 ms-per-attempt fake-provider artifact that penalises only the after run (see above). The true improvement is larger.

**Trade-off observed:** at C=1 the after run is about 26 ms slower (274 → 300 ms). The keep-alive diagnostic attributes this entirely to the fake provider's Nagle artifact. This is supported inference, not a QuoteCheck regression.

### B. What is now the first meaningful capacity constraint?

**The implicit anyio worker-thread limit (40 tokens), which is also QuoteCheck's only aggregate provider-concurrency bound.**

- Fact:
  - peak in-flight is pinned at exactly 40 at C=48 and 64;
  - server threads are exactly 41;
  - the process is near idle on CPU (≤ 0.58 cores);
  - excess requests wait invisibly for a thread (client p50 514 ms vs provider loop 340 ms at 250 ms / C=64).
- Inference: throughput ≈ 40 / provider latency once C > 40.
  - At 1 s this caps a process at about 40 rps (measured 32.9 closed-loop).
  - At realistic multi-second structured-output latency it would dominate completely.
- Fact: the constraint is **not**:
  - CPU (flat about 5 ms/request);
  - the HTTP connection pool (40 in use vs 1,000 max, zero new connections);
  - memory (91 MB).

This bound was chosen by nobody. It is a framework default, it is shared by `/analyze` (Demo and OpenAI) and `/health`, and it has no overload signal.

### C. What remains unproven?

This is all local, loopback, fake-provider evidence. None of the following was measured:

- **Railway runtime:**
  - vCPU count, CPU model and OpenSSL build.
  - Client reuse removes a per-request CPU cost that SCALE-001 measured at about 20 ms serially. On a small-vCPU host that saving is plausibly *more* important, but its production magnitude is unmeasured.
- **Real OpenAI latency and its distribution.** This decides whether 40 / latency is the practical ceiling.
- **TLS and DNS:**
  - Reuse should also avoid a TLS handshake and DNS lookup per request on the real path, but loopback HTTP cannot show that saving.
  - The idle keep-alive race described above is unexercised.
  - So is the real provider's server-side write/ACK behaviour.
- **Provider rate limits / 429 behaviour under 40-way concurrency**, and the cost per analysis and per successful analysis. Amplification is still up to 2 attempts per request, with aggregate attempts bounded only by the same 40 threads.
- **Production traffic shape:**
  - open-arrival bursts, which the closed-loop generator under-represents;
  - long-running process behaviour;
  - `/health` latency while 40 slow analyses hold every worker thread (still untested; SCALE-001 hypothesis 4).
- **Other residual unknowns:**
  - the cause of the modest provider-loop latency rise at C ≥ 32;
  - long-run fd behaviour. It is now bounded by a single pool rather than per-request clients, but that is still untested over hours.

### D. What is the smallest next intervention the evidence justifies? (Not implemented in SCALE-002.)

1. **Prerequisite measurement fix (harness only):** remove the fake provider's Nagle artifact, e.g. by setting `TCP_NODELAY` on its accepted sockets or writing headers and body in one send. Record it as a harness change so later before/after runs aren't biased against connection reuse.
2. **Then measure where the thread cap bites, before choosing a mechanism.** Extend the fake to multi-second latencies (the range structured outputs plausibly occupy) and add a `/health`-under-saturation probe. This quantifies:
   - queueing delay beyond 40 in flight;
   - `/health` starvation;
   - retry amplification against the cap.
3. **Candidate architecture, pending step 2:** replace the *incidental* 40-thread bound with a **deliberate, named provider-concurrency budget and an explicit overload behaviour** (bounded wait vs controlled 503). The budget would be owned by QuoteCheck and decoupled from the framework threadpool default. It must be sized with cost and provider rate limits in view.
   - Not justified yet: raising the anyio limit, adding workers or replicas, async conversion, queues or Redis.
   - Raising the thread limit would only move an unchosen bound and raise aggregate provider demand and cost with no overload policy.

---

## Full comparison tables

S1 = `SCALE-001-baseline`, B = `SCALE-002-before`, A = `SCALE-002-after`. Suspend-flagged trials are excluded (see Method). Demo scenarios have no fresh before run, so they are compared S1 vs A.

#### `fake_lat250ms`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 | 3 | 48/0 | 3.65 | 274 | 278 | 288 | 20.0 | 0.07 | 48 | 1 | 1.00 | 2 | 85 | 22 |
| 1 | B | 3 | 48/0 | 3.65 | 274 | 279 | 281 | 19.4 | 0.07 | 48 | 1 | 1.00 | 2 | 86 | 22 |
| 1 | A | 3 | 48/0 | 3.33 | 300 | 303 | 305 | 5.2 | 0.02 | 48 | 1 | 0.00 | 2 | 75 | 9 |
| 2 | S1 | 3 | 48/0 | 7.21 | 276 | 287 | 292 | 20.6 | 0.15 | 48 | 2 | 1.00 | 3 | 96 | 36 |
| 2 | B | 3 | 48/0 | 7.17 | 277 | 284 | 295 | 20.4 | 0.15 | 48 | 2 | 1.00 | 3 | 97 | 36 |
| 2 | A | 3 | 48/0 | 6.68 | 300 | 301 | 302 | 4.6 | 0.03 | 48 | 2 | 0.00 | 3 | 75 | 11 |
| 4 | S1 | 3 | 48/0 | 13.14 | 306 | 314 | 320 | 39.6 | 0.52 | 48 | 4 | 1.00 | 5 | 108 | 46 |
| 4 | B | 3 | 48/0 | 13.27 | 302 | 311 | 318 | 37.5 | 0.50 | 48 | 4 | 1.00 | 5 | 108 | 46 |
| 4 | A | 3 | 48/0 | 13.17 | 300 | 319 | 322 | 4.6 | 0.06 | 48 | 4 | 0.00 | 5 | 76 | 15 |
| 8 | S1 | 3 | 96/0 | 21.91 | 353 | 439 | 443 | 75.2 | 1.65 | 96 | 8 | 1.00 | 9 | 133 | 86 |
| 8 | B | 3 | 96/0 | 22.98 | 335 | 398 | 403 | 59.2 | 1.36 | 96 | 8 | 1.00 | 9 | 129 | 78 |
| 8 | A | 3 | 96/0 | 26.10 | 300 | 323 | 333 | 4.4 | 0.11 | 96 | 8 | 0.00 | 9 | 77 | 23 |
| 16 | S1 | 3 | 192/0 | 35.16 | 348 | 698 | 702 | 149.8 | 5.25 | 192 | 16 | 1.00 | 17 | 192 | 155 |
| 16 | B | 3 | 192/0 | 34.59 | 359 | 661 | 664 | 148.7 | 5.14 | 192 | 16 | 1.00 | 17 | 187 | 146 |
| 16 | A | 3 | 192/0 | 50.69 | 302 | 361 | 383 | 5.3 | 0.27 | 192 | 16 | 0.00 | 17 | 79 | 40 |
| 32 | S1 | 3 | 384/0 | 36.48 | 933 | 1144 | 1251 | 472.5 | 17.22 | 384 | 32 | 1.00 | 33 | 306 | 284 |
| 32 | B | 3 | 384/0 | 39.38 | 863 | 1069 | 1174 | 422.6 | 16.63 | 384 | 32 | 1.00 | 33 | 300 | 283 |
| 32 | A | 3 | 384/0 | 83.78 | 359 | 451 | 498 | 5.5 | 0.46 | 384 | 32 | 0.00 | 33 | 86 | 72 |
| 48 | S1 | 3 | 576/0 | 38.38 | 1177 | 1501 | 2340 | 580.3 | 22.26 | 576 | 40 | 1.00 | 43 | 364 | 358 |
| 48 | B | 3 | 576/0 | 44.32 | 999 | 1335 | 1924 | 485.1 | 21.50 | 576 | 40 | 1.00 | 42 | 347 | 338 |
| 48 | A | 3 | 576/0 | 96.92 | 418 | 771 | 1032 | 5.7 | 0.56 | 576 | 40 | 0.00 | 41 | 90 | 97 |
| 64 | S1 | 3 | 768/0 | 40.86 | 1315 | 2275 | 2678 | 576.0 | 23.51 | 768 | 40 | 1.00 | 46 | 377 | 360 |
| 64 | B | 3 | 768/0 | 46.56 | 1116 | 2147 | 2211 | 468.9 | 21.83 | 768 | 40 | 1.00 | 48 | 381 | 336 |
| 64 | A | 3 | 768/0 | 102.09 | 514 | 863 | 1199 | 5.7 | 0.58 | 768 | 40 | 0.00 | 41 | 92 | 112 |

Server-logged provider-loop latency (`latency_ms`), `fake_lat250ms`, p50 / p95 ms:

| C | S1 | B | A |
|---:|---|---|---|
| 1 | 256 / 258 | 255 / 260 | 296 / 299 |
| 2 | 257 / 261 | 258 / 262 | 296 / 297 |
| 4 | 257 / 266 | 258 / 266 | 297 / 304 |
| 8 | 258 / 277 | 259 / 275 | 296 / 306 |
| 16 | 256 / 275 | 256 / 274 | 292 / 331 |
| 32 | 277 / 359 | 279 / 340 | 336 / 421 |
| 48 | 267 / 371 | 264 / 336 | 343 / 478 |
| 64 | 259 / 382 | 259 / 339 | 340 / 465 |

#### `fake_lat1s`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 | 3 | 48/0 | 0.97 | 1028 | 1041 | 1044 | 22.3 | 0.02 | 48 | 1 | 1.00 | 2 | 85 | 22 |
| 1 | B | 3 | 48/0 | 0.97 | 1024 | 1052 | 1078 | 20.0 | 0.02 | 48 | 1 | 1.00 | 2 | 86 | 23 |
| 1 | A | 3 | 48/0 | 0.94 | 1056 | 1073 | 1077 | 6.2 | 0.01 | 48 | 1 | 0.00 | 2 | 75 | 9 |
| 2 | S1 | 3 | 48/0 | 1.94 | 1027 | 1046 | 1058 | 21.7 | 0.04 | 48 | 2 | 1.00 | 3 | 97 | 38 |
| 2 | B | 3 | 48/0 | 1.94 | 1029 | 1053 | 1058 | 21.5 | 0.04 | 48 | 2 | 1.00 | 3 | 97 | 36 |
| 2 | A | 3 | 48/0 | 1.89 | 1052 | 1072 | 1072 | 5.0 | 0.01 | 48 | 2 | 0.00 | 3 | 75 | 11 |
| 4 | S1 | 3 | 48/0 | 3.78 | 1045 | 1110 | 1112 | 30.0 | 0.11 | 48 | 4 | 1.00 | 5 | 108 | 46 |
| 4 | B | 3 | 48/0 | 3.80 | 1052 | 1074 | 1076 | 32.9 | 0.13 | 48 | 4 | 1.00 | 5 | 108 | 42 |
| 4 | A | 3 | 48/0 | 3.78 | 1052 | 1068 | 1075 | 4.6 | 0.02 | 48 | 4 | 0.00 | 5 | 76 | 15 |
| 8 | S1 | 3 | 96/0 | 7.32 | 1070 | 1155 | 1164 | 56.6 | 0.41 | 96 | 8 | 1.00 | 9 | 130 | 78 |
| 8 | B | 3 | 96/0 | 7.27 | 1092 | 1143 | 1162 | 61.8 | 0.45 | 96 | 8 | 1.00 | 9 | 134 | 79 |
| 8 | A | 3 | 96/0 | 7.49 | 1054 | 1077 | 1085 | 4.7 | 0.04 | 96 | 8 | 0.00 | 9 | 77 | 23 |
| 16 | S1 | 3 | 192/0 | 12.85 | 1117 | 1460 | 1487 | 167.0 | 2.15 | 192 | 16 | 1.00 | 17 | 197 | 157 |
| 16 | B | 3 | 192/0 | 13.44 | 1090 | 1385 | 1438 | 126.9 | 1.71 | 192 | 16 | 1.00 | 17 | 194 | 153 |
| 16 | A | 3 | 192/0 | 14.89 | 1056 | 1126 | 1168 | 5.3 | 0.08 | 192 | 16 | 0.00 | 17 | 80 | 40 |
| 32 | S1 | 3 | 384/0 | 21.54 | 1300 | 1820 | 1907 | 284.5 | 6.13 | 384 | 32 | 1.00 | 33 | 304 | 279 |
| 32 | B | 3 | 384/0 | 21.07 | 1464 | 1803 | 1897 | 334.4 | 7.04 | 384 | 32 | 1.00 | 33 | 332 | 323 |
| 32 | A | 3 | 384/0 | 28.21 | 1103 | 1228 | 1264 | 5.9 | 0.17 | 384 | 32 | 0.00 | 33 | 84 | 72 |
| 48 | S1 | 3 | 576/0 | 26.76 | 1611 | 2153 | 2855 | 308.2 | 8.23 | 576 | 40 | 1.00 | 44 | 369 | 344 |
| 48 | B | 2 | 384/0 | 28.44 | 1511 | 2241 | 2778 | 248.1 | 7.05 | 384 | 40 | 1.00 | 44 | 385 | 347 |
| 48 | A | 3 | 576/0 | 33.62 | 1174 | 2204 | 2497 | 6.0 | 0.20 | 576 | 40 | 0.00 | 41 | 89 | 96 |
| 64 | S1 | 3 | 768/0 | 28.66 | 1939 | 3556 | 3829 | 253.4 | 7.22 | 768 | 40 | 1.00 | 49 | 387 | 359 |
| 64 | B | 3 | 768/0 | 29.86 | 1853 | 3385 | 3563 | 215.5 | 6.42 | 768 | 40 | 1.00 | 48 | 398 | 365 |
| 64 | A | 3 | 768/0 | 32.89 | 1738 | 2374 | 3379 | 5.9 | 0.19 | 768 | 40 | 0.00 | 41 | 91 | 112 |

Server-logged provider-loop latency (`latency_ms`), `fake_lat1s`, p50 / p95 ms:

| C | S1 | B | A |
|---:|---|---|---|
| 1 | 1007 / 1021 | 1005 / 1033 | 1052 / 1069 |
| 2 | 1007 / 1024 | 1006 / 1033 | 1048 / 1069 |
| 4 | 1012 / 1056 | 1009 / 1032 | 1047 / 1065 |
| 8 | 1010 / 1025 | 1010 / 1029 | 1048 / 1069 |
| 16 | 1010 / 1045 | 1009 / 1024 | 1046 / 1089 |
| 32 | 1011 / 1053 | 1014 / 1077 | 1082 / 1188 |
| 48 | 1008 / 1053 | 1010 / 1055 | 1085 / 1226 |
| 64 | 1008 / 1073 | 1006 / 1044 | 1081 / 1207 |

#### `retry_fail_first_250ms`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 | 3 | 48/0 | 1.74 | 572 | 582 | 595 | 24.2 | 0.04 | 96 | 1 | 1.00 | 2 | 85 | 22 |
| 1 | B | 2 | 32/0 | 1.75 | 571 | 577 | 585 | 21.9 | 0.04 | 64 | 1 | 1.00 | 2 | 85 | 22 |
| 1 | A | 3 | 48/0 | 1.68 | 596 | 604 | 604 | 7.9 | 0.01 | 96 | 1 | 0.00 | 2 | 75 | 9 |
| 8 | S1 | 3 | 96/0 | 12.36 | 619 | 722 | 732 | 70.2 | 0.87 | 192 | 8 | 1.00 | 9 | 125 | 71 |
| 8 | B | 3 | 96/0 | 12.58 | 616 | 695 | 700 | 62.0 | 0.78 | 192 | 8 | 1.00 | 9 | 125 | 73 |
| 8 | A | 3 | 96/0 | 13.31 | 596 | 613 | 621 | 6.0 | 0.08 | 192 | 8 | 0.00 | 9 | 78 | 23 |
| 32 | S1 | 3 | 384/0 | 31.01 | 988 | 1355 | 1459 | 368.5 | 11.42 | 768 | 32 | 1.00 | 33 | 278 | 286 |
| 32 | B | 3 | 384/0 | 31.60 | 995 | 1284 | 1294 | 333.7 | 10.54 | 768 | 32 | 1.00 | 33 | 257 | 246 |
| 32 | A | 3 | 384/0 | 48.42 | 614 | 781 | 838 | 7.1 | 0.34 | 768 | 32 | 0.00 | 33 | 90 | 72 |

Server-logged provider-loop latency (`latency_ms`), `retry_fail_first_250ms`, p50 / p95 ms:

| C | S1 | B | A |
|---:|---|---|---|
| 1 | 553 / 561 | 553 / 558 | 592 / 600 |
| 8 | 555 / 572 | 555 / 571 | 592 / 600 |
| 32 | 557 / 637 | 555 / 634 | 600 / 719 |

#### `retry_fail_always_250ms`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | S1 | 3 | 0/48 | 0.00 | 601 | 619 | 621 | 40.6 | 0.27 | 96 | 4 | 1.00 | 5 | 95 | 37 |
| 4 | B | 3 | 0/48 | 0.00 | 599 | 615 | 615 | 37.9 | 0.25 | 96 | 4 | 1.00 | 5 | 96 | 40 |
| 4 | A | 3 | 0/48 | 0.00 | 595 | 604 | 606 | 5.8 | 0.04 | 96 | 4 | 0.00 | 5 | 74 | 15 |

Server-logged provider-loop latency (`latency_ms`), `retry_fail_always_250ms`, p50 / p95 ms:

| C | S1 | B | A |
|---:|---|---|---|
| 4 | 597 / 611 | 595 / 608 | 593 / 599 |

#### `demo_analyze_short`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 | 3 | 600/0 | 949.47 | 1 | 2 | 2 | 1.0 | 0.90 | – | – | – | 2 | 58 | 9 |
| 1 | A | 3 | 600/0 | 1103.16 | 1 | 1 | 2 | 0.8 | 0.90 | – | – | – | 2 | 58 | 8 |
| 2 | S1 | 3 | 600/0 | 957.75 | 2 | 3 | 3 | 1.2 | 1.12 | – | – | – | 3 | 58 | 10 |
| 2 | A | 3 | 600/0 | 1065.11 | 2 | 3 | 4 | 1.0 | 1.10 | – | – | – | 3 | 58 | 10 |
| 4 | S1 | 3 | 600/0 | 835.26 | 5 | 6 | 8 | 1.5 | 1.22 | – | – | – | 5 | 58 | 14 |
| 4 | A | 3 | 600/0 | 929.36 | 4 | 6 | 7 | 1.3 | 1.19 | – | – | – | 5 | 58 | 13 |
| 8 | S1 | 3 | 600/0 | 810.81 | 10 | 13 | 15 | 1.6 | 1.27 | – | – | – | 9 | 58 | 20 |
| 8 | A | 3 | 600/0 | 899.74 | 9 | 11 | 16 | 1.4 | 1.24 | – | – | – | 9 | 58 | 19 |
| 16 | S1 | 3 | 600/0 | 797.90 | 19 | 24 | 60 | 1.6 | 1.27 | – | – | – | 17 | 59 | 29 |
| 16 | A | 3 | 600/0 | 876.97 | 18 | 23 | 37 | 1.4 | 1.26 | – | – | – | 17 | 59 | 32 |
| 32 | S1 | 3 | 600/0 | 849.37 | 36 | 48 | 52 | 1.5 | 1.29 | – | – | – | 33 | 59 | 61 |
| 32 | A | 3 | 600/0 | 924.85 | 33 | 42 | 72 | 1.4 | 1.26 | – | – | – | 33 | 60 | 51 |
| 64 | S1 | 3 | 600/0 | 795.15 | 74 | 102 | 120 | 1.6 | 1.26 | – | – | – | 49 | 60 | 82 |
| 64 | A | 3 | 600/0 | 841.03 | 69 | 102 | 121 | 1.5 | 1.22 | – | – | – | 45 | 61 | 84 |

#### `demo_analyze_normal`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 | 3 | 600/0 | 652.86 | 1 | 2 | 3 | 1.5 | 0.95 | – | – | – | 2 | 58 | 9 |
| 1 | A | 3 | 600/0 | 754.61 | 1 | 2 | 2 | 1.2 | 0.93 | – | – | – | 2 | 58 | 8 |
| 2 | S1 | 3 | 600/0 | 661.43 | 3 | 4 | 6 | 1.6 | 1.08 | – | – | – | 3 | 58 | 11 |
| 2 | A | 3 | 600/0 | 680.67 | 3 | 4 | 5 | 1.5 | 1.04 | – | – | – | 3 | 58 | 10 |
| 4 | S1 | 3 | 600/0 | 599.04 | 6 | 9 | 11 | 1.9 | 1.16 | – | – | – | 5 | 58 | 14 |
| 4 | A | 3 | 600/0 | 635.58 | 6 | 8 | 11 | 1.8 | 1.13 | – | – | – | 5 | 58 | 12 |
| 8 | S1 | 3 | 600/0 | 602.39 | 13 | 16 | 24 | 2.0 | 1.20 | – | – | – | 9 | 58 | 19 |
| 8 | A | 3 | 600/0 | 619.14 | 13 | 16 | 22 | 1.9 | 1.17 | – | – | – | 9 | 58 | 19 |
| 16 | S1 | 3 | 600/0 | 590.28 | 26 | 34 | 74 | 2.0 | 1.21 | – | – | – | 17 | 58 | 29 |
| 16 | A | 3 | 600/0 | 618.30 | 25 | 33 | 48 | 1.9 | 1.18 | – | – | – | 17 | 58 | 30 |
| 32 | S1 | 3 | 600/0 | 613.91 | 51 | 61 | 90 | 2.0 | 1.21 | – | – | – | 33 | 59 | 57 |
| 32 | A | 3 | 600/0 | 637.50 | 49 | 64 | 84 | 1.8 | 1.17 | – | – | – | 33 | 59 | 46 |
| 64 | S1 | 3 | 600/0 | 556.41 | 109 | 148 | 186 | 2.1 | 1.19 | – | – | – | 45 | 61 | 86 |
| 64 | A | 3 | 600/0 | 598.84 | 101 | 142 | 161 | 1.9 | 1.17 | – | – | – | 53 | 61 | 83 |

#### `demo_analyze_near_max`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 | 3 | 600/0 | 102.84 | 10 | 11 | 12 | 9.0 | 0.92 | – | – | – | 2 | 58 | 8 |
| 1 | A | 3 | 600/0 | 114.04 | 9 | 9 | 16 | 8.4 | 0.96 | – | – | – | 2 | 58 | 8 |
| 2 | S1 | 3 | 600/0 | 106.62 | 19 | 21 | 30 | 9.3 | 0.99 | – | – | – | 3 | 58 | 10 |
| 2 | A | 3 | 600/0 | 109.92 | 18 | 23 | 29 | 9.0 | 0.99 | – | – | – | 3 | 58 | 10 |
| 4 | S1 | 3 | 600/0 | 102.51 | 39 | 52 | 67 | 10.0 | 1.02 | – | – | – | 5 | 58 | 13 |
| 4 | A | 3 | 600/0 | 106.76 | 37 | 50 | 67 | 9.4 | 1.01 | – | – | – | 5 | 58 | 13 |
| 8 | S1 | 3 | 600/0 | 104.98 | 75 | 95 | 133 | 9.9 | 1.04 | – | – | – | 9 | 58 | 19 |
| 8 | A | 3 | 600/0 | 106.61 | 75 | 94 | 140 | 9.6 | 1.02 | – | – | – | 9 | 58 | 19 |
| 16 | S1 | 3 | 600/0 | 104.48 | 153 | 184 | 281 | 10.0 | 1.04 | – | – | – | 17 | 58 | 32 |
| 16 | A | 3 | 600/0 | 106.56 | 149 | 191 | 254 | 9.7 | 1.03 | – | – | – | 17 | 59 | 30 |
| 32 | S1 | 3 | 600/0 | 105.78 | 302 | 386 | 568 | 10.0 | 1.06 | – | – | – | 33 | 59 | 54 |
| 32 | A | 3 | 600/0 | 108.14 | 295 | 364 | 592 | 9.8 | 1.06 | – | – | – | 33 | 60 | 63 |
| 64 | S1 | 3 | 600/0 | 103.11 | 622 | 750 | 827 | 10.3 | 1.06 | – | – | – | 44 | 62 | 96 |
| 64 | A | 3 | 600/0 | 107.61 | 597 | 755 | 797 | 9.8 | 1.06 | – | – | – | 53 | 63 | 93 |

#### `health_floor`

| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 | 3 | 600/0 | 1866.36 | 0 | 1 | 1 | 0.5 | 0.84 | – | – | – | 2 | 58 | 8 |
| 1 | A | 3 | 600/0 | 2103.66 | 0 | 1 | 1 | 0.4 | 0.84 | – | – | – | 2 | 58 | 8 |
| 2 | S1 | 3 | 600/0 | 2391.03 | 1 | 1 | 2 | 0.5 | 1.08 | – | – | – | 3 | 58 | 9 |
| 2 | A | 3 | 600/0 | 2516.63 | 1 | 1 | 2 | 0.4 | 1.05 | – | – | – | 3 | 58 | 9 |
| 4 | S1 | 3 | 600/0 | 2390.70 | 2 | 2 | 3 | 0.5 | 1.12 | – | – | – | 5 | 58 | 11 |
| 4 | A | 3 | 600/0 | 2519.14 | 2 | 2 | 2 | 0.4 | 1.05 | – | – | – | 5 | 58 | 11 |
| 8 | S1 | 3 | 600/0 | 2640.00 | 3 | 4 | 8 | 0.4 | 1.10 | – | – | – | 9 | 58 | 15 |
| 8 | A | 3 | 600/0 | 2642.39 | 3 | 4 | 6 | 0.4 | 1.06 | – | – | – | 9 | 58 | 15 |
| 16 | S1 | 3 | 600/0 | 2594.16 | 6 | 8 | 11 | 0.4 | 1.08 | – | – | – | 17 | 58 | 23 |
| 16 | A | 3 | 600/0 | 2637.26 | 6 | 8 | 12 | 0.4 | 1.05 | – | – | – | 17 | 58 | 23 |
| 32 | S1 | 3 | 600/0 | 2286.25 | 12 | 30 | 37 | 0.5 | 1.06 | – | – | – | 33 | 59 | 39 |
| 32 | A | 3 | 600/0 | 2338.04 | 12 | 31 | 42 | 0.5 | 1.03 | – | – | – | 33 | 59 | 39 |
| 64 | S1 | 3 | 600/0 | 2249.61 | 23 | 38 | 47 | 0.5 | 1.01 | – | – | – | 39 | 60 | 71 |
| 64 | A | 3 | 600/0 | 2316.64 | 23 | 40 | 48 | 0.4 | 1.00 | – | – | – | 41 | 60 | 71 |
