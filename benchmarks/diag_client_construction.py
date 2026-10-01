"""SCALE-001 focused diagnostic: cost of per-request OpenAI client construction.

Added because the main fake-provider evidence showed server CPU per request
rising roughly 25× with concurrency while QuoteCheck's own provider-loop
latency stayed flat, meaning the extra work happens outside the provider loop.
``analyze_quote_openai`` builds a new ``OpenAI(...)`` client, and therefore a
new ``httpx.Client`` and SSL context, on every request, before that loop starts.

This isolates each layer of that construction in one process, with N threads
doing it concurrently. Nothing touches the network, and no runtime code is
changed or patched.

    python -m benchmarks.diag_client_construction [--out <file.json>]
"""

from __future__ import annotations

import argparse
import json
import resource
import ssl
import sys
import threading
import time

import certifi
import httpx
from openai import OpenAI

from backend.core.config import OPENAI_TIMEOUT_DEFAULT_SECONDS
from backend.core.prompt import build_messages
from backend.core.schema_export import quotecheck_result_schema_obj
from benchmarks.workloads import WORKLOADS

THREAD_COUNTS = (1, 8, 32)
OPS = {
    # Exactly the analyzer's construction call (backend/core/openai_analyzer.py).
    "openai_client": lambda: OpenAI(api_key="sk-diag-not-a-key",
                                    timeout=OPENAI_TIMEOUT_DEFAULT_SECONDS, max_retries=0),
    "httpx_client": lambda: httpx.Client(),
    "ssl_context_certifi": lambda: ssl.create_default_context(cafile=certifi.where()),
    # The other per-request pre-loop work, for comparison.
    "schema_and_messages": lambda: (quotecheck_result_schema_obj(),
                                    build_messages(quote_text=WORKLOADS["normal"].text)),
}


def _process_cpu_s() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def measure(op, threads: int, per_thread: int) -> dict:
    for _ in range(3):  # warm-up, excluded
        op()
    barrier = threading.Barrier(threads + 1)

    def work():
        barrier.wait()
        for _ in range(per_thread):
            op()

    ts = [threading.Thread(target=work) for _ in range(threads)]
    for t in ts:
        t.start()
    c0, t0 = _process_cpu_s(), time.perf_counter()
    barrier.wait()
    for t in ts:
        t.join()
    wall, cpu = time.perf_counter() - t0, _process_cpu_s() - c0
    n = threads * per_thread
    return {"threads": threads, "ops": n, "wall_s": round(wall, 4),
            "ops_per_s": round(n / wall, 1), "cpu_ms_per_op": round(cpu / n * 1000, 2),
            "cores_busy": round(cpu / wall, 2)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    rows = []
    for name, op in OPS.items():
        for c in THREAD_COUNTS:
            row = {"op": name, **measure(op, c, 40 if c == 1 else 12)}
            rows.append(row)
            print(f"{name:20s} threads={c:2d} ops/s={row['ops_per_s']:7.1f} "
                  f"cpu_ms/op={row['cpu_ms_per_op']:8.2f} cores_busy={row['cores_busy']:5.2f}",
                  flush=True)
    out = {"openssl": ssl.OPENSSL_VERSION, "python": sys.version, "results": rows}
    if args.out:
        with open(args.out, "w") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
    print(ssl.OPENSSL_VERSION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
