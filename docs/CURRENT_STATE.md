# CURRENT_STATE.md

Last updated: 2026-07-08 (TASK-001)

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
- `backend/core/prompt.py` — versioned prompt artifacts (`PROMPT_VERSION = quotecheck_v0.1`).
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

- `/analyze` returns a schema-valid structured result in stub mode (deterministic,
  vehicle-service keyword heuristics: brake/tyre, else "needs clarification").
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

### Fixed in TASK-001

- `backend/requirements.txt` now exists (pinned: fastapi, uvicorn, pydantic, openai,
  python-dotenv); README install step works as written.
- `backend/core/schema.py`: `uncertainty_markers` default_factory kwarg corrected from
  `ambigious_items_present` to `ambiguous_items_present`.
- `backend/core/prompt.py` (`build_messages`): user content now uses real newlines
  instead of literal `\n` / `\N` escape text.
- `README.md` config example corrected from `gpt-40-mini` to `gpt-4o-mini`.
