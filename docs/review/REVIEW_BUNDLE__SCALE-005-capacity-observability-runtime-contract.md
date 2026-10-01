# REVIEW BUNDLE — SCALE-005 Capacity Observability & Runtime Contract

- **Ticket:** `docs/tickets/SCALE-005-capacity-observability-runtime-contract.md`
- **Contract, envelope and Decision Gate E:** `docs/scalability/SCALE-005_RUNTIME_CONTRACT.md`
- **Branch:** `task/SCALE-005-capacity-observability-runtime-contract`, from `v1/scalability` @ `25d0ebf`. It merges back into `v1/scalability`, never `main`. **Nothing is committed yet.**
- **Risk class:** T1, documentation and runtime contract only.
- **Provider spend:** ₹0. No OpenAI credential, no provider call, no new benchmark run, and no contact with the public deployment. No deployment configuration changed.

## Scope summary

SCALE-005 asked whether QuoteCheck already exposes enough runtime state and overload semantics to make its v1 operating envelope understandable and defensible.

The approved assessment answered yes, so the outcome was **Outcome 1: documentation and contract only.**

What this ticket does:
1. Freezes the v1 runtime contract: 15 claims, each mapped to source and an existing enforcing test or accepted evidence.
2. States the overload and failure semantics and the local operating envelope.
3. Sharpens the cost claim: concurrency and per-request amplification are bounded; cumulative spend is **not** application-bounded.
4. Provides an operator guide with JSONL commands, validated on retained SCALE-004 logs.
5. Classifies the 14 open candidates, with revisit triggers.
6. Ends at Decision Gate E (**PASSED**), with a recommended minimum SCALE-006 scope.

## Files changed

| File | Change |
|---|---|
| `docs/tickets/SCALE-005-capacity-observability-runtime-contract.md` (new) | The ticket |
| `docs/scalability/SCALE-005_RUNTIME_CONTRACT.md` (new) | The sharpened definition, runtime contract (C1–C15), overload semantics, local envelope, cost contract, operator guide (A1–A10, field semantics, commands), decision register (D1–D14), and Gate E |
| `docs/review/REVIEW_BUNDLE__SCALE-005-capacity-observability-runtime-contract.md` (new) | This bundle |
| `docs/CURRENT_STATE.md` | Date line; `latency_ms` semantics and "no token usage" in the run-logger bullet; a new "Changed in SCALE-005" section |
| `CLAUDE.md` | One paragraph in "Current architecture facts": a pointer to the contract, plus the cost-claim boundary (no cumulative-spend bound, no `max_output_tokens`, no token logging, and the deferral trigger). Future sessions read CLAUDE.md first, so this keeps them from overclaiming. |

There are **no** changes to `backend/`, `frontend/`, `eval/`, `benchmarks/`, `.gitignore`, deployment or dependencies.

## Acceptance criteria with evidence

| # | Criterion | Evidence | Result |
|---|---|---|---|
| 1 | Every contract claim cites source plus an existing test or accepted evidence | Contract §2, C1–C15. All 26 cited test functions exist exactly once in `eval/tests/`, and the 4 cited test classes or tables exist. All 25 spot-checked `file:line` citations contain the cited code (commands below). C14 is structural, backed by source and `env.json`. | ✅ |
| 2 | Envelope numbers match committed SCALE-004 evidence | Every §4 range was recomputed programmatically from committed `report_tables.out` (output below). The storm figures come from committed `trials.jsonl`. The one figure taken from the SCALE-004 report (outage p50 6141 ms) is labelled as such. | ✅ |
| 3 | Operator commands validated on retained logs | Manifest verified (42/42 files OK). C1–C4 ran verbatim on 4 retained after-build server logs. Categories the retained logs don't contain are documented (contract §6.3). | ✅ |
| 4 | A1–A10 labelled; missing signals carry scope and trigger | Contract §6.1: 7 missing signals, each with its scope and revisit trigger | ✅ |
| 5 | 14 candidates classified with evidence and trigger | Contract §7, D1–D14. None is REQUIRED. | ✅ |
| 6 | Cost contract statements | Contract §1, §5.2–§5.4. Also stated in CURRENT_STATE and CLAUDE.md. | ✅ |
| 7 | `32 / latency` only as an idealized ceiling; no SLA claims | Contract §4 banner and §4.1 ("not a throughput guarantee") | ✅ |
| 8 | `git diff --check` clean; docs-only diff; ₹0 | Commands below | ✅ |

## Exact commands run, with real results

```bash
git status --short && git rev-parse HEAD
#   (clean) 25d0ebfe4e1e9d96fbef0172a52d9e1d22ab8941
git checkout -b task/SCALE-005-capacity-observability-runtime-contract

# 1. Integrity of the retained (non-Git) SCALE-004 raw evidence against the committed manifest
python3 - <<'EOF'
import hashlib,os
ok=bad=missing=0
for line in open("benchmarks/results/SCALE-004_RAW_EVIDENCE_MANIFEST.txt"):
    p=line.split()
    if len(p)<4 or len(p[0])!=64: continue
    h,size,path=p[0],int(p[1]),p[3]
    if not os.path.exists(path): missing+=1; print("MISSING",path); continue
    d=hashlib.sha256(open(path,"rb").read()).hexdigest()
    if d==h and os.path.getsize(path)==size: ok+=1
    else: bad+=1; print("MISMATCH",path)
print("ok",ok,"mismatch",bad,"missing",missing)
EOF
#   ok 42 mismatch 0 missing 0

# 2. Operator commands C1–C4 (exactly as printed in contract §6.3), run in
#    benchmarks/results/SCALE-004-after/server/ on four logs
#    (output kept in the session scratchpad, not committed). Real output:
### adm_sustained_5000ms__app_runs.jsonl
C1: [(('openai', 'capacity_exceeded', 0), 9700), (('openai', 'ok', 1), 1317)]
C2: {'records': 11017, 'openai': 11017, 'rejected': 9700, 'rejected_with_calls': 0, 'admitted': 1317, 'provider_attempts': 1317, 'attempts_per_admitted': 1.0, 'retried': 0, 'attempts_unknown': 0}
C3: [(('capacity_exceeded', None, None, True, 0), 9700)]
C4: [('2026-09-28T10:50', 767), ('2026-09-28T10:51', 3435), ('2026-09-28T10:52', 5498)]
### adm_retry_fail_first_sustained_3000ms__app_runs.jsonl
C1: [(('openai', 'capacity_exceeded', 0), 4657), (('openai', 'ok', 2), 230)]
C2: {'records': 4887, 'openai': 4887, 'rejected': 4657, 'rejected_with_calls': 0, 'admitted': 230, 'provider_attempts': 460, 'attempts_per_admitted': 2.0, 'retried': 230, 'attempts_unknown': 0}
C3: [(('capacity_exceeded', None, None, True, 0), 4657)]
C4: [('2026-09-28T11:00', 2000), ('2026-09-28T11:01', 2657)]
### adm_retry_fail_always_sustained_3000ms__app_runs.jsonl
C1: [(('openai', 'capacity_exceeded', 0), 4661), (('openai', 'provider_unavailable', 2), 232)]
C2: {'records': 4893, 'openai': 4893, 'rejected': 4661, 'rejected_with_calls': 0, 'admitted': 232, 'provider_attempts': 464, 'attempts_per_admitted': 2.0, 'retried': 232, 'attempts_unknown': 0}
C3: [(('capacity_exceeded', None, None, True, 0), 4661), (('provider_unavailable', 503, 'InternalServerError', True, 2), 232)]
C4: [('2026-09-28T11:01', 96), ('2026-09-28T11:02', 4565)]
### adm_burst_lat3s__app_runs.jsonl
C1: [(('openai', 'ok', 1), 613), (('openai', 'capacity_exceeded', 0), 344)]
C2: {'records': 957, 'openai': 957, 'rejected': 344, 'rejected_with_calls': 0, 'admitted': 613, 'provider_attempts': 613, 'attempts_per_admitted': 1.0, 'retried': 0, 'attempts_unknown': 0}
C3: [(('capacity_exceeded', None, None, True, 0), 344)]
C4: [('2026-09-28T10:46', 344)]
```

**3. Reconciling the retained logs with committed `trials.jsonl`.** For each scenario, whole-log counts were compared with Σ trial `log_records`, `log_provider_attempts` and `rejected`:

```
adm_burst_lat3s                         trials:log_records=   680 log=957   | trials:attempts= 480 log=613  | trials:rejected=   200 log=344
adm_retry_fail_always_sustained_3000ms  trials:log_records=  4760 log=4893  | trials:attempts= 390 log=464  | trials:rejected=  4565 log=4661
adm_retry_fail_first_sustained_3000ms   trials:log_records=  4754 log=4887  | trials:attempts= 386 log=460  | trials:rejected=  4561 log=4657
adm_sustained_5000ms                    trials:log_records= 10740 log=11017 | trials:attempts=1184 log=1317 | trials:rejected=  9556 log=9700
adm_sustained_5000ms_nobackoff          trials:log_records=117032 log=(removed in SCALE-004 cleanup)
all 53 trials: reconciled and attempts_joined = True; peak_in_flight = 32
```

- The differences are exactly the harness warm-ups, which `trials.jsonl` excludes (`scenarios.jsonl`: `seq_warmup_requests: 5`, `burst_warmup_per_point: "2 x concurrency"`; `benchmarks/README.md:87`):
  - the 32/40/64 ladders differ by 277 = 5 + 2 × (32 + 40 + 64);
  - the C=64 retry scenarios differ by 133 = 5 + 2 × 64.
- Fail-always detail: 37 admitted warm-up requests (5 sequential + 32 burst) plus 96 rejected burst warm-ups (128 − 32).
- Fail-first: attempts differ by 74 = 37 × 2.

```bash
# 4. Storm CPU from committed trials.jsonl (server_cpu_s / wall_s; rejected/wall_s)
#   adm_sustained_5000ms_nobackoff C=64: 0.952 / 0.96 / 0.952 core; 1869 / 1889 / 1871 rejections/s

# 5. Envelope ranges recomputed from committed SCALE-004-after/report_tables.out
#    (output kept in the session scratchpad, not committed)
peak in-flight (all after analysis rows): {'32'}
peak in-flight (health load rows): {'32'}
rps burst3s (10.0, 10.14) burst5s (6.09, 6.11) sust5s (6.15, 6.21)
ok p95 burst3s (3170.0, 3270.0) burst5s (5272.0, 5302.0) sust5s (5312.0, 5355.0) sust max (5339.0, 5460.0) retry (6304.0, 6415.0)
pre p95 all (136.0, 272.0) post p95 all (23.0, 216.0)
burst rej p50/p95/max (55.7, 98.6) (141.6, 181.2) (176.3, 199.1)
sustained-backoff rej p50/p95/max (1.4, 1.5) (3.4, 10.8) (157.3, 179.9)
cpu ms/req (0.51, 8.88)
health backoff p50/p95/max (1.8, 2.0) (3.5, 27.8) (30.0, 167.7)
health probes total / non-200: 400 0

# 6. Provenance: SCALE-004-after/env.json harness_sha256 vs the current harness files
#   run_capacity.py 484c1a9f / stats.py 13f353e4 / fake_provider.py 9f35ae00 / workloads.py ef8e426a: identical
#   env.json: git_commit 1e7f2ed, git_dirty true, server_processes 1, server_workers 1 (no backend hashes)
git diff 1e7f2ed 25d0ebf --stat -- backend eval/run_eval.py
#   backend/app.py, core/admission.py, core/config.py, core/errors.py, eval/run_eval.py (SCALE-004 only)

# 7. Citation checks
#   All 26 cited test function names: each defined exactly once in eval/tests/*.py.
#   _ROUTE_CASES, ResponseStateTests, ConfigurationTests, FailureLoggingTests present.
#   25 cited file:line locations: each line contains the cited code ("ok" x 25).

# 8. Diff hygiene
git diff --check                    # clean
git diff --stat 25d0ebf             # CLAUDE.md | 2 ++ ; docs/CURRENT_STATE.md | 35 +++-- (tracked)
git status --short --untracked-files=all
#   M CLAUDE.md
#   M docs/CURRENT_STATE.md
#   ?? docs/scalability/SCALE-005_RUNTIME_CONTRACT.md
#   ?? docs/review/REVIEW_BUNDLE__SCALE-005-capacity-observability-runtime-contract.md
#   ?? docs/tickets/SCALE-005-capacity-observability-runtime-contract.md
#   Paths outside docs/ and CLAUDE.md: none    (final check, after this bundle was written)
```

**Not run (deliberately, per the approved verification scope).**
- The unit suite, `--validate-only`, the Demo eval and any capacity benchmark were not run.
- SCALE-005 changes no executable file. Those regressions belong to SCALE-006 closure verification.
- The last recorded result (SCALE-004) is: 201 tests OK; Demo 27/27 schema-valid, 24/27 passing (AUTO-004, CONT-003, HVAC-003).

## Corrections made during self-review

The draft contract was checked against the source before finalizing. These errors were found and fixed:

1. **Pre-call configuration errors.** They log `provider_attempts: null`, not `0`. `resolve_openai_timeout_seconds` and the missing-key check raise without setting attempts. `0` therefore means a capacity rejection and nothing else.
2. **Demo-success `latency_ms`.** It is computed *before* the Demo analyzer runs (`app.py:277`), so it is ≈ 0. It is not "Demo analyzer time".
3. **`ConfigurationTests` count.** It has 8 tests, not 7.
4. **Admitted-request overhead.** The planning draft said p95 overhead was "≤ ~250 ms". The evidence gives pre-provider p95 136–272 ms and post-provider p95 23–216 ms, and the contract now states those ranges.
5. **Scope banner.** It now names the SCALE-004 report as the source of the one figure that isn't in `report_tables.out`.

## Known limitations

- **Envelope.** It is local, uses a fake provider, comes from one WSL2 host, and uses closed-loop load (SCALE-004 conditions). It is not an SLA, and not an OpenAI or Railway claim.
- **Operator commands were validated only on OpenAI-mode (fake) logs.**
  - The validated categories are success, `capacity_exceeded` and `provider_unavailable`.
  - Demo records and the other failure categories are not in the retained logs. Their log shape is test-enforced instead.
  - The retained logs live outside Git (hash-verified), so the validation can be repeated exactly only with the raw archive. The commands themselves work on any `app_runs.jsonl`.
- **Deployment topology was not inspected.** Railway dashboard settings could override the committed single-process start command (`railpack.json`).
- **Cost.**
  - Token usage, real model pricing and provider billing behaviour on timeouts are unmeasured.
  - The timeout-billing point is labelled HYPOTHESIS.
  - Provider-account spend limits are external and not verified.

## Out-of-scope findings (recorded, not fixed)

1. **Demo-success `latency_ms` is always ≈ 0.**
   - `app.py:277` reads the clock before calling `analyze_quote_stub`, and passes that value into the result metadata as well as the log.
   - This predates v1. It is harmless to capacity reasoning, because Demo is not provider-bound, but the field is misleading.
   - It is documented in the contract §6.2 and in CURRENT_STATE.
   - Fixing it would change Demo `metadata.latency_ms`, so it needs its own ticket.
2. **`provider_attempts` is `null` on a post-analysis `internal_error`** (`app.py:355`), even though calls were made. It is practically unreachable and documented in §6.2.
3. **SCALE-004 evidence provenance.** `env.json` records the backend as `1e7f2ed` + dirty, without backend hashes. The evidence-to-code link for `78cc5d3` rests on attestation. This motivates the minimal SCALE-006 smoke check (contract §8).
4. **Public-doc drift** (carried from SCALE-004 finding 4). `PROJECT_STATUS.md` still cites "~144" tests and does not state the capacity/overload behaviour or the cost boundary. It is assigned to SCALE-006.

## Dependency changes

None.

## Architectural observations

- **The cost bound is a property of exposure, not of the application.** QuoteCheck bounds the *rate* at which spend can accrue (≤ 32 concurrent attempts per process, ≤ 2 attempts per request). It does not bound the *integral* over time.
  - That is acceptable for v1, because OpenAI mode is not publicly exposed.
  - The deferral triggers in contract §5.4 and §7 (D1, D6) mark exactly when this stops being acceptable.
- **The log is sufficient for admission questions, but it is not a metrics system.** `failure_category` plus `provider_attempts` fully determine admitted vs rejected and the degree of amplification. Structured admission fields would add nothing in a fixed-budget, single-process topology (D4).
- **`latency_ms` is not one metric.** It measures four different intervals depending on the path. Any future capacity analysis based on server logs must segment by path, or rely on the harness's client-side timings, as SCALE-001–004 did.

## Incidental files

Two scratch outputs were written only to the session scratchpad (not the repository): `s005_query_validation.txt` and `s005_envelope_check.txt`. No `eval/results/` or `benchmarks/results/` files were created.
