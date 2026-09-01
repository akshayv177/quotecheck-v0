# QuoteCheck

**Understand a service quote before you approve it.**

QuoteCheck turns a pasted service, maintenance, repair, parts, or vendor quote into a
structured review: what each line item appears to mean, what is vague or bundled, what
evidence to request, what to ask the vendor, and what remains uncertain. It is an
explanation-first tool, not a price checker.

### ▶ Live demo — [quotecheck-frontend.vercel.app](https://quotecheck-frontend.vercel.app)

No sign-up or API key required. The observed hosted path uses QuoteCheck's
deterministic Demo analyzer with zero provider calls; successful analyses are validated
against the same `QuoteCheckResult` contract as the OpenAI path.

[Engineering highlights](#engineering-highlights) ·
[Architecture](#architecture) ·
[Evaluation](#evaluation) ·
[Live deployment](#live-deployment) ·
[Limitations](#limitations) ·
[Run locally](#run-locally)

> **Not safety advice; verify with a qualified professional.** QuoteCheck is an
> early-stage implementation — see [Limitations](#limitations).

---

## What QuoteCheck does

You paste raw quote text — from a garage, contractor, appliance technician, or any
other vendor — and get back a structured report:

- **Explains each line item** in plain language: what it is and why a vendor might
  recommend it, before any risk judgment.
- **Flags what is vague, bundled, or confusing** — "shop supplies", "misc service
  charge", "materials as required" are surfaced rather than passed through silently.
- **Assigns a risk level** (red / yellow / green) with a short rationale.
- **Generates questions to ask the vendor** before approving.
- **Lists things to verify** and the evidence to request (measurements, photos,
  diagnostic codes).
- **States uncertainty explicitly** instead of inventing certainty — "needs
  clarification" is a valid, common outcome.

Domain-neutral by design: vehicle servicing, HVAC/appliance repair, plumbing and
electrical work, contractor and renovation quotes, electronics repair, and generic
parts/labour invoices.

### Not in scope

QuoteCheck does **not** benchmark market prices, judge whether a price is objectively
fair, score vendor trustworthiness, or verify vendor claims against external
authoritative sources. It does not replace a qualified professional's judgment. These
are deliberate product non-goals, recorded in [`SPEC.md`](SPEC.md).

---

## Product preview

![QuoteCheck UI showing a structured service quote analysis report](docs/assets/quotecheck-ui.png)

One example from the cross-domain Demo pack — an excerpt from a real captured response
(full file: [`examples/sample_output.json`](examples/sample_output.json)):

```json
{
  "name_raw": "Brake service/ pads (from quote)",
  "explanation": "Brake pads are the friction material that presses on the rotor to slow the vehicle. A shop typically recommends replacement when pad thickness drops below a safe threshold or the rotor shows wear.",
  "risk_level": "red",
  "recommended_action": "needs_inspection",
  "vague_or_confusing": false,
  "evidence_needed": ["Pad thickness measurement (mm)", "Rotor condition photo", "Reason for replacement"]
}
```

The same quote's "Shop supplies / misc service charge" line comes back with
`"vague_or_confusing": true`. Six captured cross-domain reports — vehicle, AC/appliance,
home maintenance, a vague-charges parts quote, and a genuinely under-specified quote —
are in [`examples/README.md`](examples/README.md).

---

## Engineering highlights

- **Schema-first contract.** A Pydantic `QuoteCheckResult` defines the canonical result
  contract consumed by the API, the UI, and the eval harness. Successful analysis
  results rendered by the UI have been validated against that contract.
- **Structured Outputs with mandatory validation.** The OpenAI path calls the Responses
  API with a strict JSON Schema generated *from* the Pydantic contract
  (`backend/core/schema_export.py`), then re-validates the response with Pydantic
  before returning it. Output that cannot become a valid result is reported, never
  patched.
- **Deterministic Demo analyzer.** The default path is a keyword-heuristic analyzer
  that makes zero provider calls, costs nothing, and needs no API key — so anyone can
  clone the repo or open the live demo and get a real, schema-valid response.
- **One analyzer, chosen once by configuration.** No silent fallback: an OpenAI-path
  failure returns a classified error, it never quietly serves Demo output instead.
- **Honest provenance in every response.** `metadata` carries `request_id`,
  `prompt_version`, `model`, `created_at`, `latency_ms`, and `schema_valid`; the UI
  badge and the run logs are derived from the same field, so a Demo response can never
  claim an OpenAI model produced it.
- **Structured failure taxonomy.** Eight failure categories, each mapped once to an
  HTTP status, a `retryable` flag, and a user-safe message — no stack traces, keys, or
  raw provider payloads reach the client.
- **Bounded timeout and retry.** Explicit per-attempt timeout (default 30s, against the
  SDK's 600s default), SDK retries disabled, at most one application-owned retry for
  transient failures — **maximum two provider calls per request**.
- **Versioned prompt artifacts.** `PROMPT_VERSION` (`quotecheck_v0.4`) ships in both
  API responses and run logs, so a prompt change is traceable as a product change.
- **Exact-origin CORS.** Comma-separated exact browser origins parsed with
  `urllib.parse.urlsplit`; `*`, a path/query/fragment, or an empty value fails at import.
- **Server-side input bound.** `quote_text` is capped at 12,000 characters, enforced by
  the schema and mirrored in the UI as a character counter.
- **Per-request JSONL observability.** One sanitized record per `/analyze` call —
  provenance, latency, schema validity, risk counts, uncertainty, and on failure the
  category, retryable flag, exception class name, and observed provider-attempt count.
- **Cost-aware evaluation.** The eval runner defaults to Demo mode; `--mode openai`
  exits before any billed inference unless `--allow-paid` is passed explicitly.
- **Public deployment.** Vercel frontend, Railway FastAPI backend, driven by a minimal
  repo-root [`railpack.json`](railpack.json).

---

## Architecture

```
Browser (React / Vite SPA)
   │  POST /analyze  { quote_text }
   ▼
FastAPI backend
   │  assigns request_id, measures latency
   ▼
Analyzer selected by configuration (QUOTECHECK_USE_OPENAI)
   ├── deterministic Demo analyzer      (default, no provider call)
   └── OpenAI Structured Outputs path   (opt-in)
   ▼
Pydantic QuoteCheckResult validation  (mandatory, both paths)
   ▼
JSON response + run metadata  →  logs/app_runs.jsonl (append-only JSONL trace)
```

The analyzer is chosen once by configuration, not negotiated per request. **The
observed public deployment executes the deterministic Demo analyzer** — live
`/analyze` responses report `metadata.model = "quotecheck-demo-analyzer"`. The OpenAI
path is a repository capability exercised locally; it is not the runtime observed in
the hosted verification below.

### Demo mode vs. OpenAI mode

| | Demo mode (default) | OpenAI mode (opt-in) |
|---|---|---|
| Config | `QUOTECHECK_USE_OPENAI=0` | `QUOTECHECK_USE_OPENAI=1` + `OPENAI_API_KEY` |
| Analyzer | deterministic keyword heuristics (`backend/core/stub_analyzer.py`) | OpenAI Responses API + strict Structured Outputs |
| Provider calls | none | at most 2 per request |
| `metadata.model` | `quotecheck-demo-analyzer` | the configured `QUOTECHECK_MODEL` |

Demo mode is a stand-in for realistic responses, not an accuracy claim: it recognizes
a small fixed keyword set per domain and is **not** equivalent to OpenAI-mode output.
Local setup for either mode is in
[Local demo and development](docs/LOCAL_DEMO.md).

### API contract

`POST /analyze` accepts a required, non-empty `quote_text` of up to 12,000 characters
and returns a validated `QuoteCheckResult`. `GET /health` returns `{"status": "ok"}`.

Failures use one stable, user-safe envelope:

```json
{ "detail": { "code": "provider_timeout", "message": "The analysis service took too long to respond. Please try again.", "retryable": true, "request_id": "…" } }
```

Provider transport failures, refusals, incomplete generations, invalid model output,
configuration errors, internal errors, and request validation are each classified
explicitly under their own `code`. `retryable` means a manual retry may reasonably
succeed — it does *not* mean QuoteCheck retried automatically.

The result contract itself is defined in `backend/core/schema.py`;
[`SPEC.md`](SPEC.md) describes the product contract and output principles behind it.

---

## Reliability and failure handling

OpenAI-path failures are explicit and bounded rather than swallowed:

- **Explicit per-attempt timeout** (`QUOTECHECK_OPENAI_TIMEOUT_SECONDS`, default 30s).
- **At most two provider calls per request.** SDK retries are disabled
  (`max_retries=0`); one application-owned retry covers only transient connection /
  timeout / provider-5xx failures. Rate limiting (429) is surfaced as user-retryable
  but is not auto-retried. No exponential backoff, no semantic repair loop.
- **No silent analyzer fallback.** An OpenAI-mode failure stays an OpenAI-mode failure.
- **Refusals, incomplete generations, empty structured content, and schema-invalid
  output are each classified explicitly** — a 200 response is never assumed to carry a
  usable result.
- **Mandatory final validation.** A response that cannot become a valid
  `QuoteCheckResult` is `invalid_model_output`, never patched or re-requested.
- **Sanitized errors and logs.** Clients get `{code, message, retryable, request_id}`;
  logs record the failure category, provenance, retryable flag, and exception class
  name — never a raw exception dump, API key, or provider payload.

This is failure *handling*, not high availability: there is no SLA, no automatic
recovery, and no durable or centralized logging. The behaviour is covered by 42 stdlib
unit tests that patch the provider boundary (no billed calls).

---

## Evaluation

[`eval/`](eval/README.md) holds a **27-case synthetic corpus** across **six domains**
(automotive, HVAC/appliance, plumbing/home, electronics repair, contractor/vendor,
generic service) and a deterministic regression runner (`python -m eval.run_eval`).

The design is a deliberate two-layer split:

- **Layer A — deterministic.** Invariants code can check honestly: schema validity,
  metadata provenance, uncertainty-marker values, forbidden-term leakage, structured
  line-item counts. Run by the runner.
- **Layer B — semantic.** Faithfulness, unsupported inference, calibration,
  usefulness. Scored by a human against [`eval/rubric.md`](eval/rubric.md), never
  machine-scored.

Two permanent regression cases guard real past bugs: cross-domain leakage (REG-001)
and unsupported market-price judgment (REG-002).

**Current committed Demo baseline**
([`eval/results/summary_20260829T115912Z.md`](eval/results/summary_20260829T115912Z.md)):

- **27/27 schema-valid**
- **24/27 deterministic cases pass**
- Known residuals retained, not excluded: `AUTO-004`, `CONT-003`, `HVAC-003` — all
  documented limitations of the coarse keyword Demo analyzer.

**24/27 is not an AI accuracy score.** It is a deterministic contract/regression pass
count for the Demo analyzer against a corpus that deliberately targets the intended
product contract. It says nothing about model quality, hallucination rate, or
correctness. Failing cases are visible in the runner's non-zero exit and in the
committed summary rather than xfailed or dropped from the denominator.

The CI workflow re-runs the corpus validation and the Demo eval and asserts this
baseline exactly — 27/27 schema-valid, 24/27 deterministic, residuals `AUTO-004` /
`CONT-003` / `HVAC-003`, runner still non-zero; any other outcome fails the build.

Design rationale, check-by-check strength assessment, and CLI usage:
[`eval/README.md`](eval/README.md).

---

## Live deployment

| | URL |
|---|---|
| Frontend (Vercel) | **https://quotecheck-frontend.vercel.app** |
| Backend API (Railway) | `https://quotecheck-v0-production.up.railway.app` |

Observed public verification (2026-09-01):

- `GET /health` → HTTP 200 `{"status":"ok"}`
- `POST /analyze` → HTTP 200 with `metadata.model == "quotecheck-demo-analyzer"`,
  `metadata.prompt_version == "quotecheck_v0.4"`, `metadata.schema_valid == true`
- CORS preflight from the production frontend origin is allowed; a foreign origin
  returns HTTP 400 with no `access-control-allow-origin` header

These statements rest on **observed runtime provenance**, not on an inspection of the
hosting environment's variables.

The frontend is a static Vercel build rooted at `frontend/`, pointed at the backend by
a browser-visible `VITE_API_BASE_URL`. The backend runs Uvicorn on Railway via a
repo-root [`railpack.json`](railpack.json) that forces the Python provider and stages
`backend/requirements.txt` (rationale recorded in
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)).

This is a public demonstration, not a service: no scale or uptime guarantees, no
accounts or customer data, no durable hosted logs, no public rate limiting, and no
anonymous access to paid inference.

---

## Limitations

- Paste-text input only — no PDF, OCR, or image ingestion.
- No market-price benchmarking and no objective price-fairness judgment.
- No vendor verification: vendor claims are not checked against external authoritative
  sources, and vendor trustworthiness is not assessed.
- No authentication, user accounts, or persistent database; no history beyond the
  local JSONL run log.
- Semantic (Layer B) evaluation is a manual human pass. A GitHub Actions workflow
  ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) is configured to run the
  deterministic Layer A runner, the harness self-tests, and the frontend lint/build on
  pull requests and pushes to `main`; it has no deploy step and runs no paid inference.
- Hosted `logs/app_runs.jsonl` is written to the platform's local, ephemeral
  filesystem — not durable or centralized observability.
- No public rate limiting or quota control.
- OpenAI mode exists as a repository capability but was **not** the path observed in
  the hosted public verification; it stays a local, opt-in mode.
- The deterministic Demo analyzer is a narrow keyword heuristic, and the shared
  `NormalizedCategory` taxonomy still carries vehicle-era wording. The OpenAI-mode
  prompt itself is domain-generic.
- No committed environment lockfile — only a pinned `backend/requirements.txt`.
- QuoteCheck does not replace a qualified professional's judgment.

---

## Run locally

The live Demo is at **https://quotecheck-frontend.vercel.app** — nothing needs to be
installed to try the product.

For local setup, Demo and OpenAI mode configuration, and the verification steps, see
[Local demo and development](docs/LOCAL_DEMO.md).

---

## Documentation

- [`SPEC.md`](SPEC.md) — product purpose, scope, non-goals, output principles.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — current public status: what is
  ready, what is limited, what should not be overclaimed.
- [`eval/README.md`](eval/README.md) — evaluation design, check vocabulary, corpus,
  and baseline.
- [`docs/LOCAL_DEMO.md`](docs/LOCAL_DEMO.md) — local run and development guide.
- [`examples/README.md`](examples/README.md) — six real captured Demo-mode reports.
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) — detailed technical baseline and
  the per-ticket implementation history (long; written for contributors).

Every unit of work has a ticket in `docs/tickets/` and a review bundle in
`docs/review/` recording the exact commands run and their real output.

## License

MIT
