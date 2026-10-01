# SCALE-006 — Final Scalability Recharacterization + QuoteCheck v1 Closure

Risk class: **T1 — closure verification and documentation.** No application, test, harness, frontend, dependency or deployment change unless verification exposes a real defect, and then only by a separate corrective ticket.

Branch: `task/SCALE-006-final-scalability-v1-closure`, created from `v1/scalability` @ `0e039ca` (the SCALE-005 merge). It merges back into `v1/scalability`, never `main`.

Verification budget: **₹0**. No OpenAI credential, no paid evaluation, no contact with the public deployment.

## 1. Goal

Close QuoteCheck v1 on evidence:

1. verify the exact final v1 code;
2. bind the SCALE-005 runtime contract to that code with one small fresh admission smoke check;
3. consolidate SCALE-001–005 into one evidence-backed v1 scalability story;
4. synchronize public and current-state documentation;
5. audit claims and limitations;
6. decide Gate F (v1 closure).

This is a closure task, not an architecture phase.

## 2. Context

- SCALE-001–005 are complete. Gate D (SCALE-004) and Gate E (SCALE-005) passed.
- SCALE-005 changed documentation only. It recommended a minimum SCALE-006 scope (contract §8), including a quick admission smoke check. Reason: SCALE-004's evidence is bound to the admission backend only by attestation, because its `env.json` recorded `git_dirty: true` and no backend hashes.
- `PROJECT_STATUS.md` still cites "~144" tests and says nothing about capacity, overload or the cost boundary.

## 3. Scope

1. **Final regression** on the tip under test:
   - the full unit suite (report the actual count);
   - `python -m eval.run_eval --validate-only`;
   - `python -m eval.run_eval --mode demo` (generated `eval/results/` output removed afterwards);
   - frontend `npm run lint` and `npm run build`;
   - a zero-cost local Demo backend smoke (`/health`, `/analyze`).
2. **One admission smoke check:** `python -m benchmarks.run_capacity --quick --experiment admission --gate-cap 32`, with its run directory in a scratch location outside the repository. Only a compact summary is recorded, in the closure document and the review bundle.
3. `docs/scalability/SCALE-006_V1_CLOSURE.md`: the SCALE-001–005 story, the final runtime contract, the cost boundary, the local operating envelope, accepted limitations, and Decision Gate F.
4. Truth sync, only where stale: `docs/PROJECT_STATUS.md`, `docs/CURRENT_STATE.md`, `README.md`, `CLAUDE.md`.
5. The review bundle.

## 4. Non-goals

- Any new scalability mechanism: rate limiting, `Retry-After`, a configurable budget, metrics, token or cost logging, an output-token cap, queueing, workers or replicas, cross-process coordination, an async OpenAI path.
- Re-running the full SCALE-004 matrix, open-arrival load, an invalid-request flood, or any paid OpenAI run.
- Committing request-level traces, health-load traces, server logs or temporary run directories.
- Merging to `main`, tagging, releasing, deploying, or deleting branches. These wait for explicit user approval of the closure report.
- Fixing a defect found during verification inside this ticket (see §7).

## 5. Acceptance criteria

1. The unit suite, corpus validation, Demo eval (27/27 schema-valid; 24/27 with `AUTO-004`, `CONT-003`, `HVAC-003`), frontend lint and build, and the Demo smoke all pass on `0e039ca`. The actual counts are reported.
2. The admission smoke runs against a clean tree at `0e039ca` and shows, at the points it exercises:
   - peak provider in-flight ≤ 32;
   - excess requests get 503 `capacity_exceeded`;
   - rejected requests make zero provider calls (QuoteCheck log and fake provider);
   - admitted requests complete;
   - retries make exactly 2 attempts inside the cap;
   - every trial is reconciled and attempt-joined.
3. Every scalability claim in the closure document traces to accepted SCALE-001–004 evidence, an enforcing test, the SCALE-005 contract, or the SCALE-006 smoke.
4. Public docs state capacity, overload and cost at SCALE-005 strength. They make no production-scale, SLA, OpenAI-capacity or unqualified cost-bound claim.
5. Every limitation is explicitly accepted for v1 or has an existing SCALE-005 revisit trigger.
6. `git diff --check` is clean. The diff is documentation only. No `eval/results/`, benchmark bulk, secret, dependency or deployment change is present. Provider spend is ₹0.

## 6. Required evidence

- `docs/scalability/SCALE-006_V1_CLOSURE.md`, with Decision Gate F.
- The review bundle, with the exact commands and real outputs.

## 7. Stop condition

If any regression, contract check or smoke check reveals a real runtime defect: **stop**. Classify it as a closure blocker or a documented non-blocking limitation. Do not fix it inside SCALE-006. For a blocker, propose the smallest corrective ticket separately.
