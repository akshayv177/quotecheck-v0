# Review bundle — QC-4: Reliability and explicit failure handling

## 1. Ticket / phase

`docs/tickets/QC-4-reliability-hardening.md`. Hardening phase after QC-3C. Branch
`task/QC-4-reliability-hardening`. Nothing committed.

## 2. Scope summary

Make OpenAI-mode failures bounded, classified, observable, safely presented, and
testable without paid inference; never silently fall back to Demo mode. The
successful `QuoteCheckResult` contract is unchanged. Demo analyzer behaviour, the
eval corpus/graders/termsets, the prompt, and dependencies are untouched.

## 3. Previous reliability behaviour

- `backend/core/openai_analyzer.py` built `OpenAI(api_key=…)` per request with **no
  `timeout`** (SDK default 600s) and **no `max_retries`** override (SDK default 2 → up
  to 3 hidden provider calls, including on 429).
- Structured output was read with `json.loads(resp.output_text.strip())` — **no**
  check of `resp.status`, `resp.incomplete_details`, `resp.error`, refusal output
  items, or empty `output_text`.
- Any failure (SDK exception, `json.JSONDecodeError`, `pydantic.ValidationError`, the
  pre-flight missing-key `RuntimeError`) propagated uncaught. `backend/app.py` logged
  one JSONL record with `error=f"{type(e).__name__}: {e}"` (raw `str(exc)`) then bare
  `raise` → FastAPI default **HTTP 500 `{"detail":"Internal Server Error"}`**, no
  structured code, no `request_id` returned.
- `frontend/src/App.jsx` showed `HTTP 500: Internal Server Error` verbatim in the
  error card; client abort at 55s.
- No fallback to Demo on failure (already intentional; QC-4 keeps and test-guards it).

## 4. Installed OpenAI SDK / client behaviour inspected

`openai==2.24.0`, Python 3.11 conda env `quotecheck`. `httpx==0.28.1`,
`fastapi==0.128.6` already present (so `fastapi.testclient.TestClient` is usable — no
new dependency).

- `openai/_constants.py`: `DEFAULT_MAX_RETRIES = 2`,
  `DEFAULT_TIMEOUT = httpx.Timeout(timeout=600, connect=5.0)`.
- `openai/_base_client.py` `SyncAPIClient.request`:
  `for retries_taken in range(max_retries + 1):` — **`max_retries` is a retry count;
  `max_retries=0` ⇒ exactly one HTTP attempt, no `Retry-After` sleep, no backoff.**
- `_should_retry`: SDK would retry 408 / 409 / 429 / ≥ 500 and honour `x-should-retry`
  / `Retry-After`. Disabling SDK retry (`max_retries=0`) removes all of that from the
  hidden path so QuoteCheck's loop is the single retry owner.
- Exception hierarchy: `APITimeoutError` ⊂ `APIConnectionError` ⊂ `APIError`;
  `RateLimitError`/`InternalServerError`/`AuthenticationError`/`BadRequestError`/… ⊂
  `APIStatusError` ⊂ `APIError`; `APIResponseValidationError` ⊂ `APIError`.
  `APIStatusError.status_code` and `.request_id` (from `x-request-id`) available.
- `client.responses.create` is used (not `.parse`). Even `.parse` does **not** raise
  on refusal/incomplete — the caller must inspect the `Response`:
  `.status` ∈ {completed, failed, in_progress, queued, cancelled, incomplete};
  `.incomplete_details.reason` ∈ {max_output_tokens, content_filter} | None;
  `.error` (ResponseError) | None; a refusal is an `output[].content[]` part with
  `type == "refusal"`; `.output_text` is `""` when there is no text part.

## 5. Final failure taxonomy

`backend/core/errors.py` — `FailureCategory` (str Enum), 8 values:

`provider_timeout`, `provider_unavailable`, `provider_rate_limited`,
`provider_refusal`, `provider_incomplete_response`, `invalid_model_output`,
`configuration_error`, `internal_error`.

Provider/transport vs model/response vs application/configuration are kept
conceptually separate. One `_SPECS` table maps each category to
`(http_status, retryable, user_message)`. `QuoteCheckError` carries the original
`cause` for tests but only ever logs `cause_type` (the class name).

## 6. Failure mapping table

`retryable` = "a manual user retry may reasonably succeed" — distinct from
"auto-retried".

| Failure | Category | Auto-retry? | User-retryable | HTTP | User message |
|---|---|:--:|:--:|:--:|---|
| `APITimeoutError` | `provider_timeout` | yes (≤1) | yes | 504 | The analysis service took too long to respond. Please try again. |
| `APIConnectionError` (non-timeout) / `InternalServerError` / `APIStatusError` ≥ 500 | `provider_unavailable` | yes (≤1) | yes | 503 | The analysis service is temporarily unavailable. Please try again shortly. |
| `RateLimitError` (429) | `provider_rate_limited` | **no** | yes | 429 | The analysis service is busy right now. Please wait a moment and try again. |
| refusal output part / `incomplete_details.reason == "content_filter"` | `provider_refusal` | no | no | 502 | The analysis service could not complete this request. |
| `resp.status` in {incomplete, failed} / `incomplete_details` / `resp.error` | `provider_incomplete_response` | no | yes | 502 | The analysis could not be completed reliably. Please try again. |
| empty `output_text` / `JSONDecodeError` / `pydantic.ValidationError` / `APIResponseValidationError` | `invalid_model_output` | no | no | 502 | The analysis could not be completed reliably. Please try again. |
| missing `OPENAI_API_KEY` / bad `QUOTECHECK_OPENAI_TIMEOUT_SECONDS` / `AuthenticationError` / `PermissionDeniedError` / `NotFoundError` / `BadRequestError` | `configuration_error` | no | no | 503 | AI analysis is temporarily unavailable. |
| any other exception | `internal_error` | no | no | 500 | Something went wrong while analyzing this quote. Please try again. |

Log fields per failure: `failure_category`, `retryable`, `cause_type`,
`provider_status`, `provider_request_id`, `response_status`, `incomplete_reason`,
`provider_attempts` (see §12).

## 7. Retry ownership and maximum attempts

**QuoteCheck owns the single automatic retry; the SDK's own retry is disabled.**

- Client: `OpenAI(api_key=…, timeout=<validated>, max_retries=0)`.
- `config.OPENAI_MAX_RETRIES = 1` (fixed code constant, **not** env-overridable —
  retry count affects cost/amplification). `config.OPENAI_MAX_ATTEMPTS = 2`.
- `analyze_quote_openai` runs a bounded, no-backoff loop
  (`while provider_attempts < OPENAI_MAX_ATTEMPTS`). It retries once **only** when
  `is_transient_openai_exception(exc)` is true — i.e. `APIConnectionError` (incl.
  `APITimeoutError`), `InternalServerError`, or `APIStatusError` with
  `status_code >= 500`. `RateLimitError` and everything else make **exactly one**
  provider call.
- **Maximum provider calls for one `/analyze` request = 2.** `provider_attempts` in
  the response-path error and in the log is the **observed** count from the loop,
  never a guessed ceiling.
- No exponential-backoff machinery; no `Retry-After` sleeping; no semantic repair
  loop; no second paid call to fix JSON.

## 8. Timeout configuration

- `QUOTECHECK_OPENAI_TIMEOUT_SECONDS`, default **30s** (`config.OPENAI_TIMEOUT_DEFAULT_SECONDS`).
- Validated lazily by `resolve_openai_timeout_seconds()` at the top of
  `analyze_quote_openai`: must parse to a finite, strictly-positive float, else
  `QuoteCheckError(CONFIGURATION_ERROR)` **before** any client construction or
  provider call. Covers non-numeric, `0`, negative, `nan`, `inf`.
- Backend provider-call budget: 2 × 30s ≈ 60s. Frontend `REQUEST_TIMEOUT_MS` raised
  55s → **70s** so the browser abort sits above that budget and a classified backend
  error normally arrives first; the browser abort is a final safety bound only.
- A test (`TimeoutBudgetTests`) parses `REQUEST_TIMEOUT_MS` from `App.jsx` and
  asserts `> 1000 * OPENAI_MAX_ATTEMPTS * OPENAI_TIMEOUT_DEFAULT_SECONDS`.

## 9. OpenAI response-state handling

`_extract_structured_payload(resp)` in `openai_analyzer.py`, in order:

1. refusal output part present **or** `incomplete_details.reason == "content_filter"`
   → `provider_refusal` (carries `response_status`).
2. `resp.status` in {incomplete, failed} **or** `incomplete_details` set **or**
   `resp.error` set → `provider_incomplete_response` (carries `response_status`,
   `incomplete_reason`).
3. `resp.output_text.strip() == ""` → `invalid_model_output` ("empty structured output").
4. `json.loads` failure or non-dict → `invalid_model_output`.

A 2xx HTTP response is never assumed to contain a usable result. Fabricated
`Response`-shaped objects (matching `openai==2.24.0` type definitions) exercise each
branch — see §15.

## 10. Structured-output / schema failure behaviour

Structured Outputs (strict JSON Schema) is unchanged. After server-truth metadata is
written, `QuoteCheckResult.model_validate(payload)` still runs; on failure →
`QuoteCheckError(INVALID_MODEL_OUTPUT, cause=exc)`. **No** invented defaults, **no**
partial validation, **no** Demo switch, **no** second paid call. `schema_valid` is
now effectively derived (the analyzer only returns on a successful validation).

## 11. API error contract

`@app.exception_handler(QuoteCheckError)` returns
`JSONResponse(status_code=err.http_status, content=error_response_body(err))` where
the body is exactly:

```json
{ "detail": { "code": "<category>", "message": "<user-safe>", "retryable": <bool>, "request_id": "<uuid>" } }
```

Nothing else — no stack trace, API key, raw provider payload, internal filename, or
raw exception text. `request_id` is set from the route's `uuid4` when the error
doesn't already carry one. An unclassified exception is wrapped as
`QuoteCheckError(INTERNAL_ERROR, cause=e)` → 500 with `code: "internal_error"`.

## 12. Failure logging

`backend/core/run_logger.py` gains optional keyword params / record keys (existing
callers unaffected): `analyzer` (`openai`/`demo`), `success`, `failure_category`,
`retryable`, `cause_type` (class name only), `provider_status`,
`provider_request_id`, `response_status`, `incomplete_reason`, `provider_attempts`.
`error` is now a bounded application-authored string
(`QuoteCheckError.log_error_field()` → `"<category>: <fixed detail>"` or
`"<category> (<cause_type>)"`), **never** `str(provider_exception)`. `provider_attempts`
is the observed loop count. Provenance stays mode-accurate on the failure path
(`failure_model = MODEL if USE_OPENAI else DEMO_ANALYZER_MODEL`). All `log_app_run`
calls in the route are wrapped in `_safe_log` so a logging failure cannot mask the
analysis failure. Still exactly one JSONL record per request.

## 13. No-fallback proof

- `NoDemoFallbackTests.test_openai_failure_never_calls_stub_for_any_category` — for
  every `FailureCategory`, OpenAI mode + forced `QuoteCheckError` ⇒
  `analyze_quote_stub` (MagicMock) `assert_not_called()`.
- `NoDemoFallbackTests.test_stub_not_called_when_provider_boundary_raises` — real
  `analyze_quote_openai` with the OpenAI client patched to raise twice ⇒ HTTP 504,
  stub never called.
- Code: `backend/app.py` selects the analyzer once from `USE_OPENAI`; the `except`
  branches log and re-raise a `QuoteCheckError`; there is no path from an OpenAI
  failure to `analyze_quote_stub`.

## 14. Frontend behaviour

`frontend/src/App.jsx` only:

- `analyzeQuote` `!r.ok` branch tries `await r.json()`; if `body.detail` has
  `code`+`message` it throws a tagged `kind:"api"` error carrying
  `code`/`retryable`/`requestId`. Any parse failure falls back to a single generic
  `HTTP <status>` error (retained).
- `catch` maps `kind:"api"` to `err = { kind, message, code, retryable, requestId }`;
  `network` / `timeout` / `http` / `other` unchanged.
- Error card shows `err.message` (the backend's user-safe copy); the "Check that the
  backend is running on port 8000" hint is suppressed for `api` failures; `request_id:`
  is shown in small print for `api` failures. No new components, no layout change.
- `REQUEST_TIMEOUT_MS` 55_000 → 70_000 and the matching "over 55 seconds" copy → "70".
- No browser auto-resubmit (there was none; unchanged).
- `npm run build` and `npm run lint` both clean.

## 15. Automated reliability tests

`eval/tests/test_openai_reliability.py` — 42 stdlib `unittest` cases, **zero paid
calls** (OpenAI client boundary patched; fabricated `Response`-shaped objects and
real `openai` exception instances). Groups:

- `ClassificationTests` (8) — each SDK exception → category; transient set is exactly
  connection/timeout/≥500.
- `ResponseStateTests` (6) — refusal, content_filter, incomplete, empty, non-JSON,
  schema-violation; each makes 1 provider call.
- `ConfigurationTests` (9) — missing key (None/empty); timeout non-numeric / `0` /
  negative / `nan` / `inf` → `configuration_error` with **0** provider calls; valid
  override passes `timeout=12.5` to the client.
- `RetryOwnershipTests` (7) — client built with `max_retries=0` and
  `timeout=30.0`; transient→success reports `provider_attempts=2`; two transient
  failures stop after exactly 2; 429 = 1 call, not retried, `provider_status=429`,
  `provider_request_id` captured; terminal failure = 1 call; refusal/incomplete/empty
  = 1 call each; `OPENAI_MAX_ATTEMPTS == 2`.
- `NoDemoFallbackTests` (2) — §13.
- `RouteErrorContractTests` (4) — every category → expected HTTP status; body is
  exactly `{"detail": {code, message, retryable, request_id}}`; unclassified →
  500 `internal_error`; a `cause` containing `sk-live-SECRET…`/`stacktrace`/a file
  path never appears in `r.text`; `request_id` is a UUID.
- `FailureLoggingTests` (3) — failed run records `success=false`, `analyzer=openai`,
  `failure_category`, `retryable`, `cause_type="APITimeoutError"`,
  `provider_attempts`, and a `request_id` matching the response body; `error`
  starts with the category and does **not** contain the raw "timed out" text;
  observed `provider_attempts=2` from the real loop; a `log_app_run` that raises
  `OSError` still yields the correct 504.
- `ExistingBehaviourTests` (3) — a valid fabricated `Response` → HTTP 200 valid
  `QuoteCheckResult`, `success=true`, `provider_attempts=1`; Demo mode still 200 with
  `analyzer=demo` and `provider_attempts=null`; `analyze_quote_stub` still returns a
  `QuoteCheckResult`.
- `TimeoutBudgetTests` (1) — frontend abort > backend provider-call budget.

Full harness: `python -m unittest discover -s eval/tests -p 'test_*.py'` → **Ran 118
tests … OK** (was 76; +42).

## 16. Demo eval regression result

```
$ python -m eval.run_eval --validate-only
… OK — 27 cases, 6 domains, 9 categories, 0 errors.

$ python -m eval.run_eval --mode demo
27/27 schema-valid; 24/27 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation (known Demo-mode gaps are retained, not suppressed).
```

Identical to the committed QC-3C baseline (`eval/results/summary_20260829T115912Z.md`).
The transient `run_*/summary_*` artifacts produced by these QC-4 runs were deleted —
**no new baseline committed** (behaviour unchanged).

## 17. Acceptance-criteria table

| # | Criterion | Evidence |
|---|---|---|
| 1 | Current OpenAI failure behaviour inspected first | §3, §4; plan file |
| 2 | SDK retry/timeout semantics understood | §4 (`range(max_retries + 1)`, `max_retries=0` ⇒ 1 attempt) |
| 3 | Small failure taxonomy exists | `backend/core/errors.py` `FailureCategory` (8); §5 |
| 4 | Timeout explicitly bounded + configurable | `QUOTECHECK_OPENAI_TIMEOUT_SECONDS` (30s); `resolve_openai_timeout_seconds`; `ConfigurationTests` |
| 5 | Retry ownership unambiguous | `max_retries=0` + app loop; §7; `RetryOwnershipTests` |
| 6 | Max provider attempts documented | 2 (`OPENAI_MAX_ATTEMPTS`); §7; README; CURRENT_STATE |
| 7 | Only transient failures auto-retried | `is_transient_openai_exception`; 429 not retried; `RetryOwnershipTests` |
| 8 | Refusal handled explicitly | `_extract_structured_payload` step 1; `ResponseStateTests.test_refusal` |
| 9 | Incomplete response handled explicitly | step 2; `test_incomplete_response` |
| 10 | Invalid structured/model output handled explicitly | steps 3–4 + post-validation; `test_*_invalid_model_output` |
| 11 | Pydantic validation remains mandatory | `openai_analyzer.py` `model_validate` retained; §10 |
| 12 | Config errors distinguishable | `configuration_error` category; `ConfigurationTests` |
| 13 | Unexpected internal errors distinguishable | `internal_error`; `test_unclassified_exception_becomes_internal_error_500` |
| 14 | Stable machine-readable code | `detail.code`; `RouteErrorContractTests` |
| 15 | User-safe message | `_SPECS` messages; `RouteErrorContractTests` |
| 16 | request_id preserved on failure | route sets it; `test_request_id_preserved_when_error_has_none`; logging test cross-check |
| 17 | Failed runs record category/provenance/retry info | §12; `FailureLoggingTests` |
| 18 | Raw diagnostics not exposed | `error_response_body` shape; `test_raw_exception_detail_not_exposed`; `error` field test |
| 19 | OpenAI failure never invokes Demo | §13 |
| 20 | Frontend classified copy, no redesign | §14; build/lint clean |
| 21 | No browser auto-resubmit | §14; no retry code in `App.jsx` |
| 22 | Mocks/fakes only, no paid calls | §15 |
| 23 | Existing eval-harness tests pass | 118/118 OK |
| 24 | Demo eval 27/27 · 24/27 | §16 |
| 25 | Corpus/graders/termsets unchanged | `git diff` empty (§20) |
| 26 | Demo analyzer unchanged | `git diff -- backend/core/stub_analyzer.py` empty (§20) |
| 27 | No unnecessary dependency | `backend/requirements.txt` unchanged; TestClient uses already-present httpx |
| 28 | No deployment work | none added |
| 29 | Nothing committed | working tree only (§20) |

## 18. Exact commands and results

```
$ conda run -n quotecheck python -m compileall -q backend eval
OK   (exit 0)

$ conda run -n quotecheck python -m unittest discover -s eval/tests -p 'test_*.py'
......................................................................................................................
----------------------------------------------------------------------
Ran 118 tests in 0.806s
OK

$ conda run -n quotecheck python -m unittest eval.tests.test_openai_reliability
Ran 42 tests in 0.881s
OK

$ conda run -n quotecheck python -m eval.run_eval --validate-only
[1]…[11] all pass
OK — 27 cases, 6 domains, 9 categories, 0 errors.   (exit 0)

$ conda run -n quotecheck python -m eval.run_eval --mode demo
27/27 schema-valid; 24/27 deterministic cases pass.   (exit non-zero: retained known gaps)
(transient eval/results/run_* + summary_* artifacts deleted; no baseline committed)

$ cd frontend && npm run build
✓ built in 1.17s   (dist/index.html, index-*.css, index-*.js)

$ cd frontend && npm run lint
eslint .   (no output, exit 0)

$ git diff --check
(no output — clean)

$ git diff -- eval/cases eval/termsets.json eval/rubric.md eval/graders.py \
      backend/core/stub_analyzer.py backend/core/prompt.py backend/core/schema.py \
      backend/core/schema_export.py eval/results
(empty)
```

## 19. Remaining limitations

- No public rate limiting / quota control, no input-length cap, no
  durable/centralized logging, no live-deployment verification — OpenAI mode is not
  yet safe to expose anonymously (deployment-preparation ticket).
- The exact wire shape of a real refusal / incomplete `Response` from the live model
  is simulated from `openai==2.24.0` type definitions, not observed; classification
  is tested against fabricated objects matching those types. No end-to-end OpenAI-mode
  run (still no CI, still no `--allow-paid` run here).
- Whether the deployed model ever emits strict-schema-violating JSON in practice is
  unknowable without paid runs; QC-4 tests the handling, not the frequency.
- Semantic (Layer B) eval remains a human rubric.
- No semantic repair when output fails validation — deliberate.

## 20. git status / diff stat

```
$ git status --short
 M README.md
 M backend/.env.example
 M backend/app.py
 M backend/core/config.py
 M backend/core/openai_analyzer.py
 M backend/core/run_logger.py
 M docs/CURRENT_STATE.md
 M frontend/src/App.jsx
?? backend/core/errors.py
?? docs/review/REVIEW_BUNDLE__QC-4-reliability-hardening.md
?? docs/tickets/QC-4-reliability-hardening.md
?? eval/tests/test_openai_reliability.py

$ git diff --stat
 README.md                       |  67 ++++++++++--
 backend/.env.example            |   5 +
 backend/app.py                  |  84 +++++++++++++--
 backend/core/config.py          |  17 ++++
 backend/core/openai_analyzer.py | 219 +++++++++++++++++++++++++++++++++++-----
 backend/core/run_logger.py      |  36 ++++++-
 docs/CURRENT_STATE.md           | 127 ++++++++++++++++++++---
 frontend/src/App.jsx            |  33 +++++-
 8 files changed, 525 insertions(+), 63 deletions(-)
```

New files: `backend/core/errors.py`, `eval/tests/test_openai_reliability.py`,
`docs/tickets/QC-4-reliability-hardening.md`, this bundle. Nothing committed.
No paid OpenAI inference at any point.
