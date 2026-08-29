# QC-3C — Demo analyzer contract alignment

## 1. Goal

Repair only clearly incorrect or over-broad deterministic behaviour in the Demo
(stub) analyzer that the QC-3B baseline exposes, using that baseline as evidence:

1. `uncertainty_markers.ambiguous_items_present` must be **derived from the line-item
   analysis** (`any(item.vague_or_confusing …)`), never hardcoded `true`.
2. `missing_quote_context` must reflect an observable quote-level context deficiency
   (the quote's own words defer, omit, approximate, or externalise material detail),
   **not** "the domain is unknown", "the quote is short", or an accidental keyword
   match.
3. An unrecognised domain with a genuinely itemised quote must **not** collapse into a
   single vague fallback line item.
4. Genuinely vague / bundled charges must still surface `vague_or_confusing = true`
   with non-empty `evidence_needed`; clean itemised quotes must stay clean.
5. `needs_professional_confirmation` must stay conservative and evidence-based —
   keyed off safety-critical risk/category or a named safety-critical component /
   hazard in the quote, **never** off trade or domain identity.

Quote-level context gaps and line-level vagueness are kept as **separate** signals: a
deferred quote-context phrase never marks a line item vague, and a vague charge label
never sets `missing_quote_context` on its own. `ambiguous_items_present` stays a pure
summary of the produced line items.

This ticket does **not** target 27/27. The named repairs are implemented with small,
explainable rules; the unchanged 27-case corpus is run **once**; the real pass count
is recorded; residual failures are classified and documented, not chased.

## 2. Context

QC-3A defined a frozen, independent 27-case evaluation corpus and human rubric. QC-3B
built the deterministic (Layer A) runner and recorded the first Demo-mode baseline:
**27/27 schema-valid, 11/27 deterministic contract cases pass, 16 fail** — all on
`uncertainty_marker:*` or `line_items_where:vague_or_confusing`. Zero schema /
metadata / forbidden-term failures. REG-001 and REG-002 leakage / price-judgment
guards pass; both REG cases fail only on an uncertainty-marker check.

The 16 failures trace to seven root causes in `backend/core/stub_analyzer.py`:
(1) `ambiguous_items_present` hardcoded `true`; (2) bare `"labour"` / `"labor"` in
the generic vague-charge list matching every ordinary labour line; (3) `"not
included"` matching benign exclusions lists; (4) the generic-charge list too narrow
for real bundled labels; (5) no detection of provisional / deferred pricing language;
(6) unrecognised domains collapsing to one vague fallback; (7)
`needs_professional_confirmation` firing only on `brake` / `tyre`. All 16 are
Demo-analyzer defects or clearly over-broad behaviour — none is an eval-expectation
problem, and the corpus is not changed.

## 3. Strict file scope

Allowed to create:

- `docs/tickets/QC-3C-demo-contract-alignment.md`,
  `docs/review/REVIEW_BUNDLE__QC-3C-demo-contract-alignment.md`
- `eval/tests/test_stub_analyzer.py`
- `eval/results/run_<UTC>.jsonl`, `eval/results/summary_<UTC>.md` (new Demo baseline)

Allowed to edit:

- `backend/core/stub_analyzer.py` — the repairs above
- `examples/*.json` (6 files) — regenerate through the real Demo `/analyze` path so
  the committed outputs match the repaired analyzer. **Scope expansion:** the
  original scope sketch did not list `examples/`; it is added here deliberately
  because QC-3C changes deterministic Demo output and stale examples would make the
  repository internally inconsistent (recorded in the review bundle, §2). Example
  **inputs** (`examples/*.txt`) are not changed.
- `eval/README.md` — latest-baseline pointer only
- `README.md` — Evaluation section (both baselines, truthful)
- `docs/CURRENT_STATE.md` — "Last updated" line, Gaps, `### Fixed in QC-3C`

Not touched:

- `eval/cases/**`, `eval/termsets.json`, `eval/rubric.md`, `eval/graders.py`,
  `eval/corpus.py`, `eval/run_eval.py`
- `backend/core/openai_analyzer.py`, `backend/core/prompt.py` (`PROMPT_VERSION`
  stays `quotecheck_v0.4` — no model-visible output-field or instruction change),
  `backend/core/schema.py`, `backend/app.py`
- `frontend/**`, `SPEC.md`, dependency / deployment files, historical ticket /
  review documents

No new dependencies. Standard library plus the existing Pydantic/FastAPI stack.

## 4. Out of scope

`NormalizedCategory` taxonomy redesign; per-line-item missing-information modelling;
any OpenAI-mode / prompt behaviour change; a general NLP parser, regex invoice
parser, OCR, a domain classifier, or model inference in the stub; semantic (Layer B)
auto-scoring; CI wiring; schema-repair / retry loops; any change to the eval corpus,
termsets, rubric, or grader semantics; a paid OpenAI run; any git commit. Reaching
27/27, or adding heuristics beyond the named repairs to move the pass count.

## 5. Acceptance criteria

1. All 16 QC-3B failures inspected and classified (A/B/C/D) before any edit; the
   classification recorded in the review bundle.
2. Only clearly justified Demo-analyzer defects / over-broad behaviour are repaired.
3. `ambiguous_items_present == any(item.vague_or_confusing for item in line_items)` —
   never hardcoded.
4. `missing_quote_context` has a small, explainable, evidence-based rule: an explicit
   deferred/omitted-detail phrase in the quote, or the analysis resolving to nothing
   but unclear items. It is not set from domain-recognition failure, and it does not
   force line items vague.
5. Unrecognised / generic domains with usable priced detail (≥ 2 priced lines) are
   reproduced line by line, not collapsed into a single generic fallback.
6. Vague bundled charges still yield `vague_or_confusing = true` and non-empty
   `evidence_needed`; the six `clean_itemized` cases produce no vague line item.
7. `needs_professional_confirmation` is `any red/safety_critical line item` or a
   named safety-critical component / hazard term (whole-word). It is not triggered by
   trade or domain identity; the four `professional_confirmation_not_expected` cases
   stay `false`.
8. REG-001 `forbidden_terms:vehicle_domain` guard still passes.
9. REG-002 `forbidden_terms:price_judgment` guard still passes.
10. 27/27 schema validity preserved.
11. The same unchanged 27-case corpus is rerun; `git diff -- eval/cases
    eval/termsets.json eval/rubric.md` is empty.
12. The new deterministic pass count is recorded truthfully as a contract/regression
    pass count (not "accuracy"), with an explicit before/after against QC-3B.
13. Residual failures are enumerated and classified, not hidden or suppressed.
14. Focused Demo-analyzer unit tests added and passing; existing harness self-tests
    still pass.
15. No `eval/cases` / `eval/termsets.json` / `eval/rubric.md` change.
16. No frontend change.
17. No OpenAI analyzer / prompt behaviour change; `PROMPT_VERSION` unchanged.
18. No new dependency.
19. No paid API call.
20. The new Demo baseline artifacts are retained **alongside** the QC-3B baseline
    (`run_20260829T105921Z.*` not overwritten or deleted).
21. Nothing committed — left for user review.

## 6. Commands to run

```bash
# A. syntax
python -m compileall backend eval

# B. all self-tests (existing harness + new Demo-analyzer tests)
python -m unittest discover -s eval/tests -p 'test_*.py' -v

# C. corpus validation only (no analyzer, no network); expect exit 0, "0 errors"
python -m eval.run_eval --validate-only

# D. new Demo baseline (expected: non-zero exit, artifacts still written)
python -m eval.run_eval --mode demo

# E. regenerate the 6 committed Demo examples through the real Demo /analyze
#    (QUOTECHECK_USE_OPENAI=0; no OpenAI; inputs unchanged; each re-validated)

# F. corpus / scope must be unchanged
git diff -- eval/cases eval/termsets.json eval/rubric.md   # must be empty
git diff --check
git status --short
git diff --stat
```

## 7. Definition of done

- All acceptance criteria met, each evidenced in
  `docs/review/REVIEW_BUNDLE__QC-3C-demo-contract-alignment.md` with real command
  output — no placeholders.
- `backend/core/stub_analyzer.py` repairs are small and individually explainable;
  quote-level and line-level uncertainty signals stay separate.
- The unchanged 27-case corpus was rerun once; the real deterministic pass count and
  every residual failure are recorded and classified.
- New Demo baseline (`run_<UTC>.jsonl` + `summary_<UTC>.md`) committed alongside the
  retained QC-3B baseline.
- `examples/*.json` regenerated through the real Demo path; inputs unchanged; each
  re-validated against `QuoteCheckResult`.
- `README.md`, `eval/README.md`, and `docs/CURRENT_STATE.md` (including its "Last
  updated" line) reflect the new baseline as a deterministic contract/regression pass
  count, not an accuracy or quality gain.
- No eval-corpus / termset / rubric / grader change; no OpenAI-mode change;
  `PROMPT_VERSION` unchanged; no new dependency; no paid API call.
- Not committed — left for the user to review and commit manually.
