# SCALE-006 — QuoteCheck v1 Scalability Closure and Decision Gate F

Ticket: `docs/tickets/SCALE-006-final-scalability-v1-closure.md`

- **Code under test.** `v1/scalability` @ `0e039ca264825e2a5e85a4ed5d422c48bd1fedb8`, on a clean tree (branch `task/SCALE-006-final-scalability-v1-closure`, which adds only documentation). Runtime code is identical to the SCALE-004 commit `78cc5d3`: `git diff 78cc5d3 0e039ca -- backend eval/run_eval.py benchmarks/*.py frontend/src` is empty.
- **Spend.** ₹0. No OpenAI credential, no paid evaluation, no contact with the public deployment.
- **New evidence.** One quick admission smoke check (§6), kept outside the repository. Only the compact summary below is committed.

Labels follow SCALE-005: **OBSERVED**, **SUPPORTED INFERENCE**, **MISSING**, **HYPOTHESIS**.

> **Scope banner.** Every capacity number here comes from **one local WSL2 host, a loopback fake provider, one uvicorn process, a closed-loop load generator, and ₹0**. These numbers are not an SLA. They are not Railway capacity, OpenAI latency, OpenAI rate-limit or OpenAI capacity figures.

---

## 1. The v1 claim, in one sentence

> QuoteCheck now has an explicit, evidence-backed application capacity boundary and predictable overload behaviour, rather than relying on incidental framework queueing.

The engineering story behind that sentence is not "every scalability feature was implemented". It is: **measurement exposed one bottleneck at a time, and each mechanism was added only after the previous evidence justified it.** v1 added exactly two runtime changes, a shared OpenAI client (SCALE-002) and explicit provider admission (SCALE-004). Everything else was measurement, contract and documentation.

---

## 2. Starting point: concurrent OpenAI-style demand before v1

All of this is OBSERVED with the fake provider unless labelled otherwise.

1. **Per-request client construction was expensive** (SCALE-001).
   - Every request built a new `OpenAI(...)` client, which costs about 20 ms CPU serially (SSL context plus CA bundle load).
   - Under thread concurrency the cost rose to 110–770 ms per construction. At 250 ms provider latency, server CPU per request grew from 20 ms to about 580 ms, and the process burned up to 23.5 cores.
   - Throughput plateaued at about 36–41 rps for C=32–64, while the provider loop itself stayed flat.
2. **After client reuse, hidden worker saturation was the next constraint** (SCALE-002).
   - Sharing one client cut CPU per request from 468.9 to 5.7 ms (250 ms, C=64) and raised throughput from 46.6 to 102.1 rps.
   - Peak provider in-flight then pinned at exactly **40**, which is anyio's default worker limiter. Nobody chose that bound. It was a framework default, shared by `/analyze` and `/health`, with no overload signal.
3. **Provider-bound work could occupy all 40 tokens** (SCALE-003). Throughput plateaued at about 40 / provider latency: 34.5, 12.6 and 7.75 rps at 1, 3 and 5 s.
4. **Excess demand waited silently** (SCALE-003).
   - At 5 s and C=64, e2e p50 was 9.7 s and the max 15.3 s, against a provider loop of 5.0 s.
   - Waiting sat on both sides of the provider call. About 20% of requests waited more than half a provider period *after* their result was ready, re-queuing for a second worker token to run response validation.
   - Every request eventually got 200. The only overload signal was latency.
5. **`/health` became coupled to long provider calls** (SCALE-003). At C=40/64, `/health` p95 was 2.4–2.8 s (3 s provider) and 4.4–4.7 s (5 s provider). Every probe still returned 200.
6. **Retries amplified that waiting** (SCALE-003).
   - A transient-failure retry held its worker token for two provider periods, halving throughput (0.51–0.52×).
   - At C=64, fail-first e2e p50 was 11.7 s. A persistent outage produced 503s with an 11.8 s p50 while holding all 40 tokens.

---

## 3. What changed, ticket by ticket

| Ticket | Kind | What it established or changed | Gate |
|---|---|---|---|
| SCALE-001 | Measurement | A reproducible local harness and fake provider. Found per-request client construction to be the first constraint, and the implicit 40-token limiter to be the only aggregate provider bound. | A |
| SCALE-002 | Runtime change | One process-wide `OpenAI` client, with the same timeout, `max_retries=0` and retry loop. Removed the construction bottleneck. The 40-token limiter then became the binding constraint. | B |
| SCALE-003 | Measurement (harness only) | Repaired the fake provider's Nagle artifact and added per-attempt timelines and `/health` probes. Characterized silent queueing, `/health` coupling and retry amplification at 1/3/5 s. | C |
| SCALE-004 | Runtime change | Explicit pre-threadpool provider admission: 32 slots per process, fail-fast 503 `capacity_exceeded`, retry inside the slot. A narrow async boundary (async route and async error handler) removes the second worker-token acquisition. | D |
| SCALE-005 | Contract (docs only) | Froze the runtime contract (C1–C15) and the operating envelope. Corrected the cost claim's strength, and registered 14 candidate mechanisms, none required. | E |
| SCALE-006 | Closure | Final regression, an admission smoke bound to the exact code, this synthesis, and the public-doc truth sync. | F |

**Rejected or deferred along the way** (with evidence, in SCALE-002 §D, SCALE-003 §D and SCALE-005 §7):
- raising the anyio limit;
- workers or replicas;
- async OpenAI conversion;
- queues or Redis;
- rate limiting;
- `Retry-After`;
- a configurable budget;
- metrics;
- token logging.

None of them had evidence that it was needed for v1.

---

## 4. Final v1 runtime contract

This summarizes `SCALE-005_RUNTIME_CONTRACT.md` §2–§3, which remains authoritative. The C-numbers refer to its enforcing tests.

| # | Contract | Source of truth |
|---|---|---|
| 1 | **Single process today.** The committed start command is one uvicorn process (`railpack.json`). Railway dashboard settings were not inspected. | C14, SUPPORTED INFERENCE |
| 2 | **Fixed 32 concurrent provider-bound analyses per process** (`OPENAI_MAX_CONCURRENT_ANALYSES`, a code constant, not env-configurable). It stays below anyio's 40 tokens, leaving 8 for `/health` and the 422 handler. | C1, C15 |
| 3 | **No queue, no waiting for capacity.** Admission is decided on the event loop before threadpool dispatch, and a rejection needs no worker token. | C2 |
| 4 | **Fail-fast overload:** HTTP 503, `code: capacity_exceeded`, `retryable: true`, one sanitized JSONL record with `provider_attempts: 0`. | C3, C4 |
| 5 | **`capacity_exceeded` is application-owned** and distinct from provider failures in code, message, status (vs 429), `provider_attempts` (0 vs ≥ 1), and null `cause_type`/`provider_status`. | C5 |
| 6 | **Rejected work makes zero provider calls.** | C3 |
| 7 | **At most two provider attempts per admitted request.** Only connection, timeout and 5xx failures are retried. 429, refusal, incomplete and invalid output make one call. | C6, C7 |
| 8 | **A retry stays inside the same capacity slot.** The slot is released exactly once, after the worker thread returns. | C8 |
| 9 | **SDK auto-retries stay disabled** (`max_retries=0`), with an explicit per-attempt timeout (30 s default). | C6, C13 |
| 10 | **Demo mode bypasses provider admission.** It takes no slot, builds no client and makes zero provider calls. | C10 |
| 11 | **Input is bounded:** at most 12,000 quote characters per request, rejected with 422 before admission. | C12 |
| 12 | **Cancellation does not release capacity early.** A cancelled request keeps its slot while its worker thread is still in the provider call. | C9 |
| 13 | **No silent fallback from OpenAI mode to Demo.** | C11 |

Overload and failure semantics (HTTP, `code`, `retryable`, attempts, owner) are in SCALE-005 §3.

---

## 5. Cost and amplification boundary

This preserves SCALE-005 §1 and §5 wording strength.

**QuoteCheck v1 bounds** (OBSERVED, test-enforced):
- concurrent provider work: ≤ 32 admitted analyses per process;
- per-request provider-call amplification: ≤ 2 attempts, retrying only transient failures;
- provider calls made by rejected work: 0. The same holds for invalid (422) and Demo requests.

**QuoteCheck v1 does not claim to bound:**
- **cumulative provider spend over arbitrary time.** Under sustained demand, spend grows linearly with time. There is no quota, daily cap or spend ceiling.
- **output tokens.** No application-owned `max_output_tokens` is set.
- **public OpenAI consumption by authenticated or per-user quota.** There is no authentication, user quota, or public or per-client rate limiting.

Also not bounded: cancelled or abandoned requests keep their provider work running until the underlying worker/provider call finishes (contract 12; OBSERVED for the slot and worker by `test_cancelled_request_holds_its_slot_until_the_thread_finishes`). That work may continue to incur provider usage or cost, depending on provider billing semantics. Real-provider billing after cancellation, or after a client-side timeout, is a HYPOTHESIS that can't be checked at ₹0.

**What bounds cumulative spend in v1 is outside the application:**
- **Exposure policy.** The public v1 deployment runs Demo, and OpenAI mode is opt-in and **not anonymously exposed**.
- **Provider-account controls.** These are external, not visible from the repository, and not verified here.

Token/cost logging and an output cap are deferred together. The trigger is the first approved paid-provider exercise, or any plan to expose OpenAI mode publicly (SCALE-005 §5.4).

---

## 6. Final admission smoke check (SCALE-006, new)

**Purpose.** To bind the explicit-admission contract to the exact code being closed. SCALE-004's evidence was bound to the admission backend only by attestation, because its `env.json` recorded `git_dirty: true` and no backend hashes (SCALE-005 §8).

**What this smoke does not do.** It does not re-prove the SCALE-004 latency, health, saturation or storm measurements. Those remain the accepted SCALE-004 evidence (§7).

**Setup**
- **Command:**
  ```bash
  python -m benchmarks.run_capacity --quick --experiment admission --gate-cap 32 \
      --ticket SCALE-006 --run-id <session-scratchpad>/s006-final-admission-smoke
  ```
- **Provenance (`env.json`).**
  - `git_commit 0e039ca264825e2a5e85a4ed5d422c48bd1fedb8`, `git_dirty: false`, `quick: true`, `admission_gate_cap: 32`.
  - `server_processes: 1`, `server_workers: 1`.
  - Python 3.11.14, Linux 6.6.87.2 WSL2.
  - No host-safety guard fired, and the run took 40.2 s.
- **Instrument.** The harness sha256 prefixes (`run_capacity.py` `484c1a9f`, `stats.py` `13f353e4`, `fake_provider.py` `9f35ae00`, `workloads.py` `ef8e426a`) are byte-identical to SCALE-004's.
- **Quick plan.**
  - Fake provider latency is 0.3 s, and C ∈ {4, 40}. C=40 exceeds the 32-slot budget by 8.
  - Scenarios: bursts (2 trials), sustained (backoff 0.25 s, and zero backoff), `/health` probes under load, and retry (fail-first burst/sustained, fail-always sustained).
- **Raw output.** The 8.6 MB run directory stays in the session scratchpad and is not committed.

**Results (OBSERVED)**

| Check | Result |
|---|---|
| Peak provider in-flight | **32** at every C=40 point (bursts, sustained, zero-backoff, health load, every retry scenario). It was 4 at C=4. This comes from the harness's attempt timeline, and an independent sweep over the fake's attempt intervals gives the same result (overall peak 32). |
| Excess requests | All 6,270 rejected client requests in the measured trials (2,271 in `requests.jsonl`, 3,999 behind health probes) got HTTP **503 `capacity_exceeded`**. |
| Zero provider calls on rejection | Across all eight server logs, **6,558** `capacity_exceeded` records all have `provider_attempts: 0` (`('capacity_exceeded', None, None, True, 0)`). Every trial is `attempts_joined: true`, which requires that the fake saw no attempt carrying a rejected request's marker. |
| Why 6,558 ≠ 6,270 | The extra 288 are **harness warm-up requests**. These are logged by the server but, by design, excluded from `requests.jsonl` and the trial records (`run_capacity.py:46`). Each scenario sends 2 sequential warm-ups. Each `/analyze` ladder point also sends one 2 × C burst warm-up, once per point, not per trial (`run_capacity.py:938–940`). For every scenario, server-log records minus the summed trial `log_records` equals exactly that warm-up count: 90 for the burst and sustained ladders (2 + 8 + 80), 82 for the single-point C=40 scenarios (2 + 80), and 2 for each health scenario. The 80-request C=40 burst warm-up produced 48 rejections in each of the six non-health scenarios, and 6 × 48 = 288 = 6,558 − 6,270. The health scenarios have no burst warm-up, and their logged rejections equal their client rejections (69 and 3,930). |
| Admitted requests complete | The success scenarios have 0 non-rejection failures. Burst C=40 admits 32 and rejects 8 in each trial. |
| No hidden waiting | In both C=40 bursts, every rejection finished before the first admitted provider call ended (`all_rejections_done_before_first_provider_end: true`). Burst rejection p95 was 62.7 and 63.7 ms, against a 300 ms provider period. |
| Retry inside the slot | Fail-first and fail-always give **2.0 attempts per admitted request**, with peak in-flight still 32. Fail-always admitted requests end as `('provider_unavailable', 503, 'InternalServerError', True, 2)`, distinct from `capacity_exceeded`. |
| `/health` | All 25 probes returned 200 (idle, C=4 and C=40). At C=40 with backoff, p50 was 2.9 ms and p95 19.3 ms. Under zero-backoff load, p50 was 33.3 ms and p95 86.6 ms (n=5 per point, quick plan; indicative only). |
| Reconciliation | All 11 trials are `reconciled: true` and `attempts_joined: true`. `python -m benchmarks.stats <run> --check` reports `summary.json` and `health_summary.json` as matching recomputation: `True`. |

**Conclusion.** The exact code being closed enforces C1, C3, C5, C6 and C8. The provenance caveat from SCALE-005 §8 is closed for those claims: they are now bound by `git_dirty: false` at a named commit. C9 (cancellation) and C10 (Demo bypass) are not exercised by the harness. They remain enforced by their deterministic tests, which ran in the 201-test suite (§9, F1).

---

## 7. Final local operating envelope (SCALE-004 evidence)

These are the SCALE-004 before/after results, from `SCALE-004_ADMISSION.md` and `SCALE-004-after/report_tables.out`.
- **Pre-SCALE-004** means before explicit admission: `v1/scalability` @ `1e7f2ed`, which already includes the SCALE-002 shared client. **Post-SCALE-004** means after explicit admission.
- **This is not a comparison against the original pre-v1/v0 baseline.** The earlier stages of the progression are in §2.
- Both runs used the same harness, host and workload. The scope banner above applies.

| Measure | Pre-SCALE-004 (before explicit admission; implicit 40-token queueing) | Post-SCALE-004 (after explicit admission; 32 slots) |
|---|---|---|
| Peak provider in-flight at C ≥ 40 | 40 (framework default) | **32** at every point, retries included |
| Excess demand at C=64 | waits silently: pre-provider p95 3.3 s (3 s) / 5.3 s (5 s), then 200 | rejected `capacity_exceeded` |
| Rejection latency, sustained with 0.25 s backoff | – | p50 1.4–1.5 ms, p95 3.4–10.8 ms, max ≤ 180 ms |
| Rejection latency, simultaneous bursts (C=40/64) | – | p50 56–99 ms, p95 ≤ 181 ms (235 ms in the retry burst) |
| Admitted `ok` p95, sustained 5 s, C=64 | 10,386 ms (max 15,379) | 5,312 ms (max 5,416) |
| Admitted `ok` p95, burst 5 s, C=64 | 10,304 ms | 5,272 ms |
| `/health` p95 under C=40/64 overload | 2.2–4.7 s | 3.5–27.8 ms (all probes 200) |
| Fail-first retry admitted p95, 3 s, C=64 | 12.3 s | 6.3–6.4 s |
| Persistent outage, admitted p95 | 12.4 s | 6.4 s (p50 6.1 s) `provider_unavailable` |
| Completed throughput under saturation, 5 s | 7.73 rps (C=40, all 40 tokens busy) | about 6.2 rps (≈ 20% lower, the deliberate price of reserving 8 tokens) |

**Distinctions that must stay separate:**
- **Idealized one-attempt ceiling:** 32 / provider latency per process, i.e. 10.67 rps at 3 s and 6.40 rps at 5 s. With every request retried once, it is 32 / (2 × latency). This is **arithmetic from the budget, not a guarantee**.
- **Measured throughput against that ceiling:**
  - 3 s burst: 10.0–10.14 rps;
  - 5 s burst: 6.09–6.11 rps;
  - 5 s sustained: 6.15–6.21 rps;
  - 3 s fail-first: 5.1 rps (burst) and 4.61 rps (sustained).
- **Admitted latency** tracks provider latency and does not grow with excess demand. Pre-provider p95 is 136–272 ms and post-provider p95 23–216 ms across the after points.
- **Rejection latency** is milliseconds with backoff, and tens to ~200 ms in a simultaneous wave (event-loop dispatch of the wave, which admitted requests pay too).
- **Health responsiveness** is decoupled from provider latency while clients back off. It is **not** idle-like under a zero-backoff storm: about 1,870–1,890 rejections/s, about 0.95 of a core, `/health` p95 155 ms. In that storm the binding resource is the single event loop's CPU, not worker tokens.
- **Retry behaviour:** a retry holds its slot for two attempt periods, halving per-slot throughput. A persistent outage fails in about two provider periods instead of up to four.

---

## 8. Known limitations (all explicit)

Each is either **accepted for v1** or carries an existing SCALE-005 revisit trigger (D-numbers are SCALE-005 §7, and §6.1 is its missing-signal table).

| Limitation | Status | Revisit trigger |
|---|---|---|
| The budget is per process. Multiple workers or replicas multiply aggregate provider capacity (N × 32). | Accepted; the committed start command is single-process | Workers or replicas are introduced (D11, D13) |
| No cross-process coordination | Accepted | Same (D11) |
| No public or per-client rate limiting | Deferred; the public path is Demo | Before any public OpenAI exposure (D1) |
| No `Retry-After` on `capacity_exceeded` | Deferred; no consumer, and the frontend never auto-resubmits | A programmatic or auto-retrying client exists (D2) |
| No application-level cumulative spending quota | Accepted; bounded externally (§5) | Before any public OpenAI exposure (D1, §5.4) |
| No token/cost telemetry | Deferred | First approved paid exercise, or before public OpenAI exposure (D6, §5.4) |
| No explicit `max_output_tokens` cap | Deferred; sizing needs real output evidence | Same, designed together with token logging (§5.4) |
| Real-provider latency, rate limits and cost not characterized | Accepted; contract stated as local-only | Approved spend, or public OpenAI exposure (D10) |
| An adversarial zero-backoff rejection client can saturate the event loop (`/health` p95 155 ms) | Accepted; needs a non-cooperating client, and fail-fast and the cap still hold | Before any public OpenAI exposure (D1) |
| Cancelled or abandoned requests keep their provider work running until the underlying worker/provider call finishes. They may continue to incur provider usage or cost, depending on provider billing semantics (billing unverified at ₹0). | Accepted by design (contract 12) | Same as the cost triggers (§5.4) |
| An invalid-request flood competing with `/health` for the 8 spare tokens is unmeasured | Deferred | Evidence that an invalid-request flood couples `/health` (D8) |
| Rejection-latency tail: 1.2–1.5% of sustained rejections exceed 50 ms (max ~220 ms), only partly attributed | Accepted; no envelope statement depends on it | Accepted for v1; reopen only if a tighter rejection-latency claim is needed |
| A 32-slot budget is one local measurement point, not env-configurable | Accepted | A second environment with its own evidence (D3) |
| The Demo analyzer is deterministic keyword matching, semantically limited | Accepted product limitation (v0) | Outside v1 scalability scope |
| Demo eval residuals `AUTO-004`, `CONT-003`, `HVAC-003` (24/27) | Accepted documented Demo limitations (QC-3C) | Outside v1 scalability scope |
| Demo `latency_ms` ≈ 0 (taken before the stub runs), and `latency_ms` measures a different interval on each path | Accepted; do not overinterpret (SCALE-005 §6.2) | A need for server-side SLO measurement (§6.1) |
| Hosted logs are local and ephemeral, with no durable centralized logging | Accepted | Any hosted OpenAI exposure (§6.1) |
| Railway worker/replica settings not inspected; topology inferred from `railpack.json` | Accepted; the public path is Demo, so the budget isn't on it | Before any public OpenAI exposure, or a topology change (D11, D13) |

There is no hidden unresolved item. Everything that depends on a real provider, or on public OpenAI exposure, is gated on a trigger that has not occurred.

---

## 9. Decision Gate F — QuoteCheck v1 closure

**F1. Regression integrity: PASS.**
- 201 unit tests ran, OK.
- Corpus validation: 27 cases, 6 domains, 9 categories, 0 errors.
- Demo eval: 27/27 schema-valid, 24/27 deterministic pass. The residuals are exactly `AUTO-004`, `CONT-003` and `HVAC-003`, the accepted baseline.
- Frontend `npm run lint` and `npm run build` are clean.
- The local Demo backend smoke passed:
  - `/health` returned 200;
  - `/analyze` returned 200 with `quotecheck-demo-analyzer`, `quotecheck_v0.4` and `schema_valid: true`;
  - empty input returned 422 `invalid_request`;
  - the log record shows `analyzer: demo`, `provider_attempts: null`.

**F2. Capacity contract integrity: PASS.** The §6 smoke on a clean `0e039ca` shows all of the following, with every trial reconciled and joined:
- peak in-flight 32;
- 503 `capacity_exceeded` for excess demand;
- zero provider calls for every rejection, in both QuoteCheck's log and the fake;
- 2.0 attempts per admitted request under retry, inside the cap;
- no hidden waiting.

**F3. Evidence integrity: PASS.**
- Every claim in §2, §4, §5 and §7 cites accepted SCALE-001–004 evidence, the SCALE-005 contract (and its enforcing tests), or the §6 smoke.
- The SCALE-004 "attestation only" provenance gap is now closed for C1, C3, C5, C6 and C8.

**F4. Public truth: PASS** after this ticket's sync:
- `PROJECT_STATUS.md`: the test count, plus new capacity, overload and cost-boundary statements;
- `README.md`: the failure-category count, the reliability test count, and a capacity section;
- `CURRENT_STATE.md`;
- `CLAUDE.md`.

No public file claims production scale, an SLA, OpenAI capacity, or unqualified cost control.

**F5. Known limitations: PASS.** Every material limitation is in §8, each accepted or carrying a SCALE-005 revisit trigger. None invalidates the v1 claim in §1, which is explicitly local, per process and Demo-public.

**F6. Closure sufficiency: PASS.**
- No evidence justifies another mechanism before closing v1.
- SCALE-005 §7 classified all 14 candidates as not required. Nothing in the SCALE-006 verification changes that: no defect was found, and the smoke matches the contract.

**Gate F result: PASS.** QuoteCheck v1 is technically ready to close. No corrective ticket is required.

Merging `v1/scalability` to `main`, tagging, releasing and deploying are **not** part of this ticket. They wait for explicit user approval.
