# QC-5 — Final public inspection

## 1. Goal

Inspect QuoteCheck v0 as a skeptical external engineer / hiring manager / technical
reviewer would — landing cold on the public GitHub repository and the live demo —
and produce **one forensic inspection report** classifying anything that makes the
project look broken, misleading, stale, hard to run, poorly documented,
technically inconsistent, distractingly unfinished, weaker than the real
implementation, or stronger in its claims than the implementation supports.

QC-5 is an **inspection**, not an implementation task. It does not fix findings.

## 2. Context

Prior phases delivered the domain-neutral contract (QC-1B), the eval spec + corpus
+ deterministic runner (QC-3A/B/C), OpenAI-mode reliability hardening (QC-4),
deployment readiness (QC-2A), and the live public Demo deployment (QC-2B — Vercel
frontend + Railway backend, deterministic Demo analyzer, runtime-provenance
verified). `README.md`, `SPEC.md`, and `docs/CURRENT_STATE.md` describe the system;
`docs/PROJECT_STATUS.md` is linked from the README as the "public-ready vs. still
limited" summary.

Nothing about the public artifact had yet been inspected end to end as an outside
reader would experience it. QC-2B's own closeout explicitly named QC-5 as the next
task.

## 3. Scope

- Repository inspection: all tracked root files, `README.md`, `SPEC.md`,
  `CLAUDE.md`, `docs/**`, `backend/**`, `frontend/**`, `eval/**`, `examples/**`,
  `railpack.json`, `.gitignore` files, dependency manifests, `git` state, grep
  sweeps for stale identifiers / secrets / local-machine assumptions.
- Fresh-clone reproducibility: `git clone` the public GitHub remote into a temp
  directory and run the documented backend + frontend quickstart from scratch.
- Live product inspection: `https://quotecheck-frontend.vercel.app` and
  `https://quotecheck-v0-production.up.railway.app` — health, analyze (normal /
  vague / clean), validation errors, CORS allow + deny, unknown paths, frontend
  load.
- Engineering-evidence assessment, claim-defensibility assessment, security /
  privacy / cost hygiene, evaluation inspection, and an explicit
  automated-verification / CI axis.

## 4. Out of scope

- Fixing any finding. No edits to `README.md`, `docs/CURRENT_STATE.md`,
  `docs/PROJECT_STATUS.md`, `eval/**`, `backend/**`, `frontend/**`,
  `railpack.json`, dependencies, or deployment configuration.
- Creating repair tickets (the report proposes a grouping; the tickets themselves
  are a later step).
- Any commit or merge.
- Any browser-automation dependency; in-browser visual/mobile checks are recorded
  as human-verification items, not performed.

## 5. Acceptance criteria

1. `docs/review/REVIEW_BUNDLE__QC-5-final-public-inspection.md` exists with the
   15-section structure the QC-5 brief specifies (Executive Verdict … Final
   Closure Recommendation), containing real pasted command output — no
   placeholders.
2. The report gives one executive verdict: READY / READY WITH MINOR REPAIRS / NOT
   READY, with rationale.
3. Live-product results separate machine-verified from human-required checks.
4. Fresh-clone results record exact commands and their real output (pass or the
   actual failure).
5. Findings are listed by severity (P0–P3), each with ID / Severity / Area /
   Evidence / Why it matters / Recommended action / Repair-now YES|NO.
6. A minimal repair grouping is proposed (0–3 tiny tickets), plus explicit
   deferred / non-goal items.
7. `git status --short` after the task shows only the two new untracked files
   (this ticket + the review bundle) and nothing modified; `git diff --stat` is
   empty.
8. No repairs implemented, nothing committed, nothing merged.
