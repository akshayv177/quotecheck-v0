# Review bundle — QC-2B Public deployment

## 1. Ticket / milestone

`docs/tickets/QC-2B-public-deployment.md`. Deployment milestone: take the
deployment-ready repository from QC-2A and deploy QuoteCheck publicly end to end
(Vercel frontend + Railway FastAPI backend + deterministic Demo analyzer), then close
the task with truthful, inspectable evidence.

Branch: `task/QC-2B-closeout`. **Nothing committed. Nothing merged. QC-5 not started.**

The build manifest this task required (`railpack.json`) already landed on `main` via
the merged `task/QC-2B-public-deployment` branch (commits `576fdaa`, `e49561a`). This
closeout adds the ticket, this review bundle, and documentation truth-maintenance, and
re-runs the public verification.

## 2. Scope summary

- Documented the live public deployment: frontend
  `https://quotecheck-frontend.vercel.app`, backend
  `https://quotecheck-v0-production.up.railway.app`.
- Re-verified the public endpoints live this pass: `/health`, `/analyze` (Demo
  analyzer, schema-valid), allowed-origin CORS preflight, disallowed-origin CORS
  preflight, frontend reachability.
- Recorded the Railpack detection failure, the minimal `railpack.json` response, the
  `deployOutputs` schema mismatch, and its fix — with commit hashes and the
  before/after manifest.
- README "Deploying the public Demo" section rewritten to "Public demo deployment"
  with live URLs, the Demo-path rationale, the Railpack explanation, and a
  configuration-vs-evidence split; matching edits to Limitations, Roadmap, and the
  repo tree.
- `docs/CURRENT_STATE.md`: "Last updated" → `2026-08-31 (QC-2B)`; new
  `### Added in QC-2B` block; deployment Gaps bullet rewritten; QC-5 named as next.
- `frontend/.gitignore`: `.vercel` added (local Vercel CLI linkage metadata).
- **No** application / frontend-source / backend / `railpack.json` / dependency /
  schema / prompt / eval change in this closeout.

## 3. Files changed

Created:

- `docs/tickets/QC-2B-public-deployment.md`
- `docs/review/REVIEW_BUNDLE__QC-2B-public-deployment.md` (this file)

Edited:

| File | Change |
|------|--------|
| `README.md` | "Deploying the public Demo" → "Public demo deployment": live URL table, Demo-analyzer rationale, `railpack.json` explanation, config-vs-observed-evidence wording, exact-origin CORS note. Limitations deployment bullet, Roadmap item 1, and the repo-structure tree updated for truth-maintenance. |
| `docs/CURRENT_STATE.md` | "Last updated" line; `### Added in QC-2B` block (before `### Added in QC-2A`); deployment Gaps bullet; deployment-start note references `railpack.json` + the README "Public demo deployment" section. |
| `frontend/.gitignore` | `+ .vercel` (one line) — keeps local Vercel CLI linkage metadata out of Git. |

Already on `main`, shown here for provenance only (not in this closeout's diff):

| Commit | Change |
|--------|--------|
| `576fdaa` `chore: configure Railway Railpack build` | adds `railpack.json` (20 lines) |
| `e49561a` `fix: use Railpack deploy output filter` | `deployOutputs` string → `{"include": [".venv"]}` filter object |

## 4. Deployment / debugging history

Ordered narrative, preserved because it is legitimate deployment evidence.

1. **Railpack could not detect a Python app from the repo root.** Railpack 0.38.0
   failed before build. The repo's runtime/import contract is repo-root based
   (`backend.app:app`, `backend.core.*`); the app is at `backend/app.py`, requirements
   at `backend/requirements.txt`, and there is no root `requirements.txt` /
   `pyproject.toml`. Repointing Railway's root at `/backend` would break the validated
   repo-root import contract.
2. **Minimal manifest, not a restructure.** A root `railpack.json` was added
   (`576fdaa`) instead of moving requirements, adding Docker, or adding a Procfile.
3. **First manifest hit a Railpack schema mismatch:**
   `json: cannot unmarshal string into Go struct field
   Config.steps.deployOutputs of type plan.Filter`.
   `deployOutputs` was a bare string `[".venv"]`.
4. **Fix (`e49561a`):** `deployOutputs` repaired to a filter object:

   ```jsonc
   // before
   "deployOutputs": [".venv"]
   // after
   "deployOutputs": [ { "include": [".venv"] } ]
   ```

   The final manifest forces `provider: python`, pins `python: "3.11"`, stages
   `backend/requirements.txt` → `requirements.txt`, `python -m venv /app/.venv`,
   `/app/.venv/bin/pip install --no-cache-dir -r requirements.txt`, carries `.venv`
   into the deploy image, and starts
   `/app/.venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port $PORT`.
5. **Railway runtime started.** Logs (human-observed during deployment):
   `Application startup complete.` / `Uvicorn running on http://0.0.0.0:8080`.
6. **Public backend verified.** `POST /analyze` with
   `{"quote_text":"AC service charge ₹1500. Materials as required."}` returned a full
   `QuoteCheckResult` with `metadata.model = "quotecheck-demo-analyzer"`,
   `metadata.prompt_version = "quotecheck_v0.4"`, `metadata.schema_valid = true`.
7. **Vercel frontend deployed** from `frontend/` via the Vercel CLI. Project
   `quotecheck-frontend`; production alias `https://quotecheck-frontend.vercel.app`;
   production build variable
   `VITE_API_BASE_URL=https://quotecheck-v0-production.up.railway.app`.
8. **CORS set to the exact stable frontend origin**
   (`https://quotecheck-frontend.vercel.app`). Brief propagation/restart window where
   the preflight still accepted `localhost` and rejected the Vercel origin; after
   Railway applied the updated environment the Vercel origin succeeded.
9. **Final manual browser test** (human-observed): production frontend loaded, quote
   submitted, Railway backend reached, QuoteCheck analysis rendered in the browser.

## 5. Deployment URLs

| | URL |
|---|---|
| Live frontend | https://quotecheck-frontend.vercel.app |
| Public API backend | https://quotecheck-v0-production.up.railway.app |
| Health | https://quotecheck-v0-production.up.railway.app/health |
| Analyze | `POST https://quotecheck-v0-production.up.railway.app/analyze` |

Architecture:

```
Vercel React/Vite frontend
  → HTTPS
  → Railway FastAPI backend
  → deterministic QuoteCheck Demo analyzer
  → schema-valid QuoteCheckResult
```

## 6. Configuration vs. observed evidence

Kept deliberately separate throughout the docs and this bundle:

- **Configuration (setup guidance).** The hosted Demo *should be* / *is* configured
  with `QUOTECHECK_USE_OPENAI=0`, `QUOTECHECK_ALLOWED_ORIGINS` = the exact Vercel
  origin, `OPENAI_API_KEY` not set, `PORT` supplied by Railway,
  `VITE_API_BASE_URL` = the Railway URL at frontend build time.
- **Observed runtime evidence.** The Railway production variable state was **not**
  inspected from this environment. No doc claims "the Railway env contains no
  `OPENAI_API_KEY`" as an observed fact. What the live checks prove is that the
  observed public `/analyze` request executed through QuoteCheck's deterministic Demo
  analyzer: `metadata.model == "quotecheck-demo-analyzer"`,
  `metadata.prompt_version == "quotecheck_v0.4"`, `metadata.schema_valid == true`,
  HTTP 200. OpenAI mode is not the path observed in the public deployment.

## 7. Commands run (this closeout pass)

```bash
# live verification
curl -fsS https://quotecheck-v0-production.up.railway.app/health
curl -fsS -X POST https://quotecheck-v0-production.up.railway.app/analyze \
  -H 'Content-Type: application/json' \
  -d '{"quote_text":"AC service charge ₹1500. Materials as required."}'
curl -i -X OPTIONS https://quotecheck-v0-production.up.railway.app/analyze \
  -H 'Origin: https://quotecheck-frontend.vercel.app' \
  -H 'Access-Control-Request-Method: POST'
curl -i -X OPTIONS https://quotecheck-v0-production.up.railway.app/analyze \
  -H 'Origin: https://example.com' \
  -H 'Access-Control-Request-Method: POST'
curl -I https://quotecheck-frontend.vercel.app

# scope integrity
git diff -- backend frontend/src eval examples railpack.json \
  backend/requirements.txt SPEC.md CLAUDE.md          # expected: empty
git diff -- frontend/.gitignore
git status --short
git diff --stat
```

## 8. Exact verification results

All five checks executed live on 2026-08-31 from the closeout environment.

### 8.1 `GET /health` — machine-verified

```
$ curl -fsS https://quotecheck-v0-production.up.railway.app/health
{"status":"ok"}
```

### 8.2 `POST /analyze` — machine-verified (Demo analyzer)

```
$ curl -fsS -X POST https://quotecheck-v0-production.up.railway.app/analyze \
    -H 'Content-Type: application/json' \
    -d '{"quote_text":"AC service charge ₹1500. Materials as required."}'
HTTP 200

metadata:
{
  "model":         "quotecheck-demo-analyzer",
  "prompt_version":"quotecheck_v0.4",
  "schema_valid":  true,
  "request_id":    "a7ac4984-88e4-49e1-a8d3-9647e159be3a",
  "created_at":    "2026-08-31T11:31:08.262459Z",
  "latency_ms":    0
}

body shape: line_items[1] ("Other/unspecified charges (from quote)",
risk_level=yellow, vague_or_confusing=true), overall_summary, verification_questions,
things_to_verify, uncertainty_markers
{ambiguous_items_present:true, missing_quote_context:true,
 needs_professional_confirmation:false}, refusals, disclaimer, metadata.
```

Assertions: HTTP success ✓ · `metadata.model == "quotecheck-demo-analyzer"` ✓ ·
`metadata.prompt_version == "quotecheck_v0.4"` ✓ · `metadata.schema_valid == true` ✓.
`latency_ms: 0` is consistent with the deterministic Demo analyzer (no provider
round-trip).

### 8.3 `OPTIONS /analyze` — allowed origin — machine-verified

```
$ curl -i -X OPTIONS https://quotecheck-v0-production.up.railway.app/analyze \
    -H 'Origin: https://quotecheck-frontend.vercel.app' \
    -H 'Access-Control-Request-Method: POST'
HTTP/2 200
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-allow-origin: https://quotecheck-frontend.vercel.app
access-control-max-age: 600
vary: Origin
```

Assertion: `access-control-allow-origin: https://quotecheck-frontend.vercel.app` ✓
(exact production origin echoed, not a wildcard).

### 8.4 `OPTIONS /analyze` — disallowed origin — machine-verified

```
$ curl -i -X OPTIONS https://quotecheck-v0-production.up.railway.app/analyze \
    -H 'Origin: https://example.com' \
    -H 'Access-Control-Request-Method: POST'
HTTP/2 400
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
access-control-max-age: 600
vary: Origin
```

Assertion: the untrusted origin receives **no** `access-control-allow-origin` header
(and HTTP 400) ✓ — a browser blocks the cross-origin response. Starlette's
`CORSMiddleware` still emits generic `access-control-allow-methods` / `-max-age` on a
rejected preflight; the security-relevant fact is the absent
`access-control-allow-origin`.

### 8.5 Frontend reachability — machine-verified

```
$ curl -I https://quotecheck-frontend.vercel.app
HTTP/2 200
content-type: text/html; charset=utf-8
server: Vercel
x-vercel-cache: HIT
x-vercel-id: bom1::5xkdc-1788175869366-891fc5348a38
```

Assertion: successful production response from Vercel ✓.

### 8.6 Human-observed (from the deployment session, not re-run this pass)

- Railway startup logs: `Application startup complete.` /
  `Uvicorn running on http://0.0.0.0:8080`.
- Vercel CLI deploy from `frontend/`; production alias assignment.
- Brief CORS propagation window (old origin value still in effect) after the Railway
  environment update, then correct.
- End-to-end browser test: production frontend → submit quote → Railway backend →
  analysis rendered.

## 9. Acceptance-criteria status

| # | Criterion | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Public Vercel frontend URL documented | ✓ | §5; README "Public demo deployment"; CURRENT_STATE QC-2B block |
| 2 | Public Railway backend URL documented | ✓ | §5; README; CURRENT_STATE |
| 3 | `/health` verified live | ✓ | §8.1 — `{"status":"ok"}` |
| 4 | `/analyze` verified via Demo analyzer | ✓ | §8.2 — `metadata.model == quotecheck-demo-analyzer`, HTTP 200 |
| 5 | `schema_valid == true` observed | ✓ | §8.2 |
| 6 | `prompt_version quotecheck_v0.4` observed | ✓ | §8.2 |
| 7 | Exact-production-origin CORS verified | ✓ | §8.3 — `access-control-allow-origin: https://quotecheck-frontend.vercel.app` |
| 8 | Disallowed-origin behaviour checked | ✓ | §8.4 — HTTP 400, no `access-control-allow-origin` |
| 9 | End-to-end browser success recorded | ✓ (human-observed) | §4.9, §8.6 |
| 10 | Railpack detection/config failure and fix recorded | ✓ | §4.1–§4.4; commits `576fdaa`, `e49561a` |
| 11 | README truthfully reflects live status | ✓ | README "Public demo deployment", Limitations, Roadmap |
| 12 | CURRENT_STATE reflects QC-2B complete, QC-5 next | ✓ | CURRENT_STATE `### Added in QC-2B`, Gaps bullet |
| 13 | No product/runtime code changed | ✓ | §11 — `git diff` for `backend/**`, `frontend/src/**`, `eval/**`, `examples/**`, `railpack.json` empty |
| 14 | No dependencies changed | ✓ | `git diff -- backend/requirements.txt` empty; §10 |
| 15 | Review bundle contains actual evidence | ✓ | §8 — real captured output, no placeholders |
| 16 | No un-inspected Railway env state asserted as observed fact | ✓ | §6 — configuration vs. observed-evidence split held in every doc |
| 17 | Nothing committed/merged; QC-5 not started | ✓ | §1; §12 |
| 18 | Frontend reachability confirmed | ✓ | §8.5 |

## 10. Dependency changes

**None.** `backend/requirements.txt` unchanged; `frontend/package.json` /
`package-lock.json` unchanged; no new runtime, build, or dev dependency. `curl` and
`git` are the only tools used for verification. `railpack.json` (already on `main`)
introduces no Python package — it pins the Python runtime and reuses the existing
`backend/requirements.txt`.

## 11. Scope-integrity check

```
$ git diff -- backend frontend/src eval examples railpack.json \
    backend/requirements.txt SPEC.md CLAUDE.md
(empty)

$ git diff -- frontend/.gitignore
@@ -25,3 +25,4 @@ pnpm-debug.log*
 *.njsproj
 *.sln
 *.sw?
+.vercel
```

`SPEC.md` was inspected — it defers to `docs/CURRENT_STATE.md` for current
architecture and explicitly disclaims production-readiness; it contains no false
deployment-state statement, so it was not edited. `docs/PROJECT_STATUS.md` and
`CLAUDE.md` were left untouched (out of scope; see §13).

## 12. Observability / logging notes

- Hosted run logs (`logs/app_runs.jsonl`) are written to the Railway container's
  **local, ephemeral** filesystem. They are not durable and not centralized; a
  redeploy or restart discards them. No database, log drain, or metrics backend is
  configured. Unchanged by this closeout — stated plainly in README and CURRENT_STATE.
- `/health` performs no provider call, reads no secret, and exposes no environment
  internals — appropriate as a Railway liveness probe.
- A logging failure never masks an analysis result (`app._safe_log` wraps every
  `log_app_run` in `try/except`, QC-4) — unchanged.
- No public rate limiting, quota control, or abuse protection is deployed.

## 13. Risks / follow-ups

Real, still-open limitations (kept visible, not fake metrics):

- **The hosted public path is Demo mode.** Every public analysis is the deterministic
  keyword-heuristic Demo analyzer, not model intelligence. It recognizes a small
  fixed keyword set and is not equivalent to OpenAI-mode output.
- **OpenAI mode exists but is not exposed anonymously.** It remains a local-only,
  opt-in capability (`QUOTECHECK_USE_OPENAI=1` + `OPENAI_API_KEY` in an untracked
  `backend/.env`). It is not the path observed in the public deployment. Exposing it
  publicly would require rate limiting, quota control, and abuse protection that do
  not exist.
- **Hosted JSONL logs are ephemeral / non-durable.** No centralized observability.
- **No public rate limiting / quota control** on the Railway backend.
- **QC-5 (final public inspection) still remains** and is the next task. It is not
  started in this closeout.
- **Railway environment variable state was not inspected** from the closeout
  environment. The Demo-path claim rests on live runtime provenance
  (`metadata.model` / `prompt_version` / `schema_valid`), not an environment dump.
- **Out-of-scope docs not touched this pass:** `docs/PROJECT_STATUS.md` may still
  carry pre-QC-2B "no deployment" phrasing; `CLAUDE.md` still says "There is no
  `backend/requirements.txt` yet and no test suite" (stale — the file exists and
  `eval/tests/` is a 144-test suite; already flagged in the QC-2A bundle). Neither is
  in QC-2B's file scope; noted for a future docs pass.
- **CORS propagation.** A configuration change to `QUOTECHECK_ALLOWED_ORIGINS` on
  Railway is not instant — expect a short window where the previous value is still
  served until the environment is applied.

## 14. Explain-It-Back

QuoteCheck is now live on the public internet as a portfolio demo. A visitor loads the
React app at `https://quotecheck-frontend.vercel.app` (hosted on Vercel), pastes a
quote, and clicks Analyze. The browser calls
`https://quotecheck-v0-production.up.railway.app/analyze` (a FastAPI app on Railway),
which runs the pasted text through QuoteCheck's **deterministic Demo analyzer** and
returns a schema-valid `QuoteCheckResult` that the UI renders as a structured report.
No external model is called for hosted requests — that is deliberate, so the public
demo is reproducible and free to run, and so no anonymous visitor can drive paid
inference.

Getting the backend to build on Railway needed one small file. Railpack (Railway's
builder) could not tell this was a Python project from the repository root, because
the app and its `requirements.txt` live in `backend/` and QuoteCheck's imports are
written relative to the repo root, so moving things into `backend/` as the project
root was not an option. A minimal `railpack.json` at the root fixes this: it tells
Railpack to use Python 3.11, install `backend/requirements.txt` into a virtualenv,
keep that virtualenv in the deployed image, and start Uvicorn. The first version of
that file used the wrong shape for one field (`deployOutputs` needs a filter object,
not a bare string) and was corrected in a follow-up commit. Both commits are already
on `main`; this task did not change them.

This closeout pass itself changed only documentation: it added the QC-2B ticket and
this review bundle, updated `README.md` and `docs/CURRENT_STATE.md` to say the demo is
live (with the exact URLs and honest limits), and added `.vercel` to
`frontend/.gitignore` so local Vercel CLI metadata stays out of Git. The five live
checks in §8 were run from this environment and all passed. What is proven is that the
public `/analyze` response came from the Demo analyzer
(`metadata.model == "quotecheck-demo-analyzer"`); the Railway environment's variables
were not inspected, so no document claims more than that. The next task is QC-5, the
final public inspection — not started here, and nothing was committed or merged.
