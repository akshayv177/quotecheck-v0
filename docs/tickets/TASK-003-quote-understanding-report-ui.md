# TASK-003 — Quote-understanding report UI

## 1. Goal

Update the frontend so the user can actually see the quote-understanding value
TASK-002 added to the backend. QuoteCheck should feel like a practical
quote-understanding report, not just a risk/audit output. Product story:
understand the quote first, then verify vague, risky, or confusing items.

## 2. Context

TASK-002 added `LineItem.explanation` and `LineItem.vague_or_confusing` to the
backend contract (`backend/core/schema.py`), bumped `PROMPT_VERSION` to
`quotecheck_v0.2`, and gave the stub analyzer a conservative generic-charge
catch-all (`backend/core/stub_analyzer.py`). None of this was visible in the UI:
`frontend/src/App.jsx` rendered a flat table that never read `explanation` or
`vague_or_confusing`.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-003-quote-understanding-report-ui.md`
- `docs/review/REVIEW_BUNDLE__TASK-003-quote-understanding-report-ui.md`
- `frontend/src/App.jsx`
- `docs/CURRENT_STATE.md`

Never touch unless proven necessary for frontend compatibility: any `backend/`
source file, `README.md`, `package-lock.json`, `backend/.env`, `logs/`, secrets
of any kind.

## 4. Out of scope

No backend changes. No price benchmarking. No full redesign (kept the existing
inline-style, single-file, no-framework approach). No new dependencies.

## 5. Acceptance criteria

- Display each line item's `explanation` prominently.
- Show `vague_or_confusing` as a clear badge/warning state when true.
- Keep existing fields visible: `name_raw`, `normalized_category`, `risk_level`,
  `recommended_action`, `rationale_short`, `verification_questions`,
  `things_to_verify`, `disclaimer`.
- Result layout easier to scan (summary near top, line-item cards instead of a
  flat table).
- `verification_questions` grouped as "Questions to ask the vendor".
- `things_to_verify` grouped as "Things to verify before approving".
- Sample quote shows 3 visible line items (brake, tyre, other/unspecified
  charges) and the third visibly shows the vague/confusing badge.
- `/analyze` response compatibility preserved; no backend changes required.

## 6. Commands to run

```bash
cd frontend && (npm ci || npm install) && npm run build && npm run lint
uvicorn backend.app:app --host 0.0.0.0 --port 8000
curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}'
```

## 7. Definition of done

- Ticket approved, plan approved, implementation complete within the file scope
  above.
- All acceptance criteria have concrete evidence in the review bundle (exact
  commands, exact output, no placeholders).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-003.
- No secrets committed; no backend files changed; work stays on
  `task/003-quote-understanding-report-ui`.
