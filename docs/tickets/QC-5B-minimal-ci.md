# QC-5B — Minimal CI

## 1. Goal

Add one small GitHub Actions workflow that runs QuoteCheck's **existing**
verification surface automatically on pull requests and pushes to `main`, so the
checks that already exist become automatic and visible. Nothing else.

## 2. Context

QuoteCheck v0 already has a real verification surface:

- ~144 stdlib `unittest` tests (`python -m unittest discover -s eval/tests -p 'test_*.py'`);
- corpus validation (`python -m eval.run_eval --validate-only`);
- a deterministic, zero-cost Demo eval (`python -m eval.run_eval --mode demo`);
- frontend `npm ci` / `npm run lint` / `npm run build`.

None of it runs automatically. QC-5 (final public inspection) flagged this as
QC5-09 (P2), the last engineering repair before v0 closure, and `README.md` still
tells readers "nothing runs on push or PR yet".

The accepted Demo baseline that CI must protect honestly:

- 27/27 schema-valid;
- 24/27 deterministic cases pass;
- exact residual failures: `AUTO-004`, `CONT-003`, `HVAC-003` — retained by
  design, not xfailed or excluded from the denominator;
- the normal `python -m eval.run_eval --mode demo` command therefore exits
  non-zero.

CI must protect this without either failure mode:

- **not** a required raw `--mode demo` command (a healthy 24/27 run would fail
  every CI run);
- **not** `--mode demo || true` (an arbitrary future regression, e.g. 10/27,
  would pass).

The existing `unittest` suite pins individual analyzer behaviours and corpus
*structure*, but no existing test asserts the aggregate corpus pass count or the
exact failing set. The minimal honest gate is a shell + stdlib-Python wrapper
**inside the workflow file** that runs the existing runner into a scratch
directory and asserts the exact baseline from the runner's own `run_*.jsonl`.

## 3. Strict file scope

Allowed:

- `.github/workflows/ci.yml` — new
- `docs/PROJECT_STATUS.md`
- `docs/CURRENT_STATE.md`
- `README.md` — small CI discoverability / truth update only
- `docs/tickets/QC-5B-minimal-ci.md` — new
- `docs/review/REVIEW_BUNDLE__QC-5B-minimal-ci.md` — new

Must not be touched: `backend/**`, `frontend/**`, `eval/**`, `examples/**`,
`railpack.json`, `SPEC.md`, `CLAUDE.md`, `backend/requirements.txt`,
`frontend/package.json`, `frontend/package-lock.json`, any dependency, prompt,
schema, or deployment-configuration file.

## 4. Out of scope

- A new test project, test framework, or evaluation system.
- Deployment / release automation (the public deployment is already live).
- Dependency upgrades or lockfiles; coverage; security scanning (`npm audit` as a
  gate); refactors.
- Turning the three known residuals into xfails, or changing the residual set,
  the corpus, or the eval runner.
- Any application / runtime behaviour change.
- Claiming CI is operational on GitHub during this pass — only a live GitHub
  Actions run after push can establish that.

## 5. Acceptance criteria

Implementation-pass:

- [ ] `.github/workflows/ci.yml` exists, named `QuoteCheck CI`.
- [ ] Triggers: `pull_request` and `push` to `main`.
- [ ] `permissions: contents: read` only; no `secrets.*` reference anywhere.
- [ ] `backend-eval` job on Python 3.11; deps from `backend/requirements.txt`
      only (`python -m pip install -r backend/requirements.txt`, no pip
      self-upgrade); `QUOTECHECK_USE_OPENAI=0`; no `OPENAI_API_KEY`.
- [ ] `backend-eval` runs `python -m unittest discover -s eval/tests -p 'test_*.py'`
      and `python -m eval.run_eval --validate-only`.
- [ ] Demo-eval step runs the existing runner into a scratch `--results-dir`
      (never `eval/results/`) and asserts, from the runner's `run_*.jsonl`:
      27 records, 27 schema-valid, 24 deterministic passes, failing set exactly
      `{AUTO-004, CONT-003, HVAC-003}`, zero execution errors, runner exit
      non-zero. Any other outcome fails CI.
- [ ] `frontend` job runs `npm ci` / `npm run lint` / `npm run build` in
      `frontend/` on a stable supported Node (22 LTS), with npm caching on the
      committed lockfile.
- [ ] No artifact upload; no deploy step; no `npm audit` gate.
- [ ] 144 harness tests still pass locally; corpus validates locally; the Demo
      baseline reproduces (27/27 schema-valid, 24/27 deterministic, the exact
      three residuals) and `eval/results/` is unchanged.
- [ ] `README.md`, `docs/PROJECT_STATUS.md`, `docs/CURRENT_STATE.md` describe the
      workflow conservatively ("is configured to run …") — not as an
      externally-verified fact — and the stale "nothing runs on push or PR"
      wording is corrected.
- [ ] `docs/CURRENT_STATE.md` `Last updated` line is QC-5B / 2026-09-01 with a
      new `### Added in QC-5B` block.
- [ ] Review bundle records files changed, CI architecture, the exact
      accepted-baseline strategy, commands run with real output, and a
      LOCAL VERIFICATION vs PENDING EXTERNAL VERIFICATION split.
- [ ] Nothing committed, merged, pushed, or tagged.

Final closure additionally requires:

- [ ] A successful first GitHub Actions run after the user pushes.

## 6. Commands to run (local verification)

```bash
# backend/eval (conda env `quotecheck`, Python 3.11)
python -m unittest discover -s eval/tests -p 'test_*.py'
python -m eval.run_eval --validate-only
SCRATCH="$(mktemp -d)"
python -m eval.run_eval --mode demo --results-dir "$SCRATCH"   # exits non-zero by design
#   then parse "$SCRATCH"/run_*.jsonl and assert the accepted baseline
git status --short eval/results/                                 # must be empty

# frontend
cd frontend && npm ci && npm run lint && npm run build

# workflow + scope
python -c "..."   # YAML parse of .github/workflows/ci.yml (schema-safe for `on:`)
git status --short
git diff --stat
git diff --check
```

## 7. Definition of done

- The workflow file and all six allowed files are in place; no protected file is
  modified (`git diff --stat` / `git diff --check` confirm).
- Every underlying command passes locally, and the accepted Demo baseline is
  gated exactly — a 4th failure, a different failure, a vanished residual, a
  green run, or a crash all fail the gate locally.
- Documentation states the workflow exists and what it is configured to run,
  without asserting a GitHub run has happened.
- Ticket + review bundle committed to the branch working tree (not to git).
- Nothing committed, merged, pushed, or tagged. QC-5B stays open pending the
  first successful GitHub Actions run.
