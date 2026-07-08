# UI_REDESIGN_PLAN.md — LUXURY-UI-001

Design plan for the final public-polish pass on the QuoteCheck frontend. Companion to
`docs/tickets/LUXURY-UI-001-distinctive-public-ui.md` (which holds the binding scope
and acceptance criteria). Design-only: no backend, API, schema, or feature changes.

## 1. Current UI assessment

What's already right (keep):
- Information architecture: input card → risk-count strip → Summary → explanation-first
  line-item cards (risk-colored left border, semantic risk pill, "Needs clarification"
  badge, evidence list) → "Before you approve" two-column pair → always-visible
  disclaimer → mode badge + monospace run metadata → collapsed raw JSON with Copy.
- Honest states: staged loading with elapsed time (`aria-live="polite"`), failure-kind
  error copy, 55s client timeout, Demo/OpenAI mode badge.
- Single light theme with a coherent token set in `frontend/src/index.css`.

What makes it look generic:
- Accent is Tailwind's default blue-600 (`#2563eb`) on Tailwind-gray inks — the most
  default-looking palette on the web.
- Typography is one stock `system-ui` stack with no identity: headings differ from
  body only by size/weight; no distinct treatment for the wordmark, section labels,
  or the report itself.
- All component styling is inline JSX style objects, so there are no hover states,
  transitions, or per-component media queries beyond the two CSS helpers; everything
  has the same 12px-radius / 1px-border / faint-shadow card treatment with uniform
  visual weight.
- `frontend/index.html` still references the default Vite favicon (`/vite.svg`).
- Badges use filled-tint "alert component" styling; the report header is a bare `h2`
  plus an inline text strip, so the report doesn't read as a document with its own
  identity.

## 2. Design direction

**"Calm review document."** The report should read like a well-typeset professional
review document — the kind of artifact you'd forward to someone before approving a
purchase — not a dashboard, chatbot, or AI landing page.

Distinctiveness comes from three quiet moves, not ornament:
1. **Typography with intent** — a distinct heading/wordmark treatment and small-caps
   section labels, all from built-in system font stacks (no font dependencies).
2. **A non-default accent** — replace Tailwind blue with a deep, calm ink-teal/navy;
   lean slightly further into the existing warm paper background so surfaces feel
   like paper on a desk rather than panels in an admin tool.
3. **Hierarchy through weight, not boxes** — vary card emphasis (the line items are
   the star; summary and checklists are supporting; metadata is quiet) instead of
   giving everything identical card chrome.

Explicitly rejected: gradients as identity, glassmorphism, fake KPI tiles or metric
rows, sidebar/nav chrome pretending to be a bigger product, decorative icons, dark
mode.

## 3. Layout changes

Keep the single readable column (~860–900px max width) — report-first, no
two-pane split (a side-by-side layout would squeeze report line length, which is the
one thing that must stay highly readable).

- **App header band**: slim top band with the QuoteCheck wordmark, the existing
  "v0 prototype" chip, and the one-line purpose sentence — establishing the tool
  frame before the workflow starts.
- **Input as step one of a workflow**: the input card keeps its current content
  (label, textarea, helper line, button, loading region) but gets a visual treatment
  that reads as "workspace" (slightly stronger surface presence, refined textarea
  focus state) so it clearly begins the flow rather than floating as a lone widget.
- **Report as a document**: replace the bare `h2 Report` + inline strip with a
  document-style report header — title, the derived risk tally rendered as small
  chips (same client-side counts, no new data), and a hairline rule — so the report
  opens with its own identity and the input→report sequence reads as one coherent
  workflow.
- **Quiet footer zone**: disclaimer, mode badge, run metadata, and raw JSON stay in
  the demoted end-of-document zone they already occupy; visually quieter than the
  report body.

No reordering of sections, no new sections, no removed sections.

## 4. Visual system

- **Typography**: system stacks only, no dependencies. Wordmark and report title get
  a tighter, heavier treatment (weight/letter-spacing, not a new font); the two body
  section headings ("Line items, explained", "Before you approve") become small-caps
  letter-spaced section labels; body stays a humanist system stack at comfortable
  line-height (~1.6 for explanations); `ui-monospace` remains for run metadata and
  raw JSON.
- **Color**: swap `--accent` from `#2563eb` to a deep calm ink-teal/navy (with a
  matching hover shade); nudge `--bg` slightly warmer if needed; keep the existing
  per-risk red/yellow/green triples and violet vague tokens (they're semantic and
  readable) with at most tint refinement. All contrast stays WCAG AA.
- **Spacing**: adopt a consistent 4/8-based spacing scale via CSS custom properties;
  more air between report sections than within them (subtle hierarchy through
  spacing).
- **Cards**: hairline borders, slightly softer shadow, consistent radius; the risk
  left-border rail on line items stays but is refined; supporting cards (Summary,
  the two checklists) get a visually lighter treatment than line items.
- **Badges/pills**: keep the `Pill` primitive and all current semantics; restyle from
  filled-tint alert pills toward an editorial dot+label style (small colored dot,
  neutral pill body) for risk levels; "Needs clarification" and the mode badge keep
  their distinct identities. Wording unchanged.
- **Buttons**: primary Analyze button gets accent background with proper hover/
  active/disabled/focus-visible states; the Copy JSON button stays a quiet secondary.
- **CSS extraction (bounded)**: move inline style objects into CSS classes in
  `index.css` (or a recreated `App.css` if volume warrants) so hover states,
  transitions, and media queries become possible. **Preserve the existing React
  component structure** (`App`, `LineItemCard`, `Pill`/`RiskPill`/`VagueBadge`/
  `ModeBadge`, `Card`) — only small extractions that clearly improve readability are
  allowed; no broad component rewrite. Data flow, props, and rendered fields are
  untouched.

## 5. Interaction polish

- **Loading**: keep the existing staged labels, elapsed counter, slow hint, and
  `aria-live` logic exactly as-is; refine the `.status-pulse` bar's look (accent
  color, easing) only.
- **Report reveal**: subtle one-time fade/rise transition when the report appears,
  gated behind `prefers-reduced-motion: no-preference`.
- **Raw JSON**: stays a native `<details>` collapsed by default; style the summary
  row (chevron affordance, hover) so it reads as an intentional developer drawer
  rather than a bare disclosure triangle. Copy button behavior unchanged.
- **Micro-states**: button hover/active, textarea focus ring, card hover left as-is
  (no hover lift on report cards — it's a document, not a dashboard).

## 6. What not to change

- Backend — any file.
- The `/analyze` request payload, response handling, and every field currently
  rendered (no new fields surfaced, none removed).
- The prefilled sample quote text.
- Loading stage labels/timings, timeout logic, error-kind copy differentiation.
- Mode badge logic (`metadata.model === "quotecheck-demo-analyzer"`).
- Disclaimer always visible without expanding anything.
- `examples/` inputs and outputs.
- Section wording of the report ("Questions to ask the vendor", "Things to verify
  before approving", etc.).
- No new dependencies; no new asset files (logo/illustration) unless explicitly
  approved.

## 7. Files likely touched during implementation

- `frontend/src/App.jsx` — class names replacing inline styles; report header
  restructure; no data-flow change.
- `frontend/src/index.css` — token updates, spacing scale, extracted component
  classes (or a recreated `frontend/src/App.css` if the class volume warrants a
  separate file).
- `frontend/index.html` — tiny public-polish cleanup only: remove or replace the
  default Vite favicon reference; verify title/meta remain correct; no fake logo or
  new asset unless explicitly approved.
- `docs/CURRENT_STATE.md` — updated frontend description + "Last updated" line.
- `docs/review/REVIEW_BUNDLE__LUXURY-UI-001-distinctive-public-ui.md` — evidence.
- `README.md` — only if the UI description or screenshot instructions need a tiny
  update.

Never: `backend/`, `examples/outputs/`, `backend/.env`, `logs/`,
`package-lock.json` (stop and ask if npm changes it), secrets.

## 8. Acceptance criteria

1. App still works with the existing `/analyze` endpoint.
2. No backend behavior changes.
3. UI looks more polished and less generic.
4. Input area and report area feel like one coherent workflow.
5. Line-item report remains highly readable.
6. Vendor questions and things-to-verify are clearly separated.
7. Demo/OpenAI mode badge remains visible.
8. Loading state remains clear.
9. Raw JSON remains secondary/collapsible.
10. Responsive layout still works.
11. `npm run build` passes.
12. `npm run lint` passes.
13. Manual browser check passes using at least one sample quote.

## 9. Validation plan

1. `cd frontend && npm run lint && npm run build` — both must pass with zero new
   dependencies in `package.json`.
2. Start backend in Demo mode (`QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app
   --host 0.0.0.0 --port 8000` from repo root); `curl http://localhost:8000/health`.
3. `npm run dev -- --host`; manual browser pass with the prefilled sample quote:
   all three stub items render (brake/red, tyre/yellow, misc/needs-clarification),
   Demo mode badge visible, raw JSON collapsed then expanded + Copy works,
   disclaimer visible without expanding.
4. Loading state check (visible pulse + stage label) and error state check (stop the
   backend, confirm styled network-error card).
5. Responsive check at a narrow viewport (~375px): two-column pair collapses, no
   horizontal overflow.
6. Reduced-motion check: with `prefers-reduced-motion: reduce`, no report-reveal
   animation.
7. `git diff --stat main` — only files in the allowed scope changed.

## 10. Risks / unknowns

- **Inline-style → class extraction is the largest diff surface.** Mitigation: it's
  mechanical, bounded to styling (no prop/data changes), the component structure is
  preserved per ticket scope, and the manual browser pass re-verifies every report
  element against the acceptance list.
- **No visual regression tooling exists** — verification is a manual browser check
  plus lint/build; recorded honestly in the review bundle (no fake screenshots).
- **Favicon replacement**: removing the Vite icon is safe; *replacing* it would need
  a new asset, which requires explicit approval first — default plan is removal or
  an inline data-URI only if approved.
- **README drift**: the README's UI description ("What works today") may need a
  one-line touch if the report header wording changes; handled under the tiny-update
  allowance.
- **Taste risk**: "distinctive but not flashy" is subjective — the accent/type
  changes are deliberately conservative and reversible, and the user reviews the
  result in-browser before anything is committed.
