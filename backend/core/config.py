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