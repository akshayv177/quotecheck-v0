# Usage (repo root):
#   PYTHONPATH=. python benchmarks/results/SCALE-004-after/report_tables.py \
#       benchmarks/results/SCALE-004-before benchmarks/results/SCALE-004-after
"""SCALE-004 before/after report tables, recomputed from raw evidence with the
harness's own benchmarks.stats. Suspend-flagged trials are excluded (harness rule)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

from benchmarks import stats

dirs = [Path(a) for a in sys.argv[1:3]] or [Path("benchmarks/results/SCALE-004-before"),
                                            Path("benchmarks/results/SCALE-004-after")]


def f(x, nd=0):
    if x is None:
        return "–"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def load(d):
    reqs = stats.read_jsonl(d / "requests.jsonl")
    trials = stats.read_jsonl(d / "trials.jsonl")
    bad = {(t["scenario"], t["concurrency"], t["trial"]) for t in trials
           if t.get("suspend_suspected")}
    trials = [t for t in trials if (t["scenario"], t["concurrency"], t["trial"]) not in bad]
    reqs = [r for r in reqs if (r["scenario"], r["concurrency"], r["trial"]) not in bad]
    return reqs, trials, sorted(bad)


print("## Analysis points (burst / sustained / retry)\n")
print("| build | scenario | C | trials | admitted ok | rejected | other fail | ok rps | ok p50 | ok p95 "
      "| ok max | rej p50 | rej p95 | rej max | pre p50 | pre p95 | post p50 | post p95 | peak in-flight "
      "| att/admitted | rej→0 att | rej before 1st end | CPU ms/req | peak thr | RSS MB | fds "
      "| reconciled+joined |")
print("|" + "---|" * 27)
for d in dirs:
    reqs, trials, bad = load(d)
    if bad:
        print(f"<!-- {d.name}: excluded suspend trials {bad} -->")
    tb = defaultdict(list)
    for t in trials:
        tb[(t["scenario"], t["concurrency"])].append(t)
    for r in stats.summarize(reqs, trials):
        ts = tb[(r["scenario"], r["concurrency"])]
        a = r["admission"]
        ok, rl = a["success_latency"], a["rejection_latency"]
        ph = r.get("phase_latency", {})
        g = lambda k, q: ph.get(k, {}).get(q)
        cpu = sum(t["server_cpu_s"] for t in ts) / sum(t["requests_issued"] for t in ts) * 1000
        order = a.get("all_rejections_done_before_first_provider_end")
        print(f"| {d.name.split('-')[-1]} | {r['scenario']} | {r['concurrency']} | {r['trials']} "
              f"| {r['successes']} | {a['rejected']} | {a['non_rejection_failures']} "
              f"| {r['throughput_rps_mean']} | {f(ok.get('p50_ms'))} | {f(ok.get('p95_ms'))} "
              f"| {f(ok.get('max_ms'))} | {f(rl.get('p50_ms'), 1)} | {f(rl.get('p95_ms'), 1)} "
              f"| {f(rl.get('max_ms'), 1)} | {f(g('pre_provider', 'p50_ms'))} "
              f"| {f(g('pre_provider', 'p95_ms'))} | {f(g('post_provider', 'p50_ms'))} "
              f"| {f(g('post_provider', 'p95_ms'))} | {r['provider_peak_in_flight_max']} "
              f"| {r['provider_attempts_total'] / max(1, a['admitted']):.2f} "
              f"| {'yes' if a['rejected_with_provider_attempts'] == 0 else 'NO'} "
              f"| {'–' if order is None else ('yes' if order else 'NO')} | {cpu:.2f} "
              f"| {r['server_threads_peak_max']} "
              f"| {max(t['server_rss_kb_peak'] for t in ts) / 1024:.0f} "
              f"| {max(t['server_fds_peak'] for t in ts)} "
              f"| {r['all_trials_reconciled'] and r['all_trials_attempts_joined']} |")

print("\n## /health probes under load\n")
print("| build | scenario | C | probes | non-200 | p50 | p95 | max | probe-time provider in-flight "
      "| load ok | load rejected | load rej p50 | load rej p95 | load rej max | load post p50 "
      "| load post p95 | load peak in-flight | CPU s | peak thr |")
print("|" + "---|" * 19)
for d in dirs:
    hs = {(h["scenario"], h["concurrency"]): h for h in
          json.loads((d / "health_summary.json").read_text())}
    points = {}
    for line in (d / "scenarios.jsonl").read_text().splitlines():
        m = json.loads(line)
        for p in m.get("points", []):
            points[(m["scenario"], p["concurrency"])] = p
    loadrecs = defaultdict(list)
    for r in stats.read_jsonl(d / "health_load_requests.jsonl"):
        loadrecs[(r["scenario"], r["concurrency"])].append(r)
    for key in sorted(hs, key=lambda k: (k[0], k[1])):
        h, p = hs[key], points.get(key, {})
        a = h["all_probes"]
        lr = loadrecs.get(key, [])
        rej = stats.latency_summary(r["duration_s"] for r in lr
                                    if r.get("error_code") == stats.CAPACITY_EXCEEDED)
        post = stats.latency_summary(r["post_provider_s"] for r in lr
                                     if r.get("post_provider_s") is not None)
        bad = sum(v for k, v in a["status_counts"].items() if k != "200")
        print(f"| {d.name.split('-')[-1]} | {key[0]} | {key[1]} | {a['n']} | {bad} "
              f"| {f(a.get('p50_ms'), 1)} | {f(a.get('p95_ms'), 1)} | {f(a.get('max_ms'), 1)} "
              f"| {h['provider_in_flight_at_send_counts']} "
              f"| {sum(1 for r in lr if r['success'])} | {rej['n']} "
              f"| {f(rej.get('p50_ms'), 1)} | {f(rej.get('p95_ms'), 1)} | {f(rej.get('max_ms'), 1)} "
              f"| {f(post.get('p50_ms'))} | {f(post.get('p95_ms'))} "
              f"| {p.get('provider_peak_in_flight', '–')} | {p.get('server_cpu_s', '–')} "
              f"| {p.get('threads_peak', '–')} |")
