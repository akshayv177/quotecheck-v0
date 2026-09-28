# REVIEW BUNDLE — SCALE-001 Current-System Capacity and Bottleneck Characterization

Branch: `task/SCALE-001-capacity-characterization` (base `v1/scalability` @ `531853b`;
HEAD `484720d`, the ticket-definition commit). **Nothing committed or merged.**

## Scope summary

This ticket built a zero-provider-cost, reproducible benchmark harness,
measured current QuoteCheck with it, and wrote the baseline report ending at
Decision Gate A. It measured only: the production runtime, API contract,
schema, prompt, retry/timeout policy, logging semantics, deployment
configuration and dependencies are all unchanged.

Headline result (local WSL2 host, comparative evidence only):

- On the OpenAI execution path, **per-request `OpenAI(...)` client
  construction** (SSL context and CA bundle load, about 20 ms CPU serially and
  degrading under concurrency) is the first constraint. It caps throughput at
  about 35–41 analyses/s with the 250 ms fake provider despite additional concurrency.
- The only aggregate provider-concurrency bound is **anyio's implicit
  40-thread limiter**. Peak provider calls in flight were exactly 40 at C = 48
  and 64.
- The Demo path is single-core CPU-bound from C=1–2.

The full analysis is in `docs/scalability/SCALE-001_BASELINE.md`.

## Files changed

New:

| Path | Purpose |
| --- | --- |
| `benchmarks/__init__.py` | package marker |
| `benchmarks/README.md` | commands, safety properties, output layout, method notes |
| `benchmarks/workloads.py` | fixed `short` / `normal` / `near_max` workloads with sha256 |
| `benchmarks/fake_provider.py` | loopback fake of `POST /v1/responses`: lock-guarded counters, `success` / `fail_first` / `fail_always` modes |
| `benchmarks/run_capacity.py` | orchestration: env metadata, uvicorn and fake lifecycles, closed-loop client, `/proc` sampler, guards, reconciliation |
| `benchmarks/stats.py` | nearest-rank percentiles and summaries; `--check` recomputes from raw data |
| `benchmarks/diag_client_construction.py` | focused, evidence-driven diagnostic of client-construction cost |
| `benchmarks/results/SCALE-001-baseline/{env.json,scenarios.jsonl,trials.jsonl,requests.jsonl,summary.json,diag_client_construction.json}` | raw evidence (about 7.8 MB) |
| `benchmarks/results/SCALE-001-baseline/server/` | per-scenario uvicorn stdout and app run logs (diagnostic, about 14 MB; see the commit notes below) |
| `eval/tests/test_benchmarks.py` | 18 harness tests |
| `docs/scalability/SCALE-001_BASELINE.md` | baseline report and Decision Gate A |
| `docs/review/REVIEW_BUNDLE__SCALE-001-capacity-characterization.md` | this file |

Modified:

- `docs/CURRENT_STATE.md`: the date line, plus a new "Added in SCALE-001" entry.
  Historical entries are untouched.

Incidental, produced by the ticket's required `python -m eval.run_eval --mode demo`:

- `eval/results/run_20260924T074538Z.jsonl`
- `eval/results/summary_20260924T074538Z.md`

Earlier tickets committed their eval artifacts. Whether to keep these is the
owner's call.

**Commit notes (for the owner):**

- Recommended to commit: the `benchmarks/` code, the six top-level result files
  and the docs.
- `benchmarks/results/SCALE-001-baseline/server/` is bulky diagnostic output
  (app run logs and access logs), and `stats --check` doesn't need it. I'd
  suggest leaving it uncommitted, but I didn't change `.gitignore` because
  that is outside the ticket's file allow-list.

## Acceptance criteria with evidence

| # | Criterion | Evidence |
| --- | --- | --- |
| 1 | Reproducible zero-cost harness | `benchmarks/`; one command reproduces the run; `stats --check` → `summary.json matches recomputation: True` |
| 2 | No billed OpenAI call | Server env is built with a sentinel key, sentinel model and loopback `OPENAI_BASE_URL`, and inherited `OPENAI_*` is stripped. 60/60 fake trials reconciled (fake attempts = logged `provider_attempts`). `backend/.env` holds no API key (key names inspected, values never read). |
| 3 | No production deployment load-tested | The harness has no target-URL option. The servers it launches bind 127.0.0.1. `grep` for `api.openai.com\|railway.app\|vercel.app` in `benchmarks/*.py` finds nothing. |
| 4 | Real localhost HTTP for Demo | uvicorn subprocess plus `http.client`; see `scenarios.jsonl` `server_argv` |
| 5 | Fake path enters via `POST /analyze` in OpenAI mode | `QUOTECHECK_USE_OPENAI=1` in `scenarios.jsonl` `env_overrides`; app logs record `analyzer: "openai"` with `provider_attempts` |
| 6 | Fake cannot reach real OpenAI | loopback assertion (`assert_loopback_url`), sentinel key/model, proxy stripping, warm-up attempt check, per-trial reconciliation; tests in `SafetyTests` |
| 7 | Deterministic, reusable workloads | `benchmarks/workloads.py`; sha256 in `env.json`; the `normal` hash is pinned by a test |
| 8 | Warm-up separated | 20 (Demo) or 5 (fake) sequential requests, plus 2×C per point, never written to `requests.jsonl`; counts in `scenarios.jsonl` |
| 9 | Repeated trials | 3 trials at every point (144 trials) |
| 10 | Raw machine-readable evidence | `requests.jsonl` (21,696 measured requests), `trials.jsonl`, `scenarios.jsonl`, `env.json` |
| 11 | Demo: success/failure, throughput, p50, p95, max | baseline report, Demo tables |
| 12 | Fake: plus attempts and peak in flight | baseline report, fake tables |
| 13 | p99 omitted unless justified | the largest pooled n is 768, below the 1,000 threshold, so no p99 anywhere |
| 14 | At least two latency classes | 250 ms and 1 s, each at C = 1, 2, 4, 8, 16, 32, 48, 64 |
| 15 | Transient-failure → success scenario | `retry_fail_first_250ms` at C = 1, 8, 32 (all 200, all `provider_attempts=2`), plus a `fail_always` bound check (all 503, exactly 2 attempts) |
| 16 | Saturation knee stated | "A clear saturation knee was observed" (Demo at C≈1–2; fake 250 ms between C=16 and 32) |
| 17 | Fact / inference / hypothesis separated | baseline report, "Bottleneck assessment" |
| 18 | Best-supported bottleneck identified | per-request client construction; then the implicit 40-thread cap |
| 19 | Report ends with Decision Gate A | final section of `SCALE-001_BASELINE.md` |
| 20 | Unit/regression tests healthy | 162 tests, OK |
| 21 | Corpus validation healthy | `OK — 27 cases, 6 domains, 9 categories, 0 errors.` |
| 22 | Demo eval at baseline | `27/27 schema-valid; 24/27 deterministic cases pass.`; failing cases exactly AUTO-004, CONT-003, HVAC-003 |
| 23 | No runtime architecture change | only new benchmark, test and doc files |
| 24 | No protected file modified | the protected `git diff` is 0 bytes, and there are no untracked files under `backend/`, `frontend/` or `railpack.json` |
| 25 | No new dependency | stdlib only, plus the already-installed openai/httpx/certifi/fastapi; `backend/requirements.txt` unchanged |
| 26 | `main`, `v0-closed` and deployment untouched | `git rev-parse main v0-closed` → both `2ff1cff…` |
| 27 | Review bundle with exact commands and outputs | this file |
| 28 | Nothing committed or merged | `git status` shows only uncommitted changes; HEAD is still `484720d` |

## Commands run and real results

Environment: conda env `quotecheck` (`/home/akshay/miniconda3/envs/quotecheck/bin/python`, Python 3.11.14), repo root.

```bash
git branch --show-current                 # task/SCALE-001-capacity-characterization
git rev-parse HEAD                        # 484720d0f4e33cd0480426a037592dab0078bea2
git rev-parse v1/scalability              # 531853b39dd919f56133580c88a082cb0c5ec045 (= merge-base)
```

Harness smoke runs (`--quick`, not evidence; directories deleted afterwards):

```bash
python -m benchmarks.run_capacity --quick --run-id quick-smoke1   # completed; exposed host suspend (see Repair iterations)
python -m benchmarks.run_capacity --quick --run-id quick-smoke2   # completed; all trials reconciled; stats --check True
```

Baseline attempt 1 (failed; directory discarded):

```bash
python -m benchmarks.run_capacity --experiment all --run-id SCALE-001-baseline
# ... demo_analyze_short and demo_analyze_normal completed ...
# RuntimeError: warm-up failures in demo_analyze_near_max
# (the app log shows failure_category "internal_error", cause_type "ValidationError": Out-of-scope finding 1)
```

Baseline (the evidence run):

```bash
python -m benchmarks.run_capacity --experiment all --run-id SCALE-001-baseline
# exit 0; elapsed 434.5 s; every ladder executed fully; stopped_by None everywhere; host_safety_guard None
python -m benchmarks.diag_client_construction --out benchmarks/results/SCALE-001-baseline/diag_client_construction.json
# openai_client threads=1 ops/s=48.0 cpu_ms/op=20.31; threads=32 ops/s=40.4 cpu_ms/op=755.36 cores_busy=30.54
# OpenSSL 3.0.19 27 Jan 2026
python -m benchmarks.stats benchmarks/results/SCALE-001-baseline --check
# summary.json matches recomputation: True
```

Tallies computed from the raw evidence (the baseline report's tables are generated from `summary.json`):

```text
demo_http   200: 16800
fake_provider 200: 4320
retry       200: 528   503 provider_unavailable: 48
fake/retry trials 60, reconciled 60
retry requests 576, provider_attempts == 2 for all 576
max server RSS 387 MB, max open fds 360; suspend_suspected 0 of 144 trials
```

Tests and eval:

```bash
python -m unittest eval.tests.test_benchmarks -v
# Ran 18 tests in 1.334s — OK

python -m unittest discover -s eval/tests -p 'test_*.py' -v
# Ran 162 tests in 2.463s — OK      (v0 baseline 144 + 18 new)

python -m eval.run_eval --validate-only
# OK — 27 cases, 6 domains, 9 categories, 0 errors.

python -m eval.run_eval --mode demo      # exit 1, as expected (known gaps retained)
# 27/27 schema-valid; 24/27 deterministic cases pass.
# failing case_ids from eval/results/run_20260924T074538Z.jsonl: AUTO-004, CONT-003, HVAC-003
```

Final git checks:

```bash
git status --short
#  M docs/CURRENT_STATE.md
# ?? benchmarks/
# ?? docs/scalability/
# ?? docs/review/REVIEW_BUNDLE__SCALE-001-capacity-characterization.md
# ?? eval/results/run_20260924T074538Z.jsonl
# ?? eval/results/summary_20260924T074538Z.md
# ?? eval/tests/test_benchmarks.py
git diff --check                          # no output, exit 0
git diff --stat                           # docs/CURRENT_STATE.md | 47 ++++++++++++++++++++++++++++++++++++++++++++++-
git diff -- backend/app.py backend/core/openai_analyzer.py backend/core/stub_analyzer.py \
  backend/core/schema.py backend/core/config.py backend/core/errors.py backend/core/prompt.py \
  backend/core/run_logger.py frontend railpack.json backend/requirements.txt   # empty (0 bytes)
git rev-parse main v0-closed              # 2ff1cff8… / 2ff1cff8… (untouched)
```

(`git diff` doesn't cover untracked files. The new files were checked
separately: no trailing whitespace, and all of them `py_compile` cleanly.)

## Deviations from the approved plan (all within scope)

1. **Logging A/B not run.** This follows the owner's adjustment. The evidence
   doesn't implicate logging: Demo logs every request at 600–950 rps with
   about 1–2 ms total server CPU per request, flat across C.
2. **Host-safety guards are separate from capacity interpretation**, as the
   owner asked. None fired.
3. **Escalation guard changed from "p95 > 10× the C=1 p95" to "p95 > 30 s
   absolute, or any failure at the previous point".** On a saturated
   closed-loop system, latency rises linearly with C by Little's law, so the
   10× rule would have stopped the Demo ladder exactly where the curve becomes
   informative. The ladders are bounded at 64 anyway.
4. **Suspend detection added** after the first smoke run showed a roughly
   75-minute wall-clock gap during a 14.5 s (monotonic) run. The host or VM was
   suspended, and `perf_counter` excludes suspended time. Every trial now
   records wall-vs-monotonic skew and is flagged at > 1 s. No baseline trial
   was flagged; the maximum skew was 0.83 s.
5. **`near_max` workload made single-trade** after the multi-trade version hit
   Out-of-scope finding 1. Length scaling, not that defect, is what the fixture
   is for.
6. **Focused client-construction diagnostic added** (`benchmarks/diag_client_construction.py`).
   The main evidence pointed at pre-loop work, and a benchmark-only module
   makes that inference reproducible. It changes no runtime code.

## Known limitations

- These are single-host numbers (WSL2, 32 vCPU). The load client and fake
  provider share the host with QuoteCheck, which itself burned up to 23.5
  cores at high C, so some cross-process contention plausibly inflates the
  high-C figures.
- The closed-loop generator under-represents open-arrival queueing (coordinated
  omission).
- Real TLS, DNS, and realistic multi-second structured-output latency are
  absent. Fake latencies stop at 1 s.
- Each scenario uses an ascending ladder in one warm process, so order effects
  aren't randomized.
- `near_max` exercises input-side cost only, because the Demo analyzer's output
  is the same size as for `normal`.
- Demo-mode server-reported latency is ~0 by construction (finding 2), so Demo
  client latency can't be decomposed server-side without a runtime change.
- The `/proc` sampler runs at 100 ms, so very short trials can under-report
  peaks. That affects only the fastest Demo points, not the conclusions.

## Out-of-scope findings (recorded, not fixed)

1. **QuoteCheck defect: Demo analyzer → HTTP 500 on multi-trade quotes.**
   - `analyze_quote_stub` can emit more `verification_questions` than the
     schema's `max_length=8`. `QuoteCheckResult` validation then raises, and
     `/analyze` returns `500 internal_error` (`cause_type: ValidationError`) for
     a valid quote well under the 12,000-char limit.
   - Minimal repro (127 chars; 9 questions → fail):
     `"Brake pad replacement. AC gas top-up. Leaking tap valve replacement. Panel earthing check. Compressor overhaul after diagnosis."`
     A 122-char variant produced 12 questions.
   - The public Demo runs this analyzer, so the hosted deployment is plausibly
     affected (not verified against it, per safety rules).
   - Suggested for its own ticket: cap or dedupe questions in the stub, plus a
     corpus case.
2. **Demo `latency_ms` measures nothing.** `backend/app.py:193` computes
   `latency_ms` before `analyze_quote_stub` runs, so the Demo response metadata
   and the run log always report about 0 ms.
3. **Per-request `OpenAI` clients are never closed.** Open fds scaled with C
   (about 360 at C=64) and stayed bounded in these short runs. Long-run
   behaviour is untested.
4. **`/health` shares the anyio threadpool with `/analyze`** (both are sync
   `def`). A saturated analyze load could delay health checks, which matters
   for platform health probes. This is untested: the health ladder ran on an
   idle server.
5. **Local uvicorn auto-selects uvloop/httptools**, which production doesn't
   have. Local ad-hoc measurements taken without `--loop asyncio --http h11`
   would not match the deployment shape.

## Dependency changes

None. The harness uses the stdlib plus packages already installed via
`backend/requirements.txt` (openai, httpx, certifi as the SDK's transitive
dependency, fastapi/starlette for the in-process test).

## Architectural observations

- **API capacity and model-execution capacity are coupled today.**
  - The same anyio threadpool (40 tokens) carries every sync route and every
    blocking provider call.
  - So the effective aggregate provider-concurrency bound is 40 by accident of
    a library default, not by design, and requests beyond it queue invisibly
    in-process with no rejection signal.
- **Retry amplification is per-request bounded but aggregate-unbounded.**
  Retries multiply attempts (2× under transient failure) and hold the worker
  thread for both attempts. The only aggregate limit is the same 40-thread cap.
- **The first constraint is local CPU, not provider latency.** Per-request
  client construction dominates the OpenAI path's CPU cost: about 20 of the
  roughly 22 ms per request at C=1, and up to about 580 ms per request under
  contention.
- **Decision Gate A:**
  - The smallest justified next change is a candidate ticket to reuse one
    OpenAI client per process, measured before and after with this harness.
  - That ticket must reason about the httpx pool limits a shared client
    introduces (a new implicit bound).
  - An explicit provider-concurrency or overload policy should follow only
    after that, with evidence from multi-second fake latencies.
  - No queue, worker, replica or async rewrite is justified by current
    evidence.

## CodeFactory observations

- **Repo truth recovery:** Correct. Branch, base and HEAD were verified
  against `v1/scalability`. The key runtime facts were read directly from
  code:
  - import-time config;
  - `load_dotenv(override=False)`;
  - per-request client construction;
  - the pre-stub Demo `latency_ms`;
  - anyio's 40-token default limiter (verified in the installed anyio source);
  - the local uvloop/httptools vs Railway plain-uvicorn difference.

  `backend/.env` key names were inspected without reading values; it contains
  no API key.
- **Scope adherence:** The plan stayed inside the ticket's allowed files. No
  runtime seam, dependency, or scaling mechanism was introduced. The one
  architectural choice with seam-like implications (the network-level fake via
  the SDK's existing `OPENAI_BASE_URL`, in place of the QC-4 in-process mock)
  was surfaced and approved before implementation.
- **Unnecessary architecture:** None attempted. Client reuse, limiters and
  logging changes are recorded as candidates only.
- **Validator findings:** None; no external validator ran on this ticket. The
  harness's own reconciliation checks and `stats --check` all passed.
- **Repair iterations:**
  1. A lock-access expression in `FakeProviderState.configure` was simplified
     before first use.
  2. A host-suspend artifact in the first smoke run led to adding suspend
     detection.
  3. The first baseline attempt aborted on the Demo 500 defect. The `near_max`
     fixture was rebuilt as single-trade, and the defect was recorded as
     finding 1.

  Each was caught by the harness's own fail-closed checks rather than
  silently absorbed.
- **Manual intervention:**
  - The owner adjusted the approved plan (guards not to be treated as
    saturation evidence; no default logging A/B).
  - The session was interrupted once mid-run ("try again" / "retry"). The
    interrupted smoke run's data wasn't used.
- **Ticket ambiguity:**
  - The ticket's example Uvicorn command omits `--loop/--http`. Deployment
    fidelity required pinning asyncio/h11 (approved).
  - The ticket suggests "reuse the QC-4 pattern" for the fake provider, but
    that pattern can't exercise uvicorn, the shared threadpool, or real client
    construction (approved deviation).
  - Classification: **Ticket/control defect (minor)** for both. Separately,
    finding 1 is a **QuoteCheck defect**.
