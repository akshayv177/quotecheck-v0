# CLAUDE.md — QuoteCheck

QuoteCheck turns confusing service and parts quotes into clear explanations, red flags,
vendor questions, and optional market price checks. This repo is an honest **v0 prototype**
— do not describe it as production-ready.

## Read first

Before planning any new ticket, read:
1. `SPEC.md` — product purpose, scope, target pipeline, output principles.
2. `docs/CURRENT_STATE.md` — what actually exists right now, commands, known gaps.

Never invent implemented features. If SPEC.md and the code disagree, the code is the
truth about the present; SPEC.md describes the target.

## Workflow rules

1. **One ticket at a time.** Each unit of work has a ticket file in `docs/tickets/`
   (`TASK-NNN-<slug>.md`) with goal, scope, out-of-scope, and concrete acceptance criteria.
2. **Plan before editing.** Inspect the relevant code, produce a numbered plan, and get
   the user's approval before changing files.
3. **Review bundle required.** After implementation, write
   `docs/review/REVIEW_BUNDLE__TASK-NNN-<slug>.md` recording: files changed, acceptance
   criteria with evidence, exact commands run and their real output. No placeholders.
4. **Update the baseline.** If a ticket changes capabilities, commands, or gaps, update
   `docs/CURRENT_STATE.md` (including its "Last updated" line) in the same ticket.
5. **Stay in scope.** Do not refactor, fix unrelated issues, or add dependencies unless
   the ticket says so. Note out-of-scope findings in the review bundle instead.

## Branch / commit discipline

- Work on a branch named `task/TASK-NNN-<slug>`; do not commit directly to `main`.
- Reference the task id in commit messages.
- Do not commit or push unless the user asks.

## Secrets

- Never commit secrets. `backend/.env` is untracked and must stay that way; `backend/.env.example`
  is the committed template.
- Configuration comes from environment variables (see `backend/core/config.py`).
- Prefer stub mode (`QUOTECHECK_USE_OPENAI=0`, the default) for demos and development —
  it is deterministic and costs nothing.

## Quick commands

```bash
# Backend (from repo root; deps: fastapi uvicorn pydantic openai python-dotenv)
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
curl http://localhost:8000/health

# Frontend
cd frontend && npm install && npm run dev -- --host
npm run lint   # in frontend/

# Inspect latest run log
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
```

There is no `backend/requirements.txt` yet and no test suite — see
`docs/CURRENT_STATE.md` for the full gap list.
