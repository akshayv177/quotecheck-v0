# REVIEW BUNDLE — SCALE-006 Final Scalability Recharacterization + QuoteCheck v1 Closure

- Ticket: `docs/tickets/SCALE-006-final-scalability-v1-closure.md`
- Closure document: `docs/scalability/SCALE-006_V1_CLOSURE.md`
- Branch: `task/SCALE-006-final-scalability-v1-closure`, from `v1/scalability` @ `0e039ca264825e2a5e85a4ed5d422c48bd1fedb8`
- Provider spend: **₹0**. No OpenAI credential, no paid evaluation, public deployment never contacted.
- Environment: conda env `quotecheck`, Python 3.11.14, Linux 6.6.87.2-microsoft-standard-WSL2.

## Scope summary

Closure verification and documentation only.

**Verification.** Every check below ran against a clean tree at `0e039ca`:
- the full unit suite;
- corpus validation;
- the Demo eval;
- frontend lint and build;
- a local Demo backend smoke;
- one quick admission smoke check.

No runtime defect was found, so the stop condition was not triggered and no corrective ticket is needed.

**Documentation.**
- The SCALE-001–005 evidence is consolidated into a closure document, with Decision Gate F (**PASS**).
- Public and current-state docs were synced where they were stale.

## Files changed

| File | Change |
|---|---|
| `docs/tickets/SCALE-006-final-scalability-v1-closure.md` | new ticket |
| `docs/scalability/SCALE-006_V1_CLOSURE.md` | new: the v1 story, final contract, cost boundary, smoke results, envelope, limitations, Gate F |
| `docs/review/REVIEW_BUNDLE__SCALE-006-final-scalability-v1-closure.md` | this bundle |
| `docs/PROJECT_STATUS.md` | Test count ~144 → 201, with the v0 figure kept as history. New public-ready item: capacity boundary and overload. Two new limitations: per-process, locally measured capacity; and cost bounded per request and in concurrency, not over time. A non-overclaim item about the v1 numbers. The "planned hardening" load-testing line is clarified. |
| `README.md` | "Eight failure categories" → nine, including `capacity_exceeded`. Reliability tests "42" → 47 plus 13 admission tests. `capacity_exceeded` added to the API contract paragraph. New "Capacity and overload" section, a highlights bullet, a limitations bullet, a nav link and a docs link. |
| `docs/CURRENT_STATE.md` | Date line updated. "Changed in SCALE-006" section added. The stale "QC-5 … is the next task" sentence removed from Gaps. |
| `CLAUDE.md` | "capacity limits are a v1 measurement question" → a pointer to the closure document. The test-count line gains the SCALE-006 count of 201. |

No file outside `docs/`, `README.md` and `CLAUDE.md` changed.

## Acceptance criteria with evidence

| # | Criterion | Evidence | Result |
|---|---|---|---|
| 1 | Regression passes on `0e039ca` with actual counts | Commands 2–6 | **Met**: 201 tests OK; corpus 27 cases, 0 errors; Demo eval 27/27 and 24/27 (`AUTO-004`, `CONT-003`, `HVAC-003`); lint and build clean; Demo smoke OK |
| 2 | Admission smoke shows the core contract, all trials reconciled | Commands 7–11 | **Met**: peak 32; 503 `capacity_exceeded` for all 6,270 measured rejections; 0 provider calls on all 6,558 logged rejections (the extra 288 are warm-up rejections, command 9b); 2.0 attempts per admitted request under retry; 11/11 trials reconciled and joined; `stats --check` True |
| 3 | Every claim is traceable | Closure doc §2–§7 cite SCALE-001–004 sections, SCALE-005 C-numbers, or §6 | **Met** |
| 4 | Public docs at SCALE-005 strength, no overclaims | Command 13 | **Met** |
| 5 | Limitations explicit, accepted or triggered | Closure doc §8 (18 rows) | **Met** |
| 6 | Diff hygiene and ₹0 | Command 14 | **Met** |

## Exact commands run, with real results

```text
# 1. Base and clean tree
git status --short            -> (empty)
git rev-parse HEAD            -> 0e039ca264825e2a5e85a4ed5d422c48bd1fedb8   (v1/scalability)
git switch -c task/SCALE-006-final-scalability-v1-closure
git diff --stat 25d0ebf 0e039ca -- backend eval benchmarks frontend railpack.json   -> (empty)
git diff --stat 78cc5d3 0e039ca -- backend eval/run_eval.py benchmarks/*.py frontend/src -> (empty)
git rev-parse main            -> b7beaf291e39f8dcce0dea54a3bfc7da4bcfc7e6  (untouched)
git diff --stat main v1/scalability -- backend/requirements.txt frontend/package.json \
    frontend/package-lock.json railpack.json                                -> (empty)

# 2. Unit suite
python -m unittest discover -s eval/tests -p 'test_*.py'
  Ran 201 tests in 1.815s
  OK
  (subsets: python -m unittest eval.tests.test_openai_reliability -> Ran 47 tests OK;
            python -m unittest eval.tests.test_provider_admission -> Ran 13 tests OK)

# 3. Corpus validation
python -m eval.run_eval --validate-only
  OK — 27 cases, 6 domains, 9 categories, 0 errors.

# 4. Demo eval
python -m eval.run_eval --mode demo
  27/27 schema-valid; 24/27 deterministic cases pass.
  Exit non-zero: one or more selected cases failed deterministic evaluation
  (known Demo-mode gaps are retained, not suppressed).
  Failed cases (from the generated summary): AUTO-004, CONT-003, HVAC-003
rm eval/results/run_20261001T050102Z.jsonl eval/results/summary_20261001T050102Z.md
  (generated output removed; the tracked 2026-08-29 baselines are untouched)

# 5. Frontend
cd frontend && npm run lint      -> eslint . (no findings)
npm run build                    -> ✓ 29 modules transformed … ✓ built in 688ms
  (frontend/dist/ is gitignored; git status unchanged)

# 6. Local Demo backend smoke (port 8765, log to the session scratchpad)
env -u OPENAI_API_KEY QUOTECHECK_USE_OPENAI=0 QUOTECHECK_LOG_PATH=<scratch>/demo_smoke_runs.jsonl \
  uvicorn backend.app:app --host 127.0.0.1 --port 8765
GET  /health                       -> {"status":"ok"} HTTP 200
POST /analyze (brake + shop supplies quote) -> HTTP 200;
     metadata.model quotecheck-demo-analyzer, prompt_version quotecheck_v0.4,
     schema_valid True, 2 line items
POST /analyze {"quote_text":""}    -> HTTP 422 {"detail":{"code":"invalid_request",…,"retryable":false,…}}
log record: analyzer demo, success True, provider_attempts None, model quotecheck-demo-analyzer
(The first stop attempt used `pkill -f`, which matched the invoking shell and ended
 that command with exit 144. A follow-up check confirmed the server had stopped.)

# 7. Admission smoke
python -m benchmarks.run_capacity --quick --experiment admission --gate-cap 32 \
    --ticket SCALE-006 --run-id <scratch>/s006-final-admission-smoke
  (absolute --run-id resolves outside benchmarks/results/; git status unchanged afterwards)
  real 0m40.307s
  experiment scenario                                C   reqs ok  fail peak_inflt prov_att
  admission  adm_burst_lat300ms                      4     8   8    0   4          8
  admission  adm_burst_lat300ms                      40   80  64   16  32         64
  admission  adm_sustained_300ms                     4    16  16    0   4         16
  admission  adm_sustained_300ms                     40  149 109   40  32        109
  admission  adm_sustained_300ms_nobackoff           40 2224 105 2119  32        105
  admission  adm_retry_fail_first_burst_300ms        40   80  64   16  32        128
  admission  adm_retry_fail_first_sustained_300ms    40  104  64   40  32        128
  admission  adm_retry_fail_always_sustained_300ms   40  104   0  104  32        128
  burst C=40 trials: rej=8 each, rej_p95 62.68 / 63.65 ms, prov_peak=32
  health adm_health_lat300ms     C=40: probes=5 non200=0 p50=2.88 p95=19.34 load_rej=69 prov_peak=32
  health adm_health_300ms_nobackoff C=40: probes=5 non200=0 p50=33.27 p95=86.64 load_rej=3930 prov_peak=32
  (all 25 probes, including idle and C=4: status 200)

# 8. Provenance and reconciliation
env.json: git_commit 0e039ca264825e2a5e85a4ed5d422c48bd1fedb8, git_dirty False, quick True,
          admission_gate_cap 32, server_processes 1, server_workers 1, elapsed_s 40.2,
          host_safety_guard None
harness_sha256: run_capacity 484c1a9f… stats 13f353e4… fake_provider 9f35ae00… workloads ef8e426a…
          (identical to SCALE-004)
backend sha256 (12): app.py 2bcb5a13d5bd, admission.py f77ede779407, config.py 680744fb7347,
          errors.py 74f1532b1529, openai_analyzer.py a0d29296be8c
trials.jsonl: 11 trials, every one reconciled True and attempts_joined True
python -m benchmarks.stats <run> --check
  summary.json matches recomputation: True
  health_summary.json matches recomputation: True
summary.json admission blocks: burst C=40 and retry burst C=40
  all_rejections_done_before_first_provider_end True; non_rejection_failures 0
  except fail-always (64, expected)

# 9. SCALE-005 §6.3 operator query C2/C3, verbatim, over each server/*__app_runs.jsonl (incl. warm-ups)
  adm_burst_lat300ms                     rejected 64   (0 with calls) admitted 114 attempts/admitted 1.0
  adm_health_300ms_nobackoff             rejected 3930 (0 with calls) admitted 227 1.0
  adm_health_lat300ms                    rejected 69   (0 with calls) admitted 253 1.0
  adm_retry_fail_always_sustained_300ms  rejected 88   (0 with calls) admitted 98  2.0 retried 98
      C3: ('provider_unavailable', 503, 'InternalServerError', True, 2) x98,
          ('capacity_exceeded', None, None, True, 0) x88
  adm_retry_fail_first_burst_300ms       rejected 64   (0 with calls) admitted 98  2.0 retried 98
  adm_retry_fail_first_sustained_300ms   rejected 88   (0 with calls) admitted 98  2.0 retried 98
  adm_sustained_300ms                    rejected 88   (0 with calls) admitted 167 1.0
  adm_sustained_300ms_nobackoff          rejected 2167 (0 with calls) admitted 139 1.0
  total rejections 6,558, all provider_attempts 0; attempts_unknown 0 everywhere

# 9b. Why 6,558 logged rejections vs 6,270 rejected client requests (reconciled per scenario)
#     The server log includes harness warm-ups. requests.jsonl and trials.jsonl exclude them
#     (run_capacity.py:46). Warm-ups are 2 sequential per scenario, plus one 2×C burst
#     per /analyze ladder point (run_capacity.py:938–940), not per trial.
  scenario                               log  ΣtrialLog  extraRecs warmExpected logRej clientRej extraRej
  adm_burst_lat300ms                     178     88        90        90           64     16       48
  adm_sustained_300ms                    255    165        90        90           88     40       48
  adm_sustained_300ms_nobackoff         2306   2224        82        82         2167   2119       48
  adm_retry_fail_first_burst_300ms       162     80        82        82           64     16       48
  adm_retry_fail_first_sustained_300ms   186    104        82        82           88     40       48
  adm_retry_fail_always_sustained_300ms  186    104        82        82           88     40       48
  adm_health_lat300ms                    322   (320 load)   2         2           69     69        0
  adm_health_300ms_nobackoff            4157  (4155 load)   2         2         3930   3930        0
  total logRej 6558, clientRej 6270, difference 288 = 6 × 48 (C=40 burst warm-up rejections)
  (warmExpected = 2 + Σ over ladder points of 2×C; the health runner has seq warm-up only)

# 10. Independent peak in-flight sweep over provider_attempts.jsonl (t_start/t_end per scenario)
  every C=40 scenario peak 32; overall peak 32
  fake statuses: success scenarios 200 only; fail-first 64×503 + 64×200; fail-always 128×503

# 11. Client-side rejection check (requests.jsonl, health_load_requests.jsonl)
  requests.jsonl: 2765 records; 2271 capacity_exceeded, all HTTP 503, log provider_attempts 0,
                  no fake attempts joined
  (6,270 = 2,271 + 3,999 measured client rejections; the server logs hold 6,558 because they
   also include 288 warm-up rejections; see 9b)
  health_load_requests.jsonl: 4475 records; 3999 capacity_exceeded, all HTTP 503
  status mix (requests.jsonl): 503 capacity_exceeded 2271, 200 430, 503 provider_unavailable 64
du -sh <scratch>/s006-final-admission-smoke -> 8.6M (not committed)

# 12. Stale-claim discovery
grep "144|eight failure|42 stdlib" -> PROJECT_STATUS.md:40,81; README.md:101,202  (fixed)
FailureCategory in backend/core/errors.py: 9 values (incl. CAPACITY_EXCEEDED)

# 13. Overclaim and secret audit on changed and new files
grep -i "production.scale|battle|zero downtime|unlimited|handles .*traffic|OpenAI capacity is|cost is bounded|guarantee"
  -> every hit is a negation or a qualified statement (e.g. "not a guarantee",
     "no scale or uptime guarantees", "Cost is bounded per request and in concurrency,
     not over time"); CLAUDE.md:7 is the existing rule text
git diff | grep -E "sk-[A-Za-z0-9]{10,}|OPENAI_API_KEY=[^ <]+"   -> (no match)

# 14. Diff hygiene
git diff --check                 -> (clean)
git status --short
   M CLAUDE.md
   M README.md
   M docs/CURRENT_STATE.md
   M docs/PROJECT_STATUS.md
  ?? docs/review/REVIEW_BUNDLE__SCALE-006-final-scalability-v1-closure.md
  ?? docs/scalability/SCALE-006_V1_CLOSURE.md
  ?? docs/tickets/SCALE-006-final-scalability-v1-closure.md
git diff --stat v1/scalability   (tracked files)
  CLAUDE.md              |  4 ++--
  README.md              | 56 +++++++++++++++++++++++++++++++++++++++++++++-----
  docs/CURRENT_STATE.md  | 40 +++++++++++++++++++++++++++++++++---
  docs/PROJECT_STATUS.md | 38 +++++++++++++++++++++++++++++-----
git status --short eval benchmarks -> (empty: no eval/results or benchmark bulk)
```

## Decision Gate F

| Gate | Result |
|---|---|
| F1 Regression integrity | PASS |
| F2 Capacity contract integrity | PASS |
| F3 Evidence integrity | PASS. The SCALE-004 attestation-only provenance gap is closed for C1, C3, C5, C6 and C8 by `git_dirty: false` at `0e039ca`. |
| F4 Public truth | PASS (after sync) |
| F5 Known limitations | PASS (closure doc §8) |
| F6 Closure sufficiency | PASS. No evidence justifies another mechanism. |

**Gate F: PASS.** QuoteCheck v1 is technically ready to close. No corrective ticket is needed.

## Corrections after Gate F review (documentation only)

1. **Before/after labels.** The SCALE-004 before/after comparisons are now labelled pre-SCALE-004 / post-SCALE-004 (before/after explicit admission) in the closure doc §7, `README.md` and `PROJECT_STATUS.md`. The pre-SCALE-004 build already includes the SCALE-002 shared client; it is not the v0 baseline.
2. **Cancellation wording.** Cancelled requests keep their provider work running until the worker/provider call finishes, which is test-enforced. They *may* continue to incur provider usage or cost, depending on provider billing semantics. Real-provider billing after cancellation is unverified.
3. **6,270 vs 6,558.** This is explained from harness evidence (command 9b): the 288 extra logged rejections are C=40 burst warm-up rejections, 48 in each of the six non-health scenarios.

## Known limitations (of this ticket)

- **The smoke is a quick plan.** It used a 0.3 s fake latency, C ∈ {4, 40}, one or two trials, and five `/health` probes per point. It confirms contract enforcement only. Latency, throughput, `/health` and storm magnitudes still come from SCALE-004.
- **Not exercised by the harness:** C9 (cancellation) and C10 (Demo bypass). Both are covered by deterministic tests inside the 201-test run.
- **The raw smoke evidence is not retained in Git,** by design. It lives in the session scratchpad, which is temporary. The compact results above are its record.
- **Not inspected:** Railway dashboard settings. The topology statement remains SUPPORTED INFERENCE from `railpack.json`.

## Out-of-scope findings (recorded, not fixed)

- **Stale historical text.** `SCALE-005_RUNTIME_CONTRACT.md` §8 still says `PROJECT_STATUS.md` cites "~144". That is a historical recommendation, now resolved, and it was left unchanged.
- **`pkill -f` hazard.** In ad-hoc smoke scripts, `pkill -f <pattern>` can match the invoking shell when the pattern appears in the same command line. This is a tooling note, with no repository impact.

## Dependency changes

None. `backend/requirements.txt`, `frontend/package.json`, `frontend/package-lock.json` and `railpack.json` are identical to `main`.

## Architectural observations

- **The smoke reproduces SCALE-004 at a different latency.** At 300 ms, the qualitative shape matches SCALE-004 at 3 s and 5 s: a hard 32 cap, rejections finishing before the first admitted call ends, and 2.0 attempts per admitted request inside the cap. That fits the mechanism being latency-independent, as the deterministic tests already assert.
- **The zero-backoff storm reappears at small scale.** With 2,119 rejections in 1.5 s, `/health` p95 was 86.6 ms against 19.3 ms with backoff. This is the same event-loop-bound storm limitation recorded in SCALE-004 and SCALE-005, and it is accepted for v1 (closure doc §8).
- **The analyzer hash matches SCALE-002.** `openai_analyzer.py` sha256 `a0d29296…` is the same as the SCALE-002 "after" analyzer hash, so the analyzer has not changed since SCALE-002.

## Not done (awaiting explicit approval)

- No commit or push.
- No merge into `v1/scalability` or `main`.
- No tag, GitHub release or deploy.
- No branch deletion.
