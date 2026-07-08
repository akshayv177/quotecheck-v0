# Review Bundle — TASK-003 — Quote-understanding report UI

Branch: `task/003-quote-understanding-report-ui`

## Files changed

```
 M docs/CURRENT_STATE.md
 M frontend/src/App.jsx
?? docs/tickets/TASK-003-quote-understanding-report-ui.md
?? docs/review/REVIEW_BUNDLE__TASK-003-quote-understanding-report-ui.md
```

Stat:

```
 docs/CURRENT_STATE.md |  32 ++++++++++--
 frontend/src/App.jsx  | 133 ++++++++++++++++++++++++++++++--------------------
 2 files changed, 109 insertions(+), 56 deletions(-)
```

No backend files were touched — the backend already returned `explanation` and
`vague_or_confusing` (added in TASK-002); the frontend simply wasn't reading them.

## Design decisions

1. Line items moved from a flat `<table>` to one card per item, so each field gets
   room to breathe: `explanation` is the large/prominent text, `rationale_short` is
   shown smaller and dimmer as secondary risk reasoning, and a metadata line
   (`category · action · confidence`) keeps the previously-tabular fields visible.
2. `RiskPill`'s inline markup was factored into a small `Pill({bg, border, fg,
   label})` primitive (pure refactor, no visual change to existing risk pills), and
   a new `VagueBadge()` built on the same primitive renders "NEEDS CLARIFICATION"
   next to the risk pill whenever `vague_or_confusing` is true.
3. `evidence_needed` (previously unrendered) is now shown as a secondary bullet
   list per card, below the metadata line, per user correction during plan review.
4. "Verification questions" / "Things to verify" `Card` titles were relabeled
   "Questions to ask the vendor" / "Things to verify before approving"; bodies
   unchanged.
5. The Summary card was pulled out of the 2-column grid and placed full-width
   directly above the line items.
6. Default sample `quoteText` was extended with a clause containing "misc" (a
   stub generic-charge keyword) so the app shows all 3 stub items — brake, tyre,
   and "Other/unspecified charges" with the vague badge — on first load with no
   interaction required.
7. `th`/`td` style constants, only used by the removed `<table>`, were deleted as
   dead code.

## Acceptance criteria — evidence

- **`explanation` displayed prominently.** Each line-item card renders
  `item.explanation` as normal-weight, 15px text directly under the header row —
  confirmed present in the built JS bundle (see bundle grep below) and in the live
  `/analyze` response (section 3).
- **`vague_or_confusing` shown as a clear badge.** `VagueBadge()` renders "NEEDS
  CLARIFICATION" (violet pill, consistent with the existing `RiskPill` visual
  style) only when `item.vague_or_confusing` is true — confirmed in the built
  bundle and via the sample response, whose third item has
  `"vague_or_confusing": true`.
- **Existing fields kept visible**: `name_raw` (card header), `normalized_category`
  / `recommended_action` / `confidence` (metadata line), `risk_level` (`RiskPill`),
  `rationale_short` (secondary "Risk reasoning" line), `verification_questions` /
  `things_to_verify` (renamed `Card`s, same list bodies), `disclaimer` (unchanged,
  in the "Run metadata" card) — all confirmed by reading the diff and the bundle
  grep below.
- **Layout easier to scan.** Summary near the top; one card per line item instead
  of a dense table; explanation is the largest text per card, rationale is
  secondary, metadata is a small muted line.
- **"Questions to ask the vendor" / "Things to verify before approving" headers.**
  Confirmed present in the built bundle (grep below).
- **Sample quote shows 3 line items with the vague badge on the third.** Confirmed
  via live `/analyze` call (section 3): brake (red), tyre (yellow), "Other/
  unspecified charges" (yellow, `vague_or_confusing: true`).
- **No full redesign.** Same single-file `App.jsx`, same inline-style approach,
  same `Card` component, no new dependencies, no CSS framework introduced.
- **No price benchmarking added.** No new content or logic related to pricing;
  `overall_summary`/`disclaimer` price-benchmarking language is unchanged
  (backend-owned, untouched).
- **No backend changes.** Confirmed via `git status --short` (section 1) — only
  `frontend/src/App.jsx` and docs changed.
- **`/analyze` compatibility preserved.** `prettyJson`, `copyJson()`, and the raw
  JSON `<pre>` block are untouched; they operate on `result` as a whole. The build
  succeeded and the live `/analyze` call returned 200 with the same top-level
  shape as before (section 3).

## Commands run and exact output

### 1. Git status

```
$ git status --short
 M docs/CURRENT_STATE.md
 M frontend/src/App.jsx
?? docs/tickets/TASK-003-quote-understanding-report-ui.md
?? docs/review/REVIEW_BUNDLE__TASK-003-quote-understanding-report-ui.md
```

### 2. Frontend install, build, lint

```
$ cd frontend && (npm ci || npm install)
added 157 packages, and audited 158 packages in 3s
33 packages are looking for funding
11 vulnerabilities (2 low, 4 moderate, 5 high)   # pre-existing, unrelated to this change

$ npm run build
> frontend@0.0.0 build
> vite build

vite v7.3.1 building client environment for production...
transforming...
✓ 29 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.46 kB │ gzip:  0.29 kB
dist/assets/index-DQ3P1g1z.css    0.91 kB │ gzip:  0.49 kB
dist/assets/index-CGlOBTk8.js   198.76 kB │ gzip: 62.69 kB
✓ built in 800ms

$ npm run lint
> frontend@0.0.0 lint
> eslint .
(no output — zero lint errors/warnings)
```

### 2b. Built bundle contains the new UI strings (static fallback check, see note below)

```
$ grep -o "NEEDS CLARIFICATION" dist/assets/*.js
NEEDS CLARIFICATION
$ grep -o "Questions to ask the vendor" dist/assets/*.js
Questions to ask the vendor
$ grep -o "Things to verify before approving" dist/assets/*.js
Things to verify before approving
$ grep -o "Risk reasoning" dist/assets/*.js
Risk reasoning
$ grep -o "Evidence to ask for" dist/assets/*.js
Evidence to ask for
```

### 3. Backend stub sample (default quote text, run in the pre-existing `quotecheck`
conda env — no `fastapi`/`uvicorn`/`pydantic` on the system `python3`)

```
$ uvicorn backend.app:app --host 0.0.0.0 --port 8000   (background)
$ curl -s http://localhost:8000/health
{"status":"ok"}

$ curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}'
```

Response (200 OK, pretty-printed):

```json
{
    "line_items": [
        {
            "name_raw": "Brake service/ pads (from quote)",
            "normalized_category": "safety_critical",
            "explanation": "Brake pads are the friction material that presses on the rotor to slow the vehicle. A shop typically recommends replacement when pad thickness drops below a safe threshold or the rotor shows wear.",
            "vague_or_confusing": false,
            "recommended_action": "needs_inspection",
            "risk_level": "red",
            "confidence": 0.7,
            "rationale_short": "Braking components are safety-critical. Ask for pad thickness and rotor condition evidence.",
            "price": null,
            "evidence_needed": ["Pad thickness measurement (mm)", "Rotor condition photo", "Reason for replacement"]
        },
        {
            "name_raw": "Tyre replacement (from quote)",
            "normalized_category": "safety_critical",
            "explanation": "Tyres are the vehicle's only contact with the road, so tread depth and condition affect braking, handling, and grip. A shop recommends replacement or rotation to keep wear even and maintain safe tread depth.",
            "vague_or_confusing": false,
            "recommended_action": "ask_for_evidence",
            "risk_level": "yellow",
            "confidence": 0.65,
            "rationale_short": "Tyres affect braking and handling. Ask for tread depth and sidewall condition details.",
            "price": {"amount": 0.0, "currency": "INR"},
            "evidence_needed": ["Tread depth (mm)", "Uneven wear explanation", "Sidewall damage photo (if any)"]
        },
        {
            "name_raw": "Other/unspecified charges (from quote)",
            "normalized_category": "unknown_needs_clarification",
            "explanation": "The quote mentions one or more generically named or un-itemized charges (e.g. misc, labour, service charge, gas top-up). This stub cannot know what they specifically cover without an itemized breakdown from the vendor.",
            "vague_or_confusing": true,
            "recommended_action": "ask_for_evidence",
            "risk_level": "yellow",
            "confidence": 0.4,
            "rationale_short": "Generic or bundled charges are unclear without an itemized breakdown; ask the vendor to itemize them.",
            "price": null,
            "evidence_needed": ["Itemized breakdown of what this charge covers", "Confirm whether this is a fixed fee or time-based labour charge"]
        }
    ],
    "overall_summary": ["...unchanged, 4 items..."],
    "verification_questions": ["...unchanged, 3 items..."],
    "things_to_verify": ["...unchanged, 3 items..."],
    "uncertainty_markers": {"ambiguous_items_present": true, "missing_vehicle_context": true, "needs_mechanic_confirmation": true},
    "refusals": [],
    "disclaimer": "QuoteCheck is a v0 prototype; results may be incomplete or wrong. Not safety advice; verify with a certified mechanic. QuoteCheck explains quotes and suggests questions; it does not verify vendor claims, guarantee fair pricing, or perform price benchmarking.",
    "metadata": {
        "prompt_version": "quotecheck_v0.2",
        "model": "gpt-4o-mini",
        "created_at": "2026-07-08T09:21:12.753194Z",
        "request_id": "61203242-2e8e-42b7-a56f-f9523120f260",
        "latency_ms": 0,
        "schema_valid": true
    }
}
```

Confirms 3 line items (brake/red, tyre/yellow, other-unspecified/yellow) with the
third item's `vague_or_confusing: true`, matching this exact default `quoteText`
now hardcoded in `App.jsx`.

Corresponding JSONL log record (`logs/app_runs.jsonl`, last line):

```json
{
    "event": "quotecheck_analyze",
    "created_at": "2026-07-08T09:21:12.753241Z",
    "request_id": "61203242-2e8e-42b7-a56f-f9523120f260",
    "prompt_version": "quotecheck_v0.2",
    "model": "gpt-4o-mini",
    "latency_ms": 0,
    "schema_valid": true,
    "num_items": 3,
    "risk_counts": {"red": 1, "yellow": 2, "green": 0},
    "uncertainty": {"ambiguous_items_present": true, "missing_vehicle_context": true, "needs_mechanic_confirmation": true},
    "error": null
}
```

Server stopped after this test (`kill` on the `uvicorn` PID).

### 4. Dev server smoke check

```
$ npm run dev -- --host --port 5173   (background)
$ curl -s http://localhost:5173/ | head -5
<!doctype html>
<html lang="en">
  <head>
    <script type="module">import { injectIntoGlobalHook } from "/@react-refresh";
...
```

Confirms the Vite dev server serves the React app shell without error. Dev server
stopped after this check (`kill` on the vite PID).

**Note on browser-driven visual verification**: this sandbox has no root access,
and Playwright's headless Chromium requires OS shared libraries (`libnspr4.so`
etc.) installable only via `sudo apt-get`. `npx playwright install-deps chromium`
failed for lack of a sudo password. Per user's explicit choice when asked, visual
verification (screenshot of the rendered cards/badge in an actual browser) was
**not performed**. In its place: the production build succeeded, ESLint passed,
the dev server serves the app shell, and the built JS bundle was grepped
(section 2b) to confirm the new UI strings ("NEEDS CLARIFICATION", "Questions to
ask the vendor", "Things to verify before approving", "Risk reasoning", "Evidence
to ask for") are actually present in the shipped code, combined with the live
`/analyze` response confirming the data these strings render alongside. This is
static/API-level evidence, not a substitute for an actual rendered screenshot — if
a true visual check is wanted, re-run with
`sudo npx playwright install-deps chromium` available, or open
`http://localhost:5173` in a real browser.

### 5. Secrets grep

```
$ grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' frontend/src/App.jsx docs/CURRENT_STATE.md docs/tickets/TASK-003-quote-understanding-report-ui.md
(no output — no matches; grep exit code 1)
```

## Out-of-scope findings (not fixed, noted per CLAUDE.md rule to stay in scope)

- No live-browser screenshot verification was possible in this sandbox (see
  section 4 note above) — flagged rather than silently skipped.
- `evidence_needed` was previously defined in the schema but never rendered; this
  ticket now renders it (per explicit user correction during plan review), which
  is a small net-new UI surface beyond the ticket's original acceptance-criteria
  list, but was requested directly by the user, not assumed.
- `frontend/src/App.css` remains dead/unused (not imported by `App.jsx`); left
  untouched as out of scope for this ticket.
- Existing npm audit vulnerabilities (11, pre-existing) were not addressed — out
  of scope, unrelated to this change.

## Not committed

Per CLAUDE.md ("Do not commit or push unless the user asks"), no `git add`/`git
commit` was run. All changes are currently unstaged/untracked working-tree edits
on `task/003-quote-understanding-report-ui`.
