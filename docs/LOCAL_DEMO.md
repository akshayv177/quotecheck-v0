# Local Demo / Run Guide

Steps to run QuoteCheck locally and confirm it works end to end. All commands assume
you are in the repo root unless a step says otherwise.

## 1. Confirm a clean working tree

```bash
git status --short
```

## 2. Start the backend in Demo mode (no API key, no cost)

```bash
QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Leave this running in its own terminal.

## 3. Verify the backend is healthy

In a second terminal, from the repo root:

```bash
curl http://localhost:8000/health
```

Expect `{"status":"ok"}`.

## 4. Run `/analyze` against a sample quote

Still from the repo root (the command below reads a relative path and will fail
silently if run elsewhere):

```bash
curl -s -X POST http://localhost:8000/analyze -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json; print(json.dumps({"quote_text": open("examples/quote_ac_repair.txt").read()}))')"
```

The response's `metadata.model` should read `"quotecheck-demo-analyzer"`, confirming
no OpenAI call was made.

## 5. Start the frontend

In a third terminal:

```bash
cd frontend
npm run dev -- --host
```

Open the printed URL (usually `http://localhost:5173`).

## 6. Test the UI

- The textarea is pre-filled with a sample quote.
- Click **Analyze quote**.
- Confirm the report renders: line-item cards with explanations, risk badges, a
  "needs clarification" badge where applicable, vendor questions, and things to
  verify.
- Confirm the **"Demo mode"** badge appears next to the run metadata.

## 7. Optional: OpenAI mode

Only do this if you intend to make a real, billed API call:

1. `cp backend/.env.example backend/.env`
2. Edit `backend/.env`: set `QUOTECHECK_USE_OPENAI=1` and a real `OPENAI_API_KEY`.
3. Restart the backend.
4. Re-run step 4/6 above and confirm the badge now reads **"OpenAI mode"** and
   `metadata.model` matches `QUOTECHECK_MODEL` (default `gpt-4o-mini`).
5. Switch back to Demo mode (`QUOTECHECK_USE_OPENAI=0`) afterward to avoid further
   billed calls.

## 8. Screenshot capture location

No screenshot is committed to this repo yet (`docs/assets/` intentionally has no
image file — no placeholder or mocked-up image is used in its place). To add one:

1. Complete steps 2–6 above.
2. Capture the rendered report view in your browser.
3. Save the image at `docs/assets/quotecheck-demo-ui.png`.
4. README's Screenshot section can then embed it directly — see
   [`README.md`](../README.md#screenshot).

For a full summary of what's ready vs. still limited, see
[`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md).
