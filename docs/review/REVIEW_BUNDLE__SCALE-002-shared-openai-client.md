# REVIEW BUNDLE — SCALE-002 Shared OpenAI Client + Recharacterization

- Ticket: `docs/tickets/SCALE-002-shared-openai-client.md`
- Report: `docs/scalability/SCALE-002_SHARED_CLIENT.md`
- Branch: `task/SCALE-002-shared-openai-client`, from `v1/scalability` @ `4e33bfc`. Nothing is committed on the task branch.
- Risk class: T3 (architecture-sensitive). Provider spend: **₹0**. No real OpenAI call was made, and the public deployment was not contacted.

## Scope summary

- **Pre-step (approved):** `v1/scalability` had an in-progress, conflicted merge of `main` (QC-HOTFIX-demo-question-bound).
  - I resolved the `docs/CURRENT_STATE.md` conflict by keeping both sections, newest first. The date line took main's value.
  - I committed the result as `4e33bfc Merge branch 'main' into v1/scalability`.
  - The suite ran 166 tests OK before the commit.
- **Runtime:** one process-wide synchronous `OpenAI` client in `backend/core/openai_analyzer.py`.
  - It is built lazily, behind a double-checked `threading.Lock`, only after the existing API-key and timeout validation passes.
  - The constructor arguments are unchanged.
  - Everything after the client is obtained is byte-identical: retry loop, classification, `provider_attempts`, response-state handling, metadata, validation.
- **Tests:**
  - Shared-state isolation that explicitly **closes** any built client before resetting the singleton. Tests don't rely on GC.
  - New lifecycle tests.
  - A real-SDK loopback connection-reuse test.
  - A Demo "no client built" assertion.
- **Benchmark provenance:** `env.json` now records `harness_origin` = SCALE-001 and `measurement_ticket` (via `--ticket`). This was done before the *before* run. No measurement logic changed.
- **Evidence:**
  - fresh `SCALE-002-before` (fake + retry, pre-change code);
  - `SCALE-002-after` (all experiments);
  - before/after/SCALE-001 comparison;
  - a keep-alive diagnostic;
  - the Decision Gate B report.

## Files changed

| File | Change |
|---|---|
| `backend/core/openai_analyzer.py` | `_client`, `_client_lock` and `_get_client()`. The call site `OpenAI(...)` becomes `_get_client(timeout_seconds)`, and a docstring section was added (+33/−2). |
| `benchmarks/run_capacity.py` | Metadata only: `TICKET` becomes `HARNESS_ORIGIN`, and `env.json` gets `harness_origin` + `measurement_ticket` in place of `ticket`. Adds the `--ticket` flag. |
| `eval/tests/test_openai_reliability.py` | `isolated_shared_client()` (close, then reset); `patched_openai` starts cold; the config-error helper asserts no client is built; `counting_openai` + `SharedClientLifecycleTests` (5 tests). |
| `eval/tests/test_benchmarks.py` | `_post` becomes `_post_many`, wrapped in `isolated_shared_client()`; new `test_shared_client_reuses_one_connection_across_requests`. |
| `eval/tests/test_deployment_readiness.py` | `demo_mode_app` resets `_client`; the Demo test asserts `_client is None`. |
| `docs/tickets/SCALE-002-shared-openai-client.md` | new ticket |
| `docs/scalability/SCALE-002_SHARED_CLIENT.md` | new report, including Decision Gate B |
| `docs/review/REVIEW_BUNDLE__SCALE-002-shared-openai-client.md` | this file |
| `docs/CURRENT_STATE.md` | "Changed in SCALE-002" section; the analyzer architecture bullet; date line |
| `benchmarks/README.md` | SCALE-002 pointer and commands; `--ticket` and provenance note; known fake-provider artifact |
| `benchmarks/results/SCALE-002-before/`, `benchmarks/results/SCALE-002-after/` | new raw evidence. Following the SCALE-001 convention, only `env.json`, `scenarios.jsonl`, `trials.jsonl`, `requests.jsonl` and `summary.json` are intended for commit. `server/` holds diagnostic uvicorn and app logs (4.2 MB / 14 MB), and SCALE-001 did not commit its equivalent. |

**Unchanged:** `backend/app.py`, `backend/core/config.py`, errors, prompt, schema, the frontend, deployment config, `requirements.txt`, `benchmarks/results/SCALE-001-baseline/`, and all harness measurement logic.

Incidental untracked files: `eval/results/{run,summary}_20260928T071214Z.*` from the Demo eval run. They are not intended for commit; SCALE-001 left its equivalents uncommitted too.

## Acceptance criteria with evidence

| # | Criterion | Evidence | Result |
|---|---|---|---|
| 1a | Multiple analyses in one process reuse one client | `test_sequential_analyses_reuse_one_client`: 1 construction, 2 `create` calls, same object. Real SDK: `test_shared_client_reuses_one_connection_across_requests` shows 3 `/analyze` requests, 3 attempts, **1** TCP connection. Benchmark: in every *after* fake/retry trial, the fake accepted exactly 1 connection, and that one was the harness stats call. | Met |
| 1b | Simultaneous cold requests build exactly one client | `test_concurrent_cold_start_constructs_exactly_once`: 16 threads behind a barrier, 50 ms construction delay, 1 construction, 16 successes. 20/20 repeated runs OK. With the lock mutated away, this test **fails** (see Commands). | Met |
| 2 | Reliability semantics unchanged | Every pre-existing QC-4 test passes unmodified in its assertions: 1 attempt on success; transient → 2; two transients stop at 2; 429 → 1 attempt, not retried; auth/bad-request → `configuration_error` with 1 call; refusal/incomplete/invalid → 1 call; `max_retries=0` and the timeout (default and 12.5 override) reach the constructor; schema-invalid output → `invalid_model_output`. New: `test_retry_uses_the_shared_client`. Benchmark: fail-first gives exactly 2 attempts per request and fail-always gives 2 attempts and 503; every trial reconciled. | Met |
| 3a | Demo: no provider call, no credential | `test_openai_client_is_never_constructed_in_demo_mode` (key `None`): ctor not called, `_client is None`. All 16,800 *after* Demo benchmark requests returned 200. | Met |
| 3b | OpenAI mode + invalid config → `configuration_error`, no provider request | All 7 `ConfigurationTests` now also assert `_client is None`. `test_cached_client_does_not_bypass_configuration_checks`: even with a client already cached, a missing key or a zero timeout raises `configuration_error` and makes no `create` call. | Met |
| 4 | Same methodology rerun | Unchanged harness code for both runs. Topology, loop/http, ladders, N rules, trials and stats identical. `stats --check` True on both runs. | Met |
| 5 | Before/after comparison with fact/inference/hypothesis | Report "Headline comparison", "Capacity curve", full tables (throughput, p50/p95/max, failures, CPU, CPU/req, attempts, peak in-flight, conns/req, threads, RSS, fds). | Met |
| 6 | Pool defaults recorded, not tuned | Report "Connection-pool facts" (SDK `_constants.py:11`, httpx `keepalive_expiry` 5.0, `Timeout(30.0)` includes the pool timeout, httpcore `has_expired`). No limits changed. | Met |
| 7 | Regression | 172 tests OK; `--validate-only` OK (27 cases); Demo eval 27/27 schema-valid, 24/27 pass, failing AUTO-004 / CONT-003 / HVAC-003. | Met |
| Gate B | A/B/C/D answered | Report "Decision Gate B" | Met |

## Commands run and real results

All commands ran from the repo root in conda env `quotecheck` (Python 3.11.14).

```text
# pre-step
git add docs/CURRENT_STATE.md && git commit   # 4e33bfc (amended once to add attribution trailer)
python -m unittest discover -s eval/tests -p 'test_*.py'
# Ran 166 tests in 1.649s — OK
git checkout -b task/SCALE-002-shared-openai-client

# fresh before control (pre-change analyzer; provenance edit already applied)
python -m benchmarks.run_capacity --experiment fake retry --run-id SCALE-002-before --ticket SCALE-002
# exit 0; elapsed_s 362.3; every trial reconciled; no guard fired;
# 2 trials suspend_suspected (skew -1.004 s fake_lat1s C=48 t1; -1.097 s retry_fail_first C=1 t2)

# focused tests after implementation
python -m unittest eval.tests.test_openai_reliability eval.tests.test_benchmarks eval.tests.test_deployment_readiness
# Ran 92 tests in 1.687s — OK

# mutation checks (analyzer temporarily edited, then restored byte-identical; cmp OK)
#  no lock:                  FAIL test_concurrent_cold_start_constructs_exactly_once
#  per-request construction: FAIL test_concurrent_cold_start..., FAIL test_sequential_analyses_reuse_one_client,
#                            ERROR test_isolation_closes..., ERROR test_shared_client_reuses_one_connection...
for i in 1..20: python -m unittest eval.tests.test_openai_reliability.SharedClientLifecycleTests
# 20 × OK
python -X dev -W always::ResourceWarning -m unittest eval.tests.test_benchmarks eval.tests.test_openai_reliability
# 0 ResourceWarning lines

# after
python -m benchmarks.run_capacity --experiment all --run-id SCALE-002-after --ticket SCALE-002
# exit 0; elapsed_s 378.6; every trial reconciled; no guard fired; 0 suspend_suspected

python -m benchmarks.stats benchmarks/results/SCALE-002-before --check   # summary.json matches recomputation: True
python -m benchmarks.stats benchmarks/results/SCALE-002-after --check    # summary.json matches recomputation: True

# keep-alive diagnostic (scratch script below)
env -u OPENAI_API_KEY -u OPENAI_BASE_URL PYTHONPATH=. python diag_nagle.py diag_nagle.json
# fresh 1.6 ms / shared 44.0 / +NODELAY server 1.1 / +NODELAY client 44.0 / both 1.0 (p50)

# comparison tables (scratch script below)
PYTHONPATH=. python compare.py

# full regression
python -m unittest discover -s eval/tests -p 'test_*.py' -v
# Ran 172 tests in 2.136s — OK   (166 + 6 new)
python -m eval.run_eval --validate-only
# OK — 27 cases, 6 domains, 9 categories, 0 errors.
python -m eval.run_eval --mode demo
# 27/27 schema-valid; 24/27 deterministic cases pass.  (non-zero exit by design)
# Failed cases in eval/results/summary_20260928T071214Z.md: AUTO-004, CONT-003, HVAC-003

sha256 analyzer: HEAD b30f47a3777d3381eb6ece8e23296a8b54b44c6d730f438bc062d2970586d821
                 now  a0d29296be8ca5bdf124137d05cb012f31037fc2fe902b3500988ce16b369ddb
```

## Design decisions and rejected alternatives

The design follows the approved plan.

- **Lazy construction, not eager:**
  - Building at import would construct a client in Demo mode, or need a mode branch in the analyzer, and would move config-error detection to import time.
  - A FastAPI lifespan hook would change `app.py` and force a startup-failure policy.
  - The cost of lazy: the first OpenAI request pays about 20 ms once.
- **Double-checked lock, not `lru_cache`, `app.state` or thread-local:**
  - `lru_cache` is not safe against duplicate builds on concurrent misses.
  - `app.state` couples the analyzer to FastAPI.
  - Thread-local would create up to 40 clients and pools.
- **No explicit shutdown close.** Process exit and `SyncHttpxClientWrapper.__del__` close the pool. A close hook would be an `app.py` lifecycle change with no measured benefit.
- **Config fixed at first use.** The key and timeout were already import-time constants, and `OPENAI_BASE_URL` is read by the SDK at construction. There is no production difference. Tests that vary these reset the singleton.
- **Test isolation uses `mock.patch.object(openai_analyzer, "_client", None)` inside `isolated_shared_client()`.** It closes whatever was built, then restores. There is no production reset hook.
- Deviation from the plan (cosmetic): in `CURRENT_STATE.md` the HOTFIX section was placed *above* SCALE-001, matching the file's newest-first convention.

## Known limitations

- All numbers are local WSL2, loopback and fake-provider. They are not Railway or OpenAI capacity.
- **The fake-provider Nagle artifact** (+~40 ms per attempt on reused connections) biases *after* latency upward and throughput downward. The improvements are understated, and the C=1 latency "regression" (274 → 300 ms) is attributed to it by the diagnostic. It was not fixed, per the identical-harness constraint.
- No same-session *before* Demo run (the plan limited the control to fake + retry). The Demo comparison is SCALE-001 vs after, and the small uplift is not claimed as a SCALE-002 effect.
- `git_commit` in both SCALE-002 `env.json` files is `4e33bfc` with `git_dirty: true`. The analyzer hashes above, and the behavioural signature (CPU/request, connections per request), tell the runs apart.
- The two `suspend_suspected` *before* trials are excluded in the comparison tables but remain in `summary.json` (the `stats --check` contract).
- The concurrent cold-start test uses a mock constructor with a 50 ms delay. It proves the locking logic, not SDK-internal thread safety. SDK thread safety under shared use is evidenced by the benchmark: 40 concurrent attempts through one client, zero failures, every trial reconciled.

## Out-of-scope findings (recorded, not fixed)

1. **Fake provider Nagle / delayed-ACK artifact.** `benchmarks/fake_provider.py` `_send_json` writes the headers and body separately without `TCP_NODELAY`. Fix this before the next comparative measurement.
2. **The anyio 40-token limiter is the binding and only aggregate provider-concurrency bound.** Excess requests queue invisibly. This is the subject of Decision Gate B.
3. **Provider-loop latency rises about 40–45 ms at C ≥ 32 in the after run.** The cause is unattributed (fake server, GIL or host contention).
4. **Keep-alive idle race (production hypothesis).** A connection the server has closed while idle can surface as `APIConnectionError` and consume the single retry. Unexercised by the fake.
5. SCALE-001 findings still open: Demo `latency_ms` is computed before the stub runs, and `/health` shares the threadpool (starvation untested).

## Dependency changes

None. `requirements.txt` is unchanged, and the pinned `openai==2.24.0` / `httpx==0.28.1` were inspected, not changed.

## Architectural observations

- Moving the client from request scope to process scope turned about 20 ms of native CPU per request (degrading to about 470 ms under contention) into a one-time cost. The OpenAI path is now **latency- and thread-bound, not CPU-bound**: 0.58 cores at C=64.
- A process-scoped client brings a process-scoped connection pool (limit 1000 / keep-alive 100 / 5 s expiry). At QuoteCheck's current concurrency it is not a bound, but it is now shared state whose health (stale connections, keep-alive races) matters for all requests.
- API capacity and model-execution capacity are still conflated. One framework threadpool (40) bounds `/health`, Demo `/analyze` and OpenAI `/analyze` together, and it is the only limit on aggregate provider calls. SCALE-002 made this the visible first constraint, which is what Gate B addresses.

## Scratch scripts used (not committed)

### `compare.py` (produces the report's comparison tables)

```python
"""SCALE-002 before/after comparison (scratch; source pasted into the review bundle).

Recomputes each point with the harness's own ``benchmarks.stats.summarize`` from raw
requests.jsonl/trials.jsonl, after dropping any trial flagged suspend_suspected
(harness rule), then prints side-by-side markdown tables."""
import json, sys
from pathlib import Path
from benchmarks import stats

RUNS = {"S1": "SCALE-001-baseline", "B": "SCALE-002-before", "A": "SCALE-002-after"}
ROOT = Path("benchmarks/results")

def load(run):
    d = ROOT / run
    trials = stats.read_jsonl(d / "trials.jsonl")
    bad = {(t["scenario"], t["concurrency"], t["trial"]) for t in trials if t.get("suspend_suspected")}
    reqs = [r for r in stats.read_jsonl(d / "requests.jsonl")
            if (r["scenario"], r["concurrency"], r["trial"]) not in bad]
    trials = [t for t in trials if (t["scenario"], t["concurrency"], t["trial"]) not in bad]
    raw = {(t["scenario"], t["concurrency"]): [] for t in trials}
    for t in trials:
        raw[(t["scenario"], t["concurrency"])].append(t)
    out = {}
    for row in stats.summarize(reqs, trials):
        k = (row["scenario"], row["concurrency"])
        ts = raw[k]
        cpu = sum(t["server_cpu_s"] for t in ts); wall = sum(t["wall_s"] for t in ts)
        n = sum(t["requests_issued"] for t in ts)
        prov = [t.get("provider") for t in ts if t.get("provider")]
        row["_cpu_ms_req"] = 1000 * cpu / n
        row["_cores"] = cpu / wall
        row["_rss_mb"] = max(t["server_rss_kb_peak"] for t in ts) / 1024
        row["_fds"] = max(t["server_fds_peak"] for t in ts)
        row["_threads"] = max(t["server_threads_peak"] for t in ts)
        row["_conns_per_req"] = (sum(p["connections_accepted"] - 1 for p in prov) / n) if prov else None  # -1: harness stats call
        row["_attempts"] = sum(p["attempts_started"] for p in prov) if prov else None
        row["_peak_inflight"] = max(p["peak_in_flight"] for p in prov) if prov else None
        row["_ntrials"] = len(ts)
        out[k] = row
    return out, bad

data = {}
for tag, run in RUNS.items():
    data[tag], bad = load(run)
    print(f"<!-- {run}: dropped suspend-flagged trials: {sorted(bad) or 'none'} -->")

def f(v, nd=1):
    return "–" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))

def table(scenario, tags):
    cs = sorted({c for t in tags for (s, c) in data[t] if s == scenario})
    print(f"\n#### `{scenario}`\n")
    print("| C | run | trials | ok/fail | rps mean | p50 ms | p95 ms | max ms | CPU ms/req | cores busy | attempts | peak in-flight | new conns/req | peak threads | peak RSS MB | peak fds |")
    print("|---:|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for c in cs:
        for t in tags:
            r = data[t].get((scenario, c))
            if not r:
                continue
            L = r["pooled_latency"]
            print(f"| {c} | {t} | {r['_ntrials']} | {r['successes']}/{r['failures']} | {r['throughput_rps_mean']:.2f} | "
                  f"{L['p50_ms']:.0f} | {L['p95_ms']:.0f} | {L['max_ms']:.0f} | {r['_cpu_ms_req']:.1f} | {r['_cores']:.2f} | "
                  f"{f(r['_attempts'])} | {f(r['_peak_inflight'])} | {f(r['_conns_per_req'], 2)} | {r['_threads']} | {r['_rss_mb']:.0f} | {r['_fds']} |")

def loop_table(scenario, tags):
    cs = sorted({c for t in tags for (s, c) in data[t] if s == scenario})
    print(f"\nServer-logged provider-loop latency (`latency_ms`), `{scenario}`, p50 / p95 ms:\n")
    print("| C | " + " | ".join(tags) + " |"); print("|---:|" + "---|" * len(tags))
    for c in cs:
        cells = []
        for t in tags:
            r = data[t].get((scenario, c)); s = r and r.get("server_reported_latency")
            cells.append(f"{s['p50_ms']:.0f} / {s['p95_ms']:.0f}" if s else "–")
        print(f"| {c} | " + " | ".join(cells) + " |")

for sc in ["fake_lat250ms", "fake_lat1s", "retry_fail_first_250ms", "retry_fail_always_250ms"]:
    table(sc, ["S1", "B", "A"]); loop_table(sc, ["S1", "B", "A"])
for sc in ["demo_analyze_short", "demo_analyze_normal", "demo_analyze_near_max", "health_floor"]:
    table(sc, ["S1", "A"])
```

### `diag_nagle.py` (keep-alive diagnostic)

```python
"""Scratch diagnostic (SCALE-002, not committed): which side's Nagle/delayed-ACK
interaction adds ~40 ms per request on a reused keep-alive connection?
Loopback fake only, sentinel key, zero cost."""
import json, socket, statistics, sys, threading, time
import httpx
from openai import OpenAI
from benchmarks.fake_provider import FakeProviderServer, _Handler

NODELAY = [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)]

class NoDelayHandler(_Handler):
    def setup(self):
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

def serve(handler):
    srv = FakeProviderServer(0, latency_s=0.0, mode="success")
    srv.RequestHandlerClass = handler
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    return srv

def make_client(base, nodelay):
    kw = {"api_key": "quotecheck-benchmark-fake-key", "max_retries": 0, "timeout": 30.0, "base_url": base}
    if nodelay:
        kw["http_client"] = httpx.Client(transport=httpx.HTTPTransport(socket_options=NODELAY), timeout=30.0)
    return OpenAI(**kw)

def run(name, handler, *, shared, client_nodelay, n=40):
    srv = serve(handler); base = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    msgs = [{"role": "user", "content": "x" * 2000}]
    shared_client = make_client(base, client_nodelay) if shared else None
    make_client(base, client_nodelay).close()  # warm imports
    ds = []
    for _ in range(n):
        c = shared_client or make_client(base, client_nodelay)
        t = time.perf_counter(); c.responses.create(model="m", input=msgs); ds.append((time.perf_counter() - t) * 1000)
        if not shared: c.close()
    if shared_client: shared_client.close()
    conns = srv.state.snapshot()["connections_accepted"]; srv.shutdown(); srv.server_close()
    ds = sorted(ds[5:])
    out = {"case": name, "p50_ms": round(statistics.median(ds), 1), "min_ms": round(ds[0], 1),
           "max_ms": round(ds[-1], 1), "connections": conns}
    print(json.dumps(out)); return out

res = [
  run("fresh client per request (pre-SCALE-002 shape)", _Handler, shared=False, client_nodelay=False),
  run("shared client (SCALE-002 shape)", _Handler, shared=True, client_nodelay=False),
  run("shared client + TCP_NODELAY on fake server only", NoDelayHandler, shared=True, client_nodelay=False),
  run("shared client + TCP_NODELAY on SDK client only", _Handler, shared=True, client_nodelay=True),
  run("shared client + TCP_NODELAY both sides", NoDelayHandler, shared=True, client_nodelay=True),
]
if len(sys.argv) > 1:
    json.dump({"note": "latency_s=0 fake, sequential, 35 measured after 5 warm", "results": res}, open(sys.argv[1], "w"), indent=2)
```

Output (`diag_nagle.json`):

```json
{
  "note": "latency_s=0 fake, sequential, 35 measured after 5 warm",
  "results": [
    {
      "case": "fresh client per request (pre-SCALE-002 shape)",
      "p50_ms": 1.6,
      "min_ms": 1.3,
      "max_ms": 6.9,
      "connections": 40
    },
    {
      "case": "shared client (SCALE-002 shape)",
      "p50_ms": 44.0,
      "min_ms": 43.3,
      "max_ms": 47.9,
      "connections": 1
    },
    {
      "case": "shared client + TCP_NODELAY on fake server only",
      "p50_ms": 1.1,
      "min_ms": 0.8,
      "max_ms": 1.7,
      "connections": 1
    },
    {
      "case": "shared client + TCP_NODELAY on SDK client only",
      "p50_ms": 44.0,
      "min_ms": 43.6,
      "max_ms": 44.5,
      "connections": 1
    },
    {
      "case": "shared client + TCP_NODELAY both sides",
      "p50_ms": 1.0,
      "min_ms": 0.9,
      "max_ms": 1.5,
      "connections": 1
    }
  ]
}
```
