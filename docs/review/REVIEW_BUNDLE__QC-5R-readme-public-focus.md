# Review bundle — QC-5R — README public-reader refocus

## 1. Ticket / phase

`docs/tickets/QC-5R-readme-public-focus.md`. Phase QC-5 (final public inspection)
repair series, following QC-5A. Branch `task/QC-5R-readme-public-focus` (based on
`main` @ `12684cc`). **Nothing committed.**

Addresses the discoverability half of QC-5 §6/§7 — content that was accurate but
"poorly surfaced". CI (**QC5-09** → QC-5B) is out of scope and was not started.

## 2. Scope summary

Documentation only. **No application, `backend/**`, `frontend/**`, `eval/**`,
`examples/**`, `railpack.json`, dependency, deployment-configuration, `SPEC.md`,
`CLAUDE.md`, or `docs/PROJECT_STATUS.md` change.** No schema, prompt
(`PROMPT_VERSION` stays `quotecheck_v0.4`), analyzer, eval-corpus, or eval-results
change. No new product claim.

Files changed:

| File | Change |
|---|---|
| `README.md` | Full restructure: 571 → 324 lines (−480 / +234 in the diff) |
| `docs/LOCAL_DEMO.md` | New "Install the backend dependencies" step (steps renumbered) + the renamed README anchor |
| `docs/CURRENT_STATE.md` | `Last updated` line, `### Added in QC-5R` entry, 4 corrected current-state cross-references to README sections |
| `docs/tickets/QC-5R-readme-public-focus.md` | Created |
| `docs/review/REVIEW_BUNDLE__QC-5R-readme-public-focus.md` | Created (this file) |

## 3. README structure — before / after

### Before (571 lines)

```
# QuoteCheck — Service Quote Review Assistant
## What it is, who it helps, why it exists
### What QuoteCheck does not do
## Try it in under a minute (no API key needed)     ← line 35
### Prereqs
### 0) Clone
### 1) Backend
### 2) Frontend
## What a report looks like
## Screenshot
## Demo mode vs. OpenAI mode
## Public demo deployment                            ← first live URL, line ~186
### How it is wired
## API
### `POST /analyze`
## Architecture                                      ← line 297
### OpenAI mode
#### Reliability (QC-4)
### Demo mode
### Evaluation                                       ← line 386
## What works today
## Limitations
## Design notes
## Repo structure (high level)                       ← 58 lines
## Roadmap
## License
```

### After (324 lines)

```
# QuoteCheck
### ▶ Live demo — quotecheck-frontend.vercel.app     ← line 10
    + nav row (Engineering highlights · Architecture · Evaluation ·
      Live deployment · Limitations · Run locally)
    + disclaimer callout
## What QuoteCheck does                              ← line 27
### Not in scope
## Product preview                                   ← line 57 (screenshot + real output)
## Engineering highlights                            ← line 82
## Architecture                                      ← line 123
### Demo mode vs. OpenAI mode                        ← anchor preserved
### API contract
## Reliability and failure handling                  ← line 182
## Evaluation                                        ← line 207
## Live deployment                                   ← line 244
## Limitations                                       ← line 274
## Run locally                                       ← line 297 (pointer only, 8 lines)
## Documentation                                     ← line 307
## License
```

Net effect: the live demo moved from line ~186 to line 10; the first local-setup
material moved from line 35 to line 297. Every piece of engineering evidence
(highlights, architecture, API contract, reliability, evaluation, deployment) now
precedes it.

## 4. Sections removed or demoted

| Removed / demoted | Where the detail now lives |
|---|---|
| "Prereqs" (Python/Node versions, WSL note) | `docs/LOCAL_DEMO.md` step 2 |
| "0) Clone", "1) Backend" (venv/conda/pip walkthrough, `curl /health`, sample `/analyze` curl) | `docs/LOCAL_DEMO.md` steps 2–5 |
| "2) Frontend" (`npm install`, `npm run dev`, `VITE_API_BASE_URL` guidance) | `docs/LOCAL_DEMO.md` step 6; `frontend/.env.example` |
| `.env` tutorial in "Demo mode vs. OpenAI mode" (`cp backend/.env.example`, variable-by-variable) | `docs/LOCAL_DEMO.md` step 8; `backend/.env.example` |
| localhost URLs (`http://localhost:8000`, `:5173`) | `docs/LOCAL_DEMO.md`; **zero** localhost references remain in README |
| `tail -n 1 logs/app_runs.jsonl \| python3 -m json.tool` | `docs/CURRENT_STATE.md` → Commands |
| "How it is wired" (Vercel root dir, `railpack.json` walkthrough, backend env matrix, Railway start command) | `docs/CURRENT_STATE.md` → *Added in QC-2A* / *Added in QC-2B*; `railpack.json` still linked from README |
| "Repo structure (high level)" — 58-line tree | Replaced by the curated `## Documentation` list |
| "What works today" | Duplicated `docs/PROJECT_STATUS.md` "What's public-ready today" — removed, README links that doc |
| "Design notes" | Folded into `## Engineering highlights` |
| "Roadmap" (QC-2A/2B/QC-5 milestone narrative) | `docs/PROJECT_STATUS.md` → "Planned hardening (not yet built)" is the live version |
| Historical QC-3B eval baseline (11/27) inline | `eval/README.md` → "Latest committed Demo baseline" keeps both runs |
| "API" full section | Compressed into `### API contract` under Architecture; the exhaustive field and error-code enumerations were dropped in §14 and now point at `backend/core/schema.py` + `SPEC.md` |
| "OpenAI mode" / "Demo mode" prose subsections | Compressed into a comparison table + Engineering highlights |

No technical detail was deleted outright — each item above is already recorded in a
deeper doc, and `git diff` over those docs (except the two in scope) is empty.

## 5. Technical evidence promoted

Now visible before any setup material:

- **Engineering highlights** (new, 12 bullets): schema-first Pydantic contract;
  Structured Outputs generated *from* the contract with mandatory re-validation;
  deterministic zero-provider-call Demo analyzer; one analyzer chosen once by
  configuration with no silent fallback; per-response provenance metadata
  (`request_id` / `prompt_version` / `model` / `created_at` / `latency_ms` /
  `schema_valid`); 8-category failure taxonomy; bounded timeout + at most 2 provider
  calls; versioned prompt artifacts; exact-origin CORS; 12,000-character server-side
  input bound; per-request JSONL observability; cost-aware paid-eval gate; public
  Vercel + Railway deployment.
- **Architecture**: redrawn to show the browser → FastAPI → configuration-selected
  analyzer (Demo **or** OpenAI Structured Outputs) → mandatory Pydantic validation →
  response + JSONL trace flow, with the observed public path separately identified as
  `quotecheck-demo-analyzer`.
- **Reliability and failure handling**: promoted from a `####` sub-sub-heading under
  "OpenAI mode" to its own `##` section.
- **Evaluation**: corpus size (27), domain count (6), the Layer A / Layer B split, the
  two permanent regression cases, the committed baseline, the three retained
  residuals, and an explicit paragraph that 24/27 is not an AI accuracy score.
- **Live deployment**: URL table plus the observed public verification and the
  provenance-not-environment-inspection qualifier.

## 6. Claim-discipline check

Grep over the new `README.md`:

```
$ grep -nEi 'production-(grade|ready)|enterprise|robust ai|hallucination-safe|comprehensive evaluation|No verified public deployment|coming next|localhost|quotecheck_v0\.[0-3]|missing_vehicle_context|needs_mechanic_confirmation|v0 prototype|state-of-the-art|cutting-edge|world-class' README.md
(no hits)
```

Vehicle-framing sweep — confirming the product is not described as vehicle-only:

```
$ grep -nEi 'vehicle|mechanic|car repair|garage' README.md
30:You paste raw quote text — from a garage, contractor, appliance technician, or any
44:Domain-neutral by design: vehicle servicing, HVAC/appliance repair, plumbing and
67:  "explanation": "Brake pads are the friction material that presses on the rotor to slow the vehicle. …
76:`"vague_or_confusing": true`. Six captured cross-domain reports — vehicle, AC/appliance,
290:  `NormalizedCategory` taxonomy still carries vehicle-era wording. The OpenAI-mode
```

All five are domain-neutral in context: one of several named domains (30, 44, 76), a
verbatim quotation from a real captured Demo response (67), and the honest taxonomy
limitation (290). No vehicle-only product framing.

Qualifiers preserved verbatim in substance:

| Statement | Qualifier kept |
|---|---|
| Reliability | "This is failure *handling*, not high availability: there is no SLA, no automatic recovery, and no durable or centralized logging." |
| Evaluation | "**24/27 is not an AI accuracy score.** … It says nothing about model quality, hallucination rate, or correctness." |
| Deployment | "This is a public demonstration, not a service: no scale or uptime guarantees … no public rate limiting, and no anonymous access to paid inference." |
| Hosted mode | "These statements rest on **observed runtime provenance**, not on an inspection of the hosting environment's variables." |
| Demo analyzer | "a stand-in for realistic responses, not an accuracy claim … **not** equivalent to OpenAI-mode output." |
| Header | "Not safety advice; verify with a qualified professional… early-stage implementation" |

No résumé/hiring language, no "this project demonstrates …", no marketing superlative.

## 7. Required content still exposed (acceptance criterion 4 of the task)

| Required | Where in the new README |
|---|---|
| Public Demo | Live demo link (line 10); "Live deployment" table + observed verification |
| Optional OpenAI path | "Demo mode vs. OpenAI mode" table; Engineering highlights; Architecture diagram |
| Eval baseline | "Evaluation" → 27/27 schema-valid, 24/27 deterministic |
| Known residuals | "Evaluation" → `AUTO-004`, `CONT-003`, `HVAC-003`, "retained, not excluded" |
| Reliability / failure behaviour | "Reliability and failure handling" (6 bullets) |
| Observability limitation | "Limitations" → hosted JSONL is local/ephemeral, not durable or centralized |
| Product non-goals | "Not in scope" + "Limitations" |

## 8. Link verification

```
$ grep -oE '\]\(([^)]+)\)' README.md | sed 's/](//;s/)$//' | grep -v '^#' | grep -v '^http' | sort -u | while read -r p; do
    git ls-files --error-unmatch "$p" >/dev/null 2>&1 && echo "OK      $p" || echo "MISSING $p"; done
OK      SPEC.md
OK      docs/CURRENT_STATE.md
OK      docs/LOCAL_DEMO.md
OK      docs/PROJECT_STATUS.md
OK      docs/assets/quotecheck-ui.png
OK      eval/README.md
OK      eval/results/summary_20260829T115912Z.md
OK      eval/rubric.md
OK      examples/README.md
OK      examples/sample_output.json
OK      railpack.json
```

Internal anchors (every `](#…)` target matched against the file's own headings):

```
OK      #architecture
OK      #engineering-highlights
OK      #evaluation
OK      #limitations
OK      #live-deployment
OK      #run-locally
```

Inbound anchors from other documents:

```
OK      examples/README.md:15  -> README.md#demo-mode-vs-openai-mode
OK      docs/LOCAL_DEMO.md:93  -> README.md#product-preview
```

`examples/**` is out of scope, so the `### Demo mode vs. OpenAI mode` heading was
deliberately retained (as a compact comparison table) rather than renamed.
`docs/LOCAL_DEMO.md` *is* in scope, so its `#screenshot` link was updated to the
renamed `#product-preview` section.

`docs/LOCAL_DEMO.md` outbound links, all resolving: `../README.md#product-preview`,
`PROJECT_STATUS.md`, `assets/quotecheck-ui.png`.

## 9. Live verification (2026-09-01, run for this ticket)

```
$ curl -s -o /dev/null -w '%{http_code}\n' https://quotecheck-frontend.vercel.app
200

$ curl -s -w '\n%{http_code}\n' https://quotecheck-v0-production.up.railway.app/health
{"status":"ok"}
200

$ curl -s -X POST https://quotecheck-v0-production.up.railway.app/analyze \
    -H 'Content-Type: application/json' \
    -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); m=d["metadata"]; print("model:",m["model"]); print("prompt_version:",m["prompt_version"]); print("schema_valid:",m["schema_valid"]); print("line_items:",len(d["line_items"]))'
model: quotecheck-demo-analyzer
prompt_version: quotecheck_v0.4
schema_valid: True
line_items: 3

$ curl -s -o /dev/null -D - -X OPTIONS .../analyze \
    -H 'Origin: https://quotecheck-frontend.vercel.app' -H 'Access-Control-Request-Method: POST'
access-control-allow-origin: https://quotecheck-frontend.vercel.app
status:200

$ curl -s -o /dev/null -D - -X OPTIONS .../analyze \
    -H 'Origin: https://evil.example' -H 'Access-Control-Request-Method: POST'
foreign_preflight_status:400
# access-control-allow-origin header count: 0  (header absent)
```

This reproduces the QC-5 §3.1 findings and is the evidence behind the README's
"Live deployment" section. The Railway environment's variables were **not**
inspected; the hosted-mode statement rests on `metadata.model` alone.

## 10. Acceptance-criteria table

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Live demo above the fold; product clear in ~30s | ✓ | §3 — demo at line 10, product description lines 3–8, "What QuoteCheck does" line 27 |
| 2 | Engineering evidence precedes local setup | ✓ | §3 — highlights/architecture/reliability/eval/deployment at lines 82–273; "Run locally" at line 297 |
| 3 | Architecture current; observed public path identified without implying OpenAI | ✓ | §5; README lines 122–145 ("The observed public deployment executes the deterministic Demo analyzer … The OpenAI path is a repository capability exercised locally") |
| 4 | Eval baseline + residuals visible; 24/27 explicitly not an accuracy score | ✓ | §7; README "Evaluation" |
| 5 | Reliability evidence visible and qualified | ✓ | §6 qualifier table; README "Reliability and failure handling" |
| 6 | Limitations candid (ephemeral logs, OpenAI not the observed hosted path) | ✓ | README "Limitations", 11 bullets |
| 7 | "Run locally" is a pointer; `docs/LOCAL_DEMO.md` self-contained | ✓ | README lines 297–305; `docs/LOCAL_DEMO.md:19` `pip install -r backend/requirements.txt` |
| 8 | All README-relative links + both inbound anchors resolve | ✓ | §8 — 11 OK, 0 missing |
| 9 | Live URLs and provenance verified | ✓ | §9 |
| 10 | Stale/high-risk language grep clean | ✓ | §6 — no hits |
| 11 | Protected-path diff empty; `git diff --check` clean; nothing committed | ✓ | §11 |

## 11. Scope / no-implementation-change confirmation

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
 M docs/LOCAL_DEMO.md
?? docs/tickets/QC-5R-readme-public-focus.md

$ git diff --stat
 README.md             | 714 +++++++++++++++++---------------------------------
 docs/CURRENT_STATE.md |  70 ++++-
 docs/LOCAL_DEMO.md    |  33 ++-
 3 files changed, 317 insertions(+), 500 deletions(-)

$ git diff --check
(clean)

$ git diff -- backend frontend eval examples railpack.json SPEC.md CLAUDE.md \
      docs/PROJECT_STATUS.md docs/design
(no output — protected paths untouched)
```

(`docs/review/REVIEW_BUNDLE__QC-5R-readme-public-focus.md` appears as `??` once this
file is written; the `git diff --stat` above was captured before it existed.)

No source file, configuration file, dependency manifest, deployment manifest, eval
corpus, eval result, or example output was read-modified. The running application is
byte-identical to `main`; no test or eval run was required because nothing executable
changed. The live verification in §9 exercised the already-deployed backend only.

## 12. Out-of-scope findings (noted, not fixed)

- `docs/PROJECT_STATUS.md` and the new README overlap on the public-ready /
  still-limited summary. Both are truthful and consistent (checked while writing the
  Limitations section); merging or further differentiating them was not in scope.
- `docs/CURRENT_STATE.md` remains long (1,258 lines) with the current-state content
  and the per-ticket changelog undifferentiated — QC5-08 (P3), still open.
- QC5-06 (favicon, stray `frontend/public/vite.svg`, dev-toolchain `npm audit`
  advisories) and QC5-07 ("(v0)" in module docstrings, "AI mode" wording in
  `App.jsx`) remain open P3 items in source files this ticket may not touch.

## 13. Remaining limitations (unchanged by this ticket)

- No repository-level CI — nothing runs on push/PR. **This is QC-5B (QC5-09).**
- Semantic (Layer B) grading remains a manual human pass.
- Hosted `logs/app_runs.jsonl` is local and ephemeral; no durable or centralized
  observability.
- No public rate limiting / quota control; OpenAI mode is not exposed by the public
  demo.
- The three deterministic Demo residuals (`AUTO-004`, `CONT-003`, `HVAC-003`) remain
  documented, not chased.
- Nothing is production-grade or production-ready, and no document claims otherwise.

Nothing has been committed, merged, or pushed — left for the user to review. QC-5B
(minimal CI) has not been started.

---

## 14. Surgical refinement pass (same ticket, after human review)

Four targeted `README.md` claim/wording edits requested during final human review. **No
restructure, no reordering, no new section, no other file changed.** Section list, order,
anchors, architecture diagram, Demo-vs-OpenAI wording, evaluation figures, limitations,
and the local-development hierarchy are unchanged. README 326 → 324 lines.

| # | Edit | Reason |
|---|---|---|
| 1 | Live-demo sentence | The old wording ("every response is real, schema-valid") over-claimed: validation/error responses use the separate structured error envelope, not `QuoteCheckResult`. Now scoped to *successful analyses*, and framed as the **observed hosted path** |
| 2 | Schema-first highlight | "single source of truth for the API, the UI, and the eval harness" could be read as the React UI being generated from the Pydantic model. Now "defines the canonical result contract consumed by the API, the UI, and the eval harness" |
| 3 | `### API contract` | Dropped the exhaustive `QuoteCheckResult` field enumeration and the inline list of all nine `code` values — reference density inappropriate for a public README. Endpoint, the non-empty/12,000-character bound, the validated result, `GET /health`, the stable envelope, explicit failure classification, and the `retryable` meaning are all retained |
| 4 | Product-preview lead-in | The first captured example is automotive; a fast scanner could read the project as vehicle-only. Now "One example from the cross-domain Demo pack — …". The JSON example, the `examples/sample_output.json` link, and the surrounding material are unchanged |

### Final wording

**1 — live demo**

> No sign-up or API key required. The observed hosted path uses QuoteCheck's
> deterministic Demo analyzer with zero provider calls; successful analyses are validated
> against the same `QuoteCheckResult` contract as the OpenAI path.

Evidence discipline preserved: this describes observed runtime provenance. The README
does **not** claim Railway has `QUOTECHECK_USE_OPENAI=0`, that `OPENAI_API_KEY` is
absent, or that the deployment can never reach OpenAI — none of that was inspected.

**2 — schema-first highlight**

> - **Schema-first contract.** A Pydantic `QuoteCheckResult` defines the canonical result
>   contract consumed by the API, the UI, and the eval harness. Successful analysis
>   results rendered by the UI have been validated against that contract.

The closing sentence was tightened in the follow-up correction below: the UI also renders
structured **error** responses, which are not `QuoteCheckResult` instances, so "nothing is
rendered that has not been validated against it" was too broad.

**3 — `### API contract`** (complete subsection)

> `POST /analyze` accepts a required, non-empty `quote_text` of up to 12,000 characters
> and returns a validated `QuoteCheckResult`. `GET /health` returns `{"status": "ok"}`.
>
> Failures use one stable, user-safe envelope:
>
> ```json
> { "detail": { "code": "provider_timeout", "message": "The analysis service took too long to respond. Please try again.", "retryable": true, "request_id": "…" } }
> ```
>
> Provider transport failures, refusals, incomplete generations, invalid model output,
> configuration errors, internal errors, and request validation are each classified
> explicitly under their own `code`. `retryable` means a manual retry may reasonably
> succeed — it does *not* mean QuoteCheck retried automatically.
>
> The result contract itself is defined in `backend/core/schema.py`;
> [`SPEC.md`](SPEC.md) describes the product contract and output principles behind it.

Deviation from the requested wording, on purpose: the closing pointer does **not** say
"See `SPEC.md` for the complete contract". `SPEC.md` states scope, non-goals, and output
principles; the complete result contract is the Pydantic model in
`backend/core/schema.py` (which `eval/README.md` also names as "the single source of
truth"). Both are cited for what each actually is.

**4 — product-preview lead-in**

> One example from the cross-domain Demo pack — an excerpt from a real captured response
> (full file: [`examples/sample_output.json`](examples/sample_output.json)):

### Re-verification after the pass

```
$ # README-relative links → tracked files
OK  SPEC.md · docs/CURRENT_STATE.md · docs/LOCAL_DEMO.md · docs/PROJECT_STATUS.md
OK  docs/assets/quotecheck-ui.png · eval/README.md · eval/results/summary_20260829T115912Z.md
OK  eval/rubric.md · examples/README.md · examples/sample_output.json · railpack.json
    (11 OK, 0 missing)

$ # internal anchors
OK  #architecture #engineering-highlights #evaluation #limitations #live-deployment #run-locally

$ # inbound anchors
OK  examples/README.md:15 -> README.md#demo-mode-vs-openai-mode
OK  docs/LOCAL_DEMO.md:93 -> README.md#product-preview

$ # backend/core/schema.py is a plain mention (not a link); tracked
OK  backend/core/schema.py

$ curl -s -o /dev/null -w '%{http_code}\n' https://quotecheck-frontend.vercel.app
200
$ curl -s -w '\n%{http_code}\n' https://quotecheck-v0-production.up.railway.app/health
{"status":"ok"}
200
$ # POST /analyze
model: quotecheck-demo-analyzer
prompt_version: quotecheck_v0.4
schema_valid: True

$ grep -nEi 'production-(grade|ready)|enterprise|robust ai|hallucination-safe|comprehensive evaluation|No verified public deployment|coming next|localhost|quotecheck_v0\.[0-3]|missing_vehicle_context|needs_mechanic_confirmation|v0 prototype|high availability|scalab|customer usage' README.md
201:This is failure *handling*, not high availability: there is no SLA, no automatic
```

The single grep hit is the **negation** — the sentence that explicitly denies high
availability. Correct, and deliberately kept.

Preserved facts re-confirmed by grep: `27-case synthetic corpus`, `27/27 schema-valid`,
`24/27 deterministic cases pass`, `AUTO-004` / `CONT-003` / `HVAC-003`, "**24/27 is not
an AI accuracy score.**", and "nothing runs on push or PR yet". Zero localhost
references. No badges, no CI language, no marketing or résumé wording added.

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
 M docs/LOCAL_DEMO.md
?? docs/review/REVIEW_BUNDLE__QC-5R-readme-public-focus.md
?? docs/tickets/QC-5R-readme-public-focus.md

$ git diff --stat
 README.md             | 714 +++++++++++++++++---------------------------------
 docs/CURRENT_STATE.md |  70 ++++-
 docs/LOCAL_DEMO.md    |  33 ++-
 3 files changed, 317 insertions(+), 500 deletions(-)

$ git diff --check
(clean)

$ git diff -- backend frontend eval examples railpack.json SPEC.md CLAUDE.md \
      docs/PROJECT_STATUS.md docs/design
(no output — protected paths untouched)
```

`docs/LOCAL_DEMO.md` and `docs/CURRENT_STATE.md` were **not** touched by this pass; their
diffs are unchanged from §11 (the earlier QC-5R work). No broken reference was created.

## 15. Follow-up corrections (two edits, after review of §14)

| # | File | Change |
|---|---|---|
| 1 | `README.md` | Schema-first highlight, closing sentence: "Nothing is rendered that has not been validated against it." → "Successful analysis results rendered by the UI have been validated against that contract." The UI also renders the structured error envelope, which is not a `QuoteCheckResult`, so the original claim was broader than the code supports. The preceding sentence and all other README prose are unchanged |
| 2 | `docs/CURRENT_STATE.md` | `### Added in QC-5R` entry only: the stale "326 lines" README figure corrected to **324**. No other line in that file touched |

Section 14's "one stale number left deliberately" note is resolved by correction 2.
No other file changed; no verification result in §8, §9, §13 or §14 is affected —
neither edit adds a link, an anchor, a claim, or a command.

```
$ git diff --check
(clean)

$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
 M docs/LOCAL_DEMO.md
?? docs/review/REVIEW_BUNDLE__QC-5R-readme-public-focus.md
?? docs/tickets/QC-5R-readme-public-focus.md

$ git diff --stat
 README.md             | 714 +++++++++++++++++---------------------------------
 docs/CURRENT_STATE.md |  70 ++++-
 docs/LOCAL_DEMO.md    |  33 ++-
 3 files changed, 317 insertions(+), 500 deletions(-)
```

Nothing committed, merged, or pushed. QC-5B not started.
