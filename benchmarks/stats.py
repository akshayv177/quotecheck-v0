"""Summary statistics for SCALE-001 raw evidence.

Percentile method: **nearest-rank** on the sorted sample —
``rank = ceil(p/100 * n)`` (1-based, minimum 1), value = ``sorted[rank-1]``.
No interpolation, so every reported percentile is an observed latency.

p99 is only reported when a pooled sample has at least ``P99_MIN_SAMPLES``
(1000) values; below that it is omitted (the top 1% would be <10 samples).

Recompute a run's summary from its raw files (proves the raw evidence is
sufficient):

    python -m benchmarks.stats benchmarks/results/<run-id>

SCALE-003 additions are optional: summary rows only gain the phase / occupancy
fields when the raw records carry them, so SCALE-001/002 summaries recompute
byte-for-byte. SCALE-004 admission fields (rejected counts, rejection vs
success latency, error codes) likewise appear only for trials the harness
marked ``rejection_aware``. Health probes are summarized separately (``health_summary.json``).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

P99_MIN_SAMPLES = 1000

POINT_KEY = ("experiment", "scenario", "workload_id", "concurrency")

# SCALE-004: QuoteCheck's application-owned admission rejection code.
CAPACITY_EXCEEDED = "capacity_exceeded"


def nearest_rank(sorted_values: Sequence[float], p: float) -> float:
    if not sorted_values:
        raise ValueError("empty sample")
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    rank = max(1, math.ceil(p / 100.0 * len(sorted_values)))
    return sorted_values[rank - 1]


def latency_summary(durations_s: Iterable[float]) -> dict:
    vals = sorted(durations_s)
    if not vals:
        return {"n": 0}
    out = {
        "n": len(vals),
        "p50_ms": round(nearest_rank(vals, 50) * 1000, 2),
        "p95_ms": round(nearest_rank(vals, 95) * 1000, 2),
        "max_ms": round(vals[-1] * 1000, 2),
        "min_ms": round(vals[0] * 1000, 2),
    }
    if len(vals) >= P99_MIN_SAMPLES:
        out["p99_ms"] = round(nearest_rank(vals, 99) * 1000, 2)
    return out


# --------------------------------------------------------------------------- #
# SCALE-003: provider-attempt timelines (all times on one monotonic clock)
# --------------------------------------------------------------------------- #

def in_flight_at(intervals: Sequence[tuple[float, float]], t: float) -> int:
    """Number of ``[start, end)`` intervals covering instant ``t``."""
    return sum(1 for a, b in intervals if a <= t < b)


def mean_in_flight(intervals: Sequence[tuple[float, float]], lo: float, hi: float) -> float:
    """Time-averaged number of intervals in flight over ``[lo, hi]``."""
    if hi <= lo:
        return 0.0
    busy = sum(max(0.0, min(b, hi) - max(a, lo)) for a, b in intervals)
    return busy / (hi - lo)


def time_frac_at_least(intervals: Sequence[tuple[float, float]], level: int,
                       lo: float, hi: float) -> float:
    """Fraction of ``[lo, hi]`` during which at least ``level`` intervals overlap."""
    if hi <= lo:
        return 0.0
    events = []
    for a, b in intervals:
        a, b = max(a, lo), min(b, hi)
        if a < b:
            events.append((a, 1))
            events.append((b, -1))
    events.sort(key=lambda e: (e[0], e[1]))  # ends before starts at equal times
    cur, last, covered = 0, lo, 0.0
    for t, d in events:
        if cur >= level:
            covered += t - last
        cur += d
        last = t
    if cur >= level:
        covered += hi - last
    return covered / (hi - lo)


def decompose_request(t_send: float, t_recv: float, attempts: Sequence[dict]) -> dict:
    """Split one request's client-observed time around its provider attempts.

    ``pre_provider_s``: client send -> first attempt start (HTTP + event loop +
    waiting for a worker token + pre-call work). ``provider_span_s``: first
    attempt start -> last attempt end (includes any retry gap).
    ``post_provider_s``: last attempt end -> client receive (response parsing,
    validation, logging, any second token wait, serialization, HTTP).
    """
    atts = sorted(attempts, key=lambda a: a["t_start"])
    if not atts or any(a.get("t_end") is None for a in atts):
        return {}
    out = {
        "fake_attempts": len(atts),
        "pre_provider_s": round(atts[0]["t_start"] - t_send, 6),
        "provider_span_s": round(atts[-1]["t_end"] - atts[0]["t_start"], 6),
        "post_provider_s": round(t_recv - atts[-1]["t_end"], 6),
    }
    if len(atts) > 1:
        out["inter_attempt_gap_s"] = round(atts[1]["t_start"] - atts[0]["t_end"], 6)
    return out


def summarize_health(probes: list[dict], saturation_level: int) -> list[dict]:
    """One row per (scenario, concurrency): all probes, and separately the
    subset sent while provider in-flight was exactly ``saturation_level``."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for pr in probes:
        groups[(pr["scenario"], pr["concurrency"])].append(pr)

    def block(ps: list[dict]) -> dict:
        codes: dict[str, int] = defaultdict(int)
        for pr in ps:
            codes[str(pr["http_status"] if pr["http_status"] is not None
                      else pr.get("error_code"))] += 1
        return {"n": len(ps), **{k: v for k, v in latency_summary(
                    pr["duration_s"] for pr in ps).items() if k != "n"},
                "status_counts": dict(sorted(codes.items())),
                "timeouts": sum(1 for pr in ps if "Timeout" in (pr.get("error_code") or ""))}

    rows = []
    for key in sorted(groups, key=lambda k: (k[0], k[1])):
        ps = sorted(groups[key], key=lambda p: p["probe_index"])
        sat = [p for p in ps if p.get("provider_in_flight_at_send") == saturation_level]
        rows.append({
            "scenario": key[0], "concurrency": key[1],
            "latency_s": ps[0].get("provider_latency_s"),
            "all_probes": block(ps),
            f"probes_sent_at_provider_in_flight_eq_{saturation_level}": block(sat),
            "provider_in_flight_at_send_counts": _counts(
                p.get("provider_in_flight_at_send") for p in ps),
            "analysis_outstanding_at_send_min": min(
                (p["analysis_outstanding_at_send"] for p in ps
                 if p.get("analysis_outstanding_at_send") is not None), default=None),
        })
    return rows


def _counts(values) -> dict:
    out: dict[str, int] = defaultdict(int)
    for v in values:
        out[str(v)] += 1
    return dict(sorted(out.items(), key=lambda kv: (len(kv[0]), kv[0])))


def _point_key(rec: dict) -> tuple:
    return tuple(rec.get(k) for k in POINT_KEY)


def summarize(requests: list[dict], trials: list[dict]) -> list[dict]:
    """One summary row per (experiment, scenario, workload, concurrency) point.

    Latency percentiles are computed per trial and pooled over all trials of
    the point. Throughput is successes / trial wall time, reported per trial
    and as the mean across trials.
    """
    req_by_trial: dict[tuple, list[dict]] = defaultdict(list)
    for r in requests:
        req_by_trial[_point_key(r) + (r["trial"],)].append(r)

    trials_by_point: dict[tuple, list[dict]] = defaultdict(list)
    for t in trials:
        trials_by_point[_point_key(t)].append(t)

    rows = []
    for key in sorted(trials_by_point, key=lambda k: tuple(str(x) for x in k[:3]) + (k[3],)):
        pts = sorted(trials_by_point[key], key=lambda t: t["trial"])
        per_trial = []
        pooled = []
        server_ms = []
        status_counts: dict[str, int] = defaultdict(int)
        for t in pts:
            reqs = req_by_trial.get(key + (t["trial"],), [])
            durs = [r["duration_s"] for r in reqs]
            pooled.extend(durs)
            server_ms.extend(r["server_latency_ms"] for r in reqs
                             if r.get("server_latency_ms") is not None)
            ok = sum(1 for r in reqs if r["success"])
            for r in reqs:
                status_counts[str(r["http_status"])] += 1
            row_t = {
                "trial": t["trial"],
                "requests": len(reqs),
                "successes": ok,
                "failures": len(reqs) - ok,
                "wall_s": round(t["wall_s"], 4),
                "throughput_rps": round(ok / t["wall_s"], 2) if t["wall_s"] > 0 else None,
                **{k: v for k, v in latency_summary(durs).items() if k != "n"},
            }
            for k in ("server_cpu_s", "server_threads_peak", "server_rss_kb_peak",
                      "server_fds_peak", "guard_stop", "suspend_suspected"):
                if k in t:
                    row_t[k] = t[k]
            if t.get("provider"):
                p = t["provider"]
                row_t["provider_attempts"] = p["attempts_started"]
                row_t["provider_peak_in_flight"] = p["peak_in_flight"]
                row_t["provider_injected_failures"] = p["injected_failures"]
                row_t["provider_connections"] = p["connections_accepted"]
            if "log_provider_attempts" in t:
                row_t["log_provider_attempts"] = t["log_provider_attempts"]
                row_t["reconciled"] = t.get("reconciled")
            for k in ("attempts_joined", "provider_mean_in_flight",
                      "provider_time_frac_in_flight_ge_40"):
                if k in t:
                    row_t[k] = t[k]
            if t.get("rejection_aware"):
                row_t["rejected"] = sum(1 for r in reqs
                                        if r.get("error_code") == CAPACITY_EXCEEDED)
                for k in ("issue_duration_s", "rejections_done_before_first_provider_end"):
                    if k in t:
                        row_t[k] = t[k]
            per_trial.append(row_t)

        tputs = [x["throughput_rps"] for x in per_trial if x["throughput_rps"] is not None]
        row = dict(zip(POINT_KEY, key))
        row.update({
            "trials": len(per_trial),
            "requests_per_trial": pts[0].get("requests_planned"),
            "requests_total": sum(x["requests"] for x in per_trial),
            "successes": sum(x["successes"] for x in per_trial),
            "failures": sum(x["failures"] for x in per_trial),
            "http_status_counts": dict(sorted(status_counts.items())),
            "throughput_rps_mean": round(sum(tputs) / len(tputs), 2) if tputs else None,
            "throughput_rps_min": min(tputs) if tputs else None,
            "throughput_rps_max": max(tputs) if tputs else None,
            "pooled_latency": latency_summary(pooled),
            # QuoteCheck's own logged latency_ms (OpenAI mode: provider retry-loop
            # time; Demo mode: measured before the stub runs, so ~0 by construction).
            "server_reported_latency": latency_summary(x / 1000.0 for x in server_ms),
            "any_trial_suspend_suspected": any(x.get("suspend_suspected") for x in per_trial),
            "per_trial": per_trial,
        })
        if any("provider_attempts" in x for x in per_trial):
            row["provider_attempts_total"] = sum(x.get("provider_attempts", 0) for x in per_trial)
            row["provider_peak_in_flight_max"] = max(
                x.get("provider_peak_in_flight", 0) for x in per_trial)
            row["all_trials_reconciled"] = all(x.get("reconciled") for x in per_trial)
        if any("server_threads_peak" in x for x in per_trial):
            row["server_threads_peak_max"] = max(x.get("server_threads_peak", 0) for x in per_trial)
        # SCALE-003 phase decomposition, only when the raw records carry it.
        phases = {}
        for ph in ("pre_provider_s", "provider_span_s", "post_provider_s", "inter_attempt_gap_s"):
            vals = [r[ph] for t in pts for r in req_by_trial.get(key + (t["trial"],), [])
                    if r.get(ph) is not None]
            if vals:
                phases[ph[:-2]] = latency_summary(vals)
        if phases:
            row["phase_latency"] = phases
        if any("provider_mean_in_flight" in x for x in per_trial):
            row["all_trials_attempts_joined"] = all(x.get("attempts_joined") for x in per_trial)
        if any(t.get("rejection_aware") for t in pts):
            row["admission"] = _admission_block(
                [r for t in pts for r in req_by_trial.get(key + (t["trial"],), [])], per_trial)
        rows.append(row)
    return rows


def _admission_block(reqs: list[dict], per_trial: list[dict]) -> dict:
    """SCALE-004: separate admission rejections from successes and from every
    other failure, with a latency summary for each."""
    rej = [r for r in reqs if r.get("error_code") == CAPACITY_EXCEEDED]
    ok = [r for r in reqs if r["success"]]
    codes: dict[str, int] = defaultdict(int)
    for r in reqs:
        if not r["success"]:
            codes[str(r.get("error_code"))] += 1
    out = {
        "rejected": len(rej),
        "admitted": len(reqs) - len(rej),
        "non_rejection_failures": len(reqs) - len(rej) - len(ok),
        "failure_code_counts": dict(sorted(codes.items())),
        "rejection_http_status_counts": dict(sorted(_counts(
            r["http_status"] for r in rej).items())),
        "rejected_with_provider_attempts": sum(
            1 for r in rej if r.get("provider_attempts") or r.get("fake_attempts")),
        "rejection_latency": latency_summary(r["duration_s"] for r in rej),
        "success_latency": latency_summary(r["duration_s"] for r in ok),
    }
    flags = [x["rejections_done_before_first_provider_end"] for x in per_trial
             if "rejections_done_before_first_provider_end" in x]
    if flags:
        out["all_rejections_done_before_first_provider_end"] = all(flags)
    return out


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize_dir(run_dir: Path) -> list[dict]:
    return summarize(read_jsonl(run_dir / "requests.jsonl"), read_jsonl(run_dir / "trials.jsonl"))


def format_table(rows: list[dict]) -> str:
    hdr = ("experiment", "scenario", "workload", "C", "reqs", "ok", "fail", "rps(mean)",
           "p50ms", "p95ms", "maxms", "prov_att", "peak_inflt", "thr_peak")
    lines = ["\t".join(hdr)]
    for r in rows:
        lat = r["pooled_latency"]
        lines.append("\t".join(str(x) for x in (
            r["experiment"], r["scenario"], r["workload_id"], r["concurrency"],
            r["requests_total"], r["successes"], r["failures"], r["throughput_rps_mean"],
            lat.get("p50_ms"), lat.get("p95_ms"), lat.get("max_ms"),
            r.get("provider_attempts_total", "-"), r.get("provider_peak_in_flight_max", "-"),
            r.get("server_threads_peak_max", "-"),
        )))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recompute SCALE-001 summary from raw evidence")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--write", action="store_true", help="(re)write summary.json")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if recomputed rows differ from the stored summary.json")
    args = ap.parse_args(argv)
    rows = summarize_dir(args.run_dir)
    print(format_table(rows))
    if args.write:
        (args.run_dir / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    probes = read_jsonl(args.run_dir / "health_probes.jsonl")
    hrows = summarize_health(probes, 40) if probes else None
    if args.write and hrows is not None:
        (args.run_dir / "health_summary.json").write_text(json.dumps(hrows, indent=2) + "\n")
    if args.check:
        stored = json.loads((args.run_dir / "summary.json").read_text())
        same = stored == json.loads(json.dumps(rows))
        print(f"summary.json matches recomputation: {same}")
        if hrows is not None:
            hstored = json.loads((args.run_dir / "health_summary.json").read_text())
            hsame = hstored == json.loads(json.dumps(hrows))
            print(f"health_summary.json matches recomputation: {hsame}")
            same = same and hsame
        return 0 if same else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
