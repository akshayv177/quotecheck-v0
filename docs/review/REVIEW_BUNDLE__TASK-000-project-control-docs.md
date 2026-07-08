# REVIEW BUNDLE — TASK-000 Project control docs and current-state baseline

Date: 2026-07-08
Branch: `task/TASK-000-project-control-docs`
Ticket: `docs/tickets/TASK-000-project-control-docs.md`

## Summary of change

Docs-only ticket. Created five new files establishing project-control discipline:
CLAUDE.md (session rules), SPEC.md (product spec), docs/CURRENT_STATE.md (factual
baseline), the TASK-000 ticket, and this review bundle. No changes to `backend/`,
`frontend/`, `README.md`, or any tracked file. No dependencies added. Nothing committed.

## Files created

1. `CLAUDE.md` (60 lines)
2. `SPEC.md`
3. `docs/CURRENT_STATE.md`
4. `docs/tickets/TASK-000-project-control-docs.md`
5. `docs/review/REVIEW_BUNDLE__TASK-000-project-control-docs.md` (this file)

## Acceptance criteria → evidence

1. **Five files exist with required sections** — PASS. `ls` output below; CLAUDE.md is
   60 lines (< ~80) and contains read-first, plan-before-edit, ticket/review-bundle,
   branch, and no-secrets rules plus quick commands.
2. **SPEC.md sections** — PASS. Contains purpose, current v0 scope, non-goals, target
   pipeline (with current mapping), six output principles, honest limitation language.
3. **CURRENT_STATE.md factual + labeled** — PASS. Generic pip/uvicorn commands first
   (conda mentioned only as a README suggestion); unreproduced code observations are
   under "Observed issues to verify/fix in future tickets (not reproduced at runtime)".
4. **No modifications to tracked files** — PASS. Exact output below: `git status --short`
   shows only untracked `CLAUDE.md`, `SPEC.md`, `docs/`; `git diff --stat` is empty.
5. **No secrets in new files** — PASS after tightening the grep (see note below).
6. **Real command output recorded** — this section.

## Commands run and exact results

Baseline before creating files:

```
$ git status --short
(no output — clean; the pre-existing local docs/ and eval/ dirs were empty, and
backend/.env and logs/ are gitignored, so none appear)
```

After creating the five files:

```
$ git status --short
?? CLAUDE.md
?? SPEC.md
?? docs/

$ git diff --stat
(no output — no tracked files modified)

$ ls CLAUDE.md SPEC.md docs/CURRENT_STATE.md docs/tickets docs/review
CLAUDE.md
SPEC.md
docs/CURRENT_STATE.md
docs/tickets:
TASK-000-project-control-docs.md
docs/review:
REVIEW_BUNDLE__TASK-000-project-control-docs.md

$ wc -l CLAUDE.md
60 CLAUDE.md
```

Secret scan — first attempt used pattern `sk-[a-zA-Z0-9]|api_key\s*=`, which
false-positived on the substring "sk-" inside "TASK-NNN"/"TASK-000" (9 doc lines
matched, all ticket-name references, none secrets). Rerun with a tightened pattern:

```
$ grep -rinE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"']?[A-Za-z0-9_-]{10,}' CLAUDE.md SPEC.md docs/
(no output)
grep exit code: 1 (1 = no matches)
```

Runtime sanity (best effort, read-only):

```
$ curl -s --max-time 3 http://localhost:8000/health
curl exit code: 7 (connection refused — no server was running; not started for this docs-only ticket)

$ python3 -c "from backend.app import app; print('import OK:', app.title)"
ModuleNotFoundError: No module named 'dotenv'
(system python3 lacks backend deps — consistent with the missing-requirements.txt gap)

$ conda run -n quotecheck python -c "from backend.app import app; print('import OK:', app.title)"
import OK: QuoteCheck API
(local machine has a conda env named "quotecheck" with deps installed; app imports cleanly)
```

## Failures / unknowns / out-of-scope findings

- No failures. The curl connection refusal and system-python ModuleNotFoundError are
  expected environment states, recorded above, not regressions from this ticket.
- Unreproduced code observations (schema.py default_factory kwarg typo, prompt.py
  literal `\\n`/`\\N` escapes, README `gpt-40-mini` typo, missing
  `backend/requirements.txt`) are documented in `docs/CURRENT_STATE.md` for future
  tickets; deliberately not fixed here.
- Not committed; user to review and commit.
