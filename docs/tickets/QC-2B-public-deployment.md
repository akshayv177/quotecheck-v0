# QC-2B — Public deployment

## 1. Goal

Take the deployment-ready repository from QC-2A and **actually deploy QuoteCheck
publicly**, end to end, then close the task with truthful, inspectable evidence.

Target (and now live) architecture:

```
Browser
  → Vercel React/Vite frontend   https://quotecheck-frontend.vercel.app
  → HTTPS
  → Railway FastAPI backend       https://quotecheck-v0-production.up.railway.app
  → deterministic QuoteCheck Demo analyzer
  → schema-valid QuoteCheckResult
```

The public deployment intentionally exercises the deterministic Demo path rather than
anonymous paid OpenAI inference. OpenAI mode stays an optional repository capability;
it is **not** the path exposed or observed publicly.

QC-2B is a **deploy + verify + document** task. The application/config change it
required (a root `railpack.json`) already landed on `main`; this ticket adds the
missing ticket, review bundle, and doc truth-maintenance, and re-runs the public
verification.

## 2. Context

QC-2A made the repo safely configurable for a public Demo-only deployment
(`VITE_API_BASE_URL`, `QUOTECHECK_ALLOWED_ORIGINS` exact-origin CORS, a
12,000-character `quote_text` cap, clean startup with no OpenAI key, absolute
`backend/.env` path) but deployed nothing and committed no platform manifest.

Deploying to Railway then surfaced a real build-detection problem:

1. Railpack 0.38.0 could not auto-detect a Python app from the repository root. The
   repo's runtime/import contract is root-based (`backend.app:app`,
   `backend.core.*`); the app lives at `backend/app.py` and requirements at
   `backend/requirements.txt`; there is no root `requirements.txt` / `pyproject.toml`.
   Pointing Railway's root at `/backend` would break the validated repo-root import
   contract.
2. Rather than restructure the app, add Docker, add a Procfile, or move requirements,
   a minimal root `railpack.json` was added (commit `576fdaa`).
3. That first manifest hit a Railpack 0.38.0 schema mismatch:
   `json: cannot unmarshal string into Go struct field
   Config.steps.deployOutputs of type plan.Filter`. The `deployOutputs` entry was
   repaired from a bare string to a filter object (commit `e49561a`).
4. The final manifest forces the Python provider, pins Python 3.11, stages
   `backend/requirements.txt` into the install step, builds `/app/.venv`, installs
   requirements, carries `.venv` into the deploy image, and starts
   `/app/.venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port $PORT`.
5. Railway runtime started cleanly (`Application startup complete.` /
   `Uvicorn running on http://0.0.0.0:8080`).
6. The Vercel frontend was deployed from `frontend/` via the Vercel CLI (project
   `quotecheck-frontend`, alias `https://quotecheck-frontend.vercel.app`, build var
   `VITE_API_BASE_URL=https://quotecheck-v0-production.up.railway.app`).
7. `QUOTECHECK_ALLOWED_ORIGINS` on Railway was set to the exact Vercel origin. There
   was a brief propagation/restart window where the preflight still accepted
   `localhost` and rejected the Vercel origin; after Railway applied the updated
   environment the Vercel origin succeeded.

This ticket records that history and re-verifies the live endpoints.

## 3. Strict file scope

Created:

- `docs/tickets/QC-2B-public-deployment.md` (this file)
- `docs/review/REVIEW_BUNDLE__QC-2B-public-deployment.md`

Edited (documentation truth-maintenance only):

- `README.md` — "Deploying the public Demo" section rewritten to reflect the live
  deployment (both URLs, Demo-path rationale, Railpack note), plus the matching
  Limitations / Roadmap lines.
- `docs/CURRENT_STATE.md` — "Last updated" line; new `### Added in QC-2B` block;
  Gaps bullet on public deployment updated.
- `frontend/.gitignore` — adds `.vercel` (local Vercel CLI linkage metadata). This
  is the only change in that file; kept as deployment hygiene so local Vercel
  metadata stays out of Git.

Already on `main` (not part of this closeout's diff): `railpack.json` (`576fdaa`,
`e49561a`).

## 4. Out of scope

Any change to `backend/**`, `frontend/**` (beyond the `.vercel` ignore line),
`eval/**`, `examples/**`, `railpack.json`, `backend/requirements.txt`, `SPEC.md`,
`CLAUDE.md`, `docs/PROJECT_STATUS.md`, or product/runtime/schema/prompt/eval
behaviour. No new dependency. No new deployment file. No custom domain, CDN tuning,
analytics, rate limiting, quota control, durable/centralized logging, or public
OpenAI exposure — all still deliberately absent and still listed as gaps. QC-5 (final
public inspection) is **not** started here.

## 5. Configuration vs. observed evidence (claim discipline)

This ticket, the README, CURRENT_STATE, and the review bundle keep two things
separate:

- **Configuration instructions** — how the hosted Demo *should* be configured
  (`QUOTECHECK_USE_OPENAI=0`, `QUOTECHECK_ALLOWED_ORIGINS` = the exact Vercel origin,
  `OPENAI_API_KEY` deliberately not set). These are setup guidance.
- **Observed runtime evidence** — what the live public endpoints actually returned
  during verification. The Railway production variable state was **not** inspected
  from this environment, so no doc asserts "the Railway env has no `OPENAI_API_KEY`"
  as an observed fact. What is proven: the observed public `/analyze` response
  carried `metadata.model == "quotecheck-demo-analyzer"`,
  `metadata.prompt_version == "quotecheck_v0.4"`, `metadata.schema_valid == true` —
  i.e. the request executed through QuoteCheck's deterministic Demo analyzer, not the
  OpenAI path.

## 6. Acceptance criteria

1. Public Vercel frontend URL documented.
2. Public Railway backend URL documented.
3. `/health` verified live.
4. `/analyze` verified live, served by the Demo analyzer.
5. `metadata.schema_valid == true` observed on the live response.
6. `metadata.prompt_version == "quotecheck_v0.4"` observed on the live response.
7. Exact-production-origin CORS preflight verified
   (`access-control-allow-origin: https://quotecheck-frontend.vercel.app`).
8. Disallowed-origin preflight verified to receive **no** permissive
   `access-control-allow-origin`.
9. End-to-end browser success recorded (human-observed).
10. Railpack detection failure and the `railpack.json` fix (both commits, the schema
    mismatch, the repair) recorded.
11. README truthfully reflects the live status without overclaiming.
12. `docs/CURRENT_STATE.md` marks QC-2B complete and names QC-5 as next.
13. No product/runtime/schema/prompt/eval code changed in this closeout.
14. No dependency changed.
15. Review bundle contains actual evidence, not placeholders.
16. No doc asserts un-inspected Railway environment-variable state as observed fact.
17. Nothing committed or merged; QC-5 not started.

## 7. Commands to run (live verification)

```bash
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

git diff -- backend frontend/src eval examples railpack.json \
  backend/requirements.txt SPEC.md CLAUDE.md    # expected: empty
git status --short && git diff --stat
```

## 8. Definition of done

- All five live checks run this pass with real output recorded in the review bundle.
- Railpack deployment/debugging history recorded with both commit hashes and the
  before/after manifest.
- README + CURRENT_STATE updated truthfully; QC-2B marked complete, QC-5 named next.
- `git diff` for `backend/**`, `frontend/src/**`, `eval/**`, `examples/**`,
  `railpack.json`, `backend/requirements.txt`, `SPEC.md`, `CLAUDE.md` is empty.
- `frontend/.gitignore` diff is exactly the one `.vercel` line.
- No commit, no merge, no QC-5 work.
