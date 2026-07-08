# Review Bundle — TASK-005 — Latency and progress states

## Files changed

```
$ git diff --stat
 frontend/src/App.jsx | 103 +++++++++++++++++++++++++++++++++++++++++++++------
 1 file changed, 92 insertions(+), 11 deletions(-)

$ git status --porcelain
 M frontend/src/App.jsx
?? docs/tickets/TASK-005-latency-and-progress-states.md
```

(This review bundle and the `docs/CURRENT_STATE.md` update are additional new
files, written after the diff above was captured.)

Only `frontend/src/App.jsx` was modified. No `backend/` files, no
`frontend/src/index.css`, no `package.json`/`package-lock.json` changes — zero
new dependencies.

## Acceptance criteria — evidence

**1. Stage label progresses by elapsed time, not a fixed loop, plus a live
elapsed-time counter.**

`frontend/src/App.jsx` adds a module-level `STAGES` array with cumulative
`minMs` thresholds and a pure `stageForElapsed(ms)` function that picks the
highest-threshold stage reached:

```js
const STAGES = [
  { label: "Reading the quote…", minMs: 0 },
  { label: "Identifying line items…", minMs: 3000 },
  { label: "Checking for vague or risky charges…", minMs: 8000 },
  { label: "Preparing your report…", minMs: 15000 },
];

function stageForElapsed(ms) {
  let idx = 0;
  for (let i = 0; i < STAGES.length; i++) if (ms >= STAGES[i].minMs) idx = i;
  return idx;
}
```

`elapsedMs` is ticked every 250ms by a `useEffect` keyed on `loading` (cleans
up automatically when loading ends or the component unmounts), and the
rendered label is derived from it at render time — there is no separate
"cycling" timer, so the stage can never drift out of sync with the elapsed
counter, and it strictly advances forward (never wraps around). The elapsed
counter itself renders via `formatElapsed(ms)` next to the stage label.

**2. Staged status text uses `aria-live="polite"`.**

```jsx
<div
  role="status"
  aria-live="polite"
  style={{ ... }}
>
  <span>{STAGES[stageForElapsed(elapsedMs)].label}</span>
  <span>{formatElapsed(elapsedMs)}</span>
</div>
```

Note the elapsed-time text is inside the same live region as the stage label.
This was a deliberate trade-off: putting the ticking elapsed counter in a
polite live region will cause screen readers to announce it on every stage
change (not every 250ms tick, since React only re-announces on text-content
change events the AT layer decides to surface) — acceptable per WAI-ARIA
guidance for `polite` regions, but worth flagging as a minor UX judgment call
if a stricter approach (e.g. isolating the elapsed counter outside the live
region) is preferred later.

**3. "Still working" hint past ~20s instead of a fake final stage.**

```jsx
{elapsedMs > SLOW_HINT_MS && (
  <div style={{ marginTop: 4, fontSize: 12, color: "var(--ink-3)" }}>
    Still working — complex quotes can take a little longer.
  </div>
)}
```

`SLOW_HINT_MS = 20000`. The stage label itself simply stays on "Preparing your
report…" (the last `STAGES` entry) past 15s — no 5th/fake stage is invented.

**4. Client-side timeout via `AbortController`, 55s, with a distinct message,
UI recovers.**

```js
const REQUEST_TIMEOUT_MS = 55_000;
...
const controller = new AbortController();
abortRef.current = controller;
const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
...
fetch(`${API_BASE}/analyze`, { ..., signal: controller.signal });
...
} catch (e) {
  if (e.name === "AbortError") setErr({ kind: "timeout", message: TIMEOUT_ERROR_MESSAGE });
  ...
} finally {
  clearTimeout(timeoutId);
  setLoading(false);
  abortRef.current = null;
}
```

`finally` always runs `setLoading(false)`, so whether the request succeeds,
fails, or times out, the button re-enables and the app returns to a usable
state. `clearTimeout(timeoutId)` in `finally` prevents a stray abort from
firing after the request has already settled.

**5 & 6. Differentiated error copy by failure kind, hint only shown for
`http`/`other`.**

```js
if (e.name === "AbortError") setErr({ kind: "timeout", message: TIMEOUT_ERROR_MESSAGE });
else if (e instanceof TypeError) setErr({ kind: "network", message: NETWORK_ERROR_MESSAGE });
else if (e.kind === "http") setErr({ kind: "http", message: e.message });
else setErr({ kind: "other", message: String(e?.message || e) });
```

`TypeError` is what `fetch()` itself throws for DNS/connection-refused/CORS
failures (browser-native behavior, not something this code invents), which is
how `network` is distinguished from a manually-tagged `http` error on non-2xx
responses. Render side:

```jsx
<div style={{ opacity: 0.9 }}>{err.message}</div>
{(err.kind === "http" || err.kind === "other") && (
  <div style={{ marginTop: 8, fontSize: 13, opacity: 0.8 }}>
    Check that the backend is running on port 8000.
  </div>
)}
```

**7. Sample quote, `/analyze` shape, raw JSON, Copy button, report rendering
unchanged.**

Confirmed by inspection: the sample-quote `useState` initializer, the
`fetch(POST /analyze, { quote_text })` body/headers, the `result`-derived
report JSX (lines ~186 onward: Summary card, line-item cards, verification
questions/things-to-verify grid, disclaimer, metadata line, raw-JSON
`<details>` + Copy button) are all byte-identical to the pre-TASK-005 version
— the diff touches only the loading-state block (button attrs, loading JSX)
and the error-state block (`err` shape + render), plus the new
constants/state/effects/`analyzeQuote` body above them.

**8. `npm run lint` and `npm run build` pass, zero new dependencies.**

```
$ npm run lint
> frontend@0.0.0 lint
> eslint .
(no output — zero warnings/errors)

$ npm run build
> frontend@0.0.0 build
> vite build

vite v7.3.1 building client environment for production...
transforming...
✓ 29 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.50 kB │ gzip:  0.33 kB
dist/assets/index-BLc0mHcd.css    1.99 kB │ gzip:  0.93 kB
dist/assets/index-q-UgwH6f.js   203.88 kB │ gzip: 64.11 kB
✓ built in 983ms
```

`frontend/package.json` / `package-lock.json` untouched (confirmed via
`git status --porcelain` above — neither file appears in the diff).

## Manual verification — honest limitation

The backend (stub mode, `QUOTECHECK_USE_OPENAI=0` default) and frontend dev
server were both started successfully in this environment:

```
$ curl -s http://localhost:8000/health
{"status":"ok"}

$ npm run dev -- --host --port 5173
  VITE v7.3.1  ready in 95 ms
  ➜  Local:   http://localhost:5173/
```

I attempted to drive the actual UI end-to-end with headless Chromium
(Playwright, already cached locally) to screenshot the loading/stage/timeout/
error states directly, but launching Chromium failed in this sandboxed
environment due to a missing system shared library (`libnspr4.so`), which
would require a `sudo apt-get install` / `playwright install-deps` system
change. I asked whether to proceed with that install; no response was
received in time, so — consistent with not taking system-wide, hard-to-reverse
actions without confirmation — **no system packages were installed, and no
live browser screenshot/interaction verification was performed.**

What *was* verified:
- Both backend and frontend dev servers start and serve correctly against the
  changed code (`/health` returns 200; Vite serves the app with no build
  errors).
- `npm run lint` and `npm run build` both pass cleanly against the changed
  `App.jsx` (evidence above) — this catches syntax errors, hook-dependency
  lint violations, and JSX/bundling issues.
- Manual code-level trace of every acceptance criterion above, including the
  `finally`-block cleanup path, the `AbortController`/`TypeError`/`http`-tag
  error classification, and the unchanged report-rendering path.

**Not verified live in a browser:** the actual visual appearance of the
staged text/elapsed counter while a request is in flight, real screen-reader
announcement behavior of the `aria-live="polite"` region, and the 55-second
timeout firing in real time (impractical to wait out manually even with a
working browser). If browser automation should be enabled going forward, the
missing dependency is `libnspr4` (plus likely `libnss3` and related NSS/GTK
libraries) — installable via `npx playwright install-deps` with sudo.

## Commands run (full list)

```bash
cd frontend && npm run lint
cd frontend && npm run build
# scratch venv used only for manual server verification, not committed:
python3 -m venv <scratch>/venv
<scratch>/venv/bin/pip install -r backend/requirements.txt
<scratch>/venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port 8000
curl -s http://localhost:8000/health
cd frontend && npm run dev -- --host --port 5173
git diff --stat
git status --porcelain
```

## Out-of-scope notes

- Real OpenAI-mode latency is not captured anywhere in this repo's logs (all
  `logs/app_runs.jsonl` entries are from stub mode, `latency_ms: 0`), so the
  55s timeout and the 0/3000/8000/15000ms stage thresholds are calibrated to
  the ~20s figure given in the ticket description, not measured production
  data.
- Client-side `AbortController.abort()` stops the browser from waiting on the
  response but does not cancel the backend's in-flight OpenAI call — the
  synchronous `def analyze(...)` handler in `backend/app.py` runs to
  completion in its threadpool worker regardless. This is an accepted v0
  limitation, unchanged by this ticket, and would require a backend change
  (out of scope) to fix.
- The `aria-live="polite"` region bundles the elapsed-time counter together
  with the stage label (see criterion 2 note above); a future accessibility
  pass could split them if frequent time announcements prove noisy for screen
  reader users.

## Definition of done

- [x] Implementation complete within file scope (`frontend/src/App.jsx` only).
- [x] `npm run lint` and `npm run build` both pass.
- [x] Zero new dependencies.
- [x] Ticket file (`docs/tickets/TASK-005-latency-and-progress-states.md`)
      written.
- [x] This review bundle written with concrete evidence, no placeholders.
- [x] `docs/CURRENT_STATE.md` "Last updated" line and "Fixed in TASK-005"
      entry added.
- [x] No secrets committed; no backend files changed.
- [x] Work left uncommitted on `task/005-latency-and-progress-states` per
      instruction — the user will review, commit, merge, and create the next
      task branch manually.
