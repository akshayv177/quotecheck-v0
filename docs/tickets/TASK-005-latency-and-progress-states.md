# TASK-005 — Latency and progress states

## 1. Goal

Make the ~20-second wait during real-LLM-mode analysis feel understandable and
trustworthy instead of broken, by adding staged progress messaging, an elapsed-
time readout, a client-side request timeout, and error copy differentiated by
failure kind. This is not a full async job system and does not add any real
backend progress signal.

## 2. Context

TASK-004 gave QuoteCheck a product-grade UI, but the `/analyze` request is
still a single blocking call with no visibility into what's happening while it
runs. The only feedback today is a static "Analyzing your quote…" line plus an
indeterminate pulse bar; there is no timeout, so a hung request leaves the
button disabled forever with no explanation, and all errors (network-
unreachable, non-2xx, other) show the same generic message and hint.

The backend (`backend/app.py`, `backend/core/openai_analyzer.py`) makes exactly
one synchronous `client.responses.create()` call in OpenAI mode, with no
streaming and no server-side timeout/retry config. There is no real
intermediate progress signal available without adding streaming or a
multi-step pipeline, both out of scope. Stage messaging is therefore a
client-side sequence derived from elapsed time, not a real backend signal —
UI copy must not claim otherwise.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-005-latency-and-progress-states.md`
- `docs/review/REVIEW_BUNDLE__TASK-005-latency-and-progress-states.md`
- `frontend/src/App.jsx`
- `docs/CURRENT_STATE.md`

Never touch: any `backend/` source file, `frontend/src/index.css` (no visual
changes needed — reuse `.status-pulse` as-is), `package.json` /
`package-lock.json` (no new dependencies), `README.md`, `backend/.env`,
`logs/`, secrets of any kind.

## 4. Out of scope

No backend changes, no streaming/SSE/websockets, no real backend progress
signal, no full async job queue. No price benchmarking, OCR, PDF parsing,
database/session history, or local-model migration. No new dependencies. No UI
redesign beyond the loading/error states described here. No change to the
`/analyze` request/response shape. No disabling of the textarea while loading.
No "last request wins" concurrency bookkeeping (the disabled button already
prevents overlapping requests).

## 5. Acceptance criteria

1. While a request is in flight, the UI shows a stage label that progresses
   based on elapsed time (not a fixed/looping cycle) through: "Reading the
   quote…" → "Identifying line items…" → "Checking for vague or risky
   charges…" → "Preparing your report…", plus a live elapsed-time counter.
2. The staged status text is exposed to assistive technology via
   `aria-live="polite"` (`role="status"`), so screen-reader users get updates
   without needing to poll the DOM.
3. After ~20s+ the UI adds a small non-alarming "still working" hint rather
   than staying silent or fabricating a fake final stage.
4. A request that doesn't resolve is aborted client-side after 55 seconds
   (`AbortController`) and shows a clear, distinct timeout message; the button
   re-enables and the UI remains usable (not stuck on "Analyzing…" forever).
5. A network-unreachable failure (backend not running / CORS/connection
   failure) shows a distinct message from a generic non-2xx HTTP error.
6. Non-2xx HTTP errors and other unexpected errors still surface useful detail
   (status/body) plus the "check the backend is running" hint; that hint is
   not shown for the network-unreachable or timeout messages (which are
   already self-contained).
7. The default sample quote, `/analyze` request/response shape, raw-JSON
   `<details>` block, Copy button, and full report rendering are unchanged
   from TASK-004 behavior.
8. `npm run lint` and `npm run build` both pass with zero new dependencies.

## 6. Commands to run

```bash
cd frontend && npm run lint && npm run build
uvicorn backend.app:app --host 0.0.0.0 --port 8000   # separate terminal, from repo root
cd frontend && npm run dev -- --host                 # manual browser check against the above
```

## 7. Definition of done

- Ticket approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (exact
  commands, exact output, no placeholders); any verification limitation
  (e.g. browser automation unavailable in this environment) stated honestly
  rather than claimed as done.
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-005.
- No secrets committed; no backend files changed; work stays on
  `task/005-latency-and-progress-states`. Not committed — implementation is
  left for the user to review and commit manually.
