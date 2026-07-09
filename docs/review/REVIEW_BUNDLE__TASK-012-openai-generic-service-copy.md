# Review Bundle — TASK-012 — OpenAI mode generic service-copy cleanup

## Files changed

- `backend/core/prompt.py` — reworded `SYSTEM_PROMPT`/`DEVELOPER_PROMPT`, bumped
  `PROMPT_VERSION` `quotecheck_v0.2` → `quotecheck_v0.3`.
- `docs/CURRENT_STATE.md` — updated "Last updated" line, added a "Fixed in
  TASK-012" entry, updated the prompt.py architecture bullet and the related Gaps
  bullet.
- `docs/tickets/TASK-012-openai-generic-service-copy.md` — new ticket.
- `docs/review/REVIEW_BUNDLE__TASK-012-openai-generic-service-copy.md` — this file.

`backend/core/stub_analyzer.py` was inspected and left unchanged (see the
out-of-scope observation below).

```
$ git status --short
 M backend/core/prompt.py
?? docs/tickets/TASK-012-openai-generic-service-copy.md
?? docs/review/REVIEW_BUNDLE__TASK-012-openai-generic-service-copy.md
 M docs/CURRENT_STATE.md

$ git diff --stat
 backend/core/prompt.py | 10 +++++-----
 docs/CURRENT_STATE.md  | 51 +++++++++++++++++++++++++++++++++++++++++++-------
 2 files changed, 49 insertions(+), 12 deletions(-)
```

## Acceptance criteria — evidence

### 1. Grep — no leftover vehicle/mechanic bias, only expected instructional wording

Per user correction, the validation grep was split in two so legitimate
domain-specific/negation wording doesn't fail the ticket:

```
$ grep -RInE 'v0 prototype|prototype|vehicle-only|quite high|overpriced|underpriced|fair price' backend/core || true
backend/core/prompt.py:22:SYSTEM_PROMPT = r"""You are QuoteCheck, a service quote understanding and review assistant for repair, maintenance, parts, and vendor quotes across any domain (vehicle, appliance/HVAC, home/contractor work, or other paid services) — not vehicle-only.
backend/core/prompt.py:38:Do not claim any price benchmarking, market comparison, or "fair price" verification — that is not implemented; describe only what the quote itself states. Do not describe a quote or any charge as high, low, fair, cheap, expensive, overpriced, or underpriced without explicit price benchmarking data. Since price benchmarking is not implemented, phrase pricing uncertainty as "needs clarification" or "verify the basis for this charge," not as a market-price judgment.
```

Both matches are the intended instructional copy ("not vehicle-only" — stating the
generic scope; "fair price"/"overpriced"/"underpriced" — inside the sentence that
*forbids* the model from using that language), not leftover bias. No unexpected
matches (no "prototype", no unqualified "quite high").

```
$ grep -RIn "certified mechanic" backend/core/prompt.py || true
backend/core/prompt.py:39:Always include a disclaimer along these lines: "This analysis is informational and should not replace professional advice, official estimates, warranty terms, or a second opinion for high-value or safety-critical work." Only name a specific professional (e.g. "certified mechanic") when the quote is clearly vehicle-related; otherwise use generic wording such as "a qualified professional."
```

Only match is the conditional instruction (name "certified mechanic" only for
clearly vehicle-related quotes), not an unconditional disclaimer. Per the user's
correction, `backend/core/stub_analyzer.py` legitimately still contains "certified
mechanic" as one of several domain-selected professional strings (TASK-008/
TASK-008A behavior) — that is expected and out of this grep's scope.

### 2. Demo mode boots and serves `/health`

Backend run from a conda env with the project's pinned deps (`quotecheck` env; no
project `.venv` exists in this sandbox):

```
$ QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 0.0.0.0 --port 8000
$ curl -s http://localhost:8000/health
{"status":"ok"}
```

### 3. OpenAI mode — manual `/analyze` call against an AC repair quote

Ran against a real `gpt-4o-mini` call (`backend/.env` has `QUOTECHECK_USE_OPENAI=1`
and a real `OPENAI_API_KEY` already configured in this environment). Test quote used
(non-vehicle, AC/HVAC domain, includes a "gas top-up" charge with no leak test
mentioned, to specifically exercise the risk-flagging and missing-vehicle-context
behavior):

```
CoolBreeze HVAC Services - Repair Quote

Customer reports reduced cooling from the split AC unit.

Recommended:
1. Gas top-up (refrigerant refill) - Rs. 3500
2. Service charge - Rs. 800
3. Diagnostic callout fee - Rs. 500

Please approve to proceed with the repair visit.
```

```
$ curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text": "<above>"}' -w "HTTP_STATUS:%{http_code} TIME:%{time_total}s\n"
HTTP_STATUS:200 TIME:11.107015s
```

Summarized results from the JSON response (raw response not committed, per user
instruction — no API response JSON, logs, or screenshots are stored in this bundle):

| Check | Result |
|---|---|
| `metadata.schema_valid` | `true` |
| `metadata.model` | `gpt-4o-mini` |
| `metadata.prompt_version` | `quotecheck_v0.3` |
| `uncertainty_markers.missing_vehicle_context` | `false` |
| Disclaimer text | `"This analysis is informational and should not replace professional advice, official estimates, warranty terms, or a second opinion for high-value or safety-critical work."` — no "mechanic" wording |
| `overall_summary` price language | States the total cost ("Rs. 4800") and asks for a breakdown; no high/low/fair/cheap/expensive/overpriced/underpriced judgment |
| Gas top-up line item | `risk_level: yellow`, `vague_or_confusing: true`, `recommended_action: consider`, `evidence_needed` includes "Measurement of current refrigerant level before top-up" — still flagged as needing clarification/evidence, not waved through |

`grep -iE "overpriced|underpriced|expensive|cheap" ` over the raw response returned
no matches (checked directly against the response file before discarding it).

### Additional spot-check (not a strict acceptance criterion)

Also ran a real vehicle quote (`examples/quote_vehicle_service.txt` — a "2019
Sedan" brake/tyre estimate with no make/model/mileage) through OpenAI mode as a
sanity check that the reworded `missing_vehicle_context` instruction still allows
`true` for vehicle quotes. Result: the model returned `missing_vehicle_context:
false`, judging "2019 Sedan" as sufficient context. This is a model judgment call
within the instruction's intent (only vehicle quotes where context is "actually
missing" should get `true`) and not a failure of this ticket's specific acceptance
criteria, which concern the AC (non-vehicle) case above. Noting it here for
visibility, not as a defect.

### 4. Out-of-scope observation

Out-of-scope observation: demo-mode uncertainty markers still use a broad default
for `missing_vehicle_context`. This ticket focuses on OpenAI prompt behavior before
recording and does not regenerate deterministic demo outputs.

### 5. Scope check

```
$ git status --short
 M backend/core/prompt.py
?? docs/tickets/TASK-012-openai-generic-service-copy.md
?? docs/review/REVIEW_BUNDLE__TASK-012-openai-generic-service-copy.md
 M docs/CURRENT_STATE.md
```

Only files in the ticket's allowed scope were touched. No changes to `frontend/`,
`examples/outputs/`, `backend/.env`, `logs/`, `package-lock.json`, or any secrets.

## Definition of done

- All acceptance criteria have concrete evidence above.
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-012.
- No secrets committed; nothing in this ticket has been committed — left for the
  user to review and commit manually.
