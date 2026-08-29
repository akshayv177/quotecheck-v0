# CURRENT_STATE.md

Last updated: 2026-08-29 (QC-3B)

Short, factual snapshot of what exists right now. Update this file (and this date
line) in any ticket that changes capabilities, commands, or gaps.

## Architecture

Two-process local app: a React single-page frontend posts pasted quote text to a
FastAPI backend, which returns a schema-valid `QuoteCheckResult` and appends one
JSONL log record per request.

- `backend/app.py` — FastAPI app; `GET /health`, `POST /analyze`; CORS for the Vite
  dev server; per-request logging (success and failure paths).
- `backend/core/schema.py` — Pydantic contract (`AnalyzeRequest`, `QuoteCheckResult`
  and nested models: line items, risk levels, uncertainty markers, refusals, metadata).
- `backend/core/stub_analyzer.py` — deterministic keyword-heuristic analyzer
  (default mode, zero cost, product-facing name "Demo mode"). Recognizes vehicle
  (brake/tyre), AC/appliance (air conditioning/compressor/refrigerant/hvac/appliance),
  and home-maintenance/contractor (plumbing/electrical/contractor/handyman/
  renovation) keywords, plus a generic vague-charge catch-all and a no-match
  fallback (TASK-008). Reports `metadata.model = "quotecheck-demo-analyzer"`
  (`config.DEMO_ANALYZER_MODEL`), a label distinct from `QUOTECHECK_MODEL`, so
  demo-mode responses and JSONL logs never claim an OpenAI model was called.
- `backend/core/openai_analyzer.py` — OpenAI Responses API with strict Structured
  Outputs (JSON Schema generated from the Pydantic `QuoteCheckResult` contract via
  `schema_export.py`), then final Pydantic validation of the response; server
  overrides metadata. Default model `gpt-4o-mini` (`QUOTECHECK_MODEL`). An
  OpenAI-path failure returns an error to the caller; it does not fall back to Demo
  output.
- `backend/core/prompt.py` — versioned prompt artifacts (`PROMPT_VERSION = quotecheck_v0.4`),
  explanation-first: every line item must carry a plain-English `explanation` before
  risk judgment, and vague/bundled charges must be flagged via `vague_or_confusing`.
  Generic across domains (vehicle, appliance/HVAC, home/contractor, other services):
  the uncertainty markers are domain-neutral (QC-1B) — `missing_quote_context` is set
  `true` only when the quote omits contextual detail needed to interpret a
  recommendation confidently (scope, symptoms, quantities, diagnostic basis), and
  `needs_professional_confirmation` `true` when technical/safety-sensitive work
  should be checked by an appropriate qualified professional, with no assumed trade;
  the disclaimer only names a specific professional (e.g. "certified mechanic") for
  clearly vehicle-related quotes and otherwise stays generic; the model is
  explicitly told not to characterize a quote/charge as high/low/fair/cheap/
  expensive/overpriced/underpriced without benchmarking data.
- `backend/core/config.py` — env-var config: `QUOTECHECK_USE_OPENAI`, `QUOTECHECK_MODEL`
  (default `gpt-4o-mini`), `QUOTECHECK_LOG_PATH`, `OPENAI_API_KEY`, and
  `DEMO_ANALYZER_MODEL` (fixed label, not env-configurable). Loaded from untracked
  `backend/.env` (template: `backend/.env.example`); if `backend/.env` doesn't exist
  at all, the app still runs — defaults are `QUOTECHECK_USE_OPENAI=0` (Demo mode).
- `backend/core/run_logger.py` / `logs/app_runs.jsonl` — append-only JSONL run logs.
- `backend/core/schema_export.py` — JSON Schema export used by the OpenAI analyzer.
- `frontend/src/App.jsx` — entire UI: textarea → Analyze → quote-understanding
  report (report header with a derived risk-count strip, summary card, then one
  card per line item with `explanation` as the prominent field, `rationale_short`
  as secondary risk reasoning, a risk-colored left border, a risk pill using
  semantic wording ("High risk" / "Caution" / "Low risk"), a "Needs
  clarification" badge when `vague_or_confusing` is true, and `evidence_needed`
  as a secondary bullet list), a "Before you approve" section ("Questions to
  ask the vendor" / "Things to verify before approving", responsive 2→1 column),
  a footer with the disclaimer always visible, run metadata, and raw JSON
  collapsed by default in a `<details>` block with the Copy button inside it. A
  real loading state (pulse indicator plus an elapsed-time-driven stage
  label and elapsed-time counter, `aria-live="polite"`) and a styled error
  card (copy differentiated by timeout/network/HTTP/other failure kind)
  replace the earlier button-label-only loading and single generic error
  message. Requests time out client-side after 55s via `AbortController`. A small
  "Demo mode" / "OpenAI mode" badge (`ModeBadge`, built on the existing `Pill`
  primitive) sits next to the run-metadata line, derived from
  `result.metadata.model` — no separate flag or endpoint.
  Single light theme (`frontend/src/index.css` token set); no dark mode.
  React 19 + Vite 7. Visual identity (LUXURY-UI-001): inline style objects were
  extracted into CSS classes; the accent color moved off the default
  Tailwind-blue to a deep ink-teal (`--accent`), the report opens with a
  document-style header (title + a risk-tally chip row using the same
  client-side counts), section headings use a small-caps label treatment, risk/
  vague/mode badges render as a neutral pill with a colored dot + colored label
  text (`Pill`/`RiskPill`/`VagueBadge`/`ModeBadge` unchanged in signature/usage
  except `Pill` now takes `{ fg, label }` instead of `{ bg, border, fg, label }`),
  and the report has a subtle fade/rise reveal on first render (skipped under
  `prefers-reduced-motion: reduce`). Component structure, props, data flow, and
  every rendered field are unchanged. `frontend/index.html` no longer references
  the default Vite favicon (no replacement asset added).

## Commands

Backend (from repo root; deps pinned in `backend/requirements.txt`, verified against
a clean venv on Python 3.10 and a conda env on Python 3.11; TASK-009 re-verified the
plain-venv path end-to-end from a clean working-tree copy):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
```

(The README also documents conda as an alternative; any Python 3.10+ environment with
`backend/requirements.txt` installed works. README's quickstart leads with plain `venv`
as of TASK-009 since it's more universal than assuming conda is installed.)

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host   # dev server, usually http://localhost:5173
npm run build
npm run lint            # eslint; only frontend check that exists
```

Logs:

```bash
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
```

Eval (deterministic Layer A runner, QC-3B; from repo root, `backend/requirements.txt`
installed):

```bash
python -m eval.run_eval --validate-only        # corpus validation only, no analyzer
python -m eval.run_eval --mode demo            # zero-cost deterministic run
python -m eval.run_eval --mode openai --allow-paid   # billed; explicit opt-in only
python -m unittest discover -s eval/tests -p 'test_*.py' -v
```

`--mode demo` exits non-zero today: the corpus targets the product contract, not the
Demo stub, so known gaps surface as real failures (see *Added in QC-3B*).

Modes: no `backend/.env` file is required to run in Demo mode — it's the default
with zero setup. To switch modes explicitly, copy `backend/.env.example` to
`backend/.env`; `QUOTECHECK_USE_OPENAI=0` (default) = Demo mode (stub analyzer,
no API key), `=1` = OpenAI mode (requires `OPENAI_API_KEY`).

## Capabilities

- `/analyze` returns a schema-valid, explanation-first structured result. Each
  `LineItem` carries a plain-English `explanation` (what the item is and why a vendor
  might recommend it, distinct from the risk-focused `rationale_short`) and an
  explicit `vague_or_confusing` flag, in addition to category/risk/action/evidence.
- Every response's `metadata.model` honestly identifies which analyzer produced it:
  `quotecheck-demo-analyzer` in Demo mode, the configured `QUOTECHECK_MODEL` (e.g.
  `gpt-4o-mini`) in OpenAI mode. The frontend shows this as a "Demo mode" / "OpenAI
  mode" badge; the same value is also what gets written to `logs/app_runs.jsonl`.
- Demo/stub mode (deterministic keyword heuristics, TASK-008 broadened beyond
  vehicle-only): brake → safety-critical/red; tyre → safety-critical/yellow; AC/
  appliance terms (air conditioning, compressor, refrigerant, hvac, appliance) →
  wear-and-tear/yellow with appliance-appropriate evidence requests; home-maintenance
  terms (plumbing, electrical, contractor, handyman, renovation) →
  preventive-maintenance/green with scope-of-work evidence requests; generic/
  un-itemized terms (misc, labour/labor, service charge, gas top-up, consumables,
  other/unitemized charges) → a conservative "Other/unspecified charges" catch-all
  with `vague_or_confusing=true`, independent of any other match, so those charges
  are surfaced instead of silently dropped; else a single "needs clarification" item.
  Top-level `overall_summary`/`disclaimer` text is domain-generic by default (e.g.
  "verify with a qualified professional"), with vehicle-specific phrasing
  ("brakes/tyres", "certified mechanic") only added when a vehicle item actually
  matched — no more asserting vehicle language on a non-vehicle quote.
  `verification_questions` and `things_to_verify` are built per-domain from the
  same matched keyword blocks (vehicle/AC/home-maintenance/generic-charge, each
  combining additively when more than one matches, e.g. a vehicle quote with a
  bundled charge gets both chunks) so the two bottom report sections are
  domain-specific and non-duplicate content rather than fixed boilerplate; only the
  true no-match fallback (nothing domain-specific detected) uses plain clarifying
  questions. This is still keyword matching, not a real line-item parser/extractor
  or NLP.
- OpenAI mode is implemented (strict structured outputs + Pydantic validation).
- Frontend renders the full result as a quote-understanding report (explanation
  prominent per line item, vague/confusing charges visibly badged, verification
  questions and things-to-verify grouped with vendor-facing headers) and can copy
  raw JSON.
- Every request logs one JSONL record (request_id, prompt_version, model, latency,
  schema_valid, risk counts, uncertainty, error).
- Secrets hygiene: `backend/.env` and `logs/` are gitignored and untracked.
- `examples/` sample/eval pack (TASK-008): 6 real captured Demo-mode input/output
  pairs spanning vehicle service, AC/appliance repair, home maintenance/contractor,
  a vague-labour/misc parts quote, and a genuinely vague quote (uncertainty
  fallback), indexed in `examples/README.md`. Demo mode only, no OpenAI calls; not
  an automated eval harness (no pass/fail scoring, no CI) — see Roadmap item 2 in
  `README.md`.
- Project-status/run docs (TASK-010): `docs/PROJECT_STATUS.md` (public-ready vs.
  still-limited vs. not-to-overclaim summary) and `docs/LOCAL_DEMO.md` (neutral local
  run guide: start backend/frontend, verify `/health` and `/analyze`, optional OpenAI
  mode), both linked from README's Limitations section. A real UI screenshot is
  committed at `docs/assets/quotecheck-ui.png` and embedded in `README.md`.

## Gaps

- No committed `environment.yml`/lockfile — only a pinned `backend/requirements.txt`.
  Reproducibility depends on the developer activating a compatible Python 3.10+
  environment themselves (README documents a conda-based path).
- No backend tests and no CI. A deterministic eval/regression runner exists
  (`eval/`, QC-3B) and has stdlib self-tests, but semantic grading remains manual,
  and the application-level Demo gaps its baseline reveals are unresolved.
- No verified public deployment.
- No repair/retry when model output fails schema validation.
- Paste-text input only: no PDF/OCR, no auth/users/DB.
- The deterministic Demo analyzer and the shared `NormalizedCategory` taxonomy
  remain narrower than the general service / repair / parts / vendor product scope,
  and carry vehicle-era wording. The OpenAI-mode prompt's copy was made domain-generic
  in TASK-012 (see below), but the taxonomy itself is unchanged. The Demo-mode stub's
  keyword coverage was broadened in TASK-008 (vehicle, AC/appliance, home maintenance)
  but is still a small fixed keyword list, not real language understanding, and only
  covers Demo mode.
- No market-price benchmarking and no objective price-fairness judgment anywhere in
  the system.
- No verification of vendor claims against external authoritative sources.
- Stub's generic-charge catch-all is a fixed keyword list, not real line-item
  extraction; a quote whose vague charges don't match one of those keywords still
  falls through to the single generic "needs clarification" item.
- Missing information is represented at the top level (`things_to_verify`,
  `missing_quote_context`) rather than per line item.

### Added in QC-3B

An **executable deterministic eval / regression runner** for the QC-3A corpus. It is
Layer A only — it measures nothing semantic. **No `backend/`, `frontend/`, or
`examples/` code changed; no corpus expectation changed; no dependencies added.**

What now exists:

- `python -m eval.run_eval` — loads and **permanently validates** the 27-case corpus
  (parse, unique `case_id`, closed domain/category enums, exact deterministic-check
  shapes, termset resolution, single-source termset mode, no duplicate quote text,
  REG-001/REG-002 exactly once, corpus size 24–30, and the QC-3A category →
  expectation consistency rules), then runs each selected case through the real route
  handler `backend.app.analyze` and grades it.
- **Zero-cost Demo mode** (`--mode demo`, the default): no OpenAI calls.
- **Explicit paid boundary**: `--mode openai` exits before any billed inference unless
  `--allow-paid` is passed; then it prints the case count, model, and a billing
  warning first.
- **Deterministic graders** for exactly the vocabulary the corpus uses: `schema_valid`
  (independent Pydantic re-validation), `metadata_complete` (provenance + completeness,
  one result per sub-assertion, `prompt_version` compared to `backend.core.prompt`
  rather than hardcoded), `forbidden_terms` (shared termsets only; `absolute` and
  `not_in_source` modes; case-insensitive whole-word/phrase matching over the
  `analysis_text` field group, `name_raw` excluded), `uncertainty_marker`, and
  `line_items_where` (`vague_or_confusing` / `evidence_needed_nonempty`, `min_count`).
  Every assertion emits an interpretable `CheckResult` with expected / observed /
  message.
- **Artifacts**: timestamped `eval/results/run_<UTC>.jsonl` (one record per case) and
  `eval/results/summary_<UTC>.md` (rates, failures by domain and category, per-failed-
  case reasons, explicit REG-001/REG-002 status, latency, human-review boundary,
  fixed interpretation-boundary note). One failing case never aborts the suite; a
  malformed corpus aborts before any analyzer call.
- **Exit semantics**: `0` only if every selected case passes deterministic evaluation;
  non-zero otherwise, with artifacts written first. No `--ignore-failures`, no xfail.
- **First committed Demo baseline**: `eval/results/summary_20260829T105921Z.md` —
  27/27 schema-valid; 11/27 deterministic cases pass. The 16 failures are the
  already-documented Demo-mode gaps above (e.g. `ambiguous_items_present` hardcoded
  `true`); they are retained, not excluded.
- **Automated tests for the grader machinery**: `python -m unittest discover -s
  eval/tests -p 'test_*.py' -v` (stdlib `unittest`, no test dependency added).

What does **not** exist:

- No semantic (Layer B) auto-scoring — `semantic_expectations` are never machine-checked;
  the rubric in `eval/rubric.md` is still a manual pass.
- No CI wiring.
- No new model-quality, accuracy, hallucination, or production-readiness claim. A
  Layer A pass rate is not a quality number.

### Added in QC-3A

Evaluation specification and case corpus, written before the runner so QC-3B targets a
contract that was decided deliberately rather than inferred from whatever the code
happens to do. **No application source, examples, logs, or config behaviour changed.**

What now exists:

- `eval/README.md` — the evaluation specification: the Layer A (deterministic
  invariants) vs. Layer B (semantic judgment) split, the case-file format, the
  deterministic check vocabulary, an honest per-check statement of which checks are
  robust and which are proxies, the corpus coverage tables, the two historical
  regression cases, current non-goals, and what QC-3B may and may not do with the
  results.
- `eval/rubric.md` — a human semantic rubric: six dimensions (Faithfulness, Unsupported
  inference, Uncertainty calibration, Explanation quality, Actionability,
  Professional-boundary discipline) on a 0/1/2 scale with each level defined.
  Faithfulness and Unsupported inference are gates: a 0 on either fails the case
  regardless of the other four scores. Scores are reported as per-dimension
  distributions; averaging the six dimensions into a single number is explicitly
  prohibited.
- `eval/cases/*.json` — **27 synthetic cases**, one JSON file per case, spanning six
  domains: automotive 5, hvac_appliance 5, contractor_vendor 5, plumbing_home 4,
  electronics_repair 4, generic_service 4. Nine categories are covered:
  price_present 10, missing_scope_or_quantity 9, clean_itemized 6,
  vague_bundled_charge 6, conditional_work 5, cross_domain_trap 5,
  professional_confirmation_expected 4, professional_confirmation_not_expected 4,
  noisy_input 3. Every quote is synthetic with fictional vendor names and no personal
  data. Every case carries a stable `case_id`, a one-sentence `rationale`, deterministic
  expectations, and semantic expectations.
- **Permanent historical regression cases.** `REG-001` guards HVAC → vehicle/mechanic
  domain leakage (the TASK-012 failure), asserted against inappropriate leakage rather
  than the deleted `missing_vehicle_context` field name, which no longer exists.
  `REG-002` guards unsupported market-price/fairness judgment (the "quite high" failure)
  on a quote carrying deliberately large amounts.
- `eval/termsets.json` — three shared forbidden-term sets (`price_judgment`,
  `vehicle_domain`, `trade_domain`). Each termset's match `mode` is defined here and
  only here; case files reference a termset by name and never restate its mode.
- **Deterministic expectations designed for QC-3B**: six check types
  (`schema_valid`, `metadata_complete`, `forbidden_terms`, `uncertainty_marker`,
  `line_items_where`, `topic_present`), three of them applied as global invariants to
  every case. Matching is case-insensitive whole-word, never substring. No
  exact-output golden files were introduced.

Deliberate design decisions recorded in `docs/tickets/QC-3A-eval-spec-and-corpus.md`:
the `price_judgment` termset is high-precision rather than comprehensive (bare
"expensive"/"fair price" false-positive on correct boundary language such as "QuoteCheck
cannot determine whether this is a fair price", and a negation parser is not worth
building); nuanced price-fairness language stays with the semantic rubric; and category
tags carry mandatory matching assertions so they cannot become decorative.

What does **not** exist:

- **No executable eval runner.** Nothing in `eval/` runs. QC-3B owns the runner and any
  `results/` artifacts.
- **No automated scoring**, no pass rates, no CI, no `results/` directory.
- **No new model-quality claims.** This ticket produced a specification and inputs; it
  measured nothing and says nothing about how well QuoteCheck currently performs.

The corpus deliberately targets the intended product contract, not the Demo stub's
keyword heuristics, so Demo mode will fail some cases by construction — most visibly the
six `clean_itemized` cases, since `stub_analyzer.py` hardcodes
`ambiguous_items_present = True` (see the QC-1B block below). Those are real,
already-documented gaps left in as signal; `eval/README.md` records that QC-3B must
report per mode and must not xfail or exclude them from pass-rate denominators.

`README.md` received a minimal truth-maintenance edit only (Evaluation section, repo
tree, Roadmap item 2). `SPEC.md` was inspected and needed no change.

### Fixed in QC-1B

Small contract / provenance hardening before the eval harness (QC-3) is built. No
new product capability; `NormalizedCategory` deliberately untouched.

- **Domain-neutral uncertainty contract.** `UncertaintyMarkers` fields
  `missing_vehicle_context` → `missing_quote_context` and
  `needs_mechanic_confirmation` → `needs_professional_confirmation`
  (`backend/core/schema.py`), each with a precise `Field(description=...)`. No
  back-compat aliases (there are no known consumers). New semantics:
  `missing_quote_context` = the quote omits contextual information needed to
  interpret one or more recommendations confidently (scope, symptoms, quantities,
  diagnostic basis, other material detail) — not a synonym for "contains a vague
  line item"; `needs_professional_confirmation` = one or more technical or
  safety-sensitive recommendations should be confirmed by an appropriate qualified
  professional, stated domain-neutrally.
- **Prompt.** `backend/core/prompt.py` `DEVELOPER_PROMPT` now instructs both new
  fields with domain-generic wording and no assumed trade; the price-benchmarking /
  fairness prohibition and the rest of the prompt are unchanged. `PROMPT_VERSION`
  bumped `quotecheck_v0.3` → `quotecheck_v0.4` (renamed, redefined model-visible
  output fields).
- **Demo uncertainty behavior.** `backend/core/stub_analyzer.py` no longer
  hardcodes `missing_vehicle_context=True` / `needs_mechanic_confirmation=True`.
  Deterministic, transparent heuristics instead: `missing_quote_context` is `true`
  only when the quote text contains an explicit missing/deferred/externalised-context
  phrase (fixed `MISSING_CONTEXT_PHRASES` substring list) **or** the quote resolves
  to nothing but generic/bundled charges with no substantive service item; failing
  to recognise a domain alone never sets it. `needs_professional_confirmation` is
  `true` when a line item is `red` risk or `safety_critical` category (keys off
  risk/category, never a trade name). `ambiguous_items_present` is unchanged
  (still constant `true` — deliberately out of QC-1B scope).
- **Failure provenance.** `backend/app.py` failure-path logging is now mode-aware:
  a Demo-mode failure logs `model = quotecheck-demo-analyzer` (was always
  `gpt-4o-mini`); an OpenAI-mode failure logs the configured `QUOTECHECK_MODEL`.
  No new field, no `run_logger.py` change.
- **Misleading fallback wording.** `stub_analyzer.py` module docstring no longer
  says it "provides a deterministic fallback if OpenAI is unavailable" — the
  analyzer is selected once by configuration and an OpenAI failure returns an
  error, it does not switch to the stub. Comment-only.
- **Dead schema plumbing removed.** `build_messages()` never used its `schema_json`
  argument; removed it, plus the now-orphaned
  `schema_export.quotecheck_result_schema_json()` helper and its call in
  `openai_analyzer.py`. The only Structured Outputs path is unchanged:
  `QuoteCheckResult` → `quotecheck_result_schema_obj()` →
  `client.responses.create(... text.format.schema ...)`.
- **Examples regenerated.** All six committed Demo outputs
  (`examples/sample_output.json`, `examples/outputs/*.json`) were regenerated by
  replaying their unchanged input files through the real Demo-mode `/analyze`
  endpoint (`QUOTECHECK_USE_OPENAI=0`, no API call). Every file validates against
  `QuoteCheckResult`, reports `metadata.model = quotecheck-demo-analyzer` and
  `prompt_version = quotecheck_v0.4`, carries the new uncertainty field names, and
  no longer contains the stale `quotecheck_v0.2` / `v0 prototype` wording that the
  previous captures still had. New deterministic `missing_quote_context`:
  `false` for the two vehicle quotes and the AC quote; `true` for the
  home-maintenance, parts/labour-misc, and vague-missing-details quotes.
  `needs_professional_confirmation`: `true` for the two vehicle quotes (brake =
  red / safety_critical), `false` for the rest.
- No frontend change (`frontend/src/App.jsx` never referenced the uncertainty
  markers). No dependency, deployment, eval-harness, retry, or taxonomy work.

### Fixed in QC-1A

Documentation truth-alignment pass — no source code, examples, logs, or config
behaviour changed. Public docs now describe only the current implemented system.

- `README.md`: retitled to "QuoteCheck — Service Quote Review Assistant"; removed the
  "v0" product framing and the "v0 prototype" disclaimer wording; replaced the
  "vehicle-service-flavored" scope paragraph with an accurate split (the OpenAI path
  and its prompt are domain-generic; the Demo heuristics and the `NormalizedCategory`
  taxonomy are narrower, with vehicle-era wording); added an explicit
  product-boundary list (no market-price benchmarking, no price-fairness judgment, no
  vendor-trust scoring, no external claim verification); rewrote Architecture to show
  the real configuration-selected single-analyzer flow and that an OpenAI failure
  returns an error rather than switching to Demo; added "OpenAI mode" (Responses API
  + Structured Outputs generated from the Pydantic contract, `gpt-4o-mini` default),
  "Demo mode" (deterministic, zero-key, heuristic — not equivalent to OpenAI mode),
  and "Evaluation" (six captured examples, schema validation, historical manual QA;
  no automated harness) subsections; tightened Limitations; removed the
  `eval/ (coming next)` line from the repo tree (no such directory exists).
- `SPEC.md`: removed "optional market price checks" from present-tense positioning;
  broadened positioning to service/maintenance/repair/parts/vendor review;
  distinguished the domain-generic OpenAI prompt from the narrower Demo
  heuristics/taxonomy; expanded non-goals (price fairness, vendor verification);
  replaced "v0 prototype" limitation wording with "early-stage implementation".
- `docs/PROJECT_STATUS.md`: dropped "v0" from the title; corrected the claim that the
  OpenAI-mode prompt is vehicle-service-flavored; replaced "No screenshot committed
  yet" with the committed `docs/assets/quotecheck-ui.png`; added a compact "Planned
  hardening (not yet built)" list.
- `docs/LOCAL_DEMO.md`: rewrote the screenshot section (screenshot is now committed;
  corrected the stale `quotecheck-demo-ui.png` filename to `quotecheck-ui.png`);
  added `npm install` to the frontend run steps.
- `docs/CURRENT_STATE.md`: this entry; updated the `Last updated` line; corrected the
  OpenAI-path and screenshot facts; added "no verified public deployment" and vendor
  /price-fairness bullets to Gaps.
- `CLAUDE.md`: removed the stale "v0 prototype" and "optional market price checks"
  product wording from the intro paragraph only. Coding-workflow, agent-instruction,
  and build-protocol sections were not touched.

No QC-1B / QC-3 / QC-4 work exists yet. The stale `quotecheck_v0.2` example outputs
under `examples/` were intentionally left unchanged (regeneration is out of scope for
QC-1A). Known implementation issues (e.g. `missing_vehicle_context` /
`needs_mechanic_confirmation` hardcoding in the Demo stub, no repair/retry, no eval
harness) were documented here honestly, not fixed.

### Fixed in LUXURY-UI-001

- `frontend/src/App.jsx`: extracted inline JSX style objects into CSS classes
  (`frontend/src/index.css`) so the report reads as a calm review document
  rather than a generic component-library UI. Added a document-style report
  header (title + risk-tally chips, same client-side `riskCounts` computation
  as before) replacing the bare `h2`+inline-strip; section labels ("Line
  items, explained", "Before you approve") restyled as small-caps labels.
  `Pill` (and `RiskPill`/`VagueBadge`/`ModeBadge`, which call it) restyled from
  a filled-tint badge to a neutral pill with a colored dot + colored label
  text; `Pill`'s prop shape changed from `{ bg, border, fg, label }` to
  `{ fg, label }` (internal to `App.jsx`, not a public/API change).
  `getRiskColors()` no longer returns an unused `bg` field. Component
  structure (`App`, `LineItemCard`, `Pill`/`RiskPill`/`VagueBadge`/`ModeBadge`,
  `Card`), all props consumed from `/analyze` responses, and all rendered
  fields are unchanged.
- `frontend/src/index.css`: replaced the Tailwind-blue accent (`#2563eb`) with
  a deep ink-teal (`--accent: #0f4c46`); added a spacing scale
  (`--space-1`..`--space-7`), radius tokens, and warmed the background/border
  tokens slightly; added the new component classes referenced above
  (`.qc-*`); kept `.two-col-grid` and `.status-pulse` (existing selectors,
  refined colors only); added a report-reveal fade/rise animation gated on
  `prefers-reduced-motion: no-preference`. No new dependencies (no fonts, no
  icon libraries).
- `frontend/index.html`: removed the default Vite favicon `<link>` reference
  (no replacement asset added — none was approved); title and viewport meta
  unchanged.
- No backend changes; `/analyze` request/response shape and every currently
  rendered field are unchanged; sample quote text, loading-stage labels,
  timeout logic, error-kind copy, and mode-badge logic are all unchanged. See
  `docs/review/REVIEW_BUNDLE__LUXURY-UI-001-distinctive-public-ui.md` for
  exact validation commands/output and manual-browser-check evidence.

### Fixed in TASK-012

- `backend/core/prompt.py`: reworded `SYSTEM_PROMPT`/`DEVELOPER_PROMPT` (OpenAI mode
  only) to remove leftover vehicle/mechanic bias found via manual testing with a
  non-vehicle AC repair quote. `SYSTEM_PROMPT` now states the assistant's scope
  covers repair/maintenance/parts/vendor quotes "across any domain ... — not
  vehicle-only". `DEVELOPER_PROMPT` changes: (1) `missing_vehicle_context` is only
  set `true` when the quote is clearly vehicle-related and vehicle context is
  actually missing, and must be `false` for every other domain (previously the
  instruction only ever said when to set it `true`, defaulting the model toward
  `true` on non-vehicle quotes); (2) the model is now explicitly told not to
  describe a quote/charge as high/low/fair/cheap/expensive/overpriced/underpriced
  without benchmarking data (which is not implemented), and to phrase pricing
  uncertainty as "needs clarification"/"verify the basis for this charge" instead;
  (3) the disclaimer instruction no longer hardcodes "verify with a certified
  mechanic" — it now uses generic professional-advice wording by default and only
  names a specific professional for clearly vehicle-related quotes.
  `PROMPT_VERSION` bumped `quotecheck_v0.2` → `quotecheck_v0.3`.
- `backend/core/stub_analyzer.py`: inspected, no changes needed — its disclaimer
  and per-domain professional wording were already generalized in TASK-008/
  TASK-008A. Out-of-scope observation: demo-mode uncertainty markers still use a
  broad default for `missing_vehicle_context`. This ticket focuses on OpenAI
  prompt behavior before recording and does not regenerate deterministic demo
  outputs.
- No schema, frontend, or dependency changes. `/analyze` request/response shape is
  unchanged; this only changes what OpenAI mode is instructed to output. See
  `docs/review/REVIEW_BUNDLE__TASK-012-openai-generic-service-copy.md` for exact
  validation commands/output.

### Fixed in LUXURY-UI-001A

- `frontend/src/App.jsx`: removed the "v0 prototype" chip from the app header
  (it no longer appears next to the QuoteCheck wordmark anywhere in the UI).
  Restructured the header into a three-line hierarchy — `h1` wordmark, a new
  `qc-header__subhead` ("Understand quotes before you approve them."), and a
  `qc-header__intro` body paragraph (reworded from the prior single tagline) —
  replacing the old wordmark+chip row and single tagline `div`. No other JSX
  changed: input card, loading, error card, report, footer, and every
  component (`LineItemCard`, `Pill`/`RiskPill`/`VagueBadge`/`ModeBadge`,
  `Card`) are unchanged; the Demo/OpenAI mode badge still renders in the
  report footer.
- `frontend/src/index.css`: removed `.qc-chip` and `.qc-header__title-row`
  (both dead after the chip removal); added `.qc-header__subhead` and
  `.qc-header__intro` (replacing `.qc-header__tagline`); the intro
  paragraph's prior `max-width: 62ch` cap was dropped so it spans the same
  width as the input card and report below — header, intro copy, input card,
  and report title now share one left-aligned grid inside `.qc-shell`
  (verified via headless-browser bounding-rect checks; all four sit at the
  same left edge). Overall page width is still bounded by `.qc-shell`'s
  existing `max-width: 880px` — nothing was made full-width.
- `backend/core/stub_analyzer.py` (tiny copy-only exception, approved for this
  ticket): the Demo-mode `disclaimer` and one `overall_summary` line were the
  only place the "v0 prototype" phrase was still visibly rendered in the
  product UI (in the report footer / Summary card, sourced from the backend
  response) — the header-only fix above didn't touch it. Reworded both
  strings to drop "v0 prototype"/"prototype" while preserving the same
  limitations: the disclaimer now reads "QuoteCheck results may be incomplete
  or wrong. This analysis is informational and should not replace
  professional advice, official estimates, warranty terms, or a second
  opinion for high-value or safety-critical work — verify with a
  {professional}. QuoteCheck explains quotes and suggests questions; it does
  not verify vendor claims, guarantee fair pricing, or perform price
  benchmarking."; the summary line now reads "Price benchmarking is not
  implemented; no market price comparison is being made." Copy-only: no
  schema change, no `/analyze` behavior change, no analyzer logic change
  (the dynamic `{professional}` selection is unchanged), no new fields.
  `backend/core/prompt.py` (OpenAI-mode prompt) was checked and does not
  reference "prototype" anywhere, so it was left untouched, per the same
  exception's scope.
- No other backend/API/schema change; `/analyze` request/response shape and
  every rendered field are otherwise unchanged; no new dependencies. See
  `docs/review/REVIEW_BUNDLE__LUXURY-UI-001A-final-header-alignment-polish.md`
  for exact validation commands/output and manual-browser-check evidence
  (including screenshots).

### Fixed in TASK-010A

- `README.md`: reframed the README design-rationale section under a neutral
  "Design notes" heading. The prior heading framed the project's engineering
  choices as credibility proof rather than stating them plainly; the underlying
  factual content (schema-first API responses, deterministic Demo mode, optional
  OpenAI mode, structured/reviewable report sections, JSONL request logs, honest
  limitations) is preserved, just restated as plain design choices with a link to
  `docs/PROJECT_STATUS.md`. No other README section changed.
- No backend/frontend/example-output changes; no new dependencies.

### Fixed in TASK-010

- Added `docs/PROJECT_STATUS.md` (new): a neutral summary of what's public-ready
  today, what's still limited, and what should not be overclaimed — written from
  direct inspection, cross-linking `docs/CURRENT_STATE.md` for the full technical
  baseline rather than duplicating it.
- Added `docs/LOCAL_DEMO.md` (new): a neutral local run guide (start backend in Demo
  mode, verify `/health`, run `/analyze` with an explicit repo-root reminder, start
  frontend, test the UI, optional OpenAI mode, screenshot capture location). An
  earlier draft of this ticket also added a presenter-style `docs/DEMO_CHECKLIST.md`
  and a scripted `docs/DEMO_SCRIPT.md`; per user direction both were dropped —
  `DEMO_SCRIPT.md` was deleted outright (presenter/audience framing doesn't belong in
  a public repo) and `DEMO_CHECKLIST.md` was reframed and renamed to the neutral
  `LOCAL_DEMO.md` above.
- Renamed the public-readiness summary from `docs/PUBLIC_READINESS_REVIEW.md` to
  `docs/PROJECT_STATUS.md` (content unchanged apart from the title/heading) — a more
  normal name for a public-repo status doc.
- Added `docs/assets/.gitkeep` (new): no real screenshot exists yet, so no image was
  added — this only reserves the directory. No placeholder or mocked-up image was
  created, per the no-fake-assets constraint.
- `README.md`: added an explicit "run this from the repo root" note directly above
  the `/analyze` curl example (it depends on a relative path,
  `examples/quote_ac_repair.txt`); reworded the Screenshot section to state plainly
  that no placeholder image is used and link to
  `docs/LOCAL_DEMO.md#8-screenshot-capture-location`; added a paragraph in the
  Limitations section linking to `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md`, and
  `examples/README.md`; added `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md`, and
  `docs/assets/` to the "Repo structure" tree. No other prose changes.
- Scanned `README.md`, `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md`, and
  `docs/CURRENT_STATE.md` for private career/outreach context and for embedded
  secrets — none found. See the review bundle for the exact grep commands and output.
- No backend/frontend behavior changes, no new dependencies, no changes to
  `examples/README.md` or `backend/.env.example` (both inspected, found already
  accurate, left unchanged).

### Fixed in TASK-009

- `README.md`: added a missing `git clone` step (`0) Clone`) before the backend
  quickstart — previously the walkthrough started at "From repo root" with no clone
  instructions at all. Swapped the primary backend quickstart from conda-first to plain
  `python3 -m venv` (conda kept as a one-line alternative, not removed) since it's more
  universal for a stranger who may not have conda installed and matches what was actually
  validated below. Added an explicit `QUOTECHECK_USE_OPENAI=0` prefix on the `uvicorn` run
  command so the no-paid-call guarantee is visible in the command itself, not only in
  prose. Added a literal `curl -X POST /analyze` example (against
  `examples/quote_ac_repair.txt`) so Demo-mode analysis is verifiable without opening the
  frontend. Added `backend/requirements.txt` to the "Repo structure" tree. Updated the
  Limitations section's environment-reproducibility note from "conda steps above" to
  "`venv` or conda steps above". No other prose changes; no product/UI/analyzer behavior
  changed.
- Verified the full clean-room setup path end-to-end from a temporary `rsync` copy of the
  working tree at `/tmp/quotecheck-v0-setup-test` (outside the repo; excluded `.git`,
  `node_modules`, `.venv`, `logs`, `backend/.env`) — not a `git clone` of the public
  GitHub remote, because this ticket's doc edits are uncommitted and out of scope forbids
  commits, so a public clone would only have validated the pre-TASK-009 docs. Confirmed:
  `pip install -r backend/requirements.txt` succeeds in a fresh venv with versions
  matching the pins exactly; `python -c "from backend.app import app"` imports cleanly;
  the server starts with `QUOTECHECK_USE_OPENAI=0` and serves `/health` (`{"status":
  "ok"}`) and a real `/analyze` call against `examples/quote_ac_repair.txt`
  (`metadata.model == "quotecheck-demo-analyzer"`, no OpenAI call); `frontend/`
  `npm install` (157 packages) and `npm run build` both succeed. See
  `docs/review/REVIEW_BUNDLE__TASK-009-public-setup-cleanup.md` for exact commands and
  output. A real `git clone` verification of the public remote is a documented follow-up
  for after this branch is merged and pushed — not done as part of this ticket.
- `backend/.env.example` inspected and found accurate/safe already (Demo-mode-needs-no-key
  comment, placeholder key text, safe defaults) — left unchanged, no mismatch found.
- No Makefile/scripts/`docs/SETUP.md`/`frontend/README.md` added: the setup path is fully
  covered by README.md in well under 15 commands once the above fixes landed: adding new
  files would be maintenance surface for marginal benefit. Not ruled out permanently, just
  not justified by this ticket's findings.
- No backend/frontend behavior changes, no new dependencies, no changes to
  `backend/requirements.txt` or `backend/.env.example`.

### Fixed in TASK-008A

- `backend/core/stub_analyzer.py`: `verification_questions`/`things_to_verify` were
  changed from fixed static lists to a new `_domain_questions_and_verification()`
  helper that builds both lists from the same matched keyword blocks (vehicle/AC/
  home-maintenance/generic-charge established in TASK-008), combining additively
  when more than one block matches (e.g. a vehicle quote with a bundled charge gets
  both chunks); only the true no-match fallback (nothing domain-specific detected)
  falls back to plain clarifying questions. Follow-up to TASK-008 after manual UI
  verification showed the two bottom report cards ("Questions to ask the vendor" /
  "Things to verify before approving") read as near-duplicate generic boilerplate
  across every sample domain. `verification_questions` stays within the schema's
  3–8 bound (up to 6 for a quote matching two keyword blocks); `things_to_verify`
  has no upper bound. No change to `backend/core/schema.py`,
  `backend/core/openai_analyzer.py`, `backend/core/prompt.py`, or any frontend file.
- All 6 example outputs (`examples/sample_output.json` and the 5 files under
  `examples/outputs/`) were regenerated from real Demo-mode `/analyze` calls against
  their unchanged input files, so every example now shows domain-specific vendor
  questions and verification items instead of the prior shared boilerplate; all
  still validate against `QuoteCheckResult` with `metadata.model ==
  "quotecheck-demo-analyzer"`.

### Fixed in TASK-008

- `backend/core/stub_analyzer.py`: added deterministic keyword detection for AC/
  appliance repair (`air conditioning`, `air conditioner`, `compressor`,
  `refrigerant`, `hvac`, `appliance`) and home-maintenance/contractor work
  (`plumbing`, `electrical`, `contractor`, `handyman`, `renovation`), each producing
  a domain-appropriate `LineItem` (category, explanation, evidence_needed) the same
  way the existing brake/tyre blocks do. Restructured the top-level
  `overall_summary`/`verification_questions`/`things_to_verify`/`disclaimer` text to
  be domain-generic by default (e.g. "verify with a qualified professional",
  "manufacturer-specified or vendor-suggested" instead of "OEM-specified"), adding
  vehicle-specific phrasing ("brakes/tyres", "certified mechanic") only when a
  vehicle item actually matched — non-vehicle Demo-mode responses no longer assert
  vehicle-specific language. `overall_summary` stays within the schema's 3–5 item
  bound in all cases (3 generic entries, or 4 with the vehicle-specific line
  inserted). No change to `backend/core/schema.py`, `backend/core/openai_analyzer.py`,
  `backend/core/prompt.py` (OpenAI-mode prompt is unchanged), or any frontend file.
  The existing `examples/sample_output.json` (TASK-007) still validates against
  `QuoteCheckResult` after this change (re-checked as a regression test); its exact
  wording now differs slightly from a fresh run's `overall_summary`/`disclaimer`
  text (reordered/reworded, not regenerated as part of this ticket).
- `examples/` sample/eval pack: 5 new realistic input files
  (`quote_vehicle_service.txt`, `quote_ac_repair.txt`, `quote_home_maintenance.txt`,
  `quote_parts_labour_misc.txt`, `quote_vague_missing_details.txt`) each with a real
  captured Demo-mode `/analyze` response under `examples/outputs/` (not
  hand-written), validated against `QuoteCheckResult`. `examples/README.md` (new)
  indexes all 6 examples (including the original TASK-007 sample) and states
  plainly that Demo mode is a deterministic keyword stub (not an LLM), these are
  real outputs, and no price benchmarking or market evidence is implemented.
- `README.md`: added a link to `examples/README.md` near the existing sample-report
  excerpt, and listed the new `examples/` files in the "Repo structure" tree. No
  other prose changes.
- No frontend changes, no OpenAI-mode calls made, no new dependencies.

### Fixed in TASK-007

- `README.md`: rewritten for a general public audience. Now opens with a "what /
  who / why" product framing before any setup or architecture detail (previously led
  with an engineering-tooling bullet list). Adds a "What a report looks like" section
  with a real Demo-mode excerpt plus links to new `examples/` files, a "Screenshot"
  placeholder section (no screenshot committed — no headless-browser tooling is
  installed and adding one would be a new dependency, out of scope), and a design-
  rationale section (schema-first contract, honest mode labeling, JSONL
  observability, ticket/review-bundle discipline; reframed under a neutral "Design
  notes" heading in TASK-010A). Setup steps now explicitly state
  the backend requires an activated Python environment and that no
  `environment.yml`/lockfile is committed (only pinned `backend/requirements.txt`);
  this reproducibility gap is also called out in the Limitations section. No setup
  commands changed — same conda/pip/uvicorn/npm steps as before, just framed more
  explicitly.
- `examples/sample_quote.txt` (new): the frontend's existing built-in sample quote
  text, copied verbatim so docs stay in sync with what a visitor sees in the app.
- `examples/sample_output.json` (new): a real `POST /analyze` response captured by
  running the backend in Demo mode (`QUOTECHECK_USE_OPENAI=0`, the default) against
  `examples/sample_quote.txt`. Confirmed `metadata.model ==
  "quotecheck-demo-analyzer"`. Not hand-written; `request_id`/`created_at`/
  `latency_ms` will differ on a fresh run, noted in the README.
- No backend/frontend behavior changes. No new dependencies. No
  `docs/ARCHITECTURE.md` added (existing inline README diagram judged sufficient at
  this size).

### Fixed in TASK-006

- `backend/core/config.py`: added `DEMO_ANALYZER_MODEL = "quotecheck-demo-analyzer"`,
  a fixed label distinct from `MODEL`/`QUOTECHECK_MODEL`.
- `backend/core/stub_analyzer.py`: `MetaData.model` now uses `DEMO_ANALYZER_MODEL`
  instead of `MODEL`. Previously, stub-mode responses (and their
  `logs/app_runs.jsonl` entries) reported `model: "gpt-4o-mini"` even though no
  OpenAI call was made — misleading for a public demo and inconsistent with
  SPEC.md's honest-limitation-language principle. OpenAI mode is unchanged (still
  reports the real configured model).
- `frontend/src/App.jsx`: added a small `ModeBadge` (built on the existing `Pill`
  primitive) next to the run-metadata footer line, reading "Demo mode" when
  `metadata.model === "quotecheck-demo-analyzer"`, else "OpenAI mode". No other
  UI, loading/error, or `/analyze` request/response change.
- `README.md`: added an explicit "no OpenAI API key needed" callout near the top,
  clarified the Demo-mode-first walkthrough (no `backend/.env` required), and
  renamed "stub mode" to the product-facing "Demo mode" throughout the prose
  (internal code identifiers — `QUOTECHECK_USE_OPENAI`, `stub_analyzer.py`,
  `analyze_quote_stub` — are unchanged).
- `backend/.env.example`: clarifying comment that Demo mode needs no key and no
  `.env` file at all; no functional change.
- No new dependencies; no changes to `backend/app.py`,
  `backend/core/openai_analyzer.py`, `backend/core/schema.py`,
  `backend/core/prompt.py`, or the `/analyze` request/response shape.

### Fixed in TASK-005

- `frontend/src/App.jsx`: the ~20s real-LLM-mode wait now has staged, honest
  feedback instead of a static "Analyzing your quote…" line. A stage label
  ("Reading the quote…" → "Identifying line items…" → "Checking for vague or
  risky charges…" → "Preparing your report…") advances based on elapsed time
  (client-side simulation — the backend makes a single blocking LLM call with
  no real progress signal, so this is explicitly not claimed as true backend
  progress) alongside a live elapsed-time counter; both are inside an
  `aria-live="polite"` status region. Past ~20s a "still working" hint appears
  instead of a fake final stage. Requests now abort client-side via
  `AbortController` after 55s with a dedicated timeout message; `err` state
  changed from a plain string to `{ kind, message }` so network-unreachable,
  timeout, non-2xx HTTP, and other errors each get distinct copy (the "check
  the backend is running on port 8000" hint now only shows for HTTP/other
  errors, not for the already-self-contained network/timeout messages). No
  backend changes, no new dependencies, `/analyze` request/response shape
  unchanged, sample quote and full report rendering (including raw JSON/Copy)
  unchanged.

### Fixed in TASK-004

- `frontend/src/index.css`: replaced the stock Vite template theme (dark
  `#242424` default under `prefers-color-scheme: dark`, `body` flex-centering,
  `3.2em` h1) with a single light-only design-token set (`--bg`, `--surface`,
  ink/border/accent, per-risk color triples, vague/error colors) plus small
  helpers (`.two-col-grid` responsive collapse, `.status-pulse` loading
  animation). `frontend/src/App.css` (dead, unimported since before TASK-003)
  deleted.
- `frontend/src/App.jsx`: visual restyle only — no data-flow change. Header now
  reads "QuoteCheck" with a "v0 prototype" chip; input is a card with helper
  text; a real loading indicator (pulse bar + status text) supplements the
  button label; a styled error card replaces bare `crimson` error text; the
  report gained a derived risk-count strip (computed client-side from existing
  `line_items`, e.g. "3 items · 1 high risk · 1 caution · 1 needs
  clarification"); line-item cards gained a risk-colored left border and
  semantic risk-badge wording ("High risk" / "Caution" / "Low risk" instead of
  "RED"/"YELLOW"/"GREEN"); the two checklist cards are now grouped under a
  "Before you approve" heading with a responsive 2→1 column collapse; raw JSON
  moved into a collapsed-by-default `<details>` block (Copy JSON button inside
  it) while the disclaimer stays visible without expanding anything.
  `frontend/index.html` title changed from the default "frontend" to a real
  page title. `/analyze` request/response shape, `Pill`/`Card`/`RiskPill`/
  `VagueBadge`/`LineItemCard` props, and the prefilled sample quote are all
  unchanged. No backend files touched; no new dependencies.

### Fixed in TASK-003

- `frontend/src/App.jsx`: replaced the flat line-item `<table>` with one card per
  line item so `explanation` (already returned by the backend since TASK-002, but
  never rendered) is now the prominent, human-readable field; `rationale_short` is
  shown as secondary risk reasoning; a new "NEEDS CLARIFICATION" badge
  (`VagueBadge`, built on a generalized `Pill` primitive shared with `RiskPill`)
  appears when `vague_or_confusing` is true; `evidence_needed` is now rendered as a
  secondary bullet list per item (previously unrendered). The Summary card moved
  above the line items; "Verification questions" / "Things to verify" cards were
  relabeled "Questions to ask the vendor" / "Things to verify before approving".
  Default sample quote text updated to include a generic-charge keyword ("misc")
  so the out-of-box demo shows all 3 stub items (brake/tyre/other-unspecified)
  including the vague badge. No backend files changed; `/analyze` response shape
  is unchanged — this only renders fields the backend already returns.

### Fixed in TASK-002

- `backend/core/schema.py`: `LineItem` gained `explanation` (plain-English
  understanding, distinct from the risk-focused `rationale_short`) and
  `vague_or_confusing` (explicit flag, independent of `normalized_category`). Both
  are additive with safe defaults (`""` / `false`) for backward compatibility;
  analyzers are required to always populate a non-empty `explanation`.
  `verification_questions` / `things_to_verify` got clarifying descriptions
  (vendor-facing questions vs. missing-information gaps) with no shape change.
- `backend/core/prompt.py`: `PROMPT_VERSION` bumped to `quotecheck_v0.2`; system/
  developer prompts now require explanation-first output per line item, require
  `vague_or_confusing` for generic/bundled charges, and explicitly forbid claiming
  price benchmarking or market-price comparison.
- `backend/core/stub_analyzer.py`: brake/tyre items now include real `explanation`
  text; added an independent, conservative catch-all for generic/un-itemized charges
  (misc, labour/labor, service charge, gas top-up, consumables, other/unitemized
  charges) that no longer gets silently dropped when brake/tyre also match;
  `overall_summary` and `disclaimer` reworded to be explanation-first and to state
  price benchmarking is not implemented (matches SPEC.md's honest limitation
  language).
- `/analyze` response shape is unchanged for all fields the frontend reads
  (`name_raw`, `normalized_category`, `risk_level`, `recommended_action`,
  `rationale_short`, `overall_summary`, `verification_questions`,
  `things_to_verify`, `disclaimer`); the two new fields are additive.

### Fixed in TASK-001

- `backend/requirements.txt` now exists (pinned: fastapi, uvicorn, pydantic, openai,
  python-dotenv); README install step works as written.
- `backend/core/schema.py`: `uncertainty_markers` default_factory kwarg corrected from
  `ambigious_items_present` to `ambiguous_items_present`.
- `backend/core/prompt.py` (`build_messages`): user content now uses real newlines
  instead of literal `\n` / `\N` escape text.
- `README.md` config example corrected from `gpt-40-mini` to `gpt-4o-mini`.
