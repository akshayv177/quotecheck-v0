# TASK-006 — Mock/demo mode

## 1. Goal

Make it unambiguous, in both the API response and the UI, that QuoteCheck's default
mode is a deterministic, zero-cost, zero-credential "Demo mode" — not a real OpenAI
call — so a stranger can clone the repo and produce a polished quote-understanding
report without any private API keys, and can tell at a glance which mode produced
a given report.

## 2. Context

The deterministic stub analyzer (`backend/core/stub_analyzer.py`) already runs by
default (`QUOTECHECK_USE_OPENAI=0`) and needs no `OPENAI_API_KEY` — `backend/app.py`'s
`load_dotenv("backend/.env")` no-ops silently if that file doesn't exist, so the
zero-credential path already worked mechanically. Two things undermined it:

1. `backend/core/stub_analyzer.py` set `MetaData.model = MODEL` (the
   `QUOTECHECK_MODEL` config value, default `gpt-4o-mini`), even though no OpenAI
   call happens in stub mode. Both the API response and `logs/app_runs.jsonl`
   therefore claimed an OpenAI model was used when it wasn't — dishonest by
   SPEC.md's own "honest limitation language" standard, and confusing for anyone
   inspecting a demo's raw JSON or run logs.
2. README.md led with conda/OpenAI-flavored setup and never clearly stated the
   default mode needs no key at all; "stub mode" is internal engineering language,
   not something a portfolio visitor would parse as "you don't need my secrets."

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-006-mock-demo-mode.md`
- `docs/review/REVIEW_BUNDLE__TASK-006-mock-demo-mode.md`
- `backend/core/config.py`
- `backend/core/stub_analyzer.py`
- `frontend/src/App.jsx`
- `README.md`
- `backend/.env.example`
- `docs/CURRENT_STATE.md`

Never touch: `backend/app.py`, `backend/core/openai_analyzer.py`,
`backend/core/schema.py`, `backend/core/prompt.py`, `package.json` /
`package-lock.json`, `backend/.env`, `logs/`, secrets of any kind.

## 4. Out of scope

No local-model migration, no price benchmarking, no OCR/PDF/database, no new
dependencies, no broad rename of internal identifiers (`QUOTECHECK_USE_OPENAI`
stays; `stub_analyzer.py` / `analyze_quote_stub` stay), no UI redesign beyond a
small mode badge, no change to `/analyze` request/response shape or field types,
no CI/test suite addition.

## 5. Acceptance criteria

1. A clean clone with no `backend/.env` file, run with default env, `POST /analyze`
   returns `metadata.model == "quotecheck-demo-analyzer"` (not an OpenAI model name).
2. `logs/app_runs.jsonl` entries produced in default mode log the same honest label.
3. OpenAI mode (`QUOTECHECK_USE_OPENAI=1` + real key) is unchanged in code: still
   sets `metadata.model = MODEL` (e.g. `gpt-4o-mini`).
4. The frontend shows a small "Demo mode" / "OpenAI mode" badge next to the run
   metadata footer line, driven by `result.metadata.model`; no other UI, loading,
   error, or data-flow change.
5. README.md states near the top, plainly, that the default mode needs no OpenAI
   API key, with a walkthrough a stranger can follow end-to-end.
6. `backend/.env.example` still has no real secret and clarifies Demo mode needs
   no key.
7. `docs/CURRENT_STATE.md` "Last updated" line and relevant sections reflect the
   change.
8. Zero new dependencies; `npm run lint` and `npm run build` both pass.

## 6. Commands to run

```bash
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Misc charges."}' \
  | python3 -m json.tool
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
cd frontend && npm run lint && npm run build
```

## 7. Definition of done

- Ticket approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (exact
  commands, exact output, no placeholders); any verification limitation stated
  honestly rather than claimed as done.
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-006.
- No secrets committed; work stays on `task/006-mock-demo-mode`. Not committed —
  implementation is left for the user to review and commit manually.
