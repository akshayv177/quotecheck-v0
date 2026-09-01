# Review Bundle — QC-5B Minimal CI

## Ticket / phase / branch

- **Ticket:** `docs/tickets/QC-5B-minimal-ci.md`
- **Phase:** QC-5B — Minimal CI (final engineering repair before QuoteCheck v0 closure)
- **Branch:** `task/QC-5B-minimal-ci` (based on `main` @ `2ff1cff`)
- **Date:** 2026-09-01
- **Commit status:** nothing committed, merged, pushed, or tagged.

## Scope summary

Add one small GitHub Actions workflow that runs QuoteCheck's **existing**
verification surface automatically on pull requests and pushes to `main`:

- `backend-eval` job — the ~144 stdlib `unittest` tests, corpus validation, and a
  Demo-eval step that asserts the accepted baseline exactly.
- `frontend` job — the existing `npm ci` / `npm run lint` / `npm run build`.

No new tests, no new evaluation system, no dependency change, no deployment
automation, no paid inference, no application/runtime behaviour change. Three
documentation files were updated to correct now-stale "there is no CI / nothing
runs on push or PR" wording, using deliberately conservative phrasing ("is
configured to run …") because no live GitHub Actions run has happened yet.

## Files changed

| File | Status | Change |
|---|---|---|
| `.github/workflows/ci.yml` | new | The workflow (2 jobs). |
| `docs/tickets/QC-5B-minimal-ci.md` | new | Ticket. |
| `docs/review/REVIEW_BUNDLE__QC-5B-minimal-ci.md` | new | This bundle. |
| `README.md` | modified | Limitations bullet: "nothing runs on push or PR yet" → workflow is configured to run Layer A + harness + frontend lint/build on PR / push to `main`. Evaluation section: one sentence noting CI asserts the accepted baseline exactly. |
| `docs/PROJECT_STATUS.md` | modified | "still limited" CI bullet rewritten (minimal CI configured, no deploy, no paid inference, Layer B still manual); "Planned hardening" line reworded from "CI wiring (QC-5B)" to "deeper CI than the QC-5B minimal workflow". |
| `docs/CURRENT_STATE.md` | modified | `Last updated` → `2026-09-01 (QC-5B)`; new `### Added in QC-5B` block; "No CI" gap bullet → "Minimal CI (QC-5B)". |

`git diff --stat` (tracked):

```
 README.md              | 10 ++++++++--
 docs/CURRENT_STATE.md  | 48 ++++++++++++++++++++++++++++++++++++++++++------
 docs/PROJECT_STATUS.md | 17 ++++++++++++-----
 3 files changed, 62 insertions(+), 13 deletions(-)
```

Untracked: `.github/` (contains only `workflows/ci.yml`),
`docs/tickets/QC-5B-minimal-ci.md`.

No file under `backend/**`, `frontend/**`, `eval/**`, `examples/**`, and no
`railpack.json`, `SPEC.md`, `CLAUDE.md`, `backend/requirements.txt`,
`frontend/package.json`, or `frontend/package-lock.json` was modified.

## CI architecture

```
QuoteCheck CI  (.github/workflows/ci.yml)
├── on: pull_request  +  push → main
├── permissions: contents: read          (no write scope; no secrets referenced)
├── concurrency: cancel superseded runs on the same ref
│
├── job: backend-eval   (ubuntu-latest, Python 3.11, env QUOTECHECK_USE_OPENAI=0)
│   1. actions/checkout@v4
│   2. actions/setup-python@v5   (python-version 3.11)
│   3. python -m pip install -r backend/requirements.txt      (no pip self-upgrade)
│   4. python -m unittest discover -s eval/tests -p 'test_*.py'
│   5. python -m eval.run_eval --validate-only
│   6. Demo eval — accepted-baseline gate:
│        run the existing runner into  $(mktemp -d)  (never eval/results/)
│        capture its (by-design non-zero) exit code
│        stdlib-Python parse of the scratch run_*.jsonl, assert the exact baseline
│
└── job: frontend        (ubuntu-latest, working-directory: frontend)
    1. actions/checkout@v4
    2. actions/setup-node@v4   (node-version 22, cache: npm, key: frontend/package-lock.json)
    3. npm ci
    4. npm run lint
    5. npm run build
```

Only official first-party actions (`actions/checkout@v4`,
`actions/setup-python@v5`, `actions/setup-node@v4`). No third-party actions. No
artifact upload. No deploy step. No `npm audit` gate.

## Trigger configuration

```yaml
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
```

- `pull_request` — every PR, any base branch.
- `push` — only `main`.
- Least privilege: `contents: read`. No job requests write scope; no
  `secrets.*` / `secrets:` token appears anywhere in the file (asserted in
  verification).

## Backend / eval job

- **Runtime:** Python 3.11 (`actions/setup-python@v5`). Matches the Railway
  runtime pin and the local conda env used for verification.
- **Dependencies:** `python -m pip install -r backend/requirements.txt` only —
  `fastapi==0.128.6`, `uvicorn==0.40.0`, `pydantic==2.12.5`, `openai==2.24.0`,
  `python-dotenv==1.2.1`. No `pip install --upgrade pip`, no added package, no
  lockfile.
- **Determinism / cost:** job-level `env: QUOTECHECK_USE_OPENAI: "0"`. No
  `OPENAI_API_KEY` and no other provider credential is provided anywhere in the
  workflow, so the OpenAI path is unreachable from CI. `backend.core.config`
  freezes `USE_OPENAI` from the environment at import; the Demo (stub) analyzer
  is selected.
- **Commands:** the existing, unchanged verification commands —
  `python -m unittest discover -s eval/tests -p 'test_*.py'` and
  `python -m eval.run_eval --validate-only`.
- **Baseline gate:** see next section.

## Frontend job

- **Runtime:** Node 22 (current LTS). The project declares no `engines` in
  `frontend/package.json` or `frontend/package-lock.json`; Vite 7 requires Node
  `^20.19.0 || >=22.12.0`, and React 19 + ESLint 9 are satisfied on 22. The
  developer machine's Node 24 is deliberately **not** pinned — the project does
  not require 24.
- **Caching:** `actions/setup-node@v4` with `cache: npm` and
  `cache-dependency-path: frontend/package-lock.json` (the committed
  lockfile, `lockfileVersion 3`).
- **Working directory:** `frontend` (via `defaults.run.working-directory`).
- **Commands:** the existing, unchanged `npm ci` / `npm run lint`
  (`eslint .`) / `npm run build` (`vite build`). `npm audit` is not run as a
  gate.

## Exact accepted-baseline strategy

**Problem.** The accepted Demo baseline is 27/27 schema-valid, 24/27
deterministic, with exactly `AUTO-004` / `CONT-003` / `HVAC-003` failing by
design; `python -m eval.run_eval --mode demo` therefore exits non-zero on a
healthy repo. A required raw `--mode demo` step would fail every CI run; a
`--mode demo || true` step would let an arbitrary future regression (e.g. 10/27)
pass.

**Does the existing `unittest` suite already gate this?** No. Inspected in full:

- `eval/tests/test_stub_analyzer.py` pins *individual* QC-3C analyzer behaviours
  with short synthetic quotes — it never loads the 27-case corpus and never
  asserts a corpus-level pass count.
- `eval/tests/test_corpus.py` validates corpus *structure* only (27 files load,
  REG-001/REG-002 once, enum/shape rules); no analyzer call.
- `eval/tests/test_run_eval.py` tests pure reporting/exit-code helpers against
  hand-built `CaseResult` objects; no real corpus, no real analyzer.
- `grep -rn 'AUTO-004|CONT-003|HVAC-003|24/27' eval/tests/` → no matches.

So a regression that made a *fourth* case fail, or a *different* case fail
instead of one of the three, would pass the entire `unittest` suite. The suite
is a necessary regression gate for the machinery and named behaviours, but not
sufficient as the accepted-baseline gate.

**Minimal additional mechanism (inside the allowed workflow file, no other new
code).** `eval/**` and `backend/**` are out of scope, so no new test file is
added there. The Demo-eval CI step:

1. runs `python -m eval.run_eval --mode demo --results-dir "$SCRATCH"` where
   `$SCRATCH="$(mktemp -d)"` — never `eval/results/`;
2. records the runner's exit code (`set +e` around the call, then `set -e`);
3. parses the machine-readable `run_<UTC>.jsonl` the runner just wrote, with the
   **standard library only** (`glob`, `json`, `os`, `sys`), and asserts **all**
   of:
   - exactly **27** case records;
   - `schema_pass` true for exactly **27**;
   - `deterministic_pass` true for exactly **24**;
   - `{case_id : deterministic_pass is false}` is exactly
     `{"AUTO-004", "CONT-003", "HVAC-003"}`;
   - **zero** records with `execution_error`;
   - the runner exited **non-zero** (the by-design "residuals remain" signal);
4. exits 0 only if every assertion holds; `sys.exit(<message>)` (non-zero,
   failing the CI step) for **any** other outcome — a 4th failure, a different
   failure, a vanished residual, a suddenly-green run, or a runner crash.

This reads the runner's own structured output; it does not re-implement grading,
touch the runner or corpus, xfail anything, or change the residual set. It is
neither blanket suppression nor a required raw non-zero command.

## Commands run (local verification)

Environment: conda env `quotecheck`, Python 3.11.14; Node v24.14.1 / npm 11.11.0
for the frontend (CI itself pins Node 22).

### 1. Harness self-tests

```
$ python -m unittest discover -s eval/tests -p 'test_*.py'
................................................................................................................................................
----------------------------------------------------------------------
Ran 144 tests in 0.983s

OK
```

### 2. Corpus validation

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
```

### 3. Demo baseline — the exact `ci.yml` step body, executed under bash

The Demo-eval `run:` block was extracted from the parsed workflow and executed
verbatim (only the interpreter is the conda `python`; `--results-dir` is a
scratch dir):

```
Demo eval -> /tmp/tmp.Mwmw4YwVo5 (the runner exits non-zero by design: 3 accepted residuals)

Wrote /tmp/tmp.Mwmw4YwVo5/run_20260901T051445Z.jsonl
Wrote /tmp/tmp.Mwmw4YwVo5/summary_20260901T051445Z.md
27/27 schema-valid; 24/27 deterministic cases pass.
Exit non-zero: one or more selected cases failed deterministic evaluation (known Demo-mode gaps are retained, not suppressed).
runner exit code: 1
cases=27 schema_valid=27 deterministic_pass=24 failing=['AUTO-004', 'CONT-003', 'HVAC-003'] runner_rc=1
Accepted Demo baseline intact: 27/27 schema-valid, 24/27 deterministic, residuals AUTO-004 / CONT-003 / HVAC-003.
STEP EXIT: 0  (0 = baseline gate passed)
```

**Exact failure IDs:** `AUTO-004`, `CONT-003`, `HVAC-003`
(`AUTO-004` — `uncertainty_marker:missing_quote_context` expected True, observed
False; `CONT-003` and `HVAC-003` — `uncertainty_marker:ambiguous_items_present`
expected True, observed False). Identical to
`eval/results/summary_20260829T115912Z.md`.

`eval/results/` after the run:

```
$ git status --short eval/results/
(clean — no output)
```

### 4. Negative control — the gate fails on a regression

The scratch `run_*.jsonl` was tampered to mark `GEN-001` as an additional
failure (simulating a 4th regression), then re-parsed with the gate script:

```
cases=27 schema_valid=27 deterministic_pass=23 failing=['AUTO-004', 'CONT-003', 'GEN-001', 'HVAC-003'] runner_rc=1
ACCEPTED DEMO BASELINE VIOLATED:
  - deterministic passes 23 != 24
  - failing set ['AUTO-004', 'CONT-003', 'GEN-001', 'HVAC-003'] != ['AUTO-004', 'CONT-003', 'HVAC-003']
negative-case parser exit: 1 (expect non-zero)
```

### 5. Frontend

```
$ cd frontend && npm ci
...
12 vulnerabilities (2 low, 1 moderate, 9 high)     # informational npm output; audit is NOT a CI gate

$ npm run lint
> frontend@0.0.0 lint
> eslint .
                                                  # clean, no findings

$ npm run build
> frontend@0.0.0 build
> vite build
vite v7.3.1 building client environment for production...
✓ 29 modules transformed.
dist/index.html                   0.44 kB │ gzip:  0.30 kB
dist/assets/index-DsGHRHoV.css    8.93 kB │ gzip:  2.49 kB
dist/assets/index-BoTkB8Wo.js   202.28 kB │ gzip: 63.69 kB
✓ built in 661ms
```

`node_modules/` and `frontend/dist/` are gitignored — no repo change from the
frontend build.

### 6. Workflow validation

Parsed `.github/workflows/ci.yml` with PyYAML 6.0.3, handling the YAML 1.1 gotcha
where a bare `on:` key is remapped to boolean `True` (GitHub's own parser is
YAML 1.2 and keeps it the string `on`; the local check accepts either):

```
top-level keys (note: PyYAML 1.1 maps bare `on:` -> True): ['name', True, 'permissions', 'concurrency', 'jobs']
triggers: {'pull_request': None, 'push': {'branches': ['main']}}
backend-eval uses: ['actions/checkout@v4', 'actions/setup-python@v5']
frontend uses: ['actions/checkout@v4', 'actions/setup-node@v4']

ALL WORKFLOW STRUCTURE ASSERTIONS PASSED
```

Assertions that passed: `name == "QuoteCheck CI"`; trigger key present with
`pull_request` and `push.branches == ["main"]`; `permissions == {contents: read}`;
jobs are exactly `{backend-eval, frontend}`; `backend-eval.env.QUOTECHECK_USE_OPENAI
== "0"`; `setup-python` `python-version == "3.11"`; `setup-node` `node-version ==
"22"`, `cache == "npm"`; `frontend` working directory `frontend`; only
`actions/*` actions used; the strings `secrets.` and `secrets:` appear nowhere
in the file.

The embedded heredoc Python body was extracted after YAML block-scalar dedent
and `ast.parse`d successfully; the `<<'PY'` terminator sits at column 0 after
dedent (required for a quoted heredoc). A full bash execution of the step body
(section 3) confirms the dedent, the exit-code capture, and the gate all behave.

Manual read of the final file was also performed.

### 7. Scope

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
 M docs/PROJECT_STATUS.md
?? .github/
?? docs/tickets/QC-5B-minimal-ci.md

$ git diff --stat
 README.md              | 10 ++++++++--
 docs/CURRENT_STATE.md  | 48 ++++++++++++++++++++++++++++++++++++++++++------
 docs/PROJECT_STATUS.md | 17 ++++++++++++-----
 3 files changed, 62 insertions(+), 13 deletions(-)

$ git diff --check
(no output — no whitespace errors)

$ find .github -type f
.github/workflows/ci.yml
```

(The review bundle file itself adds a fourth untracked path,
`docs/review/REVIEW_BUNDLE__QC-5B-minimal-ci.md`, once written.)

## Security / cost notes

- **Least privilege:** `permissions: contents: read`. No job needs or requests
  write scope (no release, no comment, no push).
- **No secrets:** the workflow references no `secrets.*` and defines no `secrets:`
  — verified by string search. There is nothing for a forked-PR run to exfiltrate.
- **No paid inference reachable:** `backend-eval` sets `QUOTECHECK_USE_OPENAI=0`
  and never sets `OPENAI_API_KEY`; the Demo (stub) analyzer does zero network
  I/O. `eval.run_eval` also has its own `--mode openai` cost guard, unused here.
- **`concurrency`** only cancels superseded runs on the same ref — no security or
  cost implication beyond saving compute.
- **Supply chain:** only pinned first-party `actions/*@vN`. No third-party action.
- **Artifacts:** none uploaded, so no run output is published.

## Dependency changes

None. `backend/requirements.txt`, `frontend/package.json`, and
`frontend/package-lock.json` are untouched. No `pip install --upgrade pip`. No
new Python or npm package. The workflow installs exactly the committed pinned
sets.

## Deployment changes

None. The workflow has no deploy job, no Vercel/Railway step, no environment
promotion, no `railpack.json` reference. The existing public deployment is
unaffected and out of scope.

## Acceptance criteria

### Implementation-pass

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `.github/workflows/ci.yml` exists, name `QuoteCheck CI` | ✅ | `find .github -type f`; YAML validation |
| 2 | Triggers on PR and pushes to `main` | ✅ | `triggers: {pull_request: None, push: {branches: [main]}}` |
| 3 | `permissions: contents: read` only | ✅ | YAML validation |
| 4 | Python 3.11 backend/eval job | ✅ | `setup-python` `python-version == "3.11"` |
| 5 | Deps from `backend/requirements.txt`, no pip self-upgrade | ✅ | step body `python -m pip install -r backend/requirements.txt` |
| 6 | Runs `unittest discover` + `run_eval --validate-only` | ✅ | steps 4–5; local runs §1–2 |
| 7 | Demo baseline protected without masking arbitrary regressions | ✅ | gate design + negative control §4 |
| 8 | Exact gate: 27 records, 27 schema-valid, 24 deterministic, `{AUTO-004,CONT-003,HVAC-003}`, 0 exec errors, runner non-zero | ✅ | §3 output; script in `ci.yml` |
| 9 | Frontend job runs `npm ci` / `lint` / `build` in `frontend/`, Node 22, npm cache | ✅ | YAML validation; local run §5 |
| 10 | No provider secret, no paid inference | ✅ | `QUOTECHECK_USE_OPENAI=0`; no `secrets` token |
| 11 | No deployment automation | ✅ | no deploy step in file |
| 12 | No artifact upload, no `npm audit` gate | ✅ | file inspection |
| 13 | Only official `actions/*` actions, pinned | ✅ | `uses` lists in YAML validation |
| 14 | 144 tests still pass locally | ✅ | §1 |
| 15 | Corpus validates locally | ✅ | §2 |
| 16 | Demo baseline reproduces (27/27, 24/27, 3 residuals); `eval/results/` unchanged | ✅ | §3 |
| 17 | Frontend lint/build pass locally | ✅ | §5 |
| 18 | `README.md` "nothing runs on push/PR" wording corrected, conservatively | ✅ | `git diff README.md` |
| 19 | `docs/PROJECT_STATUS.md` reflects CI, conservatively | ✅ | `git diff docs/PROJECT_STATUS.md` |
| 20 | `docs/CURRENT_STATE.md` records QC-5B (`Last updated` + `### Added in QC-5B`) | ✅ | `git diff docs/CURRENT_STATE.md` |
| 21 | No application/runtime behaviour change | ✅ | no `backend/**` `frontend/**` `eval/**` file touched |
| 22 | No dependency change | ✅ | see *Dependency changes* |
| 23 | Review bundle has real evidence, no placeholders | ✅ | this document |
| 24 | Nothing committed or merged | ✅ | `git status` shows an uncommitted working tree |

### Pending — required for final ticket closure

| # | Criterion | Status |
|---|---|---|
| E1 | A successful first GitHub Actions run of `QuoteCheck CI` after the user pushes the branch / opens a PR | ⏳ PENDING EXTERNAL VERIFICATION |

## Risks / follow-ups

- **GitHub verification boundary.** Local checks establish that the workflow YAML
  is well-formed, the trigger/permission config is correct, and every command it
  runs passes locally with the baseline protected. They cannot establish that
  GitHub's scheduler, runners, action versions, and network behave — that is E1,
  the first live run after push. Until E1 is green, QC-5B stays open and the docs
  say "is configured to run", not "runs".
- **Action major-version pinning.** Pinned to `@v4` / `@v5` tags (project norm),
  not commit SHAs. Acceptable for a portfolio repo with `contents: read` and no
  secrets; SHA-pinning + Dependabot is a possible later hardening.
- **Node 22 vs local Node 24.** CI will build on 22; a contributor on 24 could in
  principle hit a version-specific issue CI misses (or vice versa). A Node matrix
  is listed under `docs/PROJECT_STATUS.md` "Planned hardening" as deeper-CI work.
- **Baseline gate is intentionally exact.** When a future ticket legitimately
  fixes one of the three residuals, that ticket must also update the three
  constants and the residual set in `ci.yml` (and the docs) in the same change —
  the gate will (correctly) fail until it does. This is by design: the accepted
  baseline should not drift silently.
- **`concurrency` block.** Minor convenience; if a reviewer prefers the barest
  possible file it can be dropped with no functional loss.

## Explain-it-back

QuoteCheck already had a real way to check itself — 144 fast unit tests, a corpus
validator, a deterministic zero-cost "Demo" evaluation of 27 sample quotes, and
the frontend's lint + build — but a human had to remember to run all of it.
QC-5B adds a single GitHub Actions file so those same commands run by themselves
on every pull request and every push to `main`, and the result is visible.

The one non-trivial part is the Demo evaluation. On a healthy repo it *passes 24
of 27 cases and deliberately fails 3* (`AUTO-004`, `CONT-003`, `HVAC-003` — known
limits of the keyword-based Demo analyzer, kept visible rather than hidden), so
the command exits with an error on purpose. CI can't just run it and require
success (every run would fail), and it can't ignore the exit code (a real future
breakage down to 10/27 would sneak through). So the CI step runs the existing
evaluator, writes its results to a throwaway folder, and then a ~40-line
standard-library Python snippet reads those results and checks the exact shape of
the accepted state: 27 cases, 27 schema-valid, 24 passing, and precisely those
three failing — nothing more, nothing less. Anything else — a 4th failure, a
different failure, all-green, a crash — fails the build. Nothing in the evaluator
or the test suite was modified.

The frontend job just runs `npm ci`, `npm run lint`, `npm run build` on Node 22
(the current LTS; the repo doesn't require the newer Node on the dev machine).

The workflow can only read the repo (`contents: read`), holds no secrets, and
forces the free offline Demo mode, so it can never spend money on the OpenAI API
and can't deploy anything.

Docs were updated to stop saying "there is no CI", but carefully: they say the
workflow "is configured to run" these checks, because the real proof is the first
actual run on GitHub, which happens after this branch is pushed.

## Verification status

**LOCAL VERIFICATION (this pass):** workflow YAML parsed and structurally
asserted; the exact Demo-eval step body executed under bash and passed the
baseline gate; a negative control confirmed the gate fails on a simulated
regression; 144 unit tests pass; corpus validates; frontend `npm ci` / lint /
build pass; `eval/results/` unchanged; scope confined to the six allowed files.

**PENDING EXTERNAL VERIFICATION:** the first real GitHub Actions run of
`QuoteCheck CI` after the branch is pushed / a PR is opened. QC-5B is **not**
fully closed until that run succeeds; final external verification will be
recorded during release closure.

## Final git status / diff stat

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
 M docs/PROJECT_STATUS.md
?? .github/
?? docs/tickets/QC-5B-minimal-ci.md
?? docs/review/REVIEW_BUNDLE__QC-5B-minimal-ci.md

$ git diff --stat
 README.md              | 10 ++++++++--
 docs/CURRENT_STATE.md  | 48 ++++++++++++++++++++++++++++++++++++++++++------
 docs/PROJECT_STATUS.md | 17 ++++++++++++-----
 3 files changed, 62 insertions(+), 13 deletions(-)

$ git diff --check
(no output — no whitespace errors)
```

Nothing committed, merged, pushed, or tagged.
