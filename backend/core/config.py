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

# Observability
APP_RUN_LOG_PATH = os.environ.get("QUOTECHECK_LOG_PATH", "logs/app_runs.jsonl")

# OpenAI secret (required when USE_OPENAI=1)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Prompt version belongs with prompt artifacts, but we keep a fallback here
# only if we want config to print a complete runtime snapshot later.
# (We still treat backend/core/prompt.py as the source of truth.)