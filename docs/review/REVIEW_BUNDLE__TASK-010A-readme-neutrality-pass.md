# REVIEW_BUNDLE — TASK-010A — README neutrality pass

## Files changed

- `README.md` (edited)
- `docs/CURRENT_STATE.md` (edited)
- `docs/tickets/TASK-010A-readme-neutrality-pass.md` (new)
- `docs/review/REVIEW_BUNDLE__TASK-010A-readme-neutrality-pass.md` (this file, new)

No files under `frontend/`, `backend/`, `examples/outputs/`, `backend/.env`, `logs/`,
or `package-lock.json` touched. No commits made.

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
?? docs/tickets/TASK-010A-readme-neutrality-pass.md

$ git diff --stat
 README.md             | 34 ++++++++++++++++++----------------
 docs/CURRENT_STATE.md | 22 +++++++++++++++++-----
 2 files changed, 35 insertions(+), 21 deletions(-)
```

## What changed (wording)

README.md, a section near the end of the file (previously headed with a
self-promotional "portfolio-credibility" framing) was replaced with a neutral
`## Design notes` section. The intro line was reworded from a defensive/
credibility-framed statement to a plain lead-in ("A few deliberate choices in this
v0:").

The underlying factual content was preserved and restated as plain design choices,
not credibility evidence:

```markdown
## Design notes

A few deliberate choices in this v0:

- **Schema-first API responses** (Pydantic) — the UI and any future analyzer are
  bound to the same validated shape, not to whatever a prompt happens to return.
- **Deterministic demo mode** — `metadata.model = "quotecheck-demo-analyzer"` in
  Demo mode, never an OpenAI model name, so the UI badge and JSONL logs can't
  accidentally overstate what produced a result.
- **Optional OpenAI mode** — opt-in, requires `backend/.env` with
  `OPENAI_API_KEY`; see [Demo mode vs. OpenAI mode](#demo-mode-vs-openai-mode).
- **Reviewable report sections** — explanation, risk, vendor questions, and
  things to verify are separate, structured fields, not a single free-text blob.
- **JSONL request logs** — every request is a traceable record (request_id,
  prompt version, latency, schema validity, risk counts) in
  `logs/app_runs.jsonl`.
- **Honest limitations, stated plainly** rather than glossed over, per `SPEC.md`
  and [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).
```

One bullet from the prior version (a ticket/review-bundle workflow claim) was
dropped rather than restated — it described process/methodology rather than a
product design choice, and is already visible from the `docs/tickets/`/`docs/review/`
entries in the repo-structure tree just below this section, so restating it here
would have re-introduced "look how disciplined my workflow is" framing. Every other
factual claim from the original section was preserved.

`docs/CURRENT_STATE.md` was also updated in two places to satisfy the acceptance
criteria's zero-match grep across the file:
- A new "Fixed in TASK-010A" entry describes the change neutrally (reframed under a
  "Design notes" heading; content preserved) without quoting the removed heading.
- A pre-existing TASK-007 changelog entry (predating this ticket) referenced the
  removed heading and described the README as rewritten "for a public/portfolio
  audience." Since the ticket's acceptance criteria require the grep to return no
  matches across `docs/CURRENT_STATE.md` as a whole, this historical entry was
  reworded to describe the same facts (a general-audience README rewrite adding a
  design-rationale section) without the flagged words. No historical fact was
  changed — only the flagged wording.

## Acceptance criteria — evidence

- **README no longer contains self-promotional/portfolio-specific wording.** ✅ See
  grep evidence below.
- **README has a neutral "Design notes" section preserving the underlying factual
  content.** ✅ `grep -n '^## ' README.md` shows `## Design notes` at README.md:260,
  content shown above.
- **grep for portfolio/credible/etc. across README.md, docs/PROJECT_STATUS.md,
  docs/LOCAL_DEMO.md, and docs/CURRENT_STATE.md returns no matches.** ✅ See below —
  zero matches after also fixing the pre-existing TASK-007 changelog entry.
- **README links still resolve to existing files.** ✅ `docs/PROJECT_STATUS.md`,
  `docs/LOCAL_DEMO.md`, `examples/README.md` all confirmed present.
- **`docs/CURRENT_STATE.md` has a short TASK-010A entry and updated "Last updated"
  line.** ✅ "Last updated" now reads TASK-010A; new entry added, described
  neutrally per user direction (no verbatim quote of the removed heading).
- **No backend/frontend/example-output files changed.** ✅ `git status --short`
  below shows only the four files listed above.
- **Review bundle records exact commands and exact output.** ✅ This file.

## Commands run (exact, real output)

### 1. Repo state before changes

```
$ git branch --show-current
task/TASK-010A-readme-neutrality-pass

$ git status --short
(clean)

$ git log --oneline -5
60619cd Merge branch 'task/TASK-010-public-readiness-review'
a480c83 docs: add TASK-010 public project status docs
1b0a73f Merge branch 'task/TASK-009-public-setup-cleanup'
30e0ee6 docs: clean up TASK-009 public setup path
a30f5fa Merge branch 'task/TASK-008A-personalize-demo-guidance'
```

Confirms TASK-010 is merged into main and this branch starts clean.

### 2. Neutrality grep (first pass — before fixing the historical TASK-007 entry)

```
$ grep -RInE 'portfolio|credible|LinkedIn|Finny|\bDM\b|hiring|resume|candidate|interview' \
    README.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md docs/CURRENT_STATE.md || echo "no matches"
docs/CURRENT_STATE.md:314:- `README.md`: rewritten for a public/portfolio audience. [...]
docs/CURRENT_STATE.md:320:  is portfolio-credible" section (schema-first contract, [...]
```

Both hits were in a pre-existing TASK-007 changelog entry (not touched by this
ticket's README edit) — reworded per the "What changed" section above, keeping the
same facts.

### 3. Neutrality grep (final)

```
$ grep -RInE 'portfolio|credible|LinkedIn|Finny|\bDM\b|hiring|resume|candidate|interview' \
    README.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md docs/CURRENT_STATE.md || echo "no matches"
no matches
```

### 4. Heading check

```
$ grep -n '^## ' README.md
9:## What it is, who it helps, why it exists
25:## Try it in under a minute (no API key needed)
92:## What a report looks like
125:## Screenshot
133:## Demo mode vs. OpenAI mode
166:## API
189:## Architecture
220:## What works today
234:## Limitations
260:## Design notes
281:## Repo structure (high level)
332:## Roadmap
341:## License
```

### 5. Link-target existence

```
$ test -f docs/PROJECT_STATUS.md && echo "docs/PROJECT_STATUS.md OK"
docs/PROJECT_STATUS.md OK
$ test -f docs/LOCAL_DEMO.md && echo "docs/LOCAL_DEMO.md OK"
docs/LOCAL_DEMO.md OK
$ test -f examples/README.md && echo "examples/README.md OK"
examples/README.md OK
```

### 6. Final repo state

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
?? docs/tickets/TASK-010A-readme-neutrality-pass.md

$ git diff --stat
 README.md             | 34 ++++++++++++++++++----------------
 docs/CURRENT_STATE.md | 22 +++++++++++++++++-----
 2 files changed, 35 insertions(+), 21 deletions(-)
```

(This bundle file itself is untracked/new at the time of these commands and so does
not yet appear in `git status`; it is listed under "Files changed" above.)

## Out-of-scope observations (not acted on)

- No broken README links or commands were discovered during this pass — no setup
  changes were needed.

## Definition of done — check

- [x] Ticket file created (`docs/tickets/TASK-010A-readme-neutrality-pass.md`).
- [x] Plan approved by user (with one correction on wording in `docs/CURRENT_STATE.md`
      and this review bundle) before implementation.
- [x] Implementation stayed within approved file scope.
- [x] All acceptance criteria have concrete evidence above, no placeholders.
- [x] `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-010A.
- [x] No secrets committed; no commits made at all — work is on
      `task/TASK-010A-readme-neutrality-pass`, left for the user to review and
      commit manually.
