"""SCALE-001 capacity-characterization harness (extended in SCALE-003).

Zero provider cost. Everything runs on 127.0.0.1; the harness launches its own
servers and has no option to target any other host.

Topology (three OS processes)
-----------------------------
1. this process — closed-loop load client (stdlib threads + http.client, one
   persistent keep-alive connection per worker);
2. QuoteCheck, unmodified, as one deployment-shaped uvicorn process:
   ``python -m uvicorn backend.app:app --host 127.0.0.1 --port <p> --loop asyncio --http h11``
   (asyncio + h11 match the production install, which has no uvloop/httptools);
3. (fake/retry experiments) ``benchmarks.fake_provider`` — a loopback fake of the
   OpenAI Responses endpoint, reached through the SDK's own ``OPENAI_BASE_URL``.

Experiments
-----------
demo    Demo analyzer via real HTTP ``POST /analyze`` for each workload, plus a
        ``GET /health`` ladder as the HTTP/framework/client floor.
fake    OpenAI-mode path with ~250 ms and ~1 s deterministic provider latency.
retry   transient-failure -> retry -> success, and fail-fail (two-attempt bound).

SCALE-003 (``all`` still means the three above; name these explicitly):

saturation  success at 1 s / 3 s / 5 s provider latency around and above the
            40-token anyio limiter (C = 16..64; C = 1 at 1 s as fake-repair evidence).
health      sequential ``GET /health`` probes while sustained slow ``/analyze``
            load holds C = 32 / 40 / 64 in flight, plus an idle control.
retry_sat   fail-first at 3 s, C = 32 / 40 / 64, and one fail-always spot check.

SCALE-003 request bodies carry a unique ``[bench-marker:...]`` so every fake
provider attempt (timestamped by the fake on the shared CLOCK_MONOTONIC) joins
to its request. That splits each request into time before its first provider
attempt, provider time, and time after its last attempt, without adding any
instrumentation to QuoteCheck.

Usage (repo root, conda env ``quotecheck``)
-------------------------------------------
    python -m benchmarks.run_capacity --quick                       # ~1 min smoke
    python -m benchmarks.run_capacity --experiment all --run-id SCALE-001-baseline
    python -m benchmarks.stats benchmarks/results/SCALE-001-baseline --check

Outputs in ``benchmarks/results/<run-id>/``: ``env.json``, ``scenarios.jsonl``,
``trials.jsonl``, ``requests.jsonl`` (one line per measured request),
``summary.json``, and ``server/`` (per-scenario uvicorn/app run logs).
Warm-up requests are never written to ``requests.jsonl``. SCALE-003 experiments
add ``provider_attempts.jsonl`` (the fake's raw attempt log per trial/point),
``health_probes.jsonl``, ``health_load_requests.jsonl`` and ``health_summary.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.metadata
import json
import os
import platform
import random
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from benchmarks import stats
from benchmarks.fake_provider import MARKER_RE
from benchmarks.workloads import WORKLOADS

# The ticket that created this harness. The ticket a given run measures for is
# recorded separately (--ticket -> env.json "measurement_ticket").
HARNESS_ORIGIN = "SCALE-001"
REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = REPO_ROOT / "benchmarks" / "results"

# Sentinels: even if traffic were somehow misrouted to the real provider, a fake
# key and a nonexistent model name are rejected (401/400) without billing.
SENTINEL_API_KEY = "quotecheck-benchmark-fake-key"
SENTINEL_MODEL = "quotecheck-bench-fake-model"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

# Host-safety guards. Tripping one stops the run for machine safety; it is NOT
# evidence that QuoteCheck saturated.
RSS_GUARD_KB = 1024 * 1024          # QuoteCheck server RSS > 1 GiB
MEMAVAIL_GUARD_KB = 1024 * 1024     # host MemAvailable < 1 GiB
# Escalation guards: stop climbing a ladder when the previous point had any
# failed request (unexpected in these scenarios) or pooled p95 > 30 s.
P95_ESCALATION_GUARD_S = 30.0
# Wall-clock minus monotonic elapsed time beyond this marks a trial as invalid.
SUSPEND_SKEW_GUARD_S = 1.0

# SCALE-003 health probes: one outstanding at a time, fresh connection each.
HEALTH_PROBE_TIMEOUT_S = 60.0
# The anyio default thread limiter QuoteCheck currently runs under (a framework
# default, not a QuoteCheck budget). Used only to label saturation evidence.
ANYIO_DEFAULT_TOKENS = 40

PACKAGES = ("fastapi", "starlette", "uvicorn", "anyio", "h11", "uvloop", "httptools",
            "openai", "httpx", "pydantic", "python-dotenv")


# --------------------------------------------------------------------------- #
# Safety
# --------------------------------------------------------------------------- #

def assert_loopback_url(url: str) -> None:
    host = urlsplit(url).hostname
    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(f"refusing non-loopback provider URL host {host!r}")


def build_child_env(*, use_openai: bool, log_path: Path, base_url: str | None = None,
                    parent_env: dict | None = None) -> dict:
    """Explicit QuoteCheck server environment.

    Strips inherited proxy, OPENAI_* and QUOTECHECK_* variables, then sets every
    value that matters explicitly — ``backend/.env`` is loaded with
    ``override=False``, so these explicit values always win over the file.
    """
    src = os.environ if parent_env is None else parent_env
    env = {
        k: v for k, v in src.items()
        if not (k.upper().endswith("_PROXY") or k.upper().startswith("OPENAI_")
                or k.upper().startswith("QUOTECHECK_"))
    }
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    env["QUOTECHECK_USE_OPENAI"] = "1" if use_openai else "0"
    env["QUOTECHECK_LOG_PATH"] = str(log_path)
    env["QUOTECHECK_MODEL"] = SENTINEL_MODEL
    env["OPENAI_API_KEY"] = SENTINEL_API_KEY
    if use_openai:
        if not base_url:
            raise RuntimeError("OpenAI-mode benchmark requires a loopback fake base_url")
        assert_loopback_url(base_url)
        env["OPENAI_BASE_URL"] = base_url
    else:
        env["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"  # discard port; Demo never calls it
    env["PYTHONUNBUFFERED"] = "1"
    return env


# --------------------------------------------------------------------------- #
# Environment metadata
# --------------------------------------------------------------------------- #

def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _meminfo() -> dict:
    out = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                out[k + "_kB"] = int(v.split()[0])
    except OSError:
        pass
    return out


def _cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def clocks_shared() -> bool:
    """True when the harness's perf_counter and the fake's monotonic are the same
    system-wide clock, so client and fake timestamps can be compared directly."""
    a = time.get_clock_info("perf_counter").implementation
    b = time.get_clock_info("monotonic").implementation
    return a == b and "CLOCK_MONOTONIC" in a


def environment_metadata(argv: list[str], measurement_ticket: str | None = None) -> dict:
    versions = {}
    for p in PACKAGES:
        try:
            versions[p] = importlib.metadata.version(p)
        except importlib.metadata.PackageNotFoundError:
            versions[p] = None
    return {
        "harness_origin": HARNESS_ORIGIN,
        "measurement_ticket": measurement_ticket,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("branch", "--show-current"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "kernel": platform.release(),
        "wsl": "microsoft" in platform.release().lower(),
        "cpu_model": _cpu_model(),
        "logical_cpus": os.cpu_count(),
        "memory": _meminfo(),
        "packages": versions,
        "server_argv_template": uvicorn_argv(0),
        "server_processes": 1,
        "server_workers": 1,
        "harness_argv": argv,
        "clocks": {k: time.get_clock_info(k).implementation
                   for k in ("perf_counter", "monotonic")},
        "clocks_shared": clocks_shared(),
        "harness_sha256": {f: _sha256(REPO_ROOT / "benchmarks" / f) for f in (
            "run_capacity.py", "fake_provider.py", "stats.py", "workloads.py")},
        "workloads": [w.describe() for w in WORKLOADS.values()],
        "percentile_method": "nearest-rank, no interpolation; p99 only if pooled n >= "
                             f"{stats.P99_MIN_SAMPLES}",
        "load_model": "closed loop: C workers, one persistent HTTP/1.1 connection each, "
                      "back-to-back requests until N measured requests are issued",
        "guards": {
            "host_safety_rss_kb": RSS_GUARD_KB,
            "host_safety_memavailable_kb": MEMAVAIL_GUARD_KB,
            "escalation_p95_s": P95_ESCALATION_GUARD_S,
            "escalation_on_previous_failures": True,
        },
    }


# --------------------------------------------------------------------------- #
# Processes
# --------------------------------------------------------------------------- #

def uvicorn_argv(port: int) -> list[str]:
    return [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1",
            "--port", str(port), "--loop", "asyncio", "--http", "h11"]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http(port: int, method: str, path: str, body: bytes | None = None,
          timeout: float = 10.0) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


class QuoteCheckServer:
    def __init__(self, env: dict, log_file: Path):
        self.port = free_port()
        self.argv = uvicorn_argv(self.port)
        self._log = open(log_file, "w")
        self.proc = subprocess.Popen(self.argv, cwd=REPO_ROOT, env=env,
                                     stdout=self._log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"uvicorn exited early (see {log_file})")
            try:
                if _http(self.port, "GET", "/health", timeout=2)[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        self.stop()
        raise RuntimeError("uvicorn did not become healthy within 30 s")

    @property
    def pid(self) -> int:
        return self.proc.pid

    def stop(self) -> None:
        _stop(self.proc)
        self._log.close()


class FakeProviderProcess:
    def __init__(self, log_file: Path):
        env = dict(os.environ)
        self._log = open(log_file, "w")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "benchmarks.fake_provider", "--port", "0"],
            cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=self._log, text=True)
        line = self.proc.stdout.readline().strip()
        if not line.startswith("READY "):
            self.stop()
            raise RuntimeError(f"fake provider failed to start: {line!r}")
        parts = line.split()
        self.port = int(parts[1])
        self.output_chars = int(parts[2].split("=")[1])
        self.base_url = f"http://127.0.0.1:{self.port}/v1"
        assert_loopback_url(self.base_url)

    def stats(self) -> dict:
        return json.loads(_http(self.port, "GET", "/__stats")[1])

    def wait_idle(self, timeout: float = 5.0) -> dict:
        """Wait for handler threads to finish their bookkeeping after replying."""
        deadline = time.monotonic() + timeout
        snap = self.stats()
        while snap["in_flight"] and time.monotonic() < deadline:
            time.sleep(0.02)
            snap = self.stats()
        return snap

    def attempts(self) -> list[dict]:
        return json.loads(_http(self.port, "GET", "/__attempts")[1])["attempts"]

    def reset(self, **cfg) -> dict:
        self.wait_idle()
        body = json.dumps(cfg).encode() if cfg else None
        return json.loads(_http(self.port, "POST", "/__reset", body)[1])

    def stop(self) -> None:
        _stop(self.proc)
        self._log.close()


# --------------------------------------------------------------------------- #
# /proc sampling (Linux; stdlib only)
# --------------------------------------------------------------------------- #

_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def cpu_seconds(pid: int) -> float | None:
    try:
        rest = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return (int(rest[11]) + int(rest[12])) / _CLK_TCK  # utime + stime
    except (OSError, IndexError, ValueError):
        return None


def _proc_status(pid: int) -> tuple[int | None, int | None]:
    threads = rss = None
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("Threads:"):
                threads = int(line.split()[1])
            elif line.startswith("VmRSS:"):
                rss = int(line.split()[1])
    except OSError:
        pass
    return threads, rss


def _fd_count(pid: int) -> int | None:
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except OSError:
        return None


class ProcSampler(threading.Thread):
    """Samples server threads / RSS / open fds and host MemAvailable every 100 ms."""

    def __init__(self, pid: int, interval: float = 0.1):
        super().__init__(daemon=True)
        self.pid, self.interval = pid, interval
        self._lock = threading.Lock()
        self._halt = threading.Event()
        self.guard: str | None = None
        self.reset_peaks()

    def reset_peaks(self) -> None:
        with self._lock:
            self._peaks = {"threads": 0, "rss_kb": 0, "fds": 0}

    def peaks(self) -> dict:
        with self._lock:
            return dict(self._peaks)

    def run(self) -> None:
        while not self._halt.is_set():
            threads, rss = _proc_status(self.pid)
            fds = _fd_count(self.pid)
            memavail = _meminfo().get("MemAvailable_kB")
            with self._lock:
                for k, v in (("threads", threads), ("rss_kb", rss), ("fds", fds)):
                    if v is not None and v > self._peaks[k]:
                        self._peaks[k] = v
            if rss is not None and rss > RSS_GUARD_KB and not self.guard:
                self.guard = f"host_safety:server_rss_kb={rss}"
            if memavail is not None and memavail < MEMAVAIL_GUARD_KB and not self.guard:
                self.guard = f"host_safety:host_memavailable_kb={memavail}"
            self._halt.wait(self.interval)

    def stop(self) -> None:
        self._halt.set()


# --------------------------------------------------------------------------- #
# Closed-loop load client
# --------------------------------------------------------------------------- #

def run_load(port: int, *, method: str, path: str, bodies: list[bytes | None],
             concurrency: int, abort: threading.Event | None = None,
             timeout_s: float = 180.0, clock_out: dict | None = None
             ) -> tuple[list[dict], float]:
    """Issue ``len(bodies)`` requests with ``concurrency`` workers.

    Returns per-request records (times relative to the shared start instant)
    and the wall time from start to the last response. If ``clock_out`` is
    given, ``clock_out["t0"]`` receives that start instant (``perf_counter``).
    """
    n = len(bodies)
    next_idx = [0]
    idx_lock = threading.Lock()
    start = threading.Event()
    results: list[list[dict]] = [[] for _ in range(concurrency)]
    t0_box = [0.0]

    def take() -> int | None:
        with idx_lock:
            if next_idx[0] >= n or (abort is not None and abort.is_set()):
                return None
            i = next_idx[0]
            next_idx[0] += 1
            return i

    def worker(wid: int) -> None:
        out = results[wid]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout_s)
        start.wait()
        while (i := take()) is not None:
            body = bodies[i]
            headers = {"Content-Type": "application/json"} if body is not None else {}
            ts = time.perf_counter()
            status, data, err = None, b"", None
            try:
                conn.request(method, path, body=body, headers=headers)
                resp = conn.getresponse()
                data = resp.read()
                status = resp.status
            except Exception as exc:  # noqa: BLE001 - recorded, class name only
                err = f"client_exception:{type(exc).__name__}"
                conn.close()
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout_s)
            te = time.perf_counter()
            out.append({"request_index": i, "worker": wid, "_ts": ts, "_te": te,
                        "http_status": status, "_data": data, "error_code": err})
        conn.close()

    threads = [threading.Thread(target=worker, args=(w,), daemon=True)
               for w in range(concurrency)]
    for t in threads:
        t.start()
    t0_box[0] = time.perf_counter()
    if clock_out is not None:
        clock_out["t0"] = t0_box[0]
    start.set()
    for t in threads:
        t.join()

    t0 = t0_box[0]
    records = []
    last_end = t0
    for rs in results:
        for r in rs:
            data = r.pop("_data")
            ts, te = r.pop("_ts"), r.pop("_te")
            last_end = max(last_end, te)
            r["t_start_s"] = round(ts - t0, 6)
            r["t_end_s"] = round(te - t0, 6)
            r["duration_s"] = round(te - ts, 6)
            r["success"] = r["http_status"] == 200
            r["request_id"] = None
            if data and path == "/analyze":
                try:
                    obj = json.loads(data)
                    if r["success"]:
                        r["request_id"] = obj["metadata"]["request_id"]
                    else:
                        r["error_code"] = obj["detail"]["code"]
                        r["request_id"] = obj["detail"]["request_id"]
                except (ValueError, KeyError, TypeError):
                    r["error_code"] = r["error_code"] or "unparseable_body"
            records.append(r)
    records.sort(key=lambda r: r["request_index"])
    return records, last_end - t0


# --------------------------------------------------------------------------- #
# Scenario execution
# --------------------------------------------------------------------------- #

def analyze_body(text: str) -> bytes:
    return json.dumps({"quote_text": text}).encode("utf-8")


def _read_log_slice(log_path: Path, offset: int) -> list[dict]:
    if not log_path.exists():
        return []
    with open(log_path, "rb") as f:
        f.seek(offset)
        return [json.loads(line) for line in f.read().splitlines() if line.strip()]


def _log_size(log_path: Path) -> int:
    return log_path.stat().st_size if log_path.exists() else 0


class Run:
    def __init__(self, run_dir: Path, trials: int):
        self.dir = run_dir
        self.server_dir = run_dir / "server"
        self.server_dir.mkdir(parents=True, exist_ok=False)
        self.trials = trials
        self._req_f = open(run_dir / "requests.jsonl", "a")
        self._trial_f = open(run_dir / "trials.jsonl", "a")
        self._scen_f = open(run_dir / "scenarios.jsonl", "a")
        self._extra: dict[str, object] = {}  # SCALE-003 files, created on first use
        self.host_guard: str | None = None

    def close(self) -> None:
        for f in (self._req_f, self._trial_f, self._scen_f, *self._extra.values()):
            f.close()

    def _append(self, name: str, obj: dict) -> None:
        if name not in self._extra:
            self._extra[name] = open(self.dir / name, "a")
        self._write(self._extra[name], obj)

    @staticmethod
    def _write(f, obj: dict) -> None:
        f.write(json.dumps(obj) + "\n")
        f.flush()

    def scenario(self, *, experiment: str, scenario: str, workload_id: str | None,
                 method: str, path: str, ladder: list[int], n_for, body_for,
                 use_openai: bool, fake: FakeProviderProcess | None = None,
                 fake_cfg: dict | None = None, seq_warmup: int = 20,
                 expected_attempts_per_request: int | None = None,
                 expect_failures: bool = False, join_attempts: bool = False) -> None:
        if self.host_guard:
            return
        log_path = self.server_dir / f"{scenario}__app_runs.jsonl"
        env = build_child_env(use_openai=use_openai, log_path=log_path,
                              base_url=fake.base_url if fake else None)
        if fake is not None:
            fake.reset(**(fake_cfg or {}))
        srv = QuoteCheckServer(env, self.server_dir / f"{scenario}__uvicorn.log")
        sampler = ProcSampler(srv.pid)
        sampler.start()
        meta = {
            "experiment": experiment, "scenario": scenario, "workload_id": workload_id,
            "method": method, "path": path, "server_argv": srv.argv,
            "analyzer_mode": ("openai(fake-provider)" if use_openai else "demo")
            if path == "/analyze" else "n/a",
            "env_overrides": {k: env[k] for k in (
                "QUOTECHECK_USE_OPENAI", "QUOTECHECK_MODEL", "OPENAI_BASE_URL")},
            "fake_provider": fake_cfg, "ladder_planned": ladder, "ladder_executed": [],
            "trials_per_point": self.trials, "seq_warmup_requests": seq_warmup,
            "burst_warmup_per_point": "2 x concurrency", "stopped_by": None,
        }
        if join_attempts:
            meta["join_attempts"] = True
        try:
            # Deterministic sequential warm-up (process start / first-request effects).
            warm, _ = run_load(srv.port, method=method, path=path,
                               bodies=[body_for(f"warm-seq-{i}") for i in range(seq_warmup)],
                               concurrency=1)
            meta["seq_warmup_failures"] = sum(1 for r in warm if not r["success"])
            if fake is not None and fake.wait_idle()["attempts_started"] == 0 and seq_warmup:
                raise RuntimeError("fail-closed: warm-up produced no fake-provider attempts")
            if (meta["seq_warmup_failures"] and not expect_failures):
                raise RuntimeError(f"warm-up failures in {scenario}")

            prev = None
            for c in ladder:
                stop = self._escalation_stop(prev, sampler, expect_failures)
                if stop:
                    meta["stopped_by"] = stop
                    break
                prev = self._point(srv, sampler, meta, fake, log_path, c, n_for(c), body_for,
                                   expected_attempts_per_request, join_attempts)
                meta["ladder_executed"].append(c)
                if self.host_guard:
                    meta["stopped_by"] = self.host_guard
                    break
        finally:
            sampler.stop()
            srv.stop()
            self._write(self._scen_f, meta)
        print(f"  done {scenario}: ladder={meta['ladder_executed']} "
              f"stopped_by={meta['stopped_by']}", flush=True)

    def _join_attempts(self, key: dict, trial: int, fake: "FakeProviderProcess", t0: float,
                       wall: float, recs: list[dict], bodies: list[bytes | None],
                       trial_rec: dict) -> None:
        """SCALE-003: attach each request's fake-provider attempts (by marker) and
        derive its pre/provider/post phases plus trial-level provider occupancy.

        Fail-closed: ``attempts_joined`` is False unless the clocks are shared,
        every request's marker is found, and the fake's per-request attempt count
        equals QuoteCheck's logged ``provider_attempts``.
        """
        atts = fake.attempts()
        for a in atts:
            self._append("provider_attempts.jsonl", {**key, "trial": trial, "t0": t0, **a})
        by_marker: dict[str, list[dict]] = {}
        for a in atts:
            by_marker.setdefault(a["marker"], []).append(a)
        joined = clocks_shared()
        for r in recs:
            body = bodies[r["request_index"]] or b""
            m = MARKER_RE.search(body.decode("utf-8", errors="replace"))
            mine = by_marker.get(m.group(1), []) if m else []
            d = stats.decompose_request(t0 + r["t_start_s"], t0 + r["t_end_s"], mine)
            r.update(d)
            if not d or d["fake_attempts"] != r.get("provider_attempts"):
                joined = False
        joined = joined and sum(len(v) for v in by_marker.values()) == len(atts)
        intervals = [(a["t_start"], a["t_end"]) for a in atts if a["t_end"] is not None]
        trial_rec["attempts_joined"] = joined
        trial_rec["t0_monotonic"] = t0
        trial_rec["provider_mean_in_flight"] = round(
            stats.mean_in_flight(intervals, t0, t0 + wall), 3)
        trial_rec["provider_time_frac_in_flight_ge_40"] = round(
            stats.time_frac_at_least(intervals, ANYIO_DEFAULT_TOKENS, t0, t0 + wall), 4)
        if not joined:
            print(f"    WARNING: attempt join failed {key} trial {trial}", flush=True)

    # ------------------------------------------------------------------ #
    # SCALE-003 Experiment B: /health under sustained slow /analyze load
    # ------------------------------------------------------------------ #

    def health(self, *, scenario: str, latency_s: float, ladder: list[int], probes_n: int,
               fake: "FakeProviderProcess", body_for, seq_warmup: int, seed: int,
               gap_s: tuple[float, float] = (0.2, 0.6)) -> None:
        """Idle control, then for each C: start closed-loop /analyze load, confirm
        provider saturation on the *fake* (a separate process, so confirming uses
        no QuoteCheck worker token), wait one further provider period, then issue
        ``probes_n`` sequential /health probes (fresh connection each, seeded
        irregular gaps), stop the load and let it drain.

        Each probe is later tagged with the exact provider in-flight count at its
        send and receive instants (from the fake's attempt log) and the number of
        analysis requests outstanding at the client at its send instant.
        """
        if self.host_guard:
            return
        log_path = self.server_dir / f"{scenario}__app_runs.jsonl"
        env = build_child_env(use_openai=True, log_path=log_path, base_url=fake.base_url)
        fake.reset(latency_s=latency_s, mode="success")
        srv = QuoteCheckServer(env, self.server_dir / f"{scenario}__uvicorn.log")
        sampler = ProcSampler(srv.pid)
        sampler.start()
        rng = random.Random(seed)
        meta = {"experiment": "health", "scenario": scenario, "server_argv": srv.argv,
                "analyzer_mode": "openai(fake-provider)",
                "fake_provider": {"latency_s": latency_s, "mode": "success"},
                "ladder_planned": ladder, "ladder_executed": [], "probes_per_point": probes_n,
                "probe_gap_s_uniform": list(gap_s), "probe_seed": seed,
                "probe_timeout_s": HEALTH_PROBE_TIMEOUT_S, "seq_warmup_requests": seq_warmup,
                "saturation_gate": f"fake in_flight >= min(C, {ANYIO_DEFAULT_TOKENS}), "
                                   "then one further provider period",
                "points": [], "stopped_by": None}
        try:
            warm, _ = run_load(srv.port, method="POST", path="/analyze",
                               bodies=[body_for(f"warm-seq-{i}") for i in range(seq_warmup)],
                               concurrency=1)
            if any(not r["success"] for r in warm):
                raise RuntimeError(f"warm-up failures in {scenario}")
            if seq_warmup and fake.wait_idle()["attempts_started"] == 0:
                raise RuntimeError("fail-closed: warm-up produced no fake-provider attempts")

            fake.reset()
            sampler.reset_peaks()
            idle = self._probe_series(srv.port, probes_n, rng, gap_s, stop=None)
            atts = fake.attempts()
            self._record_probes(scenario, 0, latency_s, idle, atts, [], None)
            meta["points"].append({"concurrency": 0, "probes": len(idle),
                                   "threads_peak": sampler.peaks()["threads"]})
            print(f"  {scenario} idle: {self._probe_line(idle)}", flush=True)

            for c in ladder:
                if sampler.guard or self.host_guard:
                    meta["stopped_by"] = sampler.guard or self.host_guard
                    self.host_guard = self.host_guard or sampler.guard
                    break
                point = self._health_point(srv, sampler, fake, scenario, latency_s, c,
                                           probes_n, rng, gap_s, body_for)
                meta["points"].append(point)
                meta["ladder_executed"].append(c)
        finally:
            sampler.stop()
            srv.stop()
            self._write(self._scen_f, meta)
        print(f"  done {scenario}: ladder={meta['ladder_executed']} "
              f"stopped_by={meta['stopped_by']}", flush=True)

    def _health_point(self, srv, sampler, fake, scenario, latency_s, c, probes_n, rng,
                      gap_s, body_for) -> dict:
        fake.reset()
        sampler.reset_peaks()
        target = min(c, ANYIO_DEFAULT_TOKENS)
        n_load = c * 200  # far more than the probe window needs; stopped via abort
        bodies = [body_for(f"hl-c{c}-{i}") for i in range(n_load)]
        abort = threading.Event()
        clock: dict = {}
        box: dict = {}
        cpu0 = cpu_seconds(srv.pid)

        def load():
            box["recs"], box["wall"] = run_load(srv.port, method="POST", path="/analyze",
                                                bodies=bodies, concurrency=c, abort=abort,
                                                clock_out=clock)
        lt = threading.Thread(target=load, daemon=True)
        lt.start()
        point = {"concurrency": c, "gate_target_in_flight": target}
        deadline = time.monotonic() + 3 * latency_s + 10
        reached = None
        while time.monotonic() < deadline:
            if fake.stats()["in_flight"] >= target:
                reached = time.monotonic()
                break
            time.sleep(0.02)
        probes = []
        if reached is None:
            point["gate"] = "gate_failed"
            print(f"    WARNING: {scenario} C={c} saturation gate not reached; not probed",
                  flush=True)
        else:
            point["gate"] = "reached"
            time.sleep(latency_s)  # let the >40 queue and post-provider waiters form
            probes = self._probe_series(srv.port, probes_n, rng, gap_s,
                                        stop=lambda: bool(sampler.guard))
        abort.set()
        lt.join()
        cpu1 = cpu_seconds(srv.pid)
        fake.wait_idle(timeout=3 * latency_s + 10)
        atts = fake.attempts()
        t0 = clock["t0"]
        recs = box["recs"]
        for a in atts:
            self._append("provider_attempts.jsonl", {"experiment": "health_load",
                                                     "scenario": scenario, "concurrency": c,
                                                     "trial": 1, "t0": t0, **a})
        by_marker: dict[str, list[dict]] = {}
        for a in atts:
            by_marker.setdefault(a["marker"], []).append(a)
        for r in recs:
            m = MARKER_RE.search(bodies[r["request_index"]].decode("utf-8", errors="replace"))
            r.update(stats.decompose_request(t0 + r["t_start_s"], t0 + r["t_end_s"],
                                             by_marker.get(m.group(1), []) if m else []))
            self._append("health_load_requests.jsonl", {
                "experiment": "health_load", "scenario": scenario, "concurrency": c,
                "t0": t0, **r})
        self._record_probes(scenario, c, latency_s, probes, atts, recs, t0)
        peaks = sampler.peaks()
        point.update({
            "probes": len(probes), "load_requests": len(recs),
            "load_failures": sum(1 for r in recs if not r["success"]),
            "load_wall_s": round(box["wall"], 3),
            "server_cpu_s": round(cpu1 - cpu0, 3) if None not in (cpu0, cpu1) else None,
            "threads_peak": peaks["threads"], "rss_kb_peak": peaks["rss_kb"],
            "fds_peak": peaks["fds"], "provider_attempts": len(atts),
            "provider_peak_in_flight": fake.stats()["peak_in_flight"],
            "guard": sampler.guard})
        if sampler.guard:
            self.host_guard = sampler.guard
        print(f"    {scenario} C={c}: {self._probe_line(probes)} load_reqs={len(recs)} "
              f"load_fail={point['load_failures']} thr_peak={peaks['threads']} "
              f"prov_peak={point['provider_peak_in_flight']}", flush=True)
        return point

    @staticmethod
    def _probe_series(port: int, n: int, rng: random.Random, gap_s: tuple[float, float],
                      stop) -> list[dict]:
        """``n`` sequential GET /health probes, never more than one outstanding.
        The next probe is sent at max(previous send + seeded gap, previous receive)."""
        out = []
        next_send = time.perf_counter()
        for i in range(n):
            if stop is not None and stop():
                break
            delay = next_send - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            ts = time.perf_counter()
            status, err = None, None
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=HEALTH_PROBE_TIMEOUT_S)
            try:
                conn.request("GET", "/health")
                resp = conn.getresponse()
                resp.read()
                status = resp.status
            except Exception as exc:  # noqa: BLE001 - recorded, class name only
                err = f"client_exception:{type(exc).__name__}"
            finally:
                conn.close()
            te = time.perf_counter()
            out.append({"probe_index": i, "t_send": ts, "t_recv": te,
                        "duration_s": round(te - ts, 6), "http_status": status,
                        "error_code": err})
            next_send = ts + rng.uniform(*gap_s)
        return out

    def _record_probes(self, scenario, c, latency_s, probes, atts, load_recs, t0) -> None:
        intervals = [(a["t_start"], a["t_end"]) for a in atts if a["t_end"] is not None]
        load_iv = [(t0 + r["t_start_s"], t0 + r["t_end_s"]) for r in load_recs] if t0 else []
        for pr in probes:
            self._append("health_probes.jsonl", {
                "experiment": "health", "scenario": scenario, "concurrency": c,
                "provider_latency_s": latency_s, **pr,
                "provider_in_flight_at_send": stats.in_flight_at(intervals, pr["t_send"]),
                "provider_in_flight_at_recv": stats.in_flight_at(intervals, pr["t_recv"]),
                "analysis_outstanding_at_send": stats.in_flight_at(load_iv, pr["t_send"])
                if load_iv else 0})

    @staticmethod
    def _probe_line(probes: list[dict]) -> str:
        lat = stats.latency_summary(pr["duration_s"] for pr in probes)
        bad = sum(1 for pr in probes if pr["http_status"] != 200)
        return (f"probes={len(probes)} non200={bad} p50={lat.get('p50_ms')} "
                f"p95={lat.get('p95_ms')} max={lat.get('max_ms')}")

    @staticmethod
    def _escalation_stop(prev: dict | None, sampler: ProcSampler,
                         expect_failures: bool) -> str | None:
        if sampler.guard:
            return sampler.guard
        if prev is None:
            return None
        if prev["failures"] and not expect_failures:
            return f"escalation:failures_at_C={prev['concurrency']}"
        if prev["p95_s"] > P95_ESCALATION_GUARD_S:
            return f"escalation:p95>{P95_ESCALATION_GUARD_S}s_at_C={prev['concurrency']}"
        return None

    def _point(self, srv, sampler, meta, fake, log_path, c, n, body_for,
               expected_attempts, join_attempts=False) -> dict:
        key = {"experiment": meta["experiment"], "scenario": meta["scenario"],
               "workload_id": meta["workload_id"], "concurrency": c}
        # Burst warm-up at the target concurrency (threads/connections spun up).
        run_load(srv.port, method=meta["method"], path=meta["path"],
                 bodies=[body_for(f"warm-c{c}-{i}") for i in range(2 * c)], concurrency=c)
        pooled, failures = [], 0
        for trial in range(1, self.trials + 1):
            if fake is not None:
                fake.reset()
            off = _log_size(log_path)
            sampler.reset_peaks()
            cpu0 = cpu_seconds(srv.pid)
            bodies = [body_for(f"c{c}-t{trial}-{i}") for i in range(n)]
            abort = threading.Event()
            watchdog_halt = threading.Event()

            def watchdog():
                while not watchdog_halt.wait(0.1):
                    if sampler.guard:
                        abort.set()
                        return
            wd = threading.Thread(target=watchdog, daemon=True)
            wd.start()
            epoch0, mono0 = time.time(), time.monotonic()
            clock: dict = {}
            recs, wall = run_load(srv.port, method=meta["method"], path=meta["path"],
                                  bodies=bodies, concurrency=c, abort=abort, clock_out=clock)
            clock_skew_s = (time.time() - epoch0) - (time.monotonic() - mono0)
            watchdog_halt.set()
            cpu1 = cpu_seconds(srv.pid)
            peaks = sampler.peaks()
            trial_rec = {**key, "trial": trial, "requests_planned": n,
                         "requests_issued": len(recs), "wall_s": round(wall, 6),
                         "server_cpu_s": round(cpu1 - cpu0, 3) if None not in (cpu0, cpu1) else None,
                         "server_threads_peak": peaks["threads"],
                         "server_rss_kb_peak": peaks["rss_kb"],
                         "server_fds_peak": peaks["fds"],
                         # Host suspend (e.g. a sleeping laptop/WSL VM) stops the
                         # monotonic clock but not wall time; such a trial is invalid.
                         "clock_skew_s": round(clock_skew_s, 3),
                         "suspend_suspected": abs(clock_skew_s) > SUSPEND_SKEW_GUARD_S}
            if meta["path"] == "/analyze":
                logs = _read_log_slice(log_path, off)
                by_id = {r["request_id"]: r for r in logs}
                for r in recs:
                    lr = by_id.get(r["request_id"])
                    r["server_latency_ms"] = lr["latency_ms"] if lr else None
                    r["provider_attempts"] = lr["provider_attempts"] if lr else None
                trial_rec["log_records"] = len(logs)
                if fake is not None:
                    pstats = fake.wait_idle()
                    log_attempts = sum(r.get("provider_attempts") or 0 for r in logs)
                    trial_rec["provider"] = pstats
                    trial_rec["log_provider_attempts"] = log_attempts
                    ok = (pstats["attempts_started"] == log_attempts
                          and pstats["attempts_completed"] == pstats["attempts_started"]
                          and len(logs) == len(recs))
                    if expected_attempts is not None:
                        ok = ok and log_attempts == expected_attempts * len(recs)
                    trial_rec["reconciled"] = ok
                    if not ok:
                        print(f"    WARNING: reconciliation failed {key} trial {trial}: "
                              f"fake={pstats} log_attempts={log_attempts} logs={len(logs)}",
                              flush=True)
                    if join_attempts:
                        self._join_attempts(key, trial, fake, clock["t0"], wall, recs,
                                            bodies, trial_rec)
            if trial_rec["suspend_suspected"]:
                print(f"    WARNING: host suspend suspected (skew {clock_skew_s:.1f}s) "
                      f"{key} trial {trial}; trial is invalid", flush=True)
            if sampler.guard:
                trial_rec["guard_stop"] = sampler.guard
                self.host_guard = sampler.guard
            for r in recs:
                self._write(self._req_f, {**key, "trial": trial, **r})
            self._write(self._trial_f, trial_rec)
            pooled.extend(r["duration_s"] for r in recs)
            failures += sum(1 for r in recs if not r["success"])
            lat = stats.latency_summary(r["duration_s"] for r in recs)
            print(f"    {meta['scenario']} C={c} trial={trial} n={len(recs)} "
                  f"fail={sum(1 for r in recs if not r['success'])} wall={wall:.2f}s "
                  f"rps={len(recs) / wall if wall else 0:.1f} p50={lat.get('p50_ms')} "
                  f"p95={lat.get('p95_ms')} thr_peak={peaks['threads']}"
                  + (f" prov_peak={trial_rec['provider']['peak_in_flight']}"
                     f" att={trial_rec['provider']['attempts_started']}"
                     if "provider" in trial_rec else ""), flush=True)
            if self.host_guard:
                break
        p95 = stats.nearest_rank(sorted(pooled), 95) if pooled else 0.0
        return {"concurrency": c, "failures": failures, "p95_s": p95}


# --------------------------------------------------------------------------- #
# Experiment plans
# --------------------------------------------------------------------------- #

def plan(quick: bool) -> dict:
    if quick:
        return {"demo_ladder": [1, 4], "demo_n": 20, "demo_workloads": ["normal"],
                "fake_ladder": [1, 4], "fake_latencies": {"lat50ms": 0.05},
                "fake_n": lambda c: max(2 * c, 4), "retry_points": [1, 4],
                "retry_latency": 0.05, "fail_always_c": 2, "fail_always_n": 4,
                "seq_warmup_demo": 5, "seq_warmup_fake": 2,
                # SCALE-003
                "sat_latencies": {"lat100ms": (0.1, [1, 4])},
                "health_latencies": {"lat200ms": 0.2}, "health_ladder": [2, 4],
                "health_probes": 5, "retry_sat_latency": 0.1, "retry_sat_points": [2, 4],
                "retry_sat_fail_always_c": 4, "retry_sat_fail_always_n": 8}
    return {"demo_ladder": [1, 2, 4, 8, 16, 32, 64], "demo_n": 200,
            "demo_workloads": list(WORKLOADS),
            "fake_ladder": [1, 2, 4, 8, 16, 32, 48, 64],
            "fake_latencies": {"lat250ms": 0.25, "lat1s": 1.0},
            "fake_n": lambda c: max(4 * c, 16), "retry_points": [1, 8, 32],
            "retry_latency": 0.25, "fail_always_c": 4, "fail_always_n": 16,
            "seq_warmup_demo": 20, "seq_warmup_fake": 5,
            # SCALE-003
            "sat_latencies": {"lat1s": (1.0, [1, 16, 32, 40, 48, 64]),
                              "lat3s": (3.0, [16, 32, 40, 48, 64]),
                              "lat5s": (5.0, [16, 32, 40, 48, 64])},
            "health_latencies": {"lat3s": 3.0, "lat5s": 5.0}, "health_ladder": [32, 40, 64],
            "health_probes": 40, "retry_sat_latency": 3.0, "retry_sat_points": [32, 40, 64],
            "retry_sat_fail_always_c": 64, "retry_sat_fail_always_n": 128}


def run_demo(run: Run, p: dict) -> None:
    for wid in p["demo_workloads"]:
        body = analyze_body(WORKLOADS[wid].text)
        run.scenario(experiment="demo_http", scenario=f"demo_analyze_{wid}", workload_id=wid,
                     method="POST", path="/analyze", ladder=p["demo_ladder"],
                     n_for=lambda c: p["demo_n"], body_for=lambda tag, b=body: b,
                     use_openai=False, seq_warmup=p["seq_warmup_demo"])
    run.scenario(experiment="demo_http", scenario="health_floor", workload_id=None,
                 method="GET", path="/health", ladder=p["demo_ladder"],
                 n_for=lambda c: p["demo_n"], body_for=lambda tag: None,
                 use_openai=False, seq_warmup=p["seq_warmup_demo"])


def run_fake(run: Run, p: dict, fake: FakeProviderProcess) -> None:
    body = analyze_body(WORKLOADS["normal"].text)
    for name, lat in p["fake_latencies"].items():
        run.scenario(experiment="fake_provider", scenario=f"fake_{name}", workload_id="normal",
                     method="POST", path="/analyze", ladder=p["fake_ladder"],
                     n_for=p["fake_n"], body_for=lambda tag, b=body: b, use_openai=True,
                     fake=fake, fake_cfg={"latency_s": lat, "mode": "success"},
                     seq_warmup=p["seq_warmup_fake"], expected_attempts_per_request=1)


def run_retry(run: Run, p: dict, fake: FakeProviderProcess, run_id: str) -> None:
    text = WORKLOADS["normal"].text
    lat = p["retry_latency"]
    ms = int(lat * 1000)

    def marked(scen):
        return lambda tag: analyze_body(f"{text}\n[bench-marker:{run_id}-{scen}-{tag}]")

    scen = f"retry_fail_first_{ms}ms"
    run.scenario(experiment="retry", scenario=scen, workload_id="normal", method="POST",
                 path="/analyze", ladder=p["retry_points"], n_for=p["fake_n"],
                 body_for=marked(scen), use_openai=True, fake=fake,
                 fake_cfg={"latency_s": lat, "mode": "fail_first"},
                 seq_warmup=p["seq_warmup_fake"], expected_attempts_per_request=2)
    scen = f"retry_fail_always_{ms}ms"
    run.scenario(experiment="retry", scenario=scen, workload_id="normal", method="POST",
                 path="/analyze", ladder=[p["fail_always_c"]],
                 n_for=lambda c: p["fail_always_n"], body_for=marked(scen), use_openai=True,
                 fake=fake, fake_cfg={"latency_s": lat, "mode": "fail_always"},
                 seq_warmup=p["seq_warmup_fake"], expected_attempts_per_request=2,
                 expect_failures=True)


def _marked(run_id: str, scen: str):
    text = WORKLOADS["normal"].text
    return lambda tag: analyze_body(f"{text}\n[bench-marker:{run_id}-{scen}-{tag}]")


def run_saturation(run: Run, p: dict, fake: FakeProviderProcess, run_id: str) -> None:
    for name, (lat, ladder) in p["sat_latencies"].items():
        scen = f"sat_{name}"
        run.scenario(experiment="saturation", scenario=scen, workload_id="normal",
                     method="POST", path="/analyze", ladder=ladder, n_for=p["fake_n"],
                     body_for=_marked(run_id, scen), use_openai=True, fake=fake,
                     fake_cfg={"latency_s": lat, "mode": "success"},
                     seq_warmup=p["seq_warmup_fake"], expected_attempts_per_request=1,
                     join_attempts=True)


def run_health(run: Run, p: dict, fake: FakeProviderProcess, run_id: str) -> None:
    for i, (name, lat) in enumerate(p["health_latencies"].items()):
        scen = f"health_{name}"
        run.health(scenario=scen, latency_s=lat, ladder=p["health_ladder"],
                   probes_n=p["health_probes"], fake=fake, body_for=_marked(run_id, scen),
                   seq_warmup=p["seq_warmup_fake"], seed=3003 + i)


def run_retry_sat(run: Run, p: dict, fake: FakeProviderProcess, run_id: str) -> None:
    lat = p["retry_sat_latency"]
    ms = int(lat * 1000)
    scen = f"retry_sat_fail_first_{ms}ms"
    run.scenario(experiment="retry_sat", scenario=scen, workload_id="normal", method="POST",
                 path="/analyze", ladder=p["retry_sat_points"], n_for=p["fake_n"],
                 body_for=_marked(run_id, scen), use_openai=True, fake=fake,
                 fake_cfg={"latency_s": lat, "mode": "fail_first"},
                 seq_warmup=p["seq_warmup_fake"], expected_attempts_per_request=2,
                 join_attempts=True)
    scen = f"retry_sat_fail_always_{ms}ms"
    run.scenario(experiment="retry_sat", scenario=scen, workload_id="normal", method="POST",
                 path="/analyze", ladder=[p["retry_sat_fail_always_c"]],
                 n_for=lambda c: p["retry_sat_fail_always_n"], body_for=_marked(run_id, scen),
                 use_openai=True, fake=fake, fake_cfg={"latency_s": lat, "mode": "fail_always"},
                 seq_warmup=p["seq_warmup_fake"], expected_attempts_per_request=2,
                 expect_failures=True, join_attempts=True)


SCALE003_EXPERIMENTS = ("saturation", "health", "retry_sat")
_SCALE003_PLAN_KEYS = {"sat_latencies", "health_latencies", "health_ladder", "health_probes",
                       "retry_sat_latency", "retry_sat_points", "retry_sat_fail_always_c",
                       "retry_sat_fail_always_n"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description="SCALE-001 capacity characterization (local only)")
    ap.add_argument("--experiment",
                    choices=("demo", "fake", "retry", "all", *SCALE003_EXPERIMENTS),
                    nargs="+", default=["all"],
                    help="'all' = demo fake retry (SCALE-001 set); SCALE-003 experiments "
                         "must be named explicitly")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--ticket", default=None,
                    help="ticket this measurement is for, recorded in env.json (metadata only)")
    ap.add_argument("--trials", type=int, default=None, help="default 3 (1 with --quick)")
    ap.add_argument("--quick", action="store_true", help="tiny smoke run, not evidence")
    args = ap.parse_args(argv)

    exps = set(args.experiment) - {"all"}
    if "all" in args.experiment:
        exps |= {"demo", "fake", "retry"}
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or (f"quick-{ts}" if args.quick else f"run-{ts}")
    run_dir = RESULTS_ROOT / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        print(f"refusing to overwrite existing results dir {run_dir}", file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True, exist_ok=True)
    trials = args.trials or (1 if args.quick else 3)
    p = plan(args.quick)

    env_meta = environment_metadata(["-m", "benchmarks.run_capacity", *argv],
                                    measurement_ticket=args.ticket)
    env_meta.update({"run_id": run_id, "quick": args.quick, "experiments": sorted(exps),
                     "trials_per_point": trials,
                     # SCALE-003 plan keys are recorded only for runs that use them,
                     # so a SCALE-001-style run's env.json plan is unchanged.
                     "plan": {k: v for k, v in p.items() if not callable(v) and (
                         k not in _SCALE003_PLAN_KEYS or exps & set(SCALE003_EXPERIMENTS))},
                     "fake_n_rule": "max(2*C, 4)" if args.quick else "max(4*C, 16)"})
    run = Run(run_dir, trials)
    fake = None
    t_start = time.monotonic()
    try:
        if "demo" in exps:
            print("== Experiment A: Demo via real localhost HTTP", flush=True)
            run_demo(run, p)
        if exps & {"fake", "retry", *SCALE003_EXPERIMENTS}:
            if exps & set(SCALE003_EXPERIMENTS) and not clocks_shared():
                raise RuntimeError("fail-closed: perf_counter and monotonic are not one "
                                   "shared CLOCK_MONOTONIC; attempt timelines can't be joined")
            fake = FakeProviderProcess(run.server_dir / "fake_provider.log")
            env_meta["fake_provider_output_chars"] = fake.output_chars
            if "fake" in exps:
                print("== Experiment B: fake provider latency classes", flush=True)
                run_fake(run, p, fake)
            if "retry" in exps:
                print("== Experiment B2: retry amplification spot checks", flush=True)
                run_retry(run, p, fake, run_id)
            if "saturation" in exps:
                print("== SCALE-003 A: slow-provider saturation", flush=True)
                run_saturation(run, p, fake, run_dir.name)
            if "health" in exps:
                print("== SCALE-003 B: /health under saturation", flush=True)
                run_health(run, p, fake, run_dir.name)
            if "retry_sat" in exps:
                print("== SCALE-003 C: retry under saturation", flush=True)
                run_retry_sat(run, p, fake, run_dir.name)
    finally:
        if fake is not None:
            fake.stop()
        run.close()
        env_meta["host_safety_guard"] = run.host_guard
        env_meta["elapsed_s"] = round(time.monotonic() - t_start, 1)
        (run_dir / "env.json").write_text(json.dumps(env_meta, indent=2) + "\n")

    rows = stats.summarize_dir(run_dir)
    (run_dir / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(stats.format_table(rows))
    probes = stats.read_jsonl(run_dir / "health_probes.jsonl")
    if probes:
        hrows = stats.summarize_health(probes, ANYIO_DEFAULT_TOKENS)
        (run_dir / "health_summary.json").write_text(json.dumps(hrows, indent=2) + "\n")
        for h in hrows:
            a = h["all_probes"]
            sat = h[f"probes_sent_at_provider_in_flight_eq_{ANYIO_DEFAULT_TOKENS}"]
            print(f"health {h['scenario']} C={h['concurrency']}: all n={a['n']} "
                  f"p50={a.get('p50_ms')} p95={a.get('p95_ms')} max={a.get('max_ms')} "
                  f"status={a['status_counts']} | at-40 n={sat['n']} p50={sat.get('p50_ms')} "
                  f"p95={sat.get('p95_ms')}")
    print(f"\nresults: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
