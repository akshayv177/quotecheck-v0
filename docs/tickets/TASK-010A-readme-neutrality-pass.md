# TASK-010A — README neutrality pass

## 1. Goal

Make the README read like a natural public project README, not a portfolio/
application artifact — without changing any underlying facts about the project.

## 2. Context

TASK-010 (public readiness review) is committed and merged into main. One section of
README.md still frames the project's engineering choices as credibility proof
(a self-promotional "portfolio" heading) rather than stating them plainly. A grep
scan confirms this is the only portfolio/credible-flavored wording in README.md or
docs/CURRENT_STATE.md — the rest of the README (setup, examples, architecture,
limitations, project-status links) already reads neutrally and is unchanged by this
ticket.

## 3. Strict file scope

Allowed to create/update:
- `README.md`
- `docs/CURRENT_STATE.md`
- `docs/tickets/TASK-010A-readme-neutrality-pass.md`
- `docs/review/REVIEW_BUNDLE__TASK-010A-readme-neutrality-pass.md`

Never touch: `frontend/`, `backend/`, `examples/outputs/`, `backend/.env`, `logs/`,
`package-lock.json`, any secrets.

## 4. Out of scope

No product changes, no UI changes, no setup changes (unless a broken README
link/command is discovered during this pass), no new features, no screenshots, no
OpenAI calls, no application/career/outreach language.

## 5. Acceptance criteria

- README no longer contains self-promotional/portfolio-specific wording.
- README has a neutral "Design notes" section preserving the underlying factual
  content.
- `grep -RInE 'portfolio|credible|LinkedIn|Finny|\bDM\b|hiring|resume|candidate|interview'
  README.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md docs/CURRENT_STATE.md` returns
  no matches.
- README links still resolve to existing files (`docs/PROJECT_STATUS.md`,
  `docs/LOCAL_DEMO.md`, `examples/README.md` all present).
- `docs/CURRENT_STATE.md` has a short TASK-010A entry (described neutrally, without
  quoting the old heading verbatim) and an updated "Last updated" line.
- No backend/frontend/example-output files changed.
- Review bundle records exact commands and exact output.

## 6. Commands to run

```bash
grep -RInE 'portfolio|credible|LinkedIn|Finny|\bDM\b|hiring|resume|candidate|interview' \
  README.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md docs/CURRENT_STATE.md || true
grep -n '^## ' README.md
test -f docs/PROJECT_STATUS.md
test -f docs/LOCAL_DEMO.md
test -f examples/README.md
git status --short
git diff --stat
```

## 7. Definition of done

- Ticket approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle.
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-010A.
- No secrets committed; not committed at all — left for the user to review and
  commit manually.
