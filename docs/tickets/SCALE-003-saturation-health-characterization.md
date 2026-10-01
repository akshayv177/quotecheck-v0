# SCALE-003 — Saturation, Queueing & Health Characterization

Risk class: **T3 — Architecture-Sensitive Measurement**. It measures the architecture and changes none of it.

Branch: `task/SCALE-003-saturation-health-characterization`, created from `v1/scalability` @ `e8bdce7` (the SCALE-002 merge). It merges back into `v1/scalability`, never `main`.

Verification budget: **₹0**. No real or paid provider calls, no OpenAI credential, and no load against the public deployment.

## 1. Goal

Characterize QuoteCheck when slow provider work consumes all available synchronous worker capacity:

> When provider latency is multi-second and incoming analysis concurrency exceeds execution capacity, how do analysis latency, hidden queueing, retries and `/health` behave?

The ticket ends at **Decision Gate C**:

> Does QuoteCheck now have enough evidence to introduce an explicit provider-concurrency/admission policy, and what specific failure mode must that mechanism solve?

The policy itself is not implemented here.

## 2. Context

SCALE-002 (`docs/scalability/SCALE-002_SHARED_CLIENT.md`) replaced per-request `OpenAI(...)` construction with one process-wide client. Its findings:
- provider calls in flight pin at exactly 40;
- the process is near idle on CPU at that point;
- requests above C=40 wait silently for AnyIO worker capacity;
- the same implicit 40-token framework limiter also serves synchronous `/health`.

Decision Gate B asked for this saturation failure mode to be measured before any limiter is chosen.

SCALE-002 also found a benchmark artifact. The loopback fake provider adds about 40 ms per attempt on reused HTTP connections (Nagle's algorithm on the fake's socket). Repairing it is a prerequisite for SCALE-003 evidence.

## 3. Scope

- **Step 0, fake repair:** set `TCP_NODELAY` on the fake provider's accepted sockets.
  - Add deterministic tests: the socket option is set, a persistent connection is reused, and the existing fake semantics and reconciliation still hold.
  - Record the before/after reused-connection latency as runtime evidence (`benchmarks/diag_keepalive.py`), **not** as a machine-sensitive unit-test threshold.
- **Benchmark-only timeline instrumentation:**
  - The fake logs per-attempt `time.monotonic()` start and end times and the request marker.
  - The harness joins them to client send/receive times on the shared `CLOCK_MONOTONIC`.
  - No instrumentation is added to QuoteCheck.
- **Experiment A, slow-provider saturation:**
  - 1 s at C = 1, 16, 32, 40, 48, 64 (C=1 is repair evidence);
  - 3 s and 5 s at C = 16, 32, 40, 48, 64;
  - 3 trials per point, N = max(4·C, 16).
- **Experiment B, `/health` under active saturation:**
  - provider latency 3 s and 5 s;
  - an idle control, then sustained load at C = 32, 40, 64;
  - saturation confirmed on the fake before probing;
  - 40 sequential probes per point;
  - every probe tagged with the exact provider in-flight count at send;
  - results reported for all probes and, separately, for the subset sent while provider in-flight == 40.
- **Experiment C, retry under saturation:**
  - fail-first at 3 s, C = 32, 40, 64, compared with success at 3 s;
  - one fail-always spot check at 3 s, C = 64.
- **Report, bundle and docs:**
  - `docs/scalability/SCALE-003_SATURATION.md`, with Decision Gate C;
  - a review bundle;
  - `benchmarks/README.md` and `docs/CURRENT_STATE.md` updates.

## 4. Non-goals

- **Concurrency and admission controls:** a provider semaphore or limiter, explicit admission control, an overload-503 policy, or a queue.
- **Infrastructure:** a worker service, Redis, async OpenAI or an async FastAPI rewrite.
- **Capacity tuning:** raising the AnyIO thread limit, adding Uvicorn workers, horizontal replicas, or SDK connection-pool tuning.
- **Provider and cost features:** provider rate-limit logic or cost-control features.
- **Unrelated work:** product, schema, prompt, API, logging or frontend changes, deployment changes, and unrelated cleanup.
- **Runtime code:** any change to `backend/`.
- **Historical evidence:** any change to SCALE-001 or SCALE-002 results.

## 5. Acceptance criteria

1. The fake-provider artifact is repaired and validated. Reused persistent connections no longer incur the ~40 ms fake-only delay, and the existing fake semantics and reconciliation still pass.
2. Multi-second saturation evidence exists for 1 s, 3 s and 5 s, around and above the 40-token boundary. It covers throughput, latency, queueing/waiting, provider concurrency and resource usage.
3. The report contains real `/health` measurements taken while slow analysis work is actively consuming worker capacity.
4. The report quantifies the latency and capacity effect of one transient retry under slow-provider saturation.
5. No QuoteCheck runtime architecture or product change is made. `git diff` for `backend/` and `frontend/` is empty.
6. Regression verification passes:
   - the full unit suite, with the actual count reported;
   - `eval.run_eval --validate-only`;
   - Demo eval at 27/27 schema-valid and 24/27 passing, with residuals AUTO-004, CONT-003 and HVAC-003.

## 6. Required evidence

- Raw results in `benchmarks/results/SCALE-003-saturation/`. `stats --check` must reproduce `summary.json` and `health_summary.json`.
- `stats --check` must still pass on SCALE-001-baseline, SCALE-002-before and SCALE-002-after.
- The `diag_keepalive` output (fake with and without `TCP_NODELAY`).
- Exact commands and real outputs in the review bundle.
- Decision Gate C answers A–D, using the OBSERVED FACT / SUPPORTED INFERENCE / REMAINING HYPOTHESIS discipline.
