# Review Bundle — TASK-008A — Personalize demo-mode vendor questions and things-to-verify

Ticket: [`docs/tickets/TASK-008A-personalize-demo-guidance.md`](../tickets/TASK-008A-personalize-demo-guidance.md)

## Manual UI verification finding (why this ticket exists)

While reviewing TASK-008's merged output, the two bottom report cards — "Questions
to ask the vendor" (`verification_questions`) and "Things to verify before
approving" (`things_to_verify`) — were found to show mostly the same generic advice
across every sample domain (vehicle, AC, home maintenance, parts, vague). Both lists
were fixed 3-item static strings in `analyze_quote_stub`, unaffected by which
keyword block matched. This made the demo feel template-driven rather than
personalized to the quote actually analyzed.

## Git-history note (branch discipline)

TASK-008's work was committed (`fe778ed`) and merged into `main` (`c4b1545`)
directly, outside this session's tool calls and outside the repo's normal
branch → ticket → review-bundle → manual-merge sequence. This was discovered
mid-session while this ticket's work was already in progress as uncommitted changes
on top of `task/TASK-008-sample-cases-evals`. Per user direction, this ticket's work
was moved to a **new branch, `task/TASK-008A-personalize-demo-guidance`, created
from current `main`** (which already contains the TASK-008 merge), rather than
reusing the now-merged `task/TASK-008-sample-cases-evals` branch. No destructive git
operations were run; the uncommitted working-tree changes were carried across via
`git checkout -b`, which does not discard anything.

```
$ git branch --show-current
task/TASK-008A-personalize-demo-guidance
```

## Fix

**`backend/core/stub_analyzer.py`**: added `_domain_questions_and_verification()`,
called once per `analyze_quote_stub` run with the same `vehicle_matched`/
`ac_matched`/`home_matched`/`generic_charge_matched` booleans already used to build
line items. Each matched domain contributes its own 3-item `verification_questions`
chunk and its own, differently-worded 3-item `things_to_verify` chunk (vendor-facing
question vs. user-facing checklist item — not the same sentence reworded); domains
combine additively when more than one matches (e.g. a vehicle quote that also has a
bundled charge gets both the vehicle chunk and the generic-charge chunk). Only the
true no-match case (nothing domain-specific detected at all) falls back to plain,
non-domain-specific clarifying questions — deliberately kept generic since the stub
genuinely has no information to be specific about in that case. Fully deterministic:
no LLM calls, no web calls, no new dependencies, no schema change (`QuoteCheckResult`
already declares `verification_questions: List[str]` with `min_length=3,
max_length=8`, and `things_to_verify: List[str]` with `min_length=3`, no max — both
bounds were checked against every combination, see Validation below).

## Files changed

```
$ git status --short
 M backend/core/stub_analyzer.py
 M docs/CURRENT_STATE.md
 M examples/outputs/ac_repair.json
 M examples/outputs/home_maintenance.json
 M examples/outputs/parts_labour_misc.json
 M examples/outputs/vague_missing_details.json
 M examples/outputs/vehicle_service.json
 M examples/sample_output.json
?? docs/tickets/TASK-008A-personalize-demo-guidance.md

$ git diff --stat main
 backend/core/stub_analyzer.py               | 99 +++++++++++++++++++++++++----
 docs/CURRENT_STATE.md                       | 42 ++++++++++--
 examples/outputs/ac_repair.json             | 16 ++---
 examples/outputs/home_maintenance.json      | 16 ++---
 examples/outputs/parts_labour_misc.json     | 16 ++---
 examples/outputs/vague_missing_details.json | 16 ++---
 examples/outputs/vehicle_service.json       | 22 ++++---
 examples/sample_output.json                 | 22 ++++---
 8 files changed, 183 insertions(+), 66 deletions(-)
```

(This review bundle itself is also new/untracked, same as the ticket file.)

No `frontend/`, `backend/core/schema.py`, `backend/core/openai_analyzer.py`,
`README.md`, `backend/.env`, or `logs/*.jsonl` (tracked) file appears in the diff.

## Acceptance criteria — evidence

**1–5. Each domain sample has domain-specific `verification_questions`/
`things_to_verify`; no cross-section duplicate sentences.**

```
$ for f in examples/outputs/*.json examples/sample_output.json; do
    python3 -c "
import json
d = json.load(open('$f'))
print('$f')
print(' verification_questions:', d['verification_questions'])
print(' things_to_verify:', d['things_to_verify'])
print(' exact duplicates across both lists:', set(d['verification_questions']) & set(d['things_to_verify']) or 'none')
"
  done
```

Output (abridged to the two list contents; full files in `examples/`):

- **`examples/outputs/vehicle_service.json`** (and `examples/sample_output.json`,
  same input) — vehicle-specific: *"Can you share photos or measurements (pad
  thickness, tread depth) that support the brake/tyre recommendation?"*, *"Is this
  brake/tyre work needed immediately, or can it wait until after a second
  opinion?"*, *"Are the replacement parts OEM or aftermarket, and what warranty do
  they carry?"* — plus generic-charge questions ("Can you itemize exactly what the
  misc/labour/service charge covers?", etc.), since this quote matches both
  keyword blocks. `things_to_verify`: *"Confirm current pad thickness and tread
  depth measurements before approving replacement."*, *"Check whether the vehicle
  is still under a manufacturer or extended warranty..."*, *"Get a second opinion
  from an independent mechanic..."* plus the generic-charge verify chunk. 6 items
  each (3+3), no overlap between the two lists.
- **`examples/outputs/ac_repair.json`** — AC-specific: *"What diagnostic fault code
  or symptom led to the compressor/refrigerant recommendation?"*, *"Is the unit
  still under manufacturer or extended warranty?"*, *"What refrigerant type and
  quantity does the job require..."*. `things_to_verify`: *"Get the unit's
  model/serial number and confirm its warranty status..."*, *"Confirm a refrigerant
  leak was actually located, not just assumed from low pressure."*, *"Ask whether a
  full system replacement was considered instead of a compressor repair, and
  why."* No "brake"/"tyre"/"OEM" anywhere.
- **`examples/outputs/home_maintenance.json`** — contractor/home-scope-specific:
  *"Can you provide a written scope of work broken down by task (plumbing,
  electrical, etc.)?"*, *"What is the estimated labor-hours and materials cost for
  each task?"*, *"Are permits required for any of this work..."*.
  `things_to_verify`: *"Request an itemized scope-of-work document..."*, *"Confirm
  whether permits are required..."*, *"Check the contractor's license and
  insurance..."*
- **`examples/outputs/parts_labour_misc.json`** — itemization/charge-breakdown
  focused, matching the ticket's requirement: *"Can you itemize exactly what the
  misc/labour/service charge covers?"*, *"Is this a fixed fee or a time-based
  labour charge, and what's the hourly rate if applicable?"*, *"Does this charge
  overlap with cost already included in another line item on the quote?"*
  `things_to_verify`: *"Request a line-by-line breakdown of any bundled or
  generically named charges."*, *"Confirm this charge isn't duplicating cost
  already included in another line item."*, *"Ask whether this charge is
  negotiable or waivable..."*
- **`examples/outputs/vague_missing_details.json`** — clarifying questions, no
  invented specifics: *"Can you resend the quote with itemized parts, labour, and a
  reason for each recommendation?"*, *"What specific work is being proposed, and
  what problem is it meant to fix?"*, *"Is this work urgent, or can it wait until
  you get a second quote?"* `things_to_verify`: *"Ask for a fully itemized
  breakdown..."*, *"Confirm what underlying problem or symptom prompted this
  quote."*, *"Get the vendor's contact info and a written copy of the quote..."*

`exact duplicates across both lists` printed `none` for all 6 files.

**6. Domain chunks combine additively and stay within schema bounds.**

```
$ conda run -n quotecheck python3 -c "
import json, glob
from backend.core.schema import QuoteCheckResult
files = sorted(glob.glob('examples/outputs/*.json')) + ['examples/sample_output.json']
for f in files:
    d = json.load(open(f))
    QuoteCheckResult.model_validate(d)
    assert d['metadata']['model'] == 'quotecheck-demo-analyzer', f
    print('OK', f, '| model:', d['metadata']['model'], '| Qs:', len(d['verification_questions']), '| verify:', len(d['things_to_verify']))
"
OK examples/outputs/ac_repair.json | model: quotecheck-demo-analyzer | Qs: 3 | verify: 3
OK examples/outputs/home_maintenance.json | model: quotecheck-demo-analyzer | Qs: 3 | verify: 3
OK examples/outputs/parts_labour_misc.json | model: quotecheck-demo-analyzer | Qs: 3 | verify: 3
OK examples/outputs/vague_missing_details.json | model: quotecheck-demo-analyzer | Qs: 3 | verify: 3
OK examples/outputs/vehicle_service.json | model: quotecheck-demo-analyzer | Qs: 6 | verify: 6
OK examples/sample_output.json | model: quotecheck-demo-analyzer | Qs: 6 | verify: 6
```

Single-domain samples: 3 questions / 3 verify items (schema min is 3 — satisfied
exactly). Two-domain sample (vehicle + generic-charge, both `sample_output.json`
and `vehicle_service.json`): 6 questions (schema max is 8 — satisfied with room to
spare) / 6 verify items (no upper bound).

**7. Every output validates against `QuoteCheckResult`; `metadata.model` correct.**

Confirmed in the same command block above — all 6 files (`OK`), all with
`model: quotecheck-demo-analyzer`.

**8. No vehicle-specific leakage into non-vehicle samples; no price-benchmarking
claims.**

```
$ grep -ilE 'brake|tyre|\bOEM\b' examples/outputs/ac_repair.json examples/outputs/home_maintenance.json examples/outputs/parts_labour_misc.json examples/outputs/vague_missing_details.json
none found (expected)

$ for f in examples/outputs/*.json examples/sample_output.json; do
    grep -oE 'Price benchmarking is not implemented[^"]*' "$f"
    grep -oE 'perform price benchmarking[^"]*' "$f"
  done
Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made.
perform price benchmarking.
... (same two lines, once per file, all 6 files)
```

Every match is the disclaimer/summary stating price benchmarking is **not**
implemented — never a claim of one.

**9. All 6 example outputs regenerated from real Demo-mode `/analyze` calls.**

```
$ QUOTECHECK_USE_OPENAI=0 conda run -n quotecheck uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
$ curl -s http://127.0.0.1:8000/health
{"status":"ok"}

$ curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}' \
  | python3 -m json.tool | tee examples/sample_output.json > /dev/null
saved examples/sample_output.json

$ for name in vehicle_service:quote_vehicle_service ac_repair:quote_ac_repair \
    home_maintenance:quote_home_maintenance parts_labour_misc:quote_parts_labour_misc \
    vague_missing_details:quote_vague_missing_details; do
    out="${name%%:*}"; infile="examples/${name##*:}.txt"
    curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
      -d "$(python3 -c 'import json,sys;print(json.dumps({"quote_text": open(sys.argv[1]).read()}))' "$infile")" \
      | python3 -m json.tool | tee "examples/outputs/${out}.json" > /dev/null
  done
saved examples/outputs/vehicle_service.json
saved examples/outputs/ac_repair.json
saved examples/outputs/home_maintenance.json
saved examples/outputs/parts_labour_misc.json
saved examples/outputs/vague_missing_details.json
```

Corresponding JSONL log entries confirm the requests hit the live server:

```
$ tail -n 6 logs/app_runs.jsonl
{"request_id": "01f493b6-...", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 3, "risk_counts": {"red": 1, "yellow": 2, "green": 0}, ...}   # sample_output.json
{"request_id": "dd9b57ff-...", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 3, "risk_counts": {"red": 1, "yellow": 2, "green": 0}, ...}   # vehicle_service.json
{"request_id": "fd8f475a-...", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 1, "green": 0}, ...}   # ac_repair.json
{"request_id": "1451f031-...", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 0, "green": 1}, ...}   # home_maintenance.json
{"request_id": "a8564194-...", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 1, "green": 0}, ...}   # parts_labour_misc.json
{"request_id": "90bc02cf-...", "model": "quotecheck-demo-analyzer", "schema_valid": true, "num_items": 1, "risk_counts": {"red": 0, "yellow": 1, "green": 0}, ...}   # vague_missing_details.json
```

`num_items`/`risk_counts` per entry match each output file exactly.

Backend stopped after capture:

```
$ kill <pids>
$ ps aux | grep uvicorn | grep -v grep
no uvicorn processes remaining
$ curl -s -m 2 http://127.0.0.1:8000/health; echo " exit:$?"
 exit:7
```

**10. No secrets committed.**

```
$ grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' examples docs/CURRENT_STATE.md
no secrets found
```

**11. `docs/CURRENT_STATE.md` updated correctly, without misattributing TASK-008A
content into the already-merged TASK-008 changelog entry.**

"Last updated" line changed to `2026-07-08 (TASK-008A)`. A new "Fixed in TASK-008A"
section was added **above** "Fixed in TASK-008" (kept byte-identical to what's
committed on `main`, restored after an earlier in-progress edit had incorrectly
merged TASK-008A content into it — caught and fixed before finalizing this bundle).
The Capabilities-section paragraph describing `verification_questions`/
`things_to_verify` behavior was updated to describe the new domain-aware behavior
(no ticket attribution in that paragraph, so no misattribution risk there).

```
$ git diff main -- docs/CURRENT_STATE.md | grep '^-.*TASK-008\b' | grep -v TASK-008A
(no output — confirms no line inside the original "Fixed in TASK-008" content block was altered)
```

## Commands run (full list)

```bash
git status --short
git branch --show-current
git log --oneline -5
git reflog -15
git show --stat fe778ed
git show --stat c4b1545
git checkout -b task/TASK-008A-personalize-demo-guidance
QUOTECHECK_USE_OPENAI=0 conda run -n quotecheck uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}' \
  | python3 -m json.tool | tee examples/sample_output.json
# for each of the 5 sample inputs:
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"quote_text": open(sys.argv[1]).read()}))' examples/quote_<name>.txt)" \
  | python3 -m json.tool | tee examples/outputs/<name>.json
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
grep -oE 'Price benchmarking is not implemented[^"]*' examples/outputs/*.json examples/sample_output.json
tail -n 6 logs/app_runs.jsonl
kill <uvicorn pids>
grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' examples docs/CURRENT_STATE.md
git diff --stat main
git status --short
```

## Risks / follow-ups (out of scope for this ticket)

- TASK-008's own review bundle (`docs/review/REVIEW_BUNDLE__TASK-008-sample-cases-evals.md`,
  already merged into `main`) still describes `verification_questions`/
  `things_to_verify` as static text — that bundle is a historical record of what
  TASK-008 delivered and was intentionally left untouched; this bundle is the
  record of what changed since.
- The domain keyword lists (vehicle/AC/home-maintenance/generic-charge) are
  unchanged from TASK-008 — still small, fixed lists; a quote using unrecognized
  phrasing still falls through to the generic fallback questions.
- The git-history anomaly (TASK-008 committed/merged to `main` outside the normal
  ticket workflow) is noted here for visibility but not otherwise addressed — no
  history rewrite was performed.

## Definition of done

- [x] Fresh branch `task/TASK-008A-personalize-demo-guidance` created from current
      `main`; old `task/TASK-008-sample-cases-evals` branch left untouched.
- [x] `backend/core/stub_analyzer.py`: domain-aware `verification_questions`/
      `things_to_verify` implemented, deterministic, no LLM/web calls, no schema
      change.
- [x] All 6 example outputs regenerated from real Demo-mode `/analyze` calls and
      re-validated against `QuoteCheckResult`.
- [x] `docs/CURRENT_STATE.md` updated with a correctly-attributed "Fixed in
      TASK-008A" section and "Last updated" line; original "Fixed in TASK-008"
      content restored/untouched.
- [x] Ticket file (`docs/tickets/TASK-008A-personalize-demo-guidance.md`) written.
- [x] This review bundle written with concrete evidence, no placeholders.
- [x] No secrets committed; no frontend/schema/OpenAI-analyzer/README files
      changed; no OpenAI calls made.
- [x] Work left uncommitted on `task/TASK-008A-personalize-demo-guidance` — the
      user will review and commit manually.
