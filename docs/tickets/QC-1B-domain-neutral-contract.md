# QC-1B — Domain-neutral uncertainty contract + provenance cleanup

## 1. Goal

Make the structured contract domain-neutral and fix small provenance / dead-plumbing
inconsistencies identified during the QC-0 forensic audit, **before** the
eval/regression harness (QC-3) is built, so QC-3 targets the contract we intend to
keep.

Specifically:

- `UncertaintyMarkers.missing_vehicle_context` → `missing_quote_context`;
  `needs_mechanic_confirmation` → `needs_professional_confirmation`; with precise,
  domain-neutral semantics used consistently across schema, prompt, Demo logic, and
  examples.
- Demo mode populates the uncertainty markers deterministically instead of
  hardcoding vehicle-era values.
- Demo/OpenAI provenance stays explicit on both success and failure paths.
- Comments no longer imply an automatic OpenAI → Demo fallback.
- Dead prompt/schema plumbing removed if confirmed unused.
- The six committed Demo examples represent the current contract and application
  version.

Not a feature ticket. No new product capability, no eval infrastructure, no
deployment, no new dependencies, no taxonomy or UI redesign.

## 2. Context

QC-1A truthfully re-documented QuoteCheck as a general service / maintenance /
repair / parts / vendor quote-review assistant but deliberately left several
vehicle-era implementation leftovers in place and documented them honestly:

- `missing_vehicle_context` / `needs_mechanic_confirmation` are vehicle-specific
  field names in the machine contract, hardcoded `True` in the Demo stub
  (`stub_analyzer.py`) and in the `QuoteCheckResult` default factory.
- `backend/app.py`'s failure-logging path always logs `model = MODEL`
  (`gpt-4o-mini`) even in Demo mode, where OpenAI was never called.
- `stub_analyzer.py`'s module docstring calls the stub "a deterministic fallback if
  OpenAI is unavailable" — the app selects one analyzer by configuration; an OpenAI
  failure returns an error, it does not switch to the stub.
- `prompt.build_messages()` accepts a `schema_json` argument it never uses;
  `openai_analyzer.py` computes it via `schema_export.quotecheck_result_schema_json()`.
  The real Structured Outputs path is `quotecheck_result_schema_obj()` →
  `client.responses.create(... text.format.schema ...)`.
- The six committed `examples/*.json` were captured at `prompt_version
  quotecheck_v0.2` and still carry `v0 prototype` disclaimer/summary wording.

`NormalizedCategory` also carries vehicle-era residue but is **explicitly out of
scope** here — changing the taxonomy would expand scope and invalidate more
downstream assumptions than necessary. It stays a documented limitation.

### New uncertainty semantics

- **`missing_quote_context`** — `true` when the quote omits contextual information
  needed to interpret one or more recommendations confidently, such as scope,
  symptoms, quantities, diagnostic basis, or other material details. Not a synonym
  for "the quote contains a vague line item."
- **`needs_professional_confirmation`** — `true` when one or more technical or
  safety-sensitive recommendations should be confirmed by an appropriate qualified
  professional before relying on the analysis. Domain-neutral; no mechanic
  terminology hardcoded.

## 3. Strict file scope

Allowed to edit:

- `backend/core/schema.py`
- `backend/core/prompt.py`
- `backend/core/stub_analyzer.py`
- `backend/core/openai_analyzer.py` (dead schema plumbing)
- `backend/core/schema_export.py` (dead schema plumbing — scope expansion approved
  in review)
- `backend/app.py` (failure provenance)
- `docs/CURRENT_STATE.md`
- `README.md` (prompt-version string only)
- existing `examples/*.json` (regenerated, not hand-edited)
- `examples/README.md` (only if regenerated artifacts need a description change)

Allowed to create:

- `docs/tickets/QC-1B-domain-neutral-contract.md`
- `docs/review/REVIEW_BUNDLE__QC-1B-domain-neutral-contract.md`

Never touch: `frontend/` (unless it directly references a renamed field — it does
not), `backend/core/run_logger.py`, `backend/core/config.py`, dependency files,
`.env*`, deployment/CORS config, `NormalizedCategory`, and any historical
ticket/review document or historical `### Fixed in ...` block in
`docs/CURRENT_STATE.md`.

## 4. Out of scope

Eval harness, new eval cases, automated semantic graders, provider timeout policy,
rate-limit handling, retries, schema repair loops, input-size limits, public
deployment, CORS deployment config, `VITE_API_BASE_URL`, auth, DB/history, PDF/OCR,
RAG, price benchmarking, vendor verification, general taxonomy redesign, UI
redesign, CI. `ambiguous_items_present` behavior (still constant `true`) is left
unchanged — only the two obviously domain-specific fields change.

## 5. Acceptance criteria

1. `UncertaintyMarkers` exposes `missing_quote_context` and
   `needs_professional_confirmation` (with `Field` descriptions matching the
   semantics above); `missing_vehicle_context` / `needs_mechanic_confirmation` no
   longer appear in any active source, example, or frontend file. No back-compat
   aliases.
2. `backend/core/prompt.py` instructs the model to populate both new fields with
   domain-generic wording and no assumed trade; the existing prohibition on
   unsupported market-price / fairness judgments and all other prompt content are
   preserved.
3. A prompt-version decision is recorded. If bumped, the new version follows the
   existing `quotecheck_v0.N` scheme and every live reference is updated.
4. Demo mode computes both fields deterministically (transparent heuristics, no
   NLP). No AC/appliance, home/contractor, or generic-service quote receives
   vehicle/mechanic-specific uncertainty. A vehicle quote may still set
   `needs_professional_confirmation=true` where the existing deterministic logic
   identifies genuinely safety-sensitive work. `missing_quote_context` is `true`
   only on real evidence that material context is absent — never merely because a
   domain was not recognised.
5. Failure logging is mode-aware: Demo failure → `model = quotecheck-demo-analyzer`;
   OpenAI failure → `model = <configured QUOTECHECK_MODEL>`. No new dependency; a
   new provenance field only if justified (none added).
6. Misleading "fallback" wording near `stub_analyzer.py` is corrected; no automatic
   fallback is implemented.
7. Dead `schema_json` plumbing is removed after confirming it is unused; the
   Structured Outputs path (`quotecheck_result_schema_obj()` → `text.format.schema`)
   is unchanged.
8. Frontend references updated only if `frontend/src/App.jsx` directly uses a
   renamed field (it does not — no frontend change).
9. The six committed Demo examples are regenerated through the real Demo `/analyze`
   path (no OpenAI call, `QUOTECHECK_USE_OPENAI=0`); every output validates against
   `QuoteCheckResult`, reports `metadata.model = quotecheck-demo-analyzer` and the
   current `prompt_version`, uses the new field names, and contains no
   `v0 prototype` wording or vehicle/mechanic leakage in non-vehicle examples. JSON
   is not hand-edited.
10. `docs/CURRENT_STATE.md` gains a `### Fixed in QC-1B` block and an updated
    `Last updated` line; live Architecture/Gaps references are corrected; historical
    blocks are untouched. `README.md`'s prompt-version string is updated. No
    eval/reliability/deployment work is claimed.
11. `git diff --stat` shows only in-scope files. Nothing committed.

## 6. Commands to run

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt

# A. old contract names gone from active code/examples/frontend
git grep -nE 'missing_vehicle_context|needs_mechanic_confirmation' \
  -- ':!docs/tickets/**' ':!docs/review/**'

# B. new names consistent
git grep -nE 'missing_quote_context|needs_professional_confirmation'

# C. syntax + import
python -m compileall backend
python -c "from backend.app import app; print('import ok')"

# D. strict schema export (existing utility)
python -c "import json; from backend.core.schema_export import quotecheck_result_schema_obj as s; \
d=s(); um=d['\$defs']['UncertaintyMarkers']; print(um['additionalProperties'], um['required']); \
assert um['additionalProperties'] is False; \
assert set(um['required'])=={'ambiguous_items_present','missing_quote_context','needs_professional_confirmation'}; \
assert 'missing_vehicle_context' not in json.dumps(d) and 'needs_mechanic_confirmation' not in json.dumps(d); \
print('strict schema OK')"

# E. Demo-mode regeneration + smoke (backend on :8011, QUOTECHECK_USE_OPENAI=0)
#    replay each examples/*.txt input through POST /analyze, write examples/*.json
#    verify metadata.schema_valid, metadata.model, uncertainty_markers per case

# F. saved examples load + string scan
python -c "import json,glob; from backend.core.schema import QuoteCheckResult; \
fs=sorted(glob.glob('examples/**/*.json',recursive=True)); \
[QuoteCheckResult.model_validate(json.load(open(f))) for f in fs]; print(len(fs),'examples PASS')"
grep -RInE 'missing_vehicle_context|needs_mechanic_confirmation|v0 prototype' examples/ || true

# G. OpenAI path static verification (no API spend)
python -c "import inspect, backend.core.openai_analyzer as oa; \
src=inspect.getsource(oa); \
assert 'quotecheck_result_schema_json' not in src; \
assert 'schema_obj = quotecheck_result_schema_obj()' in src and '\"schema\": schema_obj' in src; \
print('schema_obj still passed via text.format.schema')"

# H. frontend — not changed by the diff (no lint/build required)

# I. scope
git status --short
git diff --stat
git diff --check
```

## 7. Definition of done

- All acceptance criteria met, with evidence (exact commands + real output, no
  placeholders) recorded in
  `docs/review/REVIEW_BUNDLE__QC-1B-domain-neutral-contract.md`.
- `docs/CURRENT_STATE.md` `Last updated` line reflects QC-1B; new `### Fixed in
  QC-1B` block present; historical blocks unmodified.
- No frontend, `run_logger.py`, `config.py`, dependency, or deployment changes.
- No historical ticket/review file modified.
- Nothing committed — left for the user to review and commit manually.
