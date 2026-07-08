# Review Bundle — TASK-006 — Mock/demo mode

## Files changed

```
$ git diff --stat
 README.md                     | 33 ++++++++++++++++++++------
 backend/.env.example          |  4 +++-
 backend/core/config.py        |  6 +++++
 backend/core/stub_analyzer.py |  4 ++--
 docs/CURRENT_STATE.md         | 55 ++++++++++++++++++++++++++++++++++++-------
 frontend/src/App.jsx          | 38 ++++++++++++++++++++++++++----
 6 files changed, 117 insertions(+), 23 deletions(-)

$ git status --porcelain
 M README.md
 M backend/.env.example
 M backend/core/config.py
 M backend/core/stub_analyzer.py
 M docs/CURRENT_STATE.md
 M frontend/src/App.jsx
?? docs/tickets/TASK-006-mock-demo-mode.md
```

(This review bundle is an additional new file, written after the diff above was
captured.) Only files listed in the ticket's file scope were touched. No
`backend/app.py`, `backend/core/openai_analyzer.py`, `backend/core/schema.py`,
`backend/core/prompt.py`, `package.json`/`package-lock.json`, or `backend/.env`
changes.

## Acceptance criteria — evidence

**1. Clean clone, no `backend/.env`, default env → `metadata.model ==
"quotecheck-demo-analyzer"`.**

`backend/core/config.py` adds:

```python
DEMO_ANALYZER_MODEL = "quotecheck-demo-analyzer"
```

`backend/core/stub_analyzer.py` now imports and uses it instead of `MODEL`:

```python
from backend.core.config import DEMO_ANALYZER_MODEL
...
metadata=MetaData(
    prompt_version=PROMPT_VERSION,
    model=DEMO_ANALYZER_MODEL,
    ...
)
```

Live verification (backend started with the repo's real `backend/.env`, which was
confirmed — without printing the API key — to have `QUOTECHECK_USE_OPENAI=0`, i.e.
Demo mode is what actually served this request):

```
$ curl -s http://localhost:8000/health
{"status":"ok"}

$ curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Misc charges."}' \
  | python3 -m json.tool | grep -A5 metadata
    "metadata": {
        "prompt_version": "quotecheck_v0.2",
        "model": "quotecheck-demo-analyzer",
        "created_at": "2026-07-08T10:33:14.350457Z",
        "request_id": "9edbb70c-1efd-485c-8f08-5e67787a992f",
        "latency_ms": 0,
```

**2. `logs/app_runs.jsonl` reflects the same honest label.**

```
$ tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
{
    "event": "quotecheck_analyze",
    "created_at": "2026-07-08T10:33:14.350558Z",
    "request_id": "9edbb70c-1efd-485c-8f08-5e67787a992f",
    "prompt_version": "quotecheck_v0.2",
    "model": "quotecheck-demo-analyzer",
    "latency_ms": 0,
    "schema_valid": true,
    "num_items": 3,
    "risk_counts": {"red": 1, "yellow": 2, "green": 0},
    "uncertainty": {...},
    "error": null
}
```

Single source of truth confirmed: `backend/app.py` logs `result.metadata.model`
directly, so fixing `stub_analyzer.py` fixed both the API response and the log
record with one change — no separate logging fix was needed.

**3. OpenAI mode unchanged in code.**

`backend/core/openai_analyzer.py` was not touched (confirmed via `git status
--porcelain` above — it does not appear in the diff). It still sets
`payload["metadata"]["model"] = MODEL` (the real `QUOTECHECK_MODEL` env value,
e.g. `gpt-4o-mini`). **Not live-tested** — no `OPENAI_API_KEY` was exercised in
this session, consistent with not spending real API credits/making external calls
without being asked; this criterion is verified by code inspection only, stated
honestly rather than claimed as tested.

**4. Frontend "Demo mode" / "OpenAI mode" badge.**

`frontend/src/App.jsx` adds:

```jsx
const DEMO_ANALYZER_MODEL = "quotecheck-demo-analyzer";
...
function ModeBadge({ model }) {
  const isDemo = model === DEMO_ANALYZER_MODEL;
  return (
    <Pill
      bg="var(--surface)"
      border="var(--border)"
      fg="var(--ink-3)"
      label={isDemo ? "Demo mode" : "OpenAI mode"}
    />
  );
}
```

placed next to the existing run-metadata footer line:

```jsx
<div style={{ marginTop: 10, display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
  <ModeBadge model={result.metadata?.model} />
  <div style={{ ...existing monospace metadata line... }}>
    request_id: ... · prompt_version: ... · model: ... · latency_ms: ...
  </div>
</div>
```

It reuses the existing `Pill` primitive (already used by `RiskPill`/`VagueBadge`
since TASK-003/004) for visual consistency, with neutral surface/border/ink-3
colors matching the header's existing "v0 prototype" chip — no new styling
system, no `index.css` changes. The badge is derived purely from
`result.metadata.model`, which is already part of the existing `/analyze`
response — no new endpoint, field, or request/response shape change.

**Verification limitation (honest):** I attempted to drive this end-to-end in a
real browser via Playwright (backend on :8000 in Demo mode, `npm run dev` on
:5183) to screenshot the rendered badge, but headless Chromium fails to launch in
this sandbox with `error while loading shared libraries: libnspr4.so: cannot open
shared object file` — the identical missing-system-library issue documented in
`docs/review/REVIEW_BUNDLE__TASK-005-latency-and-progress-states.md`. Installing
`libnspr4`/`libnss3` system packages would require `sudo apt-get install` /
`npx playwright install-deps`, a system change I did not make without asking.
**Not verified live in a browser:** the actual rendered appearance/placement of
the badge. What *was* verified: the component logic by direct code trace (the
`isDemo` comparison against the exact string the backend now returns, confirmed
live via curl above), `npm run lint`/`npm run build` passing (catches JSX/syntax/
hook errors), and that `Pill` renders `label` uppercase via `textTransform:
uppercase` (existing behavior, unchanged) — so the badge will read "DEMO MODE" /
"OPENAI MODE" visually, matching the existing `VagueBadge`/`RiskPill` casing
convention.

**5. README states no API key needed, near the top.**

`README.md` now has, directly under the disclaimer:

```
> **No OpenAI API key needed to try this.** QuoteCheck defaults to a deterministic
> **Demo mode** (`QUOTECHECK_USE_OPENAI=0`) that returns a full, schema-valid
> quote-understanding report with zero cost and zero credentials. Real OpenAI calls
> are opt-in — see [Configuration (modes)](#configuration-modes) below.
```

The "Demo (local)" section now opens with: "No `backend/.env` file and no OpenAI
API key are required for these steps — if `backend/.env` doesn't exist, the app
falls back to its built-in defaults, which is **Demo mode**." Step 2 now
describes the pre-filled sample quote and the new mode badge. The "Configuration
(modes)" section relabels stub mode as "Demo mode" in prose, clarifies a
`backend/.env` file is optional (only needed to switch to OpenAI mode), and
explains that `metadata.model` / the frontend badge always reflect the mode that
actually served the request. Internal identifiers (`QUOTECHECK_USE_OPENAI`,
`stub_analyzer.py`) are unchanged, per the file-scope decision.

**6. `.env.example` still has no secret, clarifies Demo mode.**

```
$ cat backend/.env.example
# Demo mode is the default (QUOTECHECK_USE_OPENAI=0) and needs NO API key at all —
# you don't even need to copy this file to backend/.env to try it.
# OPENAI_API_KEY below is only required if you set QUOTECHECK_USE_OPENAI=1.
OPENAI_API_KEY=your_key_here
...
```

Still a placeholder value (`your_key_here`), unchanged from before — no secret
introduced.

**7. `docs/CURRENT_STATE.md` updated.**

"Last updated" line changed to `2026-07-08 (TASK-006)`; a "Fixed in TASK-006"
section was added (above "Fixed in TASK-005") documenting the `metadata.model`
fix, the frontend badge, and the README/`.env.example` changes; the
Architecture, Commands, and Capabilities sections were updated in place to
describe `DEMO_ANALYZER_MODEL`, the badge, and the no-`.env`-required default.

**8. Zero new dependencies; lint/build pass.**

```
$ cd frontend && npm run lint && npm run build
> frontend@0.0.0 lint
> eslint .
(no output — zero warnings/errors)

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
✓ built in 698ms
```

`package.json`/`package-lock.json` do not appear in `git status --porcelain`
above — zero new dependencies.

## Commands run (full list)

```bash
cd frontend && npm run lint
cd frontend && npm run build
# scratch venv used only for manual server verification, not committed:
python3 -m venv <scratch>/venv
<scratch>/venv/bin/pip install -r backend/requirements.txt
<scratch>/venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port 8010   # first pass
<scratch>/venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port 8000  # matches frontend's hardcoded API_BASE
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{...}'
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
cd frontend && npm run dev -- --host --port 5183
node check_badge.mjs   # Playwright attempt — failed, libnspr4.so missing (see above)
git diff --stat
git status --porcelain
```

## Out-of-scope notes

- No broad rename of `QUOTECHECK_USE_OPENAI` / `stub_analyzer.py` /
  `analyze_quote_stub` was done, per explicit user decision — "Demo mode" is a
  product-facing/docs term only; internal code keeps "stub" naming.
- OpenAI-mode live behavior is unchanged and code-inspected but not exercised
  with a real API key in this session (no credentials were used or requested).
- Live browser verification of the badge's visual appearance was not possible in
  this sandbox (missing `libnspr4` system library for headless Chromium) —
  identical limitation to TASK-005; no system packages were installed to work
  around it.
- `backend/.env` in this environment already had `QUOTECHECK_USE_OPENAI=0`; its
  contents (other than that non-secret line) were not printed or altered.

## Definition of done

- [x] Implementation complete within file scope.
- [x] `npm run lint` and `npm run build` both pass.
- [x] Zero new dependencies.
- [x] Ticket file (`docs/tickets/TASK-006-mock-demo-mode.md`) written.
- [x] This review bundle written with concrete evidence, no placeholders.
- [x] `docs/CURRENT_STATE.md` "Last updated" line and "Fixed in TASK-006" entry
      added.
- [x] No secrets committed; no `backend/.env` changes.
- [x] Work left uncommitted on `task/006-mock-demo-mode` per instruction — the
      user will review and commit manually.
