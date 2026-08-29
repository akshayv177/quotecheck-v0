# QC-3B — Executable deterministic eval / regression harness

## 1. Goal

Build a repository-native executable runner for the QC-3A case corpus that:

1. loads and **permanently** validates the 27-case corpus before any inference;
2. runs each selected case through the real QuoteCheck analysis path;
3. re-validates each response against `QuoteCheckResult` independently;
4. applies **only** the deterministic (Layer A) checks defined by QC-3A;
5. records an interpretable per-case result for every assertion;
6. writes a timestamped JSONL run artifact and a readable Markdown summary;
7. exits non-zero when any selected case fails deterministic evaluation;
8. runs the whole suite at zero API cost in Demo mode;
9. gates OpenAI mode behind an explicit `--allow-paid` flag so no billed inference
   happens by accident.

This ticket implements **Layer A only**. It does not score semantics, does not
measure model quality, and must not present a Layer A pass rate as an accuracy or
correctness number. Layer B stays human, against `eval/rubric.md`.

## 2. Context

QC-3A produced the evaluation specification (`eval/README.md`), the human rubric
(`eval/rubric.md`), the shared forbidden-term sets (`eval/termsets.json`), and 27
synthetic cases under `eval/cases/`, including two permanent regression cases —
REG-001 (HVAC → vehicle/mechanic domain leakage) and REG-002 (unsupported
market-price / fairness judgment). QC-3A deliberately did **not** write a runner;
it used a throwaway validator that was never committed.

The corpus targets the intended product contract, not the Demo stub's keyword
heuristics, so Demo mode fails some cases by construction (most visibly the six
`clean_itemized` cases, because `stub_analyzer.py` hardcodes
`ambiguous_items_present = true`). Those failures are real, already-documented
product gaps and are retained as signal — not xfailed, suppressed, or excluded from
denominators.

## 3. Strict file scope

Allowed to create:

- `eval/__init__.py`, `eval/corpus.py`, `eval/graders.py`, `eval/run_eval.py`
- `eval/tests/__init__.py`, `eval/tests/support.py`, `eval/tests/test_corpus.py`,
  `eval/tests/test_graders.py`, `eval/tests/test_run_eval.py`
- `eval/results/run_<UTC>.jsonl`, `eval/results/summary_<UTC>.md` (committed Demo
  baseline)
- `docs/tickets/QC-3B-eval-runner.md`, `docs/review/REVIEW_BUNDLE__QC-3B-eval-runner.md`

Allowed to edit:

- `eval/README.md` — extend with runner usage; trim the check vocabulary to exactly
  what the runner implements
- `README.md` — Evaluation section (truthful), repo tree, Roadmap, Limitations bullet
- `docs/CURRENT_STATE.md` — "Last updated" line, Gaps, Commands, `### Added in QC-3B`

Not touched:

- `backend/**`, `frontend/**`, `examples/**`
- `eval/cases/**`, `eval/termsets.json`, `eval/rubric.md`
- `SPEC.md`, dependency/deployment files, historical ticket/review documents

No new dependencies. Standard library plus the existing Pydantic/FastAPI stack.

## 4. Out of scope

Semantic / Layer B auto-scoring; any machine reading of `semantic_expectations`; an
LLM judge; CI wiring; changes to analyzer or schema behaviour; schema-repair /
retry loops; `NormalizedCategory` redesign; a PII detector in the runner (the
corpus is synthetic); latency/cost benchmarking as a quality claim; a paid OpenAI
run during this ticket; any git commit.

## 5. Acceptance criteria

1. The 27-case corpus can be loaded and permanently validated; unknown or malformed
   eval specification fails before inference.
2. Deterministic graders implement exactly the QC-3A vocabulary in use
   (`forbidden_terms` via shared termset, `uncertainty_marker`, `line_items_where`
   over `vague_or_confusing` / `evidence_needed_nonempty`) plus the global
   invariants `schema_valid`, `metadata_complete`, and the `price_judgment` guard.
   `topic_present`, `line_items_where` `risk_level` / `max_count`, inline
   `forbidden_terms`, per-case termset `mode`, and `all_text` are neither
   implemented nor documented; a case using any of them fails corpus validation.
3. `forbidden_terms` honours the termset's own `mode` (`absolute` /
   `not_in_source`) and matches case-insensitively on whole words / phrases, never
   substrings; `name_raw` is excluded from the scanned text.
4. Schema validity is checked with an independent `QuoteCheckResult.model_validate`,
   not by reading `metadata.schema_valid`.
5. `metadata_complete` checks real returned metadata and provenance against the
   running application (`DEMO_ANALYZER_MODEL` / configured `QUOTECHECK_MODEL`;
   `prompt_version` compared to `backend.core.prompt.PROMPT_VERSION`, not hardcoded).
6. Every deterministic assertion emits an interpretable result (check, passed,
   expected, observed, message).
7. One failing case does not abort the suite; a malformed corpus does abort before
   any analyzer call.
8. Corpus size is validated to the QC-3A range [24, 30] inclusive (hard failure
   outside it), and REG-001 / REG-002 each appear exactly once.
9. Demo mode runs with zero OpenAI calls. `--mode openai` without `--allow-paid`
   exits before the application / analyzer execution path runs — no `analyze` call,
   no OpenAI client, no billed inference. No paid run is performed in this ticket.
10. The runner writes `eval/results/run_<UTC>.jsonl` and
    `eval/results/summary_<UTC>.md`, never overwriting, and exits non-zero after
    writing both if deterministic failures exist.
11. The summary reports total / schema / deterministic rates, failures by domain and
    by category (a multi-category case counted in each), explicit REG-001 / REG-002
    status, a human-review boundary statement, and a fixed interpretation-boundary
    note.
12. The first complete Demo baseline is committed even though it contains failures.
13. Eval-harness unit tests pass under stdlib `unittest`.
14. `README.md` links the real latest baseline without overstating what it proves;
    `docs/CURRENT_STATE.md` records executable deterministic evaluation with
    semantic evaluation still manual.
15. No `backend/` / `frontend/` / `examples/` change; no corpus expectation change;
    nothing committed.

## 6. Commands to run

```bash
# A. syntax
python -m compileall eval

# B. harness self-tests
python -m unittest discover -s eval/tests -p 'test_*.py' -v

# C. corpus validation only (no analyzer, no network)
python -m eval.run_eval --validate-only

# D. Demo baseline (expected: non-zero exit; artifacts still written)
python -m eval.run_eval --mode demo

# E. cheap regression-only rerun
python -m eval.run_eval --mode demo --case-id REG-001 --case-id REG-002

# F. paid-mode guard (expected: exit before inference, no OpenAI call)
python -m eval.run_eval --mode openai

# G. scope
git status --short
git diff --stat
git diff --check
git status --short -- backend/ frontend/ examples/   # must be empty
```

## 7. Definition of done

- All acceptance criteria met, each evidenced in
  `docs/review/REVIEW_BUNDLE__QC-3B-eval-runner.md` with real command output — no
  placeholders.
- `eval/README.md`, `README.md`, and `docs/CURRENT_STATE.md` (including its "Last
  updated" line) reflect that a deterministic runner exists and that semantic
  evaluation remains manual.
- The first Demo baseline (`run_<UTC>.jsonl` + `summary_<UTC>.md`) is committed with
  its real, failing numbers.
- No application, example, corpus, or dependency change.
- Not committed — left for the user to review and commit manually.
