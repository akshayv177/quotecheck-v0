# QuoteCheck evaluation specification

**Status: specification and corpus only. There is no executable eval runner, no
automated scoring, and no CI in this repo today.** This directory defines *what*
QuoteCheck should be evaluated on and *which* inputs to evaluate it against. QC-3B will
implement the runner against this specification.

Nothing here makes a claim about how well QuoteCheck currently performs.

---

## Purpose

QuoteCheck turns pasted service, maintenance, repair, parts, and vendor quotes into
explanations, risk flags, vendor questions, and things to verify. Until now its quality
evidence has been six captured Demo-mode examples (`examples/`) and manual QA recorded in
`docs/review/`. Neither has pass/fail semantics, and neither permanently guards the
regressions QuoteCheck has actually had.

This specification exists so that:

1. product behaviour has a fixed, inspectable set of representative inputs;
2. two historical regressions can never silently return;
3. the difference between "a machine checked this" and "a human judged this" is explicit
   rather than blurred.

---

## The core distinction: Layer A and Layer B

Evaluating an LLM product honestly means refusing to let easy checks stand in for hard
ones.

### Layer A — deterministic invariants

Things code can establish honestly from the response JSON:

- the response validates against `QuoteCheckResult`;
- required fields exist and enum values are legal;
- run metadata is present and analyzer provenance is populated;
- a specific uncertainty marker has a specific boolean value;
- at least one line item carries an evidence request;
- a forbidden phrase does not appear in analysis-authored text.

### Layer B — semantic judgment

Things that cannot be reduced to string checks without lying about what was verified:

- is the explanation faithful to the submitted quote;
- did the model invent a fault, part, measurement, or vendor intention;
- is the uncertainty calibrated to the source language;
- is the risk level sensible;
- are the vendor questions and evidence requests actually useful;
- does the output stay inside QuoteCheck's product boundary.

Layer B is scored by a human against [`rubric.md`](rubric.md).

> **Layer A passing proves nothing about Layer B.** A response can satisfy every
> deterministic invariant in this directory and still be a confidently wrong analysis of
> the quote. Any report QC-3B produces must present the two layers separately and must
> never describe a Layer A pass rate as an accuracy, quality, or correctness number.

---

## Case files

One JSON file per case in [`cases/`](cases/), named `<CASE_ID>-<slug>.json`. One file per
case is deliberate: a failure maps to exactly one case ID, a new case is a small
self-contained diff, and a reviewer can read one case without scrolling a bundle.

```json
{
  "case_id": "HVAC-002",
  "domain": "hvac_appliance",
  "categories": ["vague_bundled_charge"],
  "rationale": "One sentence: why this case exists.",
  "quote_text": "...",
  "deterministic_expectations": {
    "must": [ { "check": "line_items_where", "property": "vague_or_confusing", "value": true, "min_count": 1 } ],
    "must_not": [ { "check": "forbidden_terms", "termset": "price_judgment" } ]
  },
  "semantic_expectations": {
    "should_identify": ["..."],
    "should_preserve_uncertainty": ["..."],
    "must_not_invent": ["..."],
    "notes": "..."
  }
}
```

| Field | Why it exists |
|---|---|
| `case_id` | Stable, permanent address. A QC-3B failure names exactly one case. Required for REG-001/REG-002 to survive future refactors. |
| `domain` | Coverage aggregation, and the axis cross-domain leakage is defined against. Closed enum. |
| `categories` | Coverage reporting and filtering. Closed enum. Not decorative — see *Category consistency* below. |
| `rationale` | Every case must justify its existence to a reviewer in one sentence. |
| `quote_text` | The input, verbatim, as a user would paste it. |
| `deterministic_expectations` | Layer A. What QC-3B may assert in code. |
| `semantic_expectations` | Layer B. Anchors for the human rubric. **Never machine-scored.** |
| `regression_origin` | Optional, present only on REG-001/REG-002: the historical failure the case preserves. |

Two things are deliberately **absent**: no expected-output snapshot, and no per-field
golden values. Golden files for generative output rot on every prompt change and teach a
suite to detect edits rather than defects. This corpus asserts invariants.

The corpus also does not restate the `QuoteCheckResult` schema. That contract lives in
`backend/core/schema.py` and is the single source of truth.

---

## Deterministic expectation vocabulary

Six check types, deliberately small. `must` holds positive assertions; `must_not` holds
`forbidden_terms` entries.

### Global invariants

QC-3B applies these to **every** case. They are not repeated in 27 case files.

| Check | Meaning |
|---|---|
| `schema_valid` | The response parses and validates against `QuoteCheckResult`. |
| `metadata_complete` | `metadata.prompt_version`, `.model`, `.request_id` are non-empty; `metadata.schema_valid` is `true`; `metadata.model` matches the run mode's expected provenance label (`quotecheck-demo-analyzer` in Demo mode, the configured `QUOTECHECK_MODEL` in OpenAI mode). |
| `forbidden_terms` / `price_judgment` | No affirmative unsupported price judgment, on any case, because no benchmarking exists anywhere in the system. |

REG-002 restates the `price_judgment` guard in its own `must_not`. That restatement is
deliberate: the price regression case should be readable standalone.

### Case-level checks

**`forbidden_terms`** — a term must not appear in the output.

- `termset`: a name resolved from [`termsets.json`](termsets.json), or
- `terms`: an inline case-specific list.
- `mode` — **for shared termsets, the mode lives in `termsets.json` and only there.** A
  case referencing a termset must not restate `mode`, and QC-3B must not implement
  per-case termset-mode overrides. Only inline `terms` may carry their own `mode`.
  - `absolute` — the phrase must never appear in analysis-authored text, whatever the
    quote says. QuoteCheck must not assert a market judgment even if the vendor did.
  - `not_in_source` — the term fails only if it appears in the output **and** does not
    appear in `quote_text`. If the customer's own quote says "mechanic", the word is not
    forbidden; inventing it is.
- `fields` — `analysis_text` (default: `explanation`, `rationale_short`,
  `evidence_needed`, `overall_summary`, `verification_questions`, `things_to_verify`,
  `disclaimer`) or `all_text` (adds `name_raw`). `name_raw` is excluded by default
  because the schema defines it as text copied from the quote, so a term appearing there
  is quotation, not invention.
- Matching is **case-insensitive whole-word / whole-phrase, never substring** — so "tire"
  does not match "entire", and "fair price" does not match "guarantee fair pricing".

**`uncertainty_marker`** — `marker` (one of `ambiguous_items_present`,
`missing_quote_context`, `needs_professional_confirmation`) and `expected` (bool). A
direct boolean read of the contract in `backend/core/schema.py`.

**`line_items_where`** — `property` (`vague_or_confusing`, `evidence_needed_nonempty`, or
`risk_level`), `value`, and `min_count` / `max_count`. Covers "ambiguity was surfaced" and
"evidence was requested" with one check.

**`topic_present`** — `any_of` (terms/synonyms) and `in` (field group). Used sparingly.

### How strong is each check, honestly

| Check | Strength |
|---|---|
| `schema_valid` | Robust. Pydantic either validates or it does not. |
| `metadata_complete` | Robust. Field presence and a provenance label comparison. |
| `uncertainty_marker` | Robust as a *mechanism* check. Whether `true` is the *right* value for a given quote is a design claim made per case, argued in that case's `rationale`. |
| `line_items_where` | Robust for counting. It proves an evidence request exists, never that it is a useful one. |
| `forbidden_terms`, `absolute` | High precision, low recall by design. A hit is strong evidence of a real defect; a pass is not evidence of absence. |
| `forbidden_terms`, `not_in_source` | A **proxy**. It shows a domain word appeared in output and not in the quote. Whether a legitimately *sourced* domain word was used faithfully is Layer B. |
| `topic_present` | Weakest. Proves a word appears. Proves nothing about whether the question is worth asking. |

### Why the price termset is small

The obvious termset — "expensive", "overpriced", "fair price", "reasonable price" — is
wrong, because it false-positives on exactly the boundary language QuoteCheck *should*
use:

> "QuoteCheck cannot determine whether this is a fair price."

The fix is not a negation/scope parser. String matching cannot reliably tell an assertion
from its disclaimer, and pretending otherwise would put a fragile parser at the centre of
the suite's credibility.

So `price_judgment` contains only phrasings that are strong evidence of an *affirmative*
unsupported judgment ("quite high", "seems overpriced", "competitively priced", "good
deal"). Bare "high" and "low" are excluded too — the product's own honest disclaimer says
"high-value or safety-critical work".

**Precision is optimized over recall, on purpose.** Hedged, paraphrased, or implied
price-fairness inference that this list cannot catch is the responsibility of the
rubric's **Unsupported inference** dimension, not of string matching. A clean
`price_judgment` result means "no blatant judgment phrase was emitted" — never "this
output made no price judgment".

The allowed/forbidden boundary, stated plainly:

| Allowed and desirable | Forbidden |
|---|---|
| "The basis for this charge is not stated." | "This charge is quite high." |
| "Ask what the ₹6,800 refrigerant line includes." | "This looks expensive for the work described." |
| "Confirm whether this is a fixed fee or time-based." | "This seems like a good deal." |
| "Price benchmarking is not implemented." | "Competitively priced for the market." |

Commenting on a **missing price basis** is the product working. Claiming **market
fairness or magnitude** is the regression.

---

## Category consistency

Category tags carry obligations, so they cannot become decorative metadata. A case
claiming to test a behaviour must assert it:

| Category | Required deterministic assertion |
|---|---|
| `clean_itemized` | `ambiguous_items_present == false` **and** `missing_quote_context == false` |
| `professional_confirmation_expected` | `needs_professional_confirmation == true` |
| `professional_confirmation_not_expected` | `needs_professional_confirmation == false` |
| `cross_domain_trap` | at least one `forbidden_terms` leakage guard in `must_not` |

QC-3A validated these relationships with a temporary script (output in
`docs/review/REVIEW_BUNDLE__QC-3A-eval-spec-and-corpus.md`). QC-3B should enforce them in
the runner so a future case cannot drift.

---

## Corpus

27 synthetic cases. Every quote is fictional — invented vendor and customer names, no
real customer quotes, no personal data. Inputs are written the way vendors actually
write, with no tells like "THIS ITEM IS VAGUE"; a case is only useful if the ambiguity has
to be found rather than read off a label.

### Domains

| Domain (`domain` value) | Cases | IDs |
|---|---|---|
| Automotive repair / servicing (`automotive`) | 5 | `AUTO-001`…`AUTO-005` |
| HVAC / appliance service (`hvac_appliance`) | 5 | `REG-001`, `REG-002`, `HVAC-001`…`HVAC-003` |
| Plumbing / home maintenance (`plumbing_home`) | 4 | `HOME-001`…`HOME-004` |
| Electronics repair (`electronics_repair`) | 4 | `ELEC-001`…`ELEC-004` |
| Contractor / renovation / vendor (`contractor_vendor`) | 5 | `CONT-001`…`CONT-005` |
| Generic service / parts / labour (`generic_service`) | 4 | `GEN-001`…`GEN-004` |
| **Total** | **27** | |

Automotive is 5 of 27 by design — QuoteCheck is not a vehicle product, and a corpus
dominated by car quotes would re-teach the bias QC-1B removed.

### Categories

`clean_itemized` · `vague_bundled_charge` · `missing_scope_or_quantity` ·
`conditional_work` · `price_present` · `noisy_input` · `cross_domain_trap` ·
`professional_confirmation_expected` · `professional_confirmation_not_expected`

Every domain has exactly one `clean_itemized` case. QuoteCheck is built to find
ambiguity, which makes manufacturing ambiguity its most likely systematic failure — the
suite has to be able to catch that, so each domain carries a quote that should come back
calm.

---

## Historical regression cases

These two are permanent. They have stable IDs, and they should not be renamed, merged, or
deleted.

### REG-001 — HVAC → vehicle/mechanic leakage

An AC/HVAC quote once produced vehicle-oriented output: a `missing_vehicle_context`
marker set true on a non-vehicle quote, and mechanic-specific disclaimer wording
(TASK-012). The contract has been domain-neutral since QC-1B.

The invariant targets **inappropriate domain leakage**, not the deleted field name —
`missing_vehicle_context` no longer exists, so asserting on it would test nothing.

The nuance that makes this checkable: **the deterministic check can only distinguish
output text from source text.** `not_in_source` mode fails a vehicle word only when the
customer's quote did not contain it. It cannot tell whether a legitimately sourced domain
word was used faithfully — that is the rubric's job. A future case whose quote genuinely
mentions a vehicle must not be graded by string matching alone.

### REG-002 — unsupported price judgment

An AC quote was once described as "quite high" although QuoteCheck has no market-price
benchmark and none is implemented. The case carries realistic, deliberately large-looking
amounts, so the temptation to editorialize is present in the input.

Its `missing_quote_context == true` assertion rests on **objective absence**: the quote
recommends a compressor replacement while explicitly providing no pressure readings, no
leak-test result, no electrical measurements, no error code, and no diagnostic report. A
reviewer can point at what is missing rather than judging whether a diagnosis "feels
thin".

---

## Expected Demo-mode behaviour

**This corpus targets the intended QuoteCheck product contract, not the current Demo
stub's keyword heuristics.** Demo mode (`backend/core/stub_analyzer.py`) is a small fixed
keyword matcher, not language understanding, and it will fail some cases by construction:

- `ambiguous_items_present` is hardcoded `true`, so the six `clean_itemized` cases will
  fail their `ambiguous_items_present == false` assertion in Demo mode;
- `missing_quote_context` is derived from a fixed phrase list, so it will disagree with
  cases whose missing context is real but differently worded;
- domains outside the keyword list (electronics, most generic service) fall through to a
  single "needs clarification" item.

These are **real, already-documented product gaps** (see `docs/CURRENT_STATE.md`), not
broken cases. They are deliberately left in.

Consequently:

- QC-3B must report results **per mode**, never blended;
- known Demo-mode failures must **not** be xfailed, suppressed, or excluded from pass-rate
  denominators — a suite that hides its red rows is decoration;
- the corpus must not be tuned down to whatever the stub already does.

---

## Non-goals (current)

- No executable runner, scoring code, or CI. QC-3B owns those.
- No `results/` artifacts. QC-3B owns those.
- No price-benchmarking evaluation — there is nothing to evaluate; benchmarking is not
  implemented anywhere in QuoteCheck.
- No vendor-trust or claim-verification evaluation, for the same reason.
- No latency, cost, or throughput benchmarking.
- No statistical significance claims. 27 cases is a coverage instrument, not a sample
  supporting inference about a population.
- No new dependencies. Cases are plain JSON, readable by the standard library.

---

## Relationship to QC-3B

| QC-3A (this ticket) | QC-3B (next) |
|---|---|
| Defines the case schema and the check vocabulary | Implements the checks |
| Writes the 27-case corpus | Runs the corpus against `/analyze` |
| Defines the human rubric | Produces per-mode reports and `results/` artifacts |
| States which checks are proxies | Must carry that framing into its output |

QC-3B must not widen the deterministic vocabulary to make a case pass, must not
re-interpret a `semantic_expectations` field as machine-checkable, and must not report a
Layer A pass rate as a quality score.

---

## Related

- [`rubric.md`](rubric.md) — the human semantic rubric.
- [`termsets.json`](termsets.json) — shared forbidden-term sets.
- `backend/core/schema.py` — the output contract these cases assert against.
- `docs/CURRENT_STATE.md` — what actually exists right now.
- `examples/` — six captured Demo-mode sample reports (illustrative, not an eval).
