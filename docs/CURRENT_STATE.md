# CURRENT_STATE.md

Last updated: 2026-07-08 (TASK-000)

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

Backend (from repo root; Python 3.11; deps installed manually — see gaps):

```bash
pip install fastapi uvicorn pydantic openai python-dotenv
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

(The README additionally suggests a conda env; any Python 3.11 environment works.)

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

- `backend/requirements.txt` does not exist, although the README install step
  references it (`pip install -r backend/requirements.txt` fails).
- No backend tests, no eval harness, no CI. `docs/` and `eval/` were empty until TASK-000.
- No repair/retry when model output fails schema validation.
- Paste-text input only: no PDF/OCR, no auth/users/DB.
- Scope is vehicle-service-flavored (taxonomy, stub heuristics, prompt), narrower
  than the SPEC.md target (general service / repair / parts / vendor quotes).
- Price benchmarking does not exist.

### Observed issues to verify/fix in future tickets (not reproduced at runtime)

- `backend/core/schema.py` (~line 158): `uncertainty_markers` default_factory passes a
  misspelled kwarg `ambigious_items_present`; would likely fail validation if the
  default ever fires. Both analyzers currently pass explicit values.
- `backend/core/prompt.py` (`build_messages`): user content contains literal `\\n` /
  `\\N` escape text instead of newlines.
- `README.md` config example says `gpt-40-mini` (code default is `gpt-4o-mini`).
