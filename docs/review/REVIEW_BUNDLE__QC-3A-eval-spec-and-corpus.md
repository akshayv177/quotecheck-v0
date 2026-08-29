# Review Bundle — QC-3A — Evaluation specification + representative case corpus

## 1. Ticket / phase

- Ticket: `docs/tickets/QC-3A-eval-spec-and-corpus.md`
- Phase: QC-3 evaluation (post-QC-1B, pre-QC-3B runner)
- Branch: `task/QC-3A-eval-spec-and-corpus`
- Not committed. No deployment. No OpenAI API calls of any kind.

## 2. Scope summary

Defined **what** QuoteCheck should be evaluated on and **which inputs** to evaluate it
against, before any runner exists. Created an evaluation specification, a human semantic
rubric, shared forbidden-term sets, and a 27-case synthetic quote corpus including two
permanent historical regression cases.

**No application source code changed.** No scoring code was written, no runner was
committed, no `results/` directory was created. `backend/`, `frontend/`, `examples/`,
dependencies, deployment config, and existing historical ticket/review docs were not
touched. `SPEC.md` was inspected for contradictions with the current implementation and
needed no change — its non-goals already cover price benchmarking, price-fairness
judgment, vendor verification, and professional advice.

## 3. Eval philosophy

Two fundamentally different kinds of evaluation, kept explicitly separate in every
artifact:

- **Layer A — deterministic invariants.** What code can establish honestly from the
  response JSON: schema validity, field presence, enum legality, metadata and analyzer
  provenance, an uncertainty marker's boolean value, an evidence request existing, a
  forbidden phrase being absent.
- **Layer B — semantic judgment.** Faithfulness, invented faults/parts/evidence/vendor
  intent, uncertainty calibration, risk sensibility, explanation quality, question
  usefulness, professional-boundary discipline.

**Layer A passing proves nothing about Layer B.** A response can satisfy every
deterministic invariant here and still be a confidently wrong analysis. That statement
appears in `eval/README.md` and `eval/rubric.md`, and constrains what QC-3B is permitted
to report: Layer A and Layer B results must be presented separately, and a Layer A pass
rate must never be described as an accuracy or quality number.

The corpus targets the **intended product contract**, not the current Demo stub's keyword
heuristics — see §14.

## 4. Case schema

One JSON file per case in `eval/cases/`, named `<CASE_ID>-<slug>.json`. Chosen over a
single JSONL file because a failure maps to exactly one case ID, a new case is a small
self-contained diff, and a reviewer can open one case without scrolling a bundle.

| Field | Why it exists |
|---|---|
| `case_id` | Stable, permanent address. Required for REG-001/REG-002 to survive refactors. |
| `domain` | Coverage aggregation; the axis cross-domain leakage is defined against. Closed enum. |
| `categories` | Coverage reporting and filtering. Closed enum, with mandatory matching assertions (§7.3 of the ticket). |
| `rationale` | One sentence justifying the case's existence to a reviewer. |
| `quote_text` | The input, as a user would paste it. |
| `deterministic_expectations` | Layer A: `must` / `must_not`. |
| `semantic_expectations` | Layer B: `should_identify`, `should_preserve_uncertainty`, `must_not_invent`, `notes`. Never machine-scored. |
| `regression_origin` | Optional; only on REG-001/REG-002. |

Deliberately absent: no expected-output snapshot and no per-field golden values. Golden
files for generative output rot on every prompt change and teach a suite to detect edits
rather than defects. The corpus also does not restate the `QuoteCheckResult` schema —
`backend/core/schema.py` is the single source of truth.

## 5. Domain distribution

Real output of the validator (§13):

| Domain | Cases | IDs |
|---|---|---|
| `automotive` | 5 | AUTO-001, AUTO-002, AUTO-003, AUTO-004, AUTO-005 |
| `contractor_vendor` | 5 | CONT-001, CONT-002, CONT-003, CONT-004, CONT-005 |
| `hvac_appliance` | 5 | HVAC-001, HVAC-002, HVAC-003, REG-001, REG-002 |
| `electronics_repair` | 4 | ELEC-001, ELEC-002, ELEC-003, ELEC-004 |
| `generic_service` | 4 | GEN-001, GEN-002, GEN-003, GEN-004 |
| `plumbing_home` | 4 | HOME-001, HOME-002, HOME-003, HOME-004 |
| **TOTAL** | **27** | |

Six domains. Automotive is 5 of 27 — the corpus is not automotive-dominated, which
matters because vehicle-era bias is precisely what QC-1B removed from the contract.
REG-001 and REG-002 are counted inside `hvac_appliance` rather than added as extra cases;
both historical failures were AC quotes.

## 6. Category coverage

| Category | Cases | IDs |
|---|---|---|
| `price_present` | 10 | AUTO-001, AUTO-003, CONT-001, CONT-004, ELEC-001, ELEC-004, GEN-001, GEN-004, HOME-001, REG-002 |
| `missing_scope_or_quantity` | 9 | AUTO-002, AUTO-004, AUTO-005, CONT-002, CONT-004, ELEC-002, GEN-003, HOME-002, REG-002 |
| `clean_itemized` | 6 | AUTO-001, CONT-001, ELEC-001, GEN-001, HOME-001, HVAC-001 |
| `vague_bundled_charge` | 6 | AUTO-003, CONT-002, ELEC-003, GEN-002, HOME-004, HVAC-002 |
| `conditional_work` | 5 | AUTO-002, CONT-003, ELEC-002, GEN-004, HVAC-003 |
| `cross_domain_trap` | 5 | ELEC-003, GEN-002, HOME-003, REG-001, REG-002 |
| `professional_confirmation_expected` | 4 | AUTO-004, CONT-005, HOME-003, REG-001 |
| `professional_confirmation_not_expected` | 4 | ELEC-004, GEN-001, HOME-001, HVAC-003 |
| `noisy_input` | 3 | AUTO-005, CONT-005, HOME-004 |

All nine categories have cases. Every one of the six domains carries exactly one
`clean_itemized` case: QuoteCheck is built to find ambiguity, which makes manufacturing
ambiguity its most likely systematic failure, so each domain needs a quote that should
come back calm.

Both directions of professional confirmation are covered — four cases where escalation is
justified (structural work with an unresolved load-bearing question, safety-relevant
suspension work with an unconfirmed root cause, domestic electrical work with an
un-isolated fault, refrigerant/sealed-system work) and four where reflexive escalation
would be noise (a fridge door gasket, a surveyed tap swap, a bench battery replacement, a
pest-control contract).

All 27 quotes are synthetic, with fictional vendor names ("Fairlane Motor Works",
"Northwind Climate Services", "Camberwell Builders & Co.") and no personal data. They are
written the way vendors actually write, with no tells such as "THIS ITEM IS VAGUE" —
noisy cases use real shorthand ("2 nos tap fitting - 1200/-", "flywheel machining IF REQD
approx 2000", "** wall is 9 inch , will confirm on site whether load bearing or not").

## 7. Historical regression cases

### REG-001 — HVAC → vehicle/mechanic leakage

`eval/cases/REG-001-hvac-vehicle-domain-leakage.json`, domain `hvac_appliance`,
categories `cross_domain_trap` + `professional_confirmation_expected`.

Input: a split-AC compressor replacement quote with real diagnostic detail (start current
14.2 A against a rated 8.6 A, low-side pressure 42 psi against 68–72 psi, soap test
bubbling at the service valve). Zero vehicle vocabulary.

```json
"must": [
  { "check": "uncertainty_marker", "marker": "needs_professional_confirmation", "expected": true },
  { "check": "line_items_where", "property": "evidence_needed_nonempty", "value": true, "min_count": 1 }
],
"must_not": [
  { "check": "forbidden_terms", "termset": "vehicle_domain" }
]
```

The invariant targets **inappropriate domain leakage**, not the deleted
`missing_vehicle_context` field name — that field no longer exists after QC-1B, so
asserting on it would test nothing.

**The documented nuance:** `vehicle_domain` runs in `not_in_source` mode, so a term fails
only if it appears in the output **and** not in `quote_text`. A quote that itself says
"mechanic" does not make the word forbidden; inventing it does. The check can only
distinguish output text from source text — deciding whether a *legitimately sourced*
domain word was used faithfully is a Layer B judgment (rubric dimension 2). This is
stated in `eval/README.md` under "Historical regression cases".

### REG-002 — unsupported price judgment

`eval/cases/REG-002-unsupported-price-judgment.json`, domain `hvac_appliance`,
categories `price_present` + `missing_scope_or_quantity` + `cross_domain_trap`.

Input: an AC repair quote with deliberately large-looking amounts — compressor Rs. 32,500,
refrigerant recharge Rs. 6,800, labour Rs. 4,500, callout Rs. 800, total Rs. 44,600.

```json
"must": [
  { "check": "uncertainty_marker", "marker": "missing_quote_context", "expected": true }
],
"must_not": [
  { "check": "forbidden_terms", "termset": "price_judgment" },
  { "check": "forbidden_terms", "termset": "vehicle_domain" }
]
```

`price_judgment` is a global invariant; restating it here is deliberate so the price
regression case reads standalone.

**`missing_quote_context == true` rests on objective absence, not a subjective sense that
the diagnosis "feels thin".** The quote recommends a compressor replacement while
providing no pressure readings, no leak-test result, no electrical measurements, no error
code, and explicitly not including the diagnostic report ("Diagnostic report available on
request"). A reviewer can point at what is missing.

The allowed/forbidden boundary is stated in `eval/README.md`, `eval/rubric.md`, and the
case's own `notes`:

| Allowed and desirable | Forbidden |
|---|---|
| "The basis for this charge is not stated." | "This charge is quite high." |
| "Ask what the Rs. 6,800 refrigerant line includes." | "This looks expensive for the work described." |
| "Price benchmarking is not implemented." | "Competitively priced for the market." |

Commenting on a **missing price basis** is the product working. Claiming **market fairness
or magnitude** is the regression.

## 8. Semantic rubric summary

`eval/rubric.md`. Six dimensions, each scored 0/1/2 by a human, with every level defined
in the file:

1. **Faithfulness** *(gate)* — every claim traceable to the quote.
2. **Unsupported inference** *(gate)* — no invented fault, part, evidence, vendor motive,
   price judgment, or cross-domain import.
3. **Uncertainty calibration** — hedged source language stays hedged; definite work is not
   fogged; the three markers match what the quote supports.
4. **Explanation quality** — understandable to a non-expert without buying readability
   with invented certainty.
5. **Actionability** — questions sendable as written; evidence obtainable and
   decision-relevant; not generic boilerplate.
6. **Professional-boundary discipline** — no safety determinations, no unrelated trade
   named, disclaimer present; and no reflexive escalation of benign quotes.

Scale: **2** = pass, **1** = mixed / needs review, **0** = fail. Deliberately coarse — a
finer scale would imply a precision a single reviewer does not have.

Gates: a 0 on Faithfulness or Unsupported inference **fails the case outright**,
regardless of the other four scores. Fluent, actionable output built on something the
quote never said is worse than unhelpful output, and four good scores must not average
that away.

Reporting rules in the file: report per-dimension distributions and every 0 by name with
a one-line reason; state the sample size (27) next to any aggregate; **do not average the
six dimensions into a single number**, do not report a mean to a decimal place, and do
not combine Layer A and Layer B into one headline figure.

## 9. Deterministic expectation vocabulary

Six check types — the smallest set that covers the corpus.

**Global invariants**, applied by QC-3B to every case and not repeated in 27 files:

| Check | Meaning |
|---|---|
| `schema_valid` | Response parses and validates against `QuoteCheckResult`. |
| `metadata_complete` | `prompt_version` / `model` / `request_id` non-empty, `schema_valid` true, and `model` matches the run mode's provenance label (`quotecheck-demo-analyzer` in Demo mode, configured `QUOTECHECK_MODEL` in OpenAI mode). |
| `forbidden_terms` / `price_judgment` | No affirmative unsupported price judgment on any case. |

**Case-level checks:** `forbidden_terms` (`termset` or inline `terms`; field scope
`analysis_text` by default, excluding `name_raw` since the schema defines it as text
copied from the quote), `uncertainty_marker` (`marker` + `expected`), `line_items_where`
(`property` + `value` + `min_count`/`max_count`), `topic_present` (`any_of` + `in`).

Matching is **case-insensitive whole-word/whole-phrase, never substring** — so "tire" does
not match "entire", and "fair price" does not match "guarantee fair pricing".

**Termset mode is single-source-of-truth.** `mode` lives in `eval/termsets.json` and only
there; cases reference a termset by name and never restate it; QC-3B must not implement
per-case termset-mode overrides. Enforced by validator check `[10]`.

### Which checks are robust, and which are proxies

Stated explicitly in `eval/README.md` so nobody mistakes a green Layer A for quality:

| Check | Strength |
|---|---|
| `schema_valid` | Robust. Pydantic validates or does not. |
| `metadata_complete` | Robust. Field presence and a label comparison. |
| `uncertainty_marker` | Robust as a mechanism check. Whether the expected value is *right* for a given quote is a design claim argued in that case's `rationale`. |
| `line_items_where` | Robust for counting. Proves an evidence request exists, never that it is useful. |
| `forbidden_terms` (`absolute`) | High precision, low recall by design. A hit is strong evidence of a defect; a pass is not evidence of absence. |
| `forbidden_terms` (`not_in_source`) | A **proxy** for invented domain terminology, not proof of it. |
| `topic_present` | Weakest. Proves a word appears, nothing about whether the question is worth asking. |

### Why `price_judgment` is high-precision rather than comprehensive

The obvious termset — "expensive", "overpriced", "fair price", "reasonable price" —
false-positives on exactly the boundary language QuoteCheck *should* use:

> "QuoteCheck cannot determine whether this is a fair price."

The fix is not a negation/scope parser: string matching cannot reliably tell an assertion
from its disclaimer, and a fragile parser at the centre of the suite would undermine its
credibility. So the termset contains only phrasings that are strong evidence of an
**affirmative** unsupported judgment:

```
quite high · unusually high · on the higher side · seems expensive · looks expensive ·
appears expensive · seems overpriced · appears overpriced · clearly overpriced ·
seems inflated · appears inflated · competitively priced · reasonably priced ·
above market rate · below market rate · good deal · bad deal · value for money
```

Bare "high" and "low" are excluded too — the product's own honest disclaimer says
"high-value or safety-critical work". **Precision is optimized over recall on purpose.**
Hedged, paraphrased, or implied price-fairness inference this list cannot catch is
explicitly the responsibility of the rubric's **Unsupported inference** dimension. A clean
`price_judgment` result means "no blatant judgment phrase was emitted", never "this output
made no price judgment". Documented in `eval/README.md` under "Why the price termset is
small", and echoed in the CONT-004 case notes.

### Category → expectation consistency

Category tags carry obligations so they cannot become decorative metadata:

| Category | Required assertion |
|---|---|
| `clean_itemized` | `ambiguous_items_present == false` and `missing_quote_context == false` |
| `professional_confirmation_expected` | `needs_professional_confirmation == true` |
| `professional_confirmation_not_expected` | `needs_professional_confirmation == false` |
| `cross_domain_trap` | at least one `forbidden_terms` leakage guard in `must_not` |

Verified by validator check `[10b]`. QC-3B should enforce it in the runner so future
cases cannot drift.

## 10. Files changed

Created (all new, none previously existed — `eval/` was an empty untracked directory):

```
eval/README.md                   357 lines   evaluation specification
eval/rubric.md                   170 lines   human 0/1/2 semantic rubric
eval/termsets.json                67 lines   3 shared forbidden-term sets
eval/cases/*.json                 27 files   the corpus, one JSON file per case
docs/tickets/QC-3A-eval-spec-and-corpus.md
docs/review/REVIEW_BUNDLE__QC-3A-eval-spec-and-corpus.md
```

The 27 case files:

```
AUTO-001-clean-scheduled-service.json          HOME-001-clean-tap-valve-replacement.json
AUTO-002-conditional-brake-inspection.json     HOME-002-leak-repair-no-scope.json
AUTO-003-shop-supplies-sundries.json           HOME-003-electrical-panel-earthing.json
AUTO-004-unconfirmed-root-cause-suspension.json HOME-004-pasted-plumber-shorthand.json
AUTO-005-whatsapp-shorthand-estimate.json      HVAC-001-clean-amc-itemized.json
CONT-001-clean-cabinet-installation.json       HVAC-002-bundled-service-handling.json
CONT-002-lump-sum-additional-work.json         HVAC-003-benign-gasket-conditional.json
CONT-003-renovation-subject-to-inspection.json REG-001-hvac-vehicle-domain-leakage.json
CONT-004-large-partially-itemized-total.json   REG-002-unsupported-price-judgment.json
CONT-005-structural-opening-noisy.json         ELEC-001-clean-laptop-screen.json
GEN-001-clean-pest-control-contract.json       ELEC-002-conditional-motherboard.json
GEN-002-parts-labour-misc-no-domain.json       ELEC-003-phone-repair-handling-charge.json
GEN-003-as-discussed-approximate-total.json    ELEC-004-battery-replacement-large-amount.json
GEN-004-equipment-contract-conditional.json
```

Edited:

- `docs/CURRENT_STATE.md` — `Last updated` line set to QC-3A; new `### Added in QC-3A`
  block stating only what exists and explicitly stating what does not (no runner, no
  automated scoring, no new model-quality claims); the Gaps bullet "No backend tests, no
  automated eval / regression harness, no CI" extended to note that a specification and
  corpus now exist but nothing executes them. Historical blocks untouched.
- `README.md` — minimal truth maintenance only: one paragraph added to the `### Evaluation`
  section (specification and 27-case corpus exist; nothing executes yet; no performance
  claim); `eval/` added to the repo-structure tree; Roadmap item 2 reworded to say the
  specification and corpus exist and the runner does not. No other prose changed.

**Approved scope addition:** `eval/termsets.json` sits outside the ticket's literal
allowed list (`eval/README.md`, `eval/rubric.md`, `eval/cases/**`). It was confirmed with
the user before implementation. Rationale: the three shared term lists are referenced by
seven cases plus one global invariant; defining them once makes a termset edit a one-file
diff, and it is what makes single-source-of-truth mode possible.

## 11. Acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `eval/README.md` explains purpose, deterministic vs. semantic, non-goals, QC-3A→QC-3B relationship | Met | `eval/README.md` sections "Purpose", "The core distinction: Layer A and Layer B", "Non-goals (current)", "Relationship to QC-3B" |
| 2 | `eval/rubric.md` defines a small, defensible human semantic rubric | Met | 6 dimensions, 0/1/2 scale, 2 gates, reporting rules; §8 above |
| 3 | Corpus contains 24–30 synthetic cases | Met | 27 cases; validator `[5]` |
| 4 | At least six meaningful domains represented | Met | 6 domains; validator domain table, §5 |
| 5 | Corpus includes all eight required case kinds | Met | 9 categories all populated; validator category table, §6 |
| 6 | REG-001 permanently covers HVAC/AC → vehicle/mechanic leakage | Met | §7; validator `[6]` = 1 occurrence |
| 7 | REG-002 permanently covers unsupported market-price/fairness judgment | Met | §7; validator `[6]` = 1 occurrence |
| 8 | Every case has stable `case_id`, `domain`, `quote_text`, `rationale`, deterministic + semantic expectations | Met | validator `[2] [3] [4] [7]` |
| 9 | Deterministic expectations implementable without pretending to solve semantic correctness | Met | §9 strength table; `eval/README.md` "How strong is each check, honestly" |
| 10 | No giant exact-output golden files | Met | No case contains an expected response; §4 |
| 11 | No application source code changes | Met | `git status --short -- backend/ frontend/ examples/` is empty, §12 |
| 12 | No paid OpenAI API calls | Met | Nothing was executed against `/analyze`; the validator imports only `json`, `re`, `sys`, `collections`, `pathlib` |
| 13 | README/CURRENT_STATE do not claim an executable automated eval harness exists | Met | Both state plainly that nothing in `eval/` runs; §10 |
| 14 | Ticket and review bundle contain exact corpus counts and coverage summary | Met | §5, §6; ticket §7, §10 |

## 12. Validation commands

```bash
# Temporary corpus validator (scratchpad, NOT committed — QC-3B owns the permanent runner)
python3 /tmp/claude-1000/.../scratchpad/validate_corpus.py

# Leakage guards are live, not vacuous
python3 - <<'PY'   # inline; see §13 for the script and output
PY

# Git verification
git diff --check
git status --short
git diff --stat
git status --short -- backend/ frontend/ examples/
```

The validator makes no `/analyze` calls, no OpenAI calls, and imports nothing from
`backend/`. It reads only `eval/**` and the six committed `examples/*.json` files.

## 13. Exact validation output

### 13.1 Corpus validator

```
$ python3 /tmp/claude-1000/.../scratchpad/validate_corpus.py
[1] JSON parse            : 27/27 files parsed
[2] case_id uniqueness    : 27 unique / 27 cases
[3] required keys         : checked on 27 cases
[4] domain/category enums : checked on 27 cases
[5] corpus size           : 27 (required 24-30)
[6] REG-001 present       : 1 occurrence(s)
[6] REG-002 present       : 1 occurrence(s)
[7] quote_text unique     : 27 distinct normalized quotes
[10] check vocabulary     : all checks in ['forbidden_terms', 'line_items_where', 'metadata_complete', 'schema_valid', 'topic_present', 'uncertainty_marker']
     termsets resolve     : ['price_judgment', 'trade_domain', 'vehicle_domain']
     no per-case mode     : ok
[10b] category->expectation consistency : enforced on all 4 tagged categories
[11] termset false-positive sweep over examples/*.json (6 captured Demo outputs)
     price_judgment       : 0 false positives on committed product copy
     (confirms 'high-value or safety-critical work' and 'guarantee fair pricing' do not trip the termset)
[12] personal-data sweep  : no phone numbers, emails, or id numbers in any quote_text

Domain coverage
---------------
Domain                 Cases   IDs
automotive                 5   AUTO-001, AUTO-002, AUTO-003, AUTO-004, AUTO-005
contractor_vendor          5   CONT-001, CONT-002, CONT-003, CONT-004, CONT-005
hvac_appliance             5   HVAC-001, HVAC-002, HVAC-003, REG-001, REG-002
electronics_repair         4   ELEC-001, ELEC-002, ELEC-003, ELEC-004
generic_service            4   GEN-001, GEN-002, GEN-003, GEN-004
plumbing_home              4   HOME-001, HOME-002, HOME-003, HOME-004
TOTAL                     27

Category coverage
-----------------
Category                               Cases   IDs
price_present                             10   AUTO-001, AUTO-003, CONT-001, CONT-004, ELEC-001, ELEC-004, GEN-001, GEN-004, HOME-001, REG-002
missing_scope_or_quantity                  9   AUTO-002, AUTO-004, AUTO-005, CONT-002, CONT-004, ELEC-002, GEN-003, HOME-002, REG-002
clean_itemized                             6   AUTO-001, CONT-001, ELEC-001, GEN-001, HOME-001, HVAC-001
vague_bundled_charge                       6   AUTO-003, CONT-002, ELEC-003, GEN-002, HOME-004, HVAC-002
conditional_work                           5   AUTO-002, CONT-003, ELEC-002, GEN-004, HVAC-003
cross_domain_trap                          5   ELEC-003, GEN-002, HOME-003, REG-001, REG-002
professional_confirmation_expected         4   AUTO-004, CONT-005, HOME-003, REG-001
professional_confirmation_not_expected     4   ELEC-004, GEN-001, HOME-001, HVAC-003
noisy_input                                3   AUTO-005, CONT-005, HOME-004

OK — 27 cases, 6 domains, 9 categories, 0 errors.
```

Note: an earlier run of this script failed with one error —
`AUTO-001-clean-scheduled-service.json: possible personal data in quote_text:
['94109-14   1']`. That was a false positive in the validator's own PII regex matching a
drain-plug part number (`P/N 94109-14  1 no.`), not real data. The regex was tightened to
require at least 10 actual digits before flagging a run as a phone/ID candidate. The
corpus was not changed.

### 13.2 Leakage guards are live, not vacuous

Confirms that every `not_in_source` guard can actually fire — if a guarded term already
appeared in a case's own quote, the guard would be silently neutered for that term.

```
$ python3 - <<'PY' ... PY
case       termset         terms present in quote_text (guard would be neutered)
--------------------------------------------------------------------------------
ELEC-003   trade_domain    none — guard is live
ELEC-003   vehicle_domain  none — guard is live
GEN-002    vehicle_domain  none — guard is live
GEN-002    trade_domain    none — guard is live
HOME-003   vehicle_domain  none — guard is live
REG-001    vehicle_domain  none — guard is live
REG-002    vehicle_domain  none — guard is live

All not_in_source leakage guards are live (no guarded term appears in its own quote).
```

### 13.3 File inventory

```
$ ls eval/cases/ | wc -l
27

$ wc -l eval/README.md eval/rubric.md eval/termsets.json
  357 eval/README.md
  170 eval/rubric.md
   67 eval/termsets.json
  594 total
```

### 13.4 Git

```
$ git diff --check
(no whitespace errors)

$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
?? docs/tickets/QC-3A-eval-spec-and-corpus.md
?? eval/

$ git diff --stat
 README.md             | 16 ++++++++++-
 docs/CURRENT_STATE.md | 75 +++++++++++++++++++++++++++++++++++++++++++++++++--
 2 files changed, 88 insertions(+), 3 deletions(-)

$ git status --short -- backend/ frontend/ examples/
(empty — no application source, frontend, or example changes)
```

## 14. Remaining limitations

- **Nothing executes.** This ticket produced a specification and inputs. It measured
  nothing, and says nothing about how well QuoteCheck currently performs. Every case's
  deterministic expectations are a *design claim* about correct behaviour that has not
  been run against either analyzer.
- **The corpus will fail in Demo mode by construction, on purpose.** It targets the
  product contract, not `stub_analyzer.py`'s keyword heuristics. Expected failures
  include: all six `clean_itemized` cases (the stub hardcodes
  `ambiguous_items_present = True`); cases whose missing context is real but not phrased
  in the stub's fixed `MISSING_CONTEXT_PHRASES` list; and the electronics and most
  generic-service cases, which match no stub keyword and fall through to a single "needs
  clarification" item. These are real, already-documented gaps left in as signal.
  `eval/README.md` records that QC-3B must report per mode and must **not** xfail,
  suppress, or exclude them from pass-rate denominators.
- **`forbidden_terms` in `not_in_source` mode is a proxy**, not proof of invention. It
  cannot judge whether a legitimately sourced domain word was used faithfully.
- **`price_judgment` has deliberately low recall.** Hedged or paraphrased price inference
  ("a substantial sum for this scope") passes the string check and depends entirely on a
  human applying rubric dimension 2.
- **The semantic rubric is unvalidated.** No inter-rater agreement has been measured, and
  with one reviewer none can be. Scores are a structured reading, not a metric.
- **27 cases is a coverage instrument, not a statistical sample.** No significance claim
  is or should be made from it.
- **The `topic_present` check is specified but unused** by the current 27 cases. It is
  retained in the vocabulary because QC-3B is likely to need it; if it is still unused
  after the runner lands, it should be dropped rather than kept as dead spec.
- **Deterministic expectations do not cover risk-level correctness.** `line_items_where`
  can assert a risk distribution, but no case does, because whether `red` or `yellow` is
  right for a given quote is a judgment. Risk sensibility lives entirely in the rubric.
- Out-of-scope observation, recorded not fixed: `uncertainty_markers.ambiguous_items_present`
  is a constant `true` in the Demo stub (deliberately left alone in QC-1B). It is the
  single largest source of expected Demo-mode failures in this corpus, and is the obvious
  candidate for the next contract-hardening ticket.

## 15. `git status --short`

```
 M README.md
 M docs/CURRENT_STATE.md
?? docs/tickets/QC-3A-eval-spec-and-corpus.md
?? eval/
```

(`docs/review/REVIEW_BUNDLE__QC-3A-eval-spec-and-corpus.md` — this file — was written
after that command ran and will appear as a fourth untracked path.)

## 16. `git diff --stat`

```
 README.md             | 16 ++++++++++-
 docs/CURRENT_STATE.md | 75 +++++++++++++++++++++++++++++++++++++++++++++++++--
 2 files changed, 88 insertions(+), 3 deletions(-)
```

Tracked-file changes are documentation only. Everything else in this ticket is new
untracked files under `eval/` and `docs/`. Not committed.
