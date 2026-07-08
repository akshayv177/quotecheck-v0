# TASK-010 — Public readiness review

## 1. Goal

Perform a neutral public-readiness review and tightening pass for QuoteCheck v0 so
the repo is clear, honest, reproducible, and understandable for any public visitor —
without overclaiming what exists, and without presenter/audience-facing framing that
doesn't belong in a normal public repo.

## 2. Context

TASK-006 through TASK-009 already made the README/docs demo-mode-first, honest about
OpenAI mode being opt-in, and validated the clean-room setup path. This ticket adds
the artifacts a public visitor or reviewer would look for that don't exist yet: a
standalone project-status summary and a neutral local run guide — plus closes small
remaining setup-clarity gaps (explicit "run from repo root" framing, doc cross-links)
and documents screenshot status honestly (no fake screenshot is added).

**Revision note:** an earlier pass of this ticket also added a presenter-style
`docs/DEMO_CHECKLIST.md` ("before showing QuoteCheck to anyone") and a scripted
`docs/DEMO_SCRIPT.md` (narration beats, anticipated audience Q&A). Per user
direction, that framing was judged to read as presenter/application prep rather than
a normal public-repo artifact, so:
- `docs/DEMO_SCRIPT.md` was deleted outright — not replaced.
- `docs/DEMO_CHECKLIST.md` was reframed into a neutral local run guide and renamed to
  `docs/LOCAL_DEMO.md` (practical steps only: start backend, verify `/health`, run
  `/analyze`, start frontend, test UI, optional OpenAI mode, screenshot capture
  location — no "before showing," "memorized," "if asked," or audience language).
- `docs/PUBLIC_READINESS_REVIEW.md` was renamed to `docs/PROJECT_STATUS.md` (content
  unchanged apart from title/heading) as a more normal name for a public-repo status
  doc.

Product framing to preserve everywhere touched: quote understanding comes first, risk
detection second; Demo mode is deterministic and requires no API key; OpenAI mode is
optional and requires credentials; price benchmarking is not implemented; outputs are
review aids, not professional advice; setup commands are reproducible from repo root.

Repo docs must stay free of private career/outreach context — no such wording exists
in this repo's public-facing files today (verified by scan before and after this
ticket) and none should be introduced.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-010-public-readiness-review.md`
- `docs/review/REVIEW_BUNDLE__TASK-010-public-readiness-review.md`
- `docs/PROJECT_STATUS.md` (new)
- `docs/LOCAL_DEMO.md` (new)
- `docs/CURRENT_STATE.md`
- `README.md`
- `docs/assets/` (only a `.gitkeep` — no images unless a real screenshot already exists)

Intentionally not committed:
- `docs/DEMO_SCRIPT.md` — created in an earlier pass, deleted per user direction
  (presenter/audience framing doesn't belong in a public repo).
- `docs/DEMO_CHECKLIST.md` — created in an earlier pass, superseded by
  `docs/LOCAL_DEMO.md` (renamed + reframed, not kept alongside it).

Allowed only if needed:
- `examples/README.md`, only if sample/demo instructions need clarity
- `backend/.env.example`, only if a real setup/documentation mismatch exists

Never touch: `frontend/src/`, `backend/core/`, `examples/outputs/`, `backend/.env`,
`logs/`, `package-lock.json`, any secrets.

## 4. Out of scope

No product feature changes, no UI changes, no analyzer changes, no new examples, no
OpenAI calls, no price benchmarking, no OCR/PDF/image parsing, no database/auth, no
local model/Ollama integration, no fake screenshots, no fake metrics, no
production-readiness claims, no private career/outreach context in repo files, no
presenter/audience-facing scripted content, no commits.

## 5. Acceptance criteria

- `docs/PROJECT_STATUS.md` exists and summarizes what is public-ready, what is still
  limited, and what should not be overclaimed.
- `docs/LOCAL_DEMO.md` exists and gives a neutral, practical local run guide (not
  presenter-framed).
- `docs/DEMO_SCRIPT.md` does not exist in the working tree.
- `docs/DEMO_CHECKLIST.md` does not exist in the working tree (superseded by
  `docs/LOCAL_DEMO.md`).
- README points to `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md`, and
  `examples/README.md` — no dangling links to the removed/renamed files.
- README/setup instructions are explicit about running commands from the repo root
  where needed.
- README clearly separates Demo mode and OpenAI mode.
- README does not imply price benchmarking is implemented.
- No fake screenshots or fake assets are added.
- `docs/CURRENT_STATE.md` is updated with TASK-010 (including its "Last updated"
  line) and documents the DEMO_SCRIPT/DEMO_CHECKLIST → LOCAL_DEMO revision.
- Backend demo-mode validation still passes.
- Frontend build still passes.
- No product behavior changes.
- No secrets committed.
- Review bundle contains exact commands and exact outputs.

## 6. Commands to run

```bash
git status --short
python -c "from backend.app import app; print(app.title)"
QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
sleep 2
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json; print(json.dumps({"quote_text": open("examples/quote_ac_repair.txt").read()}))')"
kill %1

cd frontend && npm run build && cd ..

test -f docs/PROJECT_STATUS.md
test -f docs/LOCAL_DEMO.md
test ! -f docs/DEMO_SCRIPT.md
test ! -f docs/DEMO_CHECKLIST.md

grep -RInE 'Finny|LinkedIn|Loom|\bDM\b|hiring' README.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md docs/CURRENT_STATE.md || true
grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' README.md docs backend/.env.example
```

## 7. Definition of done

- Ticket approved, plan approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (exact commands,
  exact real output, no placeholders).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-010.
- No secrets committed; work stays on `task/TASK-010-public-readiness-review`. Not
  committed — left for the user to review and commit manually.
