# REVIEW BUNDLE — SCALE-004 Explicit Provider Admission Control

- **Ticket:** `docs/tickets/SCALE-004-provider-admission-control.md`
- **Report and Decision Gate D:** `docs/scalability/SCALE-004_ADMISSION.md`
- **Branch:** `task/SCALE-004-provider-admission-control`, from `v1/scalability` @ `1e7f2ed`. It merges back into `v1/scalability`, never `main`. **Nothing is committed yet.**
- **Risk class:** T3, Architecture-Sensitive Runtime Change.
- **Provider spend:** ₹0. No OpenAI credential was used and the public deployment was never contacted. No deployment configuration changed.

## Scope summary

1. **Admission.** OpenAI-mode `POST /analyze` now takes a slot from a process-local, non-blocking budget of 32 **on the event loop, before threadpool dispatch**.
   - With no slot free, the request gets an immediate `capacity_exceeded` (503, `retryable: true`), makes zero provider calls, and writes one sanitized JSONL record (`provider_attempts: 0`).
   - One slot covers the whole synchronous analysis, including the retry. It is released exactly once, when the worker thread has finished.
   - Demo mode takes no slot.
2. **Execution shape (coupled with admission).**
   - `/analyze` is an `async def` wrapper around the unchanged sync body.
   - The `QuoteCheckError` handler is `async`.
   - Response-model validation now runs on the event loop.
3. **Harness.** A new `admission` experiment (burst, sustained, health, retry) with rejection-aware accounting, and a new event-loop cost diagnostic.
4. **Evidence.** A before/after run on the same harness, fake, host and session. Report and Gate D.
5. **Eval runner adapter.** The async route broke direct route calls; this is the minimal repair.

## Files changed

| file | change |
|---|---|
| `backend/core/admission.py` (new) | `ProviderAdmission`: a lock-protected counter with `try_acquire()` (never blocks) and `release()` (raises on underflow), plus `in_flight` and `capacity`. It also defines the eager module instance `provider_admission`. |
| `backend/app.py` | `analyze` is now `async`: it takes the admission slot and, on rejection, logs the rejection and raises. `_run_admitted` releases the slot in a `finally`. The admitted task runs behind `asyncio.shield`, with `_consume_task_outcome` as its done callback. The former body moved verbatim to `_analyze_sync(req, request_id)`. `_quotecheck_error_handler` is now `async`. |
| `backend/core/config.py` | `OPENAI_MAX_CONCURRENT_ANALYSES = 32`, a fixed code constant that can't be overridden from the environment |
| `backend/core/errors.py` | `FailureCategory.CAPACITY_EXCEEDED = "capacity_exceeded"` plus its spec (503, retryable, user message) |
| `eval/run_eval.py` | `sync_route_adapter()`, which runs the async route to completion per case. `run_suite` uses it. |
| `eval/tests/test_provider_admission.py` (new) | 13 deterministic tests (below) |
| `eval/tests/test_openai_reliability.py` | One new `_ROUTE_CASES` row: `CAPACITY_EXCEEDED, 503, True` |
| `eval/tests/test_run_eval.py` | 2 adapter tests |
| `eval/tests/test_benchmarks.py` | 3 harness tests: the admission block, its absence for older records, and `LazyBodies` |
| `benchmarks/run_capacity.py` | `CAPACITY_EXCEEDED`; the `run_load(reject_backoff_s=)` option; `LazyBodies`; the `admission` option on `Run.scenario`, `_point`, `health` and `_health_point`; `run_admission`; the `adm_*` plan keys (recorded only when used); `--gate-cap`; the experiment choice `admission` |
| `benchmarks/stats.py` | `_admission_block`, whose per-trial and per-row fields appear only for `rejection_aware` trials |
| `benchmarks/diag_rejection_log.py` (new) | In-process event-loop cost of a rejection (with and without the sync log), of the log call alone, and of response-model validation |
| `benchmarks/README.md` | SCALE-004 experiment, accounting, compatibility notes and file table; "Evidence retention" policy |
| `docs/CURRENT_STATE.md` | Architecture bullets for `app.py`, `admission.py`, `errors.py` and `config.py`; a "Changed in SCALE-004" section; the date line |
| `docs/tickets/SCALE-004-provider-admission-control.md` (new) | The ticket |
| `docs/scalability/SCALE-004_ADMISSION.md` (new) | The report and Gate D |
| `benchmarks/results/SCALE-004-before/` (new; 14 MB as produced, 2.8 MB committed) | Evidence for the unmodified backend, plus `run_console.log`. Request-level/server bulk omitted from Git (see "Evidence compaction before publication"). |
| `benchmarks/results/SCALE-004-after/` (new; 205 MB as produced, 94 MB after cleanup, 1.7 MB committed) | Evidence for the admission build, plus `run_console.log`, `report_tables.py`, `report_tables.out` and `diag_rejection_log.json`. The four zero-backoff server logs were removed (see "Final cleanup"); the remaining request-level/server bulk is omitted from Git (see "Evidence compaction before publication"). |
| `CLAUDE.md` | Narrow "Current architecture facts" correction (final cleanup pass) |
| `.gitignore` | Ignores generated benchmark bulk: `benchmarks/results/*/requests.jsonl`, `*/health_load_requests.jsonl`, `*/server/` |
| `benchmarks/results/SCALE-004_RAW_EVIDENCE_MANIFEST.txt` (new) | sha256 and byte size of every omitted SCALE-004 raw file |

There are **no** frontend, deployment, dependency or `main` changes.

**New tests** (`test_provider_admission.py`):
- `test_cap_rejects_excess_immediately_with_zero_provider_calls`: the cap, fail-fast ordering while the gate is still closed, and re-admission.
- `test_rejection_needs_no_worker_token`: the anyio default limiter is fully borrowed and restored in `finally`.
- `test_transient_retry_stays_in_the_original_slot`.
- `test_every_terminal_path_releases_its_slot`, covering 10 provider and configuration outcomes.
- `test_unexpected_exception_releases_its_slot`.
- `test_cancelled_request_holds_its_slot_until_the_thread_finishes`.
- `test_demo_requests_never_touch_the_provider_budget`.
- `test_rejection_body_and_single_sanitized_log_record`.
- `test_invalid_request_is_rejected_before_admission`.
- `ProviderAdmission` unit tests:
  - accounting and underflow;
  - a 50-thread `Barrier` race on capacity 8;
  - the constant and instance;
  - the constant is below anyio's limiter.

## Acceptance criteria with evidence

| # | criterion | evidence | result |
|---|---|---|---|
| 1 | Cap, zero calls for rejections, fail-fast | `test_cap_rejects_…` (the rejection is awaited while both admitted calls are parked). Runtime: peak in-flight 32 at every after point, rejected requests have 0 attempts in both logs, and in bursts every rejection completed before the first provider call ended (25/25 trials). | ✅ |
| 2 | A rejection needs no worker token | `test_rejection_needs_no_worker_token`. The mutations (sync handler, in-thread admission) both fail it. | ✅ |
| 3 | A retry stays in one slot and is released once | The unit test; runtime shows 2.00 attempts per admitted request and peak 32 under fail-first and fail-always at C=64 | ✅ |
| 4 | Every terminal path releases; cancellation holds the slot until the thread ends | `test_every_terminal_path_…`, `test_unexpected_exception_…`, `test_cancelled_request_…`. Mutation: dropping the shield fails the last one. | ✅ |
| 5 | Demo never touches the budget | `test_demo_requests_never_touch_…` (budget 0, a `try_acquire` spy, the `OpenAI` constructor never called). Demo HTTP smoke and Demo eval are unchanged. | ✅ |
| 6 | Rejection API and log contract | `test_rejection_body_and_single_sanitized_log_record`; the `_ROUTE_CASES` row. The rejection's status, code and attempt count differ from provider 429 and 503. | ✅ |
| 7 | Before/after runtime evidence | Report §1–§5: burst, sustained, zero-backoff, health (800 probes, all 200), retry, and the event-loop cost diagnostic | ✅ |
| 8 | Regression | 201 tests OK; `--validate-only` OK; Demo 27/27 schema-valid and 24/27 passing (AUTO-004, CONT-003, HVAC-003); `stats --check` True for SCALE-001, SCALE-002 (before and after), SCALE-003, and SCALE-004 (before and after), verified against the full raw evidence before compaction | ✅ |

## Exact commands run, with real results

```bash
# conda env quotecheck (python 3.11); repo root
git checkout -b task/SCALE-004-provider-admission-control        # from v1/scalability @ 1e7f2ed

# harness first, smoke against the UNMODIFIED backend (scratchpad, not evidence)
python -m benchmarks.run_capacity --quick --experiment admission --run-id <scratch>/smoke_before
#   all admission rows reconciled + joined; stats --check True (summary + health)
for d in SCALE-001-baseline SCALE-002-before SCALE-002-after SCALE-003-saturation; do
  python -m benchmarks.stats benchmarks/results/$d --check; done                # all True

# backend change, then
python -m unittest discover -s eval/tests -p 'test_*.py'          # Ran 183 tests — OK (existing)
python -m unittest eval.tests.test_provider_admission -v          # Ran 13 tests — OK
# mutation checks (app.py restored from a copy after each; cmp confirmed restore):
#   M1 plain await+finally (no shield)  -> FAIL test_cancelled_request_holds_its_slot_...
#   M2 sync QuoteCheckError handler     -> ERROR test_rejection_needs_no_worker_token
#   M3 admission inside worker thread   -> ERROR test_rejection_needs_no_worker_token
python -m benchmarks.run_capacity --quick --experiment admission --gate-cap 32 --run-id <scratch>/smoke_after
#   rejections joined with 0 attempts; prov_peak=32 everywhere; stats --check True

# evidence: before from a detached worktree of v1/scalability@1e7f2ed with the new
# harness files copied in (identical sha256), after from this tree
git worktree add --detach <scratch>/wt_before v1/scalability
cp benchmarks/run_capacity.py benchmarks/stats.py <scratch>/wt_before/benchmarks/
(cd <scratch>/wt_before && python -m benchmarks.run_capacity --experiment admission \
    --gate-cap 40 --run-id SCALE-004-before --ticket SCALE-004)
#   elapsed 1548.5 s; host_safety_guard None; 0 warnings; stats --check True/True
python -m benchmarks.run_capacity --experiment admission --gate-cap 32 \
    --run-id SCALE-004-after --ticket SCALE-004
#   elapsed 1059.9 s; host_safety_guard None; 0 warnings; stats --check True/True
cp -r <scratch>/wt_before/benchmarks/results/SCALE-004-before benchmarks/results/
git worktree remove --force <scratch>/wt_before
PYTHONPATH=. python benchmarks/results/SCALE-004-after/report_tables.py \
    > benchmarks/results/SCALE-004-after/report_tables.out
python -m benchmarks.diag_rejection_log --out benchmarks/results/SCALE-004-after/diag_rejection_log.json
#   rejection mean 367 us with sync log / 295 us without; log call 38 us mean, 74 us p95;
#   sync_log_share 0.195; response_model validate+serialize 30 us mean

# regression
python -m unittest discover -s eval/tests -p 'test_*.py'          # Ran 199 tests — OK
python -m eval.run_eval --validate-only                            # OK — 27 cases, 6 domains, 9 categories, 0 errors.
python -m eval.run_eval --mode demo
#   FAILED: AttributeError: 'coroutine' object has no attribute 'metadata'
#   (run_eval calls the route function directly; it is now async) -> added sync_route_adapter
python -m unittest discover -s eval/tests -p 'test_*.py'          # Ran 201 tests in 2.738s — OK
python -m eval.run_eval --validate-only                            # OK — 27 cases, 6 domains, 9 categories, 0 errors.
python -m eval.run_eval --mode demo
#   27/27 schema-valid; 24/27 deterministic cases pass. (non-zero exit by design)
#   failed cases: AUTO-004, CONT-003, HVAC-003
python -m benchmarks.run_capacity --quick --experiment demo --run-id <scratch>/smoke_demo
#   Demo /analyze over real HTTP: 20/20 ok at C=1 and C=4
for d in SCALE-001-baseline SCALE-002-before SCALE-002-after SCALE-003-saturation \
         SCALE-004-before SCALE-004-after; do python -m benchmarks.stats benchmarks/results/$d --check; done
#   every summary.json and health_summary.json: True
git diff --check                                                   # clean
```

**Provenance recorded in `env.json`:**
- both runs: `git_commit 1e7f2ed`, `git_dirty: true`;
- `harness_sha256`: `run_capacity.py 484c1a9f…`, `stats.py 13f353e4…`, `fake_provider.py 9f35ae00…`, `workloads.py ef8e426a…`, identical for both;
- `admission_gate_cap` is 40 (before) or 32 (after).

## Headline results (details and Gate D in the report)

- **Provider in-flight.** 32 in every after-run point, including fail-first and fail-always retries. It was 40 before. Rejected requests make 0 provider attempts.
- **C=64 at 5 s, sustained:**
  - admitted p50/p95/max goes from 9.7/10.4/15.4 s to 5.1/5.3/5.4 s;
  - pre-provider p95 goes from 5295 to 191 ms;
  - post-provider p95 goes from 5120 to 129 ms (attributed to the coupled change, not to the budget alone);
  - rejections take p50 1.4 ms and p95 10.7 ms.
- **`/health` p95 at C=40/64** falls from 2.2–4.7 s to 3.5–27.8 ms. In the zero-backoff rejection storm (~2k rejections/s) it is 155 ms, against 4.7 s before.
- **Price:** peak completed throughput under saturation is about 20% lower (6.2 vs 7.7 rps at 5 s), because the ceiling is now 32 / latency.

## Deviations from the approved plan (surfaced, not silent)

1. **Slot release mechanism.**
   - The plan said releasing in `finally` after `await run_in_threadpool(...)` was safe because of anyio's `abandon_on_cancel=False`. A direct check disproved this: a native asyncio `Task.cancel()` resumes the coroutine immediately, while the thread is still in the provider call.
   - The implementation therefore runs admitted work in its own task behind `asyncio.shield` and releases in that task's `finally`. A test covers it, and a mutation check confirms the test catches the plain-await version.
   - Practical exposure in the installed stack is limited to uvicorn's graceful-shutdown timeout. Nothing cancels a request task on client disconnect.
2. **Before-run location.**
   - The plan said to run "before" before editing the backend. The backend had already been edited when the harness was ready.
   - "before" was run from a detached worktree of `v1/scalability` @ `1e7f2ed` with byte-identical harness files. This is an equivalent control, with hashes recorded.
3. **Eval runner adapter.** This file change wasn't listed in the plan. The Demo eval exposed that `eval/run_eval.py` calls the route function directly. The adapter keeps evaluation on the real route; no eval semantics changed.

## Known limitations

- **Environment.** One WSL2 host with client, QuoteCheck and fake together; loopback HTTP only; closed-loop load. Burst and backoff behaviour are harness choices: the 0.25 s backoff and the zero-backoff worst case.
- **Unattributed effects:**
  - The rejection-latency tail: 1.2–1.5% over 50 ms, max ~220 ms.
  - At 5 s / C=32 the after build shows about +2.5 ms CPU per request and about +40–60 ms pre-provider p50, with no rejections involved. This doesn't occur at 3 s, and it is not connection churn.
- **Health probes.** 40 probes per point, so p95 is rank 38 of 40. Health wasn't probed during retry load.
- **Not measured:**
  - real OpenAI latency or rate limits;
  - Railway resources or health-check timeouts;
  - multi-process topology;
  - open-arrival traffic.
- **Paid eval.** `eval.run_eval --mode openai` was not run. It is paid and not approved. The adapter path is exercised in Demo mode and by the unit test.
- **Uncommitted evidence.** The evidence comes from an uncommitted tree; file hashes are recorded instead.
- **Budget scope.** 32 is a locally evidence-backed v1 per-process budget. It is not a claim about real OpenAI or Railway capacity.

## Final cleanup (after Gate D acceptance)

**Evidence size.** As produced, `SCALE-004-after/` was 205 MB. After cleanup it is 94 MB; `SCALE-004-before/` stays at 14 MB and is unchanged. Almost all of the original size came from the two zero-backoff scenarios (116,648 + 39,377 rejection records).

**Removed.** Four `SCALE-004-after/server/` logs from the zero-backoff scenarios. They are the only oversized server logs, and no replay or report script reads `server/`.

| file | bytes | sha256 prefix |
|---|---:|---|
| `server/adm_sustained_5000ms_nobackoff__app_runs.jsonl` | 77,925,250 | `e232bd08efe66048` |
| `server/adm_health_5000ms_nobackoff__app_runs.jsonl` | 26,299,557 | `7d8b28739d0a0345` |
| `server/adm_sustained_5000ms_nobackoff__uvicorn.log` (access log) | 9,014,956 | `b3d30b80bba51b37` |
| `server/adm_health_5000ms_nobackoff__uvicorn.log` (access log) | 3,046,977 | `c077abd509024aca` |

Their content is still represented in the retained evidence:
- per-trial reconciliation (`log_records`, `log_provider_attempts`, `reconciled`, `attempts_joined`) in `trials.jsonl`;
- each request's logged `provider_attempts` in `requests.jsonl`. All 116,648 sustained zero-backoff rejections record 0.

**Retained** at this cleanup stage (see "Evidence compaction before publication" for what was later omitted from Git):
- `env.json` (provenance and harness hashes);
- `scenarios.jsonl`, `trials.jsonl`, `requests.jsonl`;
- `provider_attempts.jsonl`;
- `health_probes.jsonl`, `health_load_requests.jsonl`;
- `summary.json`, `health_summary.json`;
- `report_tables.py` and `report_tables.out`;
- `diag_rejection_log.json`;
- `run_console.log`;
- every other `server/` log.

`requests.jsonl` (57 MB) and `health_load_requests.jsonl` (16 MB) are the remaining bulk. Both are read by `stats --check` or `report_tables.py`, so they were kept at this stage; they were later omitted from Git with the rest of the request-level/server bulk.

**Also removed:** the generated, untracked Demo eval artifacts `eval/results/run_20260928T110613Z.jsonl` and `eval/results/summary_20260928T110613Z.md`.

**Integrity after cleanup** (checked on the full evidence, before compaction):
- `stats --check` is True for SCALE-001-baseline, SCALE-002-before, SCALE-002-after, SCALE-003-saturation, SCALE-004-before and SCALE-004-after, for `summary.json` and, where present, `health_summary.json`.
- Re-running `report_tables.py` reproduces `report_tables.out` byte for byte (`cmp`).
- The current sha256 of `run_capacity.py`, `stats.py`, `fake_provider.py` and `workloads.py` equals the `harness_sha256` in both SCALE-004 `env.json` files.
- `git status` shows no change under the historical result directories.
- No executable code changed during cleanup, so the regression result stands: 201 tests; validate-only OK; Demo 27/27 schema-valid and 24/27 passing (AUTO-004, CONT-003, HVAC-003); ₹0.

**`CLAUDE.md`.** The "Current architecture facts" section now states:
- `/analyze` is a thin async admission wrapper around the synchronous body;
- the fixed 32-slot, per-process OpenAI admission budget, decided before threadpool dispatch;
- fail-fast 503 `capacity_exceeded`, with zero provider calls on rejection;
- a retry stays inside its request's slot;
- Demo bypasses admission;
- the per-process budget multiplies across processes and replicas, and 32 is not an OpenAI or Railway capacity claim.

In the "does not currently have" list, "aggregate provider-concurrency control" became cross-process provider-concurrency control.

## Evidence compaction before publication

SCALE-004 was executed with full request-level and server evidence. That full evidence was used for report generation (`report_tables.py`), reconciliation, `stats --check` and Decision Gate D; every result above was obtained from it.

Before final branch publication, the generated bulk was intentionally omitted from Git, in both `SCALE-004-before/` and `SCALE-004-after/`:

- `requests.jsonl`
- `health_load_requests.jsonl`
- `server/`

Details:

- **Manifest.** sha256 hashes and byte sizes of every omitted file are in `benchmarks/results/SCALE-004_RAW_EVIDENCE_MANIFEST.txt`.
- **External archive.** The full raw evidence is retained outside the repository.
- **Committed compact evidence** (4.4 MB total): `env.json`, `scenarios.jsonl`, `trials.jsonl`, `summary.json`, `health_summary.json`, `health_probes.jsonl`, `provider_attempts.jsonl`, `run_console.log`, `diag_rejection_log.json`, `report_tables.py`, `report_tables.out`, plus the benchmark harness and workload definitions.
- **`.gitignore`** now excludes `benchmarks/results/*/requests.jsonl`, `*/health_load_requests.jsonl` and `*/server/` for future runs. Historical SCALE-001–003 raw files stay tracked.
- **Reproducibility contract.** A fresh clone reproduces the experiment by rerunning the harness. Exact replay of the original SCALE-004 run from request-level events (`stats --check`, `report_tables.py`) requires the separately retained raw archive. The `stats --check` passes recorded in this bundle are verification results from before compaction, not something the compact committed bundle guarantees.
- No executable code changed during compaction (docs, `.gitignore` and index only), so the benchmark suite was not rerun and the regression result above stands.

## Out-of-scope findings (recorded, not fixed)

1. **Rejection storms saturate the single event loop.** At about 2k/s the server runs at ~0.95 of a core and `/health` p95 is 155 ms. Candidate levers: per-client rate limiting, `Retry-After`, client backoff. None was added (Gate D, item E1).
2. **The `RequestValidationError` (422) handler is still sync.** Each invalid request takes one of the 8 unreserved worker tokens. An invalid-request flood competing with `/health` was not measured.
3. **Stale `CLAUDE.md` statement (resolved in the final cleanup).** "Current architecture facts" described `/analyze` as a synchronous `def` route and listed aggregate provider-concurrency control as absent. It was narrowly corrected with owner approval; see "Final cleanup".
4. **Stale `docs/PROJECT_STATUS.md` test count.** It still cites "~144 stdlib harness tests" (now 201). This predates SCALE-004 and was left unchanged. Nothing in PROJECT_STATUS contradicts SCALE-004: public rate limiting / quota control is still absent.
5. **The pre-existing absolute-`--run-id` marker issue** in `run_retry` is still unchanged. It didn't block SCALE-004, whose experiments use `run_dir.name`.

## Dependency changes

None. Only stdlib and already-installed modules are used (`asyncio`, `inspect`, `starlette.concurrency`, `httpx`, `anyio`).

## Architectural observations

- **The new binding resource.** Overload is now decided in O(µs) on the event loop, and admitted provider work is capped at 32 worker tokens. Under a rejection storm, the binding resource becomes the single event loop's CPU, at roughly 0.3–0.5 ms per rejection over real HTTP. Worker tokens are no longer the binding resource.
- **What `/health` isolation needed.** It needed admission plus the removal of the second token acquisitions. No separate health-path change was required.
- **Three coupled parts.** Admission, the async route/error boundary, and the unchanged sync provider body cannot be separated in this implementation. The post-provider improvement is attributed to that coupled change.
- **Topology.** The budget is per process; aggregate provider concurrency equals processes × 32.

## Incidental files

`eval/results/{run,summary}_20260928T110613Z.*` came from the Demo eval run. They were not intended for commit, following SCALE-001–003 practice, and were deleted in the final cleanup.
