# QC-4 — Reliability and explicit failure handling

## 1. Goal

Make OpenAI-mode failures **bounded, classified, observable, safely presented to the
frontend, and testable without paid inference**, with an absolute invariant that an
OpenAI-mode failure never silently runs the Demo analyzer.

Specifically:

1. A small failure taxonomy (`backend/core/errors.py`) maps every provider,
   model-output, and configuration failure to one category, an HTTP status, a
   user-safe message, and a `retryable` flag.
2. The OpenAI request has an explicit bounded timeout
   (`QUOTECHECK_OPENAI_TIMEOUT_SECONDS`, default 30s).
3. QuoteCheck owns the single automatic retry: the SDK client is built with
   `max_retries=0`; a bounded no-backoff loop retries **once**, only for clearly
   transient provider/transport failures (connection, timeout, provider ≥ 500).
   Maximum provider attempts per `/analyze` request = **2**.
4. Rate limiting (429) is surfaced as user-retryable but is **not** auto-retried.
5. Refusal, incomplete response, empty structured content, and schema-invalid output
   are each recognised explicitly. Final Pydantic validation stays mandatory; there is
   no repair loop and no second paid call to "fix the JSON".
6. `/analyze` failures return a stable body
   `{"detail": {code, message, retryable, request_id}}` — no stack traces, API keys,
   raw provider payloads, or internal filenames.
7. Failed runs are logged to `logs/app_runs.jsonl` with sanitized classification
   fields (category, provenance, retryable, `cause_type`, observed `provider_attempts`,
   provider/response status) — never a raw exception dump.
8. The frontend consumes the structured body and shows classified copy instead of
   `HTTP 500: Internal Server Error`. No redesign, no browser auto-resubmit. The
   client abort bound is raised to 70s so it sits above the backend provider-call
   budget.

The successful `QuoteCheckResult` contract is unchanged. This is not a deployment
ticket.

## 2. Context

Prior tickets delivered the domain-neutral contract (QC-1B), the deterministic eval
runner (QC-3B), and the Demo contract alignment to 24/27 (QC-3C). The OpenAI
execution path was explicitly deferred: `openai_analyzer.py` constructed the client
with no timeout (SDK default 600s) and no `max_retries` override (SDK default 2 → up
to 3 hidden provider calls). Any failure — SDK exception, `json.JSONDecodeError`,
`pydantic.ValidationError`, missing key — propagated uncaught to FastAPI's default
**HTTP 500 `{"detail":"Internal Server Error"}`**, with `str(exc)` written to the run
log and shown verbatim in the frontend error card. Refusal / incomplete / empty
responses were not inspected at all.

Installed SDK inspected: `openai==2.24.0`. `max_retries` is a retry count
(`_base_client.request`: `for retries_taken in range(max_retries + 1)`), so
`max_retries=0` ⇒ exactly one HTTP attempt, no backoff. Exception hierarchy and
`Response` fields (`.status`, `.incomplete_details.reason`, `.error`, refusal output
parts, `.output_text`) confirmed from SDK source.

## 3. Strict file scope

Created:

- `backend/core/errors.py`
- `eval/tests/test_openai_reliability.py`
- `docs/tickets/QC-4-reliability-hardening.md`
- `docs/review/REVIEW_BUNDLE__QC-4-reliability-hardening.md`

Edited:

- `backend/core/config.py` — `QUOTECHECK_OPENAI_TIMEOUT_SECONDS`, raw value kept for
  lazy validation; `OPENAI_MAX_RETRIES = 1`, `OPENAI_MAX_ATTEMPTS = 2` constants.
- `backend/core/openai_analyzer.py` — timeout validation, `max_retries=0` client,
  bounded retry loop, response-state inspection, `QuoteCheckError` raising, 3-tuple
  return.
- `backend/app.py` — `QuoteCheckError` exception handler, structured failure body,
  route catch/wrap, sanitized + guarded failure logging.
- `backend/core/run_logger.py` — new optional sanitized fields.
- `frontend/src/App.jsx` — parse structured error body, classified copy,
  `REQUEST_TIMEOUT_MS` 55_000 → 70_000 and matching copy.
- `docs/CURRENT_STATE.md` — `### Added in QC-4`, architecture bullets, gap updates.
- `README.md` — reliability paragraph, API failure body, updated field list.

## 4. Out of scope

Deployment config, public rate limiting, auth, quotas/accounts, persistent DB,
queue/job system, circuit-breaker/resilience framework, observability vendor,
tracing platform, RAG, agent framework, prompt redesign, model-quality work,
eval-corpus/grader/termset changes, Demo analyzer behaviour changes, frontend
redesign, automatic Demo fallback, exponential-backoff machinery, new dependencies.

## 5. Acceptance criteria

1. Current OpenAI failure behaviour inspected before editing.
2. Installed SDK retry/timeout semantics explicitly understood (`max_retries` is a
   retry count; `max_retries=0` ⇒ one attempt).
3. Small failure taxonomy exists (`FailureCategory`, 8 values).
4. Timeout is explicitly bounded and configurable
   (`QUOTECHECK_OPENAI_TIMEOUT_SECONDS`, default 30s); malformed value ⇒
   `configuration_error`.
5. Retry ownership is unambiguous — QuoteCheck owns it, SDK retry disabled.
6. Maximum provider attempts for one request documented = 2.
7. Only clearly transient failures are auto-retried (connection, timeout, ≥ 500);
   429 is not.
8-11. Refusal, incomplete response, invalid structured/model output each handled
   explicitly; Pydantic validation remains mandatory; no repair loop.
12-13. Configuration errors and unexpected internal errors are distinguishable from
   provider/model failures.
14-16. Failure responses carry a stable machine-readable `code`, a user-safe
   `message`, and preserve `request_id`.
17. Failed runs record category / provenance / retryable / observed attempt count.
18. Raw internal/provider diagnostics are not exposed to users.
19. OpenAI failure never invokes `analyze_quote_stub` (test-guarded).
20. Frontend presents classified failure copy without redesign.
21. Browser does not auto-issue another paid request.
22. Reliability behaviour is covered by mocks/fakes, not paid calls.
23. Existing eval-harness tests still pass.
24. Demo eval remains 27/27 schema-valid and 24/27 deterministic-pass.
25-26. Eval corpus/graders/termsets and Demo analyzer behaviour unchanged.
27. No unnecessary dependency added.
28. No deployment work included.
29. Nothing committed until user review.

## 6. Commands to run

```bash
conda run -n quotecheck python -m compileall backend eval
conda run -n quotecheck python -m unittest discover -s eval/tests -p 'test_*.py' -v
conda run -n quotecheck python -m eval.run_eval --validate-only
conda run -n quotecheck python -m eval.run_eval --mode demo
cd frontend && npm run build && npm run lint
git diff --check
git diff -- eval/cases eval/termsets.json eval/rubric.md eval/graders.py backend/core/stub_analyzer.py   # empty
git status --short && git diff --stat
```

## 7. Definition of done

- All commands above run with real output recorded in the review bundle.
- `--mode demo` is exactly 27/27 schema-valid and 24/27 deterministic-pass; no new
  baseline committed (behaviour unchanged).
- New reliability suite passes with zero paid API calls.
- `git diff` for eval corpus/graders/termsets and `backend/core/stub_analyzer.py` is
  empty.
- Review bundle written; `docs/CURRENT_STATE.md` and `README.md` updated truthfully.
- Nothing committed.
