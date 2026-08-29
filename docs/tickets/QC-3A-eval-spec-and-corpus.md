# QC-3A — Evaluation specification + representative case corpus

## 1. Goal

Define **what** QuoteCheck should be evaluated on and **which inputs** to evaluate it
against, before any runner exists. Specifically:

1. what QuoteCheck should be evaluated on;
2. which cases represent important product behaviours and historical regressions;
3. which checks can be determined mechanically;
4. which qualities require semantic/human judgment.

QC-3B will implement the executable runner against this specification. **This ticket
writes no scoring code and changes no application source.**

## 2. Context

QC-1A aligned public documentation with the real implementation. QC-1B made the
uncertainty contract domain-neutral (`missing_quote_context`,
`needs_professional_confirmation`), fixed analyzer provenance on the failure path, bumped
`PROMPT_VERSION` to `quotecheck_v0.4`, and regenerated all Demo examples.

Systematic evaluation is the next priority. Today the only quality evidence is six
captured Demo-mode examples under `examples/` (no pass/fail semantics) and manual QA in
`docs/review/`. Two real historical regressions are documented but not permanently
guarded:

- an AC/HVAC quote produced vehicle-oriented output — the old `missing_vehicle_context`
  marker set true on a non-vehicle quote, plus mechanic-specific disclaimer wording
  (TASK-012);
- an AC quote was described as "quite high", although price benchmarking is not
  implemented anywhere in QuoteCheck and is an explicit SPEC.md non-goal.

Current code is the product-contract source of truth. Historical docs were read only to
understand the regressions.

## 3. Core evaluation principle

Two fundamentally different kinds of evaluation, kept explicitly separate throughout:

- **Layer A — deterministic invariants.** Things code can establish honestly: schema
  validity, field presence, enum legality, metadata and analyzer provenance, an
  uncertainty marker's boolean value, an evidence request existing, a forbidden phrase
  being absent.
- **Layer B — semantic judgment.** Faithfulness, invented faults, uncertainty
  calibration, risk sensibility, question usefulness, explanation quality, boundary
  discipline.

**Layer A passing proves nothing about Layer B.** That statement appears in
`eval/README.md`, in `eval/rubric.md`, and is a constraint on QC-3B's reporting.

## 4. Strict file scope

Allowed to create:

- `eval/README.md`
- `eval/rubric.md`
- `eval/cases/**`
- `eval/termsets.json` — **approved scope addition**, see §9
- `docs/tickets/QC-3A-eval-spec-and-corpus.md`
- `docs/review/REVIEW_BUNDLE__QC-3A-eval-spec-and-corpus.md`

Allowed to edit:

- `docs/CURRENT_STATE.md`
- `README.md` — only the minimum needed to keep it truthful

Not touched: `backend/`, `frontend/`, `examples/`, dependencies, deployment config,
existing historical ticket/review docs. `SPEC.md` was inspected for contradictions and
needed no change — its non-goals already cover price benchmarking, price-fairness
judgment, vendor verification, and professional advice.

## 5. Out of scope

No executable runner, no scoring code, no `results/` artifacts, no CI, no application
source change, no new dependencies, no paid OpenAI API calls, no commit.

## 6. Required work

1. **Case schema** — one JSON file per case: `case_id`, `domain`, `categories`,
   `rationale`, `quote_text`, `deterministic_expectations` (`must` / `must_not`),
   `semantic_expectations`, plus optional `regression_origin` on the REG cases. No
   output snapshots, no golden files, no restatement of `QuoteCheckResult`.
2. **Deterministic vocabulary** — the smallest set that covers the corpus: six checks
   (`schema_valid`, `metadata_complete`, `forbidden_terms`, `uncertainty_marker`,
   `line_items_where`, `topic_present`), with three global invariants applied by QC-3B to
   every case, and named termsets in `eval/termsets.json`.
3. **Semantic rubric** — six dimensions on a 0/1/2 scale, with Faithfulness and
   Unsupported inference as gates, and an explicit prohibition on averaging into a single
   number.
4. **Corpus** — 24–30 synthetic cases across at least six domains, covering clean
   itemization, vague bundled charges, missing scope/quantity/basis, conditional work,
   price-containing quotes, noisy pasted input, cross-domain leakage traps, and both
   sides of professional confirmation.
5. **REG-001 / REG-002** — permanent, stable IDs, guarding the two historical failures.
6. **Documentation updates** — `docs/CURRENT_STATE.md` and minimal `README.md`.

## 7. Design decisions made during implementation

### 7.1 price_judgment is high-precision, not comprehensive

A naive termset ("expensive", "overpriced", "fair price", "reasonable price")
false-positives on exactly the boundary language QuoteCheck should use:

> "QuoteCheck cannot determine whether this is a fair price."

Building a negation/scope parser to disambiguate would put a fragile heuristic at the
centre of the suite's credibility. Instead the termset contains only phrasings that are
strong evidence of an **affirmative** unsupported judgment ("quite high", "seems
overpriced", "competitively priced", "good deal"). Bare "high"/"low" are excluded — the
product's own disclaimer says "high-value or safety-critical work".

Precision is optimized over recall on purpose. Hedged or paraphrased price inference that
string matching cannot classify reliably is explicitly the responsibility of the rubric's
**Unsupported inference** dimension. Documented in `eval/README.md`.

### 7.2 Termset mode is single-source-of-truth

`mode` (`absolute` / `not_in_source`) lives in `eval/termsets.json` and only there. A case
references a termset by name and must not restate `mode`; QC-3B must not implement
per-case termset-mode overrides. Only inline `terms` may carry their own semantics. The
validator enforces this.

### 7.3 Category tags carry obligations

A category that claims a behaviour is under test must carry the matching deterministic
assertion, so tags cannot become decorative metadata:

| Category | Required assertion |
|---|---|
| `clean_itemized` | `ambiguous_items_present == false` and `missing_quote_context == false` |
| `professional_confirmation_expected` | `needs_professional_confirmation == true` |
| `professional_confirmation_not_expected` | `needs_professional_confirmation == false` |
| `cross_domain_trap` | at least one `forbidden_terms` leakage guard |

Verified by the QC-3A validator (check `[10b]`); QC-3B should enforce it in the runner.

### 7.4 REG-002's missing context is objectively supported

`missing_quote_context == true` does not rest on a subjective sense that the diagnosis
"feels thin". REG-002's quote recommends a compressor replacement while providing no
pressure readings, no leak-test result, no electrical measurements, no error code, and
explicitly not including the diagnostic report ("available on request"). A reviewer can
point at what is absent.

### 7.5 The corpus targets the product contract, not the Demo stub

Demo mode is a fixed keyword matcher. It will fail some cases by construction — most
visibly the six `clean_itemized` cases, because `stub_analyzer.py` hardcodes
`ambiguous_items_present = True`. Those failures are real, already-documented product
gaps and are deliberately left in. QC-3B must report per mode, and must not xfail,
suppress, or exclude known failures from pass-rate denominators.

## 8. Acceptance criteria

1. `eval/README.md` explains purpose, deterministic vs. semantic evaluation, current
   non-goals, and the QC-3A → QC-3B relationship.
2. `eval/rubric.md` defines a small, defensible human semantic rubric.
3. Corpus contains 24–30 synthetic cases.
4. At least six meaningful domains represented.
5. Corpus includes clean itemized quotes, vague bundled charges, missing
   scope/quantity/basis, conditional/uncertain work, price-containing cases, noisy pasted
   input, cross-domain leakage traps, and professional-confirmation cases (both
   directions).
6. REG-001 permanently covers HVAC/AC → vehicle/mechanic leakage.
7. REG-002 permanently covers unsupported market-price/fairness judgments.
8. Every case has a stable `case_id`, `domain`, `quote_text`, `rationale`, deterministic
   expectations, and semantic expectations.
9. Deterministic expectations are implementable without pretending to solve semantic
   correctness.
10. No giant exact-output golden files.
11. No application source code changes.
12. No paid OpenAI API calls.
13. `README.md` / `docs/CURRENT_STATE.md` do not claim an executable automated eval
    harness exists.
14. Ticket and review bundle contain exact corpus counts and a coverage summary.

## 9. Approved scope addition

`eval/termsets.json` is one file outside the literal allowed list
(`eval/README.md`, `eval/rubric.md`, `eval/cases/**`). It was confirmed with the user
before implementation. Rationale: the three shared term lists are referenced by seven
cases and one global invariant; defining them once keeps a termset edit a one-file diff
instead of a twenty-file one, and it is what makes decision 7.2 possible.

## 10. Validation

A temporary Python validator, run from the scratchpad and **not committed** (QC-3B owns
the permanent runner), proves: all case files parse; `case_id`s are unique; required keys
present; domain/category enums valid; corpus size in range; REG-001 and REG-002 each
appear exactly once; `quote_text` non-empty and non-duplicate; deterministic and semantic
expectations present; check names and termset references resolve; no case restates a
shared termset's `mode`; category→expectation consistency holds; the `price_judgment`
termset produces zero false positives against the six committed `examples/*.json`
outputs; no personal data in any quote.

Plus `git diff --check`, `git status --short`, `git diff --stat`, and a scoped
`git status --short -- backend/ frontend/ examples/` proving no source-code change.

Exact commands and their real output are in
`docs/review/REVIEW_BUNDLE__QC-3A-eval-spec-and-corpus.md`.

## 11. Definition of done

- All acceptance criteria evidenced in the review bundle with real command output.
- `docs/CURRENT_STATE.md` "Last updated" line reflects QC-3A, with an `Added in QC-3A`
  block stating only what exists and explicitly stating what does not.
- No secrets; no application code touched; not committed — left for the user to review
  and commit manually.
