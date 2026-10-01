# Project Status — QuoteCheck

A neutral, honest snapshot of what exists in this repo today: what's public-ready,
what's still limited, and what should not be overclaimed. Written from direct
inspection of the code and docs, not aspirational copy. See `SPEC.md` for the
product target and `docs/CURRENT_STATE.md` for the full technical baseline — this
file is a summary, not a replacement for either.

## What's public-ready today

- **Quote understanding first, risk second.** `POST /analyze` returns an
  explanation-first result: every line item carries a plain-English `explanation`
  before any risk judgment, matching `SPEC.md`'s output principles.
- **Zero-key Demo mode.** The default mode (`QUOTECHECK_USE_OPENAI=0`) is a
  deterministic keyword-heuristic stub — no `backend/.env` file, no OpenAI API key,
  no cost, no network call. A stranger can clone the repo and get a real response in
  under a minute.
- **OpenAI mode is clearly optional.** It's opt-in, requires `backend/.env` with
  `OPENAI_API_KEY`, and is documented separately from Demo mode. Every response's
  `metadata.model` field honestly identifies which mode produced it
  (`quotecheck-demo-analyzer` vs. the configured model), shown in the UI as a
  "Demo mode" / "OpenAI mode" badge.
- **Schema-first contract.** The Pydantic `QuoteCheckResult` schema is the single
  source of truth for both the API and the frontend; nothing is rendered that isn't
  schema-validated.
- **Real, captured example outputs.** All files under `examples/` are actual
  Demo-mode `/analyze` responses, not hand-written — see `examples/README.md`.
- **UI screenshot committed.** `docs/assets/quotecheck-ui.png` is a real captured
  screenshot of the rendered report, embedded in `README.md`.
- **Observability from day one.** Every request appends one JSONL record to
  `logs/app_runs.jsonl` (request_id, prompt version, model, latency, schema validity,
  risk counts, uncertainty, error).
- **Deterministic eval + regression harness.** `eval/` ships a 27-case synthetic
  quote corpus, a deterministic zero-cost Demo-mode runner (`python -m eval.run_eval`),
  and a separate human semantic rubric (`eval/rubric.md`). The committed Demo baseline
  (`eval/results/summary_20260829T115912Z.md`, QC-3C) is **27/27 schema-valid, 24/27
  deterministic checks passing**; the three known residuals (`AUTO-004`, `CONT-003`,
  `HVAC-003`) are retained, not excluded. Two permanent regression cases guard domain
  leakage and unsupported price judgment.
- **Harness self-tests.** 201 stdlib `unittest` tests
  (`python -m unittest discover -s eval/tests -p 'test_*.py'`), run during the
  SCALE-006 v1 closure (144 at the v0 QC-5 inspection).
- **Explicit capacity boundary and predictable overload (v1).** In OpenAI mode, at
  most 32 analyses per process are admitted to the provider at once. Excess requests
  are rejected immediately with HTTP 503 `capacity_exceeded` (`retryable: true`) and
  make zero provider calls; there is no queue. Each admitted request makes at most two
  provider attempts, and a retry stays inside its slot. Demo mode is unaffected.
  Before explicit admission (pre-SCALE-004), excess demand waited silently in the
  framework's worker pool and `/health` slowed with provider latency. The budget,
  the before/after evidence and the limitations are in
  [`docs/scalability/SCALE-006_V1_CLOSURE.md`](scalability/SCALE-006_V1_CLOSURE.md).
  All of it was measured locally against a simulated provider: it is not an SLA, and
  not a statement of OpenAI or Railway capacity.
- **Live public Demo deployment.** Frontend on Vercel
  (`https://quotecheck-frontend.vercel.app`) and backend on Railway
  (`https://quotecheck-v0-production.up.railway.app`), verified end-to-end in the
  browser. The observed public hosted path executed through the deterministic Demo
  analyzer (`metadata.model == "quotecheck-demo-analyzer"`,
  `prompt_version == "quotecheck_v0.4"`, `schema_valid == true`). OpenAI mode remains
  an optional repository capability and was not the path observed during public
  deployment verification.
- **Ticket + review-bundle discipline.** Every change is scoped to a ticket in
  `docs/tickets/` with a review bundle in `docs/review/` recording exact commands and
  real output — the project's full history is auditable.
- **Clean-room setup validated.** TASK-009 verified the backend install, Demo-mode
  run, `/health`, `/analyze`, and frontend build all succeed from a fresh Python
  environment with no pre-existing configuration.
- **No secrets or private context in tracked files.** `backend/.env` and `logs/` are
  gitignored; a scan of the public-facing docs found no API keys and no private
  career/outreach context.

## What's still limited

- **Narrow taxonomy and Demo heuristics.** The deterministic Demo stub and the
  shared `NormalizedCategory` taxonomy still carry vehicle-era wording (brakes/tyres),
  with AC/appliance and home-maintenance keyword coverage added on top — not the
  general service/repair/parts/vendor scope `SPEC.md` targets. The OpenAI-mode prompt
  itself was made domain-generic in TASK-012.
- **Demo mode is keyword matching, not language understanding.** It recognizes a
  small fixed set of keywords per domain and falls back to a single "needs
  clarification" item otherwise. It is a stand-in for realistic responses, not an
  accuracy claim.
- **Price benchmarking does not exist.** No price database, no market-price
  comparison, anywhere in the system.
- **No PDF/OCR/image ingestion.** Paste-text input only.
- **No auth, accounts, or persistent database.** State beyond the local JSONL log
  does not exist.
- **No committed environment lockfile.** Only a pinned `backend/requirements.txt`;
  reproducibility depends on the developer using a compatible Python 3.10+
  environment.
- **Semantic grading is still manual, and there is no CI.** The deterministic
  Layer A eval runner and the 201 stdlib harness tests exist and run, but Layer B
  (semantic faithfulness / calibration / usefulness) is a human pass against
  `eval/rubric.md`, and nothing runs automatically on push or PR.
- **The public deployment is a portfolio Demo, not a service.** No scale or uptime
  guarantee, no accounts or customer data, no durable or centralized logging (hosted
  `logs/app_runs.jsonl` is written to the platform's local, ephemeral filesystem), and
  no public rate limiting / quota control. The observed hosted path is the
  deterministic Demo analyzer; OpenAI mode is a local, opt-in repository capability and
  was not the observed public path.
- **Capacity limits are per process and locally measured.** The 32-slot provider
  budget applies to each server process; more workers or replicas would multiply it,
  and nothing coordinates across processes. It has no `Retry-After` hint and no
  per-client fairness. A client that resends rejected requests with no backoff can
  saturate the single event loop. Real OpenAI latency, rate limits and cost have not
  been measured (all v1 measurement was ₹0, against a simulated provider).
- **Cost is bounded per request and in concurrency, not over time.** QuoteCheck caps
  concurrent provider work (32 per process) and provider calls per request (2), and
  rejected or Demo requests make no provider calls. It does **not** cap cumulative
  spend: there is no spending quota, no output-token cap and no token/cost logging.
  In v1, spend is bounded by keeping the public deployment in Demo mode and by
  provider-account controls outside the application.
- **No repair/retry on schema-validation failure** if a model output doesn't match
  the contract.
- **No market-price benchmarking and no objective price-fairness judgment.**
  QuoteCheck describes only what the quote states.
- **No vendor verification.** Vendor claims are not checked against external
  authoritative sources; vendor trustworthiness is not assessed.

## What should not be overclaimed

- This is **not** a production-ready system: no SLAs, no hardening, no scale
  guarantees, no uptime commitments.
- The v1 capacity numbers (32-slot budget, rejection and `/health` latencies,
  throughput) come from a local machine and a simulated provider. They are **not**
  OpenAI capacity, Railway capacity or a throughput guarantee, and the provider
  budget does **not** bound cumulative cost.
- QuoteCheck does **not** provide professional or safety advice, and does not
  replace a qualified professional's judgment (mechanic, contractor, technician, etc.).
- QuoteCheck does **not** verify vendor claims or guarantee fair pricing.
- OpenAI-mode output has not been benchmarked for accuracy; using a stronger model
  does not itself constitute a validated claim of correctness.
- Demo mode's keyword matches should never be described as "AI analysis" in the
  literal sense — it's a deterministic stub used specifically so a visitor can try
  the product without cost or credentials.

## Planned hardening (not yet built)

Tracked as future work; none of this is implemented today:

- Scored semantic (Layer B) checks — the deterministic Layer A harness exists; only
  the semantic scoring is future work.
- CI wiring that runs the existing verification commands on push / PR (QC-5B).
- Bounded repair/retry when a model response fails schema validation.
- Broader, de-vehicled result taxonomy.
- Production monitoring, and load testing against a real provider or the hosted
  environment (v1 capacity work was local and simulated only).
- Public rate limiting / quota control and durable, centralized logging — required
  before OpenAI mode could ever be exposed anonymously.

For the exact current architecture, commands, and full gap list, see
[`docs/CURRENT_STATE.md`](CURRENT_STATE.md).
