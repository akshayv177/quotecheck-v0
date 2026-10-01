# SCALE-005 — v1 Runtime Contract, Operating Envelope and Decision Gate E

Ticket: `docs/tickets/SCALE-005-capacity-observability-runtime-contract.md`

- **Scope.** Documentation and runtime contract only. No application, test, harness, frontend, dependency or deployment file changed.
- **Spend and evidence.** ₹0 provider spend. No new benchmark run and no new evidence directory.
- **Baseline.** Every source reference below is to `v1/scalability` @ `25d0ebf`.

Labels used throughout:
- **OBSERVED**: shown by an enforcing test or by committed or retained runtime evidence;
- **SUPPORTED INFERENCE**: follows from code and evidence, but no test or measurement shows it directly;
- **MISSING**: not answerable today;
- **HYPOTHESIS**: plausible, but not checked.

---

## 1. The v1 scalability definition (sharpened)

The accepted definition said QuoteCheck "keeps provider usage and cost bounded". Read literally, that claims something the application does not do. The v1 definition is now:

> As simultaneous analysis demand rises, QuoteCheck admits only work it has capacity to execute; **bounds concurrent provider work; bounds per-request provider amplification; makes zero provider calls for rejected work**; degrades predictably under overload; preserves its product and evaluation contracts; and produces enough evidence to explain its **local** operating envelope.
>
> **Cumulative provider spend over time is not bounded by QuoteCheck.** In v1 it is bounded by exposure policy and by provider-account controls. The public v1 deployment runs Demo, OpenAI mode is opt-in and not publicly exposed, and provider-account controls sit outside the application (§5).

---

## 2. Runtime contract

Each claim has a mechanism and an existing enforcing test or accepted evidence. No new tests were written for this document. The "Test" column names tests that exist at `25d0ebf`. Test files:
- `test_provider_admission.py` (**PA**);
- `test_openai_reliability.py` (**OR**);
- `test_deployment_readiness.py` (**DR**);

all in `eval/tests/`.

| # | Claim | Mechanism (source) | Enforcing test | Runtime evidence |
|---|---|---|---|---|
| C1 | At most `OPENAI_MAX_CONCURRENT_ANALYSES = 32` OpenAI-mode analyses are admitted at once per process. | `config.py:131`; `admission.py:47–53` (`try_acquire`); `app.py:211` | PA `test_cap_rejects_excess_immediately_with_zero_provider_calls`, `test_concurrent_try_acquire_admits_exactly_capacity`, `test_budget_constant_is_named_32_and_process_instance_uses_it` | Peak provider in-flight is 32 at every SCALE-004 after point, retry included (`report_tables.out`) |
| C2 | Admission is decided on the event loop before threadpool dispatch, and a rejection needs no worker token. | `app.py:172–244` (async route); `app.py:94–105` (async error handler) | PA `test_rejection_needs_no_worker_token`. Mutations M2 and M3 in the SCALE-004 bundle fail it. | Burst rejections completed before the first admitted provider call ended in 25/25 trials (SCALE-004 §1) |
| C3 | A rejection is immediate (no waiting, no queue). It returns HTTP 503 `capacity_exceeded`, `retryable: true`, and makes **zero provider calls**. | `app.py:211–240`; `errors.py:97–101` | PA `test_cap_rejects_…` (the rejection arrives while admitted calls are parked, and the provider call count is unchanged); `test_rejection_body_and_single_sanitized_log_record` (`create.assert_not_called()`); OR `_ROUTE_CASES` row `CAPACITY_EXCEEDED, 503, True` | 116,648 zero-backoff rejections, all with `provider_attempts=0` and no fake-provider attempt (SCALE-004 Gate D A). Retained logs re-checked by SCALE-005: §6.3. |
| C4 | A rejection writes exactly one sanitized JSONL record: `failure_category: capacity_exceeded`, `provider_attempts: 0`, null provider fields, no quote text. | `app.py:223–239` | PA `test_rejection_body_and_single_sanitized_log_record` | §6.3 (C3 query) |
| C5 | `capacity_exceeded` cannot be confused with a provider 429 or 503. It differs in `code` and message from both, in status from 429, and in `provider_attempts` (0 vs ≥ 1) and null `cause_type`/`provider_status` from 503. | `errors.py:28–102` | PA `test_rejection_body_and_single_sanitized_log_record` (asserts code, message and status differ) | §6.3: the fail-always log shows `('capacity_exceeded', None, None, True, 0)` next to `('provider_unavailable', 503, 'InternalServerError', True, 2)` |
| C6 | At most **2 provider attempts** per admitted request: 1 initial plus 1 application-owned retry. The SDK makes no retries of its own. | `config.py:118–120`; `openai_analyzer.py:106` (`max_retries=0`), `:209–230` | OR `test_max_attempts_constant_is_two`, `test_two_transient_failures_stop_after_exactly_two`, `test_sdk_client_built_with_no_sdk_retry_and_explicit_timeout` | Attempts per admitted request are 2.00 under fail-first and fail-always (SCALE-004 §4); §6.3 |
| C7 | Only transient failures are retried automatically: connection error, timeout and provider 5xx. Rate limiting (429), configuration errors, refusal, incomplete responses and invalid model output each make exactly **one** call. | `errors.py:215–232`; `openai_analyzer.py:217–230`. Response-state failures are raised after the loop (`:234–261`). | OR `test_transient_set_is_exactly_connection_timeout_5xx`, `test_rate_limit_makes_exactly_one_call_and_is_not_retried`, `test_terminal_failure_makes_exactly_one_call`, `test_refusal_incomplete_invalid_each_make_one_call`, and the `ResponseStateTests` call counts (including schema violation) | — |
| C8 | A retry stays inside its request's admission slot. The slot is released exactly once, after the worker thread returns. | `app.py:242–253` | PA `test_transient_retry_stays_in_the_original_slot`, `test_every_terminal_path_releases_its_slot` (10 outcomes), `test_unexpected_exception_releases_its_slot` | Peak in-flight is 32 under fail-first and fail-always at C=64 (SCALE-004 §4) |
| C9 | A cancelled request keeps its slot until its provider call has actually finished. A cancellation never frees capacity early. | `app.py:242–244` (`asyncio.shield`), `:247–253` | PA `test_cancelled_request_holds_its_slot_until_the_thread_finishes`. Mutation M1 (no shield) fails it. | — |
| C10 | Demo mode takes no slot, builds no OpenAI client and makes zero provider calls. | `app.py:208–209` | PA `test_demo_requests_never_touch_the_provider_budget` (budget 0, `try_acquire` spy, OpenAI constructor never called); OR `test_demo_mode_unchanged` | The hosted path is observed as Demo (§5) |
| C11 | There is no silent fallback from OpenAI mode to Demo. | `openai_analyzer.py` (no stub import); `app.py:272–279` | OR `test_openai_failure_never_calls_stub_for_any_category`, `test_stub_not_called_when_provider_boundary_raises` | — |
| C12 | Provider input per attempt is bounded: at most 12,000 characters of quote, plus the fixed prompt and schema. Larger input is rejected with 422 before any analysis. | `schema.py:38`, `:245` | DR `test_quote_over_maximum_is_rejected_before_analysis` (OpenAI constructor not called), `test_quote_at_maximum_length_is_accepted`; PA `test_invalid_request_is_rejected_before_admission` | — |
| C13 | Each attempt has an explicit timeout, 30 s by default. A malformed value is a `configuration_error`. The frontend's 70 s abort sits above the 2 × 30 s worst case. | `config.py:110–111`; `openai_analyzer.py:65–86`; `frontend/src/App.jsx:58` | OR `ConfigurationTests` (8), `test_frontend_request_timeout_exceeds_backend_provider_budget` | — |
| C14 | The budget is **per process**. N processes or replicas give N × 32, with no cross-process coordination. | `admission.py:12–19`, `:65` (a module-level instance) | Structural (no test can assert absence of coordination) | SCALE-004 evidence was single process (`env.json`: `server_processes: 1`, `server_workers: 1`) |
| C15 | The budget stays below anyio's default 40-token worker limiter, so 8 tokens remain for `/health` and the sync 422 handler. | `config.py:131` | PA `test_budget_is_below_the_anyio_default_worker_limit` | `/health` under C=40/64 overload (§4.4) |

**Traceability result.** Every intended claim is enforced or evidenced. C14 is structural: it is a scope statement, not a guarantee. The stop condition "an intended claim is not enforced or evidenced" was **not triggered**.

### Deployment topology (SUPPORTED INFERENCE)

- The committed start command (`railpack.json` → `deploy.startCommand`) is one uvicorn process with no `--workers`, so for the deployment as committed, the per-process budget is also the aggregate.
- Railway dashboard settings were not inspected and could override this. Any change to workers or replicas multiplies provider concurrency (C14).
- The deployment runs Demo, so the budget is not on the public path in v1.

---

## 3. Overload and failure semantics (API contract)

| Condition | HTTP | `code` | `retryable` | `provider_attempts` | Owner |
|---|---:|---|---|---|---|
| Admission budget full | 503 | `capacity_exceeded` | true | 0 | QuoteCheck |
| Provider rate limit | 429 | `provider_rate_limited` | true | 1 (never auto-retried) | provider |
| Provider unavailable (connection error or 5xx, after the retry) | 503 | `provider_unavailable` | true | 1–2 | provider |
| Provider timeout (after the retry) | 504 | `provider_timeout` | true | 1–2 | provider |
| Refusal | 502 | `provider_refusal` | false | 1 | provider or model |
| Incomplete response | 502 | `provider_incomplete_response` | true | 1 | provider or model |
| Invalid model output | 502 | `invalid_model_output` | false | 1 | model |
| Configuration | 503 | `configuration_error` | false | `null` (invalid timeout or missing key, before any call) or 1 (provider rejected the credential or request) | operator |
| Unclassified | 500 | `internal_error` | false | 1–2 (unknown exception from the provider call) or `null` (§6.2) | QuoteCheck |
| Invalid request body | 422 | `invalid_request` (response string, not a `FailureCategory`) | false | — (no log record) | client |

Sources: `errors.py:56–102`, `app.py:108–136`. Enforced by OR `_ROUTE_CASES` and `test_category_maps_to_status_and_body_shape`.

- **`retryable`** means "a manual user retry may reasonably succeed" (`errors.py:13–18`). It does not mean QuoteCheck retried automatically.
- **Body shape.** Every failure body is exactly `{"detail": {code, message, retryable, request_id}}`.
- **What overload behaviour is *not*:**
  - there is no queue and no waiting for capacity;
  - there is no `Retry-After` header, so clients get no timing guidance;
  - there is no per-client fairness or rate limiting.
- **The frontend** sends one request per user action and never auto-resubmits (`App.jsx:119–129`).

---

## 4. Local operating envelope (SCALE-004 evidence only)

> **Scope banner.** Everything in this section is from the SCALE-004 *after* run:
> - one local WSL2 host (32 logical CPUs, 7 GiB), one uvicorn process;
> - a loopback fake provider with a fixed 3 s or 5 s latency;
> - a closed-loop load generator; ₹0.
>
> It is **not an SLA**. It is **not** a claim about OpenAI latency, OpenAI rate limits, Railway resources or public-deployment capacity. Every number comes from committed `benchmarks/results/SCALE-004-after/report_tables.out` or `trials.jsonl`, except where a line cites the SCALE-004 report (`SCALE-004_ADMISSION.md`), whose figures were computed from the full raw evidence before compaction.

### 4.1 Provider-bound ceiling

- **The idealized one-attempt ceiling** implied by the budget is **32 / provider latency** completed analyses per second per process. This is arithmetic from the budget, **not a throughput guarantee**. Real throughput also depends on:
  - provider latency variance;
  - retries: a retried request holds its slot for two attempt periods, giving an idealized 32 / (2 × latency);
  - arrival pattern;
  - host and provider behaviour that was not measured.
- **Measured against that ceiling** (completed `ok` rps):

| Fake latency | Idealized ceiling | Measured (after build) |
|---|---:|---|
| 3 s | 10.67 rps | burst 10.0–10.14 (C = 32–64) |
| 5 s | 6.40 rps | burst 6.09–6.11; sustained 6.15–6.21 (C = 32–64, including zero-backoff) |
| 3 s, every request retried once | 5.33 rps | fail-first burst 5.1; fail-first sustained 4.61 |

- Peak provider in-flight was **32 at every after point**.

### 4.2 Admitted-request latency

Admitted latency tracks provider latency and does not grow with excess demand:
- **`ok` p95.** Burst 3 s: 3170–3270 ms. Burst 5 s: 5272–5302 ms. Sustained 5 s: 5312–5355 ms (max 5460). Fail-first retry: 6304–6415 ms.
- **Waiting outside the provider call.** Pre-provider p95 is 136–272 ms and post-provider p95 is 23–216 ms across all after analysis points.
- **For comparison, before admission** (C=64, 5 s, sustained), `ok` p95 was 10386 ms, with pre-provider p95 5295 ms.

### 4.3 Rejection latency

| Load shape | p50 | p95 | max |
|---|---|---|---|
| Simultaneous bursts (C=40/64) | 55.7–98.6 ms | 141.6–181.2 ms | 176.3–199.1 ms |
| Simultaneous retry burst (C=64, fail-first) | 92.0 ms | 235.1 ms | 254.6 ms |
| Sustained, clients back off 0.25 s | 1.4–1.5 ms | 3.4–10.8 ms | 157–180 ms |
| Sustained, zero backoff (storm) | 15.1 ms | 17.8 ms | 216.6 ms |

### 4.4 `/health` under overload

- **With backoff, C=40/64.** p50 is 1.8–2.0 ms, p95 3.5–27.8 ms and max 30.0–167.7 ms. All 400 after-build probes returned 200.
- **Zero-backoff storm** (39,377 rejections during the probe window). p50 is 70.8 ms, p95 155.4 ms and max 222.1 ms.

### 4.5 The storm limit

- A client resending rejections with zero backoff drives about 1,870–1,890 rejections/s. The server process then runs at **0.95–0.96 of a core** (`server_cpu_s / wall_s` in the three sustained zero-backoff trials).
- The binding resource then becomes the single event loop's CPU. Worker tokens are not the binding resource.
- Fail-fast and the 32 cap still hold, but `/health` is no longer idle-like (§4.4).
- No rate limiting exists to stop this (§7, D1).

### 4.6 Retry and outage

- Under a persistent provider outage at C=64, admitted requests fail as `provider_unavailable` after 2 attempts (p50 6141 ms, SCALE-004 report §4), and excess requests are still rejected in milliseconds.
- A transient-failure retry halves per-slot throughput, because one slot is held for two attempt periods.

---

## 5. Cost and amplification contract

### 5.1 Bounded by QuoteCheck (OBSERVED, test-enforced)

| Bound | Value | Claim |
|---|---|---|
| Concurrent provider-bound analyses | ≤ 32 per process | C1, C8 |
| Provider attempts per admitted request | ≤ 2 | C6 |
| Automatically retried failure types | connection, timeout, 5xx only | C7 |
| Provider calls for rejected or invalid requests | 0 | C3, C12 |
| Provider calls in Demo mode | 0 | C10 |
| Quote input per attempt | ≤ 12,000 characters, plus the fixed prompt and schema | C12 |
| Wall time per attempt | explicit timeout (30 s default) | C13 |

**Consequence (SUPPORTED INFERENCE).** At any instant at most 32 provider attempts per process are in flight. Spend *rate* is therefore bounded by 32 × (cost per attempt / duration per attempt). Concurrency and per-request amplification cannot multiply each other past 32 × 2 attempts for 32 requests.

### 5.2 Not bounded by QuoteCheck

- **Cumulative spend over time is not bounded by the application.**
  - Under sustained demand, spend grows linearly with time.
  - There is no authentication, public or per-client rate limiting, quota, daily cap or spend ceiling.
- **There is no output-token cap.**
  - `client.responses.create(...)` passes no `max_output_tokens` (`openai_analyzer.py:212`), so output length per attempt is limited only by the selected model's own limit.
  - Truncation by such a limit is classified `provider_incomplete_response` and is not auto-retried (C7).
- **Price per attempt depends on configuration.** `QUOTECHECK_MODEL` (`config.py:27`) selects the model, and with it the price and the output limit.
- **Abandoned requests still cost.**
  - A client that aborts or disconnects does not cancel its admitted provider work (SCALE-004 §0, SUPPORTED INFERENCE from the installed stack).
  - Cancellation keeps the slot until the provider call ends (C9).
  - The provider work, and any cost, continues.
- **Timeouts may still bill (HYPOTHESIS, not checkable at ₹0).**
  - A client-side attempt timeout may not stop provider-side generation or billing.
  - A timeout is classified transient and retried, so the worst case is two billed full-length attempts for one request.

### 5.3 What bounds cumulative spend in v1 (outside the application)

1. **Exposure policy.** The public v1 deployment runs **Demo**.
   - The observed hosted path is `metadata.model = "quotecheck-demo-analyzer"` (CURRENT_STATE, QC-2B).
   - Demo makes zero provider calls (C10).
   - OpenAI mode is **opt-in and not publicly exposed**.
   - `PROJECT_STATUS.md` already makes public rate limiting and quota control a prerequisite for any anonymous OpenAI exposure.
2. **Provider-account controls.** These are spend or usage limits on the OpenAI account. They are external, not visible from the repository, and not verified here.

### 5.4 Deferred cost instrumentation

QuoteCheck logs no token usage (`run_logger.py:95–117` has no usage field), and it sets no `max_output_tokens`. Both are **deferred** to the first of:
- the first approved paid-provider exercise;
- any plan to expose OpenAI mode publicly.

Reasons:
- every v1 run is ₹0, so usage fields would be `null` in all v1 evidence;
- `usage` is unavailable on attempts that time out or fail in transport;
- sizing an output cap needs real output-token evidence;
- a cap set too low would turn valid large analyses into `provider_incomplete_response`, which changes OpenAI-mode behaviour.

At that trigger, the cap and the usage fields should be designed together.

---

## 6. Operator guide

### 6.1 Runtime questions (A1–A10)

| # | Question | Status | How to answer |
|---|---|---|---|
| A1 | Admitted or rejected by QuoteCheck capacity? | **OBSERVED** | API `code == "capacity_exceeded"`. Log: `failure_category == "capacity_exceeded"` with `provider_attempts == 0`. Any other `analyzer == "openai"` record was admitted. |
| A2 | Was the failure application capacity, a provider rate limit, an outage, a timeout or something else? | **OBSERVED** | `failure_category`, plus `provider_status` and `cause_type` (§3). Retained logs exercise capacity and outage. The other categories are test-enforced only (`_ROUTE_CASES`, `FailureLoggingTests`). |
| A3 | How many provider attempts? | **OBSERVED** | `provider_attempts` on every OpenAI-mode record. It is `null` for pre-call configuration errors (no call was made), and in one post-analysis `internal_error` edge case where calls *were* made (§6.2). |
| A4 | What is the configured per-process budget? | **SUPPORTED INFERENCE** | A fixed code constant (`config.py:131`), test-pinned at 32. Logs show it only inside the rejection `error` string, and that string always reads `N/N` (§6.2). Logs record no build or commit, so the deployed commit determines the budget. |
| A5 | What is the scope of that budget? | **SUPPORTED INFERENCE** | Per process (C14). Logs carry no process id, so records from several processes writing to one log could not be told apart. That is not relevant to the committed single-process start command. |
| A6 | Did retry amplification occur? | **OBSERVED** (per request and in aggregate) | `provider_attempts == 2` per request; Σ attempts / admitted requests in aggregate (query C2). |
| A7 | Demo or OpenAI execution? | **OBSERVED** | `analyzer` (log) and `metadata.model` (API and log). The retained SCALE-004 logs contain only OpenAI-mode (fake) records, so the Demo side is test-enforced (`test_demo_requests_never_touch_the_provider_budget`), not exercised by the retained logs. |
| A8 | Is the local operating envelope explained by committed evidence? | **OBSERVED** (local only) | §4, from committed `report_tables.out` and `trials.jsonl`. |
| A9 | Can amplification and cost exposure be reasoned about? | Amplification **OBSERVED**; cost **SUPPORTED INFERENCE** only | §5. Attempts are logged; tokens and price are not. |
| A10 | What remains unanswerable? | **MISSING, intentionally** | See below. |

**Intentionally unanswerable in v1.** None is closure-critical. Each has a scope and a revisit trigger:

| Missing signal | Scope of the gap | Revisit trigger |
|---|---|---|
| Tokens and cost per analysis | OpenAI mode only; v1 runs are ₹0 | First approved paid exercise, or before public OpenAI exposure (§5.4) |
| The first attempt's failure cause when the retry succeeded | The success record shows only `provider_attempts: 2` | A need to diagnose transient-failure patterns on a real provider |
| In-flight count or load context when a request was admitted | Only reconstructable approximately from timestamps | Configurable budget, or capacity tuning on a real host |
| Process or build identity in log records | Relevant only with more than one process, or for log-to-commit attribution | Workers or replicas are introduced |
| End-to-end server latency for admitted requests | `latency_ms` excludes dispatch and validation (§6.2); the harness measures it client-side | A need for server-side SLO measurement |
| Durable hosted logs | Railway's local filesystem is ephemeral | Any hosted OpenAI exposure |
| Real OpenAI latency, rate limits and billing behaviour | Never measured (₹0 policy) | An approved paid exercise |

### 6.2 JSONL field semantics that matter for capacity

- **One record per `/analyze` call** that passed request validation: success, classified failure or rejection. Logging is best-effort: a write failure is swallowed so it never masks the outcome (`app.py:139–144`). Requests that fail validation (422) write **no** record (`app.py:108–136`).
- **`latency_ms` measures a different interval on each path.** It is not one comparable metric:

| Path | What `latency_ms` measures |
|---|---|
| OpenAI success | Time inside the provider attempt loop only (`openai_analyzer.py:208–231`). Excludes threadpool dispatch, response-state handling, validation and serialization. |
| OpenAI or Demo failure | Time inside `_analyze_sync` (`app.py:309`) |
| Demo success | ≈ 0. It is computed at `app.py:277`, *before* the Demo analyzer runs, so it excludes the analyzer itself. |
| Rejection | Route entry to log write, on the event loop (`app.py:228`) |

- **`error` on a rejection** is always `capacity_exceeded: provider admission budget full (C/C in flight)`. A rejection only happens at `in_flight >= capacity`, so the embedded in-flight value carries no extra information. Don't parse it. Use `failure_category` and `provider_attempts`.
- **`provider_attempts`:**
  - `0` means a capacity rejection, and only that;
  - `1` or `2` means calls were made;
  - `null` in Demo mode;
  - `null` for a `configuration_error` raised before any call (invalid timeout or missing key, `openai_analyzer.py:183–190`). No call was made.
  - **edge case:** also `null` for an `internal_error` raised *after* a successful analyzer return (`app.py:334–356`). The analyzer itself raises only `QuoteCheckError`, so this path is reachable only through a bug in post-analysis code. In that case attempts happened but are not recorded.
- **`analyzer`** is fixed at startup from `QUOTECHECK_USE_OPENAI` (`app.py:91`).

### 6.3 Validated operator commands

These use the stdlib only. Each takes one JSONL path, `LOG`.

```bash
# C1 — outcome mix: (analyzer, outcome, provider_attempts)
python3 -c 'import json,sys,collections as c; print(c.Counter((r["analyzer"], r["failure_category"] or "ok", r["provider_attempts"]) for r in map(json.loads, open(sys.argv[1]))).most_common())' "$LOG"

# C2 — admission and amplification summary
python3 -c 'import json,sys; R=[json.loads(l) for l in open(sys.argv[1])]; O=[r for r in R if r["analyzer"]=="openai"]; rej=[r for r in O if r["failure_category"]=="capacity_exceeded"]; adm=[r for r in O if r["failure_category"]!="capacity_exceeded"]; a=[r["provider_attempts"] for r in adm]; n=sum(x or 0 for x in a); print(dict(records=len(R), openai=len(O), rejected=len(rej), rejected_with_calls=sum(r["provider_attempts"]!=0 for r in rej), admitted=len(adm), provider_attempts=n, attempts_per_admitted=round(n/len(adm),3) if adm else None, retried=a.count(2), attempts_unknown=a.count(None)))' "$LOG"

# C3 — failure attribution: (category, provider_status, cause_type, retryable, attempts)
python3 -c 'import json,sys,collections as c; print(c.Counter((r["failure_category"], r["provider_status"], r["cause_type"], r["retryable"], r["provider_attempts"]) for r in map(json.loads, open(sys.argv[1])) if r["success"] is False).most_common())' "$LOG"

# C4 — capacity rejections per UTC minute
python3 -c 'import json,sys,collections as c; print(sorted(c.Counter(r["created_at"][:16] for r in map(json.loads, open(sys.argv[1])) if r["failure_category"]=="capacity_exceeded").items()))' "$LOG"
```

**How they were validated.**
- They ran verbatim against the retained SCALE-004 after-build server logs. Those files are not in Git; all 42 raw files were verified against `benchmarks/results/SCALE-004_RAW_EVIDENCE_MANIFEST.txt` first.
- Selected outputs:

| Log (`SCALE-004-after/server/…`) | C2 result |
|---|---|
| `adm_sustained_5000ms__app_runs.jsonl` | 11,017 records: 9,700 rejected (0 with calls), 1,317 admitted, 1.0 attempts per admitted |
| `adm_retry_fail_first_sustained_3000ms__app_runs.jsonl` | 4,657 rejected (0 with calls), 230 admitted, **2.0** attempts per admitted, 230 retried |
| `adm_retry_fail_always_sustained_3000ms__app_runs.jsonl` | 4,661 rejected, 232 admitted, 2.0 attempts per admitted. C3 shows `('capacity_exceeded', None, None, True, 0)` vs `('provider_unavailable', 503, 'InternalServerError', True, 2)`. |
| `adm_burst_lat3s__app_runs.jsonl` | 344 rejected (0 with calls), 613 admitted, 1.0 attempts per admitted |

- **Reconciliation.** Whole-file counts include the harness's warm-up requests, which `trials.jsonl` excludes. For every scenario, log records − Σ trial `log_records` = 5 sequential warm-up requests + 2 × ΣC burst warm-ups (277 for the 32/40/64 ladders, 133 for the C=64 retry scenarios), exactly. Every trial in `trials.jsonl` is `reconciled` and `attempts_joined`.
- **Not exercised by the retained logs:** Demo records, and the `provider_rate_limited`, `provider_timeout`, refusal, incomplete, invalid and configuration categories. Their log shape is test-enforced instead (C7, `FailureLoggingTests`).

---

## 7. Decision register (the SCALE-004 open items and SCALE-005 candidates)

| # | Candidate | Class | Evidence / reason | Revisit trigger |
|---|---|---|---|---|
| D1 | Per-client / public rate limiting | USEFUL BUT DEFER | The public path is Demo (₹0). The storm needs a non-cooperating zero-backoff client, and the frontend never auto-resubmits (§3). Behind Railway, per-IP limiting needs trusted `X-Forwarded-For` and per-process state, which is a separate design. | Before any public OpenAI exposure (already a PROJECT_STATUS prerequisite) |
| D2 | `Retry-After` on `capacity_exceeded` | USEFUL BUT DEFER | No consumer: the frontend doesn't auto-retry, and storm clients would ignore it. Any value would be a guess, because real provider latency is unmeasured. | A programmatic or auto-retrying client exists |
| D3 | Configurable 32-slot budget | NOT JUSTIFIED | One measured local point and one deployment. A knob invites values nobody has measured. Changing the constant plus its test is the deliberate path. | A second environment with its own evidence |
| D4 | Structured admission fields | NOT JUSTIFIED | A rejection's in-flight value always equals capacity. Admission state is fully derivable from `failure_category` and `provider_attempts` (A1). | Configurable budget, or more than one process |
| D5 | Admission counters / metrics endpoint | NOT JUSTIFIED | No consumer, and a metrics stack is excluded. An unauthenticated public endpoint would expose internals. The JSONL already counts (§6.3). | A metrics consumer is approved |
| D6 | Token / cost logging | USEFUL BUT DEFER | §5.4 | First approved paid exercise, or before public OpenAI exposure |
| D7 | The ~+2.5 ms CPU/request at 5 s / C=32 | NOT JUSTIFIED (to investigate now) | About 0.05% of a 5 s provider period, and it changes no envelope statement or decision. It is unattributed (SCALE-004 §E5). | It reproduces and grows in a later measurement |
| D8 | Make the sync 422 handler async | USEFUL BUT DEFER | No evidence of a problem. The handler runs in microseconds, and under a flood the event loop would likely saturate before the 8 spare tokens (an inference, not measured). | Evidence that an invalid-request flood couples `/health` |
| D9 | Open-arrival-load benchmark | NOT JUSTIFIED for v1 closure | No closure claim depends on the arrival model. The admission bounds (C1–C9) are enforced by deterministic tests that don't depend on how requests arrive. | A latency-distribution claim under open arrivals is needed |
| D10 | Real OpenAI capacity test | NOT JUSTIFIED for v1 closure | Paid, and the public path doesn't use OpenAI. The contract is stated as local-only. | Approved spend, or public OpenAI exposure |
| D11 | Cross-process coordination | NOT JUSTIFIED | Single process (C14, `railpack.json`) | Workers or replicas are introduced |
| D12 | Queueing | NOT JUSTIFIED | Fail-fast keeps admitted latency at provider latency and `/health` responsive (§4). The client is interactive. | Evidence that the rejection rate at expected demand is unacceptable |
| D13 | More uvicorn workers or replicas | NOT JUSTIFIED | Server CPU is 0.5–8.9 ms per request (after build). The ceiling is provider-bound, and replicas multiply provider concurrency and cost (§5). Only the adversarial storm is CPU-bound. | Measured CPU-bound non-adversarial load |
| D14 | Broad async OpenAI conversion | NOT JUSTIFIED | Admitted work (≤ 32) stays below the 40-token limiter, and SCALE-004 found no threadpool bottleneck. It would be a large rewrite with no measured gain. | The threadpool becomes the measured bound |

**No candidate is REQUIRED for v1 closure.**

---

## 8. Decision Gate E

**E1. Can every v1 closure-critical runtime question be answered from the existing API, logs, code and evidence? Are the intentionally unanswerable questions documented with their scope and revisit trigger?**
**PASS.**
- A1–A3, A6 and A7 are OBSERVED from the API and log fields. The A1, A3 and A6 log queries were validated on retained SCALE-004 logs (§6.3).
- A4, A5 and A9 (cost) are SUPPORTED INFERENCE from code constants, tests and topology.
- A8 is OBSERVED from committed evidence.
- A10's seven missing signals are each listed with their scope and revisit trigger (§6.1). None is needed to support a v1 closure claim.

**E2. Is every contract claim enforced by an existing test or backed by accepted evidence?**
**PASS.**
- C1–C13 and C15 each name an existing enforcing test.
- C14 is a structural scope statement, backed by source and `env.json`.
- No claim needed a new test, and the stop condition was not triggered.

**E3. Is the cost claim stated at exactly the strength the system supports?**
**PASS.**
- §1 sharpens the definition.
- §5 separates what is bounded (concurrency, per-request amplification, rejected and Demo work, input size, attempt time) from what is not (cumulative spend, output tokens, model price, abandoned work).
- §5 names the external controls and the deferral trigger.

**E4. Does every deferred item have an evidence-based revisit trigger, with no hidden "later"?**
**PASS.** §7 (D1–D14), §5.4 and the §6.1 missing-signal table.

**E5. Is the minimum SCALE-006 closure scope identified?**
**PASS.** See below.

**Gate E result: PASSED.** No SCALE-005A patch is needed.

### Recommended minimum SCALE-006 scope

SCALE-005 changes no executable file. The runtime behaviour on the final `v1/scalability` tip is therefore the code measured in SCALE-004, with one provenance caveat:
- SCALE-004's `env.json` binds the *harness* by sha256, and those hashes still match.
- It records the *backend* only as `git_commit 1e7f2ed` + `git_dirty: true`, with no backend file hashes.
- The link between the SCALE-004 evidence and the backend in `78cc5d3` therefore rests on the review bundle's attestation that no executable code changed afterwards. No hash binds them.

**Smallest sufficient SCALE-006 scope:**

1. **Final regression on the tip that will be tagged:** the full unit suite (report the actual count), `--validate-only`, and the Demo eval (27/27 schema-valid, 24/27 with AUTO-004, CONT-003 and HVAC-003).
2. **One minimal admission smoke check:**
   - command: `python -m benchmarks.run_capacity --quick --experiment admission --gate-cap 32`, written to a scratch or compact run directory;
   - **justification:** it is the cheapest way to bind the contract (C1, C3, C6, C8) to the exact code being tagged, because SCALE-004 evidence is bound to it only by attestation;
   - **pass criteria:** peak in-flight 32, rejections with 0 attempts, 2.00 attempts per admitted request under retry, all rows reconciled.
   - Commit only a compact summary, if anything.
3. **Consolidate SCALE-001–004 evidence** into the final v1 before/after story. Reference the committed evidence; do not re-run it.
4. **Resolve public-doc and status drift:**
   - `PROJECT_STATUS.md` cites "~144" tests and has no statement of capacity or overload behaviour or of the cost boundary from §1/§5;
   - the README and CLAUDE.md statements need the same check.
5. **Verify limitations and non-overclaims** against this contract (§4 banner, §5.2, §6.1).
6. **Close v1:** tag and release with your approval, following the `main` merge policy in CLAUDE.md.

**Not recommended for SCALE-006,** because no closure claim depends on them (D9, D10, D8 and §4):
- open-arrival load;
- an invalid-request flood;
- paid OpenAI verification;
- another full saturation matrix.
