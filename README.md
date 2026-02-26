# QuoteCheck v0 — Service Quote Review Assistant (OpenAI API + React)

QuoteCheck helps users understand messy vehicle service quotes by turning unstructured text into a **schema-valid JSON breakdown** with **risk flags (red/yellow/green)**, **confidence**, and **verification questions** to ask the service center.

> Disclaimer: **Not safety advice; verify with a certified mechanic.**

---

This repo is deliberately built like a deployable LLM product:
- **Schema-first contract** (Pydantic) → predictable UI + measurable reliability
- **Structured Outputs (OpenAI Responses API)** → JSON constrained by strict schema
- **Observability (JSONL run logs)** → traceability per request (request_id, latency, schema_valid, risk_counts)
- **Prompt/version discipline** → prompt changes are versioned “product changes”
- **Config + `.env`** → clean local dev, secrets never committed

---

## Demo (local)

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
pip install python-dotenv
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

Open the URL Vite prints (usually `http://localhost:5173`) → paste a quote → **Analyze**.

---

## Configuration (modes)

We use an untracked `.env` for local settings and secrets.

1. Copy example:

```bash
cp backend/.env.example backend/.env
```

2. Edit `backend/.env`:
Stub mode (default, zero cost)
* `QUOTECHECK_USE_OPENAI=0`

OpenAI mode (real model calls)
* `QUOTECHECK_USE_OPENAI=1` 
* `OPENAI_API_KEY=your_key_here` 
* `QUOTECHECK_MODEL=gpt-40-mini`

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
  - (v0) stub analyzer
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
- ✅ `/analyze` returns schema-valid response (stub mode)
- ✅ React UI renders results table + cards + raw JSON
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
