# Project Status — QuoteCheck v0

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
- **Observability from day one.** Every request appends one JSONL record to
  `logs/app_runs.jsonl` (request_id, prompt version, model, latency, schema validity,
  risk counts, uncertainty, error).
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

- **Narrow taxonomy.** Demo mode's stub and the OpenAI-mode prompt are still
  vehicle-service-flavored (brakes/tyres) with AC/appliance and home-maintenance
  keyword coverage added on top — not the general service/repair/parts/vendor scope
  `SPEC.md` targets.
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
- **No automated test suite, eval harness, or CI.** The `examples/` pack is a
  manually curated sample set, not scored evaluation.
- **No repair/retry on schema-validation failure** if a model output doesn't match
  the contract.
- **No screenshot committed yet.** See `docs/LOCAL_DEMO.md` for how to add one —
  this repo does not use placeholder or mocked-up images.

## What should not be overclaimed

- This is **not** a production-ready system: no SLAs, no hardening, no scale
  guarantees, no uptime commitments.
- QuoteCheck does **not** provide professional or safety advice, and does not
  replace a certified mechanic, contractor, or other professional's judgment.
- QuoteCheck does **not** verify vendor claims or guarantee fair pricing.
- OpenAI-mode output has not been benchmarked for accuracy; using a stronger model
  does not itself constitute a validated claim of correctness.
- Demo mode's keyword matches should never be described as "AI analysis" in the
  literal sense — it's a deterministic stub used specifically so a visitor can try
  the product without cost or credentials.

For the exact current architecture, commands, and full gap list, see
[`docs/CURRENT_STATE.md`](CURRENT_STATE.md).
