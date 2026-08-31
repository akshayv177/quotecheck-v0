"""QC-2A deployment-readiness suite.

No paid API calls and no network: Demo mode is exercised through the real stub
analyzer, and the one integration test that needs import-time config runs an
isolated subprocess with ``OPENAI_API_KEY`` stripped from its environment.

Run: ``python -m unittest discover -s eval/tests -p 'test_*.py' -v`` from repo root.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.core.config import _normalize_origin, _parse_allowed_origins
from backend.core.schema import MAX_QUOTE_TEXT_CHARS

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_JSX = REPO_ROOT / "frontend" / "src" / "App.jsx"
DEMO_MODEL = "quotecheck-demo-analyzer"
DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


@contextlib.contextmanager
def demo_mode_app(*, openai_key=None):
    """Force ``backend.app`` into Demo mode with a chosen OPENAI_API_KEY value.

    Mirrors ``test_openai_reliability.openai_mode_app``: patch module attributes
    rather than mutate the environment, and redirect the run log to a throwaway
    path so the real ``logs/app_runs.jsonl`` is never touched.
    """
    import backend.app as appmod

    with contextlib.ExitStack() as es:
        es.enter_context(mock.patch.object(appmod, "USE_OPENAI", False))
        es.enter_context(mock.patch.object(appmod, "ANALYZER_NAME", "demo"))
        td = es.enter_context(tempfile.TemporaryDirectory())
        es.enter_context(mock.patch.object(appmod, "APP_RUN_LOG_PATH", str(Path(td) / "runs.jsonl")))
        # Prove the Demo path never constructs / calls the OpenAI client, and that
        # a missing key does not break Demo startup or /analyze.
        es.enter_context(mock.patch("backend.core.openai_analyzer.OPENAI_API_KEY", openai_key))
        openai_ctor = mock.MagicMock(name="OpenAI")
        es.enter_context(mock.patch("backend.core.openai_analyzer.OpenAI", openai_ctor))
        yield appmod, openai_ctor


# --------------------------------------------------------------------------- #
# 1. CORS origin parsing / validation
# --------------------------------------------------------------------------- #

class AllowedOriginParsingTests(unittest.TestCase):
    def test_default_origins_parse(self):
        self.assertEqual(
            _parse_allowed_origins(
                "http://localhost:5173,http://127.0.0.1:5173", explicitly_set=False
            ),
            DEFAULT_ORIGINS,
        )

    def test_configured_list_parses_in_order(self):
        self.assertEqual(
            _parse_allowed_origins(
                "https://a.vercel.app, https://b.vercel.app", explicitly_set=True
            ),
            ["https://a.vercel.app", "https://b.vercel.app"],
        )

    def test_whitespace_is_normalized(self):
        self.assertEqual(
            _parse_allowed_origins("   https://a.vercel.app   ", explicitly_set=True),
            ["https://a.vercel.app"],
        )

    def test_single_trailing_slash_is_normalized(self):
        self.assertEqual(_normalize_origin("https://a.vercel.app/"), "https://a.vercel.app")
        self.assertEqual(
            _parse_allowed_origins("https://a.vercel.app/", explicitly_set=True),
            ["https://a.vercel.app"],
        )

    def test_explicit_port_is_preserved(self):
        self.assertEqual(_normalize_origin("http://localhost:5173"), "http://localhost:5173")

    def test_wildcard_is_rejected(self):
        with self.assertRaises(RuntimeError):
            _parse_allowed_origins("*", explicitly_set=True)

    def test_missing_scheme_is_rejected(self):
        with self.assertRaises(RuntimeError):
            _parse_allowed_origins("a.vercel.app", explicitly_set=True)

    def test_url_with_path_query_or_fragment_is_rejected(self):
        for bad in (
            "https://a.vercel.app/path",
            "https://a.vercel.app/?q=1",
            "https://a.vercel.app/#frag",
        ):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                _normalize_origin(bad)

    def test_non_http_scheme_is_rejected(self):
        with self.assertRaises(RuntimeError):
            _normalize_origin("ftp://a.vercel.app")

    def test_explicitly_set_but_empty_is_rejected(self):
        with self.assertRaises(RuntimeError):
            _parse_allowed_origins("  ,  ", explicitly_set=True)

    def test_unset_empty_falls_back_to_no_origins(self):
        # explicitly_set=False + no usable entries -> [] (caller supplies the default string)
        self.assertEqual(_parse_allowed_origins("  ,  ", explicitly_set=False), [])

    def test_duplicates_are_deduped_deterministically(self):
        self.assertEqual(
            _parse_allowed_origins(
                "https://a.io, https://a.io/, https://b.io", explicitly_set=True
            ),
            ["https://a.io", "https://b.io"],
        )


# --------------------------------------------------------------------------- #
# 2. CORS wired into the app (default origins, in-process)
# --------------------------------------------------------------------------- #

class DefaultCorsBehaviourTests(unittest.TestCase):
    def setUp(self):
        import backend.app as appmod

        self.client = TestClient(appmod.app)

    def _preflight(self, origin):
        return self.client.options(
            "/analyze",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

    def test_allowed_origin_preflight_is_granted(self):
        r = self._preflight("http://localhost:5173")
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_disallowed_origin_preflight_is_not_granted(self):
        r = self._preflight("https://evil.example")
        self.assertNotEqual(r.headers.get("access-control-allow-origin"), "https://evil.example")
        self.assertIsNone(r.headers.get("access-control-allow-origin"))


# --------------------------------------------------------------------------- #
# 3. CORS wired into the app for a NON-default configured origin (subprocess).
#    config is import-time state, so this runs a clean child process rather
#    than reloading modules in-place.
# --------------------------------------------------------------------------- #

_SUBPROC_SNIPPET = r"""
import json
from fastapi.testclient import TestClient
import backend.app as appmod

client = TestClient(appmod.app)

def allow_origin(origin):
    r = client.options(
        "/analyze",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    return r.headers.get("access-control-allow-origin")

print(json.dumps({
    "configured": appmod.ALLOWED_ORIGINS,
    "match": allow_origin("https://example.vercel.app"),
    "other": allow_origin("https://other.example"),
}))
"""


class ConfiguredCorsIntegrationTests(unittest.TestCase):
    def test_configured_origin_is_honored_by_cors_middleware(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        env["QUOTECHECK_USE_OPENAI"] = "0"
        env["QUOTECHECK_ALLOWED_ORIGINS"] = "https://example.vercel.app"

        proc = subprocess.run(
            [sys.executable, "-c", _SUBPROC_SNIPPET],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["configured"], ["https://example.vercel.app"])
        self.assertEqual(payload["match"], "https://example.vercel.app")
        self.assertNotEqual(payload["other"], "https://other.example")


# --------------------------------------------------------------------------- #
# 4. Quote input-size contract
# --------------------------------------------------------------------------- #

class QuoteInputContractTests(unittest.TestCase):
    def setUp(self):
        self._ctx = demo_mode_app()
        self.appmod, self.openai_ctor = self._ctx.__enter__()
        self.client = TestClient(self.appmod.app)

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def test_normal_quote_is_accepted(self):
        r = self.client.post("/analyze", json={"quote_text": "Brake pads replacement. Misc shop supplies."})
        self.assertEqual(r.status_code, 200, msg=r.text)
        self.assertEqual(r.json()["metadata"]["model"], DEMO_MODEL)

    def test_quote_at_maximum_length_is_accepted(self):
        r = self.client.post("/analyze", json={"quote_text": "x" * MAX_QUOTE_TEXT_CHARS})
        self.assertEqual(r.status_code, 200, msg=r.text)

    def test_quote_over_maximum_is_rejected_before_analysis(self):
        r = self.client.post("/analyze", json={"quote_text": "x" * (MAX_QUOTE_TEXT_CHARS + 1)})
        self.assertEqual(r.status_code, 422)
        detail = r.json()["detail"]
        self.assertEqual(detail["code"], "invalid_request")
        self.assertFalse(detail["retryable"])
        self.assertRegex(detail["request_id"], r"^[0-9a-f-]{36}$")
        self.assertIn(str(f"{MAX_QUOTE_TEXT_CHARS:,}"), detail["message"])
        self.openai_ctor.assert_not_called()

    def test_empty_quote_is_rejected(self):
        r = self.client.post("/analyze", json={"quote_text": ""})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], "invalid_request")

    def test_whitespace_only_quote_still_reaches_analyzer(self):
        # Unchanged product contract: min_length=1 is satisfied, so it is analyzed.
        r = self.client.post("/analyze", json={"quote_text": "   \n  "})
        self.assertEqual(r.status_code, 200, msg=r.text)

    def test_malformed_json_body_is_product_safe(self):
        r = self.client.post(
            "/analyze",
            content="{not json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["code"], "invalid_request")


# --------------------------------------------------------------------------- #
# 5. Public Demo configuration: no OpenAI key required
# --------------------------------------------------------------------------- #

class PublicDemoConfigTests(unittest.TestCase):
    def setUp(self):
        self._ctx = demo_mode_app(openai_key=None)
        self.appmod, self.openai_ctor = self._ctx.__enter__()
        self.client = TestClient(self.appmod.app)

    def tearDown(self):
        self._ctx.__exit__(None, None, None)

    def test_health_works_without_openai_key(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_analyze_returns_demo_result_without_openai_key(self):
        r = self.client.post("/analyze", json={"quote_text": "Replace cabin air filter. Shop supplies."})
        self.assertEqual(r.status_code, 200, msg=r.text)
        self.assertEqual(r.json()["metadata"]["model"], DEMO_MODEL)

    def test_openai_client_is_never_constructed_in_demo_mode(self):
        self.client.post("/analyze", json={"quote_text": "Coolant flush and top-up."})
        self.openai_ctor.assert_not_called()


# --------------------------------------------------------------------------- #
# 6. Cross-language length-contract consistency (backend <-> frontend)
# --------------------------------------------------------------------------- #

class LengthContractConsistencyTests(unittest.TestCase):
    def test_frontend_mirror_matches_backend_authoritative_bound(self):
        source = APP_JSX.read_text(encoding="utf-8")
        m = re.search(r"const\s+MAX_QUOTE_CHARS\s*=\s*(\d+)\s*;", source)
        self.assertIsNotNone(m, "MAX_QUOTE_CHARS not found in frontend/src/App.jsx")
        self.assertEqual(
            int(m.group(1)),
            MAX_QUOTE_TEXT_CHARS,
            "frontend MAX_QUOTE_CHARS drifted from backend MAX_QUOTE_TEXT_CHARS",
        )

    def test_frontend_api_base_uses_vite_env_with_localhost_fallback(self):
        source = APP_JSX.read_text(encoding="utf-8")
        self.assertIn("import.meta.env.VITE_API_BASE_URL", source)
        self.assertIn('"http://localhost:8000"', source)


if __name__ == "__main__":
    unittest.main()
