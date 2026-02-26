# QuoteCheck v0 — Service Quote Review Assistant (OpenAI API + React)

QuoteCheck helps users understand messy vehicle service quotes by turning unstructured text into a **schema-valid JSON breakdown** with **risk flags (red/yellow/green)**, **confidence**, and **verification questions** to ask the service center.

> Disclaimer: **Not safety advice; verify with a certified mechanic.**

---

This repo is deliberately built like a deployable LLM product:
- **Schema-first contract** (Pydantic) → predictable UI + measurable reliability
- **Observability** (JSONL run logs) → traceability per request
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

## Configuration

We use an untracked `.env` for local settings and secrets.

1. Copy example:

```bash
cp backend/.env.example backend/.env
```

2. Edit `backend/.env`:

* `QUOTECHECK_USE_OPENAI=0` (default; stub mode)
* `OPENAI_API_KEY=...` (only needed when you enable OpenAI)
* `QUOTECHECK_MODEL=...` (used when OpenAI is enabled)

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

Planned next step:

* OpenAI **Responses API** + **Structured Outputs (strict JSON schema)** + bounded repair retry

---

## Observability (JSONL)

Every `/analyze` call appends one line to:

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

## Repo structure

```
backend/
  app.py
  core/
    schema.py
    prompt.py
    schema_export.py
    run_logger.py
    config.py
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

- [x] Backend + frontend run locally
- [x] `/analyze` returns schema-valid response (stub mode)
- [x] React UI renders results table + cards + raw JSON
- [x] JSONL run logging + prompt version discipline
- [x] Config + dotenv workflow

---

## Limitations (v0)

* No authentication/users/DB
* No PDF/OCR ingestion (paste text only)
* Stub analyzer (OpenAI integration is next)
* Eval harness not wired yet

---

## Roadmap

1. OpenAI Responses API integration (structured outputs + strict schema)
2. Pydantic validation + **bounded repair retry** for schema failures
3. Eval harness: 10–20 quotes + JSONL results + summary metrics
4. Cost controls: token caps, caching hooks, batch eval discount
5. Product wedge: expanded taxonomy + evidence requirements + HITL workflow

---

## License

MIT 
````
