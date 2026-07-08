# LUXURY-UI-001 — Distinctive public UI polish

## 1. Goal

Final visual polish pass before public recording/review. Make QuoteCheck look clean,
calm, smooth, tasteful, and product-like — a thoughtful quote-review workflow tool,
not a generic AI landing page or chatbot — without changing backend behavior, the
`/analyze` contract, or product scope.

Desired qualities: readable report-first layout, subtle hierarchy, strong spacing,
business/workflow oriented, distinctive but not flashy. Explicitly avoid: generic AI
gradient overload, fake enterprise dashboard clutter, fake metrics.

The full design direction lives in `docs/design/UI_REDESIGN_PLAN.md`; this ticket is
the scope/acceptance contract for the implementation.

## 2. Context

The information architecture from TASK-003/004/005/006 is right (explanation-first
line-item cards, semantic risk pills, needs-clarification badge, "Before you approve"
grouping, mode badge, staged loading, collapsed raw JSON) but the visual identity is
generic: default Tailwind-blue accent (`#2563eb`), stock `system-ui` type with no
typographic hierarchy beyond size, all styling as inline JSX objects (which blocks
hover/transition/media-query polish), and the default Vite favicon still referenced in
`frontend/index.html`. This is a design-only pass: no new data fields, no new
endpoints, no architecture change.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/LUXURY-UI-001-distinctive-public-ui.md` (this file)
- `docs/design/UI_REDESIGN_PLAN.md`
- `frontend/src/App.jsx`
- `frontend/src/index.css` (and recreating `frontend/src/App.css` only if class
  extraction warrants a separate file)
- `frontend/index.html` — **tiny public-polish cleanup only**: remove or replace the
  default Vite favicon reference, verify title/meta remain correct. Do **not** add a
  fake logo or any new asset file unless explicitly approved.
- `docs/CURRENT_STATE.md` (including its "Last updated" line)
- `docs/review/REVIEW_BUNDLE__LUXURY-UI-001-distinctive-public-ui.md`
- `README.md` — only if screenshot instructions or the UI description need a tiny
  update; no other prose changes.

Never touch: `backend/` (any file), `examples/outputs/`, `backend/.env`, `logs/`,
`package-lock.json` (unless npm itself changes it, in which case stop and ask),
secrets of any kind. No new dependencies (fonts, icon libraries, animation libraries,
CSS frameworks) unless there is a very strong reason — and if so, stop and ask first.

CSS extraction is bounded: extracting inline styles into CSS classes is allowed, but
preserve the existing React component structure (`App`, `LineItemCard`, `Pill`/
`RiskPill`/`VagueBadge`/`ModeBadge`, `Card`) unless a small extraction clearly
improves readability. No broad component rewrite.

## 4. Out of scope

No backend changes. No API/schema changes — the `/analyze` request payload
(`{ quote_text }`) and every field currently rendered stay exactly the same. No new
product features. No price benchmarking. No OCR/PDF/image parsing. No database/auth.
No local model/Ollama. No fake screenshots. No production claims. No career/outreach
language in repo files. No changes to `examples/` inputs or outputs. No dark mode /
theme switcher. No routing.

## 5. Acceptance criteria

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
12. `npm run lint` passes (it exists and is the only other frontend check).
13. Manual browser check passes using at least one sample quote (Demo mode; the
    prefilled sample must still visibly show all three stub items including the
    needs-clarification badge).

## 6. Commands to run

```bash
cd frontend && npm run lint && npm run build
QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 0.0.0.0 --port 8000   # separate terminal, from repo root
cd frontend && npm run dev -- --host    # manual browser check against the above
git diff --stat main    # confirm only allowed files changed
```

## 7. Definition of done

- Ticket and design plan approved before any frontend edit.
- Implementation complete within the file scope above; all acceptance criteria have
  concrete evidence in
  `docs/review/REVIEW_BUNDLE__LUXURY-UI-001-distinctive-public-ui.md` (exact commands,
  real output, no placeholders); manual browser verification recorded honestly.
- `docs/CURRENT_STATE.md` "Last updated" line reflects LUXURY-UI-001.
- No secrets committed; no backend files changed; work happens on
  `task/LUXURY-UI-001-distinctive-public-ui`; no commits without explicit user
  request.
