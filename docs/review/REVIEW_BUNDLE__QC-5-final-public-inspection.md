# QC-5 Final Public Inspection

Ticket: `docs/tickets/QC-5-final-public-inspection.md`
Branch: `task/QC-5-final-public-inspection` (based on `main` @ `c3422e4`).
Nothing committed. This is an inspection report; no finding was repaired.

Inspection performed: 2026-08-31. Live probes and the fresh-clone build were run
the same day; timestamps are in each section.

---

## 1. Executive Verdict

**READY WITH MINOR REPAIRS.**

No P0. The live product works end to end and its observable behaviour matches the
documentation: `/health` and `/analyze` return the schema-valid `QuoteCheckResult`
the docs describe, runtime provenance is honest (`metadata.model =
quotecheck-demo-analyzer`, `prompt_version = quotecheck_v0.4`, `schema_valid =
true`), exact-origin CORS allows the Vercel origin and denies others, all four
malformed-request classes return the documented `invalid_request` 422 envelope,
and unknown paths 404 without a stack trace. Secrets hygiene is clean — no keys in
the repo or the built bundle, `.env` / `logs/` / `.vercel` all correctly ignored,
every example quote is synthetic. A fresh `git clone` of the public GitHub remote
builds and runs from the documented commands on Python 3.10 / Node 24 with no
edits. The committed eval baseline (24/27 deterministic, 27/27 schema-valid) and
the 144-test harness reproduce exactly against current code.

The engineering is real and mostly discoverable: schema-first Pydantic contract,
OpenAI structured-output path with mandatory re-validation, an 8-category bounded
failure taxonomy (max 2 provider calls, explicit timeout, no silent fallback),
per-request JSONL logging, a 27-case eval corpus with a deterministic regression
runner and a separate human semantic rubric, exact-origin CORS, a 12,000-char
input bound, and a live Vercel + Railway deployment driven by a minimal
`railpack.json`.

What holds it back from a clean **READY** is documentation truthfulness, not
behaviour:

- **P1 — `docs/PROJECT_STATUS.md` is stale and under-sells the project.** The
  README links it as the "public-ready vs. still limited" summary, yet it still
  says there is "No automated test suite, eval harness, or CI" and "No verified
  public deployment" — both false since QC-3B/QC-3C and QC-2B. A skeptical reader
  who follows the README's own pointer lands on a document that contradicts the
  README and makes the work look less finished than it is.
- **P2 — `eval/README.md` "Expected Demo-mode behaviour" contradicts itself**
  (claims `ambiguous_items_present` is hardcoded `true` and the 6 `clean_itemized`
  cases fail; the current baseline cited lower in the same file shows them
  passing).
- **P2 — no repository-level CI** despite a substantial automated-verification
  surface, on a now-publicly-deployed project (QC5-09).
- **P2 — housekeeping**: no `docs/tickets/QC-5-*.md` (fixed by this task);
  `docs/design/UI_REDESIGN_PLAN.md` is a stale pre-implementation plan.

All proposed repairs are documentation / config only. None touch application code,
architecture, or dependencies.

---

## 2. Inspection Scope

### 2.1 What was inspected, and how

| Area | Method |
|---|---|
| Root / docs | Full read: `README.md`, `SPEC.md`, `CLAUDE.md`, `docs/CURRENT_STATE.md` (all 1171 lines), `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md`, `docs/design/UI_REDESIGN_PLAN.md`, `railpack.json`, `.gitignore`, `frontend/.gitignore`, `backend/.env.example`, `frontend/.env.example`, `backend/requirements.txt`, `frontend/package.json` |
| Backend | Full read: `backend/app.py`, `backend/core/{schema,config,errors,prompt,openai_analyzer,stub_analyzer,run_logger,schema_export}.py` |
| Frontend | Full read: `frontend/src/{App.jsx,index.css,main.jsx}`, `frontend/index.html`, `frontend/{vite,eslint}.config.js` |
| Eval | Full read: `eval/{README.md,rubric.md,run_eval.py,termsets.json}`, both `eval/results/summary_*.md`, spot reads of `eval/results/run_*.jsonl` |
| Examples | `examples/README.md`, `examples/sample_output.json`, all `examples/*.txt` |
| Git | `status`, `ls-files` (140 tracked), `log`, branch list; public-remote `git clone` + `rev-parse` comparison |
| Grep sweeps | `localhost`, `quotecheck_v0.1/2/3`, `v0 prototype` / `prototype`, `missing_vehicle_context` / `needs_mechanic_confirmation`, `TODO`/`FIXME`/`XXX`/`HACK`, `/home/<user>` paths, `sk-…` / `BEGIN` / `AKIA…` secret patterns, CI-provider config names |
| Fresh clone | `git clone https://github.com/akshayv177/quotecheck-v0` into a temp dir; venv + `pip install -r backend/requirements.txt`; `uvicorn` Demo start; README `/health` + `/analyze` curls; `npm ci` + `npm run build` + `npm run lint`; `python -m eval.run_eval --validate-only` / `--mode demo`; `python -m unittest discover -s eval/tests` |
| Live backend | `curl` probes against `https://quotecheck-v0-production.up.railway.app` |
| Live frontend | `curl` of `https://quotecheck-frontend.vercel.app` HTML + built JS/CSS bundle |

### 2.2 What could not be done

- **In-browser visual / mobile / accessibility inspection** of the live React app
  (no browser automation available and none was introduced). The HTML shell, the
  built JS/CSS, and the backend it talks to were inspected; the rendered report,
  responsive behaviour, loading/error states, and reduced-motion behaviour are
  **human-verification items** (§3.2).
- **Confirming `docs/assets/quotecheck-ui.png` matches the current deployed UI** —
  requires a visual comparison. The screenshot commit (`fae2b1e`) post-dates the
  LUXURY-UI-001/001A redesign, so it is *probably* current, but this was not
  visually verified.
- **OpenAI-mode live behaviour** — out of scope (no key; the public demo does not
  expose paid inference by design). The OpenAI path was inspected by source
  reading only.
- **Railway environment-variable state** — not inspectable from here; runtime
  provenance (`metadata.model`) is the evidence the OpenAI path was not taken, as
  the README itself states.

---

## 3. Live Product Results

### 3.1 Machine-verified (probe run 2026-08-31T13:31Z, `https://quotecheck-v0-production.up.railway.app`)

| Check | Result |
|---|---|
| `GET /health` | `{"status":"ok"}` — HTTP 200 |
| `POST /analyze` sample ("Brake pads… Tyre rotation. Shop supplies / misc…") | HTTP 200; `model=quotecheck-demo-analyzer` `prompt_version=quotecheck_v0.4` `schema_valid=True` `items=3` `vague=1`; markers `{ambiguous_items_present:True, missing_quote_context:False, needs_professional_confirmation:True}`. Body is byte-identical to `examples/sample_output.json` apart from `request_id`/`created_at`/`latency_ms`. |
| `POST /analyze` vague ("see the attached estimate … Approximate total cost as agreed") | HTTP 200; `items=1` `vague=1`; markers `{ambiguous:True, missing_quote_context:True, needs_professional_confirmation:False}` — uncertainty path, no guessing |
| `POST /analyze` clean-itemized (synthetic "1. Cabin air filter - 450 …", bare numbers) | HTTP 200; `items=1` `vague=1` `missing_quote_context:True` — Demo analyzer does **not** recognise this domain (no keyword match; bare `- 450` is not a currency token) and correctly falls to the single "needs clarification" item. Documented Demo limitation, not a defect. |
| `POST /analyze` empty `{"quote_text":""}` | HTTP 422 `{"detail":{"code":"invalid_request","message":"That request wasn't valid. Paste the quote text and try again.","retryable":false,"request_id":"…"}}` |
| `POST /analyze` malformed JSON `{bad` | HTTP 422, same `invalid_request` envelope |
| `POST /analyze` missing field `{}` | HTTP 422, same `invalid_request` envelope |
| `POST /analyze` oversize (~13,000 chars) | HTTP 422 `{"detail":{"code":"invalid_request","message":"That quote is too long. Please shorten it to 12,000 characters or fewer and try again.",…}}` |
| CORS preflight, `Origin: https://quotecheck-frontend.vercel.app` | HTTP 200; `access-control-allow-origin: https://quotecheck-frontend.vercel.app` |
| CORS preflight, `Origin: https://evil.example` | HTTP 400; **no** `access-control-allow-origin` header |
| `GET /` and `GET /nope` | HTTP 404 `{"detail":"Not Found"}` — no stack trace, no internals |
| `GET https://quotecheck-frontend.vercel.app/` | HTTP 200; `<title>QuoteCheck — understand a quote before you approve it</title>`; SPA shell; `strict-transport-security` header present; `server: Vercel` |
| Built JS bundle (`/assets/index-*.js`) | Contains the Railway backend URL and the harmless `http://localhost:8000` dev-fallback literal from `App.jsx`. **No** `sk-…`, `OPENAI_API_KEY`, or other secret. |

All error responses use the same `{"detail":{code,message,retryable,request_id}}`
envelope the README documents; none leak a stack trace, key, provider payload, or
internal filename. `latency_ms` is `0` in every Demo response (the analyzer does no
I/O — documented).

### 3.2 Requires human verification (browser, ~2–5 min)

1. Frontend renders the full report: line-item cards with `explanation` prominent,
   risk pills, "Needs clarification" badge on the misc charge, evidence list,
   "Questions to ask the vendor" / "Things to verify before approving",
   always-visible disclaimer, "Demo mode" badge, collapsed raw-JSON drawer.
2. Empty-textarea state: the "Analyze quote" button is disabled at
   `quoteText.trim().length === 0` (verified in source; not exercised in browser).
3. Loading state (staged labels + elapsed counter + `aria-live`), and the styled
   error card when the backend is unreachable.
4. Responsive layout at ~375px (the `.two-col-grid` collapses at `max-width:720px`
   per `index.css`); no horizontal overflow.
5. `prefers-reduced-motion: reduce` suppresses the report reveal animation.
6. `docs/assets/quotecheck-ui.png` still depicts the current deployed UI.
7. Browser-console cleanliness (a missing favicon request is expected — see
   QC5-06).

---

## 4. Fresh-Clone / Reproducibility Results

Environment: WSL2 Ubuntu, Python 3.10.12, Node v24.14.1, npm 11.11.0.
Target: `git clone https://github.com/akshayv177/quotecheck-v0` into a scratch dir
(not the working copy).

### 4.1 Clone matches the public remote

```
$ git clone --depth 1 https://github.com/akshayv177/quotecheck-v0 qc5-clone
Cloning into 'qc5-clone'... (exit 0)
$ cd qc5-clone && git log --oneline -1 && git ls-files | wc -l
c3422e4 Merge branch 'task/QC-2B-closeout'
140
$ git rev-parse HEAD; git rev-parse main origin/main   # (run in the working repo)
c3422e481c78d5a642dae164bbb65c2614bc7592
c3422e481c78d5a642dae164bbb65c2614bc7592   (main)
c3422e481c78d5a642dae164bbb65c2614bc7592   (origin/main)
```

The public GitHub `HEAD` equals local `main` / `origin/main`. 140 tracked files.
This is the **first** verification against a true public clone — TASK-009 only ever
tested an `rsync` copy of the working tree and flagged the real-clone check as an
open follow-up.

### 4.2 Backend (README "Try it in under a minute")

```
$ python3 -m venv .venv && . .venv/bin/activate
$ pip install -r backend/requirements.txt          # exit 0
$ pip freeze | grep -iE '^(fastapi|uvicorn|pydantic|openai|python-dotenv)=='
fastapi==0.128.6
openai==2.24.0
pydantic==2.12.5
python-dotenv==1.2.1
uvicorn==0.40.0                                     # exact pin match
$ python -c "from backend.app import app; print(app.title, app.version)"
QuoteCheck API 0.1.0                                # import OK (namespace packages; no backend/__init__.py needed)

$ QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8777
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8777

$ curl -s http://127.0.0.1:8777/health
{"status":"ok"}                                     # HTTP 200

$ curl -s -X POST http://127.0.0.1:8777/analyze -H "Content-Type: application/json" \
    -d "$(python3 -c 'import json; print(json.dumps({"quote_text": open("examples/quote_ac_repair.txt").read()}))')"
# -> model: quotecheck-demo-analyzer | prompt_version: quotecheck_v0.4 | schema_valid: True | line_items: 1
```

The exact README §1 commands work with no edits. `QUOTECHECK_USE_OPENAI=0` is the
default anyway; no `backend/.env` was created; the OpenAI client was never
constructed.

### 4.3 Frontend

```
$ cd frontend && npm ci                             # exit 0
# npm audit reports 12 vulnerabilities (2 low, 1 moderate, 9 high) — all in the
# Vite/ESLint build toolchain (babel, esbuild, rollup, postcss, nanoid, vite,
# minimatch, brace-expansion, js-yaml, flatted, ajv, picomatch). None in the
# runtime tree (react, react-dom). "fix available via npm audit fix" for all.
$ npm run build
vite v7.3.1 ... ✓ 29 modules transformed.
dist/assets/index-DsGHRHoV.css   8.93 kB
dist/assets/index-*.js         202.28 kB
✓ built in 679ms                                    # exit 0
$ npm run lint                                      # eslint . — exit 0, no findings
```

`dist/` also contains the default `vite.svg` (still present in `frontend/public/`),
though `index.html` no longer references it — harmless leftover (see QC5-06).

### 4.4 Eval + harness (run in the clone, artifacts written to scratch)

```
$ python -m eval.run_eval --validate-only
[1] JSON parse            : 27/27 case files parsed
[2] case_id uniqueness    : 27 unique / 27 cases
[5] corpus size           : 27 (required 24-30)
[6] REG-001 / REG-002     : 1 / 1 occurrence(s)
OK — 27 cases, 6 domains, 9 categories, 0 errors.        # exit 0

$ python -m eval.run_eval --mode demo --results-dir <scratch>
27/27 schema-valid; 24/27 deterministic cases pass.
Exit non-zero: ... known Demo-mode gaps are retained, not suppressed.   # exit 1 (by design)
# Overall results + failed-case set (AUTO-004, CONT-003, HVAC-003) are IDENTICAL
# to the committed QC-3C baseline eval/results/summary_20260829T115912Z.md.

$ python -m unittest discover -s eval/tests -p 'test_*.py'
Ran 144 tests in 0.782s
OK                                                       # exit 0
```

The committed eval baseline and the harness are **not stale** — they reproduce
exactly against current code. The clone's `eval/results/` was untouched.

### 4.5 Reproducibility verdict

The documented quickstart is accurate and complete for a stranger with Python
3.10+ and Node 20.19+. The only rough edge is the `npm audit` output (dev-toolchain
advisories, §10 / QC5-06).

---

## 5. Repository Truthfulness / Consistency

### 5.1 Accurate / consistent (checked, no issue)

- `README.md` architecture, API, "OpenAI mode", "Reliability (QC-4)", "Demo mode",
  and "Public demo deployment" sections all match the source and the live API
  behaviour. The `/analyze` failure envelope, the 8 `code` values, the
  `PROMPT_VERSION` string, the "max 2 provider calls" bound, the 12,000-char cap,
  the exact-origin CORS description, and the `railpack.json` explanation are all
  correct.
- `README.md` "What a report looks like" JSON excerpt matches the live Demo brake
  item exactly.
- `SPEC.md` scope / non-goals / "current scope" are consistent with the code and
  with `docs/CURRENT_STATE.md`.
- `docs/CURRENT_STATE.md` ("Last updated: 2026-08-31 (QC-2B)") is a dense but
  accurate technical baseline + per-ticket changelog. Its "Gaps" section is
  honest, including the 3 residual Demo eval limitations.
- `examples/*.json` are current (`prompt_version: quotecheck_v0.4`,
  `model: quotecheck-demo-analyzer`); `examples/sample_output.json` reproduces from
  the live API.
- `backend/.env.example` / `frontend/.env.example` are accurate and carry the
  "VITE_* is browser-visible, never a secret" warning.
- All `v0 prototype` / `quotecheck_v0.2` / `missing_vehicle_context` grep hits are
  confined to `docs/CURRENT_STATE.md` historical `### Fixed in …` blocks,
  `docs/review/**` (frozen per-ticket records), `docs/tickets/**`, and
  `docs/design/UI_REDESIGN_PLAN.md`. **None** in `README.md`, `SPEC.md`, live code
  output, or the live API. `eval/README.md` and `eval/cases/REG-001` reference
  `missing_vehicle_context` correctly (as the *deleted* field the regression case
  guards against).
- No `TODO` / `FIXME` / `XXX` / `HACK` anywhere in tracked files.
- `README.md` Roadmap already lists "QC-5 final public inspection" as open.

### 5.2 Findings

- **QC5-01 (P1)** — `docs/PROJECT_STATUS.md` stale; see §12.
- **QC5-02 (P2)** — `eval/README.md` self-contradiction; see §12.
- **QC5-04 (P2)** — `docs/design/UI_REDESIGN_PLAN.md` stale; see §12.
- **QC5-07 (P3)** — "v0" / "(v0)" left in backend + frontend module docstrings
  (`backend/app.py`, `backend/core/{schema,config,prompt,stub_analyzer}.py`,
  `App.jsx` header comment) after QC-1A removed "v0" product framing from public
  docs; `App.jsx` `TIMEOUT_ERROR_MESSAGE` says "AI mode" rather than "OpenAI
  mode". Cosmetic, internal.
- **QC5-08 (P3)** — `docs/CURRENT_STATE.md` is 1171 lines with the current-state
  section and the changelog undifferentiated for a first-time reader.

---

## 6. Public Reader Experience

Answers to the Phase-2 fresh-reader questions:

| # | Question | Verdict |
|---|---|---|
| 1 | Understand what QuoteCheck does in ~30s? | **Yes.** README title + first paragraph + "What it is, who it helps, why it exists". |
| 2 | Product boundary obvious? | **Yes.** "What QuoteCheck does not do" (no benchmarking / no fairness / no vendor-trust / no external verification) is in the README intro and in `SPEC.md` non-goals. |
| 3 | Clear what the hosted demo does / does not do? | **Yes.** "Public demo deployment" section is explicit: deterministic Demo analyzer, no external model call, no scale/uptime/rate-limiting/accounts. |
| 4 | Obvious that public hosting = Demo analyzer, OpenAI = optional local capability? | **Yes** in the README; **undermined** by `docs/PROJECT_STATUS.md` which still says "No verified public deployment" (QC5-01). |
| 5 | Unsupported claims avoided? | **Yes** in README/SPEC/CURRENT_STATE (see §11). |
| 6 | Architecture / eval / reliability / observability evidence findable without spelunking? | **Mostly.** README has dedicated Architecture, "Reliability (QC-4)", and Evaluation subsections and links `eval/README.md`. The debugging/regression story lives mostly in `docs/review/**`. `docs/PROJECT_STATUS.md` actively points the wrong way (QC5-01). |
| 7 | Quickstart accurate? | **Yes** — verified end to end (§4). |
| 8 | Fresh backend setup works from documented commands? | **Yes** (§4.2). |
| 9 | Fresh frontend setup works? | **Yes** (§4.3), modulo `npm audit` noise. |
| 10 | Env vars clearly documented? | **Yes** — `backend/.env.example`, `frontend/.env.example`, README env matrix, `docs/CURRENT_STATE.md` config section. |
| 11 | Deployment instructions truthful / understandable? | **Yes** — README "How it is wired" + `railpack.json` match reality; the manifest's rationale is spelled out. |
| 12 | Internal build-process docs overwhelming? | **Partly.** `docs/CURRENT_STATE.md` (1171 lines) and the 24 review bundles are thorough but heavy; they are clearly labelled and not forced on the reader. `docs/design/UI_REDESIGN_PLAN.md` is stale internal planning (QC5-04). |
| 13 | Feels like an internal scratch project vs a deliberate public artifact? | **Mostly deliberate.** README is public-facing, limitations are stated plainly, examples are real captures. The scratch-project tells are: no CI (QC5-09), the stale status doc (QC5-01), the stray redesign plan (QC5-04), "v0" in docstrings (QC5-07), and the missing favicon (QC5-06). |

Net: a reviewer spending 2–5 minutes on the repo + live demo comes away positive,
**unless** they open `docs/PROJECT_STATUS.md` (linked from the README) — which
tells them there is no eval harness and no deployment, directly contradicting what
they just read. That single document is the biggest public-perception risk.

---

## 7. Engineering Evidence Matrix

Rating key: **A** strong and publicly discoverable · **B** strong implementation
but poorly surfaced · **C** partial evidence · **D** unsupported / should not be
claimed.

| Area | Rating | Evidence | Discoverability issue |
|---|---|---|---|
| AI application engineering (structured outputs + re-validation) | **A** | `backend/core/openai_analyzer.py`: Responses API, strict JSON Schema from the Pydantic contract, mandatory final `QuoteCheckResult.model_validate`, no repair loop | README "OpenAI mode" covers it |
| Architecture & technical judgment | **A** | One analyzer chosen once by config; OpenAI failure returns an error, never silently switches to Demo; `app.py` stays thin | README Architecture + `docs/CURRENT_STATE.md` |
| Model / tool orchestration | **A** | `prompt.py` versioned artifacts (`quotecheck_v0.4`), `schema_export.py` JSON-Schema export, `text.format` strict schema | README |
| Schema / contracts | **A** | `backend/core/schema.py` Pydantic models; schema-first is the through-line for API + UI + eval | README "Design notes", `eval/README.md` |
| Evaluation | **A−** | `eval/`: 27-case corpus, deterministic runner with exit codes + per-mode reporting, human rubric, 2 permanent regression cases, committed baselines | Dented by **QC5-02** (self-contradicting section in `eval/README.md`) |
| Reliability & explicit failure handling | **A** | `backend/core/errors.py` 8-category taxonomy + spec table; bounded 1-retry loop (`OPENAI_MAX_ATTEMPTS = 2`); explicit timeout; sanitized logging; `eval/tests/test_openai_reliability.py` (42 cases) | README "Reliability (QC-4)" |
| Debugging | **B** | REG-001 / REG-002 encode real past bugs (domain leakage, unsupported price judgment) with `regression_origin`; QC-3C baseline-driven repair (11→24 / 27) | The debugging narrative is in `docs/review/**` / `docs/tickets/**`, not surfaced in the README |
| Observability | **A−** | `run_logger.py` + `logs/app_runs.jsonl`: one sanitized JSONL record per request (provenance, latency, risk counts, failure classification, `provider_attempts`) | README is explicit that hosted logs are local/ephemeral — correct, not a gap |
| Cost / resource awareness | **A** | `--mode openai` requires `--allow-paid`; SDK `max_retries=0`; 30s timeout vs SDK's 600s; retry count deliberately not env-overridable; 12,000-char cap; Demo is the default | README Evaluation + "Reliability (QC-4)" |
| Human-control boundaries | **A** | Mandatory disclaimer; "needs clarification" over guessing; prompt + termset forbid price/fairness/vendor-motive claims; disclaimer names a trade only for clearly vehicle quotes | `SPEC.md` output principles, `eval/rubric.md` dimensions 2 & 6 |
| Deployment | **A−** | Live Vercel + Railway; `railpack.json` (Python provider, staged `backend/requirements.txt`, `.venv` carried to deploy); provenance-verified live | **QC5-01**: `docs/PROJECT_STATUS.md` still says "No verified public deployment" |
| End-to-end ownership | **A** | Ticket + review-bundle per unit of work with real command output; baseline discipline; branch hygiene | `docs/tickets/**`, `docs/review/**` |
| **Automated verification / CI** | **C** | Strong *local* verification surface — 144 stdlib `unittest` tests, deterministic `eval.run_eval` with exit codes, `npm run lint` + `npm run build`, fresh-clone verification recorded in bundles — but **no** `.github/workflows/**` or any other CI/pre-commit/Makefile config. Nothing runs automatically on push/PR. | Honestly disclosed (README ×2, Roadmap item 2, `docs/CURRENT_STATE.md`), so not *misleading* — but on a publicly deployed project the absent Actions tab is a visible production-discipline gap. See **QC5-09**. |

No area rates **D**. Nothing in the repo currently claims something it cannot
support.

---

## 8. Evaluation Inspection

Against the Phase-7 questions:

- **Understandable to an outsider?** Yes. `eval/README.md` opens with the Layer A
  (deterministic invariants) vs Layer B (human semantic rubric) split, states
  plainly that "a Layer A pass rate is not an accuracy, quality, or correctness
  number", documents the case-file format, the 5-check vocabulary, and *how strong
  each check is* (including which are proxies).
- **Deterministic vs semantic boundary clear?** Yes, and enforced in tooling:
  `run_eval.py` implements only Layer A; `rubric.md` is explicitly "not implemented
  in code, and should not be"; the runner has no `semantic_expectations` scoring.
- **Reproducible?** Yes — verified in §4.4: `--validate-only` clean,
  `--mode demo` → 27/27 schema-valid, 24/27 deterministic, **identical failed-case
  set** to the committed QC-3C baseline; 144 harness tests pass.
- **Known failures represented honestly?** Yes. The 3 residuals (`AUTO-004`
  `missing_quote_context`; `CONT-003` / `HVAC-003` `ambiguous_items_present`) are
  named in `eval/results/summary_20260829T115912Z.md`, `eval/README.md`, and
  `docs/CURRENT_STATE.md`, with the reason (coarse one-item-per-domain Demo
  analyzer). They are **not** xfailed or excluded from the denominator; the runner
  exits non-zero.
- **Fake precision / misleading aggregate?** No. `rubric.md` explicitly prohibits
  averaging the six dimensions or reporting a mean; the runner labels Demo latency
  "local wall-clock only … not provider-performance evidence"; the summary carries
  a fixed "Interpretation boundary" note.
- **Results stale relative to the implementation?** No — reproduced exactly (§4.4).
- **Missing public-facing explanation of what the eval does / doesn't prove?**
  The explanation exists and is good — **except** the "Expected Demo-mode
  behaviour" section of `eval/README.md`, which still describes pre-QC-3C
  hardcoded behaviour and predicts failures that the current baseline (cited lower
  in the same file) does not have. See **QC5-02**.

---

## 9. Reliability / Failure Handling Inspection

Source-verified (`backend/core/errors.py`, `openai_analyzer.py`, `config.py`,
`app.py`) and consistent with the README "Reliability (QC-4)" section:

- **Classification** — `FailureCategory` has exactly the 8 values the README
  lists; `_SPECS` maps each once to `(http_status, retryable, user_message)`.
  `classify_openai_exception` orders subclasses before bases;
  auth/permission/not-found/bad-request → `configuration_error` (our fault, not a
  model failure).
- **No silent Demo fallback** — `app.py` selects the analyzer once from
  `USE_OPENAI`; the OpenAI path raises `QuoteCheckError` and re-`raise`s; it never
  calls `analyze_quote_stub`. Test-guarded (`test_openai_reliability.py`).
- **Bounded timeout** — `OpenAI(..., timeout=resolve_openai_timeout_seconds(),
  max_retries=0)`; default 30s; a malformed `QUOTECHECK_OPENAI_TIMEOUT_SECONDS`
  raises `configuration_error` before any client is built.
- **One owned retry** — bounded no-backoff loop, `OPENAI_MAX_ATTEMPTS = 2`, retries
  only `is_transient_openai_exception` (connection / timeout / provider ≥ 500);
  429 is surfaced retryable but **not** auto-retried. Retry count is a code
  constant, deliberately not env-overridable.
- **Response-state handling** — refusal, content-filter stop, incomplete/failed,
  empty structured content, non-JSON, and non-object payloads are each classified
  before any parse; a 200 is not assumed to carry a usable result.
- **Mandatory validation, no repair** — final `QuoteCheckResult.model_validate`;
  a failure is `invalid_model_output`, never patched or re-requested.
- **Sanitized errors & logs** — `error_response_body` returns only
  `{code,message,retryable,request_id}`; `QuoteCheckError.cause` is retained for
  tests but only `cause_type` (class name) is logged; `log_error_field` is
  application-authored, never `str(cause)`.
- **Frontend** — `App.jsx` parses the structured body, shows `detail.message` +
  `request_id` for `api` failures, never renders raw `str(exc)`; client abort at
  70s sits above the 2×30s backend budget; no auto-resubmit.

Live evidence (§3.1): all four malformed-request classes return the documented
`invalid_request` 422 envelope; unknown paths 404 cleanly. The OpenAI failure
paths could not be exercised live (no key) but are covered by the 42-case
reliability suite (§4.4).

The README frames this correctly as "failure *handling*, not high availability …
no SLA, no automatic recovery, no durable/centralized logging, and no
live-deployment verification". That qualification is accurate and should be kept.

---

## 10. Security / Privacy / Cost Hygiene

| Check | Result |
|---|---|
| Committed secrets / API keys | **None.** `git grep` for `sk-…` / `-----BEGIN` / `AKIA…` across all tracked files → 0 hits. |
| `.env` files | `backend/.env` exists locally, is **untracked** (gitignored `backend/.env`), and is **not** used in the hosted env (README + `app.py` load it by absolute path with `override=False`). `backend/.env.example` is the committed template, no secrets. |
| Browser-exposed values treated as secret | Correctly **not** — `VITE_API_BASE_URL` is documented as browser-visible in `frontend/.env.example` and the README; the built bundle contains only the public Railway URL + a localhost fallback literal, no key. |
| Unsafe public OpenAI exposure | **None.** Public demo runs the Demo analyzer (`metadata.model` verified live); README says leave `OPENAI_API_KEY` unset on Railway; `analyze_quote_openai` raises `configuration_error` if the key is absent. |
| Accidental paid calls in the default/public flow | **None.** `QUOTECHECK_USE_OPENAI` defaults to `0`; `eval.run_eval --mode openai` refuses to run without `--allow-paid`; Demo mode makes no network call. |
| CORS | Exact-origin only (`urlsplit`-parsed, `*` rejected at import, `allow_credentials=False`); verified live: Vercel origin allowed, `evil.example` denied with no ACAO header. |
| Raw provider errors leaking to client / logs | **None** — sanitized envelope + `cause_type`-only logging (§9). |
| Quote text / sensitive content committed | **None.** All `examples/*.txt` are synthetic with fictional vendor names (CoolBreeze HVAC, Riverside Home Services, ABC Auto Care); no PII. `logs/app_runs.jsonl` is untracked and stores no quote text. |
| Logs tracked | **No** — `logs/` is gitignored. |
| Local-machine / author leakage | Only `README.md:51` `git clone https://github.com/akshayv177/quotecheck-v0` — an intentional public repo URL, not a leak. No `/home/<user>` paths in code or core docs. `frontend/.vercel/project.json` (Vercel project/org IDs) is present locally but **gitignored**. |
| Input bounds | 12,000-char server-authoritative cap (`AnalyzeRequest`, FastAPI 422 above it); frontend mirrors it as UX only; a stdlib test asserts the two constants stay equal. README notes it is "an input-size safeguard, not complete abuse / request-body protection" — accurate. |
| Abuse / cost risk on the public backend | No public rate limiting / quota control (disclosed in README Limitations + Roadmap). Acceptable for a Demo-analyzer deployment that reaches no paid inference; would need addressing before OpenAI mode could be exposed anonymously (README says exactly this). |
| Dependency advisories | `npm audit` in a fresh `npm ci`: 12 findings (9 high), **all** in the Vite/ESLint build toolchain, none in the `react`/`react-dom` runtime tree, all "fix available". Static-SPA build-time only. See **QC5-06**. Python deps are exact-pinned and install cleanly. |

No P0/P1 security issue. The hygiene here is genuinely good for a portfolio
project.

---

## 11. Claim Defensibility

### Safe to state as-is (README / project description / CV / interview)

- "Schema-first API contract (Pydantic `QuoteCheckResult`) shared by the API, the
  UI, and the eval harness."
- "Deterministic, zero-cost Demo analyzer; optional OpenAI mode using the Responses
  API with strict Structured Outputs generated from the Pydantic contract, then
  mandatory Pydantic re-validation."
- "Classified, bounded OpenAI failure handling: 8 failure categories, explicit
  per-attempt timeout, at most 2 provider calls per request, no silent fallback,
  sanitized error envelope and logs." (implemented **and** unit-tested)
- "27-case synthetic evaluation corpus with a deterministic regression runner
  (Layer A) and a separate human semantic rubric (Layer B); two permanent
  regression cases for past bugs." (implemented **and** reproduced)
- "Per-request JSONL run logging (request id, prompt version, model, latency,
  schema validity, risk counts, sanitized failure classification)."
- "Exact-origin CORS; 12,000-character request bound."
- "Publicly deployed Demo (Vercel + Railway) driven by a minimal `railpack.json`;
  runtime provenance verified (`metadata.model = quotecheck-demo-analyzer`)."
- "End-to-end: contract, two analyzer paths, reliability model, eval harness,
  frontend, and deployment, with a ticket + review-bundle trail."

### Safe only with the qualifier the repo already uses

- "Observability" → **per-request JSONL logging**; not durable or centralized
  (hosted logs are local/ephemeral).
- "Evaluation" → **deterministic Layer A + manual Layer B**; a Layer A pass rate is
  not an accuracy / hallucination / quality number; 27 cases is a coverage
  instrument, not a statistical sample.
- "Deployed" → a **portfolio Demo**; no SLA, no rate limiting / quotas, no
  accounts, no anonymous access to paid inference.
- "Tested" → **~144 stdlib unit/harness tests + a deterministic eval runner**, run
  manually; **no CI** (QC5-09).
- "Reliability" → failure **handling**, not high availability.

### Must NOT be claimed (the repo currently avoids all of these — keep it that way)

- "production-ready" / "production-grade" — no auth, no DB, no persistence beyond a
  local log, no SLA, no load testing, no CI, no monitoring.
- "scalable", "robust / fault-tolerant AI", "hallucination-safe", "reliable AI".
- "comprehensive evaluation" — the corpus is deliberately a coverage instrument;
  Layer B is manual.
- "production observability" — JSONL to an ephemeral local file is not that.
- "customer-facing" / "deployed AI system" in the paid-inference sense — the
  public path is the deterministic Demo analyzer.

**implemented ≠ tested ≠ publicly deployed ≠ production-grade.** For QuoteCheck:
the contract, both analyzer paths, the reliability model, and the eval harness are
*implemented and tested*; the Demo path is *publicly deployed*; nothing is
*production-grade*, and the repo correctly never says otherwise.

---

## 12. Findings by Severity

### P0 — blocks public use / dangerous / major false claim

*None.*

---

### P1 — materially undermines credibility

**QC5-01**
Severity: **P1**
Area: Repository truthfulness — headline status document
Evidence: `docs/PROJECT_STATUS.md` is linked from `README.md` ("For a full,
neutral summary of what's public-ready vs. still limited, see
`docs/PROJECT_STATUS.md`") and from `docs/LOCAL_DEMO.md`. It still contains:
- *What's still limited* → "**No automated test suite, eval harness, or CI.** The
  `examples/` pack is a manually curated sample set, not scored evaluation." —
  false since QC-3B/QC-3C: `eval/` ships a 27-case corpus, a deterministic runner,
  graders, and 144 stdlib harness tests (all reproduced in §4.4).
- *What's still limited* → "**No verified public deployment.**" and *Planned
  hardening (not yet built)* → "A verified public deployment." — false since QC-2B
  (live Vercel + Railway, provenance-verified; re-verified live in §3.1).
The document was last meaningfully edited in QC-1A; QC-2A/2B/3x/4 did not update
it.
Why it matters: it is the one document the README explicitly nominates as the
honest project summary, and it contradicts the README, `docs/CURRENT_STATE.md`,
and the live deployment. A skeptical reader following the README's own pointer
concludes either that the project is less finished than it is, or that its docs
cannot be trusted — both are worse than the truth.
Recommended action: update `docs/PROJECT_STATUS.md` — move "eval harness / runner
/ harness tests" and "public Demo deployment (provenance-verified)" into *What's
public-ready*; keep the genuine residual limits (semantic Layer B is manual; no
CI; no durable/centralized logging; no public rate limiting; OpenAI mode not
exposed anonymously); reword *Planned hardening* to drop "a verified public
deployment" and keep "CI", "scored semantic checks", "broader taxonomy",
"production-scale monitoring / load testing".
Repair now before v0 closure? **YES**

---

### P2 — worthwhile polish or clarity repair

**QC5-02**
Severity: **P2**
Area: Evaluation documentation — internal contradiction
Evidence: `eval/README.md` → "Expected Demo-mode behaviour" states
`ambiguous_items_present` "is hardcoded `true`, so the six `clean_itemized` cases
will fail their `ambiguous_items_present == false` assertion in Demo mode". QC-3C
made that marker derived (`any(item.vague_or_confusing …)` — confirmed in
`backend/core/stub_analyzer.py`), and the current committed baseline
(`eval/results/summary_20260829T115912Z.md`, cited in the same file's "Latest
committed Demo baseline" section) shows `clean_itemized 6 | 6 | 0` and only 3
residual failures. The section describes the pre-QC-3C world and contradicts the
same file's footer.
Why it matters: `eval/README.md` is the public-facing explanation of what the
evaluation proves; a reader who reaches the stale section gets a wrong picture,
and a careful reader watches the document disagree with itself — either way the
eval story loses credibility it has earned.
Recommended action: rewrite that section to describe current Demo behaviour —
`ambiguous_items_present` is derived; the 3 remaining Demo residuals are
`AUTO-004` (`missing_quote_context`) and `CONT-003` / `HVAC-003`
(`ambiguous_items_present`), for the reason already stated (coarse
one-item-per-domain analyzer). Keep the "the corpus targets the product contract,
not the stub" framing.
Repair now before v0 closure? **YES**

---

**QC5-03**
Severity: **P2**
Area: Process / discoverability — missing ticket
Evidence: `docs/tickets/` contains a file for every prior unit of work
(`TASK-000…`, `QC-1A…QC-4`) but had **no** `QC-5-*.md`, while a QC-5 review
bundle is being added. CLAUDE.md workflow rule 1 requires one ticket file per unit
of work.
Why it matters: an outside reader auditing the `docs/tickets/` + `docs/review/`
trail sees the sequence break exactly at the final inspection; it reads as
process slippage on the last step.
Recommended action: **done as part of this task** —
`docs/tickets/QC-5-final-public-inspection.md` was added alongside this bundle.
No further action.
Repair now before v0 closure? **YES (already done)**

---

**QC5-04**
Severity: **P2**
Area: Documentation clutter — stale internal plan
Evidence: `docs/design/UI_REDESIGN_PLAN.md` is the *pre-implementation* plan for
the already-shipped LUXURY-UI-001. It instructs keeping the "v0 prototype" chip
(§3, §4) — which was **removed** in LUXURY-UI-001A — and references a "55s client
timeout" (§1), which QC-4 raised to 70s. It is not linked from the README.
Why it matters: a browsing reviewer who opens `docs/design/` finds a planning
document that contradicts the shipped UI and the current code; it reads as
leftover scratch, and mildly dents the "deliberate public artifact" impression.
Recommended action: either delete it (its binding scope and outcome are already
captured in `docs/tickets/LUXURY-UI-001*.md` and
`docs/review/REVIEW_BUNDLE__LUXURY-UI-001*.md`), or add a one-line header:
"Historical planning document — superseded by LUXURY-UI-001 / 001A as shipped; do
not treat as current." Fold into the same housekeeping ticket as QC5-03.
Repair now before v0 closure? **YES**

---

**QC5-09**
Severity: **P2**
Area: Automated verification / release discipline
Evidence: the repo has a substantial automated-verification *surface* — 144 stdlib
`unittest` tests (`eval/tests/`, reproduced in §4.4), a deterministic
`eval.run_eval` runner with exit codes and per-mode reporting, `npm run lint` +
`npm run build`, and a fresh-clone verification pattern recorded across the review
bundles — but **no** repository-level CI: no `.github/workflows/**`, no other
CI-provider config, no `Makefile` / `justfile` / `tox.ini` / `noxfile` /
`.pre-commit-config.yaml`. Nothing runs on push or PR. The absence is honestly
disclosed (README: "There is no CI wiring yet"; Roadmap item 2; `docs/CURRENT_STATE.md`
"No CI"), so it is **not misleading** — but the project is now publicly deployed.
Question posed: does relying entirely on manual execution materially weaken the
public engineering signal now that the project is publicly deployed?
Assessment: **yes, modestly.** The verification commands all already exist, are
fast (144 tests in 0.78s; `--mode demo` is seconds; `npm build`+`lint` < 5s), and
cost nothing. A reviewer evaluating "production / professional discipline"
reflexively checks the Actions tab; an empty one on a deployed repo with a full
test suite is the clearest "personal project, not a maintained artifact" tell
remaining. A minimal workflow that runs only the already-existing commands
(`python -m unittest discover -s eval/tests`, `python -m eval.run_eval
--validate-only`, `python -m eval.run_eval --mode demo || true` for signal,
`npm ci && npm run lint && npm run build`) is **not** architecture expansion and
would close the gap. Rated P2 rather than P3 because the project is deployed and
the fix is nearly free; rated P2 rather than P1 because the gap is fully disclosed
and the manual surface genuinely exists.
Recommended action: add a single `.github/workflows/ci.yml` that runs the existing
backend harness/eval commands and the frontend `lint` + `build` on push and PR.
No new checks, no new dependencies, no `--allow-paid` / OpenAI job. Then update
the README Roadmap + `docs/CURRENT_STATE.md` "No CI" lines.
Repair now before v0 closure? **YES** (as its own tiny ticket — config only)

---

### P3 — optional / future improvement

**QC5-05**
Severity: **P3**
Area: Reproducibility verification record
Evidence: prior to QC-5, the fresh-setup path had only ever been verified against
an `rsync` copy of the working tree (TASK-009), never a real `git clone` of the
public GitHub remote; TASK-009's own bundle flagged this as an open follow-up.
Why it matters: "documented quickstart works from a real clone" is a claim a
reviewer will test; it had not itself been tested.
Recommended action: **done in this inspection** — §4 records a real
`git clone https://github.com/akshayv177/quotecheck-v0` followed by the full
documented backend + frontend + eval path, all passing. No repo change needed;
optionally note "verified from a public clone in QC-5" in `docs/CURRENT_STATE.md`
when it is next touched.
Repair now before v0 closure? **NO**

---

**QC5-06**
Severity: **P3**
Area: Public polish — frontend assets
Evidence: `frontend/index.html` intentionally dropped the Vite favicon
(LUXURY-UI-001) with no replacement, so the live site shows a generic browser-tab
icon; `frontend/public/vite.svg` is still present and is copied into `dist/` on
build though nothing references it. Separately, `npm ci` surfaces 12 `npm audit`
findings (9 high), all in the Vite/ESLint build toolchain (not the runtime tree).
Why it matters: minor. A portfolio piece benefits from a real favicon; the stray
`vite.svg` and the `npm audit` noise are small "unfinished" tells for a reviewer
who runs the frontend.
Recommended action (optional): add a tiny inline-SVG or data-URI favicon; delete
`frontend/public/vite.svg`; optionally pin/refresh the dev toolchain (`npm audit
fix`) or add a one-line note that the advisories are build-time-only. None of this
blocks v0.
Repair now before v0 closure? **NO**

---

**QC5-07**
Severity: **P3**
Area: Internal wording consistency
Evidence: module docstrings still carry "(v0)" / "v0" (`backend/app.py`,
`backend/core/{schema,config,prompt,stub_analyzer}.py`, the `App.jsx` header
comment) after QC-1A removed "v0" product framing from public docs;
`App.jsx` `TIMEOUT_ERROR_MESSAGE` says "If you're running in AI mode" where the
rest of the UI/docs say "OpenAI mode".
Why it matters: cosmetic; only a reader opening source files sees it. Not a
contradiction, just drift.
Recommended action (optional): drop "(v0)" from the docstrings and align "AI mode"
→ "OpenAI mode" next time those files are touched. Not worth a dedicated change.
Repair now before v0 closure? **NO**

---

**QC5-08**
Severity: **P3**
Area: Documentation ergonomics
Evidence: `docs/CURRENT_STATE.md` is 1171 lines; the "current state" content
(architecture, commands, capabilities, gaps — roughly the first ~305 lines) and
the per-ticket `### Fixed in / Added in …` changelog that follows are not visually
separated for a first-time reader.
Why it matters: minor. The file is accurate and CLAUDE.md points contributors at
it; a public reader may just find it long.
Recommended action (optional): add a short banner after the "Last updated" line —
"Sections below the '## Gaps' block are a historical per-ticket changelog; the
current state is everything above it." Or split the changelog into
`docs/CHANGELOG.md`. Not a v0 blocker.
Repair now before v0 closure? **NO**

---

### Clean areas — no finding (not padded)

Backend reliability/error model, CORS config, input bounds, secrets hygiene, the
eval runner + rubric + termsets design, the JSONL logger, `railpack.json`, the
README's Architecture / API / Reliability / Demo-vs-OpenAI / Public-deployment
sections, `SPEC.md`, the `examples/` pack, `backend/.env.example` /
`frontend/.env.example`, and the live API's validation + CORS + provenance
behaviour were all inspected and are accurate and defensible as written.

---

## 13. Recommended Repair Set

Three tiny tickets. No code logic, no architecture, no dependencies.

### QC-5A — Public status truth-sync *(documentation only)*
Closes **QC5-01 (P1)**, **QC5-02 (P2)**.
- `docs/PROJECT_STATUS.md`: move eval harness / runner / 144 harness tests and the
  provenance-verified public Vercel + Railway deployment into *What's
  public-ready*; keep the real residual limits; reword *Planned hardening* to drop
  "a verified public deployment".
- `eval/README.md`: rewrite the "Expected Demo-mode behaviour" section to describe
  current (post-QC-3C) Demo behaviour and the 3 actual residuals.
- `docs/CURRENT_STATE.md`: bump the "Last updated" line and add a short QC-5 entry
  noting the inspection and these doc corrections. (No behavioural change.)

### QC-5B — QC-5 governance + doc housekeeping *(documentation only)*
Closes **QC5-03 (P2)**, **QC5-04 (P2)**.
- `docs/tickets/QC-5-final-public-inspection.md` — **already added by this task**;
  QC-5B only needs to confirm it is committed with the branch.
- `docs/design/UI_REDESIGN_PLAN.md` — delete it, or prepend a one-line
  "historical / superseded" header.

### QC-5C — Minimal CI *(config only, no new checks)*
Closes **QC5-09 (P2)**.
- Add `.github/workflows/ci.yml` running the **already-existing** verification
  commands on push + PR: backend `python -m unittest discover -s eval/tests -p
  'test_*.py'`, `python -m eval.run_eval --validate-only`, `python -m
  eval.run_eval --mode demo` (informational), and frontend `npm ci && npm run
  lint && npm run build`. No OpenAI / `--allow-paid` job. No new dependency.
- Update the "no CI" lines in `README.md` (Roadmap) and `docs/CURRENT_STATE.md`.

If only two tickets are wanted, fold QC-5B into QC-5A; QC-5C should stay separate
because it touches config rather than prose.

---

## 14. Deferred / Explicit Non-Goals

Legitimate future work, **not** v0 blockers:

- Semantic Layer B review pass against `eval/rubric.md` (human scoring of the 27
  cases) — always intended to be manual; its absence is disclosed.
- Scored semantic checks / hallucination-rate measurement — deliberately not
  built; would be a real research effort, not a v0 fix.
- Broader, de-vehicled `NormalizedCategory` taxonomy and a real line-item
  parser/extractor for Demo mode — the 3 eval residuals live here; disclosed.
- Public rate limiting / quota control and durable/centralized logging — required
  only before OpenAI mode could be exposed anonymously; the README says so.
- PDF / OCR / image ingestion; auth / accounts / persistence — explicit `SPEC.md`
  non-goals.
- Market-price benchmarking / price-fairness judgment / vendor-claim verification
  — permanent product non-goals, not omissions.
- Favicon, dev-toolchain advisory cleanup, "(v0)" docstring wording,
  `CURRENT_STATE.md` length (QC5-06 / QC5-07 / QC5-08) — cosmetic; do opportunistically.
- In-browser visual / mobile / a11y pass and a screenshot-freshness check (§3.2) —
  human verification; recommended before calling v0 done but not a code/doc change.

---

## 15. Final Closure Recommendation

QuoteCheck v0 is **functionally ready** for public presentation: the live product
works, matches its documentation, leaks nothing, and reproduces from a clean
public clone. The engineering is real and, with two exceptions, discoverable.

Before v0 can be called complete, do the following — all small, all
documentation/config:

1. **QC-5A** — fix `docs/PROJECT_STATUS.md` (P1) and the `eval/README.md`
   self-contradiction (P2). This is the one change that materially affects how an
   outside reviewer perceives the project.
2. **QC-5B** — confirm the QC-5 ticket is committed; retire or mark
   `docs/design/UI_REDESIGN_PLAN.md`.
3. **QC-5C** — add a minimal CI workflow that runs the existing verification
   commands, and update the "no CI" lines. Recommended because the project is
   publicly deployed and the fix is nearly free; if explicitly descoped, record
   that decision rather than leaving it silent.
4. **Human pass** — one 2–5 minute in-browser check of the live frontend (report
   render, empty/loading/error states, ~375px responsive, reduced-motion) and a
   glance that `docs/assets/quotecheck-ui.png` still matches.

No P0, no code changes, no architecture work, no dependency changes, and no
new product scope are required. After QC-5A–QC-5C and the human pass, QuoteCheck
v0 can be closed.

---

### Appendix A — commands run (all read-only; nothing committed)

```
# git state
git status ; git status --short ; git ls-files ; git log --oneline -25 ; git branch -vv

# grep sweeps
git grep -n -i localhost ; git grep -niE 'quotecheck_v0\.(1|2|3)|v0 prototype|prototype'
git grep -niE 'missing_vehicle_context|needs_mechanic_confirmation'
git grep -niE '\b(TODO|FIXME|XXX|HACK)\b'
git grep -nE '/home/[a-z]+|akshayv177|Akshay Verma' ; git grep -nE 'sk-[A-Za-z0-9]{16,}|-----BEGIN|AKIA[0-9A-Z]{16}'
find .github -type f ; git ls-files | grep -iE '\.github/|gitlab-ci|circleci|travis|Jenkinsfile|pre-commit|tox\.ini|noxfile|Makefile'

# live backend  (https://quotecheck-v0-production.up.railway.app)
curl /health ; curl -X POST /analyze  (sample / vague / clean / empty / malformed / missing / oversize)
curl -X OPTIONS /analyze  (Origin: vercel  |  Origin: evil.example)
curl / ; curl /nope

# live frontend (https://quotecheck-frontend.vercel.app)
curl -i / ; curl /assets/index-*.js  -> grep for URLs / secrets / localhost

# fresh clone
git clone --depth 1 https://github.com/akshayv177/quotecheck-v0 qc5-clone
python3 -m venv .venv ; pip install -r backend/requirements.txt ; python -c "from backend.app import app"
QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --port 8777 ; curl /health ; curl -X POST /analyze (README curl)
cd frontend ; npm ci ; npm run build ; npm run lint ; npm audit
python -m eval.run_eval --validate-only
python -m eval.run_eval --mode demo --results-dir <scratch>
python -m unittest discover -s eval/tests -p 'test_*.py'
```

### Appendix B — finding index

| ID | Severity | Title | Repair now? |
|---|---|---|---|
| QC5-01 | P1 | `docs/PROJECT_STATUS.md` stale — denies the eval harness and the public deployment | YES |
| QC5-02 | P2 | `eval/README.md` "Expected Demo-mode behaviour" contradicts the current baseline | YES |
| QC5-03 | P2 | No `docs/tickets/QC-5-*.md` ticket file | YES (done in this task) |
| QC5-04 | P2 | `docs/design/UI_REDESIGN_PLAN.md` is a stale pre-implementation plan | YES |
| QC5-09 | P2 | No repository-level CI despite a full local verification surface, on a deployed project | YES (config-only ticket) |
| QC5-05 | P3 | Fresh public-clone path never verified before now | NO (done in this inspection) |
| QC5-06 | P3 | No favicon; stray `vite.svg`; `npm audit` dev-toolchain noise | NO |
| QC5-07 | P3 | "(v0)" left in module docstrings; "AI mode" vs "OpenAI mode" wording | NO |
| QC5-08 | P3 | `docs/CURRENT_STATE.md` (1171 lines) has no current-vs-history signpost | NO |
