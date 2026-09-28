"""Deterministic loopback fake of the OpenAI Responses endpoint (SCALE-001).

QuoteCheck is run *unmodified* in OpenAI mode with ``OPENAI_BASE_URL`` pointed
at this server, so only the remote provider is replaced: the uvicorn/h11 HTTP
boundary, threadpool, per-request SDK client construction, httpx request,
QuoteCheck retry loop, error classification, Pydantic validation and JSONL
logging all stay real.

Endpoints
---------
POST /v1/responses   the fake provider call (sleeps ``latency_s``, then answers)
GET  /__stats        counters as JSON
POST /__reset        zero counters; optional JSON body {"latency_s", "mode"}

Modes
-----
success     every attempt returns a schema-valid Responses body.
fail_first  the first attempt carrying a given ``[bench-marker:<id>]`` in its
            input returns HTTP 503 (a transient failure QuoteCheck retries);
            the next attempt with that marker succeeds.
fail_always every attempt returns HTTP 503.

Counters (started, completed, in-flight, peak in-flight, injected failures,
TCP connections accepted) are guarded by one ``threading.Lock``.

Run standalone: ``python -m benchmarks.fake_provider --port 0`` prints
``READY <port>`` on stdout once listening. Binds 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODES = ("success", "fail_first", "fail_always")
MARKER_RE = re.compile(r"\[bench-marker:([A-Za-z0-9_.:-]+)\]")


def build_model_output_json() -> str:
    """A realistic, schema-valid model output: the Demo analyzer's result for the
    ``normal`` workload, generated once. Its metadata is overwritten server-side
    by QuoteCheck exactly as it would be for a real model response."""
    from backend.core.stub_analyzer import analyze_quote_stub
    from benchmarks.workloads import WORKLOADS

    result = analyze_quote_stub(
        quote_text=WORKLOADS["normal"].text, request_id="bench-fake", latency_ms=0
    )
    return result.model_dump_json()


def responses_body(output_text: str, *, seq: int, model: str) -> dict:
    """Minimal Responses-API-shaped JSON that the openai SDK parses into a
    ``Response`` whose ``output_text`` is ``output_text``."""
    return {
        "id": f"resp_bench_{seq}",
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "metadata": {},
        "output": [
            {
                "type": "message",
                "id": f"msg_bench_{seq}",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": output_text, "annotations": []}],
            }
        ],
        "parallel_tool_calls": False,
        "temperature": None,
        "tool_choice": "auto",
        "tools": [],
        "top_p": None,
        "usage": None,
    }


class FakeProviderState:
    def __init__(self, *, latency_s: float = 0.25, mode: str = "success"):
        self._lock = threading.Lock()
        self.configure(latency_s=latency_s, mode=mode)
        self.reset()

    def configure(self, *, latency_s: float, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        if not (latency_s >= 0):
            raise ValueError("latency_s must be >= 0")
        with self._lock:
            self.latency_s = float(latency_s)
            self.mode = mode

    def reset(self) -> None:
        with self._lock:
            self.started = 0
            self.completed = 0
            self.in_flight = 0
            self.peak_in_flight = 0
            self.injected_failures = 0
            self.connections_accepted = 0
            self._seen_markers: set[str] = set()

    def note_connection(self) -> None:
        with self._lock:
            self.connections_accepted += 1

    def begin(self) -> int:
        with self._lock:
            self.started += 1
            self.in_flight += 1
            if self.in_flight > self.peak_in_flight:
                self.peak_in_flight = self.in_flight
            return self.started

    def end(self) -> None:
        with self._lock:
            self.in_flight -= 1
            self.completed += 1

    def should_fail(self, marker: str | None) -> bool:
        """Decide (atomically) whether this attempt gets an injected 503."""
        with self._lock:
            if self.mode == "fail_always":
                fail = True
            elif self.mode == "fail_first":
                fail = marker is not None and marker not in self._seen_markers
                if marker is not None:
                    self._seen_markers.add(marker)
            else:
                fail = False
            if fail:
                self.injected_failures += 1
            return fail

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "latency_s": self.latency_s,
                "mode": self.mode,
                "attempts_started": self.started,
                "attempts_completed": self.completed,
                "in_flight": self.in_flight,
                "peak_in_flight": self.peak_in_flight,
                "injected_failures": self.injected_failures,
                "connections_accepted": self.connections_accepted,
            }


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: "FakeProviderServer"

    def log_message(self, *_args) -> None:  # keep stdout clean for READY line
        pass

    def _send_json(self, status: int, obj: dict) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def do_GET(self) -> None:
        if self.path == "/__stats":
            self._send_json(200, self.server.state.snapshot())
        else:
            self._send_json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:
        body = self._read_body()
        state = self.server.state
        if self.path == "/__reset":
            cfg = json.loads(body) if body else {}
            if cfg:
                state.configure(
                    latency_s=cfg.get("latency_s", state.latency_s),
                    mode=cfg.get("mode", state.mode),
                )
            state.reset()
            self._send_json(200, state.snapshot())
            return
        if self.path.rstrip("/") != "/v1/responses":
            self._send_json(404, {"error": {"message": "not found"}})
            return

        seq = state.begin()
        try:
            text = body.decode("utf-8", errors="replace")
            m = MARKER_RE.search(text)
            fail = state.should_fail(m.group(1) if m else None)
            time.sleep(state.latency_s)
            if fail:
                self._send_json(503, {"error": {"message": "bench injected transient failure",
                                                "type": "server_error"}})
            else:
                try:
                    model = json.loads(body).get("model", "bench")
                except ValueError:
                    model = "bench"
                self._send_json(200, responses_body(self.server.output_text, seq=seq, model=model))
        finally:
            state.end()


class FakeProviderServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 1024  # stdlib default 5 would itself throttle bursts

    def __init__(self, port: int = 0, *, latency_s: float = 0.25, mode: str = "success",
                 output_text: str | None = None):
        super().__init__(("127.0.0.1", port), _Handler)
        self.state = FakeProviderState(latency_s=latency_s, mode=mode)
        self.output_text = output_text if output_text is not None else build_model_output_json()

    def get_request(self):
        conn = super().get_request()
        self.state.note_connection()
        return conn


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--latency-s", type=float, default=0.25)
    ap.add_argument("--mode", choices=MODES, default="success")
    args = ap.parse_args(argv)
    srv = FakeProviderServer(args.port, latency_s=args.latency_s, mode=args.mode)
    print(f"READY {srv.server_address[1]} output_chars={len(srv.output_text)}", flush=True)
    try:
        srv.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
