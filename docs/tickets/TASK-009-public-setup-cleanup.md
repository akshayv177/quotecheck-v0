# TASK-009 — Public setup cleanup

## 1. Goal

Make QuoteCheck stranger-friendly from a public clone: verify and, where needed, fix the
setup path so a new user can clone the repo, install backend deps, run Demo mode with no
OpenAI credentials, hit `/health`, analyze a sample quote in Demo mode, and install/build
the frontend — with OpenAI mode clearly optional and no risk of an accidental paid call
during setup.

## 2. Context

README.md, backend/.env.example, and docs/CURRENT_STATE.md already document Demo mode as
the zero-key default (TASK-006/007/008), but no one has validated the literal clean-room
path: a fresh clone, a brand-new Python environment (not a developer's already-configured
one), no conda pre-installed. This ticket does that validation and fixes any drift found —
it does not change product behavior.

Validation runs against an `rsync` copy of the current working tree in a temp directory
outside the repo (not a `git clone` of the public GitHub URL), because this ticket's own
doc edits are uncommitted and out of scope forbids commits — cloning the public remote
would only validate the pre-TASK-009 docs. A real `git clone` verification is left as a
documented follow-up for after this branch is merged and pushed.

`backend/.env.example` was inspected and found accurate and safe (placeholder key text,
explicit comment that Demo mode needs no `.env` at all, `QUOTECHECK_USE_OPENAI=0`
default). It is left unchanged by default; it will only be touched if validation surfaces
a real mismatch.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-009-public-setup-cleanup.md`
- `docs/review/REVIEW_BUNDLE__TASK-009-public-setup-cleanup.md`
- `README.md`
- `docs/CURRENT_STATE.md`

Allowed only if validation proves there is an actual mismatch:
- `backend/.env.example`

Not used in this ticket (inspection found no justification — see review bundle):
`Makefile`, `scripts/verify_setup.sh`, `docs/SETUP.md`, `backend/requirements.txt`,
`frontend/README.md`.

Never touch: `frontend/src/`, `backend/core/`, `examples/outputs/`, `backend/.env`,
`logs/`, `package-lock.json` (unless npm explicitly modifies it and implementation stops
to ask), any secrets.

## 4. Out of scope

No product feature changes. No UI changes. No analyzer changes. No OpenAI-mode behavior
changes. No Docker unless implementation stops and asks first. No CI. No deployment. No
database/auth. No OCR/PDF/image parsing. No price benchmarking. No local model/Ollama
integration. No production-readiness claims. No commits.

## 5. Acceptance criteria

- README setup instructions match the actual repo.
- README clearly says Demo mode needs no API key.
- README clearly explains OpenAI mode is optional and requires `backend/.env` with
  `OPENAI_API_KEY`.
- `backend/.env.example` is accurate and safe (left unchanged unless validation proves a
  real mismatch).
- A clean checkout setup path is verified in a temporary directory outside the working
  repo (rsync copy of the working tree, not a public GitHub clone — see Context).
- Backend install succeeds in a fresh venv using `backend/requirements.txt`.
- Backend imports successfully.
- Backend runs in Demo mode with `QUOTECHECK_USE_OPENAI=0`.
- `/health` works.
- `/analyze` works against at least one sample quote in Demo mode.
- Frontend dependencies install and frontend build passes.
- Any setup limitation is documented honestly.
- `docs/CURRENT_STATE.md` is updated (including its "Last updated" line).
- No secrets are committed.
- Review bundle records exact commands and exact outputs, including a note that this
  validated a working-tree copy, not a `git clone`, plus a documented follow-up to
  re-verify via a real `git clone` after merge/push.

## 6. Commands to run

```bash
git status --short
git log --oneline -5

rm -rf /tmp/quotecheck-v0-setup-test
mkdir -p /tmp/quotecheck-v0-setup-test
rsync -a \
  --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='.venv-test' \
  --exclude='logs' --exclude='backend/.env' --exclude='__pycache__' \
  --exclude='.pytest_cache' --exclude='frontend/dist' \
  ./ /tmp/quotecheck-v0-setup-test/
cd /tmp/quotecheck-v0-setup-test

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -c "from backend.app import app; print(app.title)"

QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
sleep 2
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json; print(json.dumps({"quote_text": open("examples/quote_ac_repair.txt").read()}))')"
kill %1

cd frontend
npm install
npm run build

cd /tmp/quotecheck-v0-setup-test
grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' README.md backend/.env.example docs/CURRENT_STATE.md
```

## 7. Definition of done

- Ticket approved, plan approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (exact commands,
  exact real output, no placeholders).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-009.
- No secrets committed; work stays on `task/TASK-009-public-setup-cleanup`. Not
  committed — left for the user to review and commit manually.
