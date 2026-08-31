# Review bundle — QC-2A Deployment readiness

## 1. Ticket / phase

`docs/tickets/QC-2A-deployment-readiness.md`. Deployment-readiness phase: make the
repository safely configurable for the first public **Demo-only** deployment
(`Vercel frontend → Railway FastAPI → QUOTECHECK_USE_OPENAI=0 → Demo analyzer`). QC-2B
performs the actual deploy and live smoke verification. **Nothing was deployed here.**

Branch: `task/QC-2A-deployment-readiness`. Nothing committed.

## 2. Scope summary

- Configurable frontend backend URL via `VITE_API_BASE_URL` (localhost fallback).
- Environment-configurable exact CORS origins via `QUOTECHECK_ALLOWED_ORIGINS`
  (wildcard / path / missing-scheme / explicitly-empty all rejected at import).
- Bounded quote input: `MAX_QUOTE_TEXT_CHARS = 12_000`, server-authoritative (422),
  mirrored in the frontend for UX with a source-level consistency test.
- Product-safe validation-error body (`code: "invalid_request"`), no new
  `FailureCategory`.
- Absolute `backend/.env` load path (CWD-independent).
- `/health` left unchanged (already provider-free).
- Deployment documentation (README + CURRENT_STATE); no platform manifest committed.
- `frontend/.gitignore` repaired (was a corrupted copy of the root ignore).
- New stdlib test module; local CORS + clean-start smoke verified.
- Demo eval unchanged: 27/27 schema-valid, 24/27 deterministic. No new baseline.

## 3. Pre-QC-2A deployment blockers

| # | Blocker | Resolution |
|---|---------|-----------|
| 1 | `frontend/src/App.jsx:38` hardcoded `const API_BASE = "http://localhost:8000"` (only mechanism; also in two copy strings) | `import.meta.env.VITE_API_BASE_URL` (trimmed, trailing-slash stripped) with `http://localhost:8000` fallback; both strings interpolate `API_BASE` |
| 2 | `backend/app.py` `CORSMiddleware` `allow_origins` hardcoded to two localhost:5173 origins | `allow_origins=ALLOWED_ORIGINS` from `QUOTECHECK_ALLOWED_ORIGINS` |
| 3 | `AnalyzeRequest.quote_text` had `min_length=1` only — no upper bound anywhere | `max_length=MAX_QUOTE_TEXT_CHARS` (12,000) → FastAPI 422 |
| 4 | `load_dotenv("backend/.env")` CWD-relative | `load_dotenv(Path(__file__).resolve().parent / ".env")` |
| 5 | No deployment docs; `--port 8000` + `--reload` hardcoded in every doc | README "Deploying the public Demo" section with the Railway `--port $PORT` (no `--reload`) command and env matrix |
| 6 | `frontend/.gitignore` a corrupted copy of the root ignore (Python entries + literal `EOF` line) | replaced with a minimal correct Node/Vite ignore, `!.env.example` kept tracked |
| 7 | No `frontend/.env*` template | new `frontend/.env.example` with the `VITE_*` browser-visibility warning |

## 4. Frontend API URL configuration

`frontend/src/App.jsx`:

```js
const API_BASE =
  (import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/+$/, "") ||
  "http://localhost:8000";
```

- Local dev: unset → `http://localhost:8000` (unchanged behaviour; matches every doc
  and the curl examples).
- Deployment: Vercel build env `VITE_API_BASE_URL=<Railway HTTPS URL>`; leading/trailing
  whitespace and trailing slashes are normalized so a fat-fingered dashboard value
  cannot produce `https://x//analyze`.
- `NETWORK_ERROR_MESSAGE` and the `http`/`other` error-card hint now interpolate
  `API_BASE` instead of a hardcoded `http://localhost:8000` / "port 8000".
- Build verification: with the var unset the built bundle contains the literal
  `http://localhost:8000` fallback and no `VITE_API_BASE_URL` identifier; setting the
  var at build time inlines the given origin (checked, then the clean bundle rebuilt).
- `eval/tests/test_deployment_readiness.py::LengthContractConsistencyTests` also
  asserts the source still uses `import.meta.env.VITE_API_BASE_URL` with the localhost
  fallback.

`frontend/.env.example` (new):

```
# Base URL of the QuoteCheck backend the browser calls.
# Unset -> http://localhost:8000 (local dev default).
# For deployment, set this to the Railway backend HTTPS URL, e.g.
#   VITE_API_BASE_URL=https://your-backend.up.railway.app
#
# Every VITE_* variable is embedded into the built JS bundle and is visible to
# anyone using the site. Never put an OpenAI key or any other secret in a
# VITE_* variable.
VITE_API_BASE_URL=http://localhost:8000
```

## 5. Backend CORS configuration

`backend/core/config.py` adds `QUOTECHECK_ALLOWED_ORIGINS` → `ALLOWED_ORIGINS`, parsed
with `urllib.parse.urlsplit` (stdlib; **no new dependency**). `backend/app.py` feeds
`ALLOWED_ORIGINS` to `CORSMiddleware` with `allow_credentials=False`;
`allow_methods`/`allow_headers` stay `["*"]` (the origin list is the security
boundary; method/header breadth is not a public-exposure change).

Parsing rules (`_normalize_origin` / `_parse_allowed_origins`):

| Input | Result |
|-------|--------|
| unset | localhost default `["http://localhost:5173", "http://127.0.0.1:5173"]` |
| `"https://a.app, https://b.app"` | `["https://a.app", "https://b.app"]` (order preserved) |
| `"  https://a.app  "` | `["https://a.app"]` (whitespace trimmed) |
| `"https://a.app/"` | `["https://a.app"]` (lone root slash normalized away) |
| `"http://localhost:5173"` | port preserved |
| `"https://a.app, https://a.app/"` | `["https://a.app"]` (deduped) |
| `"*"` | **RuntimeError** at import |
| `"a.app"` (no scheme) | **RuntimeError** |
| `"ftp://a.app"` | **RuntimeError** |
| `"https://a.app/path"` / `"…/?q=1"` / `"…/#f"` | **RuntimeError** (URL, not an origin) |
| explicitly set but empty / whitespace-only | **RuntimeError** |
| empty **when unset** (caller default) | `[]` (never reached in practice — default string is non-empty) |

## 6. CORS security behaviour

Security invariant: **the public backend grants CORS only to explicitly configured
exact origins.** Verified two ways:

1. **In-process, default origins** (`DefaultCorsBehaviourTests`): `OPTIONS /analyze`
   with `Origin: http://localhost:5173` → `access-control-allow-origin:
   http://localhost:5173`; with `Origin: https://evil.example` → **no**
   `access-control-allow-origin` header.
2. **Subprocess, non-default configured origin** (`ConfiguredCorsIntegrationTests`) —
   because config is import-time state, a clean child process is spawned with
   `QUOTECHECK_ALLOWED_ORIGINS=https://example.vercel.app` and `OPENAI_API_KEY`
   stripped from its environment. It builds a `TestClient` and prints the preflight
   `access-control-allow-origin` for two origins. Asserted: `ALLOWED_ORIGINS ==
   ["https://example.vercel.app"]`; preflight from `https://example.vercel.app` →
   echoed; preflight from `https://other.example` → not granted.

Live smoke (§16) confirms the same against a real Uvicorn process. Wildcard is
impossible: `"*"` raises at import, and `allow_credentials` is `False`.

## 7. Input-size contract and rationale

`backend/core/schema.py`:

```python
MAX_QUOTE_TEXT_CHARS = 12_000
...
quote_text: str = Field(..., min_length=1, max_length=MAX_QUOTE_TEXT_CHARS,
                        alias="quoteText", ...)
```

**Rationale (characters, not tokens):**

| Source | Largest `quote_text` |
|--------|----------------------|
| bundled `examples/*.txt` | 341 chars (`quote_ac_repair.txt`) |
| `eval/cases/**` (27 cases) | 1,571 chars (`CONT-001`, full itemized contractor quotation); mean ~917 |
| chosen cap | **12,000** — ~7.6× the largest corpus case, ~35× the largest bundled example |

12,000 comfortably fits any realistic multi-page pasted service/repair/vendor quote
(materials table + GST + warranty + payment schedule) while rejecting document dumps.
It is an input-size safeguard, **not** complete abuse / request-body protection
(no rate limiting, no body-size middleware — out of scope, still a listed gap).

Enforcement: Pydantic `max_length` → FastAPI `RequestValidationError` → the QC-2A
handler → HTTP 422 `{"detail": {"code": "invalid_request", …}}` **before** any
analyzer runs (`openai_ctor.assert_not_called()` in the over-max test).

`min_length=1` is unchanged: `""` → 422; a whitespace-only string still satisfies
`min_length` and is analyzed (current product contract, deliberately not changed).

Frontend mirror: `frontend/src/App.jsx` `const MAX_QUOTE_CHARS = 12000` + textarea
`maxLength={MAX_QUOTE_CHARS}` + a small `N / 12,000` counter.
`LengthContractConsistencyTests` regex-reads `App.jsx` and asserts
`MAX_QUOTE_CHARS == MAX_QUOTE_TEXT_CHARS` so the two languages cannot silently drift
(same technique as QC-4's `TimeoutBudgetTests`).

## 8. Public Demo configuration

| Setting | Public Demo value |
|---------|-------------------|
| `QUOTECHECK_USE_OPENAI` | `0` |
| `QUOTECHECK_ALLOWED_ORIGINS` | exact Vercel frontend origin |
| `OPENAI_API_KEY` | **unset** (deliberate cost/safety boundary) |
| `PORT` | platform-supplied; consumed as `--port $PORT` |
| `VITE_API_BASE_URL` (frontend build) | Railway backend HTTPS URL |

`backend/core/config.py` performs **no** startup key validation (unchanged). Demo mode
selects `analyze_quote_stub` and never touches `backend.core.openai_analyzer`'s client.
The `openai` package remains a `requirements.txt` dependency (imported at module load,
never invoked, no key needed) — acceptable and not a deploy blocker.

## 9. OpenAI-key-absence proof

`eval/tests/test_deployment_readiness.py::PublicDemoConfigTests` (patches
`backend.core.openai_analyzer.OPENAI_API_KEY = None` and replaces `OpenAI` with a
`MagicMock`; forces Demo mode; redirects the run log to a tempdir):

- `test_health_works_without_openai_key` → `GET /health` == 200 `{"status": "ok"}`.
- `test_analyze_returns_demo_result_without_openai_key` → `POST /analyze` == 200,
  `metadata.model == "quotecheck-demo-analyzer"`.
- `test_openai_client_is_never_constructed_in_demo_mode` → `OpenAI` mock
  `assert_not_called()` after a Demo `/analyze`.

Live confirmation — single Uvicorn process started with `env -u OPENAI_API_KEY
QUOTECHECK_USE_OPENAI=0 QUOTECHECK_ALLOWED_ORIGINS=https://quotecheck-demo.vercel.app`
(§15/§16): `/health` 200, `/analyze` 200 with `metadata.model =
quotecheck-demo-analyzer`, `schema_valid = True`. No network / OpenAI call.

## 10. Health endpoint behaviour

`GET /health` is **unchanged** — `{"status": "ok"}`, HTTP 200, no config read, no
provider call, no analysis, no secrets / env internals / filesystem paths. It is
already an appropriate liveness endpoint for the Demo deployment; the ticket says to
leave an already-appropriate endpoint alone, so no change was made. Railway can point
its health check at `/health` directly.

## 11. Startup / working-directory assumptions

- `backend/app.py` now loads `backend/.env` by an absolute path
  (`Path(__file__).resolve().parent / ".env"`), so launching Uvicorn from any CWD
  behaves like local dev. `override=False` is unchanged, so the eval runner's
  `os.environ["QUOTECHECK_USE_OPENAI"]` still wins over the file.
- `backend` / `backend.core` are PEP 420 namespace packages (no `__init__.py`). They
  resolve when the repo root is the CWD / on `sys.path`. The documented Railway
  command runs `uvicorn backend.app:app` from the repo root (Railway's default build
  context), so this works without adding package files. Documented explicitly; no
  code change.
- `QUOTECHECK_LOG_PATH` default `logs/app_runs.jsonl` stays CWD-relative;
  `run_logger.ensure_parent_dir` already does `os.makedirs(parent, exist_ok=True)`, so
  a missing `logs/` directory is created safely on first write.
- Documented start command (README): `uvicorn backend.app:app --host 0.0.0.0 --port
  $PORT` — **no `--reload`** for the hosted process.

## 12. Logging / filesystem limitations

- A missing log directory is auto-created (`os.makedirs(..., exist_ok=True)`).
- A logging failure never kills analysis: `app._safe_log` wraps every `log_app_run`
  call in `try/except Exception: pass` (QC-4). Re-confirmed by
  `test_openai_reliability.FailureLoggingTests` (unchanged, green).
- README + CURRENT_STATE state plainly: hosted run logs (`logs/app_runs.jsonl`) are
  **local and ephemeral** on the platform filesystem — not durable or centralized
  observability. No database / cloud logging was added (out of scope).

## 13. Environment-variable matrix

| Variable | Local Demo | Public Demo | Local OpenAI | Platform supplied | Browser-visible | Secret |
|---|---|---|---|---|---|---|
| `QUOTECHECK_USE_OPENAI` | optional (`0` default) | **set `0`** | **set `1`** | no | no | no |
| `QUOTECHECK_ALLOWED_ORIGINS` | optional (localhost default) | **required** (Vercel origin) | optional (localhost default) | no | no | no |
| `OPENAI_API_KEY` | not used | **must stay unset** | **required** | no | no (must never be) | **yes** |
| `QUOTECHECK_MODEL` | ignored | ignored | optional (`gpt-4o-mini` default) | no | no | no |
| `QUOTECHECK_OPENAI_TIMEOUT_SECONDS` | ignored | ignored | optional (`30` default) | no | no | no |
| `QUOTECHECK_LOG_PATH` | optional (default, ephemeral) | optional (ephemeral) | optional | no | no | no |
| `PORT` | not used (`--port 8000`) | **consumed** via `--port $PORT` | not used | **yes (Railway)** | no | no |
| `VITE_API_BASE_URL` | optional (localhost default) | **required at build** (Railway URL) | optional (localhost default) | no | **yes (in bundle)** | no |

`QUOTECHECK_ALLOWED_ORIGINS` is a browser-deployment setting, independent of analyzer
mode. `OPENAI_API_KEY` is required only for Local OpenAI and must remain unset for the
public Demo.

## 14. Automated tests

`eval/tests/test_deployment_readiness.py` — new, stdlib `unittest`, **no network / no
paid calls**. 26 tests:

- `AllowedOriginParsingTests` (12): default parse, configured list + order,
  whitespace, trailing-slash normalization, port preserved, `*` rejected,
  missing-scheme rejected, path/query/fragment rejected, non-http scheme rejected,
  explicitly-empty rejected, unset-empty → `[]`, duplicates deduped.
- `DefaultCorsBehaviourTests` (2): allowed vs disallowed preflight via `TestClient`
  against the default-origin app.
- `ConfiguredCorsIntegrationTests` (1): subprocess proof that
  `QUOTECHECK_ALLOWED_ORIGINS=https://example.vercel.app` reaches `CORSMiddleware`;
  a different origin is not granted.
- `QuoteInputContractTests` (6): normal accepted; exactly 12,000 accepted; 12,001
  rejected 422 `invalid_request` + stub not called; `""` rejected; whitespace-only
  still analyzed; malformed JSON → `invalid_request`.
- `PublicDemoConfigTests` (3): `/health` + `/analyze` with key absent;
  OpenAI client never constructed.
- `LengthContractConsistencyTests` (2): frontend `MAX_QUOTE_CHARS` == backend
  `MAX_QUOTE_TEXT_CHARS`; frontend still uses `import.meta.env.VITE_API_BASE_URL` +
  localhost fallback.

Full harness:

```
$ conda run -n quotecheck python -m unittest discover -s eval/tests -p 'test_*.py'
Ran 144 tests in 0.949s
OK
```

(118 pre-QC-2A + 26 new.) QC-4 suite alone: `Ran 42 tests … OK` (AC 20).

## 15. Clean-start smoke test

One Uvicorn process, `OPENAI_API_KEY` stripped, kept alive across every check, then
terminated once:

```
$ env -u OPENAI_API_KEY QUOTECHECK_USE_OPENAI=0 \
    QUOTECHECK_ALLOWED_ORIGINS=https://quotecheck-demo.vercel.app \
    python -m uvicorn backend.app:app --host 127.0.0.1 --port 8771

a) GET /health                     -> {"status":"ok"}                       HTTP 200
b) POST /analyze (Demo quote)      -> metadata.model = quotecheck-demo-analyzer
                                      schema_valid  = True                  HTTP 200
e) POST /analyze  12,001 chars     -> {"detail":{"code":"invalid_request",
                                      "message":"That quote is too long. Please
                                      shorten it to 12,000 characters or fewer
                                      and try again.","retryable":false,
                                      "request_id":"c530556e-…"}}            HTTP 422
f) POST /analyze  12,000 chars     ->                                       HTTP 200
   (server terminated once at the end)
```

No OpenAI / network call was made.

## 16. CORS smoke test

Same process (`QUOTECHECK_ALLOWED_ORIGINS=https://quotecheck-demo.vercel.app`):

```
c) OPTIONS /analyze  Origin: https://quotecheck-demo.vercel.app  (allowed)
   HTTP/1.1 200 OK
   access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
   access-control-max-age: 600
   access-control-allow-origin: https://quotecheck-demo.vercel.app

d) OPTIONS /analyze  Origin: https://not-allowed.example  (disallowed)
   HTTP/1.1 400 Bad Request
   access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
   access-control-max-age: 600
   (no access-control-allow-origin header -> browser blocks the response)
```

Note: Starlette's `CORSMiddleware` answers a disallowed preflight with `400` and still
emits generic `access-control-allow-methods` / `-max-age`, but crucially **omits
`access-control-allow-origin`**, so the browser denies the cross-origin request. This
is the guard against the earlier local 5173/5174 origin-mismatch failure class.

## 17. Demo eval regression

```
$ conda run -n quotecheck python -m eval.run_eval --validate-only
OK — 27 cases, 6 domains, 9 categories, 0 errors.

$ conda run -n quotecheck python -m eval.run_eval --mode demo
27/27 schema-valid; 24/27 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation
(known Demo-mode gaps are retained, not suppressed).
```

Identical to the committed QC-3C baseline (`eval/results/summary_20260829T115912Z.md`).
**No new baseline committed**; the two transient `run_*/summary_*` artifacts this run
produced were deleted. `git status --porcelain eval/results/` is empty.

## 18. Frontend build / lint

```
$ cd frontend && npm ci
$ npm run build
vite v7.3.1 ... ✓ 29 modules transformed.
dist/index.html                   0.44 kB
dist/assets/index-DsGHRHoV.css    8.93 kB
dist/assets/index-BoTkB8Wo.js   202.28 kB
✓ built in 689ms

$ npm run lint
> eslint .
(exit 0, no output)
```

Bundle checks: `grep -riE "sk-[A-Za-z0-9]{16}|OPENAI_API_KEY" dist/` → no matches; the
`http://localhost:8000` fallback is present (production API base comes from
`VITE_API_BASE_URL`, localhost is the dev fallback). `dist/` is gitignored.

## 19. Acceptance-criteria table

| # | Criterion | Evidence |
|---|-----------|----------|
| 1 | Frontend API base URL configurable for production | §4 — `VITE_API_BASE_URL` |
| 2 | Local frontend dev still works without setup | §4 — unset → `http://localhost:8000` |
| 3 | Backend CORS origins environment-configurable | §5 — `QUOTECHECK_ALLOWED_ORIGINS` |
| 4 | Public deployment needs no wildcard CORS | §5/§6 — `"*"` raises at import |
| 5 | Allowed/disallowed origin behaviour tested | §6/§14 — in-process + subprocess + live |
| 6 | Documented server-side max input length | §7 — `MAX_QUOTE_TEXT_CHARS = 12_000`, README API section |
| 7 | Normal realistic quotes fit comfortably | §7 — ~7.6× largest corpus case |
| 8 | Oversized input rejected before analysis | §7/§14 — 422, `assert_not_called()` |
| 9 | Backend starts with no `OPENAI_API_KEY` | §9/§15 |
| 10 | Demo `/analyze` works without OpenAI config | §9/§15 |
| 11 | Demo provenance stays `quotecheck-demo-analyzer` | §9/§15/§17 |
| 12 | `/health` needs no provider/network call | §10 — unchanged `{"status":"ok"}` |
| 13 | Deployment-safe startup command documented | §11 — README "Deploying the public Demo" |
| 14 | Cwd/path assumptions inspected | §11 — absolute `.env` path; namespace-package note; log dir auto-create |
| 15 | Logging survives ephemeral FS without overstating durability | §12 |
| 16 | Frontend exposes no secret config | §4/§18 — `VITE_*` warning; bundle scan |
| 17 | Public Demo sets `QUOTECHECK_USE_OPENAI=0` | §8/§13 — README + `.env.example` |
| 18 | Public Demo docs omit `OPENAI_API_KEY` | §8/§13 — README matrix "do not set" |
| 19 | OpenAI mode still available locally | unchanged `openai_analyzer.py`; README "Demo mode vs. OpenAI mode" |
| 20 | QC-4 reliability behaviour intact | §14 — `test_openai_reliability` 42/42 OK; protected diff empty |
| 21 | Demo eval 27/27 schema-valid, 24/27 deterministic | §17 |
| 22 | Eval corpus/graders unchanged | §22 — protected `git diff` empty |
| 23 | Demo analyzer semantics unchanged | §22 — `stub_analyzer.py` diff empty |
| 24 | Frontend build/lint pass | §18 |
| 25 | Deployment-readiness tests pass | §14 |
| 26 | Clean local Demo startup with key absent verified | §15 |
| 27 | Allowed & disallowed CORS preflight verified | §16 |
| 28 | No live deployment performed | this bundle — no deploy step |
| 29 | No unnecessary dependency | `backend/requirements.txt` diff empty; `urllib`/`subprocess` are stdlib |
| 30 | Nothing committed until user review | §22 — `git status` shows working-tree changes only |

## 20. Remaining deployment gaps (for QC-2B and later)

- No verified public deployment and **no public URL yet** — QC-2B runs the live
  Vercel + Railway deploy and smoke test with real origins/URLs.
- No committed platform manifest (`Procfile` / `railway.json` / `vercel.json`) — QC-2B
  adds the smallest one only if the real workflow needs it. Vercel "Root Directory =
  `frontend`" and Railway repo-root are documented expectations, set in QC-2B's
  dashboards.
- No durable / centralized logging — hosted run logs are local and ephemeral.
- No public rate limiting / quotas / abuse protection.
- Public OpenAI mode intentionally disabled — not exposed anonymously.
- Semantic (Layer B) evaluation remains manual; no CI.
- The 3 known deterministic Demo residuals (`AUTO-004`, `CONT-003`, `HVAC-003`) remain.

Out-of-scope finding: `CLAUDE.md` still says "There is no `backend/requirements.txt`
yet and no test suite" — both are stale (the file exists; `eval/tests/` is a 144-test
stdlib suite). Not touched by QC-2A; noted for a future docs pass.

## 21. Exact commands / results

```
$ conda run -n quotecheck python -m compileall -q backend eval
OK

$ conda run -n quotecheck python -m unittest discover -s eval/tests -p 'test_*.py'
Ran 144 tests in 0.949s
OK

$ conda run -n quotecheck python -m eval.run_eval --validate-only
OK — 27 cases, 6 domains, 9 categories, 0 errors.

$ conda run -n quotecheck python -m eval.run_eval --mode demo
27/27 schema-valid; 24/27 deterministic cases pass.
(exit 1 — known residuals retained; transient artifacts deleted)

$ cd frontend && npm ci && npm run build && npm run lint
vite build ✓ built in 689ms ; eslint . -> exit 0

$ git diff --check
(clean)

$ git diff -- eval/cases eval/termsets.json eval/rubric.md eval/graders.py \
    eval/corpus.py eval/run_eval.py backend/core/stub_analyzer.py \
    backend/core/openai_analyzer.py backend/core/errors.py backend/core/prompt.py \
    backend/requirements.txt eval/results
(empty)
```

## 22. git status / diff stat

```
$ git status --short
 M README.md
 M backend/.env.example
 M backend/app.py
 M backend/core/config.py
 M backend/core/schema.py
 M docs/CURRENT_STATE.md
 M frontend/.gitignore
 M frontend/src/App.jsx
 M frontend/src/index.css
?? docs/review/REVIEW_BUNDLE__QC-2A-deployment-readiness.md
?? docs/tickets/QC-2A-deployment-readiness.md
?? eval/tests/test_deployment_readiness.py
?? frontend/.env.example

$ git diff --stat
 README.md              |  80 +++++++++++++++++++++++++---
 backend/.env.example   |  11 ++++
 backend/app.py         |  58 ++++++++++++++++++---
 backend/core/config.py |  65 +++++++++++++++++++++++
 backend/core/schema.py |  20 +++++++-
 docs/CURRENT_STATE.md  | 136 ++++++++++++++++++++++++++++++++++++++++++-------
 frontend/.gitignore    |  43 ++++------------
 frontend/src/App.jsx   |  22 ++++++--
 frontend/src/index.css |   5 ++
 9 files changed, 372 insertions(+), 68 deletions(-)
```

Protected paths (`eval/cases/**`, `eval/termsets.json`, `eval/rubric.md`,
`eval/graders.py`, `eval/corpus.py`, `eval/run_eval.py`, `backend/core/stub_analyzer.py`,
`backend/core/openai_analyzer.py`, `backend/core/errors.py`, `backend/core/prompt.py`,
`backend/requirements.txt`, committed eval baselines): **no diff.** Nothing committed.
No live deployment. No paid OpenAI inference.
