# Review bundle — QC-HOTFIX — Demo `verification_questions` bound

## 1. Ticket

`docs/tickets/QC-HOTFIX-demo-question-bound.md`. Branch
`task/QC-HOTFIX-demo-question-bound` (based on `main` @ `2ff1cff`). **Nothing
committed, merged, or deployed. The public deployment was not contacted, and no OpenAI calls were made.**

## 2. Root cause (confirmed)

`_domain_questions_and_verification()` in `backend/core/stub_analyzer.py` appends
a fixed 3-question block for each matched keyword group (vehicle, AC/appliance,
home-maintenance, generic-charge). Nothing bounds the combined list, so 3 blocks
produce 9 questions and 4 blocks produce 12. `QuoteCheckResult(...)` construction then raises
`ValidationError` (`verification_questions` `max_length=8`). `/analyze` treats this as
an unclassified failure and returns HTTP 500 `internal_error`.

The hypothesis correctly identified the mechanism, but the blocks are different from the ones expected. The reproduction matches
**vehicle** (`brake`), **AC** (`compressor`), and **generic-charge** (`gas top-up` is
in `GENERIC_CHARGE_TERMS`). **Home does not match**, because `tap` and `earthing` are not
in `HOME_MAINTENANCE_TERMS`. Before the fix:

```text
ValidationError 1 validation error for QuoteCheckResult
verification_questions
  List should have at most 8 items after validation, not 9 [type=too_long, ...]
```

`things_to_verify` has no upper bound in the schema, so it was not part of the failure
and is unchanged.

## 3. Fix and chosen boundary

The boundary is the analyzer's own combination point, because the analyzer promises schema-valid
output. The schema limit stays the same.

- `backend/core/stub_analyzer.py`: each block now goes into `question_blocks`, and a
  new `_fit_question_blocks()` flattens it. If the total is ≤ 8, the output is identical to
  before, so single-block and two-block quotes and the full eval corpus are unaffected. If the total is > 8, the 8
  slots are dealt out round-robin in block order (3 blocks → 3/3/2, 4 blocks →
  2/2/2/2), and each block's leading questions are kept in their original block order.
  The result is deterministic and every matched domain stays represented.
- `backend/core/schema.py`: the existing literal `max_length=8` is now named
  `MAX_VERIFICATION_QUESTIONS = 8` so the analyzer trims to the same single
  source. The value and contract are unchanged.

## 4. Files changed

| File | Change |
|---|---|
| `backend/core/stub_analyzer.py` | `question_blocks` + `_fit_question_blocks()` (+ import) |
| `backend/core/schema.py` | Named constant for the existing bound of 8 |
| `eval/tests/test_stub_analyzer.py` | `MixedDomainQuestionBoundTests` (4 tests) |
| `docs/CURRENT_STATE.md` | `Last updated`, capability paragraph, `### Fixed in QC-HOTFIX-demo-question-bound` |
| `docs/tickets/QC-HOTFIX-demo-question-bound.md` | Created |
| `docs/review/REVIEW_BUNDLE__QC-HOTFIX-demo-question-bound.md` | Created (this file) |

## 5. Acceptance evidence

All commands were run in the conda env `quotecheck` from the repo root.

**AC1 / AC3: the reproduction goes through the analyzer.** Direct `analyze_quote_stub(...)` followed by
`QuoteCheckResult.model_validate(...)` returned 8 questions:

```text
8
Can you share photos or measurements (pad thickness, tread depth) that support the brake/tyre recommendation?
Is this brake/tyre work needed immediately, or can it wait until after a second opinion?
Are the replacement parts OEM or aftermarket, and what warranty do they carry?
What diagnostic fault code or symptom led to the compressor/refrigerant recommendation?
Is the unit still under manufacturer or extended warranty?
What refrigerant type and quantity does the job require, and is that reflected in the price?
Can you itemize exactly what the misc/service/handling charge covers?
Is this a fixed fee or a time-based labour charge, and what's the hourly rate if applicable?
```

**AC4: regression tests.** `python -m unittest eval.tests.test_stub_analyzer.MixedDomainQuestionBoundTests`

- On `main`'s analyzer (the backend changes were stashed and the new tests kept):
  `Ran 4 tests` / `FAILED (errors=3)` with
  `List should have at most 8 items after validation, not 9` (three blocks) and `not 12`
  (four blocks, twice).
- After the fix: `Ran 4 tests` / `OK`.

The tests cover:
- the reproduction (3 blocks): valid, 3 ≤ n ≤ 8, and the vehicle, AC, and generic blocks are all present;
- the reproduction plus `Plumbing repair.` (4 blocks): valid, 3 ≤ n ≤ 8, and all four blocks are present;
- determinism;
- a two-block quote, which keeps all 6 questions in their original order.

**AC5: behaviour preservation.** `_fit_question_blocks` is the identity for totals ≤ 8,
and totals of 8 or fewer cover every single-domain and two-block quote. The eval corpus result is unchanged (see AC6). A
mixed quote keeps at least 2 questions from every matched block.

**AC6: broader verification.**

```text
$ python -m unittest discover -s eval/tests -p 'test_*.py'
Ran 148 tests ... OK

$ python -m eval.run_eval --validate-only
OK — 27 cases, 6 domains, 9 categories, 0 errors.

$ python -m eval.run_eval --mode demo
27/27 schema-valid; 24/27 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation (known Demo-mode gaps are retained, not suppressed).
# summary_*.md "Failed cases": AUTO-004, CONT-003, HVAC-003
```

This is the accepted baseline. The generated `eval/results/*_20260928T063622Z.*` files
from this verification run were deleted and are not part of the diff.

**AC2 / AC7: local HTTP smoke.** I ran `QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8765`:

```text
GET  /health  -> {"status":"ok"}
POST /analyze (reproduction) -> HTTP 200
model quotecheck-demo-analyzer schema_valid True vq 8 ttv 9 items 3
```

The response re-validated as `QuoteCheckResult`. The log line in `logs/app_runs.jsonl`
reads `"analyzer": "demo", "success": true`. The server was stopped afterwards.

## 6. Self-review

- The `while remaining` loop only runs when the total is > 8, so a free slot always exists and the loop
  terminates.
- There is no ordering change for outputs of 8 or fewer, and there is no change to `things_to_verify`, OpenAI mode,
  the prompt, the API, the frontend, or deployment.
- A quote that matches three blocks loses the third question of the last block
  (for the reproduction, that is the generic "overlap with another line item" question). This is an accepted
  trade-off for representation.

## 7. Out-of-scope observations

- `tap`, `earthing`, and `panel` are not home-maintenance terms, so the reproduction's
  plumbing and electrical lines get no home-domain questions. This is a domain-recognition gap and is
  not fixed here (the ticket excludes new domain recognition).
- `things_to_verify` can grow to 12 items for a four-block quote. The schema allows this because it has no upper bound.
