# Review Bundle — TASK-008 — Sample cases and lightweight evals

Ticket: [`docs/tickets/TASK-008-sample-cases-evals.md`](../tickets/TASK-008-sample-cases-evals.md)

## Files changed

```
$ git status --short
 M README.md
 M backend/core/stub_analyzer.py
 M docs/CURRENT_STATE.md
 M examples/sample_output.json
?? docs/review/REVIEW_BUNDLE__TASK-008-sample-cases-evals.md
?? docs/tickets/TASK-008-sample-cases-evals.md
?? examples/README.md
?? examples/outputs/
?? examples/quote_ac_repair.txt
?? examples/quote_home_maintenance.txt
?? examples/quote_parts_labour_misc.txt
?? examples/quote_vague_missing_details.txt
?? examples/quote_vehicle_service.txt

$ git diff --stat main
 README.md                     |  16 +++++
 backend/core/stub_analyzer.py | 144 ++++++++++++++++++++++++++++++++++--------
 docs/CURRENT_STATE.md         |  84 ++++++++++++++++++++----
 examples/sample_output.json   |  14 ++--
 4 files changed, 212 insertions(+), 46 deletions(-)
```

Only files inside the ticket's file scope were touched: `README.md`,
`backend/core/stub_analyzer.py`, `docs/CURRENT_STATE.md`, `examples/sample_output.json`
(regenerated as a cleanup, see item 10 below), plus new files under `docs/tickets/`,
`docs/review/`, and `examples/`. No `frontend/` file,
`backend/core/openai_analyzer.py`, `backend/core/schema.py`, `backend/.env`,
`logs/*.jsonl` (git-tracked), or `package-lock.json` appears in the diff or
untracked list.

## Acceptance criteria — evidence

**1. 3–5 realistic sample quote inputs added under `examples/`, spanning vehicle,
AC/appliance, home maintenance, vague-charges parts, and a very vague quote.**

```
$ ls examples/quote_*.txt
examples/quote_ac_repair.txt
examples/quote_home_maintenance.txt
examples/quote_parts_labour_misc.txt
examples/quote_vague_missing_details.txt
examples/quote_vehicle_service.txt
```

5 files, one per required domain (contents in the repo — see file scope above).

**2. Each has a generated Demo-mode output under `examples/outputs/`, produced by a
real `POST /analyze` call, not hand-written.**

Backend started in Demo mode and health-checked:

```
$ python -c "from backend.app import app; print(app.title)"
/bin/bash: line 1: python: command not found
$ conda run -n quotecheck python -c "from backend.app import app; print(app.title)"
QuoteCheck API

$ QUOTECHECK_USE_OPENAI=0 conda run -n quotecheck uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
$ curl -s http://127.0.0.1:8000/health
{"status":"ok"}
```

(Note: the repo has no `python` on `PATH`, only `python3` and the `quotecheck` conda
env — same environment TASK-007 used. `python3` alone lacks the project's
dependencies (`ModuleNotFoundError: No module named 'fastapi'`); all backend
commands below use `conda run -n quotecheck` or bare `python3` for stdlib-only
scripts, matching the README's documented setup.)

Each sample posted to the real endpoint and saved:

```
$ mkdir -p examples/outputs
$ for name in vehicle_service:quote_vehicle_service ac_repair:quote_ac_repair \
    home_maintenance:quote_home_maintenance parts_labour_misc:quote_parts_labour_misc \
    vague_missing_details:quote_vague_missing_details; do
    out="${name%%:*}"; infile="examples/${name##*:}.txt"
    curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
      -d "$(python3 -c 'import json,sys;print(json.dumps({"quote_text": open(sys.argv[1]).read()}))' "$infile")" \
      | python3 -m json.tool | tee "examples/outputs/${out}.json" > /dev/null
  done

$ ls -la examples/outputs/
ac_repair.json  home_maintenance.json  parts_labour_misc.json
vague_missing_details.json  vehicle_service.json
```

Corresponding `logs/app_runs.jsonl` entries (proves the requests actually hit the
live server, in order vehicle_service → ac_repair → home_maintenance →
parts_labour_misc → vague_missing_details):

```
$ tail -n 6 logs/app_runs.jsonl
{"event": "quotecheck_analyze", ..., "request_id": "c1a631de-...", ...}   # (pre-existing TASK-007 entry)
{"event": "quotecheck_analyze", "created_at": "2026-07-08T16:00:13.140389Z", "request_id": "d81f1bae-2e14-4065-8645-58da013b060a", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 3, "risk_counts": {"red": 1, "yellow": 2, "green": 0}, "error": null}
{"event": "quotecheck_analyze", "created_at": "2026-07-08T16:00:13.203099Z", "request_id": "9f87e3b4-5445-470a-904c-5abd6bd41ec0", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 1, "green": 0}, "error": null}
{"event": "quotecheck_analyze", "created_at": "2026-07-08T16:00:13.258192Z", "request_id": "a88443f6-5b4b-47d0-b68b-f266f9d431f5", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 0, "green": 1}, "error": null}
{"event": "quotecheck_analyze", "created_at": "2026-07-08T16:00:13.312711Z", "request_id": "0dbce57d-a369-42a8-a2f8-2ba833ce8674", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 1, "green": 0}, "error": null}
{"event": "quotecheck_analyze", "created_at": "2026-07-08T16:00:13.370812Z", "request_id": "eee7d0d7-fb48-4390-8756-f5100ac16a01", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 1, "green": 0}, "error": null}
```

`num_items`/`risk_counts` per entry match the captured output files exactly (see
item 3 below).

**3. At least 4 of 5 outputs have domain-appropriate line-item explanations; at
least 1 exercises the vague/missing-details fallback.**

```
$ for f in examples/outputs/*.json; do
    python3 -c "
import json
d = json.load(open('$f'))
print('$f', [(li['name_raw'], li['normalized_category'], li['risk_level'], li['vague_or_confusing']) for li in d['line_items']])
"
  done
examples/outputs/ac_repair.json [('AC/appliance repair (from quote)', 'wear_and_tear', 'yellow', False)]
examples/outputs/home_maintenance.json [('Home maintenance/contractor work (from quote)', 'preventive_maintenance', 'green', False)]
examples/outputs/parts_labour_misc.json [('Other/unspecified charges (from quote)', 'unknown_needs_clarification', 'yellow', True)]
examples/outputs/vague_missing_details.json [('Unclear item(s) - needs clarification', 'unknown_needs_clarification', 'yellow', True)]
examples/outputs/vehicle_service.json [('Brake service/ pads (from quote)', 'safety_critical', 'red', False), ('Tyre replacement (from quote)', 'safety_critical', 'yellow', False), ('Other/unspecified charges (from quote)', 'unknown_needs_clarification', 'yellow', True)]
```

- `vehicle_service`, `ac_repair`, `home_maintenance` each hit a **new, domain-specific
  keyword block** added in this ticket, with matching category/explanation/evidence
  (brake+tyre / AC+appliance / plumbing+electrical+handyman respectively) — 3 of 5.
- `parts_labour_misc` deliberately hits only the (pre-existing) generic vague-charge
  catch-all — its explanation correctly describes vague/bundled charges, which is
  exactly what that input is designed to test — 4th of 5.
- `vague_missing_details` deliberately matches no keyword list at all and falls
  through to the stub's low-confidence "needs clarification" fallback
  (`confidence: 0.35`, `recommended_action: unknown`) — the required fallback/
  uncertainty-handling example.

4-of-5 domain-appropriate bar is met (vehicle/AC/home/parts-vague), with the 5th
(`vague_missing_details`) being the intentional uncertainty-fallback case required
separately by this same criterion.

**4. Each output file validates against `QuoteCheckResult`, not just JSON syntax.**

```
$ conda run -n quotecheck python3 -c "
import json, glob
from backend.core.schema import QuoteCheckResult
for f in sorted(glob.glob('examples/outputs/*.json')):
    QuoteCheckResult.model_validate(json.load(open(f)))
    print('OK', f)
"
OK examples/outputs/ac_repair.json
OK examples/outputs/home_maintenance.json
OK examples/outputs/parts_labour_misc.json
OK examples/outputs/vague_missing_details.json
OK examples/outputs/vehicle_service.json
```

**5. No output claims market pricing or price benchmarking.**

```
$ grep -ilE 'market price|price benchmark|price comparison' examples/outputs/*.json
examples/outputs/ac_repair.json
examples/outputs/home_maintenance.json
examples/outputs/parts_labour_misc.json
examples/outputs/vague_missing_details.json
examples/outputs/vehicle_service.json

$ grep -oE '.{0,60}(market price|price benchmark).{0,60}' examples/outputs/*.json
...:"...Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made."
...:"...guarantee fair pricing, or perform price benchmarking.",
(same two lines, once per file)
```

Every match is the disclaimer/summary explicitly stating price benchmarking is
**not** implemented — never a claim of one.

**6. `overall_summary`/`disclaimer`/`things_to_verify` no longer assert
vehicle-specific language for non-vehicle samples.**

```
$ grep -ilE 'brake|tyre|oem' examples/outputs/ac_repair.json examples/outputs/home_maintenance.json \
    examples/outputs/parts_labour_misc.json examples/outputs/vague_missing_details.json
(no output, grep exit 1 — no matches)
```

Disclaimer wording per file confirms domain-appropriate "verifying professional"
substitution:

```
ac_repair.json:            ...verify with a certified technician...
home_maintenance.json:     ...verify with a licensed contractor...
parts_labour_misc.json:    ...verify with a qualified professional...
vague_missing_details.json:...verify with a qualified professional...
vehicle_service.json:      ...verify with a certified mechanic...
```

`vehicle_service.json`'s `overall_summary` has 4 entries (base 3 + the
vehicle-specific safety line); all others have 3 — both within the schema's
`min_length=3, max_length=5` bound:

```
$ for f in examples/outputs/*.json; do python3 -c "import json;print('$f', len(json.load(open('$f'))['overall_summary']))"; done
examples/outputs/ac_repair.json 3
examples/outputs/home_maintenance.json 3
examples/outputs/parts_labour_misc.json 3
examples/outputs/vague_missing_details.json 3
examples/outputs/vehicle_service.json 4
```

**7. `examples/README.md` present with required honesty notes.**

`examples/README.md` (new) states plainly, near the top: Demo mode is a
deterministic keyword-based stub (not an LLM); every `.json` file is a real captured
request, none hand-written; these are "sample reports demonstrating the product's
shape and behavior, not accuracy claims"; and "No price benchmarking or market
evidence is implemented or claimed anywhere in these outputs." It also includes a
table mapping each input/output pair to what it demonstrates, and notes
`request_id`/`created_at`/`latency_ms` will differ on a fresh run.

**8. `README.md` links to the example pack, no other prose changes.**

```
$ git diff README.md
```

Two additions only: one paragraph after the existing sample-report excerpt linking
to `examples/README.md`, and the `examples/` subtree in "Repo structure" extended to
list the new files. No other lines changed (confirmed by the `+16` / `+0 -0`
diff-stat above — the diff is purely additive).

**9. `docs/CURRENT_STATE.md` updated: "Last updated" line, example pack, stub
broadening, honest limitations preserved.**

"Last updated" line now reads `2026-07-08 (TASK-008)`. A new "Fixed in TASK-008"
section (above "Fixed in TASK-007") documents the stub broadening and the new
example pack. The Architecture and Capabilities bullets for `stub_analyzer.py` were
updated to describe the new AC/appliance and home-maintenance keyword blocks and the
domain-generic summary/disclaimer behavior. The Gaps bullet about vehicle-flavored
scope was reworded to state honestly that the `NormalizedCategory` taxonomy and the
OpenAI-mode prompt (`backend/core/prompt.py`) are still vehicle-service-flavored —
only the Demo-mode stub's keyword coverage was broadened, and it's still a small
fixed keyword list, not real language understanding.

**10. `examples/sample_output.json` (TASK-007) regenerated and validates after the
stub change.**

Initially left as-is (see prior revision of this bundle) with wording drift flagged
as a follow-up. Per a later cleanup request, it has now been **regenerated** from a
real Demo-mode call against the unchanged `examples/sample_quote.txt`, so every
example output in the repo is consistent with the current stub:

```
$ QUOTECHECK_USE_OPENAI=0 conda run -n quotecheck uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
$ curl -s http://127.0.0.1:8000/health
{"status":"ok"}

$ curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}' \
  | python3 -m json.tool | tee examples/sample_output.json
{
    "line_items": [ ... 3 items: brake/red, tyre/yellow, "Other/unspecified charges"/yellow+vague ... ],
    "overall_summary": [
        "This report explains each line item in plain language, flags risk level, and lists questions to ask the vendor before approving.",
        "Safety-critical items (like brakes/tyres) should be verified with evidence before approval.",
        "Any generically named, bundled, or unclear charges are marked as needing clarification; ask the vendor for an itemized breakdown.",
        "Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made."
    ],
    "things_to_verify": [
        "Request an itemized parts + labour breakdown for each line item.",
        "Ask for photos, measurements, or diagnostic evidence supporting each recommended item.",
        "Confirm whether the recommendation is manufacturer-specified or vendor-suggested."
    ],
    "disclaimer": "QuoteCheck is a v0 prototype; results may be incomplete or wrong. Not safety advice; verify with a certified mechanic. QuoteCheck explains quotes and suggests questions; it does not verify vendor claims, guarantee fair pricing, or perform price benchmarking.",
    "metadata": {
        "prompt_version": "quotecheck_v0.2",
        "model": "quotecheck-demo-analyzer",
        "created_at": "2026-07-08T16:09:28.127130Z",
        "request_id": "2984e1a9-599f-455b-ac0d-056d58f1c4b2",
        "latency_ms": 0,
        "schema_valid": true
    }
}
```

Validated and model-checked:

```
$ conda run -n quotecheck python3 -c "
import json
from backend.core.schema import QuoteCheckResult
d = json.load(open('examples/sample_output.json'))
QuoteCheckResult.model_validate(d)
print('OK examples/sample_output.json')
print('model:', d['metadata']['model'])
"
OK examples/sample_output.json
model: quotecheck-demo-analyzer
```

Corresponding JSONL log entry confirms the request actually hit the live server:

```
$ tail -n 1 logs/app_runs.jsonl
{"event": "quotecheck_analyze", "created_at": "2026-07-08T16:09:28.127409Z", "request_id": "2984e1a9-599f-455b-ac0d-056d58f1c4b2", "prompt_version": "quotecheck_v0.2", "model": "quotecheck-demo-analyzer", "latency_ms": 0, "schema_valid": true, "num_items": 3, "risk_counts": {"red": 1, "yellow": 2, "green": 0}, "error": null}
```

`num_items: 3` and `risk_counts` match the 3 line items above (red/yellow/yellow).
`examples/quote_vehicle_service.txt`'s output (`examples/outputs/vehicle_service.json`,
captured earlier) is unaffected — it's a separate, already-current file. Backend
stopped after capture (`kill`; follow-up health check returned connection-refused,
exit 7).

`docs/CURRENT_STATE.md` was checked for an example-count mention that might need
adjusting: it already says "6 real captured Demo-mode input/output pairs" — the
count is unchanged by this regeneration (still 6 files; only one file's content was
refreshed), so no edit was needed there.

**11. `backend/core/schema.py` unchanged.**

```
$ git diff --stat main -- backend/core/schema.py
(no output)
```

No compatibility issue was found; the new stub logic only varies which strings are
assembled into already-existing fields (`overall_summary`, `things_to_verify`,
`disclaimer`, plus new `LineItem` instances using existing enum values) — no schema
edit was needed or made.

**12. No secrets committed.**

```
$ grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' examples README.md docs/CURRENT_STATE.md
no secrets found
```

**13. No frontend files changed; no OpenAI calls made.**

```
$ git status --porcelain --untracked-files=all | grep -i frontend
(no output)
```

All 5 captured outputs have `metadata.model == "quotecheck-demo-analyzer"` (see item
2), and the server was run with `QUOTECHECK_USE_OPENAI=0` explicitly set — no
`backend/.env` existed or was created, so OpenAI mode was never reachable.

Backend stopped after capture:

```
$ kill 98542 98555
$ ps aux | grep -i uvicorn | grep -v grep
no uvicorn processes remaining
```

## Commands run (full list)

```bash
git status --short
conda run -n quotecheck python -c "from backend.app import app; print(app.title)"
QUOTECHECK_USE_OPENAI=0 conda run -n quotecheck uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1:8000/health
mkdir -p examples/outputs
# for each of the 5 sample inputs:
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"quote_text": open(sys.argv[1]).read()}))' examples/quote_<name>.txt)" \
  | python3 -m json.tool | tee examples/outputs/<name>.json
conda run -n quotecheck python3 -c "
import json, glob
from backend.core.schema import QuoteCheckResult
for f in sorted(glob.glob('examples/outputs/*.json')):
    QuoteCheckResult.model_validate(json.load(open(f)))
    print('OK', f)
"
conda run -n quotecheck python3 -c "
import json
from backend.core.schema import QuoteCheckResult
QuoteCheckResult.model_validate(json.load(open('examples/sample_output.json')))
print('OK examples/sample_output.json (TASK-007 regression check)')
"
grep -ilE 'brake|tyre|oem' examples/outputs/ac_repair.json examples/outputs/home_maintenance.json examples/outputs/parts_labour_misc.json examples/outputs/vague_missing_details.json
grep -ilE 'market price|price benchmark|price comparison' examples/outputs/*.json
tail -n 6 logs/app_runs.jsonl
kill 98542 98555   # stop background uvicorn
grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' examples README.md docs/CURRENT_STATE.md
git diff --stat main
git status --short
```

## Risks / follow-ups (out of scope for this ticket)

- `examples/sample_output.json` (TASK-007) is now regenerated and consistent with
  the current stub (see item 10 above) — the earlier wording-staleness follow-up
  from this bundle's first revision is resolved.
- The `NormalizedCategory` taxonomy and the OpenAI-mode prompt
  (`backend/core/prompt.py`) remain vehicle-service-flavored — only Demo mode's
  stub was broadened. Feeding a real OpenAI-mode request an AC/home-maintenance
  quote today would still use the vehicle-flavored prompt; broadening that is
  SPEC.md target scope, not delivered here.
- The AC/appliance and home-maintenance keyword lists are small and fixed (5-6 terms
  each), same limitation the existing brake/tyre/generic-charge lists already have —
  a quote using different phrasing (e.g. "furnace" instead of "hvac") would still
  fall through to the generic/vague fallback.
- No automated eval harness (pass/fail scoring, CI) was added — this ticket is a
  sample/example pack, not the eval-harness roadmap item; `docs/CURRENT_STATE.md`
  and `README.md`'s Roadmap already track that as future work.

## Definition of done

- [x] Implementation complete within file scope (`README.md`,
      `backend/core/stub_analyzer.py`, `docs/CURRENT_STATE.md`, `examples/`,
      `docs/tickets/`, `docs/review/`).
- [x] 5 realistic sample inputs + 5 real captured Demo-mode outputs under
      `examples/outputs/`, all schema-valid.
- [x] `backend/core/stub_analyzer.py` broadened minimally and deterministically
      (AC/appliance, home-maintenance keyword blocks; domain-generic summary text).
- [x] `backend/core/schema.py` unchanged.
- [x] `examples/README.md` written with required honesty notes.
- [x] `docs/CURRENT_STATE.md` "Last updated" line and "Fixed in TASK-008" entry
      added; Gaps section kept honest.
- [x] Ticket file (`docs/tickets/TASK-008-sample-cases-evals.md`) written.
- [x] This review bundle written with concrete evidence, no placeholders.
- [x] No secrets committed; no frontend/OpenAI-analyzer/schema files changed; no
      OpenAI calls made.
- [x] Work left uncommitted on `task/TASK-008-sample-cases-evals` — the user will
      review and commit manually.
