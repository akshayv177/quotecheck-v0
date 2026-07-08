# Review Bundle — TASK-002 — Quote-understanding contract baseline

Branch: `task/TASK-002-quote-understanding-contract`

## Files changed

```
 M backend/core/prompt.py
 M backend/core/schema.py
 M backend/core/stub_analyzer.py
 M docs/CURRENT_STATE.md
?? docs/tickets/TASK-002-quote-understanding-contract.md
?? docs/review/REVIEW_BUNDLE__TASK-002-quote-understanding-contract.md
```

Stat:

```
 backend/core/prompt.py        | 11 +++++--
 backend/core/schema.py        | 42 ++++++++++++++++++++++++---
 backend/core/stub_analyzer.py | 67 +++++++++++++++++++++++++++++++++++++++++--
 docs/CURRENT_STATE.md         | 49 ++++++++++++++++++++++++++++---
 4 files changed, 155 insertions(+), 14 deletions(-)
```

No frontend files, README.md, package-lock.json, backend/.env, or logs/ were touched.
`backend/app.py` and `backend/core/openai_analyzer.py` were not touched — validation
showed both remain compatible with the additive schema change (see below), so no
change was genuinely necessary. `backend/core/schema_export.py` was not touched —
its generic normalization logic already forces every `LineItem` property into
`required` regardless of Python-side defaults (verified below), so it needed no
special-casing for the two new fields.

## Design decisions (confirmed with user before implementation)

1. Schema: add exactly two new `LineItem` fields, both additive with safe Python-side
   defaults for backward compatibility (`explanation: str = ""`,
   `vague_or_confusing: bool = False`) — the default is for object-construction
   compatibility only; analyzers (stub + prompt) are required to always populate a
   non-empty `explanation` for new output. No other schema fields renamed or
   reshaped, to keep `/analyze` compatible with the existing frontend.
2. Stub: add one independent, conservative keyword catch-all for generic/un-itemized
   charges (misc, labour/labor, service charge, gas top-up, consumables, other/
   unitemized charges) grouped into a single "Other/unspecified charges" line item
   with `vague_or_confusing=true`, `risk_level=yellow` (no severity detection),
   without touching the existing brake/tyre matching logic.

## Acceptance criteria — evidence

- **Backend response contract clearly supports quote understanding, not only
  audit/risk.** `LineItem.explanation` (backend/core/schema.py) is a dedicated
  plain-English field, separate from the risk-focused `rationale_short`; system/
  developer prompts (backend/core/prompt.py) now state "Quote understanding comes
  first" and require populating `explanation` before risk judgment.
- **Line items include or clearly expose plain-English explanations.** Confirmed via
  live `/analyze` call below — every line item has a non-empty `explanation` distinct
  from `rationale_short`.
- **Missing information and vague/confusing charges are represented clearly.**
  `LineItem.vague_or_confusing` (explicit boolean) plus top-level `things_to_verify`
  (docstring clarified: "missing information / gaps the quote does not state").
  Confirmed in the sample response: the "Other/unspecified charges" item has
  `vague_or_confusing: true`.
- **Vendor questions are represented clearly.** `verification_questions` docstring
  clarified: "concrete, vendor-facing questions the user can send back to the vendor
  before approving." Field unchanged in shape/name (frontend compatibility).
- **Red flags/risk levels remain represented clearly.** `risk_level`,
  `recommended_action`, `rationale_short` unchanged.
- **Uncertainty markers remain explicit.** `UncertaintyMarkers` unchanged; sample
  response shows all three markers still populated.
- **Stub mode returns a realistic explanation-first report for at least one sample
  quote.** See the full `/analyze` response below for the ticket's sample quote: 3
  line items (brake=red, tyre=yellow, other-charges=yellow/vague) instead of the
  previous 2, with Labour/Misc/AC gas top-up now surfaced instead of silently
  dropped.
- **OpenAI prompt instructs the model to produce explanation-first, uncertainty-aware,
  schema-valid output.** See updated `SYSTEM_PROMPT`/`DEVELOPER_PROMPT` in
  backend/core/prompt.py; `PROMPT_VERSION` bumped to `quotecheck_v0.2` since output
  semantics changed.
- **Existing `/analyze` endpoint remains compatible and schema-valid.** FastAPI's
  `response_model=QuoteCheckResult` on `POST /analyze` (backend/app.py, unchanged)
  means a 200 response is itself proof of schema validity; confirmed below. All
  fields the frontend reads (`name_raw`, `normalized_category`, `risk_level`,
  `recommended_action`, `rationale_short`, `overall_summary`,
  `verification_questions`, `things_to_verify`, `disclaimer`) are unchanged in name
  and meaning.
- **No price benchmarking or market evidence is claimed as implemented.** Stub
  `overall_summary` and `disclaimer` now explicitly state price benchmarking is not
  implemented; `DEVELOPER_PROMPT` explicitly forbids the model from claiming
  market-price comparison.
- **`docs/CURRENT_STATE.md` is updated** with the new contract state (Capabilities)
  and remaining gaps (Gaps + "Fixed in TASK-002"), "Last updated" line bumped to
  `2026-07-08 (TASK-002)`.
- **No secrets committed.** Grep below found no matches.
- **No frontend files changed.** Confirmed via `git status --short` above.

## Commands run and exact output

### 1. Git status

```
$ git status --short
 M backend/core/prompt.py
 M backend/core/schema.py
 M backend/core/stub_analyzer.py
 M docs/CURRENT_STATE.md
?? docs/tickets/TASK-002-quote-understanding-contract.md
?? docs/review/REVIEW_BUNDLE__TASK-002-quote-understanding-contract.md
```

### 2. App import (run in the pre-existing `quotecheck` conda env, Python 3.11 — no
`python` binary on PATH in this shell, only `python3`; matches the conda env noted in
`docs/CURRENT_STATE.md`)

```
$ python -c "from backend.app import app; print(app.title)"
QuoteCheck API
```

### 3. Schema keys

```
$ python -c "from backend.core.schema import QuoteCheckResult; print(QuoteCheckResult.model_json_schema().keys())"
dict_keys(['$defs', 'description', 'properties', 'required', 'title', 'type'])
```

### 3b. New fields present and correctly forced-required in the OpenAI-strict schema
export (extra check, not in the original command list, run to validate that
`schema_export.py` needed no changes):

```
$ python -c "
from backend.core.schema_export import quotecheck_result_schema_obj
import json
schema = quotecheck_result_schema_obj()
li = schema['$defs']['LineItem']
print('properties:', list(li['properties'].keys()))
print('required:', li['required'])
"
properties: ['name_raw', 'normalized_category', 'explanation', 'vague_or_confusing', 'recommended_action', 'risk_level', 'confidence', 'rationale_short', 'price', 'evidence_needed']
required: ['name_raw', 'normalized_category', 'explanation', 'vague_or_confusing', 'recommended_action', 'risk_level', 'confidence', 'rationale_short', 'price', 'evidence_needed']
```

### 4-5. Server + health check

```
$ uvicorn backend.app:app --host 127.0.0.1 --port 8000   (background)
$ curl http://127.0.0.1:8000/health
{"status":"ok"}
```

### 6. Sample quote analysis

```
$ curl -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" -d '{"quote_text":"Brake pad replacement ₹8,500. Labour ₹2,500. Misc charges ₹1,200. AC gas top-up ₹3,000. Tyre rotation included but no tyre condition report attached."}'
```

Response (200 OK, pretty-printed):

```json
{
    "line_items": [
        {
            "name_raw": "Brake service/ pads (from quote)",
            "normalized_category": "safety_critical",
            "explanation": "Brake pads are the friction material that presses on the rotor to slow the vehicle. A shop typically recommends replacement when pad thickness drops below a safe threshold or the rotor shows wear.",
            "vague_or_confusing": false,
            "recommended_action": "needs_inspection",
            "risk_level": "red",
            "confidence": 0.7,
            "rationale_short": "Braking components are safety-critical. Ask for pad thickness and rotor condition evidence.",
            "price": null,
            "evidence_needed": [
                "Pad thickness measurement (mm)",
                "Rotor condition photo",
                "Reason for replacement"
            ]
        },
        {
            "name_raw": "Tyre replacement (from quote)",
            "normalized_category": "safety_critical",
            "explanation": "Tyres are the vehicle's only contact with the road, so tread depth and condition affect braking, handling, and grip. A shop recommends replacement or rotation to keep wear even and maintain safe tread depth.",
            "vague_or_confusing": false,
            "recommended_action": "ask_for_evidence",
            "risk_level": "yellow",
            "confidence": 0.65,
            "rationale_short": "Tyres affect braking and handling. Ask for tread depth and sidewall condition details.",
            "price": {"amount": 0.0, "currency": "INR"},
            "evidence_needed": [
                "Tread depth (mm)",
                "Uneven wear explanation",
                "Sidewall damage photo (if any)"
            ]
        },
        {
            "name_raw": "Other/unspecified charges (from quote)",
            "normalized_category": "unknown_needs_clarification",
            "explanation": "The quote mentions one or more generically named or un-itemized charges (e.g. misc, labour, service charge, gas top-up). This stub cannot know what they specifically cover without an itemized breakdown from the vendor.",
            "vague_or_confusing": true,
            "recommended_action": "ask_for_evidence",
            "risk_level": "yellow",
            "confidence": 0.4,
            "rationale_short": "Generic or bundled charges are unclear without an itemized breakdown; ask the vendor to itemize them.",
            "price": null,
            "evidence_needed": [
                "Itemized breakdown of what this charge covers",
                "Confirm whether this is a fixed fee or time-based labour charge"
            ]
        }
    ],
    "overall_summary": [
        "This report explains each line item in plain language, flags risk level, and lists questions to ask the vendor before approving.",
        "Safety-critical items (like brakes/tyres) should be verified with evidence before approval.",
        "Any generically named or bundled charges are marked as needing clarification; ask the vendor for an itemized breakdown.",
        "Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made."
    ],
    "verification_questions": [
        "Can you share photos/measurements that justify each recommended item?",
        "Which items are safety-critical vs optional preventive maintenance?",
        "Confirm whether the recommendation is OEM-specified or shop-suggested."
    ],
    "things_to_verify": [
        "Request an itemized parts + labour breakdown for each line item.",
        "Ask for measurements (pad thickness, tread depth) where applicable.",
        "Confirm whether the recommendation is OEM-specified or shop-suggested."
    ],
    "uncertainty_markers": {
        "ambiguous_items_present": true,
        "missing_vehicle_context": true,
        "needs_mechanic_confirmation": true
    },
    "refusals": [],
    "disclaimer": "QuoteCheck is a v0 prototype; results may be incomplete or wrong. Not safety advice; verify with a certified mechanic. QuoteCheck explains quotes and suggests questions; it does not verify vendor claims, guarantee fair pricing, or perform price benchmarking.",
    "metadata": {
        "prompt_version": "quotecheck_v0.2",
        "model": "gpt-4o-mini",
        "created_at": "2026-07-08T08:59:58.689840Z",
        "request_id": "bd35dcf6-9e57-462f-afdb-2f0b1760e469",
        "latency_ms": 0,
        "schema_valid": true
    }
}
```

Corresponding JSONL log record (`logs/app_runs.jsonl`, last line):

```json
{
    "event": "quotecheck_analyze",
    "created_at": "2026-07-08T08:59:58.689890Z",
    "request_id": "bd35dcf6-9e57-462f-afdb-2f0b1760e469",
    "prompt_version": "quotecheck_v0.2",
    "model": "gpt-4o-mini",
    "latency_ms": 0,
    "schema_valid": true,
    "num_items": 3,
    "risk_counts": {"red": 1, "yellow": 2, "green": 0},
    "uncertainty": {
        "ambiguous_items_present": true,
        "missing_vehicle_context": true,
        "needs_mechanic_confirmation": true
    },
    "error": null
}
```

Server was stopped after this test (`pkill -f "uvicorn backend.app:app"`).

### 7. Secrets grep

```
$ grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' backend/core/schema.py backend/core/prompt.py backend/core/stub_analyzer.py docs/CURRENT_STATE.md
(no output — no matches; grep exit code 1)
```

## Out-of-scope findings (not fixed, noted per CLAUDE.md rule to stay in scope)

- The generic-charge catch-all is a fixed keyword list, not real line-item
  extraction (still keyword matching, consistent with existing stub design). A quote
  with vague charges that don't match one of the listed terms still falls through to
  the single generic "needs clarification" fallback item. Logged in
  `docs/CURRENT_STATE.md` Gaps.
- Missing information is still represented at the top level (`things_to_verify`,
  `missing_vehicle_context`) rather than per line item; adding a per-item
  `missing_info` field was considered and deliberately left out to keep the schema
  change minimal, per the ticket's "prefer minimal change over schema churn"
  instruction.
- OpenAI mode (`backend/core/openai_analyzer.py`) was not exercised end-to-end in
  this environment (no `OPENAI_API_KEY` configured / not requested); validation
  relied on stub-mode `/analyze` plus static schema introspection
  (`quotecheck_result_schema_obj()`), which confirms the new fields are correctly
  shaped for OpenAI's strict JSON Schema mode but does not confirm actual model
  behavior against the new prompt instructions.

## Not committed

Per CLAUDE.md and the ticket ("No commits"), no `git add`/`git commit` was run. All
changes are currently unstaged/untracked working-tree edits on
`task/TASK-002-quote-understanding-contract`.
