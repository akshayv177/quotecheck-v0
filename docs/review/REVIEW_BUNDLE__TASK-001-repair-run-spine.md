# REVIEW BUNDLE — TASK-001 — Repair local run spine

Ticket: `docs/tickets/TASK-001-repair-run-spine.md`

## Files changed

- `backend/requirements.txt` (new) — pinned backend deps.
- `README.md` — model typo fix, deduped install step.
- `backend/core/schema.py` — fixed misspelled kwarg in `uncertainty_markers` default_factory.
- `backend/core/prompt.py` — fixed literal escape text in `build_messages` user content.
- `docs/CURRENT_STATE.md` — updated commands, gaps, and "Fixed in TASK-001" note.
- `docs/tickets/TASK-001-repair-run-spine.md` — ticket file (created in a prior turn).

No other files were touched. `frontend/`, `backend/core/stub_analyzer.py`,
`backend/core/openai_analyzer.py`, `package-lock.json`, `backend/.env`, and `logs/`
were not modified.

## Note on an out-of-band commit

`git log` shows a commit `8744956 "docs: add TASK-001 ticket"` already present at
HEAD before implementation began, containing only the ticket file. This commit was
not made by any `git commit` invocation in this session — it appears to have been
created by an automated hook triggered on file write. Flagging it here since I was
explicitly instructed not to commit. All other changes in this bundle remain
**uncommitted** in the working tree; I did not run `git commit` at any point.

## Acceptance criteria — evidence

### 1. `backend/requirements.txt` exists and contains only currently required deps

```
fastapi==0.128.6
uvicorn==0.40.0
pydantic==2.12.5
openai==2.24.0
python-dotenv==1.2.1
```
Versions pinned from the working `quotecheck` conda env (Python 3.11.14), and then
independently verified installable on a clean Python 3.10 venv (see §6 below).

### 2. README backend install instructions match the repo

`README.md` "1) Backend" section now reads:
```bash
conda create -n quotecheck python=3.11 -y
conda activate quotecheck
pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```
The redundant `pip install python-dotenv` line was removed since `python-dotenv` is
now in `requirements.txt`.

### 3. README model typo fixed

`README.md` config example: `QUOTECHECK_MODEL=gpt-40-mini` → `QUOTECHECK_MODEL=gpt-4o-mini`
(matches the code default in `backend/core/config.py:26`).

### 4. Schema typo fixed

`backend/core/schema.py:158`: `ambigious_items_present=True` → `ambiguous_items_present=True`,
matching the `UncertaintyMarkers.ambiguous_items_present` field (`schema.py:107`).

### 5. Prompt newline issue fixed

`backend/core/prompt.py`, `build_messages`:
- Before: `"Here is a service quote. Analyze it and return the structured JSON result. \\n\\n"` /
  `f"QUOTE: \\N{quote_text}\\n\\n"` (literal backslash-n text, stray literal `\N`).
- After: real newlines, no stray escape:
```python
user_content = (
    "Here is a service quote. Analyze it and return the structured JSON result.\n\n"
    f"QUOTE: {quote_text}\n\n"
)
```

### 6. Backend imports/runs cleanly from a clean environment

Exact commands and real output:

```
$ git status --short
 M README.md
 M backend/core/prompt.py
 M backend/core/schema.py
?? backend/requirements.txt
```
(captured before the `docs/CURRENT_STATE.md` edit in this same session)

```
$ python3 -m venv .venv-test
$ source .venv-test/bin/activate
$ python --version
Python 3.10.12

$ pip install -r backend/requirements.txt
...
Successfully installed annotated-doc-0.0.4 annotated-types-0.7.0 anyio-4.14.1 certifi-2026.6.17
click-8.4.2 distro-1.9.0 exceptiongroup-1.3.1 fastapi-0.128.6 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1
idna-3.18 jiter-0.16.0 openai-2.24.0 pydantic-2.12.5 pydantic-core-2.41.5 python-dotenv-1.2.1
sniffio-1.3.1 starlette-0.52.1 tqdm-4.68.4 typing-extensions-4.16.0 typing-inspection-0.4.2 uvicorn-0.40.0
```

```
$ python -c "from backend.app import app; print(app.title)"
QuoteCheck API
```

Clean install + import succeeded on system Python 3.10 (one minor version below the
README's recommended 3.11) with no errors.

### 7. `/health` works

```
$ QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
INFO:     Started server process [21739]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

$ curl -s http://127.0.0.1:8000/health
{"status":"ok"}
```

### 8. `/analyze` works in stub mode with a sample quote

**Important finding during validation:** `backend/.env` (untracked, local to this
machine) has `QUOTECHECK_USE_OPENAI=1`. The first `/analyze` call was run without
overriding this, and it made a real OpenAI API call (15.6s latency, `gpt-4o-mini`
output) instead of exercising the stub — an unintended live API call/cost. This was
caught immediately, the server was stopped, and the check was re-run with an
explicit environment override (`QUOTECHECK_USE_OPENAI=0`) so `load_dotenv`'s
non-override default behavior would not re-enable OpenAI mode. No `backend/.env`
file was edited.

```
$ curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pad replacement ₹8,500. Labour ₹2,500. Misc charges ₹1,200. AC gas top-up ₹3,000."}'
```
Response (stub mode, `latency_ms: 0`, deterministic):
```json
{
    "line_items": [
        {
            "name_raw": "Brake service/ pads (from quote)",
            "normalized_category": "safety_critical",
            "recommended_action": "needs_inspection",
            "risk_level": "red",
            "confidence": 0.7,
            "rationale_short": "Braking components are safety-critical. Ask for pad thickness and rotor condition evidence.",
            "price": null,
            "evidence_needed": [
                "Pad thickness measurement (mm)",
                "Rotor condition photo",
                "Reason for replacement"
            ]
        }
    ],
    "overall_summary": [
        "This is a v0 stub response to validate the end-to-end contract.",
        "Safety-critical items (like brakes/tyres) should be verified with evidence before approval.",
        "Ask for measurements, photos, and the specific failure reason for any recommendation."
    ],
    "verification_questions": [
        "Can you share photos/measurements that justify each recommended item?",
        "Which items are safety-critical vs optional preventive maintenance?",
        "Confirm whether the recommendation is OEM-specified or shop-suggested."
    ],
    "things_to_verify": [
        "Request an itemized parts + labour breakdown for each line item.",
        "Ask for measurements (pad thickness, tread depth) where applicable.",
        "Confirm whether the recommendation is OEM-specified or shop-suggested."
    ],
    "uncertainty_markers": {
        "ambiguous_items_present": true,
        "missing_vehicle_context": true,
        "needs_mechanic_confirmation": true
    },
    "refusals": [],
    "disclaimer": "Not safety advice; verify with a certified mechanic.",
    "metadata": {
        "prompt_version": "quotecheck_v0.1",
        "model": "gpt-4o-mini",
        "created_at": "2026-07-08T08:41:51.402855Z",
        "request_id": "caa2a3f1-c21e-4aa2-aa16-dbcf53b512f9",
        "latency_ms": 0,
        "schema_valid": true
    }
}
```
Note: the stub analyzer only pattern-matches on brake/tyre-flavored keywords (per
`docs/CURRENT_STATE.md`), so "Labour", "Misc charges", and "AC gas top-up" were not
extracted as separate line items in stub mode — this is existing, documented stub
behavior, not a regression from this ticket's fixes.

Server was stopped after the check (`kill` on the uvicorn process).

### 9. `docs/CURRENT_STATE.md` updated

- "Last updated" line changed to `2026-07-08 (TASK-001)`.
- Commands section now references `pip install -r backend/requirements.txt`.
- Gaps section: removed the resolved `backend/requirements.txt` gap and the "Observed
  issues to verify/fix in future tickets" subsection; replaced with a "Fixed in
  TASK-001" note listing the four repairs.

### 10. Secret scan

```
$ grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'\''][^"'\'']{10,}' \
  backend/requirements.txt README.md backend/core/schema.py backend/core/prompt.py docs/CURRENT_STATE.md
(no output, exit code 1 — no matches)
```

### 11. No frontend behavior changes

No files under `frontend/` were read or modified during this ticket.

## Cleanup

`.venv-test` (throwaway validation venv) was removed after validation; it was never
part of the repo and is not present in `git status`.

## Commit status

Not committed by me. `git status --short` after implementation:
```
 M README.md
 M backend/core/prompt.py
 M backend/core/schema.py
 M docs/CURRENT_STATE.md
?? backend/requirements.txt
```
(The ticket file itself is already committed via the out-of-band commit noted above,
before this implementation began.)
