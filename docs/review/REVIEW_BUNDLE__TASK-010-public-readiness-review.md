# REVIEW_BUNDLE — TASK-010 — Public readiness review

## Revision note (read this first)

This ticket went through two passes. The first pass created
`docs/PUBLIC_READINESS_REVIEW.md`, `docs/DEMO_CHECKLIST.md`, and `docs/DEMO_SCRIPT.md`.
The user reviewed the uncommitted result and judged `DEMO_SCRIPT.md` (scripted
narration beats + anticipated audience Q&A) and `DEMO_CHECKLIST.md`'s framing
("before showing QuoteCheck to anyone," "memorized," "if asked") to read as
presenter/application prep rather than a normal public-repo artifact. Per that
direction:

- `docs/DEMO_SCRIPT.md` was **deleted**, not replaced.
- `docs/DEMO_CHECKLIST.md` was **reframed and renamed** to `docs/LOCAL_DEMO.md` — a
  neutral local run guide with no presenter/audience language.
- `docs/PUBLIC_READINESS_REVIEW.md` was **renamed** to `docs/PROJECT_STATUS.md`
  (content unchanged apart from the title/heading) — a more normal name for a
  public-repo status doc.
- README and `docs/CURRENT_STATE.md` were updated to match.

This review bundle reflects the final, revised state only.

## Files changed

- `docs/tickets/TASK-010-public-readiness-review.md` (new; rewritten in the revision
  pass to describe the final scope)
- `docs/PROJECT_STATUS.md` (new)
- `docs/LOCAL_DEMO.md` (new)
- `docs/assets/.gitkeep` (new — reserves the directory; no image added, no real
  screenshot exists yet)
- `README.md` (edited)
- `docs/CURRENT_STATE.md` (edited)
- `docs/review/REVIEW_BUNDLE__TASK-010-public-readiness-review.md` (this file, new)

Not committed / not present in the working tree:
- `docs/DEMO_SCRIPT.md` — created in the first pass, deleted per user direction.
- `docs/DEMO_CHECKLIST.md` — created in the first pass, superseded by
  `docs/LOCAL_DEMO.md` (renamed + reframed, not kept alongside it).

Not touched: `examples/README.md` and `backend/.env.example` — both inspected during
this ticket and found already accurate (Demo mode framed as a deterministic stub, no
price-benchmarking claims, safe placeholder key text) — no mismatch found, left
unchanged. No files under `frontend/src/`, `backend/core/`, `examples/outputs/`,
`backend/.env`, `logs/`, or `package-lock.json` touched. No commits made.

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
?? docs/LOCAL_DEMO.md
?? docs/PROJECT_STATUS.md
?? docs/assets/
?? docs/review/REVIEW_BUNDLE__TASK-010-public-readiness-review.md
?? docs/tickets/TASK-010-public-readiness-review.md

$ git diff --stat
 README.md             | 19 ++++++++++++++-----
 docs/CURRENT_STATE.md | 44 +++++++++++++++++++++++++++++++++++++++++++-
 2 files changed, 57 insertions(+), 6 deletions(-)
```

## Amendment notes (approved before/during implementation)

1. No private career/outreach terms are written into any committed repo file
   (ticket, review bundle, or docs) — replaced with the neutral phrase "private
   career/outreach context" in prose. Those explicit terms (Finny/LinkedIn/Loom/DM/
   hiring) appear only inside the grep command itself, never in prose.
2. The public-context grep scope targets public-facing docs only (`README.md`,
   `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md`, `docs/CURRENT_STATE.md`) rather
   than the whole repo.
3. (This pass) No presenter/audience-facing scripted content is committed —
   `docs/DEMO_SCRIPT.md` was removed and `docs/LOCAL_DEMO.md` avoids "before
   showing," "memorized," "if asked," and similar wording.

## Acceptance criteria — evidence

- **`docs/PROJECT_STATUS.md` exists and summarizes what is public-ready, what is
  still limited, and what should not be overclaimed.** ✅ Three sections: "What's
  public-ready today," "What's still limited," "What should not be overclaimed,"
  written from direct inspection.
- **`docs/LOCAL_DEMO.md` exists and gives a neutral, practical local run guide (not
  presenter-framed).** ✅ 8 numbered steps (clean git status → start backend →
  verify `/health` → run `/analyze` → start frontend → test UI → optional OpenAI
  mode → screenshot capture location), each with the literal command. Scanned for
  presenter/audience wording — none found (see "Commands run" below).
- **`docs/DEMO_SCRIPT.md` does not exist in the working tree.** ✅ Deleted; confirmed
  by `test ! -f` below.
- **`docs/DEMO_CHECKLIST.md` does not exist in the working tree.** ✅ Renamed to
  `docs/LOCAL_DEMO.md`, not left behind; confirmed by `test ! -f` below.
- **README points to `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md`, and
  `examples/README.md` — no dangling links.** ✅ Limitations-section paragraph
  (README.md) links all three; Screenshot section links
  `docs/LOCAL_DEMO.md#8-screenshot-capture-location`; repo-structure tree lists
  `docs/PROJECT_STATUS.md` and `docs/LOCAL_DEMO.md`. Grepped README for the old
  filenames — no hits (see below).
- **README/setup instructions are clear about running commands from the repo root
  where needed.** ✅ Explicit "run this from the repo root — it reads
  `examples/quote_ac_repair.txt` as a relative path" note above the `/analyze` curl
  example, on top of the pre-existing "From repo root:" note above the backend
  install block.
- **README clearly separates demo mode and OpenAI mode.** ✅ Pre-existing "Demo mode
  vs. OpenAI mode" section untouched by this ticket — already met this criterion.
- **README does not imply price benchmarking is implemented.** ✅ "Price
  benchmarking is **not implemented**" (Limitations) and "no market price comparison
  is being made" (`/analyze` sample response, unchanged) are the only
  price-benchmarking statements.
- **No fake screenshots or fake assets are added.** ✅ `docs/assets/` contains only
  `.gitkeep`; no `.png`/`.jpg`/`.jpeg` anywhere in the repo.
- **`docs/CURRENT_STATE.md` is updated with TASK-010, including the
  DEMO_SCRIPT/DEMO_CHECKLIST → LOCAL_DEMO revision.** ✅ "Last updated" line reads
  TASK-010; "Fixed in TASK-010" section documents both the new docs and the
  mid-ticket revision explicitly.
- **Backend demo-mode validation still passes.** ✅ See "Commands run" below.
- **Frontend build still passes.** ✅ `npm run build` succeeded.
- **No product behavior changes.** ✅ No files under `backend/core/` or
  `frontend/src/` touched.
- **No secrets committed.** ✅ Secret-pattern grep found nothing; no commits made.
- **Review bundle contains exact commands and exact outputs.** ✅ This file, below.

## Commands run (exact, real output)

### 1. File-removal / rename confirmation

```
$ test -f docs/PROJECT_STATUS.md && echo "PROJECT_STATUS.md OK"
PROJECT_STATUS.md OK
$ test -f docs/LOCAL_DEMO.md && echo "LOCAL_DEMO.md OK"
LOCAL_DEMO.md OK
$ test ! -f docs/DEMO_SCRIPT.md && echo "DEMO_SCRIPT.md absent OK"
DEMO_SCRIPT.md absent OK
$ test ! -f docs/DEMO_CHECKLIST.md && echo "DEMO_CHECKLIST.md absent OK"
DEMO_CHECKLIST.md absent OK
```

### 2. Backend install + import (fresh venv, created and removed within this
   validation run — not committed)

```
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip install -q -r backend/requirements.txt
(exit code 0, no errors)

$ python -c "from backend.app import app; print(app.title)"
QuoteCheck API
```

### 3. Backend run in Demo mode, `/health`, `/analyze`

```
$ QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
$ sleep 2
$ curl -s http://127.0.0.1:8000/health
{"status":"ok"}

$ curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
    -d "$(python3 -c 'import json; print(json.dumps({"quote_text": open("examples/quote_ac_repair.txt").read()}))')"
```

Response `metadata` (confirms Demo mode, no OpenAI call made):

```json
{
  "prompt_version": "quotecheck_v0.2",
  "model": "quotecheck-demo-analyzer",
  "created_at": "2026-07-08T18:40:32.927530Z",
  "request_id": "85af9229-f6f2-46e1-bfc5-1384da29bf51",
  "latency_ms": 0,
  "schema_valid": true
}
```

Full response body matched the same domain-appropriate AC/appliance content already
documented in `examples/outputs/ac_repair.json` — no drift, since no analyzer code
was touched.

```
$ kill <uvicorn PID>
$ ps aux | grep uvicorn | grep -v grep
(no output — confirmed stopped)
```

### 4. Frontend build

```
$ cd frontend && npm run build
> frontend@0.0.0 build
> vite build

vite v7.3.1 building client environment for production...
transforming...
✓ 29 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.50 kB │ gzip:  0.33 kB
dist/assets/index-BLc0mHcd.css    1.99 kB │ gzip:  0.93 kB
dist/assets/index-BMhYUSbn.js   204.19 kB │ gzip: 64.19 kB
✓ built in 1.11s
```

### 5. Neutral-context scan (public-facing docs, revised file list)

```
$ grep -RInE 'Finny|LinkedIn|Loom|\bDM\b|hiring' README.md docs/PROJECT_STATUS.md \
    docs/LOCAL_DEMO.md docs/CURRENT_STATE.md || echo "no matches"
no matches
```

### 6. Presenter/audience-language scan (new for this revision)

```
$ grep -RInE "before showing|memorized|if asked|presenter|audience" \
    docs/LOCAL_DEMO.md docs/PROJECT_STATUS.md README.md docs/CURRENT_STATE.md || echo "no presenter language found"
docs/CURRENT_STATE.md:181:  earlier draft of this ticket also added a presenter-style `docs/DEMO_CHECKLIST.md`
docs/CURRENT_STATE.md:183:  `DEMO_SCRIPT.md` was deleted outright (presenter/audience framing doesn't belong in
docs/CURRENT_STATE.md:303:- `README.md`: rewritten for a public/portfolio audience. Now opens with a "what /
```

The three hits are all in `docs/CURRENT_STATE.md`'s historical change-log prose
(describing the TASK-010 revision itself, and an unrelated pre-existing TASK-007
entry) — not in `docs/LOCAL_DEMO.md`, `docs/PROJECT_STATUS.md`, or README's live
instructions. No presenter/audience language exists in the actual demo/run guide.

### 7. Secrets scan

```
$ grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' \
    README.md docs backend/.env.example
(no output, exit code 1 — no matches)
```

### 8. Cleanup

```
$ rm -rf .venv
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
?? docs/LOCAL_DEMO.md
?? docs/PROJECT_STATUS.md
?? docs/assets/
?? docs/review/REVIEW_BUNDLE__TASK-010-public-readiness-review.md
?? docs/tickets/TASK-010-public-readiness-review.md
```

Only the files listed in "Files changed" above are present — no stray files from
validation tooling, and no `DEMO_SCRIPT.md`/`DEMO_CHECKLIST.md` leftovers.

## Out-of-scope observations (not acted on)

- `examples/README.md` and `backend/.env.example` were re-inspected in this ticket's
  context and found already accurate; no changes were needed or made.
- No new screenshot was captured (would require a live browser session);
  `docs/LOCAL_DEMO.md` gives exact steps to add one later at
  `docs/assets/quotecheck-demo-ui.png`, and README will only embed it once that file
  exists.

## Definition of done — check

- [x] Ticket file created and updated to reflect the revised scope
      (`docs/tickets/TASK-010-public-readiness-review.md`).
- [x] Plan approved by user (with amendments in both the initial approval and this
      revision) before/during README/docs edits.
- [x] Implementation stayed within approved file scope; `examples/README.md` and
      `backend/.env.example` correctly left untouched (no mismatch found).
- [x] All acceptance criteria have concrete evidence above, no placeholders.
- [x] `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-010 and documents
      the DEMO_SCRIPT/DEMO_CHECKLIST → LOCAL_DEMO revision.
- [x] No secrets committed; no commits made at all — work is on
      `task/TASK-010-public-readiness-review`, left for the user to review and
      commit manually.
