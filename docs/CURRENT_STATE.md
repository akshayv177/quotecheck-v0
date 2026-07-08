# CURRENT_STATE.md

Last updated: 2026-07-08 (TASK-002)

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
  (default mode, zero cost).
- `backend/core/openai_analyzer.py` — OpenAI Responses API with strict JSON-schema
  structured output, then Pydantic validation; server overrides metadata.
- `backend/core/prompt.py` — versioned prompt artifacts (`PROMPT_VERSION = quotecheck_v0.2`),
  explanation-first: every line item must carry a plain-English `explanation` before
  risk judgment, and vague/bundled charges must be flagged via `vague_or_confusing`.
- `backend/core/config.py` — env-var config: `QUOTECHECK_USE_OPENAI`, `QUOTECHECK_MODEL`
  (default `gpt-4o-mini`), `QUOTECHECK_LOG_PATH`, `OPENAI_API_KEY`. Loaded from
  untracked `backend/.env` (template: `backend/.env.example`).
- `backend/core/run_logger.py` / `logs/app_runs.jsonl` — append-only JSONL run logs.
- `backend/core/schema_export.py` — JSON Schema export used by the OpenAI analyzer.
- `frontend/src/App.jsx` — entire UI: textarea → Analyze → line-item table, summary /
  questions / verify / metadata cards, raw JSON view. React 19 + Vite 7.

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

Modes: copy `backend/.env.example` to `backend/.env`; `QUOTECHECK_USE_OPENAI=0`
(default) = stub mode, `=1` = OpenAI mode (requires `OPENAI_API_KEY`).

## Capabilities

- `/analyze` returns a schema-valid, explanation-first structured result. Each
  `LineItem` carries a plain-English `explanation` (what the item is and why a vendor
  might recommend it, distinct from the risk-focused `rationale_short`) and an
  explicit `vague_or_confusing` flag, in addition to category/risk/action/evidence.
- Stub mode (deterministic, vehicle-service keyword heuristics): brake → safety-
  critical/red; tyre → safety-critical/yellow; generic/un-itemized terms (misc,
  labour/labor, service charge, gas top-up, consumables, other/unitemized charges) →
  a conservative "Other/unspecified charges" catch-all with `vague_or_confusing=true`,
  independent of whether brake/tyre also matched, so those charges are surfaced
  instead of silently dropped; else a single "needs clarification" item. This is
  still keyword matching, not a real line-item parser/extractor.
- OpenAI mode is implemented (strict structured outputs + Pydantic validation).
- Frontend renders the full result and can copy raw JSON.
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
