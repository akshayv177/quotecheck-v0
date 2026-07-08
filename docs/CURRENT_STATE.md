# CURRENT_STATE.md

Last updated: 2026-07-08 (TASK-006)

Short, factual snapshot of what exists right now. Update this file (and this date
line) in any ticket that changes capabilities, commands, or gaps.

## Architecture

Two-process local app: a React single-page frontend posts pasted quote text to a
FastAPI backend, which returns a schema-valid `QuoteCheckResult` and appends one
JSONL log record per request.

- `backend/app.py` — FastAPI app; `GET /health`, `POST /analyze`; CORS for the Vite
  dev server; per-request logging (success and failure paths).
- `backend/core/schema.py` — Pydantic contract (`AnalyzeRequest`, `QuoteCheckResult`
  and nested models: line items, risk levels, uncertainty markers, refusals, metadata).
- `backend/core/stub_analyzer.py` — deterministic keyword-heuristic analyzer
  (default mode, zero cost, product-facing name "Demo mode"). Reports
  `metadata.model = "quotecheck-demo-analyzer"` (`config.DEMO_ANALYZER_MODEL`), a
  label distinct from `QUOTECHECK_MODEL`, so demo-mode responses and JSONL logs
  never claim an OpenAI model was called.
- `backend/core/openai_analyzer.py` — OpenAI Responses API with strict JSON-schema
  structured output, then Pydantic validation; server overrides metadata.
- `backend/core/prompt.py` — versioned prompt artifacts (`PROMPT_VERSION = quotecheck_v0.2`),
  explanation-first: every line item must carry a plain-English `explanation` before
  risk judgment, and vague/bundled charges must be flagged via `vague_or_confusing`.
- `backend/core/config.py` — env-var config: `QUOTECHECK_USE_OPENAI`, `QUOTECHECK_MODEL`
  (default `gpt-4o-mini`), `QUOTECHECK_LOG_PATH`, `OPENAI_API_KEY`, and
  `DEMO_ANALYZER_MODEL` (fixed label, not env-configurable). Loaded from untracked
  `backend/.env` (template: `backend/.env.example`); if `backend/.env` doesn't exist
  at all, the app still runs — defaults are `QUOTECHECK_USE_OPENAI=0` (Demo mode).
- `backend/core/run_logger.py` / `logs/app_runs.jsonl` — append-only JSONL run logs.
- `backend/core/schema_export.py` — JSON Schema export used by the OpenAI analyzer.
- `frontend/src/App.jsx` — entire UI: textarea → Analyze → quote-understanding
  report (report header with a derived risk-count strip, summary card, then one
  card per line item with `explanation` as the prominent field, `rationale_short`
  as secondary risk reasoning, a risk-colored left border, a risk pill using
  semantic wording ("High risk" / "Caution" / "Low risk"), a "Needs
  clarification" badge when `vague_or_confusing` is true, and `evidence_needed`
  as a secondary bullet list), a "Before you approve" section ("Questions to
  ask the vendor" / "Things to verify before approving", responsive 2→1 column),
  a footer with the disclaimer always visible, run metadata, and raw JSON
  collapsed by default in a `<details>` block with the Copy button inside it. A
  real loading state (pulse indicator plus an elapsed-time-driven stage
  label and elapsed-time counter, `aria-live="polite"`) and a styled error
  card (copy differentiated by timeout/network/HTTP/other failure kind)
  replace the earlier button-label-only loading and single generic error
  message. Requests time out client-side after 55s via `AbortController`. A small
  "Demo mode" / "OpenAI mode" badge (`ModeBadge`, built on the existing `Pill`
  primitive) sits next to the run-metadata line, derived from
  `result.metadata.model` — no separate flag or endpoint.
  Single light theme (`frontend/src/index.css` token set); no dark mode.
  React 19 + Vite 7.

## Commands

Backend (from repo root; deps pinned in `backend/requirements.txt`, verified against
a clean venv on Python 3.10 and a conda env on Python 3.11):

```bash
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

(The README additionally suggests a conda env; any Python 3.10+ environment with
`backend/requirements.txt` installed works.)

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host   # dev server, usually http://localhost:5173
npm run build
npm run lint            # eslint; only frontend check that exists
```

Logs:

```bash
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
```

Modes: no `backend/.env` file is required to run in Demo mode — it's the default
with zero setup. To switch modes explicitly, copy `backend/.env.example` to
`backend/.env`; `QUOTECHECK_USE_OPENAI=0` (default) = Demo mode (stub analyzer,
no API key), `=1` = OpenAI mode (requires `OPENAI_API_KEY`).

## Capabilities

- `/analyze` returns a schema-valid, explanation-first structured result. Each
  `LineItem` carries a plain-English `explanation` (what the item is and why a vendor
  might recommend it, distinct from the risk-focused `rationale_short`) and an
  explicit `vague_or_confusing` flag, in addition to category/risk/action/evidence.
- Every response's `metadata.model` honestly identifies which analyzer produced it:
  `quotecheck-demo-analyzer` in Demo mode, the configured `QUOTECHECK_MODEL` (e.g.
  `gpt-4o-mini`) in OpenAI mode. The frontend shows this as a "Demo mode" / "OpenAI
  mode" badge; the same value is also what gets written to `logs/app_runs.jsonl`.
- Demo/stub mode (deterministic, vehicle-service keyword heuristics): brake → safety-
  critical/red; tyre → safety-critical/yellow; generic/un-itemized terms (misc,
  labour/labor, service charge, gas top-up, consumables, other/unitemized charges) →
  a conservative "Other/unspecified charges" catch-all with `vague_or_confusing=true`,
  independent of whether brake/tyre also matched, so those charges are surfaced
  instead of silently dropped; else a single "needs clarification" item. This is
  still keyword matching, not a real line-item parser/extractor.
- OpenAI mode is implemented (strict structured outputs + Pydantic validation).
- Frontend renders the full result as a quote-understanding report (explanation
  prominent per line item, vague/confusing charges visibly badged, verification
  questions and things-to-verify grouped with vendor-facing headers) and can copy
  raw JSON.
- Every request logs one JSONL record (request_id, prompt_version, model, latency,
  schema_valid, risk counts, uncertainty, error).
- Secrets hygiene: `backend/.env` and `logs/` are gitignored and untracked.

## Gaps

- No backend tests, no eval harness, no CI. `docs/` and `eval/` were empty until TASK-000.
- No repair/retry when model output fails schema validation.
- Paste-text input only: no PDF/OCR, no auth/users/DB.
- Scope is vehicle-service-flavored (taxonomy, stub heuristics, prompt), narrower
  than the SPEC.md target (general service / repair / parts / vendor quotes).
- Price benchmarking does not exist.
- Stub's generic-charge catch-all is a fixed keyword list, not real line-item
  extraction; a quote whose vague charges don't match one of those keywords still
  falls through to the single generic "needs clarification" item.
- Missing information is represented at the top level (`things_to_verify`,
  `missing_vehicle_context`) rather than per line item.

### Fixed in TASK-006

- `backend/core/config.py`: added `DEMO_ANALYZER_MODEL = "quotecheck-demo-analyzer"`,
  a fixed label distinct from `MODEL`/`QUOTECHECK_MODEL`.
- `backend/core/stub_analyzer.py`: `MetaData.model` now uses `DEMO_ANALYZER_MODEL`
  instead of `MODEL`. Previously, stub-mode responses (and their
  `logs/app_runs.jsonl` entries) reported `model: "gpt-4o-mini"` even though no
  OpenAI call was made — misleading for a public demo and inconsistent with
  SPEC.md's honest-limitation-language principle. OpenAI mode is unchanged (still
  reports the real configured model).
- `frontend/src/App.jsx`: added a small `ModeBadge` (built on the existing `Pill`
  primitive) next to the run-metadata footer line, reading "Demo mode" when
  `metadata.model === "quotecheck-demo-analyzer"`, else "OpenAI mode". No other
  UI, loading/error, or `/analyze` request/response change.
- `README.md`: added an explicit "no OpenAI API key needed" callout near the top,
  clarified the Demo-mode-first walkthrough (no `backend/.env` required), and
  renamed "stub mode" to the product-facing "Demo mode" throughout the prose
  (internal code identifiers — `QUOTECHECK_USE_OPENAI`, `stub_analyzer.py`,
  `analyze_quote_stub` — are unchanged).
- `backend/.env.example`: clarifying comment that Demo mode needs no key and no
  `.env` file at all; no functional change.
- No new dependencies; no changes to `backend/app.py`,
  `backend/core/openai_analyzer.py`, `backend/core/schema.py`,
  `backend/core/prompt.py`, or the `/analyze` request/response shape.

### Fixed in TASK-005

- `frontend/src/App.jsx`: the ~20s real-LLM-mode wait now has staged, honest
  feedback instead of a static "Analyzing your quote…" line. A stage label
  ("Reading the quote…" → "Identifying line items…" → "Checking for vague or
  risky charges…" → "Preparing your report…") advances based on elapsed time
  (client-side simulation — the backend makes a single blocking LLM call with
  no real progress signal, so this is explicitly not claimed as true backend
  progress) alongside a live elapsed-time counter; both are inside an
  `aria-live="polite"` status region. Past ~20s a "still working" hint appears
  instead of a fake final stage. Requests now abort client-side via
  `AbortController` after 55s with a dedicated timeout message; `err` state
  changed from a plain string to `{ kind, message }` so network-unreachable,
  timeout, non-2xx HTTP, and other errors each get distinct copy (the "check
  the backend is running on port 8000" hint now only shows for HTTP/other
  errors, not for the already-self-contained network/timeout messages). No
  backend changes, no new dependencies, `/analyze` request/response shape
  unchanged, sample quote and full report rendering (including raw JSON/Copy)
  unchanged.

### Fixed in TASK-004

- `frontend/src/index.css`: replaced the stock Vite template theme (dark
  `#242424` default under `prefers-color-scheme: dark`, `body` flex-centering,
  `3.2em` h1) with a single light-only design-token set (`--bg`, `--surface`,
  ink/border/accent, per-risk color triples, vague/error colors) plus small
  helpers (`.two-col-grid` responsive collapse, `.status-pulse` loading
  animation). `frontend/src/App.css` (dead, unimported since before TASK-003)
  deleted.
- `frontend/src/App.jsx`: visual restyle only — no data-flow change. Header now
  reads "QuoteCheck" with a "v0 prototype" chip; input is a card with helper
  text; a real loading indicator (pulse bar + status text) supplements the
  button label; a styled error card replaces bare `crimson` error text; the
  report gained a derived risk-count strip (computed client-side from existing
  `line_items`, e.g. "3 items · 1 high risk · 1 caution · 1 needs
  clarification"); line-item cards gained a risk-colored left border and
  semantic risk-badge wording ("High risk" / "Caution" / "Low risk" instead of
  "RED"/"YELLOW"/"GREEN"); the two checklist cards are now grouped under a
  "Before you approve" heading with a responsive 2→1 column collapse; raw JSON
  moved into a collapsed-by-default `<details>` block (Copy JSON button inside
  it) while the disclaimer stays visible without expanding anything.
  `frontend/index.html` title changed from the default "frontend" to a real
  page title. `/analyze` request/response shape, `Pill`/`Card`/`RiskPill`/
  `VagueBadge`/`LineItemCard` props, and the prefilled sample quote are all
  unchanged. No backend files touched; no new dependencies.

### Fixed in TASK-003

- `frontend/src/App.jsx`: replaced the flat line-item `<table>` with one card per
  line item so `explanation` (already returned by the backend since TASK-002, but
  never rendered) is now the prominent, human-readable field; `rationale_short` is
  shown as secondary risk reasoning; a new "NEEDS CLARIFICATION" badge
  (`VagueBadge`, built on a generalized `Pill` primitive shared with `RiskPill`)
  appears when `vague_or_confusing` is true; `evidence_needed` is now rendered as a
  secondary bullet list per item (previously unrendered). The Summary card moved
  above the line items; "Verification questions" / "Things to verify" cards were
  relabeled "Questions to ask the vendor" / "Things to verify before approving".
  Default sample quote text updated to include a generic-charge keyword ("misc")
  so the out-of-box demo shows all 3 stub items (brake/tyre/other-unspecified)
  including the vague badge. No backend files changed; `/analyze` response shape
  is unchanged — this only renders fields the backend already returns.

### Fixed in TASK-002

- `backend/core/schema.py`: `LineItem` gained `explanation` (plain-English
  understanding, distinct from the risk-focused `rationale_short`) and
  `vague_or_confusing` (explicit flag, independent of `normalized_category`). Both
  are additive with safe defaults (`""` / `false`) for backward compatibility;
  analyzers are required to always populate a non-empty `explanation`.
  `verification_questions` / `things_to_verify` got clarifying descriptions
  (vendor-facing questions vs. missing-information gaps) with no shape change.
- `backend/core/prompt.py`: `PROMPT_VERSION` bumped to `quotecheck_v0.2`; system/
  developer prompts now require explanation-first output per line item, require
  `vague_or_confusing` for generic/bundled charges, and explicitly forbid claiming
  price benchmarking or market-price comparison.
- `backend/core/stub_analyzer.py`: brake/tyre items now include real `explanation`
  text; added an independent, conservative catch-all for generic/un-itemized charges
  (misc, labour/labor, service charge, gas top-up, consumables, other/unitemized
  charges) that no longer gets silently dropped when brake/tyre also match;
  `overall_summary` and `disclaimer` reworded to be explanation-first and to state
  price benchmarking is not implemented (matches SPEC.md's honest limitation
  language).
- `/analyze` response shape is unchanged for all fields the frontend reads
  (`name_raw`, `normalized_category`, `risk_level`, `recommended_action`,
  `rationale_short`, `overall_summary`, `verification_questions`,
  `things_to_verify`, `disclaimer`); the two new fields are additive.

### Fixed in TASK-001

- `backend/requirements.txt` now exists (pinned: fastapi, uvicorn, pydantic, openai,
  python-dotenv); README install step works as written.
- `backend/core/schema.py`: `uncertainty_markers` default_factory kwarg corrected from
  `ambigious_items_present` to `ambiguous_items_present`.
- `backend/core/prompt.py` (`build_messages`): user content now uses real newlines
  instead of literal `\n` / `\N` escape text.
- `README.md` config example corrected from `gpt-40-mini` to `gpt-4o-mini`.
