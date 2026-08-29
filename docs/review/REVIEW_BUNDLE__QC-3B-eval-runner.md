# Review Bundle — QC-3B — Executable deterministic eval / regression harness

## 1. Ticket / phase

- Ticket: `docs/tickets/QC-3B-eval-runner.md`
- Phase: QC-3B (hardening — executable Layer A eval runner over the QC-3A corpus)
- Branch: `task/QC-3B-eval-runner`
- Not committed. No deployment. **No paid OpenAI API call of any kind was made.**

## 2. Scope summary

Added a repository-native runner (`eval/corpus.py`, `eval/graders.py`,
`eval/run_eval.py`) plus stdlib `unittest` self-tests and a committed Demo baseline.
The runner permanently validates the 27-case corpus, executes each selected case
through the real route handler `backend.app.analyze`, applies only the QC-3A
deterministic checks, writes a timestamped JSONL + Markdown pair, and exits non-zero
on deterministic failure. Docs updated: `eval/README.md`, `README.md`,
`docs/CURRENT_STATE.md`.

**No application source code changed.** No file under `backend/`, `frontend/`, or
`examples/` was modified. No `eval/cases/**`, `eval/termsets.json`, or `eval/rubric.md`
change. No dependency added — standard library plus the existing Pydantic/FastAPI
stack.

## 3. Execution-path design decision

**Chosen boundary: call the FastAPI route handler function directly, in-process.**

```python
from backend.app import analyze
from backend.core.schema import AnalyzeRequest
result = analyze(AnalyzeRequest(quote_text=case.quote_text))   # -> QuoteCheckResult
```

Rationale:

- `analyze` (`backend/app.py:97`) is a plain `def` taking one Pydantic argument — no
  `Depends`, no `Request`, no app state, not `async`. It returns the real
  `QuoteCheckResult` object.
- It is the *only* place stub-vs-OpenAI dispatch lives (`app.py:116-120`); calling it
  exercises the genuine application orchestration (dispatch, request-id generation,
  latency handling, success/failure JSONL logging) rather than reimplementing it.
- All provenance is populated by the analyzers themselves (`prompt_version`, `model`,
  `created_at`, `request_id`, `latency_ms`, `schema_valid`) — a direct call loses
  none of it.
- The HTTP layer only adds body-validation (replicated exactly by constructing
  `AnalyzeRequest`), CORS (irrelevant), and `response_model` serialization
  (undesirable — the runner wants the object to independently re-validate).
- No HTTP server, no `TestClient`, no `httpx`, no subprocess. None were needed.

Side effect handled: the route appends one line to `logs/app_runs.jsonl` via
`run_logger`. The runner sets `QUOTECHECK_LOG_PATH` to a throwaway `tempfile` **before
importing `backend`** and deletes it afterwards, so the real app log is untouched
while the genuine logging path still runs.

Route-level error wrapping: `run_case` wraps the single `analyze(...)` call in
`try/except Exception`. Any exception — including `fastapi.HTTPException` and the
OpenAI analyzer's `RuntimeError` — becomes a readable `execution_error`
(`f"{type(e).__name__}: {e}"`, plus `status_code=` / `detail=` when present via
`getattr`). That case is marked `schema_pass=False`, `deterministic_pass=False`, and
the suite continues. Verified by `test_run_eval.ExecutionErrorWrappingTests`.

### Mode / config sequencing

`backend/core/config.py` freezes `USE_OPENAI` / `MODEL` / `OPENAI_API_KEY` /
`APP_RUN_LOG_PATH` from `os.environ` at first import, and `backend/app.py` calls
`load_dotenv("backend/.env")` at import (which does not override already-set vars).
So `main()`:

1. parses args;
2. for `--mode openai` without `--allow-paid`, prints guidance and returns `2`
   **before** any `backend` import or env mutation;
3. sets `QUOTECHECK_USE_OPENAI` and the throwaway `QUOTECHECK_LOG_PATH`;
4. only then (inside `run_suite`) imports `backend.app` / `backend.core.*`.

One invocation is one mode; per-mode reporting means running the suite twice. No
monkeypatching of `backend.app.USE_OPENAI`, no re-import tricks.

## 4. Module / file design

| File | Lines | Purpose |
|---|---|---|
| `eval/__init__.py` | 8 | package marker + Layer A / Layer B note |
| `eval/corpus.py` | 487 | corpus + termset loading; permanent `validate_corpus` (pure); `Case` / `Termset` / `Corpus` dataclasses; `CorpusError` |
| `eval/graders.py` | 347 | `CheckResult`; whole-word matcher; `analysis_text` extraction; graders for `schema_valid`, `metadata_complete`, `forbidden_terms`, `uncertainty_marker`, `line_items_where`; dispatch; `PRICE_GUARD_CHECK` |
| `eval/run_eval.py` | 627 | argparse CLI; env/mode sequencing; execution adapter (`run_case`); orchestration; pure reporting (`aggregate_by_domain/category`, `percentile`, `build_summary_md`, `suite_exit_code`); artifact writing; `--validate-only` |
| `eval/tests/support.py` | 119 | builders for real `QuoteCheckResult` / `Case` objects; real committed disclaimer text |
| `eval/tests/test_corpus.py` | 229 | corpus-validation tests |
| `eval/tests/test_graders.py` | 197 | grader tests |
| `eval/tests/test_run_eval.py` | 203 | reporting / exit / cost-guard / error-wrapping tests |

Three real modules: corpus load+validate, grader logic, orchestration+reporting.
Reporting stays in `run_eval.py` as pure functions, as the ticket allows.

## 5. Corpus validation

`validate_corpus(cases: list[dict], termsets) -> list[str]` is pure (operates on
parsed dicts). `load_corpus` does the IO and raises `CorpusError` (newline-joined) if
the list is non-empty. It runs before any analyzer call. A malformed corpus aborts
the suite (`run_suite` returns `2`); one failing *case result* does not.

Enforced (see `--validate-only` output in §13.C):

- every `eval/cases/*.json` parses;
- exactly the 7 required top-level keys (`regression_origin` allowed only as an 8th);
- `case_id` non-empty and unique;
- `domain` in the 6-value closed enum; `categories` non-empty, each in the 9-value
  closed enum;
- `rationale`, `quote_text` non-empty;
- `semantic_expectations` present with its 4 sub-keys;
- `deterministic_expectations` has list `must` and list `must_not`;
- every check has `check` in `{forbidden_terms, uncertainty_marker, line_items_where}`
  with an **exact** key set:
  - `forbidden_terms` → `{check, termset}` only; `termset` resolves in
    `termsets.json`; inline `terms` / per-case `mode` / `fields` rejected;
  - `uncertainty_marker` → `{check, marker, expected}`; `marker` in the 3
    `UncertaintyMarkers` field names (derived from `backend.core.schema`, not
    hardcoded); `expected` bool;
  - `line_items_where` → `{check, property, value, min_count}`; `property` in
    `{vague_or_confusing, evidence_needed_nonempty}`; `risk_level` / `max_count`
    rejected;
- each termset in `termsets.json` has `mode` in `{absolute, not_in_source}`,
  `fields == "analysis_text"`, non-empty `terms`;
- every referenced termset resolves;
- no duplicate whitespace-normalized `quote_text`;
- **corpus size in [24, 30] inclusive** — hard failure outside it;
- `REG-001` exactly once; `REG-002` exactly once;
- `regression_origin` present on REG-001/REG-002, absent elsewhere;
- category → expectation consistency (QC-3A rules):
  - `clean_itemized` ⇒ `must` has `ambiguous_items_present == false` **and**
    `missing_quote_context == false`;
  - `professional_confirmation_expected` ⇒ `needs_professional_confirmation == true`;
  - `professional_confirmation_not_expected` ⇒ `needs_professional_confirmation == false`;
  - `cross_domain_trap` ⇒ `must_not` has ≥1 `forbidden_terms` guard whose termset is
    a **domain-leakage** set (`vehicle_domain` / `trade_domain`) — tighter than "any
    `forbidden_terms`", so REG-002's `absolute` `price_judgment` entry alone would not
    satisfy it.

No PII detector — the corpus is synthetic; QC-3A's regex was authoring hygiene only.

## 6. Grader implementations

Exactly the QC-3A vocabulary in use. `topic_present`, `line_items_where` `risk_level`
/ `max_count`, inline `forbidden_terms`, per-case termset `mode`, and `all_text` are
**not implemented and not documented** — a case using any of them is a corpus error.

- **`schema_valid`** (global) — `QuoteCheckResult.model_validate(result.model_dump(
  mode="json"))`. An independent round-trip, not a read of `metadata.schema_valid`.
  Analyzer execution failure → `schema_pass=False`, `deterministic_pass=False`,
  `execution_error` recorded, remaining checks skipped for that case, suite continues.
- **`metadata_complete`** (global) — one `CheckResult` per sub-assertion
  (`metadata_complete:prompt_version`, `:model`, `:request_id`, `:schema_valid`,
  `:latency`, `:created_at`, `:model_provenance`, `:prompt_version_match`).
  Provenance: Demo ⇒ `model == DEMO_ANALYZER_MODEL` (`"quotecheck-demo-analyzer"`),
  OpenAI ⇒ `model == MODEL` (configured `QUOTECHECK_MODEL`). `prompt_version` compared
  to `backend.core.prompt.PROMPT_VERSION` — never hardcoded, so a legitimate prompt
  bump does not break the runner.
- **`forbidden_terms`** — shared termset only; `mode` and `terms` read from
  `termsets.json`. One `CheckResult` per entry, `detail.violations` listing
  `{term, field, snippet}`.
- **`uncertainty_marker`** — `getattr(result.uncertainty_markers, marker)` vs
  `expected`.
- **`line_items_where`** — counts line items where the predicate holds
  (`vague_or_confusing == value`, or `bool(evidence_needed) == value`); passes when
  `count >= min_count`; message reports the observed count and matching indices.

The global `price_judgment` guard is injected into every case's `must_not`,
de-duplicated against an identical entry the case already restates (REG-002,
CONT-004, ELEC-004), so it is graded once.

Every `CheckResult` carries `check`, `passed`, `label`, `expected`, `observed`,
`message`, `detail` — a reviewer sees *why* a case failed without reading grader code.

## 7. Termset matching semantics

- Whole-word / whole-phrase, case-insensitive, never substring:
  `term_pattern(term)` → `re.compile(r"(?<!\w)" + r"\s+".join(re.escape(t) for t in
  term.split()) + r"(?!\w)", re.IGNORECASE)`.
  - `tire` does **not** match `entire`; matches `new tire`.
  - `good deal` does **not** match `good dealer`.
  - the real committed disclaimer phrase `guarantee fair pricing` and
    `high-value or safety-critical work` do **not** trip `price_judgment` — verified
    in `test_graders.test_price_termset_does_not_fire_on_real_boundary_language`
    against the actual committed disclaimer + `overall_summary` line.
- `absolute` (e.g. `price_judgment`): any hit in the `analysis_text` fields fails,
  whatever the quote says.
- `not_in_source` (e.g. `vehicle_domain`, `trade_domain`): a hit in authored text
  fails **only** if the same term is not present (whole-word) in `quote_text`. A term
  in both output and quote passes (sourced). Documented, in code and in the summary,
  as *a deterministic proxy for invented domain terminology, not proof of semantic
  hallucination*.
- Scanned fields (`analysis_text`, the only group): `explanation`, `rationale_short`,
  `evidence_needed`, `overall_summary`, `verification_questions`, `things_to_verify`,
  `disclaimer`. `name_raw` is never scanned (schema-defined as quote-copied text);
  metadata / `request_id` / `model` / `refusals` never scanned.

## 8. CLI and cost boundary

```
python -m eval.run_eval [--mode {demo,openai}] [--allow-paid]
                        [--case-id ID ...] [--domain D ...] [--category C ...]
                        [--validate-only] [--results-dir PATH]
```

- `--mode demo` (default) — deterministic, zero API cost, no network.
- `--mode openai` **requires** `--allow-paid`. Without it, `main()` prints the guard
  message and returns `2` before any `backend` import, before any env mutation,
  before any `analyze` call, before any OpenAI client — **no billable inference**.
  A harmless `backend.core.schema` import (for `--validate-only`) may already have
  happened; that is not overclaimed.
- With `--mode openai --allow-paid`, `run_suite` first hard-errors if
  `OPENAI_API_KEY` is unset, then prints the selected-case count, the configured
  model, and `WARNING: this will make one billed OpenAI API call per selected case.`
  before running.
- `--case-id` (repeatable) restricts the run; an unknown id is a `SystemExit`.
  `--domain` / `--category` are simple set-membership filters. No query language.
- No `--ignore-failures`, no xfail mechanism.
- **No paid OpenAI run was performed in this ticket.** The guard is verified by
  `test_run_eval.PaidModeGuardTests` (with `run_suite` — the only path that imports
  the analyzer — replaced by a spy, `main(["--mode","openai"])` returns `2` and the
  spy is never called) and by command §13.F.

## 9. Per-case artifact schema

One JSON object per line in `run_<UTC>.jsonl` (a full run = 27 lines). Keys:

```
case_id, domain, categories, mode, prompt_version, model,
schema_pass, deterministic_pass, failed_checks,
check_results[]  -> {check, label, passed, expected, observed, message, detail},
latency_ms, execution_error, human_review_status ("not_reviewed"),
rationale, run_timestamp,
regression_origin   (only when the case carries it)
```

`deterministic_pass = schema_pass and execution_error is None and all(cr.passed …)`.
`failed_checks = [cr.label for cr in check_results if not cr.passed]`. No semantic
scores.

## 10. Summary / report format

`summary_<UTC>.md` sections, in order (see §13.D output):

- `## Run metadata` — timestamp, mode, model, prompt version, selected cases
- `## Overall results` — total, schema passes + rate, deterministic passes + rate,
  execution errors
- `## Failures by domain` — `Domain | Cases | Passed | Failed`
- `## Failures by category` — same columns; a multi-category case counted in each
- `## Failed cases` — per failing case: id, domain, each failed check with its message
- `## Historical regressions` — explicit `REG-001` / `REG-002` PASS/FAIL + failed checks
- `## Latency` — Demo: local min/mean/max with a "not provider-performance evidence"
  note; OpenAI: p50 / p95 by documented nearest-rank (`sorted[ceil(q/100 * n) - 1]`)
- `## Human review` — "Semantic rubric status: not reviewed in this automated run."
  + link to `eval/rubric.md`
- `## Interpretation boundary` — fixed note: passing deterministic invariants does not
  establish semantic correctness, faithfulness, usefulness, or absence of unsupported
  inference; those require the human rubric

Artifacts are timestamped `YYYYMMDDTHHMMSSZ` (UTC) and never overwrite. Both are
written completely before a non-zero exit.

## 11. Automated grader tests

`python -m unittest discover -s eval/tests -p 'test_*.py'` — **60 tests, all pass**
(§13.B). Coverage:

- **Corpus** (`test_corpus.py`): real 27-case corpus validates; duplicate `case_id`;
  unknown check; unknown termset; unknown marker; `risk_level` property; `max_count`;
  inline `forbidden_terms`; per-case termset `mode` override; duplicate `quote_text`;
  corpus size 23 and 31 rejected, 24 and 30 accepted; missing / doubled REG case;
  `regression_origin` on a non-REG case; the four category-consistency rules
  (violation rejected, satisfied accepted).
- **Graders** (`test_graders.py`): whole-word (`tire` ≠ `entire`); case-insensitive;
  phrase boundary (`good deal` ≠ `good dealer`); `absolute` hit / clean; **price
  termset does not fire on the real committed disclaimer + summary line**;
  `not_in_source` output-only fails / sourced passes / neither passes; `name_raw`
  not scanned but `explanation` is; `uncertainty_marker` pass/fail;
  `line_items_where` `min_count` pass/fail and `evidence_needed_nonempty` counting;
  `schema_valid` valid re-validates / bad payload fails; `metadata_complete` missing
  `request_id`, wrong model for mode, prompt-version mismatch.
- **Runner** (`test_run_eval.py`): `deterministic_pass` (schema fail / execution
  error / failed check ⇒ case fail); `suite_exit_code` (all pass ⇒ 0, any fail ⇒ 1,
  empty ⇒ 1); `aggregate_by_domain` / `aggregate_by_category` with a multi-category
  case counted in each; `percentile` nearest-rank; `build_summary_md` contains every
  required heading + REG rows + interpretation boundary; **route `HTTPException` and
  plain `RuntimeError` become readable `execution_error` records without aborting**;
  **paid guard: `main(["--mode","openai"])` returns 2 and never reaches `run_suite`**.

## 12. Demo baseline results

`python -m eval.run_eval --mode demo` (§13.D) — exit code **1**, artifacts written:

- `eval/results/run_20260829T105921Z.jsonl` (27 records)
- `eval/results/summary_20260829T105921Z.md`

| Metric | Value |
|---|---|
| Total cases | 27 |
| Schema passes | 27 / 27 (100.0%) |
| Deterministic invariant passes | **11 / 27 (40.7%)** |
| Execution errors | 0 |

Failing cases (16), all on `uncertainty_marker` / `line_items_where` — **zero**
`schema_valid`, `metadata_complete`, or `forbidden_terms` failures:

| Case | Domain | Failed checks |
|---|---|---|
| AUTO-001 | automotive | ambiguous_items_present, missing_quote_context |
| AUTO-004 | automotive | needs_professional_confirmation |
| CONT-001 | contractor_vendor | ambiguous_items_present |
| CONT-003 | contractor_vendor | missing_quote_context |
| CONT-004 | contractor_vendor | missing_quote_context |
| CONT-005 | contractor_vendor | needs_professional_confirmation |
| ELEC-001 | electronics_repair | ambiguous_items_present, missing_quote_context |
| ELEC-002 | electronics_repair | missing_quote_context |
| GEN-001 | generic_service | ambiguous_items_present |
| HOME-001 | plumbing_home | ambiguous_items_present |
| HOME-002 | plumbing_home | missing_quote_context, line_items_where:vague_or_confusing |
| HOME-003 | plumbing_home | needs_professional_confirmation |
| HVAC-001 | hvac_appliance | ambiguous_items_present, missing_quote_context |
| HVAC-002 | hvac_appliance | line_items_where:vague_or_confusing |
| REG-001 | hvac_appliance | needs_professional_confirmation |
| REG-002 | hvac_appliance | missing_quote_context |

Passing (11): AUTO-002, AUTO-003, AUTO-005, CONT-002, ELEC-003, ELEC-004, GEN-002,
GEN-003, GEN-004, HOME-004, HVAC-003.

These are the QC-3A-predicted Demo-mode gaps: `stub_analyzer.py` hardcodes
`ambiguous_items_present = true` (all six `clean_itemized` cases fail), derives
`missing_quote_context` from a fixed phrase list, sets
`needs_professional_confirmation` only on `red` / `safety_critical` items, and falls
through to a single "needs clarification" item for domains outside its keyword list
(HOME-002, HVAC-002 lose the `vague_or_confusing` line). They are **retained, not
xfailed or excluded**. No application code was changed after seeing them.

## 13. Historical regression status

Both regression guards are **live and currently FAIL in Demo mode**, for a reason
that is not the regression they guard:

- **REG-001** (HVAC → vehicle/mechanic leakage): `forbidden_terms:vehicle_domain`
  **passes** — the Demo output invents no vehicle vocabulary, which is the property
  the case exists to protect. It fails only `uncertainty_marker:
  needs_professional_confirmation` (stub does not flag the compressor work as needing
  professional confirmation).
- **REG-002** (unsupported price judgment): `forbidden_terms:price_judgment` **passes**
  and `forbidden_terms:vehicle_domain` **passes** — no market-fairness phrase, no
  vehicle framing. It fails only `uncertainty_marker:missing_quote_context` (stub
  does not set it despite the quote providing no diagnostic basis).

So the leakage / price-judgment invariants themselves hold in Demo mode today; the
red rows are the same marker gaps as the rest of the corpus. Recorded, not hidden.

## 14. Acceptance-criteria table

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Corpus loads + permanently validated; malformed spec fails before inference | PASS | §5; §13.C; `test_corpus.py` |
| 2 | Graders implement exactly the QC-3A vocabulary in use; speculative shapes rejected | PASS | §6; §7; `test_corpus.py` (risk_level/max_count/inline/mode rejected) |
| 3 | `forbidden_terms` honours termset `mode` + whole-word/phrase; `name_raw` excluded | PASS | §7; `test_graders.py` |
| 4 | Independent Pydantic `schema_valid` (not a metadata read) | PASS | §6; `test_graders.SchemaValidTests` |
| 5 | `metadata_complete` checks real provenance vs the running app; `prompt_version` not hardcoded | PASS | §6; `test_graders.MetadataCompleteTests` |
| 6 | Every assertion emits an interpretable result | PASS | §6; §9; sample record in §13.D |
| 7 | One failing case does not abort; malformed corpus does | PASS | §3; §13.D (16 fail, run completes); `run_suite` returns 2 on `CorpusError` |
| 8 | Corpus size validated to [24, 30]; REG-001/REG-002 once each | PASS | §5; §13.C; `test_corpus` size + REG tests |
| 9 | Demo = zero OpenAI calls; `--mode openai` w/o `--allow-paid` exits before inference; no paid run | PASS | §8; §13.F; `test_run_eval.PaidModeGuardTests` |
| 10 | Timestamped JSONL + Markdown written, never overwriting; non-zero exit after writing on failure | PASS | §13.D; artifacts `run_/summary_20260829T105921Z` |
| 11 | Summary: total/schema/deterministic rates, failures by domain + category, REG status, human-review boundary | PASS | §10; §13.D |
| 12 | First Demo baseline committed even with failures | PASS (staged, not committed) | `eval/results/run_20260829T105921Z.jsonl` + `.md` present |
| 13 | Eval-harness unit tests pass (stdlib unittest) | PASS | §13.B — 60 tests OK |
| 14 | README links the real baseline without overstating; CURRENT_STATE records manual semantic eval | PASS | `README.md` Evaluation section; `docs/CURRENT_STATE.md` "Added in QC-3B" |
| 15 | No backend/frontend/examples change; no corpus expectation change; nothing committed | PASS | §17; §13.G scope check empty |

## 15. Exact validation commands

```bash
python -m compileall eval
python -m unittest discover -s eval/tests -p 'test_*.py' -v
python -m eval.run_eval --validate-only
python -m eval.run_eval --mode demo
python -m eval.run_eval --mode demo --case-id REG-001 --case-id REG-002
python -m eval.run_eval --mode openai
git status --short
git diff --stat
git diff --check
git status --short -- backend/ frontend/ examples/
```

(Run inside the project's `quotecheck` conda env — Python 3.11, `pydantic 2.12.5`,
matching `backend/requirements.txt`.)

## 16. Exact results

### 16.A `python -m compileall eval`

```
(no output — success; exit 0)
```

### 16.B `python -m unittest discover -s eval/tests -p 'test_*.py'`

```
............................................................
----------------------------------------------------------------------
Ran 60 tests in 0.095s

OK
```

### 16.C `python -m eval.run_eval --validate-only`  (exit 0)

```
[1] JSON parse            : 27/27 case files parsed
[2] case_id uniqueness    : 27 unique / 27 cases
[3] domain values         : all valid — ['automotive', 'contractor_vendor', 'electronics_repair', 'generic_service', 'hvac_appliance', 'plumbing_home']
[4] category values       : all valid — ['clean_itemized', 'conditional_work', 'cross_domain_trap', 'missing_scope_or_quantity', 'noisy_input', 'price_present', 'professional_confirmation_expected', 'professional_confirmation_not_expected', 'vague_bundled_charge']
[5] corpus size           : 27 (required 24-30)
[6] REG-001 / REG-002     : 1 / 1 occurrence(s)
[7] quote_text uniqueness : 27 distinct
[8] check vocabulary      : ['forbidden_terms', 'line_items_where', 'uncertainty_marker']
[9] termsets resolve      : ['price_judgment', 'trade_domain', 'vehicle_domain']
[10] termset mode source  : ok (mode only in termsets.json; no per-case override)
[11] category consistency : enforced (clean_itemized, professional_confirmation_*, cross_domain_trap)

OK — 27 cases, 6 domains, 9 categories, 0 errors.
```

### 16.D `python -m eval.run_eval --mode demo`  (exit 1)

```
Wrote /home/akshay/dev/projects/quotecheck-v0/eval/results/run_20260829T105921Z.jsonl
Wrote /home/akshay/dev/projects/quotecheck-v0/eval/results/summary_20260829T105921Z.md
27/27 schema-valid; 11/27 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation (known Demo-mode gaps are retained, not suppressed).
```

Artifact reconciliation (from `run_20260829T105921Z.jsonl`):

```
records: 27
schema_pass 27/27  deterministic_pass 11/27  exec_errors 0
  automotive           5 cases, 3 pass, 2 fail
  contractor_vendor    5 cases, 1 pass, 4 fail
  electronics_repair   4 cases, 2 pass, 2 fail
  generic_service      4 cases, 3 pass, 1 fail
  hvac_appliance       5 cases, 1 pass, 4 fail
  plumbing_home        4 cases, 1 pass, 3 fail
  REG-001 deterministic_pass=False failed=['uncertainty_marker:needs_professional_confirmation']
  REG-002 deterministic_pass=False failed=['uncertainty_marker:missing_quote_context']
```

These domain counts match the `## Failures by domain` table in
`summary_20260829T105921Z.md` exactly; the REG rows match its `## Historical
regressions` section.

Sample per-case check result (first record, `check_results[0]`):

```json
{
  "check": "schema_valid",
  "label": "schema_valid",
  "passed": true,
  "expected": "validates against QuoteCheckResult",
  "observed": "valid",
  "message": "response independently re-validates against QuoteCheckResult",
  "detail": {}
}
```

### 16.E `python -m eval.run_eval --mode demo --case-id REG-001 --case-id REG-002`  (exit 1)

```
Wrote .../regrun/run_20260829T110407Z.jsonl
Wrote .../regrun/summary_20260829T110407Z.md
2/2 schema-valid; 0/2 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation (known Demo-mode gaps are retained, not suppressed).
```

(written to a scratch `--results-dir`; not committed.)

### 16.F `python -m eval.run_eval --mode openai`  (exit 2, no `--allow-paid`)

```
Refusing to run OpenAI mode without --allow-paid.
`--mode openai` makes one billed OpenAI API call per selected case. Re-run with
`--mode openai --allow-paid` to authorize billed inference. No API call was made.
```

No `backend.app` import, no OpenAI client, no network. `--mode openai --allow-paid`
was **not** run.

### 16.G scope checks

```
$ git diff --check
(clean)

$ git status --short -- backend/ frontend/ examples/
(empty)
```

## 17. Remaining limitations

- **Layer A only.** A clean deterministic run proves schema validity, metadata
  provenance, marker values, forbidden-term absence, and line-item counts — nothing
  about faithfulness, hallucination, explanation quality, usefulness, or semantic
  uncertainty calibration. `semantic_expectations` and `eval/rubric.md` are still an
  unrun manual pass.
- **The Demo baseline is 11/27 by construction.** 16 cases fail known
  `stub_analyzer.py` gaps (hardcoded `ambiguous_items_present`, fixed
  `MISSING_CONTEXT_PHRASES`, keyword fall-through). Not fixed here — QC-3B changed no
  application code.
- **`forbidden_terms` / `not_in_source` is a proxy**, and `price_judgment` is
  deliberately low-recall (QC-3A design). A clean result is not proof of absence of
  invented terminology or of price inference.
- **No OpenAI-mode evidence.** The runner supports `--mode openai --allow-paid` and a
  latency p50/p95 report, but no paid run was made, so there is no OpenAI baseline.
- **No CI.** The runner is not wired into any automation.
- **`risk_level` correctness is uncovered.** `line_items_where` supports only
  `vague_or_confusing` / `evidence_needed_nonempty`; no case asserts a risk
  distribution.
- **Latency in Demo mode is local wall-clock** (≈0 ms) and is labelled as not
  provider-performance evidence.

## 18. `git status --short`

```
 M README.md
 M docs/CURRENT_STATE.md
 M eval/README.md
?? docs/tickets/QC-3B-eval-runner.md
?? docs/review/REVIEW_BUNDLE__QC-3B-eval-runner.md
?? eval/__init__.py
?? eval/corpus.py
?? eval/graders.py
?? eval/results/
?? eval/run_eval.py
?? eval/tests/
```

## 19. `git diff --stat`

```
 README.md             |  46 ++++++++++-----
 docs/CURRENT_STATE.md |  70 +++++++++++++++++++++--
 eval/README.md        | 151 +++++++++++++++++++++++++++++++++++++-------------
 3 files changed, 212 insertions(+), 55 deletions(-)
```

(Tracked-file changes are docs only. New code lands as untracked `eval/*.py`,
`eval/tests/`, `eval/results/`. `backend/`, `frontend/`, `examples/`, `SPEC.md`,
`eval/cases/**`, `eval/termsets.json`, `eval/rubric.md` untouched.)

## Definition of done

- All 15 acceptance criteria met (§14), each with real evidence.
- Deterministic runner, permanent corpus validation, zero-cost Demo mode, explicit
  paid boundary, JSONL + Markdown artifacts, and the first (failing) Demo baseline
  all exist.
- 60 stdlib `unittest` tests pass.
- Docs (`eval/README.md`, `README.md`, `docs/CURRENT_STATE.md`) updated truthfully;
  semantic evaluation is stated as still manual.
- No application / example / corpus / dependency change.
- **Not committed** — left for the user to review and commit manually.
