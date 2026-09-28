"""SCALE-004 diagnostic: event-loop cost of the two pieces of work SCALE-004 moved
onto (or added to) the asyncio event loop.

1. A ``capacity_exceeded`` rejection, end to end in-process (ASGI, no network),
   with the real synchronous JSONL rejection log vs. the log call replaced by a
   no-op. The difference is the synchronous logging share of a rejection.
2. FastAPI ``response_model`` validation + serialization of one realistic
   ``QuoteCheckResult`` (the fake provider's output), which now runs on the loop
   for the async ``/analyze`` endpoint.

Everything below runs on one thread, so each figure is the time the event loop
is blocked per item. It uses the real ``backend.app`` with a zero-capacity
admission budget; no provider, no server process, no network, zero cost.

    python -m benchmarks.diag_rejection_log [--n 5000] [--out path.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path
from unittest import mock

import httpx
from fastapi.responses import JSONResponse

from benchmarks import stats
from benchmarks.fake_provider import build_model_output_json


def _summ(samples_s: list[float]) -> dict:
    out = stats.latency_summary(samples_s)
    out["mean_us"] = round(statistics.fmean(samples_s) * 1e6, 1)
    out["p50_us"] = round(stats.nearest_rank(sorted(samples_s), 50) * 1e6, 1)
    out["p95_us"] = round(stats.nearest_rank(sorted(samples_s), 95) * 1e6, 1)
    return out


async def _rejections(appmod, n: int) -> list[float]:
    transport = httpx.ASGITransport(app=appmod.app)
    body = {"quote_text": "Replace brake pads: $240. Shop supplies: $35."}
    out = []
    async with httpx.AsyncClient(transport=transport, base_url="http://diag") as client:
        for _ in range(50):  # warm-up
            await client.post("/analyze", json=body)
        for _ in range(n):
            t = time.perf_counter()
            r = await client.post("/analyze", json=body)
            out.append(time.perf_counter() - t)
            assert r.status_code == 503 and r.json()["detail"]["code"] == "capacity_exceeded"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=5000)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    import backend.app as appmod
    from backend.core.admission import ProviderAdmission
    from backend.core.schema import QuoteCheckResult

    result = {"n": args.n}
    with tempfile.TemporaryDirectory() as td:
        log_path = str(Path(td) / "runs.jsonl")
        with mock.patch.object(appmod, "USE_OPENAI", True), \
             mock.patch.object(appmod, "ANALYZER_NAME", "openai"), \
             mock.patch.object(appmod, "APP_RUN_LOG_PATH", log_path), \
             mock.patch.object(appmod, "provider_admission", ProviderAdmission(0)):
            with_log = asyncio.run(_rejections(appmod, args.n))
            logged = sum(1 for _ in open(log_path))
            with mock.patch.object(appmod, "_safe_log", lambda **_k: None):
                without_log = asyncio.run(_rejections(appmod, args.n))
        # The log call alone, same record shape, same file.
        rec = json.loads(Path(log_path).read_text().splitlines()[-1])
        log_only = []
        for _ in range(args.n):
            t = time.perf_counter()
            appmod._safe_log(
                log_path=log_path, request_id=rec["request_id"],
                prompt_version=rec["prompt_version"], model=rec["model"], latency_ms=0,
                schema_valid=False, num_items=0, risk_counts=rec["risk_counts"],
                uncertainty={}, error=rec["error"], analyzer="openai", success=False,
                failure_category="capacity_exceeded", retryable=True, provider_attempts=0)
            log_only.append(time.perf_counter() - t)

    result["rejection_with_sync_log"] = _summ(with_log)
    result["rejection_log_disabled"] = _summ(without_log)
    result["log_call_only"] = _summ(log_only)
    result["log_records_written"] = logged
    result["sync_log_share_of_rejection_mean"] = round(
        1 - statistics.fmean(without_log) / statistics.fmean(with_log), 3)

    # response_model validation + serialization, exactly as FastAPI does it for
    # an async endpoint (fastapi/routing.py serialize_response, is_coroutine=True).
    route = next(r for r in appmod.app.routes if getattr(r, "path", None) == "/analyze")
    field = route.response_field
    payload = json.loads(build_model_output_json())
    obj = QuoteCheckResult.model_validate(payload)
    val = []
    for i in range(args.n + 50):
        t = time.perf_counter()
        value, errors = field.validate(obj, {}, loc=("response",))
        assert not errors
        body = JSONResponse(field.serialize(value, by_alias=True)).body
        if i >= 50:
            val.append(time.perf_counter() - t)
    result["response_model_validate_serialize"] = _summ(val)
    result["response_body_bytes"] = len(body)

    print(json.dumps(result, indent=2))
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
