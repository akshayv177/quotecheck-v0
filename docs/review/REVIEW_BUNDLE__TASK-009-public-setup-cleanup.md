# REVIEW_BUNDLE — TASK-009 — Public setup cleanup

## Files changed

- `docs/tickets/TASK-009-public-setup-cleanup.md` (new)
- `README.md` (edited)
- `docs/CURRENT_STATE.md` (edited)
- `docs/review/REVIEW_BUNDLE__TASK-009-public-setup-cleanup.md` (this file, new)

Not touched: `backend/.env.example` — inspected, found accurate and safe already
(placeholder key text, explicit "Demo mode needs no key/`.env`" comment,
`QUOTECHECK_USE_OPENAI=0` default), and validation found no mismatch, so per the user's
amendment it was left unchanged. No Makefile/`scripts/`/`docs/SETUP.md`/
`frontend/README.md` added (see "Makefile/scripts/SETUP.md decision" below). No files
under `frontend/src/`, `backend/core/`, `examples/outputs/`, `backend/.env`, `logs/`, or
`package-lock.json` touched. No commits made.

```
$ git status --short
 M README.md
 M docs/CURRENT_STATE.md
?? docs/tickets/TASK-009-public-setup-cleanup.md

$ git diff --stat
 README.md             | 39 +++++++++++++++++++++++++++++----------
 docs/CURRENT_STATE.md | 51 ++++++++++++++++++++++++++++++++++++++++++++++-----
 2 files changed, 75 insertions(+), 15 deletions(-)
```

## Validation-target note (read this first)

The ticket's own suggested commands include a `git clone` of the public GitHub URL
(`https://github.com/akshayv177/quotecheck-v0`). This ticket's doc edits are uncommitted
and "no commits" is out of scope, so cloning the public remote would only have exercised
the **pre-TASK-009** README/`.env.example`/`CURRENT_STATE.md` — not the files actually
being changed here. This was confirmed with the user before implementation (see plan).

Instead, validation used an `rsync` copy of the current working tree (including the
uncommitted TASK-009 edits) into `/tmp/quotecheck-v0-setup-test`, a temporary directory
outside the repo, excluding `.git`, `node_modules`, `.venv`, `logs`, `backend/.env`,
`__pycache__`, `.pytest_cache`, `frontend/dist`. This is a genuine deviation from a literal
`git clone` and is called out explicitly rather than glossed over.

**Follow-up (not done in this ticket):** after this branch is merged and pushed to the
public remote, do one real `git clone https://github.com/akshayv177/quotecheck-v0` +
backend/frontend smoke test to confirm the public repo matches what was validated here.

## Acceptance criteria — evidence

- **README setup instructions match the actual repo.** ✅ Verified by running every
  README-documented command from a clean working-tree copy (see "Commands run" below);
  all succeeded with real output matching what the README now describes (venv-first
  quickstart, `QUOTECHECK_USE_OPENAI=0` explicit, `/health`, `/analyze`, frontend
  install/build).
- **README clearly says Demo mode needs no API key.** ✅ Unchanged pre-existing section
  "Try it in under a minute (no API key needed)" (README.md:25) plus the new explicit
  `QUOTECHECK_USE_OPENAI=0` prefix on the run command (README.md:53) and inline note
  that it's "already the default even without setting it explicitly."
- **README clearly explains OpenAI mode is optional and requires `backend/.env` with
  `OPENAI_API_KEY`.** ✅ Unchanged pre-existing "Demo mode vs. OpenAI mode" section
  (README.md, `## Demo mode vs. OpenAI mode`) — not touched by this ticket, already met
  this criterion.
- **`backend/.env.example` is accurate and safe.** ✅ Inspected, no mismatch found, left
  unchanged per user's amendment (see "Files changed" above).
- **A clean checkout setup path is verified in a temporary directory outside the working
  repo.** ✅ `/tmp/quotecheck-v0-setup-test`, via `rsync` copy (see note above and
  "Commands run" below).
- **Backend install succeeds in a fresh venv using `backend/requirements.txt`.** ✅ See
  pip install output below; installed versions match pins exactly
  (fastapi 0.128.6, uvicorn 0.40.0, pydantic 2.12.5, openai 2.24.0, python-dotenv 1.2.1).
- **Backend imports successfully.** ✅ `from backend.app import app` → `QuoteCheck API`.
- **Backend runs in Demo mode with `QUOTECHECK_USE_OPENAI=0`.** ✅ Server started with
  that env var; `/analyze` response `metadata.model == "quotecheck-demo-analyzer"`
  confirms no OpenAI call was made.
- **`/health` works.** ✅ `{"status":"ok"}`.
- **`/analyze` works against at least one sample quote in Demo mode.** ✅ Ran against
  `examples/quote_ac_repair.txt`; full schema-valid JSON response captured below.
- **Frontend dependencies install and frontend build passes.** ✅ `npm install` (157
  packages) and `npm run build` (vite build, 3 output files) both succeeded.
- **Any setup limitation is documented honestly.** ✅ Pre-existing Limitations section
  (no `environment.yml`/lockfile, reproducibility depends on activating a compatible
  Python 3.10+ environment) updated to say "`venv` or conda steps above" instead of only
  "conda steps above", matching the new venv-primary quickstart.
- **`docs/CURRENT_STATE.md` is updated.** ✅ "Last updated" line now reads TASK-009; new
  "Fixed in TASK-009" section added; Commands section updated to show the venv-primary
  path with explicit `QUOTECHECK_USE_OPENAI=0`.
- **No secrets are committed.** ✅ Grep scan below found nothing; no commits were made at
  all (per out-of-scope).
- **Review bundle records exact commands and exact outputs.** ✅ This file, below.

## Commands run (exact, real output)

### 1. Repo state before changes

```
$ git status --short
 M README.md
?? docs/tickets/TASK-009-public-setup-cleanup.md

$ git log --oneline -5
a30f5fa Merge branch 'task/TASK-008A-personalize-demo-guidance'
ba560c3 fix: personalize TASK-008 demo guidance
c4b1545 Merge branch 'task/TASK-008-sample-cases-evals'
fe778ed feat: add TASK-008 sample cases and demo outputs
53d9d64 docs: package QuoteCheck for public portfolio review
```

### 2. Clean-room copy (outside the repo)

```
$ rm -rf /tmp/quotecheck-v0-setup-test
$ mkdir -p /tmp/quotecheck-v0-setup-test
$ rsync -a \
    --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='.venv-test' \
    --exclude='logs' --exclude='backend/.env' --exclude='__pycache__' \
    --exclude='.pytest_cache' --exclude='frontend/dist' \
    ./ /tmp/quotecheck-v0-setup-test/

$ ls -la /tmp/quotecheck-v0-setup-test
total 60
drwxr-xr-x  7 akshay akshay  4096 Jul  8 22:28 .
drwxrwxrwt 12 root   root   12288 Jul  8 22:28 ..
-rw-r--r--  1 akshay akshay   142 Feb 26 12:55 .gitignore
-rw-r--r--  1 akshay akshay  2565 Jul  8 13:21 CLAUDE.md
-rw-r--r--  1 akshay akshay 11248 Jul  8 22:28 README.md
-rw-r--r--  1 akshay akshay  3644 Jul  8 13:21 SPEC.md
drwxr-xr-x  3 akshay akshay  4096 Jul  8 16:12 backend
drwxr-xr-x  4 akshay akshay  4096 Jul  8 22:16 docs
drwxr-xr-x  2 akshay akshay  4096 Feb 10 14:54 eval
drwxr-xr-x  3 akshay akshay  4096 Jul  8 22:16 examples
drwxr-xr-x  4 akshay akshay  4096 Jul  8 15:29 frontend
```

No `.git`, `.venv`, `node_modules`, `logs`, or `backend/.env` present — confirms the
exclude list worked and this is a fresh copy, not the live working tree.

### 3. Backend install + import (fresh venv)

```
$ cd /tmp/quotecheck-v0-setup-test
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip install -q -r backend/requirements.txt
(exit code 0, no errors)

$ pip list | grep -iE "fastapi|uvicorn|pydantic|openai|dotenv"
fastapi           0.128.6
openai            2.24.0
pydantic          2.12.5
pydantic_core     2.41.5
python-dotenv     1.2.1
uvicorn           0.40.0
```

All versions match `backend/requirements.txt` pins exactly
(`fastapi==0.128.6`, `uvicorn==0.40.0`, `pydantic==2.12.5`, `openai==2.24.0`,
`python-dotenv==1.2.1`).

```
$ python -c "from backend.app import app; print(app.title)"
QuoteCheck API
```

### 4. Backend run in Demo mode, `/health`, `/analyze`

```
$ QUOTECHECK_USE_OPENAI=0 uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
$ sleep 2
$ curl -s http://127.0.0.1:8000/health
{"status":"ok"}

$ curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
    -d "$(python3 -c 'import json; print(json.dumps({"quote_text": open("examples/quote_ac_repair.txt").read()}))')"
```

Response (pretty-printed, `metadata.model` and `disclaimer` confirm Demo mode, no
OpenAI call made):

```json
{
    "line_items": [
        {
            "name_raw": "AC/appliance repair (from quote)",
            "normalized_category": "wear_and_tear",
            "explanation": "An AC compressor or refrigerant charge is part of an appliance's cooling system. A technician typically recommends this when cooling output drops, the system is losing refrigerant, or a diagnostic points to a failing component.",
            "vague_or_confusing": false,
            "recommended_action": "ask_for_evidence",
            "risk_level": "yellow",
            "confidence": 0.55,
            "rationale_short": "Appliance/HVAC repair scope varies widely; ask for a diagnostic report before approving.",
            "price": null,
            "evidence_needed": [
                "Diagnostic report or fault code",
                "Unit model/serial number and warranty status",
                "Refrigerant type and quantity used (if applicable)"
            ]
        }
    ],
    "overall_summary": [
        "This report explains each line item in plain language, flags risk level, and lists questions to ask the vendor before approving.",
        "Any generically named, bundled, or unclear charges are marked as needing clarification; ask the vendor for an itemized breakdown.",
        "Price benchmarking is not implemented in this v0 prototype; no market price comparison is being made."
    ],
    "verification_questions": [
        "What diagnostic fault code or symptom led to the compressor/refrigerant recommendation?",
        "Is the unit still under manufacturer or extended warranty?",
        "What refrigerant type and quantity does the job require, and is that reflected in the price?"
    ],
    "things_to_verify": [
        "Get the unit's model/serial number and confirm its warranty status before approving.",
        "Confirm a refrigerant leak was actually located, not just assumed from low pressure.",
        "Ask whether a full system replacement was considered instead of a compressor repair, and why."
    ],
    "uncertainty_markers": {
        "ambiguous_items_present": true,
        "missing_vehicle_context": true,
        "needs_mechanic_confirmation": true
    },
    "refusals": [],
    "disclaimer": "QuoteCheck is a v0 prototype; results may be incomplete or wrong. Not safety advice; verify with a certified technician. QuoteCheck explains quotes and suggests questions; it does not verify vendor claims, guarantee fair pricing, or perform price benchmarking.",
    "metadata": {
        "prompt_version": "quotecheck_v0.2",
        "model": "quotecheck-demo-analyzer",
        "created_at": "2026-07-08T16:58:51.792494Z",
        "request_id": "5b051f1a-1e03-4e4f-995d-c810f7ba6863",
        "latency_ms": 0,
        "schema_valid": true
    }
}
```

```
$ pkill -f "uvicorn backend.app:app --host 127.0.0.1 --port 8000"
$ ps aux | grep uvicorn | grep -v grep
no uvicorn process running - confirmed stopped
```

### 5. Frontend install + build

```
$ cd /tmp/quotecheck-v0-setup-test/frontend
$ npm install
added 157 packages, and audited 158 packages in 5s
33 packages are looking for funding
11 vulnerabilities (2 low, 4 moderate, 5 high)
```

(Standard `npm audit` advisory noise from upstream transitive deps, not a new issue
introduced by this ticket — fixing it would require touching `package-lock.json`, which
is out of scope / requires stopping to ask per the ticket's file scope.)

```
$ npm run build
> frontend@0.0.0 build
> vite build

vite v7.3.1 building client environment for production...
transforming...
✓ 29 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.50 kB │ gzip:  0.33 kB
dist/assets/index-BLc0mHcd.css    1.99 kB │ gzip:  0.93 kB
dist/assets/index-BMhYUSbn.js   204.19 kB │ gzip: 64.19 kB
✓ built in 1.44s
```

### 6. Secrets scan

```
$ cd /tmp/quotecheck-v0-setup-test
$ grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' \
    README.md backend/.env.example docs/CURRENT_STATE.md docs/tickets/TASK-009-public-setup-cleanup.md
(no output, exit code 1 — no matches)
```

### 7. Cleanup

```
$ rm -rf /tmp/quotecheck-v0-setup-test
cleaned up
```

## Makefile/scripts/SETUP.md decision

Not added. The full setup path (clone → venv → install → run → verify → frontend
install/build) is covered by README.md in well under 15 commands once the fixes above
landed, and every command in that path was independently verified above. Adding a
Makefile, `scripts/verify_setup.sh`, or `docs/SETUP.md` would be new maintenance surface
for marginal benefit at this repo's size, and risks scope creep beyond a docs-cleanup
ticket. Not ruled out permanently — just not justified by what this ticket's inspection
and validation found.

## Out-of-scope observations (not acted on)

- `npm install` reports 11 pre-existing vulnerabilities (2 low, 4 moderate, 5 high) in
  transitive frontend dependencies. Pre-existing, unrelated to this ticket's changes, and
  fixing it would touch `package-lock.json` — out of this ticket's file scope.

## Definition of done — check

- [x] Ticket file created (`docs/tickets/TASK-009-public-setup-cleanup.md`).
- [x] Plan approved by user before any doc edits.
- [x] Implementation stayed within approved file scope
      (`README.md`, `docs/CURRENT_STATE.md`, ticket file, this review bundle;
      `backend/.env.example` correctly left untouched — no mismatch found).
- [x] All acceptance criteria have concrete evidence above, no placeholders.
- [x] `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-009.
- [x] No secrets committed; no commits made at all — work is on
      `task/TASK-009-public-setup-cleanup`, left for the user to review and commit
      manually.
