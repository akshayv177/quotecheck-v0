# QC-2A — Deployment readiness

## 1. Goal

Make QuoteCheck safely configurable for a public **Demo-only** deployment by removing
localhost-only assumptions and adding minimal public-runtime boundaries. The intended
first public architecture is:

```
Browser → Vercel frontend → HTTPS → Railway FastAPI backend → QUOTECHECK_USE_OPENAI=0 → Demo analyzer → QuoteCheckResult
```

The first public deployment must **not** require an `OPENAI_API_KEY`. QC-2A establishes:

1. a configurable frontend API base URL;
2. environment-configurable exact CORS origins (no wildcard);
3. a bounded quote-input contract;
4. deployment-safe configuration validation that fails clearly;
5. public Demo-mode configuration that needs no OpenAI key;
6. a production-safe, provider-free `/health`;
7. clear startup/runtime documentation for QC-2B;
8. provider-neutral enough configuration that QC-2B can deploy cleanly to Vercel +
   Railway;
9. no regression in existing Demo / eval / QC-4 reliability behaviour.

**No live deployment is performed in QC-2A** — that is QC-2B.

## 2. Context

QuoteCheck has completed its pre-deployment hardening (QC-1A/1B public + contract
alignment, QC-3A/3B/3C independent eval + Demo contract alignment to 24/27, QC-4
reliability + explicit OpenAI failure handling). The remaining blockers to a safe
public deploy were all localhost assumptions:

- `frontend/src/App.jsx` hardcoded `const API_BASE = "http://localhost:8000"` as the
  only mechanism; no `import.meta.env`, no `frontend/.env*` files.
- `backend/app.py` hardcoded `CORSMiddleware` `allow_origins` to two localhost:5173
  origins; no env var.
- `AnalyzeRequest.quote_text` had `min_length=1` only — no upper bound anywhere.
- `load_dotenv("backend/.env")` and the default `QUOTECHECK_LOG_PATH` were CWD-relative.
- No deployment documentation; documented start command hardcoded `--port 8000` and
  `--reload`.
- `frontend/.gitignore` was a corrupted copy of the root ignore file.

Already correct and preserved: `backend/core/config.py` performs **no** startup key
validation, so Demo mode already starts with `OPENAI_API_KEY` absent; `/health` is
already `{"status": "ok"}` with no provider call.

## 3. Strict file scope

Created:

- `frontend/.env.example`
- `eval/tests/test_deployment_readiness.py`
- `docs/tickets/QC-2A-deployment-readiness.md`
- `docs/review/REVIEW_BUNDLE__QC-2A-deployment-readiness.md`

Edited:

- `backend/core/config.py` — `QUOTECHECK_ALLOWED_ORIGINS`, parsed/validated with
  `urllib.parse.urlsplit` into `ALLOWED_ORIGINS` (stdlib only, no dependency).
- `backend/core/schema.py` — `MAX_QUOTE_TEXT_CHARS = 12_000`; `max_length` on
  `AnalyzeRequest.quote_text`.
- `backend/app.py` — CORS wired to `ALLOWED_ORIGINS`; absolute `backend/.env` path; a
  `RequestValidationError` handler returning `{"detail": {"code": "invalid_request",
  …}}` (HTTP 422).
- `backend/.env.example` — `QUOTECHECK_ALLOWED_ORIGINS`, `PORT` note.
- `frontend/src/App.jsx` — `API_BASE` from `import.meta.env.VITE_API_BASE_URL`
  (trimmed, trailing slash stripped) with `http://localhost:8000` fallback;
  `MAX_QUOTE_CHARS`; textarea `maxLength` + a small character counter; the two former
  hardcoded URL strings now interpolate `API_BASE`.
- `frontend/src/index.css` — one `.qc-input-card__count` rule.
- `frontend/.gitignore` — replaced with a minimal correct Node/Vite ignore (keeps
  `!.env.example` tracked). *Scope amendment agreed at plan review.*
- `README.md` — "Deploying the public Demo" section, `VITE_API_BASE_URL` in the
  frontend quickstart, 12,000-char cap + `invalid_request` in the API section, Node
  version correction, Limitations + Roadmap updates, repo-structure line.
- `docs/CURRENT_STATE.md` — "Last updated" line, architecture bullets, deployment
  start command, `### Added in QC-2A`, gap updates.

## 4. Out of scope

Public OpenAI mode; auth / accounts / API quotas; persistent DB; public LLM spend;
OCR/PDF upload; RAG; rate-limiting framework; Redis; queue/job system; deployment
monitoring vendor; custom domain; analytics; CDN tuning; frontend redesign; Docker;
generic configuration framework; secrets-manager integration; committed platform
manifests (`Procfile` / `railway.json` / `vercel.json`); a new testing framework; new
runtime dependencies; **any live deployment or URL verification** (QC-2B). Protected
and untouched: `eval/cases/**`, `eval/termsets.json`, `eval/rubric.md`,
`eval/graders.py`, `eval/corpus.py`, `eval/run_eval.py`, `backend/core/stub_analyzer.py`,
`backend/core/openai_analyzer.py` reliability semantics, `backend/core/errors.py`
taxonomy, `backend/core/prompt.py`, committed eval baselines, `SPEC.md`,
`backend/requirements.txt`.

## 5. Acceptance criteria

1. Frontend API base URL is configurable for production.
2. Local frontend development still works without special setup.
3. Backend CORS allowed origins are environment-configurable.
4. Public deployment does not require wildcard CORS.
5. Allowed / disallowed origin behaviour is tested.
6. Quote input has a documented server-side maximum length.
7. Normal realistic quotes fit comfortably within that bound.
8. Oversized input is rejected before analysis.
9. Public Demo backend starts with no `OPENAI_API_KEY`.
10. Demo `/analyze` works without OpenAI configuration.
11. Demo metadata provenance remains `quotecheck-demo-analyzer`.
12. `/health` requires no provider / network call.
13. Backend startup command is deployment-safe and documented.
14. Cwd / path assumptions are inspected (absolute `backend/.env` path; log dir
    auto-created; ephemeral logging documented).
15. Local logging behaviour survives an ephemeral filesystem without overstating
    durability.
16. Frontend exposes no secret configuration.
17. Public Demo configuration explicitly sets `QUOTECHECK_USE_OPENAI=0`.
18. Public Demo documentation explicitly omits `OPENAI_API_KEY`.
19. OpenAI mode remains available for explicit local use.
20. Existing QC-4 reliability behaviour remains intact.
21. Demo eval remains 27/27 schema-valid and 24/27 deterministic-pass.
22. Eval corpus / graders remain unchanged.
23. Demo analyzer semantics remain unchanged.
24. Frontend build / lint pass.
25. Deployment-readiness tests pass.
26. Clean local Demo startup with the key absent is verified.
27. Allowed and disallowed CORS preflight behaviour is verified.
28. No live deployment is performed.
29. No unnecessary dependency is introduced.
30. Nothing committed until user review.

## 6. Commands to run

```bash
conda run -n quotecheck python -m compileall backend eval
conda run -n quotecheck python -m unittest discover -s eval/tests -p 'test_*.py' -v
conda run -n quotecheck python -m eval.run_eval --validate-only
conda run -n quotecheck python -m eval.run_eval --mode demo          # 27/27 schema, 24/27 deterministic
cd frontend && npm ci && npm run build && npm run lint
# single-process Demo smoke (key stripped): /health, /analyze, allowed + disallowed
# preflight, 12,001-char rejection, 12,000-char accept — see review bundle §15/§16
git diff --check
git diff -- eval/cases eval/termsets.json eval/rubric.md eval/graders.py \
  backend/core/stub_analyzer.py backend/core/prompt.py                # empty
git status --short && git diff --stat
```

## 7. Definition of done

- All commands above run with real output recorded in the review bundle.
- `--mode demo` is exactly 27/27 schema-valid and 24/27 deterministic-pass; no new
  baseline committed (behaviour unchanged); transient run artifacts deleted.
- New `eval/tests/test_deployment_readiness.py` passes with zero network / paid calls;
  full suite 144 tests OK.
- `git diff` for the protected eval + prompt + stub files is empty.
- Clean local Demo startup with `OPENAI_API_KEY` absent verified; allowed vs
  disallowed CORS preflight verified.
- `frontend/npm run build` and `npm run lint` pass; built bundle carries no secret.
- Review bundle written; `docs/CURRENT_STATE.md` and `README.md` updated truthfully.
- No live deployment. Nothing committed.
