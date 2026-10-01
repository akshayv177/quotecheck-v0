# REVIEW BUNDLE — SCALE-003 Saturation, Queueing & Health Characterization

- Ticket: `docs/tickets/SCALE-003-saturation-health-characterization.md`
- Report and Decision Gate C: `docs/scalability/SCALE-003_SATURATION.md`
- Branch: `task/SCALE-003-saturation-health-characterization`, from `v1/scalability` @ `e8bdce7`. It merges back into `v1/scalability`, never `main`. Nothing is committed yet.
- Risk class: T3, measurement only. Provider spend ₹0. No OpenAI credential was used, and the public deployment was never contacted.

## Scope summary

1. **Repaired the fake provider's reused-connection Nagle artifact.** `TCP_NODELAY` is now set on accepted sockets, with deterministic tests and a runtime before/after diagnostic. There is deliberately no latency-threshold unit test, per the approval note.
2. **Added benchmark-only per-attempt timelines.** The fake logs monotonic attempt times by marker. The harness joins them to client times on the shared `CLOCK_MONOTONIC`, and splits each request into pre-provider, provider and post-provider phases.
3. **Added three experiments:**
   - `saturation`: 1/3/5 s × C = 16–64, plus C=1 at 1 s;
   - `health`: idle control plus C = 32/40/64 at 3 s and 5 s, 40 probes each, saturation-gated, with each probe tagged by exact provider in-flight at send;
   - `retry_sat`: fail-first at 3 s × C = 32/40/64, plus a fail-always spot check at 3 s, C=64.
4. **Ran the evidence run.** Wrote the report and Decision Gate C, and updated `benchmarks/README.md` and `docs/CURRENT_STATE.md`.

**No runtime change.** `git diff v1/scalability -- backend/ frontend/` is empty (0 lines).

## Files changed

| file | change |
|---|---|
| `benchmarks/fake_provider.py` | `TCP_NODELAY` in `get_request` (`tcp_nodelay=True` default; `False` for the diagnostic only). Per-attempt log in `FakeProviderState` (`begin(marker)`, `end(seq, status)`, `attempts()`, cleared by `reset`). `GET /__attempts`. Marker parsing moved before `begin` so the attempt is labelled. The `begin()`/`end()` no-arg call shape still works. |
| `benchmarks/diag_keepalive.py` (new) | Reused-connection latency diagnostic: SDK shared client, SDK fresh client and raw keep-alive, each with the fake's `TCP_NODELAY` off and on |
| `benchmarks/run_capacity.py` | `clocks_shared()` with a fail-closed start check; clocks and harness sha256 in `env.json`; `run_load(clock_out=)`; `FakeProviderProcess.attempts()`; `Run.scenario(join_attempts=)` → `_join_attempts` (phases, `attempts_joined`, provider occupancy); `Run.health` / `_health_point` / `_probe_series` / `_record_probes`; the SCALE-003 plan and `run_saturation` / `run_health` / `run_retry_sat`; CLI choices (`all` unchanged); `health_summary.json` output |
| `benchmarks/stats.py` | `in_flight_at`, `mean_in_flight`, `time_frac_at_least`, `decompose_request`, `summarize_health`; optional `phase_latency` / occupancy fields, only when the raw records carry them; `--check` also verifies `health_summary.json` |
| `eval/tests/test_benchmarks.py` | 11 new tests (below). No existing test changed or removed. |
| `benchmarks/README.md` | Fake-repair and provenance note, SCALE-003 experiments, commands and outputs, file table |
| `docs/CURRENT_STATE.md` | "Changed in SCALE-003" section; date line |
| `docs/tickets/SCALE-003-saturation-health-characterization.md` (new) | The ticket |
| `docs/scalability/SCALE-003_SATURATION.md` (new) | The report and Gate C |
| `benchmarks/results/SCALE-003-saturation/` (new) | Raw evidence, 20 MB: `server/` 11 MB, `requests.jsonl` 4.4 MB, `provider_attempts.jsonl` 3.8 MB. Also `diag_keepalive.json`, `report_tables.py` and `report_tables.out`, and `run_console.log`. |

**New tests:**
- `FakeProviderTransportTests`:
  - `test_accepted_sockets_have_tcp_nodelay`;
  - `test_tcp_nodelay_can_be_disabled_for_the_diagnostic_only`;
  - `test_persistent_connection_is_reused` (5 attempts, 1 connection).
- `FakeProviderAttemptLogTests`:
  - `test_state_logs_marker_times_and_status`;
  - `test_http_fail_first_attempts_are_logged_per_marker`;
  - `test_clock_used_by_the_fake_is_the_harness_clock`.
- `TimelineStatsTests`:
  - half-open in-flight;
  - mean in-flight and time at level;
  - retry decomposition;
  - the health summary's exact at-40 subset and timeout counting;
  - phase fields appearing only when present.

## Acceptance criteria with evidence

| # | criterion | evidence | result |
|---|---|---|---|
| 1 | Fake artifact repaired and validated | `diag_keepalive`: shared-SDK reused-connection p50 43.98 → **1.00** ms, raw keep-alive 44.01 → 0.37 ms, still 1 connection. Runtime 1 s/C=1 loop p50 is 1013 ms (SCALE-002-after 1052, SCALE-001 1007). Deterministic tests pass. Every trial reconciled and joined. | ✅ |
| 2 | Multi-second saturation evidence | 1/3/5 s × C = 16, 32, 40, 48, 64 (+ C=1 at 1 s), 3 trials each (2 at two points after suspend exclusion). Throughput, e2e and loop latency, pre/post waiting, peak and mean in-flight, threads, CPU, RSS, fds and connections (report §4). | ✅ |
| 3 | Health under saturation | 320 probes: idle, C = 32/40/64 × 3 s/5 s. All probes and the exact provider-in-flight == 40 subset. Saturation gated on the fake. Every probe had C analysis requests outstanding (report §5). | ✅ |
| 4 | Retry under saturation | Fail-first 3 s × C = 32/40/64 vs success: 0.51–0.52× throughput, 2× latency, exactly 2 attempts. Fail-always C=64: 384 × 503, 2 attempts each (report §6). | ✅ |
| 5 | Runtime unchanged | `git diff v1/scalability -- backend/ frontend/ \| wc -l` → `0` | ✅ |
| 6 | Regression | 183 tests OK; validate-only OK; Demo 27/27 schema-valid, 24/27 passing, residuals AUTO-004, CONT-003, HVAC-003 | ✅ |

## Exact commands run, with real results

```bash
# conda env quotecheck (python 3.11); repo root
git checkout -b task/SCALE-003-saturation-health-characterization   # from v1/scalability @ e8bdce7

python -m benchmarks.diag_keepalive          # first run, during development
# sdk_shared False 1 conn p50 43.98 / True 1.06; raw_keepalive False 44.0 / True 0.36

python -m benchmarks.stats benchmarks/results/SCALE-001-baseline --check   # summary.json matches recomputation: True
python -m benchmarks.stats benchmarks/results/SCALE-002-before --check     # True
python -m benchmarks.stats benchmarks/results/SCALE-002-after --check      # True

# smoke runs (scratchpad, not evidence)
python -m benchmarks.run_capacity --quick --experiment saturation health retry_sat --run-id <scratch-abs-path>/smoke1
#   -> attempt join / fail-first reconciliation WARNINGs: an absolute --run-id put '/' into
#      markers, which MARKER_RE rejects (fail-closed caught it). Fixed by using run_dir.name for
#      SCALE-003 markers. The same latent issue exists in the pre-existing run_retry (out of scope).
python -m benchmarks.run_capacity --quick --experiment saturation health retry_sat --run-id <scratch>/smoke2
#   -> no warnings; stats --check True for summary and health_summary
python -m benchmarks.run_capacity --quick --run-id <scratch>/smoke_old          # SCALE-001 set; stats --check True
python -m benchmarks.run_capacity --quick --experiment retry --run-id zz-smoke-old-tmp   # clean; dir deleted
# plus an ad hoc 0.5 s health pre-check at C=40/64 (12 probes) via Run.health in the scratchpad

python -m unittest eval.tests.test_benchmarks -v
# Ran 30 tests in 1.006s — OK

# evidence
python -m benchmarks.run_capacity --experiment saturation health retry_sat \
    --run-id SCALE-003-saturation --ticket SCALE-003
# elapsed 1784.2 s; host_safety_guard None; 3 trials flagged suspend_suspected (excluded in report)
python -m benchmarks.diag_keepalive --out benchmarks/results/SCALE-003-saturation/diag_keepalive.json
# sdk_shared False: 1 conn p50 43.98 p95 44.91 | True: 1 conn p50 1.0 p95 1.48
# sdk_fresh  False: 35 conns p50 1.93         | True: 35 conns p50 1.84
# raw_keepalive False: p50 44.01              | True: p50 0.37
python -m benchmarks.stats benchmarks/results/SCALE-003-saturation --check
# summary.json matches recomputation: True
# health_summary.json matches recomputation: True
(repeat --check on SCALE-001-baseline, SCALE-002-before, SCALE-002-after)   # all True
PYTHONPATH=. python benchmarks/results/SCALE-003-saturation/report_tables.py \
    > benchmarks/results/SCALE-003-saturation/report_tables.out

# regression
python -m unittest discover -s eval/tests -p 'test_*.py' -v
# Ran 183 tests in 1.740s — OK        (172 + 11 new)
python -m eval.run_eval --validate-only
# OK — 27 cases, 6 domains, 9 categories, 0 errors.
python -m eval.run_eval --mode demo
# 27/27 schema-valid; 24/27 deterministic cases pass.  (non-zero exit by design)
# Failed cases in eval/results/summary_20260928T094608Z.md: AUTO-004, CONT-003, HVAC-003

git diff v1/scalability -- backend/ frontend/ | wc -l     # 0
```

`env.json` for the evidence run:
- `clocks`: both `clock_gettime(CLOCK_MONOTONIC)`; `clocks_shared: true`;
- `git_commit e8bdce7`, `git_dirty: true`;
- `harness_sha256`:
  - `run_capacity.py` 86fdedd7…;
  - `fake_provider.py` 9f35ae00…;
  - `stats.py` c6c5953e…;
  - `workloads.py` ef8e426a….

## Headline results (details in the report)

- **Throughput above the limit.** Throughput plateaus at about 40 / provider latency (34.5 / 12.6 / 7.75 rps at C=40) and dips 2–6% at C=64. Excess demand turns into silent waiting of 0.70 / 1.81 / 2.90 s mean at C=64, with 0 failures.
- **Waiting after the provider call.** About 20% of requests at C=64 wait more than half a provider period *after* their provider call finished. This is the second worker-token acquisition for `response_model` validation (and for the sync exception handler on failure) in the same FIFO limiter.
- **`/health` at C ≥ 40.** All 200, but p95 is 2.4–2.8 s (3 s provider) and 4.4–4.7 s (5 s provider). At C=40 it completes 1–18 ms after the next provider completion. At C=32 it is unaffected (≤ 3.2 ms p95).
- **Retry.** A fail-first retry halves throughput (0.51–0.52×) and doubles latency. Fail-always at C=64 gives 503s after a p50 of 11.8 s, exactly 2 attempts.

## Known limitations

- One WSL2 host with the client, QuoteCheck and the fake all on it; loopback HTTP only; closed-loop load, which synchronizes requests into waves (open arrivals would change the wait *distribution*).
- Three trials were excluded as `suspend_suspected` (skews +933 s, +3339 s, −1.1 s), leaving two points with 2 trials. Their values match sibling trials.
- Worker-token occupancy is **inferred** (limiter size, thread count, timing link), not observed directly. Provider in-flight == 40 is observed.
- Health used 40 probes per point, so p95 is rank 38 of 40, and the at-40 subsets are 17–24 probes.
- The fake is a single-process Python `ThreadingHTTPServer`. It contributes an unattributed ~60–95 ms loop inflation at C ≥ 32.
- Nothing here measures real OpenAI latency or rate limits, Railway resources, or platform health-check timeouts.
- The evidence was produced from an uncommitted tree. File hashes are recorded instead.

## Out-of-scope findings (recorded, not fixed)

1. **Pre-existing harness bug.** `run_retry` builds markers from `--run-id`. An absolute or `/`-containing run-id produces markers `MARKER_RE` rejects, so fail-first never injects failures. Reconciliation catches it and prints WARNING rather than failing silently. SCALE-003 experiments use `run_dir.name`. The old path was left unchanged, because changing it would alter SCALE-001 tooling behaviour.
2. **Response-path token re-acquisition.** `response_model` validation (FastAPI, sync endpoint) and the sync `QuoteCheckError` handler each take a second anyio token. This is an architectural observation for Gate C, not a defect fixed here.
3. **httpx keep-alive expiry under saturation.** With waits above 5 s, pooled provider connections idle past `keepalive_expiry = 5.0` s and are replaced (6–31 new per trial at 5 s / C ≥ 48 and in retry C=64). On the real TLS path that means reconnects under saturation. Unmeasured.
4. **Transient 42–43 peak threads at C=48.** Plausibly anyio's idle-worker turnover (`MAX_IDLE_TIME = 10`). Not investigated.

## Dependency changes

None. Stdlib only (`hashlib`, `random`, `socket` added as imports).

## Architectural observations

- **The shared resource.** The binding resource is anyio's process-wide default `CapacityLimiter(40)`, with FIFO waiters. It is shared by:
  - analysis endpoint execution, held for the full provider time and any retry;
  - response validation;
  - sync exception handling;
  - `/health`.

  It is a framework default, not a QuoteCheck budget.
- **The failure mode.** Unbounded, silent, latency-only degradation proportional to provider latency, with a slight throughput loss. There is no overload signal and no log field for waiting. Resources (CPU ≤ 0.19 cores, RSS ≤ 96 MB, fds ≤ 113) are nowhere near limits.
- **Gate C requirements (derived, not implemented):**
  - an explicit provider-concurrency budget;
  - bounded and observable overload behaviour (bounded wait or controlled rejection; the evidence does not prefer one);
  - retry attempts accounted against the budget;
  - a signal for waiting/rejection.

  `/health` isolation is a separate, smaller candidate. The response-path re-queue should be evaluated against the pre/post split with this same harness.
- **Not justified:** raising the thread limit, more workers or replicas, async conversion, queues, Redis.

## Incidental files

`eval/results/{run,summary}_20260928T094608Z.*` from the Demo eval run. Not intended for commit, following SCALE-001/002 practice.
