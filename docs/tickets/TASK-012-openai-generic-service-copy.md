# TASK-012 — OpenAI mode generic service-copy cleanup

## 1. Goal

Make OpenAI-mode output copy generic enough for service, repair, parts, and vendor
quotes without changing schema or product behavior.

## 2. Context

OpenAI mode works and returns schema-valid output, but testing with an AC repair
quote revealed leftover vehicle/mechanic bias in the generated output:
- `uncertainty_markers.missing_vehicle_context` was `true` for a non-vehicle AC
  quote, because `backend/core/prompt.py` only ever instructed the model to set it
  `true` and never told it when to use `false`.
- The disclaimer instruction hardcoded `"...verify with a certified mechanic."`
  regardless of the quote's domain.
- The prompt did not forbid the model from characterizing a price as high/low/
  fair/overpriced/underpriced, even though price benchmarking is not implemented.

This is a copy-only prompt fix: no schema change, no new fields.

## 3. Strict file scope

Allowed:
- `backend/core/prompt.py`
- `backend/core/stub_analyzer.py` only if needed for copy consistency
- `docs/CURRENT_STATE.md`
- `docs/tickets/TASK-012-openai-generic-service-copy.md`
- `docs/review/REVIEW_BUNDLE__TASK-012-openai-generic-service-copy.md`

Never touch: `frontend/`, `examples/outputs/`, `backend/.env`, `logs/`,
`package-lock.json`, secrets.

## 4. Out of scope

No schema changes, no frontend changes, no new fields, no price benchmarking, no
model/provider changes, no dependency changes, no OpenAI API key exposure, no
committed logs.

`backend/core/stub_analyzer.py` (Demo mode) was inspected and needed no copy
changes — its disclaimer/professional-selection wording was already generalized in
TASK-008/TASK-008A. It does hardcode `missing_vehicle_context=True` for every
Demo-mode response, but changing that is a logic change, not copy consistency, so
it stays out of this ticket's scope (recorded as an out-of-scope observation in the
review bundle).

## 5. Required changes

1. `backend/core/prompt.py` `SYSTEM_PROMPT`: state the generic scope (service,
   repair, parts, vendor quotes across any domain) explicitly, so the model does
   not default to a vehicle framing.
2. `DEVELOPER_PROMPT`: reword the `missing_vehicle_context` instruction so it is
   only set `true` when the quote is clearly vehicle-related **and** vehicle
   context is actually missing; every other domain must get `false`.
3. `DEVELOPER_PROMPT`: extend the no-price-benchmarking instruction to explicitly
   forbid describing a quote/charge as high, low, fair, cheap, expensive,
   overpriced, or underpriced without benchmarking data, and require phrasing
   pricing uncertainty as "needs clarification" / "verify the basis for this
   charge" instead.
4. `DEVELOPER_PROMPT`: replace the hardcoded "certified mechanic" disclaimer
   instruction with generic wording, naming a specific professional only when the
   quote is clearly vehicle-related.
5. Preserve schema validity and existing output structure. `PROMPT_VERSION` bumped
   `quotecheck_v0.2` → `quotecheck_v0.3` per the module's own versioning policy.

## 6. Acceptance criteria

- `grep -RInE 'v0 prototype|prototype|vehicle-only|quite high|overpriced|underpriced|fair price' backend/core`
  only matches instructional/negation copy in `prompt.py` (e.g. "not vehicle-only",
  "do not describe ... as ... overpriced"), not leftover bias.
- `grep -RIn "certified mechanic" backend/core/prompt.py` only matches the
  conditional instruction ("only name a specific professional ... when clearly
  vehicle-related"), not an unconditional disclaimer.
- OpenAI mode (`QUOTECHECK_USE_OPENAI=1`, real `gpt-4o-mini` call) against an AC
  repair quote returns: `schema_valid: true`, `metadata.model: gpt-4o-mini`,
  disclaimer with no "mechanic" wording, `missing_vehicle_context: false`, no
  high/low/fair/overpriced/underpriced price judgments in `overall_summary`, and
  the gas-top-up line item still flagged with `risk_level` yellow/red,
  `vague_or_confusing: true`, and evidence requested (i.e. still treated as
  risky/needing clarification, not waved through).
- No schema, frontend, or dependency changes.
- `docs/CURRENT_STATE.md` "Last updated" line and a new TASK-012 entry reflect
  this change.
- Not committed.

## 7. Commands to run

```bash
grep -RInE 'v0 prototype|prototype|vehicle-only|quite high|overpriced|underpriced|fair price' backend/core || true
grep -RIn "certified mechanic" backend/core/prompt.py || true
# Demo mode
QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/health
# OpenAI mode, manual /analyze call against an AC repair quote
QUOTECHECK_USE_OPENAI=1 uvicorn backend.app:app --host 0.0.0.0 --port 8000
curl -X POST http://localhost:8000/analyze -H "Content-Type: application/json" -d '{"quote_text": "..."}'
git status --short
git diff --stat
```

## 8. Definition of done

- Ticket approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (summarized
  validation results, not a raw committed API response).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-012.
- No secrets committed; not committed at all — left for the user to review and
  commit manually.
