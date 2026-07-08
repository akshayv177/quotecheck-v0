# Review Bundle — LUXURY-UI-001 — Distinctive public UI polish

Branch: `task/LUXURY-UI-001-distinctive-public-ui`

## 1. Files changed

```
docs/CURRENT_STATE.md  |  48 ++++-
frontend/index.html    |   1 -
frontend/src/App.jsx   | 269 ++++++++-----------------
frontend/src/index.css | 537 ++++++++++++++++++++++++++++++++++++++++++++-----
4 files changed, 617 insertions(+), 238 deletions(-)
```

Plus this bundle and the ticket/design-plan docs written in the planning turn
(`docs/tickets/LUXURY-UI-001-distinctive-public-ui.md`,
`docs/design/UI_REDESIGN_PLAN.md`). No `backend/` file touched, no
`package.json`/`package-lock.json` change, no `examples/` change, no README
change (the current README UI description/screenshot section did not need a
wording update — "before you approve", "raw JSON collapsed by default",
"Demo mode badge" etc. all remain accurate).

- `frontend/src/index.css` — replaced the Tailwind-blue accent (`#2563eb`)
  with a deep, calm ink-teal (`--accent: #0f4c46`, hover `#0b3934`); warmed
  `--bg`/`--border` tokens slightly; added a spacing scale
  (`--space-1`…`--space-7`), radius tokens (`--radius-sm/md/lg`), and a
  `--font-mono` token; added ~30 new component classes (`.qc-shell`,
  `.qc-header*`, `.qc-input-card*`, `.qc-textarea`, `.qc-btn-primary`,
  `.qc-btn-quiet`, `.qc-loading*`, `.qc-error-card*`, `.qc-report*`,
  `.qc-tally*`, `.qc-line-item*`, `.qc-card*`, `.qc-footer*`,
  `.qc-json-details`/`.qc-json-pre`, `.qc-pill*`) that replace the inline
  style objects previously in `App.jsx`; kept the existing `.two-col-grid`
  and `.status-pulse` selectors (colors refined, behavior unchanged); added a
  report-reveal fade/rise keyframe gated behind
  `@media (prefers-reduced-motion: reduce)` (animation disabled when the user
  prefers reduced motion). No new dependencies (system font stacks only, no
  icon library).
- `frontend/src/App.jsx` — every inline `style={{...}}` object in the render
  tree was replaced with a `className` from the new CSS classes; no JSX
  element was added, removed, or reordered beyond:
  - A document-style report header: the existing `h2 Report` + inline risk
    text is now `h2.qc-report__title` + a `.qc-tally` row of chip spans,
    still computed from the same client-side `riskCounts` memo (no new state,
    no new data).
  - Section headings ("Line items, explained", "Before you approve") moved
    from inline `h3` styles to `.qc-section-label` (small-caps look).
  - `Pill`'s prop shape changed from `{ bg, border, fg, label }` to
    `{ fg, label }` — the pill body is now a neutral
    `background: var(--surface-quiet)` / `border: var(--border)` (set in the
    `.qc-pill` CSS class) with a small colored dot (`.qc-pill__dot`,
    `background: currentColor`) and colored label text, both driven by the
    single `fg` value already computed per risk level. `RiskPill`,
    `VagueBadge`, and `ModeBadge` (all call `Pill` internally) — and
    `getRiskColors()`, which now returns `{ border, fg, label }` (dropped the
    now-unused `bg` field) — were updated to match; none of their own
    call-site props (`level`, `model`) changed.
  - `LineItemCard`'s risk-colored left border is now a CSS custom property
    (`style={{ "--line-item-accent": riskColors.border }}` on the
    `.qc-line-item` div, consumed by `border-left-color:
    var(--line-item-accent, var(--border))` in CSS) instead of an inline
    `borderLeft` string — same visual result, same data source.
  - `Card`'s internal markup/props (`{ title, children }`) are unchanged;
    only its inline styles became `.qc-card`/`.qc-card__title` classes.
  Component structure is otherwise identical: `App`, `LineItemCard`, `Pill`,
  `RiskPill`, `VagueBadge`, `ModeBadge`, `Card` are the same functions with
  the same responsibilities as before this ticket. No new components were
  introduced. All state (`quoteText`, `result`, `err`, `loading`, `copied`,
  `elapsedMs`), all effects, `analyzeQuote()`, `copyJson()`, the `/analyze`
  fetch call and its payload (`{ quote_text: quoteText }`), the stage-label/
  timeout/error-kind logic, and every field read off `result` are byte-for-
  byte unchanged from before this ticket.
- `frontend/index.html` — removed `<link rel="icon" type="image/svg+xml"
  href="/vite.svg" />` (the default Vite favicon reference). No replacement
  asset was added (none was approved). `<title>` and the viewport `<meta>`
  tag are unchanged.
- `docs/CURRENT_STATE.md` — updated the frontend description paragraph and
  added a "Fixed in LUXURY-UI-001" entry under Gaps history; "Last updated"
  line now reads `2026-07-09 (LUXURY-UI-001)`.

## 2. Acceptance criteria — evidence

**1. App still works with the existing `/analyze` endpoint.**
Verified live against a Demo-mode backend (see §3 commands) with three
different sample quotes — all returned valid `QuoteCheckResult` JSON and
rendered correctly in the browser (see §4).

**2. No backend behavior changes.**
```
$ git diff --name-only main -- backend | wc -l
0
```

**3. UI looks more polished and less generic.**
Accent moved off the default Tailwind blue-600 to a deliberate ink-teal;
typography gained a small-caps section-label treatment and a tighter
wordmark/report-title weight; badges moved from filled alert-style chips to
a neutral dot+label editorial style; spacing now follows a defined scale
instead of ad hoc pixel values. Confirmed visually via manual browser
screenshots (§4) — the report reads as a document rather than a component-
library demo.

**4. Input area and report area feel like one coherent workflow.**
The input card and the report both sit in the same `.qc-shell` column with
matching card/spacing language; the report now opens with its own
document-style header (title + risk-tally chips) directly below the input
card, rather than a bare `h2` — visually confirmed in the full-page
screenshot (§4).

**5. Line-item report remains highly readable.**
`explanation` is still the dominant text per card (`.qc-line-item__explanation`,
15px/1.6 line-height, `--ink`), `rationale_short` and evidence remain
secondary (`--ink-2`, 13px), and the risk-colored left border + risk pill are
both present. Confirmed in the vehicle-service, AC-repair, and vague-quote
screenshots (§4) — all three risk levels and the vague badge render legibly.

**6. Vendor questions and things-to-verify are clearly separated.**
"Before you approve" section still renders two distinct `Card`s in the
`.two-col-grid` (Questions to ask the vendor / Things to verify before
approving), unchanged content source (`verification_questions` /
`things_to_verify`). Confirmed in every report screenshot in §4.

**7. Demo/OpenAI mode badge remains visible.**
`ModeBadge` renders in the footer row in every captured report screenshot,
reading "Demo mode" (backend ran with `QUOTECHECK_USE_OPENAI=0` for every
test in §3–4).

**8. Loading state remains clear.**
Verified by delaying the `/analyze` response 4s via Playwright request
interception and screenshotting mid-request: the pulse bar (now in the new
accent color), the `aria-live="polite"` stage label ("Reading the quote…"),
and the elapsed-time counter ("1s elapsed") all rendered as before, with the
button showing the disabled "Analyzing…" state.

**9. Raw JSON remains secondary/collapsible.**
`<details className="qc-json-details">` still defaults to collapsed;
verified by loading the report and confirming the JSON block was not visible
until the summary row was clicked, at which point the pretty-printed JSON
and "Copy JSON" button appeared (chevron rotates via
`.qc-json-details[open] > summary::before`). Copy button still calls the
unchanged `copyJson()`.

**10. Responsive layout still works.**
Screenshotted the full report at a 375×900 viewport: the `.two-col-grid`
pair (Questions / Things to verify) collapsed to a single column exactly as
at desktop width, no horizontal overflow, all text remained legible.

**11. `npm run build` passes.** See §3 output — zero errors, zero warnings.

**12. `npm run lint` passes.** See §3 output — zero errors, zero warnings.

**13. Manual browser check passes using at least one sample quote.**
Performed with three sample quotes (`quote_vehicle_service.txt`,
`quote_ac_repair.txt`, `quote_vague_missing_details.txt`) plus the default
prefilled sample — see §4 for the full list of states exercised.

## 3. Commands run (exact, real output)

Environment note: no committed `.venv`/lockfile exists for the backend (a
known, pre-existing gap — see `docs/CURRENT_STATE.md` Gaps). A local venv was
created transiently for this ticket's validation only, per the README's
documented setup steps, and is not part of this diff (`.venv/` is untracked
and was not added to git).

```
$ cd frontend && npm run lint
> frontend@0.0.0 lint
> eslint .
(no output — zero errors/warnings)

$ npm run build
> frontend@0.0.0 build
> vite build

vite v7.3.1 building client environment for production...
transforming...
✓ 29 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.44 kB │ gzip:  0.30 kB
dist/assets/index-VOz-ZeiU.css    9.03 kB │ gzip:  2.47 kB
dist/assets/index-DGTwV41r.js   201.71 kB │ gzip: 63.53 kB
✓ built in 1.45s
```

```
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install -q -r backend/requirements.txt
$ QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
$ curl -s http://127.0.0.1:8000/health
{"status":"ok"}
```

`/analyze` against the three required sample files (real output, truncated to
the fields that matter for this ticket — model and per-item risk/vague flags):

```
=== quote_ac_repair ===
model: quotecheck-demo-analyzer
n_items: 1
[{'risk': 'yellow', 'vague': False}]
=== quote_vehicle_service ===
model: quotecheck-demo-analyzer
n_items: 3
[{'risk': 'red', 'vague': False}, {'risk': 'yellow', 'vague': False}, {'risk': 'yellow', 'vague': True}]
=== quote_vague_missing_details ===
model: quotecheck-demo-analyzer
n_items: 1
[{'risk': 'yellow', 'vague': True}]
```

```
$ git status --short
 M docs/CURRENT_STATE.md
 M frontend/index.html
 M frontend/src/App.jsx
 M frontend/src/index.css
?? .venv/    (transient local venv, not part of this diff)

$ git diff --stat main -- frontend docs
 docs/CURRENT_STATE.md  |  48 ++++-
 frontend/index.html    |   1 -
 frontend/src/App.jsx   | 269 ++++++++-----------------
 frontend/src/index.css | 537 ++++++++++++++++++++++++++++++++++++++++++++-----
 4 files changed, 617 insertions(+), 238 deletions(-)

$ git diff --name-only main -- backend | wc -l
0
$ git diff --name-only main -- frontend/package-lock.json | wc -l
0
$ git diff --name-only main -- frontend/package.json | wc -l
0
```

## 4. Manual browser verification

The frontend dev server (`npm run dev -- --host`) was driven with a headless
Chromium (Playwright, launched with the frontend's already-cached browser
binary; no new project dependency was added — this was a one-off local
verification tool, not added to `package.json`) against the Demo-mode backend
above. States exercised, each screenshotted (real captures, saved under
`docs/review/assets/LUXURY-UI-001/`) and visually inspected:

1. **Initial load** (`initial.png`) — header (wordmark + "v0 prototype" chip +
   tagline), input card with the prefilled sample quote, ink-teal "Analyze
   quote" button.
2. **Default sample quote → full report** (`report_full.png`) — risk-tally
   row (`3 items · 1 high risk · 2 caution · 1 needs clarification`), Summary
   card, all three line-item cards (brake/red, tyre/yellow, misc-charge/
   yellow+vague) each showing risk-colored left border, dot+label risk pill,
   "Needs clarification" badge on the third item, explanation text, "Why
   this risk level" rationale, evidence-needed bullets, and the category/
   action/confidence meta line; "Before you approve" two-column pair;
   disclaimer; Demo mode badge; monospace run metadata; collapsed raw-JSON
   `<details>`.
3. **Raw JSON expanded** (`report_json_expanded.png`) — clicking "Developer:
   raw JSON" revealed the pretty-printed JSON in the dark monospace panel
   with a working "Copy JSON" button and a rotated chevron.
4. **375px mobile viewport** (`report_mobile.png`) — same full report; the
   two-column "Before you approve" pair collapsed to one column; no
   horizontal overflow; all text remained legible at that width.
5. **Loading state** (`loading_state.png`) — `/analyze` response delayed 4s
   via request interception; captured the pulse bar, the `aria-live` stage
   label ("Reading the quote…"), the elapsed-time counter, and the disabled
   "Analyzing…" button mid-request.
6. **Error state** (`error_state.png`) — `/analyze` forced to fail via a
   `connectionrefused` route abort; captured the styled error card
   ("Couldn't analyze this quote." + the network-error message).
7. **`quote_ac_repair.txt`** (`report_ac_repair.png`) — 1 item, AC/appliance
   category, yellow/caution, domain-specific evidence requests and vendor
   questions rendered correctly.
8. **`quote_vague_missing_details.txt`** (`report_vague.png`) — 1 item,
   "Unclear item(s) — needs clarification", yellow + vague badges both
   shown, generic clarifying questions rendered correctly.
9. **Console check** — captured all `console` and `pageerror` events across
   the above; only Vite HMR connection logs and the standard React DevTools
   suggestion appeared. No warnings or errors.

All nine states matched the design intent in
`docs/design/UI_REDESIGN_PLAN.md` (calm review-document feel, ink-teal
accent, dot+label badges, document-style report header, collapsed JSON,
clear loading/error states, working responsive collapse) with no regressions
against the pre-existing information architecture.

Every screenshot above is a real capture from the running app (Demo mode,
`quotecheck-demo-analyzer`) — none are mocked up or hand-edited, consistent
with this repo's no-fake-screenshot policy. These are review-bundle evidence
images (distinct from the single canonical product screenshot reserved at
`docs/assets/quotecheck-demo-ui.png` referenced from the README, which
remains unset).

## 5. Out-of-scope observations (not fixed, noted only)

- `frontend/public/vite.svg` still exists on disk as an unreferenced asset
  now that the `<link rel="icon">` pointing to it was removed from
  `index.html`. Left in place — deleting it wasn't part of the approved
  scope (favicon *reference* removal only) and it has zero effect on the
  running app.
- No backend/requirements lockfile or `.venv` is committed to this repo (a
  pre-existing, already-documented gap in `docs/CURRENT_STATE.md`); the venv
  created for this ticket's validation was local-only and is not part of the
  diff.
