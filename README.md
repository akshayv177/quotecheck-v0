# QuoteCheck v0 — Service Quote Review Assistant (OpenAI API + React)

QuoteCheck helps users understand messy vehicle service quotes by turning unstructured text into a **schema-valid JSON breakdown** with **risk flags (red/yellow/green)**, **confidence**, and **verification questions** to ask the service center.

> Disclaimer: **Not safety advice; verify with a certified mechanic.**

> **No OpenAI API key needed to try this.** QuoteCheck defaults to a deterministic
> **Demo mode** (`QUOTECHECK_USE_OPENAI=0`) that returns a full, schema-valid
> quote-understanding report with zero cost and zero credentials. Real OpenAI calls
> are opt-in — see [Configuration (modes)](#configuration-modes) below.

---

This repo is deliberately built like a deployable LLM product:
- **Schema-first contract** (Pydantic) → predictable UI + measurable reliability
- **Structured Outputs (OpenAI Responses API)** → JSON constrained by strict schema
- **Observability (JSONL run logs)** → traceability per request (request_id, latency, schema_valid, risk_counts)
- **Prompt/version discipline** → prompt changes are versioned “product changes”
- **Config + `.env`** → clean local dev, secrets never committed

---

## Demo (local)

No `backend/.env` file and no OpenAI API key are required for these steps — if
`backend/.env` doesn't exist, the app falls back to its built-in defaults, which is
**Demo mode** (`QUOTECHECK_USE_OPENAI=0`).

### Prereqs
- Python 3.11 (conda recommended)
- Node 18+ / npm
- WSL2 Ubuntu 22 works great

### 1) Backend
From repo root:

```bash
conda create -n quotecheck python=3.11 -y
conda activate quotecheck
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
````

Sanity check:

```bash
curl http://localhost:8000/health
```

### 2) Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev -- --host
```

Open the URL Vite prints (usually `http://localhost:5173`) → the textarea is
pre-filled with a sample quote → click **Analyze quote** → see the full
quote-understanding report, with a **"Demo mode"** badge next to the run metadata
confirming no OpenAI call was made.

---

## Configuration (modes)

Local settings and secrets live in an untracked `backend/.env` file. You do **not**
need to create one to try Demo mode — it's the default. Create one only if you want
to switch to OpenAI mode:

1. Copy example:

```bash
cp backend/.env.example backend/.env
```

2. Edit `backend/.env`:

Demo mode — deterministic stub analyzer, default, zero cost, no key required
* `QUOTECHECK_USE_OPENAI=0`

OpenAI mode — real model calls, requires a key
* `QUOTECHECK_USE_OPENAI=1` 
* `OPENAI_API_KEY=your_key_here` 
* `QUOTECHECK_MODEL=gpt-4o-mini`

The frontend badge and the `metadata.model` field in every `/analyze` response
reflect whichever mode actually served the request (`quotecheck-demo-analyzer` in
Demo mode, the configured `QUOTECHECK_MODEL` in OpenAI mode) — so it's never
ambiguous which one produced a given report.

> `backend/.env` is gitignored. Never commit secrets.

---

## API

### `POST /analyze`

Request:

```json
{ "quote_text": "Brake pads replacement recommended. Tyre rotation." }
```

Response: **QuoteCheckResult** (schema-valid JSON):

* `line_items[]` with category, action, risk, confidence, short rationale
* `overall_summary[]`
* `verification_questions[]`
* `things_to_verify[]`
* `uncertainty_markers`
* `metadata` (request_id, prompt_version, model, latency_ms, schema_valid)

---

## Architecture (v0)

```
Browser (React)
  |
  |  POST /analyze  (JSON)
  v
FastAPI Backend
  - request_id, latency
  - schema contract (Pydantic)
  - (v0) stub analyzer (Demo mode, default) / OpenAI analyzer (opt-in)
  - JSONL run logging
  |
  v
logs/app_runs.jsonl  (append-only traces)
```

## Observability (JSONL)

Every `/analyze` call appends one JSON line to:

* `logs/app_runs.jsonl`

Example fields:

* `request_id`, `created_at`
* `prompt_version`, `model`
* `latency_ms`, `schema_valid`
* `num_items`, `risk_counts`
* `uncertainty`, `error`

Inspect latest entry:

```bash
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
```

---

## Prompting & Versioning

Prompt artifacts are centralized in:

* `backend/core/prompt.py`

`PROMPT_VERSION` is included in:

* API response metadata
* run logs

Schema export utility:

* `backend/core/schema_export.py`

---

## Repo structure (high level)

```
backend/
  app.py
  core/
    schema.py
    prompt.py
    schema_export.py
    run_logger.py
    config.py
    stub_analyzer.py
    openai_analyzer.py
  .env.example

frontend/
  src/App.jsx

logs/
  app_runs.jsonl

eval/   (coming next)
docs/   (coming next)
```

---

## Current status (v0)

- ✅ Backend + frontend run locally
- ✅ `/analyze` returns schema-valid response (Demo mode, no API key needed)
- ✅ React UI renders results table + cards + raw JSON, with a Demo/OpenAI mode badge
- ✅ JSONL run logging + prompt version discipline
- ✅ Config + dotenv workflow (secrets untracked)

---

## Limitations (v0)

* No authentication/users/DB
* No PDF/OCR ingestion (paste text only)
* Eval harness not wired yet
* Repair retry on schema failures is not added yet (planned)

---

## Roadmap

1. Add bounded repair retry (if model output fails Pydantic validation)
2. Eval harness: 10–20 quotes -> JSONL results + summary.md metrics
3. Cost controls: output token caps, shorter rationales, caching hooks, batch eval runs
4. Product wedge: expanded taxonomy + evidence requirements + HITL workflows

---

## License

MIT 
