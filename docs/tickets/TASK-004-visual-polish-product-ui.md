# TASK-004 — Visual polish: product-grade quote-understanding UI

## 1. Goal

Make the frontend feel like a polished AI quote-understanding product suitable for a
2-minute portfolio demo — calm, practical, trustworthy — without changing any of the
information architecture TASK-003 already got right (explanation-first line-item cards,
risk pills, NEEDS CLARIFICATION badge, evidence needed, vendor questions, things to
verify).

## 2. Context

TASK-003 made the right data visible but the app still looks like an unstyled scratchpad:
the stock Vite `index.css` theme is still loaded (dark `#242424` background under
`prefers-color-scheme: dark`, fighting the light-assuming inline styles in `App.jsx`), the
`<h1>` uses the Vite template's `3.2em` size, `index.html` still has `<title>frontend</title>`
and the Vite favicon, risk/vague badges use dark-mode-style fills, raw JSON is always
expanded at full height, there's no real loading state (only a button label change), and
errors render as bare `crimson` text. The TASK-003 review bundle also records that the UI
was never visually verified in a real browser. This is a design-only visual pass: no new
data fields, no new endpoints, no architecture change.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-004-visual-polish-product-ui.md`
- `docs/review/REVIEW_BUNDLE__TASK-004-visual-polish-product-ui.md`
- `frontend/src/App.jsx`
- `frontend/src/index.css`
- `frontend/index.html`
- `docs/CURRENT_STATE.md`
- Delete: `frontend/src/App.css` (dead, unimported since before TASK-003)

Never touch: any `backend/` source file, `package.json` / `package-lock.json` (no new
dependencies), `README.md`, `backend/.env`, `logs/`, secrets of any kind.

## 4. Out of scope

No backend changes. No new data flow — the `/analyze` request payload (`{ quote_text }`)
and the fields already rendered stay the same; no newly-surfaced fields (`price`,
`uncertainty_markers`, `refusals`, `metadata.created_at`). No price benchmarking. No
routing. No dark mode / theme switcher. No PDF/OCR. No database work. No new
dependencies (fonts, icon libraries, animation libraries, CSS frameworks). No large
redesign — restyle the existing structure, don't rearchitect the component tree beyond
light restructuring for readability.

## 5. Acceptance criteria

1. App renders a single, deliberate light theme regardless of OS
   `prefers-color-scheme` (no dark-background flash from the Vite default).
2. In each line-item card, `explanation` is the visually dominant text; risk is
   readable both from badge text and from a colored left-border accent on the card.
3. Risk badges use semantic wording (not raw color names) and a pale-tint style
   distinct from the violet "NEEDS CLARIFICATION" badge.
4. The sample quote (unchanged) still visibly demonstrates all 3 stub items
   (brake/red, tyre/yellow, other-unspecified/vague badge).
5. Raw JSON is collapsed by default (native `<details>`), expandable, and the
   "Copy JSON" action still works from within it.
6. Disclaimer text remains visible in the report without expanding anything.
7. A real loading state (beyond the button label) and a styled error state
   (replacing bare `crimson` text) both exist and were exercised manually.
8. `frontend/index.html` has a real page title (no default "frontend").
9. `npm run lint` and `npm run build` pass; `package.json` has zero new
   dependencies; `git diff` touches only `frontend/` and `docs/` files.
10. `/analyze` response compatibility preserved; no backend changes.

## 6. Commands to run

```bash
cd frontend && npm run lint && npm run build
uvicorn backend.app:app --host 0.0.0.0 --port 8000   # separate terminal, from repo root
cd frontend && npm run dev -- --host                 # manual browser check against the above
git diff --stat main   # confirm only frontend/ and docs/ changed
```

## 7. Definition of done

- Ticket approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (exact
  commands, exact output, no placeholders); manual browser verification recorded
  honestly (screenshot if tooling allows, otherwise a plain statement of what was
  checked and how).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-004.
- No secrets committed; no backend files changed; work stays on
  `task/004-visual-polish-product-ui`.
