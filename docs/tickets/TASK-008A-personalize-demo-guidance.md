# TASK-008A — Personalize demo-mode vendor questions and things-to-verify

## 1. Goal

Make the deterministic Demo-mode analyzer generate domain-aware `verification_questions`
("Questions to ask the vendor") and `things_to_verify` ("Things to verify before
approving") based on the matched quote domain and line-item types, instead of the
same near-generic advice repeated across every sample regardless of domain.

## 2. Context

TASK-008 (merged into `main` in commit `fe778ed` / merge `c4b1545`) broadened the
stub analyzer to recognize vehicle, AC/appliance, and home-maintenance/contractor
quotes, and made the top-level `overall_summary`/`disclaimer` text domain-generic
instead of always vehicle-flavored. However, `verification_questions` and
`things_to_verify` were left as two fixed 3-item static lists returned unchanged
regardless of which domain matched.

During manual UI verification of TASK-008's output, this was flagged as a
product-quality issue: the two bottom report cards ("Questions to ask the vendor" /
"Things to verify before approving") read as near-duplicate generic boilerplate
across every sample domain, making the demo feel template-driven rather than
personalized to the quote actually analyzed.

This ticket makes both lists domain-aware, generated deterministically from the same
keyword-match booleans already used to build line items (vehicle/AC/home-
maintenance/generic-charge), reusing TASK-008's existing keyword lists — no new
keyword detection, no LLM/web calls, no schema change.

Note on branch history: TASK-008's work was committed and merged into `main`
directly (outside of the ticket/review-bundle workflow's normal
branch-then-review-then-merge sequence) before this follow-up began. This ticket
starts a fresh branch off current `main` rather than reusing the old
`task/TASK-008-sample-cases-evals` branch, since that branch's content is already
merged.

## 3. Strict file scope

Allowed to update:
- `backend/core/stub_analyzer.py`
- `examples/outputs/*.json` (regenerated, real Demo-mode calls only)
- `examples/sample_output.json` (regenerated, real Demo-mode call only)
- `docs/CURRENT_STATE.md` (new "Fixed in TASK-008A" section + "Last updated" line)
- `docs/tickets/TASK-008A-personalize-demo-guidance.md` (this file)
- `docs/review/REVIEW_BUNDLE__TASK-008A-personalize-demo-guidance.md`

Never touch: `frontend/`, `backend/core/schema.py`, `backend/core/openai_analyzer.py`,
`README.md` (unless absolutely necessary — not needed here), `backend/.env`, `logs/`,
secrets of any kind.

## 4. Out of scope

No LLM calls. No web search. No price benchmarking or market evidence. No response
schema change. No new keyword domains beyond the four TASK-008 already established
(vehicle, AC/appliance, home-maintenance, generic-charge) plus the existing no-match
fallback. No frontend changes. No commits (left for manual review/commit).

## 5. Acceptance criteria

- `verification_questions` and `things_to_verify` are generated dynamically from the
  matched quote domain(s) and line-item types, not fixed static lists.
- Vehicle sample has vehicle-specific questions/verification (pad thickness, tread
  depth, OEM/aftermarket parts, second opinion for safety-critical work).
- AC/appliance sample has AC/appliance-specific questions/verification (diagnostic
  fault code, warranty, refrigerant type/quantity, leak location).
- Home-maintenance sample has contractor/home-scope-specific questions/verification
  (written scope of work, labor-hours/materials estimate, permits, license/insurance).
- Labour/misc sample asks for itemization and charge breakdown (fixed vs. time-based,
  overlap with other line items, negotiability).
- Vague/missing-details sample asks clarifying questions instead of pretending to
  know quote-specific details (itemized resend, underlying problem, urgency).
- The two bottom cards are no longer near-duplicates: no sentence appears verbatim in
  both `verification_questions` and `things_to_verify` for the same output, except
  where genuinely unavoidable.
- Generic fallback advice (plain clarifying questions with no domain-specific detail)
  is used only for the true no-match fallback case.
- Domain chunks combine additively when a quote matches more than one keyword block
  (e.g. vehicle + generic-charge), staying within the schema's bounds
  (`verification_questions`: 3–8 items; `things_to_verify`: 3+ items, no max).
- All 6 example outputs (`examples/sample_output.json` +
  `examples/outputs/{vehicle_service,ac_repair,home_maintenance,parts_labour_misc,vague_missing_details}.json`)
  are regenerated from real local Demo-mode `/analyze` calls (not hand-written) and
  validate against `QuoteCheckResult`.
- `metadata.model == "quotecheck-demo-analyzer"` on every regenerated output.
- No frontend files changed; no OpenAI calls made; no price-benchmarking or market
  evidence claims anywhere in the regenerated outputs.
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-008A; a "Fixed in
  TASK-008A" section documents this change without misattributing it as part of the
  already-merged TASK-008 changelog entry.
- Review bundle records exact commands and real output, no placeholders, and notes
  the manual-UI-verification finding that prompted this ticket plus the git-history
  anomaly that led to starting a fresh branch off `main`.

## 6. Commands to run

```bash
git status --short
git branch --show-current
QUOTECHECK_USE_OPENAI=0 conda run -n quotecheck uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1:8000/health

# Regenerate sample_output.json and all 5 examples/outputs/*.json via real /analyze calls
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"<file contents>"}' | python3 -m json.tool | tee <output file>

conda run -n quotecheck python3 -c "
import json, glob
from backend.core.schema import QuoteCheckResult
for f in sorted(glob.glob('examples/outputs/*.json')) + ['examples/sample_output.json']:
    d = json.load(open(f))
    QuoteCheckResult.model_validate(d)
    assert d['metadata']['model'] == 'quotecheck-demo-analyzer'
    print('OK', f)
"

grep -ilE 'brake|tyre|\bOEM\b' examples/outputs/ac_repair.json examples/outputs/home_maintenance.json examples/outputs/parts_labour_misc.json examples/outputs/vague_missing_details.json
grep -ilE 'market price|price benchmark' examples/outputs/*.json examples/sample_output.json
git diff --stat main
```

## 7. Definition of done

- Ticket and review bundle written within file scope.
- All acceptance criteria have concrete evidence in the review bundle (exact
  commands, exact output, no placeholders).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-008A; "Fixed in
  TASK-008" section (already on `main`) left untouched/accurately describing only
  what TASK-008 actually delivered.
- No secrets committed; no frontend/schema/OpenAI-analyzer files changed; work
  stays on `task/TASK-008A-personalize-demo-guidance`. Not committed — left for the
  user to review and commit manually.
