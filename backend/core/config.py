"""
Config (v0)

Centralized runtime settings for QuoteCheck.

Principles
----------
- Code reads configuration from environment variables.
- Secrets (OPENAI_API_KEY) is never committed to git.
- Local development can use an untracked backend/.env file.

This module is intentionally small in v0. As the app grows, we can add:
- timeouts / retry policy
- cost ceilings (max_output_tokens)
- structured logging toggles
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

# Feature flags
USE_OPENAI = os.environ.get("QUOTECHECK_USE_OPENAI", "0") == "1"

# Model selection (used once we integrate OpenAI)
MODEL = os.environ.get("QUOTECHECK_MODEL", "gpt-4o-mini")

# Label reported in MetaData.model when running the deterministic stub/demo
# analyzer (QUOTECHECK_USE_OPENAI=0, the default). Deliberately distinct from
# MODEL/QUOTECHECK_MODEL so stub-mode responses and logs never claim an OpenAI
# model was called when it wasn't.
DEMO_ANALYZER_MODEL = "quotecheck-demo-analyzer"

# Observability
APP_RUN_LOG_PATH = os.environ.get("QUOTECHECK_LOG_PATH", "logs/app_runs.jsonl")

# --- Deployment: allowed browser origins (CORS) ----------------------------- #
# QUOTECHECK_ALLOWED_ORIGINS is a comma-separated list of EXACT browser origins
# (scheme + host + optional port, nothing else), e.g.
#   QUOTECHECK_ALLOWED_ORIGINS=https://quotecheck.vercel.app
# Unset -> the local Vite dev server on both hostnames. A public backend must
# accept browser requests only from explicitly named origins, so wildcard "*",
# a path/query/fragment, a missing scheme or host, and an explicitly-set but
# empty value are all rejected at import time (fail fast, not a silent misconfig).
_ALLOWED_ORIGINS_DEFAULT = "http://localhost:5173,http://127.0.0.1:5173"


def _normalize_origin(raw: str) -> str:
    """Return the canonical ``scheme://host[:port]`` form of ``raw`` or raise.

    Accepts only a true browser Origin: an http/https scheme, a host, an empty or
    single-"/" path, and no query or fragment. A lone root "/" is normalized away
    so ``https://x.app/`` and ``https://x.app`` are treated as the same origin.
    """
    value = raw.strip()
    if value == "*":
        raise RuntimeError(
            "QUOTECHECK_ALLOWED_ORIGINS must list exact origins; '*' is not allowed "
            "for a public deployment."
        )
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        raise RuntimeError(
            f"QUOTECHECK_ALLOWED_ORIGINS entry {raw!r} needs an http:// or https:// scheme."
        )
    if not parts.hostname:
        raise RuntimeError(f"QUOTECHECK_ALLOWED_ORIGINS entry {raw!r} has no host.")
    if parts.path not in ("", "/"):
        raise RuntimeError(
            f"QUOTECHECK_ALLOWED_ORIGINS entry {raw!r} must be a bare origin (no path)."
        )
    if parts.query or parts.fragment:
        raise RuntimeError(
            f"QUOTECHECK_ALLOWED_ORIGINS entry {raw!r} must have no query or fragment."
        )
    # netloc preserves an explicit port and drops the normalized root slash.
    return f"{parts.scheme}://{parts.netloc}"


def _parse_allowed_origins(raw: str, *, explicitly_set: bool) -> list[str]:
    origins: list[str] = []
    for chunk in raw.split(","):
        if not chunk.strip():
            continue  # drop empty / whitespace-only entries
        origin = _normalize_origin(chunk)
        if origin not in origins:  # dedupe, preserve first-seen order
            origins.append(origin)
    if not origins and explicitly_set:
        raise RuntimeError(
            "QUOTECHECK_ALLOWED_ORIGINS is set but contains no usable origin."
        )
    return origins


_ALLOWED_ORIGINS_RAW = os.environ.get("QUOTECHECK_ALLOWED_ORIGINS")
ALLOWED_ORIGINS = _parse_allowed_origins(
    _ALLOWED_ORIGINS_RAW if _ALLOWED_ORIGINS_RAW is not None else _ALLOWED_ORIGINS_DEFAULT,
    explicitly_set=_ALLOWED_ORIGINS_RAW is not None,
)

# OpenAI secret (required when USE_OPENAI=1)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# --- OpenAI reliability (QC-4) ----------------------------------------------- #
# Per-attempt request timeout for the OpenAI Responses API call. This is the
# only operator-tunable reliability setting. The raw string is validated lazily
# (backend.core.openai_analyzer.resolve_openai_timeout_seconds); a malformed
# value is surfaced as a configuration_error, not a later opaque httpx failure.
OPENAI_TIMEOUT_DEFAULT_SECONDS = 30.0
OPENAI_TIMEOUT_SECONDS_RAW = os.environ.get("QUOTECHECK_OPENAI_TIMEOUT_SECONDS")

# QuoteCheck owns the single automatic retry: the OpenAI SDK client is built
# with max_retries=0 and a small bounded loop in the analyzer retries once for
# clearly transient provider/transport failures only. This is a fixed code
# constant, deliberately NOT environment-overridable — retry count affects cost
# and request amplification.
OPENAI_MAX_RETRIES = 1
# Maximum provider calls for a single /analyze request: 1 initial + the retries.
OPENAI_MAX_ATTEMPTS = 1 + OPENAI_MAX_RETRIES

# Prompt version belongs with prompt artifacts, but we keep a fallback here
# only if we want config to print a complete runtime snapshot later.
# (We still treat backend/core/prompt.py as the source of truth.)