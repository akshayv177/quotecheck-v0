# Review bundle — QC-5A — Public truth sync

## 1. Ticket / phase

`docs/tickets/QC-5A-public-truth-sync.md`. Phase QC-5 (final public
inspection) repair series — the first of the repair tickets the QC-5 bundle
(`docs/review/REVIEW_BUNDLE__QC-5-final-public-inspection.md` §13) proposes.
Branch `task/QC-5A-public-truth-sync` (based on `main` @ `6ebb7da`).
**Nothing committed.**

Closes **QC5-01 (P1)** and **QC5-02 (P2)**; folds in **QC5-04 (P2)**. CI
(**QC5-09**, → QC-5B) is out of scope.

## 2. Scope summary

Documentation-only truth-sync. Four docs edited, two governance files created:

- `docs/PROJECT_STATUS.md` — the eval harness + runner + ~144 harness tests and
  the provenance-verified live Vercel + Railway Demo deployment moved into
  *What's public-ready*; the false "No automated test suite, eval harness, or
  CI" and "No verified public deployment" limits removed / narrowed to the true
  residual; *Planned hardening* reworded (dropped "a verified public
  deployment", added CI). No production claim added.
- `eval/README.md` — the "Expected Demo-mode behaviour" section repaired to
  match the committed QC-3C baseline (derived `ambiguous_items_present`;
  `clean_itemized` passes; 24/27 deterministic / 27/27 schema-valid; residuals
  `AUTO-004`, `CONT-003`, `HVAC-003`).
- `docs/CURRENT_STATE.md` — `Last updated` line + a concise `### Added in QC-5A`
  changelog entry.
- `docs/design/UI_REDESIGN_PLAN.md` — a short header marking it a historical
  pre-implementation plan; body untouched.

**Not touched:** `README.md`, `SPEC.md`, `CLAUDE.md`, `backend/**`,
`frontend/**`, `examples/**`, `railpack.json`, dependency files, deployment
configuration, and every file under `eval/` except `eval/README.md` (corpus,
`results/`, `graders.py`, `run_eval.py`, `corpus.py`, `tests/`, `rubric.md`,
`termsets.json`). No historical `### …` changelog block in
`docs/CURRENT_STATE.md` was rewritten. No dependency added. No runtime, schema,
prompt (`PROMPT_VERSION` stays `quotecheck_v0.4`), analyzer, eval-corpus,
eval-results, or deployment change.

## 3. Files changed

Created:

- `docs/tickets/QC-5A-public-truth-sync.md`
- `docs/review/REVIEW_BUNDLE__QC-5A-public-truth-sync.md` (this file)

Edited:

| File | Change |
|---|---|
| `docs/PROJECT_STATUS.md` | *What's public-ready*: +3 bullets (deterministic eval + regression harness with the committed 24/27 · 27/27 baseline and the two regression cases; ~144 stdlib harness tests; live Vercel + Railway Demo deployment described from **observed** `metadata.model` provenance, with "OpenAI mode … was not the path observed"). *What's still limited*: "No automated test suite, eval harness, or CI" → "Semantic grading is still manual, and there is no CI" (Layer A runner + harness tests exist; Layer B is human; nothing on push/PR); new "portfolio Demo, not a service" bullet (no scale/uptime, no durable/centralized logging, no rate limiting; observed hosted path is the Demo analyzer); deleted "No verified public deployment". *Planned hardening*: "Automated eval / regression harness with scored semantic checks" → "Scored semantic (Layer B) checks — the deterministic Layer A harness exists"; +"CI wiring … on push / PR (QC-5B)"; deleted "A verified public deployment"; "A verified public deployment" line replaced by a rate-limiting / durable-logging line. |
| `eval/README.md` | "Expected Demo-mode behaviour" section only. Removed "`ambiguous_items_present` is hardcoded `true`, so the six `clean_itemized` cases will fail". New paragraph: since QC-3C the marker is **derived** (`any(item.vague_or_confusing …)`), the six `clean_itemized` cases now **pass**, committed baseline **27/27 schema-valid, 24/27 deterministic**, residuals `AUTO-004` / `CONT-003` / `HVAC-003`. The divergence bullets rewritten to name the 3 residual cases and their cause. Framing sentence, the "per mode / not xfailed / not tuned down" bullets, and every other section unchanged. |
| `docs/CURRENT_STATE.md` | `Last updated: 2026-08-31 (QC-2B)` → `2026-09-01 (QC-5A)`; new `### Added in QC-5A` entry inserted at the top of the changelog (after `## Gaps`, before `### Added in QC-2B`). No other line changed. |
| `docs/design/UI_REDESIGN_PLAN.md` | One blockquote header added directly under the H1: labels the file a historical pre-implementation plan, names the shipped UI (LUXURY-UI-001 / 001A) as the superseding source, calls out the removed "v0 prototype" chip and the "55s" → 70s (QC-4) timeout as examples not to treat as current, points current behaviour at the implementation / README / CURRENT_STATE. §1–§10 body byte-unchanged. |

No file under `backend/`, `frontend/`, `examples/`, `eval/` (bar
`eval/README.md`), and no `railpack.json` / `README.md` / `SPEC.md` /
`CLAUDE.md` / dependency file appears in the diff (§6, protected-paths diff is
empty).

## 4. Findings addressed

### QC5-01 (P1) — `docs/PROJECT_STATUS.md` stale, under-sells the project

| Was (removed) | Now |
|---|---|
| *What's still limited* → "**No automated test suite, eval harness, or CI.** The `examples/` pack is a manually curated sample set, not scored evaluation." | *What's still limited* → "**Semantic grading is still manual, and there is no CI.** The deterministic Layer A eval runner and the ~144 stdlib harness tests exist and run, but Layer B … is a human pass against `eval/rubric.md`, and nothing runs automatically on push or PR." |
| *What's still limited* → "**No verified public deployment.**" | deleted; *What's public-ready* now has "**Live public Demo deployment.** … verified end-to-end … The observed public hosted path executed through the deterministic Demo analyzer (`metadata.model == "quotecheck-demo-analyzer"` …)." |
| *Planned hardening* → "Automated eval / regression harness with scored semantic checks." | "Scored semantic (Layer B) checks — the deterministic Layer A harness exists; only the semantic scoring is future work." |
| *Planned hardening* → "A verified public deployment." | deleted; replaced by "Public rate limiting / quota control and durable, centralized logging — required before OpenAI mode could ever be exposed anonymously." + "CI wiring that runs the existing verification commands on push / PR (QC-5B)." |

Genuine limits kept visible: narrow taxonomy / Demo heuristics; keyword matching
not language understanding; no price benchmarking; no PDF/OCR; no auth/DB; no
lockfile; **semantic Layer B manual + no CI**; **portfolio Demo, not a service —
no scale/uptime, no durable/centralized logging, ephemeral hosted logs, no rate
limiting**; no repair/retry; no vendor verification. "What should not be
overclaimed" (incl. "not a production-ready system") is unchanged. No
production-grade / production-ready claim was introduced.

Hosted-mode wording follows the user's approved constraint: observed runtime
provenance only (`metadata.model`), **not** "Railway has `QUOTECHECK_USE_OPENAI=0`"
or "`OPENAI_API_KEY` is unset" — the Railway environment was not inspected by
QC-5 or QC-5A.

### QC5-02 (P2) — `eval/README.md` "Expected Demo-mode behaviour" self-contradiction

| Was (removed) | Now |
|---|---|
| "`ambiguous_items_present` is hardcoded `true`, so the six `clean_itemized` cases will fail their `ambiguous_items_present == false` assertion in Demo mode" | "Since QC-3C, `ambiguous_items_present` is **derived** from line-item ambiguity (`any(item.vague_or_confusing for item in line_items)`), not hardcoded `true`, so the six `clean_itemized` cases now **pass** … The committed Demo baseline is **27/27 schema-valid, 24/27 deterministic cases pass**, with exactly the three residuals … (`AUTO-004`, `CONT-003`, `HVAC-003`)." |
| "`missing_quote_context` … will disagree with cases whose missing context is real but differently worded" (unnamed) | Same point, now naming `AUTO-004` and its cause (symptom-only safety recommendation, no explicit deferred-detail phrasing). |
| — | New bullet: the coarse one-item-per-domain analyzer cannot flag conditional uncertainty confined to one sub-line → `CONT-003`, `HVAC-003`. |

Now consistent with the "Latest committed Demo baseline" section lower in the
same file (`results/summary_20260829T115912Z.md`, 24/27). The corpus, rubric,
termsets, results, graders, runner, and every other section of `eval/README.md`
are untouched. The eval design is not rewritten.

### QC5-04 (P2) — `docs/design/UI_REDESIGN_PLAN.md` stale pre-implementation plan

A blockquote header now labels the whole file historical and names the specific
stale examples ("v0 prototype" chip, "55s" timeout) that must not be read as
current. The historical body is intact — the header, not deletion, resolves the
finding, as the QC-5 bundle's recommended action allowed.

## 5. Acceptance-criteria table

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `PROJECT_STATUS.md` drops "No automated test suite…" / "No verified public deployment" / *Planned hardening* "a verified public deployment" | ✓ | §6 grep sweep — 0 hits in `PROJECT_STATUS.md`; §3 diff |
| 2 | `PROJECT_STATUS.md` *public-ready* names the eval runner + corpus, ~144 harness tests, live deployment; hosted mode from observed provenance | ✓ | §3 diff (3 new bullets); §4 QC5-01 |
| 3 | Genuine residual limits + non-production stance kept visible; no new production claim | ✓ | §4 QC5-01 (limits list); "What should not be overclaimed" unchanged in §3 diff |
| 4 | `eval/README.md` "Expected Demo-mode behaviour" corrected; consistent with the baseline section below it | ✓ | §3 diff; §4 QC5-02; §6 `--mode demo` = 24/27, residuals AUTO-004/CONT-003/HVAC-003 |
| 5 | No `eval/` file other than `eval/README.md` modified | ✓ | §6 `git status --short eval/` → only `eval/README.md`; protected-paths diff empty |
| 6 | `CURRENT_STATE.md` has `Last updated: 2026-09-01 (QC-5A)` + short `### Added in QC-5A`; nothing else changed | ✓ | §3 diff (only line 3 + inserted block) |
| 7 | `UI_REDESIGN_PLAN.md` opens with a historical-plan header; §1–§10 body unchanged | ✓ | §3 diff (only a +9-line header, 0 deletions) |
| 8 | No source / config / dependency / deployment file changed; protected-paths `git diff` empty | ✓ | §6 protected-paths diff → empty |
| 9 | `git diff --check` clean; `git status --short` = 4 edited docs + 2 new files | ✓ | §6 |
| 10 | Nothing committed | ✓ | §6 `git status` shows working-tree changes only; no commit made |

## 6. Exact commands / results

Environment: conda env `quotecheck`, Python 3.11.14, repo root
`/home/akshay/dev/projects/quotecheck-v0`, branch `task/QC-5A-public-truth-sync`.

### 6.1 git state

```
$ git status --short
 M docs/CURRENT_STATE.md
 M docs/PROJECT_STATUS.md
 M docs/design/UI_REDESIGN_PLAN.md
 M eval/README.md
?? docs/tickets/QC-5A-public-truth-sync.md
?? docs/review/REVIEW_BUNDLE__QC-5A-public-truth-sync.md

$ git diff --stat
 docs/CURRENT_STATE.md           | 40 +++++++++++++++++++++++++++++++++++++++-
 docs/PROJECT_STATUS.md          | 38 +++++++++++++++++++++++++++++++++-----
 docs/design/UI_REDESIGN_PLAN.md |  9 +++++++++
 eval/README.md                  | 24 ++++++++++++++++++------
 4 files changed, 99 insertions(+), 12 deletions(-)

$ git diff --check
(no output — clean)

$ git diff -- backend frontend examples railpack.json \
    eval/cases eval/results eval/graders.py eval/run_eval.py eval/corpus.py \
    eval/tests eval/rubric.md eval/termsets.json README.md SPEC.md CLAUDE.md
(no output — protected paths untouched)

$ git status --short eval/
 M eval/README.md
```

(`docs/review/REVIEW_BUNDLE__QC-5A-public-truth-sync.md` shows as `??` once this
file is written; the `git diff --stat` above was captured before it existed.)

### 6.2 Stale-phrase sweep over the repaired files

```
$ git grep -n -i "No automated test suite"       -- docs/PROJECT_STATUS.md eval/README.md docs/CURRENT_STATE.md docs/design/UI_REDESIGN_PLAN.md
(no hits)

$ git grep -n -i "No verified public deployment" -- docs/PROJECT_STATUS.md eval/README.md docs/CURRENT_STATE.md docs/design/UI_REDESIGN_PLAN.md
docs/CURRENT_STATE.md:468:Remaining after QC-2A: no verified public deployment yet; no public URL yet; no
docs/CURRENT_STATE.md:801:  OpenAI-path and screenshot facts; added "no verified public deployment" and vendor

$ git grep -n -i "hardcoded .true"               -- docs/PROJECT_STATUS.md eval/README.md
eval/README.md:319:(`any(item.vague_or_confusing for item in line_items)`), not hardcoded `true`, so the six

$ git grep -n -i "six .clean_itemized"           -- docs/PROJECT_STATUS.md eval/README.md
(no hits — the phrase now wraps across lines 319–320)

$ git grep -n "55s"                              -- docs/PROJECT_STATUS.md eval/README.md docs/design/UI_REDESIGN_PLAN.md
docs/design/UI_REDESIGN_PLAN.md:6:>   "v0 prototype" chip described below was removed, and the "55s" client timeout
docs/design/UI_REDESIGN_PLAN.md:24:  error copy, 55s client timeout, Demo/OpenAI mode badge.

$ git grep -n -i "v0 prototype"                  -- docs/PROJECT_STATUS.md eval/README.md docs/design/UI_REDESIGN_PLAN.md
docs/design/UI_REDESIGN_PLAN.md:6:>   "v0 prototype" chip described below was removed, and the "55s" client timeout
docs/design/UI_REDESIGN_PLAN.md:69:  "v0 prototype" chip, and the one-line purpose sentence — establishing the tool
```

**Interpretation.**

- `docs/PROJECT_STATUS.md` — **zero** hits for every stale phrase. Repaired.
- `eval/README.md` —
  - `six clean_itemized`: zero line-matched hits. The phrase survives only
    line-wrapped across 319–320 inside "the six `clean_itemized` cases now
    **pass**" — a *passing* assertion consistent with the committed baseline,
    not the old failure prediction.
  - `hardcoded .true`: the one hit is the corrected sentence itself —
    "…**not** hardcoded `true`…". Correct.
- `docs/design/UI_REDESIGN_PLAN.md` — `55s` and `v0 prototype` still appear in
  the historical body (lines 24 / 69) and in the new header (line 6, which
  quotes them precisely to warn the reader off). Acceptable: the file now opens
  with a header labelling the whole document historical and superseded, which is
  exactly the QC-5 finding's recommended remedy.
- `docs/CURRENT_STATE.md` — two "no verified public deployment" hits, both
  inside dated historical changelog blocks (`### Added in QC-2A` line 468 —
  true at QC-2A; `### Fixed in QC-1A` line 801 — a record of what QC-1A wrote).
  Not current-state assertions; left as historical record per the ticket scope.

### 6.3 Runtime unchanged (no paid calls)

```
$ python -m eval.run_eval --validate-only
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
# exit 0

$ python -m unittest discover -s eval/tests -p 'test_*.py'
................................................................................................................................................
----------------------------------------------------------------------
Ran 144 tests in 1.044s

OK
# exit 0

$ python -m eval.run_eval --mode demo --results-dir <scratch>   # artifacts to a scratch dir, NOT eval/results
Wrote <scratch>/run_20260901T042526Z.jsonl
Wrote <scratch>/summary_20260901T042526Z.md
27/27 schema-valid; 24/27 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation (known Demo-mode gaps are retained, not suppressed).
# exit 1 (by design)

# scratch summary — failed cases:
#   ### AUTO-004 (automotive)
#   ### CONT-003 (contractor_vendor)
#   ### HVAC-003 (hvac_appliance)
# Deterministic invariant passes: 24/27 (88.9%)

$ git status --short eval/results/
(no output — eval/results/ untouched; the run wrote only to the scratch dir)
```

The 144-test harness, the corpus validation, and the Demo baseline (27/27
schema-valid, 24/27 deterministic, residuals `AUTO-004` / `CONT-003` /
`HVAC-003`) reproduce **exactly** the committed QC-3C baseline
(`eval/results/summary_20260829T115912Z.md`) and the QC-5 inspection's §4.4
figures — confirming the prose edits changed no behaviour.

## 7. Remaining limitations

Unchanged by this ticket, still true, still disclosed:

- Semantic (Layer B) grading against `eval/rubric.md` is a manual human pass.
- No repository-level CI — nothing runs on push / PR. **This is QC-5B (QC5-09).**
- Hosted `logs/app_runs.jsonl` is local and ephemeral; no durable or centralized
  observability.
- No public rate limiting / quota control; OpenAI mode is not exposed by the
  public demo (observed hosted path is the Demo analyzer).
- The Railway environment was not inspected; hosted-mode statements rest on
  observed runtime provenance only.
- The 3 deterministic Demo residuals (`AUTO-004`, `CONT-003`, `HVAC-003`) remain
  documented, not chased.
- Nothing is production-grade / production-ready, and no document claims
  otherwise.

## 8. git status / diff stat

```
$ git status --short
 M docs/CURRENT_STATE.md
 M docs/PROJECT_STATUS.md
 M docs/design/UI_REDESIGN_PLAN.md
 M eval/README.md
?? docs/review/REVIEW_BUNDLE__QC-5A-public-truth-sync.md
?? docs/tickets/QC-5A-public-truth-sync.md

$ git diff --stat
 docs/CURRENT_STATE.md           | 40 +++++++++++++++++++++++++++++++++++++++-
 docs/PROJECT_STATUS.md          | 38 +++++++++++++++++++++++++++++++++-----
 docs/design/UI_REDESIGN_PLAN.md |  9 +++++++++
 eval/README.md                  | 24 ++++++++++++++++++------
 4 files changed, 99 insertions(+), 12 deletions(-)

$ git diff --check
(clean)
```

Nothing has been committed — left for the user to review and commit manually.
QC-5B (minimal CI) has not been started.
