# Review bundle — QC-3C — Demo analyzer contract alignment

## 1. Ticket / phase

- Ticket: `docs/tickets/QC-3C-demo-contract-alignment.md`
- Phase: QC-3 evaluation (hardening) — after QC-3B's first Demo baseline; a
  Demo-analyzer contract repair driven by that baseline.
- Branch: `task/QC-3C-demo-contract-alignment`
- Not committed. No deployment. **No paid OpenAI API call of any kind was made.**

## 2. Scope summary

Repaired clearly incorrect / over-broad deterministic behaviour in
`backend/core/stub_analyzer.py` that the QC-3B baseline exposed, added focused
Demo-analyzer unit tests, regenerated the six committed Demo example outputs through
the real Demo `/analyze` path, and recorded a new Demo baseline from the **unchanged**
27-case corpus.

**Scope expansion (user-approved).** The ticket's original file-scope sketch did not
list `examples/`. It was expanded to include `examples/*.json` because QC-3C changes
deterministic Demo output and leaving the committed example outputs stale would make
the repository internally inconsistent (QC-1B set the precedent of regenerating them
on a Demo-behaviour change). Example **inputs** (`examples/*.txt`) are unchanged.

Not touched: `eval/cases/**`, `eval/termsets.json`, `eval/rubric.md`, `eval/graders.py`,
`eval/corpus.py`, `eval/run_eval.py`; `backend/core/openai_analyzer.py`,
`backend/core/prompt.py` (`PROMPT_VERSION` stays `quotecheck_v0.4`),
`backend/core/schema.py`, `backend/app.py`; `frontend/**`; `SPEC.md`; dependency /
deployment files; historical ticket / review documents. No new dependency.

## 3. QC-3B baseline (the starting point)

`eval/results/summary_20260829T105921Z.md` (retained):

| Metric | Value |
|---|---|
| Total cases | 27 |
| Schema passes | 27 / 27 (100.0%) |
| Deterministic invariant passes | **11 / 27 (40.7%)** |
| Execution errors | 0 |

All 16 failures were on `uncertainty_marker:*` or
`line_items_where:vague_or_confusing`. Zero `schema_valid` / `metadata_complete` /
`forbidden_terms` failures. REG-001 and REG-002 leakage + price-judgment guards
passed; both REG cases failed only a marker check.

## 4. Failure forensics — all 16 QC-3B failures

Stub facts: `vehicle` = `brake`/`tyre`/`tire`; `ac`, `home` = keyword lists; `generic`
= `GENERIC_CHARGE_TERMS` (incl. bare `labour`/`labor`). Only `brake` produced a
`red`/`safety_critical` item. `missing_quote_context = <15 fixed phrases> or (generic
and not vehicle/ac/home)`. `ambiguous_items_present = True` (constant).

| case | failed check(s) | observed→expected | quote characteristic | stub rule at fault | class |
|---|---|---|---|---|---|
| AUTO-001 | ambiguous_items_present; missing_quote_context | T→F; T→F | fully itemised service, `Labour … Rs.550/hr`, totals, warranty | constant `True`; `"labour"` ⇒ vague generic item + `only_generic_charges` | **A** |
| CONT-001 | ambiguous_items_present | T→F | fully itemised cabinet quote; `home` fires on `plumbing`/`electrical` in the exclusions list; `Labour … @ Rs.900` | constant `True`; `"labour"` ⇒ extra vague item | **A** |
| ELEC-001 | ambiguous_items_present; missing_quote_context | T→F; T→F | fully itemised laptop repair, part no., diagnostic shown; `Bench labour … Rs.1,200` | no electronics branch ⇒ `"labour"` is the only match ⇒ single vague generic item + `only_generic_charges` | **A** |
| GEN-001 | ambiguous_items_present | T→F | fully itemised 12-month pest-control contract | constant `True`; no keyword match ⇒ single vague fallback item | **A** |
| HOME-001 | ambiguous_items_present | T→F | fully itemised surveyed tap/valve swap; `home` fires on `plumbing`; `Labour … Rs.700/hr` | constant `True`; `"labour"` ⇒ extra vague item | **A** |
| HVAC-001 | ambiguous_items_present; missing_quote_context | T→F; T→F | fully itemised AMC; exclusions block reads "**Not included**, chargeable separately …" | constant `True`; `"not included"` phrase matches a benign exclusions list | **A** |
| CONT-003 | missing_quote_context | F→T | renovation; 4 lines w/ real qty/rates; "subject to a **site inspection**", "estimate **may vary** 10–15%", rewiring "**will be revised**" | conditional wording not in the fixed phrase list; `home` fired ⇒ `only_generic_charges` false | **A** |
| CONT-004 | missing_quote_context | F→T | large partly-itemised total; 3 of 5 lines are "**consolidated figures**"; brands "selected … during execution" | deferred-specification wording not in phrase list; `home` fired (`electrical`) | **A** |
| ELEC-002 | missing_quote_context | F→T | preliminary assessment: one committed `Rs.1,500`, rest ranges / "**may need replacement**" / "before a **firm quote**" / "estimate **may vary**" | provisional wording not in phrase list; no domain/generic ⇒ single vague fallback, but `only_generic_charges` needs `generic` | **A** |
| HOME-002 | missing_quote_context; line_items_where:vague_or_confusing | F→T; 0→≥1 | price but no scope: "plumbing work **as required**", "Materials extra **at actual**", "verbal site visit" | `home` fires on `plumbing` ⇒ one *non-vague* item; open-scope wording not detected | **A** |
| HVAC-002 | line_items_where:vague_or_confusing | 0→≥1 | washing-machine job card; bundled "Service handling", "Materials as required", "Site charges" | none of those phrasings in `GENERIC_CHARGE_TERMS`; `appliance` ⇒ one non-vague item | **A** |
| AUTO-004 | needs_professional_confirmation | F→T | control arms + ball joints from a "knocking noise" symptom, no measurement | no `brake`/`tyre` ⇒ no `red`/`safety_critical` item; suspension/steering has no safety keyword | **A** |
| CONT-005 | needs_professional_confirmation | F→T | cut a 7 ft opening; "**load bearing**", "**lintel / support beam**", "**structural drawing** not prepared" | structural hazard has no safety keyword | **A** |
| HOME-003 | needs_professional_confirmation | F→T | replace **consumer unit** + RCBOs, dedicated circuit, **earth bonding** | domestic-mains work classified green by the `home` branch | **A** |
| REG-001 | needs_professional_confirmation | F→T | compressor replacement, **brazing**, "**full system evacuation**", refrigerant recharge | sealed-refrigerant work classified yellow by the `ac` branch | **A** |
| REG-002 | missing_quote_context | F→T | compressor replacement from "not cooling" alone; "**Diagnostic report available on request**" (i.e. not attached); no readings | deferred-diagnostic wording not in phrase list; `ac` fired ⇒ `only_generic_charges` false | **A** |

Root-cause groups: (1) constant `ambiguous_items_present`; (2) bare `"labour"`/`"labor"`
over-match; (3) `"not included"` over-match; (4) `GENERIC_CHARGE_TERMS` too narrow;
(5) no provisional/deferred-pricing detection; (6) unrecognised domain collapse to one
vague fallback; (7) `needs_professional_confirmation` only fires on `brake`/`tyre`.

**All 16 are class A.** None is a class-C eval-expectation problem. The corpus,
termsets, and rubric are unchanged. (The softest expectation, AUTO-004
`missing_quote_context = true`, is still defensible — the quote genuinely gives no
diagnostic basis — but is not reachable by a small observable rule; see §6.)

## 5. Failures selected for repair

All seven root-cause groups. Implemented as small, individually explainable rules in
`backend/core/stub_analyzer.py` (§8), holding to the review corrections:

- Quote-level `missing_quote_context` and line-level `vague_or_confusing` stay
  **separate** — a deferred-context phrase never marks a line item vague.
- `ambiguous_items_present` is `any(item.vague_or_confusing for item in line_items)`,
  never manufactured from quote-level context.
- No "safety-sensitive + stub-couldn't-classify ⇒ missing context" coupling.
- `SAFETY_RISK_TERMS` matched whole-word; narrow component/hazard vocabulary only
  (no `automotive`, no standalone `suspension`).
- New `GENERIC_CHARGE_TERMS` entries are charge-like phrases, not bare English words.
- The new price-safety unit test asserts only the exact `eval/termsets.json`
  `price_judgment` phrases, not bare `high`/`low`/`fair`.

## 6. Failures deliberately not repaired

QC-3C did **not** chase the corpus to green. After the repairs, three residual
failures remain and are left visible:

| case | residual failed check | why not repaired |
|---|---|---|
| AUTO-004 | `missing_quote_context` (expected `true`) | `needs_professional_confirmation` is now fixed. `missing_quote_context` was passing in QC-3B only via the accidental bare-`labour` `only_generic_charges` path. The correct value here rests on "a safety recommendation from a symptom alone, with no measurement" — a semantic judgment with no explicit deferred/omitted-detail phrasing in the quote. Adding a "safety work + no reading ⇒ missing context" rule was explicitly ruled out in review as a score-chasing heuristic. |
| CONT-003 | `ambiguous_items_present` (expected `true`) | `missing_quote_context` is now fixed. The conditional framing ("subject to a site inspection", "estimate may vary") lives in a price-less Conditions block, so the line-level scan cannot attach vagueness to a priced line, and the coarse `renovation` domain item is non-vague. Marking it vague would require inferring quote-wide ambiguity from quote-level context — forbidden by review correction 1. |
| HVAC-003 | `ambiguous_items_present` (expected `true`) | Same structural limitation: the single conditional line ("a second gasket may need to be ordered") carries no monetary amount, and the coarse `appliance` item is non-vague. This is the one case that regressed pass→fail when `ambiguous_items_present` stopped being hardcoded; the hardcode had been masking that the coarse analyzer cannot represent conditional uncertainty confined to one sub-line. |

Common thread: the deterministic Demo analyzer emits at most **one coarse line item
per matched domain**, so a conditional sub-line cannot be flagged without over-flagging
the whole quote. Recorded in `docs/CURRENT_STATE.md` Gaps.

## 7. Analyzer design — before

- `ambiguous_items_present = True` (literal constant in the `UncertaintyMarkers(...)`
  call).
- `GENERIC_CHARGE_TERMS` = `misc, miscellaneous, labour, labor, service charge, gas
  top-up, consumables, other charges, unitemized charges`; a substring `in` match set
  `generic_charge_matched`, which appended one "Other/unspecified charges" item with
  `vague_or_confusing = True`.
- `MISSING_CONTEXT_PHRASES` (15 fixed substrings incl. `"not included"`).
  `missing_quote_context = any(phrase in text) or (generic_charge_matched and not
  (vehicle or ac or home))`.
- `needs_professional_confirmation = any(item.risk_level == red or
  item.normalized_category == safety_critical)` — in practice only `brake`/`tyre`.
- Unrecognised domain (no `brake`/`tyre`, no `ac`, no `home`, no generic term) ⇒ one
  `"Unclear item(s) - needs clarification"` fallback item.

## 8. Analyzer design — after

`backend/core/stub_analyzer.py`, all deterministic, no network, no new dependency:

- **`ambiguous_items_present = any(li.vague_or_confusing for li in items)`** — a pure
  summary of the line items; nothing else sets it.
- **`GENERIC_CHARGE_TERMS`** — bare `"labour"`/`"labor"` removed; replaced/extended
  with charge-like phrases: `misc, miscellaneous, service charge, service handling,
  handling charge, shop supplies, sundries, site charge, site charges, materials as
  required, materials extra, labour adjustment, labor adjustment, labour extra, lump
  sum, consumables, other charges, unitemized charges, gas top-up`. Matched
  whole-word / whole-phrase (`_matches_any` → `(?<!\w)…(?!\w)`, `\s+` between words).
- **`DEFERRED_DETAIL_TERMS`** — replaces `MISSING_CONTEXT_PHRASES`; drops
  `"not included"`; adds provisional / deferred / externalised wording
  (`provisional`, `subject to inspection`, `site inspection`, `estimate may vary`,
  `firm quote`, `indicative total/cost`, `to be confirmed`, `will be assessed/advised/
  revised`, `consolidated figure(s)`, `diagnostic report available`, `as per work`,
  `at actual(s)`, …). **Sets `missing_quote_context` only; never marks a line item
  vague.**
- **`SAFETY_RISK_TERMS`** (whole-word) — structural/load-bearing (`load bearing`,
  `structural`, `lintel`, `rsj`), mains-electrical (`consumer unit`, `earth bonding`,
  `earthing`, `rcbo(s)`, `rcd`, `residual current device`, `distribution board`),
  sealed-refrigerant (`brazing`, `system evacuation`, `sealed system`, `refrigerant
  recharge`, `gas charging`, `compressor replacement`), safety-critical mechanical
  components (`brake(s)`, `control arm(s)`, `ball joint(s)`, `steering`, `tie
  rod(s)`). Broad words (`suspension`, `automotive`, `contractor`) are not triggers.
- **Line scan** (`_is_itemised_line` = label + `Rs.`/`₹`/`INR`/`/-` amount, minus
  total/tax/subtotal):
  - no domain and no generic term matched and ≥ 2 priced lines ⇒ emit one
    `unknown_needs_clarification` item per line (cap 5) instead of the single
    fallback; a line is `vague_or_confusing` only if its own text carries a
    `GENERIC_CHARGE_TERMS` phrase or (an amount **and** an on-line approximate token
    from `{approx, tbd, to be confirmed, range, may vary, may need}`);
  - any path ⇒ additionally, any priced line whose own text carries an approximate
    token becomes one `vague_or_confusing = true` item (strictly line-level).
  - fewer than 2 priced lines and nothing else matched ⇒ the existing single
    `"Unclear item(s) - needs clarification"` fallback.

## 9. Ambiguity-marker rule

```
ambiguous_items_present = any(li.vague_or_confusing for li in items)
```
A line item is `vague_or_confusing` when: it is the `GENERIC_CHARGE_TERMS` summary
item; or the no-detail fallback item; or a line-scan item whose own source line
carries a generic charge label or (an amount + an approximate token). Quote-level
context gaps do **not** feed this marker.

## 10. Missing-context rule

```
deferred_detail_matched = any DEFERRED_DETAIL_TERMS phrase is in the quote (whole-word)
only_unclear_items      = items and every line item is vague_or_confusing
missing_quote_context   = deferred_detail_matched or only_unclear_items
```
Explainable in one sentence each: the quote's own wording says material detail is
omitted / deferred / provisional / externalised, **or** the analysis resolved to
nothing but unclear charges. It is not set from domain-recognition failure, quote
length, or a single vague line among precise ones.

## 11. Generic-domain behaviour

Retained: the `vehicle` / `ac` / `home` keyword blocks and their enrichments
(explanations, `evidence_needed`, domain-appropriate questions) — additive, unchanged.
Added: when none of those and no generic-charge term matched, a currency-token line
scan reproduces a quote with ≥ 2 priced lines line by line
(`normalized_category = unknown_needs_clarification`, figures/labels taken from the
quote as written, `vague_or_confusing` decided per line). This fixes ELEC-001 and
GEN-001 (fully itemised quotes that previously collapsed to one vague item). No NLP
parser, no regex invoice parser, no OCR, no classifier — a line filter on a currency
token plus a six-word token set.

## 12. Professional-confirmation behaviour

```
needs_professional_confirmation = (
    any(li.risk_level == red or li.normalized_category == safety_critical for li in items)
    or _matches_any(text_lower, SAFETY_RISK_TERMS)   # whole-word
)
```
Trigger = a named safety-critical component / hazard in the quote, or a
red/safety-critical line item — never trade or domain identity. Checked against the
four `professional_confirmation_not_expected` cases (ELEC-004, GEN-001, HOME-001,
HVAC-003): none contains any `SAFETY_RISK_TERMS` phrase, so all stay `false`
(HVAC-003's residual failure is on `ambiguous_items_present`, not this marker). These
terms only set the boolean; they are never written into analysis text, so REG-001's
`vehicle_domain` leakage guard is unaffected (verified — §16).

## 13. Automated tests

`eval/tests/test_stub_analyzer.py` (new, stdlib `unittest`, run by the existing
`python -m unittest discover -s eval/tests -p 'test_*.py'`):

- schema round-trip + provenance (`model == quotecheck-demo-analyzer`,
  `prompt_version == PROMPT_VERSION`, `schema_valid is True`);
- clean itemised quote ⇒ no vague line item, `ambiguous_items_present is False`,
  `missing_quote_context is False`; clean plumbing quote not escalated;
- bundled quote ⇒ ≥ 1 vague line item with non-empty `evidence_needed`,
  `ambiguous_items_present is True`; a bare `Labour … Rs./hr` line alone is neither
  vague nor missing-context;
- explicit deferred-detail quote ⇒ `missing_quote_context is True`; a mostly-precise
  quote with one externally-referenced element sets the quote-level flag **without**
  making every priced line vague;
- unknown-domain itemised quote ⇒ > 1 line item, not the single
  `"Unclear item(s) - needs clarification"` fallback; a no-detail quote still uses it;
- benign work ⇒ `needs_professional_confirmation is False`; structural /
  mains-electrical / sealed-refrigerant work ⇒ `True`; an automotive quote naming no
  safety-critical component ⇒ `False` (domain identity alone does not escalate);
- non-vehicle quotes ⇒ no `eval/termsets.json` `vehicle_domain` phrase in
  analysis-authored text;
- price-bearing quotes ⇒ none of the exact `eval/termsets.json` `price_judgment`
  phrases in analysis-authored text (bare `high`/`low`/`fair` are **not** asserted
  absent).

Result: **76 tests, all pass** (harness self-tests 60 → 76).

## 14. New eval result

`eval/results/summary_20260829T115912Z.md` — `python -m eval.run_eval --mode demo`,
exit code **1** (residual failures retained, not suppressed):

| Metric | Value |
|---|---|
| Total cases | 27 |
| Schema passes | 27 / 27 (100.0%) |
| Deterministic invariant passes | **24 / 27 (88.9%)** |
| Execution errors | 0 |

Failures by domain: automotive 4/5, contractor_vendor 4/5, hvac_appliance 4/5,
electronics_repair 4/4, generic_service 4/4, plumbing_home 4/4.
Failures by category: `conditional_work` 3/5, `professional_confirmation_expected`
3/4, `professional_confirmation_not_expected` 3/4, `missing_scope_or_quantity` 8/9;
all others 100%. `clean_itemized` 6/6, `vague_bundled_charge` 6/6,
`cross_domain_trap` 5/5, `price_present` 10/10.

Failed cases (all `uncertainty_marker`, no schema / metadata / forbidden-term
failure): AUTO-004 `missing_quote_context`; CONT-003 `ambiguous_items_present`;
HVAC-003 `ambiguous_items_present`.

## 15. Before / after baseline comparison

**Same 27-case corpus, unchanged between runs**
(`git diff -- eval/cases eval/termsets.json eval/rubric.md` is empty — §16).

    deterministic contract pass count improved from 11/27 to 24/27
    (27/27 schema-valid in both runs)

This is a deterministic contract / regression pass count. It is **not** an accuracy,
model-quality, or hallucination measurement, and no semantic (Layer B) judgement was
made.

Per-case:

| case | QC-3B | QC-3C | note |
|---|---|---|---|
| AUTO-001 | FAIL | pass | fixed |
| AUTO-002 | pass | pass | |
| AUTO-003 | pass | pass | |
| AUTO-004 | FAIL | FAIL | `needs_professional_confirmation` fixed; now fails `missing_quote_context` (was passing incidentally via bare-`labour`) |
| AUTO-005 | pass | pass | |
| CONT-001 | FAIL | pass | fixed |
| CONT-002 | pass | pass | |
| CONT-003 | FAIL | FAIL | `missing_quote_context` fixed; now fails `ambiguous_items_present` (coarse domain item) |
| CONT-004 | FAIL | pass | fixed |
| CONT-005 | FAIL | pass | fixed |
| ELEC-001 | FAIL | pass | fixed |
| ELEC-002 | FAIL | pass | fixed |
| ELEC-003 | pass | pass | |
| ELEC-004 | pass | pass | |
| GEN-001 | FAIL | pass | fixed |
| GEN-002 | pass | pass | |
| GEN-003 | pass | pass | |
| GEN-004 | pass | pass | |
| HOME-001 | FAIL | pass | fixed |
| HOME-002 | FAIL | pass | fixed |
| HOME-003 | FAIL | pass | fixed |
| HOME-004 | pass | pass | |
| HVAC-001 | FAIL | pass | fixed |
| HVAC-002 | FAIL | pass | fixed |
| HVAC-003 | pass | FAIL | regressed on `ambiguous_items_present`: de-hardcoding exposed that the coarse `appliance` item cannot carry a conditional sub-line |
| REG-001 | FAIL | pass | fixed |
| REG-002 | FAIL | pass | fixed |

13 fixed, 1 regressed (HVAC-003), 2 lateral (AUTO-004, CONT-003 — a different check
now fails on a case that already failed).

## 16. REG-001 / REG-002 status

Both cases now pass **in full** (QC-3B: both failed a marker check). From
`run_20260829T115912Z.jsonl`:

- **REG-001** `deterministic_pass = true`:
  - `uncertainty_marker:needs_professional_confirmation` — expected True, observed True (PASS)
  - `line_items_where:evidence_needed_nonempty` — 1 line item (index [0]) (PASS)
  - `forbidden_terms:vehicle_domain` (`not_in_source`) — no terms in analysis-authored text (PASS)
  - `forbidden_terms:price_judgment` (`absolute`) — no terms (PASS)
- **REG-002** `deterministic_pass = true`:
  - `uncertainty_marker:missing_quote_context` — expected True, observed True (PASS)
  - `forbidden_terms:price_judgment` (`absolute`) — no terms (PASS)
  - `forbidden_terms:vehicle_domain` (`not_in_source`) — no terms (PASS)

The leakage / price-judgment invariants QC-3A added these cases to guard continue to
hold; QC-3C also closes their marker gaps. Regression-only rerun
(`--mode demo --case-id REG-001 --case-id REG-002`, scratch results dir): `2/2
schema-valid; 2/2 deterministic cases pass`, exit 0.

## 17. Acceptance-criteria table

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | All 16 failures inspected + classified before edits | Met | §4 (all class A) |
| 2 | Only justified defects repaired | Met | §5, §6 |
| 3 | `ambiguous_items_present` derived, not hardcoded | Met | §9; `stub_analyzer.py` |
| 4 | Small evidence-based `missing_quote_context` rule; separate from line vagueness | Met | §10 |
| 5 | Unknown/generic domains not collapsed when priced detail exists | Met | §11; ELEC-001/GEN-001 pass |
| 6 | Vague bundled charges still surface ambiguity + evidence; clean stays clean | Met | §13 tests; `vague_bundled_charge` 6/6, `clean_itemized` 6/6 |
| 7 | Conservative, non-domain-triggered professional confirmation | Met | §12; 3/4 `pcne` pass (HVAC-003 fails a different marker) |
| 8 | REG-001 `vehicle_domain` guard passes | Met | §16 |
| 9 | REG-002 `price_judgment` guard passes | Met | §16 |
| 10 | 27/27 schema validity preserved | Met | §14 |
| 11 | Same unchanged corpus rerun | Met | §18 (`git diff -- eval/cases …` empty) |
| 12 | New pass count recorded truthfully, before/after explicit | Met | §14, §15 |
| 13 | Residual failures documented, not hidden | Met | §6; exit code 1 |
| 14 | Focused Demo-analyzer tests pass; harness self-tests pass | Met | §13 (76/76) |
| 15 | No eval case / termset / rubric change | Met | §18 |
| 16 | No frontend change | Met | §20 |
| 17 | No OpenAI analyzer / prompt change; `PROMPT_VERSION` unchanged | Met | §20; still `quotecheck_v0.4` |
| 18 | No new dependency | Met | stdlib `re` only |
| 19 | No paid API call | Met | §18 (paid guard exit 2) |
| 20 | New baseline retained alongside QC-3B baseline | Met | §18 (`run_20260829T105921Z.*` unchanged) |
| 21 | Nothing committed | Met | §20 |

## 18. Exact commands / results

Run in the project's `quotecheck` conda env (Python 3.11.14, pydantic 2.12.5), from
the repo root.

```
$ python -m compileall backend eval -q
compileall OK exit=0

$ python -m unittest discover -s eval/tests -p 'test_*.py'
Ran 76 tests in 0.109s
OK

$ python -m eval.run_eval --validate-only        ; echo exit=$?
[1] 27/27 case files parsed ... [11] category consistency : enforced
OK — 27 cases, 6 domains, 9 categories, 0 errors.
exit=0

$ python -m eval.run_eval --mode demo
Wrote .../eval/results/run_20260829T115912Z.jsonl
Wrote .../eval/results/summary_20260829T115912Z.md
27/27 schema-valid; 24/27 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation
(known Demo-mode gaps are retained, not suppressed).
# exit code 1

$ python -m eval.run_eval --mode demo --case-id REG-001 --case-id REG-002 --results-dir <scratch> ; echo exit=$?
2/2 schema-valid; 2/2 deterministic cases pass.
exit=0

$ python -m eval.run_eval --mode openai            ; echo exit=$?
Refusing to run OpenAI mode without --allow-paid. ... No API call was made.
exit=2

# regenerate the 6 committed Demo examples through the real Demo /analyze (no OpenAI)
$ PYTHONPATH=. python <regen script>
examples/sample_output.json                 items=3 amb=True  missing=False needs_prof=True  model=quotecheck-demo-analyzer
examples/outputs/vehicle_service.json       items=3 amb=True  missing=False needs_prof=True  model=quotecheck-demo-analyzer
examples/outputs/ac_repair.json             items=1 amb=False missing=False needs_prof=True  model=quotecheck-demo-analyzer
examples/outputs/home_maintenance.json      items=1 amb=False missing=True  needs_prof=False model=quotecheck-demo-analyzer
examples/outputs/parts_labour_misc.json     items=1 amb=True  missing=True  needs_prof=False model=quotecheck-demo-analyzer
examples/outputs/vague_missing_details.json items=1 amb=True  missing=True  needs_prof=False model=quotecheck-demo-analyzer
OK - 6 examples regenerated, all schema-valid, no OpenAI call

$ git diff -- eval/cases eval/termsets.json eval/rubric.md
# (no output — empty)

$ git diff --check
# (no output — clean)
```

## 19. Remaining limitations

- **AUTO-004 / CONT-003 / HVAC-003** — see §6. The coarse one-item-per-domain Demo
  analyzer cannot flag conditional uncertainty confined to a single sub-line
  (`ambiguous_items_present`) or infer a missing diagnostic basis from a symptom-only
  safety recommendation with no deferred-detail phrasing (`missing_quote_context`).
- Keyword coverage is still a fixed list — a vague charge whose label matches none of
  `GENERIC_CHARGE_TERMS`, and an unrecognised-domain quote with fewer than 2 priced
  lines, still fall through to the single generic fallback item.
- The line scan detects `Rs.`/`₹`/`INR`/`/-` amounts only; a quote using a currency
  format it does not recognise will not be reproduced line by line.
- Layer B (faithfulness, unsupported inference, calibration, explanation quality,
  actionability, professional-boundary) is unscored — a 24/27 Layer A pass rate is
  not a quality number. `eval/rubric.md` remains a manual pass.
- Minor wording tidy in the no-detail fallback line item ("Ask the service center" →
  "Ask the vendor"; explanation now also lists "priced line items"), for
  domain-neutral consistency with the rest of the file. No behavioural effect.
- `examples/README.md` prose still describes the generic vague-charge catch-all
  firing on `quote_parts_labour_misc.txt` / `quote_vehicle_service.txt`; still true
  (those inputs contain `miscellaneous` / `shop supplies` / `other charges`), so the
  file was left unchanged.

## 20. git status / diff stat

```
$ git status --short
 M README.md
 M backend/core/stub_analyzer.py
 M docs/CURRENT_STATE.md
 M eval/README.md
 M examples/outputs/ac_repair.json
 M examples/outputs/home_maintenance.json
 M examples/outputs/parts_labour_misc.json
 M examples/outputs/vague_missing_details.json
 M examples/outputs/vehicle_service.json
 M examples/sample_output.json
?? docs/review/REVIEW_BUNDLE__QC-3C-demo-contract-alignment.md
?? docs/tickets/QC-3C-demo-contract-alignment.md
?? eval/results/run_20260829T115912Z.jsonl
?? eval/results/summary_20260829T115912Z.md
?? eval/tests/test_stub_analyzer.py

$ git diff --stat
 README.md                                   |  14 +-
 backend/core/stub_analyzer.py               | 365 +++++++++++++++++++++++------
 docs/CURRENT_STATE.md                       | 100 +++++++-
 eval/README.md                              |  13 +-
 examples/outputs/ac_repair.json             |   8 +-
 examples/outputs/home_maintenance.json      |   6 +-
 examples/outputs/parts_labour_misc.json     |   8 +-
 examples/outputs/vague_missing_details.json |   8 +-
 examples/outputs/vehicle_service.json       |   8 +-
 examples/sample_output.json                 |   8 +-
 10 files changed, 417 insertions(+), 121 deletions(-)
```

- `eval/cases/**`, `eval/termsets.json`, `eval/rubric.md`, `eval/graders.py`,
  `eval/corpus.py`, `eval/run_eval.py` — not in the diff.
- `backend/core/prompt.py`, `backend/core/openai_analyzer.py`,
  `backend/core/schema.py`, `backend/app.py` — not in the diff.
- `frontend/**`, `SPEC.md`, dependency / deployment files, historical ticket / review
  docs — not in the diff.
- `eval/results/run_20260829T105921Z.*` (QC-3B baseline) — not modified, not deleted.
- Not committed — left for the user to review and commit manually.
