# Review Bundle — QC-1B — Domain-neutral uncertainty contract + provenance cleanup

## 1. Ticket / phase

- Ticket: `docs/tickets/QC-1B-domain-neutral-contract.md`
- Phase: QC-1 hardening (post-QC-1A, pre-QC-3 eval harness)
- Branch: `task/QC-1B-domain-neutral-contract`
- Not committed. No deployment.

## 2. Scope summary

Small contract / provenance hardening. Removed the two vehicle-specific uncertainty
fields from the machine contract, replaced the Demo stub's hardcoded vehicle-era
uncertainty values with deterministic heuristics, made failure-path logging
mode-aware, corrected a misleading "fallback" docstring, removed confirmed-dead
`schema_json` plumbing, and regenerated the six committed Demo examples against the
current contract. `NormalizedCategory` deliberately untouched. No new capability,
eval infra, dependency, retry logic, deployment, or UI change. Frontend not touched
(it never referenced the uncertainty markers).

## 3. Contract change

`backend/core/schema.py` — `UncertaintyMarkers`:

| Old field | New field |
|---|---|
| `missing_vehicle_context: bool` | `missing_quote_context: bool = Field(..., description=…)` |
| `needs_mechanic_confirmation: bool` | `needs_professional_confirmation: bool = Field(..., description=…)` |

- No back-compat aliases (there are no known production consumers — a clean
  contract was preferred).
- `ambiguous_items_present` unchanged.
- `QuoteCheckResult.uncertainty_markers` `default_factory` updated to the new kwarg
  names (still conservative all-`True`; both analyzers pass the value explicitly, so
  this default is effectively dead but must stay valid).

Field descriptions as committed:

- `missing_quote_context` — "True when the quote omits contextual information needed
  to interpret one or more recommendations confidently, such as scope, symptoms,
  quantities, diagnostic basis, or other material details. This is not a synonym
  for 'the quote contains a vague line item.'"
- `needs_professional_confirmation` — "True when one or more technical or
  safety-sensitive recommendations should be confirmed by an appropriate qualified
  professional (for the relevant trade or domain) before relying on this analysis.
  Domain-neutral."

## 4. Design decision for new uncertainty semantics

**`missing_quote_context`** must mean "material context needed to interpret a
recommendation is actually absent", NOT "a line item is vaguely named" (that is
`vague_or_confusing` / `ambiguous_items_present`). It must not be driven by the
deterministic analyzer merely failing to recognise a domain — the limited keyword
list not knowing a domain is not evidence about the user's quote.

**`needs_professional_confirmation`** must be domain-neutral: keyed off whether
genuinely safety-sensitive / technical work was identified, never off a specific
trade word.

Deterministic Demo rules (`backend/core/stub_analyzer.py`):

```python
# fixed substring list, same technique as AC_APPLIANCE_TERMS / GENERIC_CHARGE_TERMS
explicit_missing_context = any(term in text_lower for term in MISSING_CONTEXT_PHRASES)
only_generic_charges = generic_charge_matched and not (
    vehicle_matched or ac_matched or home_matched
)
missing_quote_context = explicit_missing_context or only_generic_charges

needs_professional_confirmation = any(
    it.risk_level == RiskLevel.red
    or it.normalized_category == NormalizedCategory.safety_critical
    for it in items
)
```

`MISSING_CONTEXT_PHRASES` = `no specific`, `not included`, `no measurements`,
`no parts`, `follow-up estimate`, `to be determined`, `tbd`, `approximate total`,
`as agreed`, `as discussed`, `discussed during`, `attached estimate`,
`see attached`, `depending on additional work`, `additional work found`.

Rationale:
- `explicit_missing_context` — the quote text itself says context is deferred,
  omitted, externalised, or only approximate.
- `only_generic_charges` — the quote resolves to nothing but bundled/un-itemised
  charges with no substantive service item; itemisation/scope is genuinely absent.
  Requires the absence of any substantive domain item, so it is not a mirror of the
  `vague_or_confusing` flag alone.
- Domain-recognition failure alone is deliberately **not** a trigger.
- `needs_professional_confirmation` reuses the analyzer's existing risk/category
  determination; it is `true` for a quote with `red` risk or `safety_critical`
  work regardless of trade.

Expected vs. actual for the six example inputs (all matched):

| Input | `missing_quote_context` | trigger | `needs_professional_confirmation` |
|---|---|---|---|
| `examples/quote_vehicle_service.txt` | `false` | — | `true` (brake red / safety_critical) |
| `examples/sample_quote.txt` | `false` | — | `true` (brake red / safety_critical) |
| `examples/quote_ac_repair.txt` | `false` | — | `false` |
| `examples/quote_home_maintenance.txt` | `true` | "no specific parts or measurements", "follow-up estimate" | `false` |
| `examples/quote_parts_labour_misc.txt` | `true` | "depending on additional work found" + only-generic-charges | `false` |
| `examples/quote_vague_missing_details.txt` | `true` | "attached estimate", "discussed during our call", "approximate total", "as agreed" | `false` |

No AC/appliance, home/contractor, generic, or vague case receives
`needs_professional_confirmation=true`; the vehicle cases still do, for real
safety-critical work.

## 5. Files changed

| File | Change |
|---|---|
| `backend/core/schema.py` | `UncertaintyMarkers` field rename + `Field` descriptions; `default_factory` kwargs renamed |
| `backend/core/prompt.py` | `PROMPT_VERSION` → `quotecheck_v0.4`; `DEVELOPER_PROMPT` uncertainty instruction rewritten domain-generic + `needs_professional_confirmation` instruction added; `build_messages()` `schema_json` param removed (+ docstring note) |
| `backend/core/stub_analyzer.py` | misleading "fallback" docstring reworded; `MISSING_CONTEXT_PHRASES` added; deterministic `missing_quote_context` / `needs_professional_confirmation` computed in `analyze_quote_stub`; hardcoded vehicle-era `UncertaintyMarkers` values removed |
| `backend/core/openai_analyzer.py` | dead `schema_str = quotecheck_result_schema_json()` var + call removed; import trimmed to `quotecheck_result_schema_obj`; `build_messages(quote_text=…)` |
| `backend/core/schema_export.py` | orphaned `quotecheck_result_schema_json()` helper removed; now-unused `import json` removed; module docstring updated. `quotecheck_result_schema_obj()` / `_normalize_for_openai_strict` / `_make_nullable` unchanged |
| `backend/app.py` | failure-path log `model` is now `MODEL if USE_OPENAI else DEMO_ANALYZER_MODEL`; import adds `DEMO_ANALYZER_MODEL` |
| `examples/sample_output.json`, `examples/outputs/{vehicle_service,ac_repair,home_maintenance,parts_labour_misc,vague_missing_details}.json` | regenerated via the real Demo `/analyze` endpoint (no OpenAI call) |
| `docs/CURRENT_STATE.md` | `Last updated` → `2026-08-28 (QC-1B)`; live prompt-version + uncertainty-semantics text updated; Gaps bullet field name updated; new `### Fixed in QC-1B` block; historical blocks untouched |
| `README.md` | prompt-version string `quotecheck_v0.3` → `quotecheck_v0.4` (one line) |
| `docs/tickets/QC-1B-domain-neutral-contract.md` | new (this ticket) |
| `docs/review/REVIEW_BUNDLE__QC-1B-domain-neutral-contract.md` | new (this bundle) |

Not changed: `frontend/`, `backend/core/run_logger.py`, `backend/core/config.py`,
dependency files, `.env*`, deployment config, `SPEC.md`, `examples/README.md`
(inspected — its references are generic and still accurate), `NormalizedCategory`.

## 6. Prompt-version decision and rationale

**Bumped `quotecheck_v0.3` → `quotecheck_v0.4`.** The change renames two
model-visible output fields (`missing_vehicle_context` → `missing_quote_context`,
`needs_mechanic_confirmation` → `needs_professional_confirmation`) and redefines
what the model is told to put in them. That is a model-visible behavior change,
exactly what `PROMPT_VERSION` exists to track. Next increment in the existing
`quotecheck_v0.N` scheme; no new versioning machinery. Live references updated:
`backend/core/prompt.py:19`, `README.md:230`, `docs/CURRENT_STATE.md:32`.
Historical mentions (`docs/CURRENT_STATE.md` TASK-002 / TASK-012 blocks, prior
review bundles) left as-is.

## 7. Demo uncertainty logic

See §4. The stub now derives both fields from evidence it already computes
(`text_lower`, `vehicle_matched` / `ac_matched` / `home_matched` /
`generic_charge_matched`, and the built `items` list) plus one new fixed-substring
list. No LLM, no network, no new dependency — still transparent keyword heuristics.
`ambiguous_items_present` remains a constant `True` (deliberately out of QC-1B
scope; noted in §14).

## 8. Provenance fix

`backend/app.py` `except` path previously logged `model=MODEL` (`gpt-4o-mini`)
regardless of mode. Now:

```python
failure_model = MODEL if USE_OPENAI else DEMO_ANALYZER_MODEL
```

`backend/core/run_logger.py` unchanged (it records whatever `model` string it is
handed). No new provenance field — mode is fully recoverable from the corrected
`model` value, consistent with the success path.

Verified (FastAPI `TestClient`, forced failure in each mode, last JSONL line
inspected):

```
########## Provenance: Demo-mode failure ##########
HTTP 500 | logged model = quotecheck-demo-analyzer | schema_valid = False | error = RuntimeError: forced demo failure
PASS — Demo failure logs quotecheck-demo-analyzer, not gpt-4o-mini

########## Provenance: OpenAI-mode failure ##########
HTTP 500 | logged model = gpt-4o-mini | error = RuntimeError: OPENAI_API_KEY is not set. Add it to backend/.env (untracked).
PASS — OpenAI failure logs the configured QUOTECHECK_MODEL
```

## 9. Dead-plumbing result

**Confirmed dead.** `build_messages(*, quote_text, schema_json)` never referenced
`schema_json` in its body; `openai_analyzer.py` computed it via
`quotecheck_result_schema_json()` only to pass it into that unused parameter.

Removed: the `schema_json` parameter, the `schema_str = quotecheck_result_schema_json()`
call, the `quotecheck_result_schema_json` import, and — after `git grep` confirmed
zero remaining callers — the `quotecheck_result_schema_json()` helper itself and
the now-unused `import json` in `schema_export.py`.

`git grep -n quotecheck_result_schema_json` after the change: no matches.

The only Structured Outputs path is unchanged:

```
QuoteCheckResult  ->  quotecheck_result_schema_obj()  ->  client.responses.create(... text={"format": {..., "schema": schema_obj}})
```

Static check output:

```
build_messages signature : (*, quote_text: 'str') -> 'List[Dict[str, str]]'
openai_analyzer still builds schema_obj from the Pydantic contract and passes it via text.format.schema: OK
schema_export.quotecheck_result_schema_json removed; quotecheck_result_schema_obj intact: OK
```

## 10. Example regeneration evidence

Method: `QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app` on `127.0.0.1:8011`, then
each unchanged `examples/*.txt` input replayed through `POST /analyze` via `curl`,
response validated with `QuoteCheckResult.model_validate(...)` and written with
`json.dump(..., indent=4)`. No OpenAI call. No manual edits to the JSON.

```
examples/sample_output.json
   model=quotecheck-demo-analyzer prompt_version=quotecheck_v0.4
   uncertainty_markers={'ambiguous_items_present': True, 'missing_quote_context': False, 'needs_professional_confirmation': True}
examples/outputs/vehicle_service.json
   model=quotecheck-demo-analyzer prompt_version=quotecheck_v0.4
   uncertainty_markers={'ambiguous_items_present': True, 'missing_quote_context': False, 'needs_professional_confirmation': True}
examples/outputs/ac_repair.json
   model=quotecheck-demo-analyzer prompt_version=quotecheck_v0.4
   uncertainty_markers={'ambiguous_items_present': True, 'missing_quote_context': False, 'needs_professional_confirmation': False}
examples/outputs/home_maintenance.json
   model=quotecheck-demo-analyzer prompt_version=quotecheck_v0.4
   uncertainty_markers={'ambiguous_items_present': True, 'missing_quote_context': True, 'needs_professional_confirmation': False}
examples/outputs/parts_labour_misc.json
   model=quotecheck-demo-analyzer prompt_version=quotecheck_v0.4
   uncertainty_markers={'ambiguous_items_present': True, 'missing_quote_context': True, 'needs_professional_confirmation': False}
examples/outputs/vague_missing_details.json
   model=quotecheck-demo-analyzer prompt_version=quotecheck_v0.4
   uncertainty_markers={'ambiguous_items_present': True, 'missing_quote_context': True, 'needs_professional_confirmation': False}
```

Representative diff (`examples/outputs/vehicle_service.json`) — only uncertainty
keys/values, `prompt_version`, stale `v0 prototype` wording, and per-run metadata
changed; line items unchanged:

```diff
-        "Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made."
+        "Price benchmarking is not implemented; no market price comparison is being made."
     "uncertainty_markers": {
         "ambiguous_items_present": true,
-        "missing_vehicle_context": true,
-        "needs_mechanic_confirmation": true
+        "missing_quote_context": false,
+        "needs_professional_confirmation": true
     },
-    "disclaimer": "QuoteCheck is a v0 prototype; results may be incomplete or wrong. Not safety advice; verify with a certified mechanic. ...",
+    "disclaimer": "QuoteCheck results may be incomplete or wrong. This analysis is informational and should not replace professional advice, ... — verify with a certified mechanic. ...",
-        "prompt_version": "quotecheck_v0.2",
+        "prompt_version": "quotecheck_v0.4",
```

`grep -RInE 'missing_vehicle_context|needs_mechanic_confirmation|v0 prototype' examples/`
→ no matches.

`grep -InE 'mechanic|vehicle' examples/outputs/{ac_repair,home_maintenance,parts_labour_misc,vague_missing_details}.json`
→ no matches (non-vehicle examples carry no vehicle/mechanic wording).

## 11. Acceptance-criteria table

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `UncertaintyMarkers` uses new names + descriptions; no old names in active source/examples/frontend; no aliases | PASS | §3; validation A (only historical `docs/CURRENT_STATE.md` lines + the new QC-1B block); validation B |
| 2 | Prompt instructs both new fields, domain-generic; price/fairness rule + rest of prompt preserved | PASS | §6; `git diff backend/core/prompt.py` (line 38 price rule untouched, line 39 generic-professional rule untouched) |
| 3 | Prompt-version decision recorded; bump follows scheme; all live refs updated | PASS | §6 |
| 4 | Demo computes both fields deterministically; no vehicle/mechanic uncertainty on non-vehicle quotes; vehicle still flags safety-sensitive; `missing_quote_context` evidence-based | PASS | §4; validation E |
| 5 | Failure logging mode-aware | PASS | §8 |
| 6 | Misleading "fallback" wording corrected; no auto-fallback added | PASS | §5; `git diff backend/core/stub_analyzer.py` docstring |
| 7 | Dead `schema_json` plumbing removed; Structured Outputs path unchanged | PASS | §9; validation G |
| 8 | Frontend updated only if it directly uses a renamed field | PASS (n/a) | `grep -niE 'uncertain\|mechanic\|vehicle\|professional\|missing_' frontend/src/App.jsx` → no matches; frontend not in diff |
| 9 | Six examples regenerated via real Demo path; all valid; `metadata.model` + `prompt_version` correct; new names; no `v0 prototype`; no non-vehicle leakage; not hand-edited | PASS | §10; validation F |
| 10 | `docs/CURRENT_STATE.md` `### Fixed in QC-1B` + `Last updated`; live refs corrected; historical blocks intact; no eval/deploy claims | PASS | §5; `git diff docs/CURRENT_STATE.md` |
| 11 | `git diff --stat` only in-scope files; nothing committed | PASS | §15, §16 |

## 12. Exact validation commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt        # setup

# A
git grep -nE 'missing_vehicle_context|needs_mechanic_confirmation' -- ':!docs/tickets/**' ':!docs/review/**'
# B
git grep -nE 'missing_quote_context|needs_professional_confirmation'
# C
.venv/bin/python -m compileall -q backend
.venv/bin/python -c "from backend.app import app; print('import ok')"
# D
.venv/bin/python -c "<strict-schema assertions — see §13>"
# E
QUOTECHECK_USE_OPENAI=0 .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8012 --log-level warning &
#   replay 5 example inputs through POST /analyze; assert schema_valid / model / markers
# F
.venv/bin/python -c "<load every examples/**/*.json through QuoteCheckResult.model_validate>"
grep -RInE 'missing_vehicle_context|needs_mechanic_confirmation|v0 prototype' examples/ || true
# G
.venv/bin/python -c "<inspect openai_analyzer + schema_export source; assert dead helper gone, schema_obj path intact>"
# provenance
.venv/bin/python -c "<TestClient forced failure, USE_OPENAI=0 then =1, inspect last JSONL model>"
# I
git diff --check ; git status --short ; git diff --stat
```

## 13. Exact results

**A — old contract names (excl tickets/reviews):**
```
docs/CURRENT_STATE.md:205:  `missing_vehicle_context` → `missing_quote_context` and
docs/CURRENT_STATE.md:206:  `needs_mechanic_confirmation` → `needs_professional_confirmation`
docs/CURRENT_STATE.md:221:  hardcodes `missing_vehicle_context=True` / `needs_mechanic_confirmation=True`.
docs/CURRENT_STATE.md:299:QC-1A). Known implementation issues (e.g. `missing_vehicle_context` /
docs/CURRENT_STATE.md:300:`needs_mechanic_confirmation` hardcoding in the Demo stub, no repair/retry, no eval
docs/CURRENT_STATE.md:342:  vehicle-only". `DEVELOPER_PROMPT` changes: (1) `missing_vehicle_context` is only
docs/CURRENT_STATE.md:357:  broad default for `missing_vehicle_context`. This ticket focuses on OpenAI
```
Interpretation: lines 205/206/221 are the **new** `### Fixed in QC-1B` block
(documenting the rename itself); lines 299/300 are the historical QC-1A block; lines
342/357 are the historical TASK-012 block. **No active source, example, or frontend
contract use of the old names.**

**B — new contract names:** present in `backend/core/schema.py` (×4),
`backend/core/prompt.py` (×2), `backend/core/stub_analyzer.py` (×6, incl. comments),
all six `examples/*.json` (×2 each), and `docs/CURRENT_STATE.md`. **None in
`frontend/`.**

**C — syntax + import:**
```
compileall backend: OK
import backend.app: ok
```

**D — strict schema export:**
```
additionalProperties: False
required            : ['ambiguous_items_present', 'missing_quote_context', 'needs_professional_confirmation']
properties          : ['ambiguous_items_present', 'missing_quote_context', 'needs_professional_confirmation']
every object schema strict (additionalProperties=false, required=all keys): OK
old uncertainty keys absent from exported schema: OK
```
(`missing_quote_context` / `needs_professional_confirmation` both carry a
`description` in the exported schema; `_make_nullable` still applied only to
`price`.)

**E — Demo-mode `/analyze` smoke (fresh server, 5 categories):**
```
vehicle-service        schema_valid=True  model=quotecheck-demo-analyzer  prompt=quotecheck_v0.4
                       missing_quote_context=False  needs_professional_confirmation=True   non-vehicle vehicle/mechanic leak=False
AC/HVAC                schema_valid=True  model=quotecheck-demo-analyzer  prompt=quotecheck_v0.4
                       missing_quote_context=False  needs_professional_confirmation=False  non-vehicle vehicle/mechanic leak=False
home/contractor        schema_valid=True  model=quotecheck-demo-analyzer  prompt=quotecheck_v0.4
                       missing_quote_context=True   needs_professional_confirmation=False  non-vehicle vehicle/mechanic leak=False
generic parts/labour   schema_valid=True  model=quotecheck-demo-analyzer  prompt=quotecheck_v0.4
                       missing_quote_context=True   needs_professional_confirmation=False  non-vehicle vehicle/mechanic leak=False
vague/missing-details  schema_valid=True  model=quotecheck-demo-analyzer  prompt=quotecheck_v0.4
                       missing_quote_context=True   needs_professional_confirmation=False  non-vehicle vehicle/mechanic leak=False
```

**F — saved examples load + string scan:**
```
PASS examples/outputs/ac_repair.json | model=quotecheck-demo-analyzer prompt=quotecheck_v0.4
PASS examples/outputs/home_maintenance.json | model=quotecheck-demo-analyzer prompt=quotecheck_v0.4
PASS examples/outputs/parts_labour_misc.json | model=quotecheck-demo-analyzer prompt=quotecheck_v0.4
PASS examples/outputs/vague_missing_details.json | model=quotecheck-demo-analyzer prompt=quotecheck_v0.4
PASS examples/outputs/vehicle_service.json | model=quotecheck-demo-analyzer prompt=quotecheck_v0.4
PASS examples/sample_output.json | model=quotecheck-demo-analyzer prompt=quotecheck_v0.4
6 examples PASS

(grep missing_vehicle_context|needs_mechanic_confirmation|v0 prototype in examples/) → (no matches in examples/)
```
**Example count: 6, all PASS.**

**G — OpenAI path static verification:** see §9. `git grep -n quotecheck_result_schema_json` → no matches.

**Provenance:** see §8 (both PASS).

**H — frontend:** `frontend/` is not in the diff; `frontend/src/App.jsx` never
referenced the uncertainty markers. `npm run lint` / `npm run build` not required
by this change.

**I — scope:** see §15, §16. `git diff --check` → clean.

## 14. Remaining limitations deliberately deferred

- `NormalizedCategory` still carries vehicle-era values
  (`safety_critical` / `wear_and_tear` / …) and vehicle-flavoured enum semantics.
  Out of scope per the ticket — a taxonomy change would invalidate more downstream
  assumptions than QC-1B should.
- `UncertaintyMarkers.ambiguous_items_present` is still a constant `True` in both
  the stub and the schema default. QC-1B changes only the two obviously
  domain-specific fields; making this one evidence-based is a later cleanup.
- Demo `missing_quote_context` relies on a fixed phrase list, not language
  understanding — it will miss missing-context signals phrased differently, exactly
  like the rest of the stub's keyword heuristics.
- No eval/regression harness, no retry/repair loop, no timeout/rate-limit policy,
  no deployment — all explicitly deferred to later hardening tickets.
- `.venv/` is present in the working tree as an untracked dir (not in
  `.gitignore`); it is not staged and `.gitignore` was not modified (out of scope).

## 15. `git status --short`

```
 M README.md
 M backend/app.py
 M backend/core/openai_analyzer.py
 M backend/core/prompt.py
 M backend/core/schema.py
 M backend/core/schema_export.py
 M backend/core/stub_analyzer.py
 M docs/CURRENT_STATE.md
 M examples/outputs/ac_repair.json
 M examples/outputs/home_maintenance.json
 M examples/outputs/parts_labour_misc.json
 M examples/outputs/vague_missing_details.json
 M examples/outputs/vehicle_service.json
 M examples/sample_output.json
?? .venv/
?? docs/tickets/QC-1B-domain-neutral-contract.md
?? docs/review/REVIEW_BUNDLE__QC-1B-domain-neutral-contract.md
```
(`.venv/` = local virtualenv for validation, not part of the change and not
committed.)

## 16. `git diff --stat`

```
 README.md                                   |  2 +-
 backend/app.py                              |  7 ++-
 backend/core/openai_analyzer.py             |  5 +-
 backend/core/prompt.py                      | 16 ++++--
 backend/core/schema.py                      | 24 +++++++--
 backend/core/schema_export.py               | 17 ++----
 backend/core/stub_analyzer.py               | 57 +++++++++++++++++++++++++++--
 docs/CURRENT_STATE.md                       | 83 +++++++++++++++++++++++++----
 examples/outputs/ac_repair.json             | 14 +++----
 examples/outputs/home_maintenance.json      | 14 +++----
 examples/outputs/parts_labour_misc.json     | 14 +++----
 examples/outputs/vague_missing_details.json | 14 +++----
 examples/outputs/vehicle_service.json       | 14 +++----
 examples/sample_output.json                 | 14 +++----
 14 files changed, 212 insertions(+), 83 deletions(-)
```
(plus the two new untracked docs in §15.)

## Definition of done

All acceptance criteria PASS with real command output above. `docs/CURRENT_STATE.md`
`Last updated` reflects QC-1B; new `### Fixed in QC-1B` block added; historical
blocks unmodified. No frontend, `run_logger.py`, `config.py`, dependency, or
deployment change. No historical ticket/review file modified. Nothing committed —
left for the user to review and commit.
