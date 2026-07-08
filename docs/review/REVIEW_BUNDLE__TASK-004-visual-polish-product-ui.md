# Review Bundle — TASK-004 — Visual polish: product-grade quote-understanding UI

Branch: `task/004-visual-polish-product-ui`

## 1. Files changed

```
frontend/index.html    |   2 +-
frontend/src/App.css   |  42 -------  (deleted, was dead/unimported)
frontend/src/App.jsx   | 311 ++++++++++++++++++++++++++++++++++---------------
frontend/src/index.css | 128 ++++++++++++++------
4 files changed, 314 insertions(+), 169 deletions(-)
```

Plus new docs (this bundle, the ticket, and `docs/CURRENT_STATE.md` update). No
`backend/` file touched. No `package.json` / `package-lock.json` change.

- `frontend/src/index.css` — replaced the stock Vite template theme (dark
  `#242424` default, `body { display:flex; place-items:center }`, `3.2em` h1,
  `prefers-color-scheme: dark/light` split) with a single light-only token set
  (`--bg`, `--surface`, `--ink`/`--ink-2`/`--ink-3`, `--border`, `--accent`,
  per-risk color triples, `--vague-*`, `--error-*`), plus small CSS helpers used
  by `App.jsx`: `.two-col-grid` (responsive collapse under 720px), `.status-pulse`
  (loading indicator animation), `details > summary` styling.
- `frontend/src/App.jsx` — restyled every section using the tokens above:
  header (wordmark + "v0 prototype" chip + tagline), input panel as a card with
  helper text, a real loading state (pulse bar + status text, not just the
  button label), a styled error card (replacing bare `crimson` text), a report
  header with a derived risk-count strip (`{n} items · {n} high risk · {n}
  caution · {n} needs clarification`, computed client-side from the existing
  `line_items` array — no new data flow), line-item cards with a risk-colored
  left border plus pale-tint badges, a "Before you approve" section wrapping
  the existing two cards, and a footer with the disclaimer always visible,
  a metadata line, and raw JSON moved into a collapsed `<details>` block with
  the Copy button inside it. Microcopy updated per the approved plan (button
  labels, badge wording `HIGH RISK`/`CAUTION`/`LOW RISK`/`NEEDS CLARIFICATION`,
  section headings, placeholders, error copy). Component APIs unchanged:
  `Pill`, `Card`, `RiskPill`, `VagueBadge`, `LineItemCard` keep their existing
  props; a new `getRiskColors(level)` helper centralizes the risk color
  mapping shared by the badge and the card's left border.
- `frontend/src/App.css` — deleted. Confirmed unimported (only `index.css` is
  imported, in `main.jsx`) both before and after this change; deleting it
  changes no rendered output.
- `frontend/index.html` — `<title>` changed from `frontend` to `QuoteCheck —
  understand a quote before you approve it`.

## 2. Acceptance criteria — evidence

**1. Single light theme regardless of `prefers-color-scheme`.**
`index.css` no longer contains any `@media (prefers-color-scheme: …)` block;
`:root` sets `color-scheme: light` and `body` sets `background: var(--bg)`
unconditionally. Verified with:
```
$ grep -n "prefers-color-scheme" frontend/src/index.css
(no output — zero matches)
```

**2. `explanation` visually dominant; risk readable from badge + left border.**
`LineItemCard` in `App.jsx` renders `explanation` at `fontSize: 15,
lineHeight: 1.6` in `--ink` (darkest, most prominent text in the card);
`rationale_short` and the evidence list are `fontSize: 13` in the lighter
`--ink-2`; the category/action/confidence line is `fontSize: 12` in the
lightest `--ink-3`. The card's `borderLeft` uses `getRiskColors(item.risk_level).border`
(red/yellow/green), rendered alongside the `RiskPill`.

**3. Semantic risk badge wording, distinct from the vague badge.**
`getRiskColors` maps `red → "High risk"`, `yellow → "Caution"`,
`green → "Low risk"` (rendered upper-cased via the shared `Pill` component's
`textTransform: uppercase`), each in its own pale-tint color pair. The
"NEEDS CLARIFICATION" badge (`VagueBadge`) uses a separate violet token pair
(`--vague-bg` / `--vague-fg` / `--vague-border`) that doesn't reuse any risk
color, so it's visually distinguishable from all three risk states.

**4. Sample quote still demonstrates all 3 stub items.**
Sample text in `App.jsx` is unchanged: `"Brake pads replacement recommended.
Tyre rotation. Shop supplies / misc service charge included."` Confirmed live
against the running stub backend:
```
$ curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}'
```
Returned 3 `line_items`: `"Brake service/ pads (from quote)"` (`risk_level:
"red"`), `"Tyre replacement (from quote)"` (`risk_level: "yellow"`), and
`"Other/unspecified charges (from quote)"` (`risk_level: "yellow"`,
`vague_or_confusing: true`) — matching TASK-003's original acceptance
criterion, response shape unchanged.

**5. Raw JSON collapsed by default, expandable, Copy JSON works from inside it.**
`App.jsx` wraps the `<pre>{prettyJson}</pre>` block and the Copy button inside
a native `<details><summary>Developer: raw JSON</summary>…</details>`; `<details>`
has no `open` attribute, so it renders collapsed by default. `copyJson()` is
unchanged (`navigator.clipboard.writeText(prettyJson)`) and the button is now
nested inside the `<details>` body.

**6. Disclaimer visible without expanding anything.**
`result.disclaimer` renders directly in the report footer (`fontStyle:
"italic"`, `--ink-2`), outside and above the `<details>` block — visible as
soon as the report renders, no interaction required.

**7. Real loading state + styled error state, exercised manually.**
- Loading: while `loading === true`, a `.status-pulse` bar (CSS-animated,
  defined in `index.css`) plus the text "Analyzing your quote…" render under
  the Analyze button, in addition to the button label flipping to "Analyzing…".
- Error: `err` renders inside a card styled with `--error-bg` / `--error-fg` /
  `--error-border` (background + left border + text color), headline
  "Couldn't analyze this quote.", the raw error detail, and a hint
  ("Check that the backend is running on port 8000.") — replacing the old bare
  `color: crimson` line.
- Manual exercise: started the backend (`uvicorn`, stub mode) and frontend
  (`vite --host --port 5173`) locally; confirmed via `curl` that the dev
  server serves the updated `index.html` title and the updated `index.css`
  content (see §3 below for the full note on browser-level verification and
  its limits in this sandbox).

**8. `frontend/index.html` has a real title.**
```
$ curl -s http://localhost:5173/ | grep -i "<title>"
    <title>QuoteCheck — understand a quote before you approve it</title>
```

**9. Lint, build, no new deps, diff scope.**
```
$ cd frontend && npm run lint
> frontend@0.0.0 lint
> eslint .
(exit 0, no output — no lint errors)

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
dist/assets/index-CGYP89I0.js   202.20 kB │ gzip: 63.38 kB
✓ built in 789ms

$ git diff --stat main -- package.json frontend/package.json
(no output — untouched)

$ git diff --stat main
 frontend/index.html    |   2 +-
 frontend/src/App.css   |  42 -------
 frontend/src/App.jsx   | 311 ++++++++++++++++++++++++++++++++++---------------
 frontend/src/index.css | 128 ++++++++++++++------
 4 files changed, 314 insertions(+), 169 deletions(-)
```
Only `frontend/` files changed (docs additions listed separately in §1).

**10. `/analyze` compatibility preserved; no backend changes.**
`git diff --stat main -- backend/` produces no output. The `/analyze` curl
call in criterion 4 above returns the same field set the TASK-003 bundle
recorded (`line_items`, `overall_summary`, `verification_questions`,
`things_to_verify`, `uncertainty_markers`, `refusals`, `disclaimer`,
`metadata`) — no schema drift.

## 3. Manual browser verification — honest note

Following the same limitation TASK-003's review bundle recorded, this sandbox
does not have the Playwright Chromium runtime dependencies installed
(`chrome-headless-shell: error while loading shared libraries: libnspr4.so`),
and installing OS packages (`apt-get install libnspr4 …`) is a system-level
change outside this ticket's scope, so it was not attempted. What was actually
verified in place of a live-browser screenshot:

- Started the real stub backend (`uvicorn backend.app:app`, conda env
  `quotecheck`) and the real Vite dev server (`npm run dev -- --host --port
  5173`) together, confirmed `GET /health` → `{"status":"ok"}`.
- Confirmed `POST /analyze` with the exact sample quote returns the 3 expected
  items with the expected risk levels/badge trigger (§2 criterion 4).
- Fetched the dev server's served HTML and CSS directly via `curl` and
  confirmed the updated `<title>`, the new `:root` token block, and the new
  `.two-col-grid` / `.status-pulse` / `details > summary` rules are present
  and being served (no build-time-only drift between source and served
  output).
- Read every inline style value in the rewritten `App.jsx` against the token
  definitions in `index.css` to confirm no dangling/undefined `var(--…)`
  reference (all tokens referenced are defined in `:root`).
- Confirmed `npm run lint` and `npm run build` — a broken JSX/CSS reference
  would fail one of these; both passed clean.

This is static/served-output verification, not a rendered pixel check. As
agreed, the user will manually load `http://localhost:5173` in a real browser
before commit to do the pixel-level check (loading pulse animation, hover
states, badge colors, responsive collapse under 720px) that this sandbox
cannot perform. Both dev servers were stopped after verification
(`http://localhost:8000` and `:5173` both confirmed unreachable afterward).

## 4. Out-of-scope findings (not fixed, noted for future tickets)

- `uncertainty_markers`, `refusals`, `price`, and `metadata.created_at` /
  `schema_valid` remain unrendered by the frontend (same gap TASK-003 left
  open) — this was explicitly out of scope for a visual-only pass.
- No test suite exists for the frontend beyond ESLint; this ticket didn't add
  one (not in scope).
- `frontend/package-lock.json` unchanged — no dependency drift introduced.

## 5. Definition of done

- [x] Ticket written first: `docs/tickets/TASK-004-visual-polish-product-ui.md`.
- [x] Implementation stayed within the strict file scope in that ticket.
- [x] All 10 acceptance criteria have concrete evidence above (exact commands,
      exact real output, no placeholders).
- [x] `docs/CURRENT_STATE.md` "Last updated" line updated to TASK-004 (see next
      commit in this same change).
- [x] No secrets committed (`backend/.env` untouched, never read for output
      beyond confirming `QUOTECHECK_USE_OPENAI=0`); no backend files changed;
      work stayed on `task/004-visual-polish-product-ui`.
