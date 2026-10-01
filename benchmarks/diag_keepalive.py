"""SCALE-003 focused diagnostic: the fake provider's reused-connection delay.

SCALE-002 found that the loopback fake added about 40 ms to every attempt on a
reused keep-alive connection (Nagle's algorithm on the fake's socket, against
the client's delayed ACK). SCALE-003 sets TCP_NODELAY on the fake's accepted
sockets. This script measures the fake both ways, in one process, so the repair
is shown as runtime evidence rather than asserted by a machine-sensitive unit
test threshold.

Cases, each ``--n`` sequential attempts against an in-process fake with 0 ms
injected latency (so the measured time is pure transport + parse):

- ``sdk_shared``: one real ``OpenAI`` client reused for every attempt, the
  SCALE-002 QuoteCheck shape (one pooled keep-alive connection);
- ``sdk_fresh``: a new ``OpenAI`` client per attempt, the pre-SCALE-002 shape
  (a new connection per attempt);
- ``raw_keepalive``: one stdlib ``http.client`` connection reused, no SDK.

each with ``tcp_nodelay=False`` (the SCALE-001/002 instrument) and ``True``
(SCALE-003). Nothing touches the network beyond 127.0.0.1 and no runtime code
is changed.

    python -m benchmarks.diag_keepalive [--n 35] [--out <file.json>]
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import sys
import threading
import time

from openai import OpenAI

from benchmarks import stats
from benchmarks.fake_provider import FakeProviderServer
from benchmarks.run_capacity import SENTINEL_API_KEY, SENTINEL_MODEL

PROMPT = [{"role": "user", "content": "keepalive diagnostic"}]


@contextlib.contextmanager
def _fake(tcp_nodelay: bool):
    srv = FakeProviderServer(0, latency_s=0, tcp_nodelay=tcp_nodelay)
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def _client(port: int) -> OpenAI:
    return OpenAI(api_key=SENTINEL_API_KEY, max_retries=0, timeout=10,
                  base_url=f"http://127.0.0.1:{port}/v1")


def _sdk_shared(port: int, n: int) -> list[float]:
    out = []
    with _client(port) as c:
        for _ in range(n):
            t = time.perf_counter()
            c.responses.create(model=SENTINEL_MODEL, input=PROMPT)
            out.append(time.perf_counter() - t)
    return out


def _sdk_fresh(port: int, n: int) -> list[float]:
    out = []
    for _ in range(n):
        with _client(port) as c:
            t = time.perf_counter()
            c.responses.create(model=SENTINEL_MODEL, input=PROMPT)
            out.append(time.perf_counter() - t)
    return out


def _raw_keepalive(port: int, n: int) -> list[float]:
    body = json.dumps({"model": SENTINEL_MODEL, "input": PROMPT}).encode()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    out = []
    try:
        for _ in range(n):
            t = time.perf_counter()
            conn.request("POST", "/v1/responses", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            resp.read()
            out.append(time.perf_counter() - t)
    finally:
        conn.close()
    return out


CASES = {"sdk_shared": _sdk_shared, "sdk_fresh": _sdk_fresh, "raw_keepalive": _raw_keepalive}


def run(n: int) -> list[dict]:
    rows = []
    for name, fn in CASES.items():
        for nodelay in (False, True):
            with _fake(nodelay) as srv:
                durs = fn(srv.server_address[1], n)
                snap = srv.state.snapshot()
            lat = stats.latency_summary(durs)
            rows.append({"case": name, "fake_tcp_nodelay": nodelay, "attempts": n,
                         "connections_accepted": snap["connections_accepted"],
                         "p50_ms": lat["p50_ms"], "p95_ms": lat["p95_ms"],
                         "min_ms": lat["min_ms"], "max_ms": lat["max_ms"]})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=35)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    rows = run(args.n)
    print("case\tfake_tcp_nodelay\tattempts\tconns\tp50_ms\tp95_ms\tmin_ms\tmax_ms")
    for r in rows:
        print("\t".join(str(r[k]) for k in ("case", "fake_tcp_nodelay", "attempts",
                                            "connections_accepted", "p50_ms", "p95_ms",
                                            "min_ms", "max_ms")))
    if args.out:
        with open(args.out, "w") as f:
            json.dump({"n": args.n, "rows": rows}, f, indent=2)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
