# TASK-008 — Sample cases and lightweight evals

## 1. Goal

Add 3–5 realistic quote examples spanning multiple domains (vehicle, appliance/AC
repair, home maintenance/contractor, a vague-charges parts quote, and a very vague
quote), each with a real Demo-mode `/analyze` output, plus a minimal deterministic
broadening of the stub analyzer so Demo mode produces domain-appropriate results for
each — not just vehicle-flavored boilerplate — so QuoteCheck's repo demonstrates it
works across the range of quotes SPEC.md targets, not one cherry-picked case.

## 2. Context

`examples/sample_quote.txt` / `examples/sample_output.json` (TASK-007) is the only
input/output pair in the repo today. The stub analyzer
(`backend/core/stub_analyzer.py`) currently only recognizes vehicle terms (`brake`,
`tyre`/`tire`) plus a generic-charge keyword list, and its `overall_summary`/
`things_to_verify`/`disclaimer` text is static and vehicle-flavored (mentions
"brakes/tyres", "OEM-specified") regardless of quote domain. Feeding it a non-vehicle
quote today produces a real but weak, generic, vehicle-flavored response.

This ticket adds a minimal, deterministic broadening: keyword-based detection for
AC/appliance-repair and home-maintenance/contractor quotes (same pattern as the
existing brake/tyre blocks), plus making the top-level summary/disclaimer/
things-to-verify text domain-generic by default, adding vehicle-specific phrasing only
when a vehicle item actually matched. The vague/missing-details fallback path (no
keyword match at all) is preserved unchanged — it is already domain-generic and is a
deliberate example of the uncertainty-handling path, not a gap to fix.

This is still keyword matching, not real language understanding — broadening the
taxonomy/parser itself remains target scope per SPEC.md, not delivered here. The
change is scoped to: recognize a few more domains, stop asserting vehicle-specific
language when no vehicle item matched.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-008-sample-cases-evals.md`
- `docs/review/REVIEW_BUNDLE__TASK-008-sample-cases-evals.md`
- `examples/` (new input files, new `examples/outputs/` directory, new
  `examples/README.md` index)
- `README.md` (only to add links to the new examples)
- `docs/CURRENT_STATE.md` (to note the example/eval pack and the stub broadening;
  "Last updated" line)
- `backend/core/stub_analyzer.py` — minimal, deterministic keyword-detection and
  domain-generic-summary changes only (see Context). Part of the normal scope for
  this ticket, not conditional on inspection.

Never touch: `frontend/` source, `backend/core/openai_analyzer.py`,
`backend/core/schema.py` (stop and ask first if a compatibility issue appears),
`backend/.env`, `logs/`, `package-lock.json`, any secrets.

## 4. Out of scope

No UI changes. No OpenAI-mode calls (Demo mode only, `QUOTECHECK_USE_OPENAI=0`, the
default). No price benchmarking or market evidence, real or fake. No web search. No
OCR/PDF/image parsing. No database/auth/session history. No fake metrics or hand-edited
JSON outputs — every output file must be a real captured `/analyze` response, generated
after the stub changes land. No production-readiness claims. No real NLP/LLM-based
parsing in the stub — keyword detection only, same pattern as existing brake/tyre
logic. No commits.

## 5. Acceptance criteria

- 3–5 realistic sample quote inputs added under `examples/`, spanning: vehicle
  service, AC/appliance repair, home maintenance/contractor, a parts quote with vague
  labour/misc/other charges, and a very vague/missing-details quote.
- Each has a generated Demo-mode output under `examples/outputs/`, produced by a real
  `POST /analyze` call (Demo mode) after the stub changes — not hand-written.
- At least 4 of the 5 sample outputs have domain-appropriate line-item
  `explanation`/`rationale_short` text (not generic vehicle boilerplate applied to a
  non-vehicle quote).
- At least 1 sample exercises the vague/missing-details fallback path (the stub's
  existing "Unclear item(s) - needs clarification" branch), demonstrating
  low-confidence/uncertainty handling.
- Each output file validates against `QuoteCheckResult`
  (`backend/core/schema.py`), not just generic JSON syntax.
- No output claims market pricing or price benchmarking anywhere (line items,
  summary, or disclaimer).
- `overall_summary`/`disclaimer`/`things_to_verify` text does not assert
  vehicle-specific language (e.g. "brakes/tyres", "OEM-specified") for non-vehicle
  samples.
- `examples/README.md` lists all examples, briefly explains each, and states plainly:
  Demo mode is a deterministic keyword-based stub (not an LLM), these are real
  Demo-mode outputs, price benchmarking is not implemented, and these are sample
  reports rather than accuracy claims.
- Main `README.md` links to the new example pack if useful, no other prose changes.
- `docs/CURRENT_STATE.md` updated to mention the example/eval pack and the stub
  broadening, with its "Last updated" line reflecting TASK-008.
- `backend/core/schema.py` is unchanged unless validation surfaces a real
  compatibility issue, in which case implementation stops to ask first.
- No secrets committed (verified by grep).
- Review bundle records exact commands run and their real output, no placeholders.

## 6. Commands to run

```bash
git status --short
python -c "from backend.app import app; print(app.title)"
QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1:8000/health

# For each sample input file, after stub_analyzer.py changes land:
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"quote_text": open(sys.argv[1]).read()}))' examples/quote_<name>.txt)" \
  | python3 -m json.tool | tee examples/outputs/<name>.json

# Schema validation (not just JSON syntax) for every output file:
python3 -c "
import json, glob
from backend.core.schema import QuoteCheckResult
for f in sorted(glob.glob('examples/outputs/*.json')):
    QuoteCheckResult.model_validate(json.load(open(f)))
    print('OK', f)
"

grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' examples README.md docs/CURRENT_STATE.md
git diff --stat main
```

## 7. Definition of done

- Ticket approved, plan approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (exact commands,
  exact output, no placeholders).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-008.
- No secrets committed; `backend/core/schema.py` unchanged; work stays on
  `task/TASK-008-sample-cases-evals`. Not committed — left for the user to review and
  commit manually.
