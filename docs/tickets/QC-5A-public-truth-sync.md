# QC-5A — Public truth sync

## 1. Goal

Remove the stale public-document contradictions the QC-5 final public inspection
identified, so the repo's public docs stop disagreeing with the committed eval
baseline and the live deployment.

Documentation-only. No application code, frontend, backend, `railpack.json`,
dependency, schema, prompt, Demo-analyzer, eval-corpus, eval-results, or
deployment configuration change. No product or architecture redesign. No commit.

Closes **QC5-01 (P1)** and **QC5-02 (P2)**; folds in the **QC5-04 (P2)**
housekeeping item. CI (**QC5-09**) is a separate later ticket (QC-5B).

## 2. Context

`docs/review/REVIEW_BUNDLE__QC-5-final-public-inspection.md` reached a
**READY WITH MINOR REPAIRS** verdict. No P0. The live product works and matches
its observable behaviour; what holds it back from a clean READY is documentation
truthfulness, not code. The three findings this ticket addresses:

- **QC5-01 (P1)** — `docs/PROJECT_STATUS.md`, which the README explicitly
  nominates as the honest "public-ready vs. still limited" summary, still says
  "No automated test suite, eval harness, or CI" and "No verified public
  deployment", and lists "a verified public deployment" under *Planned hardening
  (not yet built)*. All false since QC-3B/QC-3C and QC-2B. A skeptical reader
  who follows the README's own pointer lands on a document that contradicts the
  README.
- **QC5-02 (P2)** — `eval/README.md` "Expected Demo-mode behaviour" claims
  `ambiguous_items_present` is hardcoded `true` and the six `clean_itemized`
  cases will fail, contradicting the "Latest committed Demo baseline" section
  lower in the same file.
- **QC5-04 (P2)** — `docs/design/UI_REDESIGN_PLAN.md` is a stale
  pre-implementation plan (keeps the removed "v0 prototype" chip; references the
  old "55s" client timeout).

Verified current state (from the QC-5 bundle §3–§4, re-verified there
2026-08-31; the runner/harness reproduce exactly against current code):

- `python -m unittest discover -s eval/tests -p 'test_*.py'` → **Ran 144 tests … OK**.
- `python -m eval.run_eval --validate-only` → **OK — 27 cases**.
- `python -m eval.run_eval --mode demo` → **27/27 schema-valid; 24/27
  deterministic cases pass**; failed set **AUTO-004, CONT-003, HVAC-003**;
  identical to the committed QC-3C baseline
  `eval/results/summary_20260829T115912Z.md`; exits non-zero by design.
- `stub_analyzer.py` (QC-3C): `ambiguous_items_present =
  any(item.vague_or_confusing for item in line_items)` — derived, not hardcoded.
- Live frontend `https://quotecheck-frontend.vercel.app` → HTTP 200.
- Live backend `https://quotecheck-v0-production.up.railway.app` → `/health`
  `{"status":"ok"}`; observed `/analyze` provenance
  `metadata.model == "quotecheck-demo-analyzer"`,
  `prompt_version == "quotecheck_v0.4"`, `schema_valid == true`.

The Railway environment (`QUOTECHECK_USE_OPENAI`, `OPENAI_API_KEY`) was **not**
inspected by QC-5 or this ticket; hosted-mode wording rests on observed runtime
provenance only, and setup guidance stays visibly separate from observed
evidence.

## 3. Strict file scope

Allowed to edit:

- `docs/PROJECT_STATUS.md` — move the eval harness / runner / ~144 harness tests
  and the provenance-verified public Vercel + Railway Demo deployment into
  *What's public-ready*; drop the "No verified public deployment" limit; narrow
  the "no test suite / eval harness / CI" limit to the true residual (semantic
  Layer B is manual; no CI); reword *Planned hardening* to drop "a verified
  public deployment" and add the CI item; keep every genuine limit visible; add
  no production claim.
- `eval/README.md` — the "Expected Demo-mode behaviour" section only. Remove the
  "`ambiguous_items_present` hardcoded `true`" / "six `clean_itemized` cases will
  fail" claims; state the marker is derived (QC-3C), the `clean_itemized` cases
  pass, the baseline is 24/27 deterministic / 27/27 schema-valid, and the three
  residuals are `AUTO-004`, `CONT-003`, `HVAC-003`.
- `docs/CURRENT_STATE.md` — `Last updated` line and a concise `### Added in
  QC-5A` changelog entry.
- `docs/design/UI_REDESIGN_PLAN.md` — prepend a short "historical
  pre-implementation plan" header; body unchanged.

Allowed to create:

- `docs/tickets/QC-5A-public-truth-sync.md`
- `docs/review/REVIEW_BUNDLE__QC-5A-public-truth-sync.md`

Never touch: `README.md` (unless a concrete *new* contradiction is discovered —
then stop and flag first), `SPEC.md`, `CLAUDE.md`, `backend/**`, `frontend/**`,
`eval/` corpus / `results/` / `graders.py` / `run_eval.py` / `corpus.py` /
`tests/` / `rubric.md` / `termsets.json`, `examples/**`, `railpack.json`,
dependency files, deployment configuration, and any historical ticket/review
document. The `### Fixed in …` / `### Added in …` changelog blocks in
`docs/CURRENT_STATE.md` are historical and stay unchanged except for adding the
new `### Added in QC-5A` entry.

No new dependencies.

## 4. Out of scope

Repository-level CI (`.github/workflows/**`) — that is QC-5B (**QC5-09**). The
QC-5 ticket file already exists on this branch's history (**QC5-03**). P3
cosmetics — favicon / stray `vite.svg` (**QC5-06**), "(v0)" module docstrings
(**QC5-07**), `docs/CURRENT_STATE.md` length (**QC5-08**). Any runtime,
schema, prompt, analyzer, eval-corpus, eval-results, dependency, or deployment
change. Any commit or merge.

## 5. Acceptance criteria

1. `docs/PROJECT_STATUS.md` no longer contains "No automated test suite, eval
   harness, or CI" or "No verified public deployment", and no longer lists "a
   verified public deployment" under *Planned hardening*.
2. `docs/PROJECT_STATUS.md` *What's public-ready* names the deterministic eval
   runner + 27-case corpus, the ~144 stdlib harness tests, and the live Vercel +
   Railway Demo deployment, with hosted mode described from observed provenance
   (`metadata.model == "quotecheck-demo-analyzer"`), not an environment claim.
3. `docs/PROJECT_STATUS.md` keeps visible: semantic Layer B grading is manual;
   no CI; hosted logs are ephemeral; no public rate limiting; not
   production-ready / production-grade. No new production claim is introduced.
4. `eval/README.md` "Expected Demo-mode behaviour" no longer says
   `ambiguous_items_present` is hardcoded `true` or that the six `clean_itemized`
   cases fail; it states the marker is derived, the `clean_itemized` cases pass,
   the baseline is 24/27 deterministic / 27/27 schema-valid, and the residuals
   are `AUTO-004`, `CONT-003`, `HVAC-003`. It is consistent with the "Latest
   committed Demo baseline" section below it.
5. No file under `eval/` other than `eval/README.md` is modified; the corpus,
   `results/`, `rubric.md`, `termsets.json`, graders, and runner are byte-identical.
6. `docs/CURRENT_STATE.md` has `Last updated: 2026-09-01 (QC-5A)` and a short
   `### Added in QC-5A` entry recording the repair and stating no runtime change;
   no other section is modified.
7. `docs/design/UI_REDESIGN_PLAN.md` opens with a clear header marking it a
   historical pre-implementation plan superseded by the shipped UI; its §1–§10
   body is unchanged.
8. No source-code, config, dependency, or deployment file changed;
   `git diff` of `backend/ frontend/ eval/cases eval/results eval/graders.py
   eval/run_eval.py eval/corpus.py eval/tests eval/rubric.md eval/termsets.json
   railpack.json` is empty.
9. `git diff --check` is clean; `git status --short` shows only the four edited
   docs plus the two new files.
10. Nothing committed — left for the user to review and commit manually.

## 6. Commands to run

```bash
# protected paths untouched
git diff -- backend frontend examples railpack.json \
  eval/cases eval/results eval/graders.py eval/run_eval.py eval/corpus.py \
  eval/tests eval/rubric.md eval/termsets.json README.md SPEC.md CLAUDE.md   # expect empty

git diff --check
git status --short
git diff --stat

# stale-phrase sweep over the repaired files
git grep -n -i "No automated test suite"       -- docs/PROJECT_STATUS.md eval/README.md docs/CURRENT_STATE.md docs/design/UI_REDESIGN_PLAN.md || true
git grep -n -i "No verified public deployment" -- docs/PROJECT_STATUS.md eval/README.md docs/CURRENT_STATE.md docs/design/UI_REDESIGN_PLAN.md || true
git grep -n -i "hardcoded .true"               -- docs/PROJECT_STATUS.md eval/README.md || true
git grep -n -i "six .clean_itemized"           -- docs/PROJECT_STATUS.md eval/README.md || true
git grep -n    "55s"                            -- docs/PROJECT_STATUS.md eval/README.md docs/design/UI_REDESIGN_PLAN.md || true
git grep -n -i "v0 prototype"                   -- docs/PROJECT_STATUS.md eval/README.md docs/design/UI_REDESIGN_PLAN.md || true

# runtime unchanged (cheap, no paid calls; requires a Python env with backend/requirements.txt)
python -m eval.run_eval --validate-only
python -m unittest discover -s eval/tests -p 'test_*.py'
```

Interpret grep output manually: `docs/PROJECT_STATUS.md` and `eval/README.md`
must have **zero** hits for the stale claims; `docs/design/UI_REDESIGN_PLAN.md`
still contains "55s" / "v0 prototype" in its historical body, which is acceptable
only because the new header labels the whole file historical;
`docs/CURRENT_STATE.md` historical `### …` blocks may still carry these phrases
as dated changelog record.

## 7. Definition of done

- All acceptance criteria met, each evidenced in
  `docs/review/REVIEW_BUNDLE__QC-5A-public-truth-sync.md` with exact commands and
  real output — no placeholders.
- `docs/CURRENT_STATE.md` `Last updated` line reflects QC-5A.
- No source code, examples, logs, eval corpus/results, dependency, or deployment
  change. No historical ticket/review document rewritten.
- Nothing committed — left for the user to review and commit manually. QC-5B not
  started.
