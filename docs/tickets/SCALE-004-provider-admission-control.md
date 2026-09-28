# SCALE-004 — Explicit Provider Admission Control

Risk class: **T3 — Architecture-Sensitive Runtime Change**. This is the first v1 ticket that deliberately changes overload and runtime behaviour.

Branch: `task/SCALE-004-provider-admission-control`, created from `v1/scalability` @ `1e7f2ed` (the SCALE-003 merge). It merges back into `v1/scalability`, never `main`.

Verification budget: **₹0**. There are no real or paid provider calls, no OpenAI credential is used, and no load is sent to the public deployment.

## 1. Goal

Introduce the smallest deliberate provider admission mechanism that:

1. bounds aggregate concurrent OpenAI analysis work per process;
2. rejects excess work promptly instead of letting it queue silently behind provider-bound requests;
3. counts a request's entire provider retry sequence inside one admitted slot;
4. makes overload visible through the API and the structured logs;
5. preserves Demo mode, and preserves provider retry, error and validation semantics for admitted work;
6. leaves worker capacity for response handling and `/health`;
7. stays simple, local and process-scoped.

The focused SCALE-003 saturation scenarios are then re-run before and after the change. The ticket ends at **Decision Gate D**.

## 2. Context

SCALE-003 (`docs/scalability/SCALE-003_SATURATION.md`) established the following:

- AnyIO's process-wide default `CapacityLimiter(40)` is the only limit on synchronous `/analyze` work.
- Demand above 40 becomes silent FIFO waiting, both before the provider call and after it. After the call, the wait comes from response-model validation and the synchronous error handler re-acquiring a worker token.
- `/health` becomes coupled to provider latency at C ≥ 40.
- A retry holds a worker for two provider periods.

Decision Gate C asked for an explicit provider-concurrency bound with visible, bounded overload behaviour.

## 3. Design (approved at the planning checkpoint)

- **Where the decision is made.** `/analyze` becomes a narrow `async def` wrapper. It admits the request on the event loop, after FastAPI validates `AnalyzeRequest` and **before** anything is dispatched to the AnyIO threadpool. The existing synchronous body (analyzer, retry loop, logging) runs unchanged through `run_in_threadpool`.
- **Budget.** `OPENAI_MAX_CONCURRENT_ANALYSES = 32`, a fixed code constant in `backend/core/config.py` that cannot be overridden from the environment.
  - It is **per process**: N processes give N × 32.
  - It is a local v1 default, not an OpenAI or Railway capacity claim.
- **Primitive.** `backend/core/admission.py` defines `ProviderAdmission`: a non-blocking `try_acquire()`, a `release()` that is guarded against underflow, and a lock-protected counter. A module-level instance is built eagerly at import.
- **Lifetime of a slot.** The slot is acquired before the threadpool call. It covers the whole worker-thread execution, including the permitted retry.
  - The admitted work runs in its own task behind `asyncio.shield`, and the slot is released in that task's `finally`, once the worker thread has returned. A cancelled request therefore never frees a slot while its provider call is still running.
  - This is an implementation correction. The planning checkpoint assumed that anyio's `abandon_on_cancel=False` made a plain `try/finally` around the `await` safe. A direct check showed that a native asyncio `Task.cancel()` resumes the awaiting coroutine early. See the report, §0.
- **Rejecting over-capacity work.** No provider call and no worker token. The request gets `FailureCategory.CAPACITY_EXCEEDED` (`capacity_exceeded`): HTTP 503, `retryable=true`, a user-safe message, and one sanitized JSONL record with `provider_attempts=0`.
- **Error handler.** `_quotecheck_error_handler` becomes `async`. It is pure rendering, and making it async means a rejection never needs a worker token.
- **Demo mode** bypasses admission entirely.
- **Execution-shape consequences.** These are stated explicitly because they are not caused by the budget:
  - Response-model validation for `/analyze` now runs on the event loop.
  - The `QuoteCheckError` handler no longer takes a worker token.
- **Rejection logging** stays synchronous and runs on the event loop. Its cost is measured as part of rejection latency.

## 4. Non-goals

- Queueing: an application queue, Redis, a distributed semaphore, a worker service.
- Concurrency tuning: an async OpenAI SDK, a broad async rewrite, a higher AnyIO thread limit, extra Uvicorn workers, replicas, autoscaling, adaptive concurrency.
- Provider-side controls: connection-pool tuning, provider rate-limit scheduling, token buckets, cost accounting.
- Other changes: deployment changes, frontend changes, `/health` architecture changes, background logging, unrelated refactors.
- Rewriting SCALE-001, SCALE-002 or SCALE-003 evidence.

## 5. Acceptance criteria

1. A deterministic test proves that at most the budgeted number of requests enter provider execution. Excess requests are rejected with zero provider calls, and the rejection completes while admitted calls are still blocked.
2. A rejection needs no AnyIO worker token.
3. A transient-first request makes exactly two attempts inside one slot, and the slot is released once.
4. Every terminal path releases its slot. A cancelled request holds its slot until the worker thread finishes.
5. Demo requests never touch the budget.
6. The rejection's API body, status and log record match §3, and cannot be confused with a provider 429 or 5xx.
7. Before/after runtime evidence covers these points against the same harness and the same corrected fake:
   - provider peak in-flight ≤ 32, including under retry;
   - excess demand gets a prompt, explicit 503 `capacity_exceeded`;
   - `/health` stays responsive under overload;
   - rejection latency, including synchronous logging, stays prompt under C=64 zero-backoff overload.
8. Regression passes:
   - the full unit suite, with the actual count reported;
   - `--validate-only`;
   - Demo eval at 27/27 schema-valid and 24/27 passing, with residuals AUTO-004, CONT-003 and HVAC-003;
   - `stats --check` on all prior result directories.

## 6. Required evidence

- Raw results in `benchmarks/results/SCALE-004-before/` and `benchmarks/results/SCALE-004-after/`.
- `docs/scalability/SCALE-004_ADMISSION.md`, with Decision Gate D answering A–E.
  - It separates observed fact, supported inference and remaining hypothesis.
  - It attributes changes in post-provider waiting to the coupled execution-shape change, not to the budget alone.
- The review bundle, containing the exact commands and real outputs.

## 7. Stop conditions

Stop and surface the problem, without expanding scope, if any of the following happens:

- synchronous rejection logging materially stalls the event loop or makes fail-fast untrue (no background logging is added without approval);
- `/health` stays coupled even with admission in place;
- the evidence points towards queueing, a higher thread limit, more workers or distributed coordination;
- `--check` can no longer reproduce historical results;
- the absolute `--run-id` marker issue blocks valid evidence;
- any change would alter `QuoteCheckResult`, retry semantics, or the status and retryable values of existing categories.
