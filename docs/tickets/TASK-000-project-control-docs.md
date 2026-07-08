# TASK-000 — Project control docs and current-state baseline

Status: implemented on branch `task/TASK-000-project-control-docs` (2026-07-08)

## Goal

Set up project-control files so future Claude Code sessions can plan and work
efficiently and safely: a concise CLAUDE.md, a product SPEC.md, a factual
current-state baseline, and the ticket/review-bundle discipline itself.

## Scope

Create only:

- `CLAUDE.md`
- `SPEC.md`
- `docs/CURRENT_STATE.md`
- `docs/tickets/TASK-000-project-control-docs.md` (this file)
- `docs/review/REVIEW_BUNDLE__TASK-000-project-control-docs.md`

## Out of scope

- Any change to `backend/`, `frontend/`, `README.md`, or app behavior.
- Adding dependencies or a requirements file.
- Fixing observed code issues (schema default_factory typo, prompt escape literals,
  README model-name typo) — documented in `docs/CURRENT_STATE.md` for future tickets.
- Product features (parser stages, price benchmarking, PDF/OCR, tests, eval harness).
- Committing (user commits after review).

## Acceptance criteria

1. All five files above exist. CLAUDE.md includes: read-SPEC/CURRENT_STATE-first rule,
   plan-before-edit rule, ticket + review-bundle workflow, branch discipline,
   no-secrets rule, quick commands; and is under ~80 lines.
2. SPEC.md defines purpose, current v0 scope, non-goals, target pipeline, output
   principles (explanation, red flags, missing info, vendor questions, uncertainty,
   evidence), and honest limitation language.
3. `docs/CURRENT_STATE.md` factually summarizes architecture, commands, capabilities,
   and gaps, with a "Last updated" date; generic commands first (no environment-manager
   requirement baked in); observed-but-unreproduced code issues labeled as such.
4. `git status --short` / `git diff --stat` show only the five new files — no
   modifications to tracked files; exact output recorded truthfully in the review bundle.
5. No secrets in any new file (grep for key patterns comes back clean).
6. The review bundle records the actual commands run and their exact results,
   including any failures or unknowns. No placeholders.

## Verification commands

```bash
git status --short
git diff --stat
ls CLAUDE.md SPEC.md docs/CURRENT_STATE.md docs/tickets docs/review
grep -rinE 'sk-[a-zA-Z0-9]|api_key\s*=' CLAUDE.md SPEC.md docs/
wc -l CLAUDE.md
curl -s http://localhost:8000/health   # best effort; recorded honestly if unavailable
```
