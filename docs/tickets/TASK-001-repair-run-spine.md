# TASK-001 — Repair local run spine

## 1. Goal

Make QuoteCheck reproducible for a stranger before any further product/UI feature
work: a clear backend dependency install path, accurate setup instructions, and a
backend that imports/runs cleanly in stub mode.

## 2. Context

TASK-000 documented these gaps in `docs/CURRENT_STATE.md`:
- `backend/requirements.txt` does not exist; the README install step references it.
- README config example has a model typo: `gpt-40-mini` instead of `gpt-4o-mini`.
- `backend/core/schema.py` has a misspelled kwarg (`ambigious_items_present`) in an
  unused `default_factory` path.
- `backend/core/prompt.py` builds the user message with literal `\n`/`\N` escape text
  instead of real newlines.
- System Python failed previously because deps were missing; the `quotecheck` conda
  env (Python 3.11) has working installs.

QuoteCheck is a v0 prototype. This ticket does not add features or claim production
readiness; it repairs the local run spine only.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-001-repair-run-spine.md`
- `docs/review/REVIEW_BUNDLE__TASK-001-repair-run-spine.md`
- `backend/requirements.txt`
- `README.md`
- `backend/core/schema.py`
- `backend/core/prompt.py`
- `docs/CURRENT_STATE.md`

Allowed only if inspection proves it necessary:
- `backend/.env.example` (inspection found no change needed — already correct)

Never touch: `frontend/` source, `backend/core/openai_analyzer.py` (unless a tiny
compatibility fix is proven necessary — none found), `backend/core/stub_analyzer.py`,
`package-lock.json`, `backend/.env`, `logs/`, secrets.

## 4. Out of scope

No UI work, no frontend behavior changes, no new product features, no price
benchmarking, no OCR/PDF/image parsing, no database/auth, no model/provider
migration, no broad architecture refactor, no fake metrics, no production-readiness
claims, no commits.

## 5. Acceptance criteria

- `backend/requirements.txt` exists and contains only currently required backend
  dependencies.
- README backend install instructions match the repo.
- README model typo is fixed.
- Schema typo (`ambigious_items_present`) is fixed.
- Prompt newline issue is fixed.
- Backend app imports successfully from a clean Python environment with installed
  requirements, or any failure is recorded honestly.
- `/health` works when the backend server is running.
- `/analyze` works in stub mode with a sample quote.
- `docs/CURRENT_STATE.md` is updated to reflect repaired gaps.
- Review bundle contains exact commands and exact outputs after implementation.
- No secrets are committed.
- No frontend behavior changes.

## 6. Commands to run

```bash
git status --short
python3 -m venv .venv-test
source .venv-test/bin/activate
pip install -r backend/requirements.txt
python -c "from backend.app import app; print(app.title)"
uvicorn backend.app:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" -d '{"quote_text":"Brake pad replacement ₹8,500. Labour ₹2,500. Misc charges ₹1,200. AC gas top-up ₹3,000."}'
grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'\''][^"'\'']{10,}' backend/requirements.txt README.md backend/core/schema.py backend/core/prompt.py docs/CURRENT_STATE.md
```

## 7. Definition of done

All acceptance criteria above are met with evidence (exact command + exact output)
recorded in `docs/review/REVIEW_BUNDLE__TASK-001-repair-run-spine.md`, and
`docs/CURRENT_STATE.md`'s "Last updated" line and gap list reflect the repaired state.
Claude must not commit. The human may commit the ticket and implementation after
review.
