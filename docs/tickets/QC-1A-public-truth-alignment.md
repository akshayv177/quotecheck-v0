# QC-1A — Public truth alignment

## 1. Goal

Make the public-facing documentation describe **only the current implemented
system**. Remove stale claims left over from earlier project phases (vehicle-only
framing, "v0 prototype" product disclaimer, "no screenshot committed", understated
OpenAI path) so the repo can withstand technical inspection.

Documentation-only. No application code, examples, logs, or deployment configuration
changes. No eval implementation. No schema cleanup.

## 2. Context

A forensic audit confirmed the core implementation is real and largely matches its
docs, but several public documents carried stale wording:

- README titled `QuoteCheck v0`, framed as primarily vehicle-service-flavored, and
  implying the current prompt itself is vehicle-specific.
- Stale `v0 prototype` disclaimer wording and `certified mechanic` presented as
  generic behaviour.
- `docs/CURRENT_STATE.md`, `docs/PROJECT_STATUS.md`, `docs/LOCAL_DEMO.md` still said
  no screenshot is committed — one was committed in `fae2b1e`
  (`docs/assets/quotecheck-ui.png`).
- Architecture wording understated the real OpenAI path (Responses API + Structured
  Outputs generated from the Pydantic contract).
- `SPEC.md` present positioning included "optional market price checks" as if it were
  an implemented capability.
- `CLAUDE.md` intro still carried "v0 prototype" and "optional market price checks".

Current-state truth (verified against code at HEAD):

- React/Vite frontend; FastAPI backend; `GET /health`, `POST /analyze`.
- One analyzer runs per process, selected by `QUOTECHECK_USE_OPENAI`. An OpenAI-path
  failure returns an error; it does **not** silently switch to Demo output.
- OpenAI mode: OpenAI Responses API, strict Structured Outputs (JSON Schema generated
  from the Pydantic `QuoteCheckResult` contract via `schema_export.py`), final
  Pydantic validation. Default model `gpt-4o-mini` (`QUOTECHECK_MODEL`).
- Prompt version `quotecheck_v0.3`; the OpenAI prompt is domain-generic (TASK-012).
- Demo mode: deterministic keyword heuristics, no key, no OpenAI cost,
  `metadata.model = "quotecheck-demo-analyzer"`; heuristics + `NormalizedCategory`
  taxonomy still carry vehicle-era wording.
- Request IDs, latency, schema-validity, model/analyzer metadata; append-only JSONL
  trace at `logs/app_runs.jsonl`.
- Six captured cross-domain Demo-mode example outputs; committed UI screenshot.
- No automated eval harness, no automated tests, no CI, no verified public
  deployment, no market-price benchmarking, no vendor verification.

## 3. Strict file scope

Allowed to edit:

- `README.md`
- `SPEC.md`
- `docs/CURRENT_STATE.md`
- `docs/PROJECT_STATUS.md`
- `docs/LOCAL_DEMO.md`
- `CLAUDE.md` — **factual current-state/product wording only** (stale prototype
  positioning, price-benchmarking capability wording, product scope). Do **not**
  change the coding workflow, agent instructions, build protocol, or implementation
  rules.

Allowed to create:

- `docs/tickets/QC-1A-public-truth-alignment.md`
- `docs/review/REVIEW_BUNDLE__QC-1A-public-truth-alignment.md`

Never touch: `backend/`, `frontend/`, `examples/`, `logs/`, `package.json`,
`package-lock.json`, dependency files, `.env` files, deployment configuration, and
any historical ticket/review document. The `### Fixed in TASK-NNN` / `### Fixed in
LUXURY-UI-*` blocks inside `docs/CURRENT_STATE.md` are historical and stay unchanged
except for adding the new `### Fixed in QC-1A` entry.

## 4. Out of scope

Do not fix (document honestly instead): `missing_vehicle_context` /
`needs_mechanic_confirmation` hardcoding, Demo uncertainty-marker hardcoding,
failure-log provenance bug, dead `schema_json` plumbing, stale `quotecheck_v0.2`
example-output regeneration, eval harness, automated tests, failure taxonomy, retry
handling, input-size limit, rate limiting, deployment URL/config, CORS deployment
config, `VITE_API_BASE_URL`.

No product redesign, no architecture redesign, no dependency changes, no commit.

## 5. Acceptance criteria

- README title is `QuoteCheck — Service Quote Review Assistant`; no `v0` product
  framing.
- README describes general service/repair/maintenance/parts/vendor quote review, not
  a vehicle-only product.
- README distinguishes the generic OpenAI analysis path from the narrower
  deterministic Demo heuristics.
- No current public doc claims the OpenAI prompt is vehicle-only, or presents
  `certified mechanic` as the generic disclaimer, or contains stale `v0 prototype`
  product-disclaimer wording (historical `### Fixed in …` changelog blocks excepted).
- OpenAI default `gpt-4o-mini` and prompt version `quotecheck_v0.3` are stated
  accurately wherever model/prompt-version details appear.
- OpenAI Responses API + Structured Outputs (generated from the Pydantic contract)
  described accurately; no multi-provider claim.
- Demo mode described as deterministic / zero-key / zero-OpenAI-cost / heuristic —
  not an automatic OpenAI-failure fallback.
- README explicitly states market-price benchmarking and objective price-fairness
  judgment are not implemented; no automated-eval claim; no live-deployment claim.
- `docs/assets/quotecheck-ui.png` acknowledged as committed; no doc says no
  screenshot exists (historical changelog blocks excepted).
- `SPEC.md`, `CURRENT_STATE.md`, `PROJECT_STATUS.md`, `LOCAL_DEMO.md`, `CLAUDE.md` do
  not contradict README on current scope/capabilities.
- `docs/CURRENT_STATE.md` has a new `### Fixed in QC-1A` entry and an updated
  `Last updated` line; no QC-1B/QC-3/QC-4 claims.
- No source-code files changed. No historical ticket/review documents rewritten.
- Not committed.

## 6. Commands to run

```bash
git status --short
git diff --stat

grep -RInE 'gpt-40-mini|v0 prototype|certified mechanic|no screenshot|screenshot is not committed|screenshot.*not committed' \
  README.md SPEC.md docs/CURRENT_STATE.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md CLAUDE.md || true
grep -RInE 'vehicle-service-flavored|vehicle-service-only|vehicle only|vehicle-only' \
  README.md SPEC.md docs/CURRENT_STATE.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md CLAUDE.md || true
grep -RInE 'production-ready|production grade|enterprise|fully evaluated|hallucination-safe|price benchmarking implemented|fair price' \
  README.md SPEC.md docs/CURRENT_STATE.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md CLAUDE.md || true
grep -RIn 'gpt-4o-mini'     README.md SPEC.md docs/CURRENT_STATE.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md CLAUDE.md || true
grep -RIn 'quotecheck_v0.3' README.md SPEC.md docs/CURRENT_STATE.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md CLAUDE.md || true

test -f docs/assets/quotecheck-ui.png
test -f docs/tickets/QC-1A-public-truth-alignment.md

git diff -- README.md SPEC.md docs/CURRENT_STATE.md docs/PROJECT_STATUS.md docs/LOCAL_DEMO.md CLAUDE.md
```

Interpret grep output manually — not every match is wrong (historical changelog
blocks, and limitations that truthfully mention vehicle-era taxonomy residue, are
legitimate).

## 7. Definition of done

- All acceptance criteria met, with evidence recorded in
  `docs/review/REVIEW_BUNDLE__QC-1A-public-truth-alignment.md` (exact commands + real
  output, no placeholders).
- `docs/CURRENT_STATE.md` `Last updated` line reflects QC-1A.
- No source code, examples, logs, dependency, or deployment changes.
- No historical ticket/review file modified.
- Nothing committed — left for the user to review and commit manually.
