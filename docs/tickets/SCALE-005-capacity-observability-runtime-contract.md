# SCALE-005 — Capacity Observability & Runtime Contract

Risk class: **T1 — documentation and runtime contract only.** No application, test, harness, frontend, dependency or deployment change.

Branch: `task/SCALE-005-capacity-observability-runtime-contract`, created from `v1/scalability` @ `25d0ebf` (the SCALE-004 merge). It merges back into `v1/scalability`, never `main`.

Verification budget: **₹0**. No provider calls, no OpenAI credential, no new benchmark run, and no contact with the public deployment.

## 1. Goal

Determine whether QuoteCheck already exposes enough runtime state and overload semantics to make its v1 operating envelope understandable and defensible. Freeze that as an explicit, test-traceable runtime contract.

This is the last bounded hardening step before **SCALE-006 — Final Scalability Recharacterization + v1 Closure**.

## 2. Context

SCALE-004 (`docs/scalability/SCALE-004_ADMISSION.md`, Gate D passed) added per-process provider admission. It has a fixed budget of 32, fail-fast 503 `capacity_exceeded`, zero provider calls on rejection, and a retry that stays inside its slot. Gate D §E left eight open items.

The SCALE-005 assessment, approved before execution, found the following:

- Every closure-critical runtime question is already answerable from the existing API, the JSONL run log, the code, the tests, or committed evidence.
- No candidate mechanism is justified by evidence: rate limiting, `Retry-After`, a configurable budget, admission fields, metrics, token logging, queueing, workers or replicas, cross-process coordination, or an async OpenAI path.
- The accepted v1 scalability definition overclaimed cost boundedness. QuoteCheck bounds provider *concurrency* and *per-request amplification*. It does not bound *cumulative* spend over time.

The approved outcome is therefore **Outcome 1: documentation and runtime contract only.**

## 3. Scope

1. `docs/scalability/SCALE-005_RUNTIME_CONTRACT.md`, containing:
   - the sharpened v1 scalability definition;
   - the runtime contract, each claim mapped to its source location and an existing enforcing test or accepted evidence;
   - overload semantics;
   - the local operating envelope (SCALE-004 evidence only);
   - the cost and amplification contract;
   - an operator guide (questions A1–A10, JSONL field semantics, and commands validated against retained SCALE-004 logs);
   - a decision register for the 14 open candidates, each with a revisit trigger;
   - Decision Gate E, with the recommended minimum SCALE-006 scope.
2. `docs/CURRENT_STATE.md`: the date line, a "Changed in SCALE-005" section, and the `latency_ms` semantics.
3. `CLAUDE.md`: a narrow, durable pointer to the contract and the cost-claim boundary.
4. The review bundle.

## 4. Non-goals

- Any change to `backend/`, `frontend/`, `eval/`, `benchmarks/`, deployment or dependencies.
- Token or usage logging, or a `max_output_tokens` cap. Both are deferred until the first approved paid-provider exercise, or until before any public OpenAI exposure.
- Any new benchmark run or evidence directory. Operator commands are validated against the already-retained SCALE-004 raw logs.
- Rerunning the full regression suite, the Demo eval or the capacity benchmark. Those belong to SCALE-006 closure verification, because SCALE-005 changes no executable file.
- The public-doc truth sync (e.g. the `PROJECT_STATUS.md` test count). That belongs to SCALE-006.
- Reopening SCALE-001–004 decisions.

## 5. Acceptance criteria

1. Every runtime-contract claim cites its current source location and either an existing enforcing test or accepted committed evidence. No claim is uncited.
2. Every numeric operating-envelope statement matches committed SCALE-004 evidence (`report_tables.out`, `trials.jsonl`).
3. Operator commands are validated against the retained SCALE-004 raw logs, after their integrity is verified against `SCALE-004_RAW_EVIDENCE_MANIFEST.txt`. Any query the retained logs cannot exercise is documented as such.
4. Each runtime question A1–A10 is labelled OBSERVED, SUPPORTED INFERENCE or MISSING. Each intentionally unanswerable question states its scope and revisit trigger.
5. All 14 candidates are classified REQUIRED, USEFUL BUT DEFER or NOT JUSTIFIED, with evidence and a revisit trigger.
6. The cost contract states that:
   - cumulative spend is not bounded by the application;
   - the public v1 deployment runs Demo;
   - OpenAI mode is opt-in and not publicly exposed;
   - provider-account controls are external;
   - there is no `max_output_tokens` cap;
   - cost instrumentation is deferred.
7. `32 / provider latency` is described only as the idealized one-attempt ceiling, never as a guarantee. No envelope number is presented as an SLA or as an OpenAI or Railway claim.
8. `git diff --check` is clean, the diff contains documentation only, and provider spend is ₹0.

## 6. Required evidence

- `docs/scalability/SCALE-005_RUNTIME_CONTRACT.md`, with Decision Gate E.
- The review bundle, with the exact commands and real outputs: the manifest verification, the query validation and the evidence reconciliation.

## 7. Stop conditions

Stop and surface the problem, without silently adding code or tests, if any of the following happens:

- an intended contract claim is not actually enforced by a test or backed by evidence;
- code contradicts a documented claim;
- a committed evidence number disagrees with the SCALE-004 report;
- the retained raw logs fail the manifest check;
- documenting the contract would require changing `QuoteCheckResult`, the failure taxonomy, retry semantics or deployment.
