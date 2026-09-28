# Usage (repo root): PYTHONPATH=. python benchmarks/results/SCALE-003-saturation/report_tables.py
"""SCALE-003 report tables, recomputed from raw evidence with the harness's own
benchmarks.stats. Suspend-flagged trials are excluded (harness rule)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

from benchmarks import stats

d = Path(sys.argv[1] if len(sys.argv) > 1 else "benchmarks/results/SCALE-003-saturation")
reqs = stats.read_jsonl(d / "requests.jsonl")
trials = stats.read_jsonl(d / "trials.jsonl")
bad = {(t["scenario"], t["concurrency"], t["trial"]) for t in trials if t.get("suspend_suspected")}
print("excluded suspend trials:", sorted(bad))
trials = [t for t in trials if (t["scenario"], t["concurrency"], t["trial"]) not in bad]
reqs = [r for r in reqs if (r["scenario"], r["concurrency"], r["trial"]) not in bad]
rows = stats.summarize(reqs, trials)
tb = defaultdict(list)
for t in trials:
    tb[(t["scenario"], t["concurrency"])].append(t)


def f(x, nd=0):
    return "–" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


print("\n| scenario | C | trials | ok/fail | rps mean | e2e p50 | e2e p95 | e2e max | loop p50 | loop p95 "
      "| pre p50 | pre p95 | post p50 | post p95 | gap p50 | att/req | peak in-flight | mean in-flight "
      "| time ≥40 | CPU ms/req | peak thr | RSS MB | fds | new conns |")
print("|" + "---|" * 24)
for r in rows:
    ts = tb[(r["scenario"], r["concurrency"])]
    lat, sl = r["pooled_latency"], r["server_reported_latency"]
    ph = r.get("phase_latency", {})
    g = lambda k, q: ph.get(k, {}).get(q)
    cpu = sum(t["server_cpu_s"] for t in ts) / sum(t["requests_issued"] for t in ts) * 1000
    mif = sum(t["provider_mean_in_flight"] for t in ts) / len(ts)
    fr = sum(t["provider_time_frac_in_flight_ge_40"] for t in ts) / len(ts)
    conns = max(t["provider"]["connections_accepted"] for t in ts)
    print(f"| {r['scenario']} | {r['concurrency']} | {r['trials']} | {r['successes']}/{r['failures']} "
          f"| {r['throughput_rps_mean']} | {f(lat['p50_ms'])} | {f(lat['p95_ms'])} | {f(lat['max_ms'])} "
          f"| {f(sl.get('p50_ms'))} | {f(sl.get('p95_ms'))} "
          f"| {f(g('pre_provider','p50_ms'))} | {f(g('pre_provider','p95_ms'))} "
          f"| {f(g('post_provider','p50_ms'))} | {f(g('post_provider','p95_ms'))} "
          f"| {f(g('inter_attempt_gap','p50_ms'))} "
          f"| {r['provider_attempts_total'] / r['requests_total']:.2f} | {r['provider_peak_in_flight_max']} "
          f"| {mif:.1f} | {fr:.2f} | {cpu:.1f} | {r['server_threads_peak_max']} "
          f"| {max(t['server_rss_kb_peak'] for t in ts) / 1024:.0f} | {max(t['server_fds_peak'] for t in ts)} "
          f"| {conns} |")
    ok = r.get("all_trials_reconciled"), r.get("all_trials_attempts_joined")
    if ok != (True, True):
        print("   !! reconciliation/join", ok)
    codes = r["http_status_counts"]
    if list(codes) != ["200"]:
        print("   status counts", codes)

print("\nper-trial throughput:")
for r in rows:
    print(r["scenario"], r["concurrency"], [x["throughput_rps"] for x in r["per_trial"]])

# health
hs = stats.summarize_health(stats.read_jsonl(d / "health_probes.jsonl"), 40)
scen = {s["scenario"]: s for s in stats.read_jsonl(d / "scenarios.jsonl") if s["experiment"] == "health"}
print("\n| scenario | C | probes | status | p50 | p95 | max | min | timeouts | at-40 n | at-40 p50 | at-40 p95 "
      "| at-40 max | in-flight@send dist | outstanding@send min | load fail | peak thr | peak in-flight |")
print("|" + "---|" * 18)
for h in hs:
    a = h["all_probes"]
    s40 = h["probes_sent_at_provider_in_flight_eq_40"]
    pt = next((p for p in scen[h["scenario"]]["points"] if p["concurrency"] == h["concurrency"]), {})
    print(f"| {h['scenario']} | {h['concurrency']} | {a['n']} | {a['status_counts']} | {f(a.get('p50_ms'))} "
          f"| {f(a.get('p95_ms'))} | {f(a.get('max_ms'))} | {f(a.get('min_ms'))} | {a['timeouts']} | {s40['n']} "
          f"| {f(s40.get('p50_ms'))} | {f(s40.get('p95_ms'))} | {f(s40.get('max_ms'))} "
          f"| {h['provider_in_flight_at_send_counts']} | {h['analysis_outstanding_at_send_min']} "
          f"| {pt.get('load_failures', '–')} | {pt.get('threads_peak', '–')} | {pt.get('provider_peak_in_flight', '–')} |")
for name, s in scen.items():
    print(name, json.dumps(s["points"]))

# health-load phases
hl = stats.read_jsonl(d / "health_load_requests.jsonl")
g = defaultdict(list)
for r in hl:
    g[(r["scenario"], r["concurrency"])].append(r)
print("\nhealth-load analysis requests:")
for k, rs in sorted(g.items()):
    ls = stats.latency_summary(r["duration_s"] for r in rs)
    pre = stats.latency_summary(r["pre_provider_s"] for r in rs if "pre_provider_s" in r)
    post = stats.latency_summary(r["post_provider_s"] for r in rs if "post_provider_s" in r)
    print(k, "n", len(rs), "fail", sum(not r["success"] for r in rs), "e2e", ls.get("p50_ms"), ls.get("p95_ms"),
          "pre", pre.get("p50_ms"), pre.get("p95_ms"), "post", post.get("p50_ms"), post.get("p95_ms"),
          post.get("max_ms"))

# --- derived: where the waiting sits, fail-always rate, new connections, health vs next completion
from pathlib import Path as _P  # noqa: E402
LAT = {"sat_lat1s": 1, "sat_lat3s": 3, "sat_lat5s": 5,
       "retry_sat_fail_first_3000ms": 3, "retry_sat_fail_always_3000ms": 3}
g = defaultdict(list)
for r in reqs:
    g[(r["scenario"], r["concurrency"])].append(r)
print("\nscenario C | non-provider mean ms | frac pre>L/2 | frac post>L/2 | both | neither")
for k, rs in sorted(g.items()):
    L = LAT[k[0]]
    nonp = sum(r["duration_s"] - r["provider_span_s"] for r in rs) / len(rs)
    pre = [r["pre_provider_s"] > L / 2 for r in rs]
    post = [r["post_provider_s"] > L / 2 for r in rs]
    n = len(rs)
    print(k, round(nonp * 1000), round(sum(pre) / n, 3), round(sum(post) / n, 3),
          round(sum(a and b for a, b in zip(pre, post)) / n, 3),
          round(sum(not a and not b for a, b in zip(pre, post)) / n, 3))
for t in stats.read_jsonl(d / "trials.jsonl"):
    if t["provider"]["connections_accepted"] > 1:
        print("connections_accepted", t["scenario"], t["concurrency"], t["trial"],
              t["provider"]["connections_accepted"], "(suspend-flagged)" if t.get("suspend_suspected") else "")
    if t["scenario"].startswith("retry_sat_fail_always"):
        print("fail_always trial", t["trial"], "503/s", round(t["requests_issued"] / t["wall_s"], 2))
P = stats.read_jsonl(d / "health_probes.jsonl")
A = defaultdict(list)
for a in stats.read_jsonl(d / "provider_attempts.jsonl"):
    if a["experiment"] == "health_load":
        A[(a["scenario"], a["concurrency"])].append(a)
print("\nat-40 probes: probe latency minus time from send to the next provider completion (ms)")
for k in sorted(A):
    ends = sorted(a["t_end"] for a in A[k])
    diffs = sorted(round((p["duration_s"] - (next(e for e in ends if e > p["t_send"]) - p["t_send"])) * 1000)
                   for p in P if (p["scenario"], p["concurrency"]) == k
                   and p["provider_in_flight_at_send"] == 40)
    if diffs:
        print(k, "n", len(diffs), "min", diffs[0], "median", diffs[len(diffs) // 2], "max", diffs[-1])
