# Review Bundle — QC-1A — Public truth alignment

## 1. Ticket ID / phase

- Ticket: `docs/tickets/QC-1A-public-truth-alignment.md`
- Phase: hardening / documentation truth-alignment (pre-inspection)
- Type: **documentation only** — no application code, examples, logs, dependency, or
  deployment changes.

## 2. Scope summary

Bring the public-facing docs into line with the current implemented system at HEAD:

- Reframe the product from "QuoteCheck v0 / vehicle-service-flavored" to a general
  service/maintenance/repair/parts/vendor quote review assistant.
- Distinguish the domain-generic OpenAI analysis path from the narrower deterministic
  Demo heuristics / `NormalizedCategory` taxonomy.
- Describe the real OpenAI path (Responses API + Structured Outputs generated from
  the Pydantic contract, default `gpt-4o-mini`, prompt `quotecheck_v0.3`).
- State product boundaries: no market-price benchmarking, no price-fairness judgment,
  no vendor verification/trust scoring, no automated eval harness, no verified public
  deployment.
- Acknowledge the committed UI screenshot (`docs/assets/quotecheck-ui.png`).
- Remove stale `v0 prototype` product-disclaimer wording and `certified mechanic`
  as-generic-behaviour wording from current-state prose.
- Correct `CLAUDE.md` intro product wording only (workflow/agent rules untouched).

Post-review wording corrections applied on 2026-08-28:
- `README.md` Demo-mode subsection: dropped the environment-dependent "in under a
  minute" claim; now "a real, schema-valid response without an API key or model call".
- `docs/CURRENT_STATE.md` Gaps: the "still narrower than the SPEC.md target" bullet was
  reworded to pin the limitation to the deterministic Demo analyzer and the shared
  `NormalizedCategory` taxonomy (the OpenAI path is domain-generic).

## 3. Files changed

| File | Change |
|---|---|
| `README.md` | Title → `QuoteCheck — Service Quote Review Assistant`; positioning rewritten; "vehicle-service-flavored" scope paragraph replaced with the generic-prompt / narrow-Demo split; new "What QuoteCheck does not do" boundary list; Architecture rewritten (config-selected single analyzer, no silent Demo fallback); new "OpenAI mode", "Demo mode", "Evaluation" subsections; Limitations tightened; `metadata` list adds `created_at`; "in this v0" → "in this early implementation"; `eval/ (coming next)` removed from repo tree; `assets/` line notes the committed screenshot. |
| `SPEC.md` | Removed "optional market price checks" from present positioning; positioning broadened; "Current v0 scope" → "Current scope", prompt/framing described as domain-generic vs. narrower Demo heuristics/taxonomy; OpenAI mode described (Responses API + Structured Outputs + Pydantic re-validation); non-goals expanded (price fairness, vendor verification); "v0 prototype" limitation copy → "early-stage implementation"; "The v0 core workflow" → "The core workflow … (target, not all built)". |
| `docs/CURRENT_STATE.md` | `Last updated` → `2026-08-27 (QC-1A)`; OpenAI-analyzer bullet enriched (schema from Pydantic contract, final validation, `gpt-4o-mini`, no Demo fallback); screenshot capability text corrected to "committed at `docs/assets/quotecheck-ui.png`"; Gaps updated (no automated eval/regression harness, no verified public deployment, no market-price benchmarking / price-fairness, no external vendor-claim verification; taxonomy+Demo-heuristics narrow wording); new `### Fixed in QC-1A` entry. Historical `### Fixed in TASK-NNN` / `### Fixed in LUXURY-UI-*` blocks unchanged. |
| `docs/PROJECT_STATUS.md` | Title → `Project Status — QuoteCheck`; added "UI screenshot committed" to public-ready; "Narrow taxonomy" limitation corrected (OpenAI prompt is generic; Demo stub + taxonomy are the narrow part); "No screenshot committed yet" removed, replaced with market-price / vendor-verification / no-deployment limitations; "certified mechanic, contractor…" → "a qualified professional (…)"; new "Planned hardening (not yet built)" section. |
| `docs/LOCAL_DEMO.md` | Section 8 rewritten: screenshot is committed at `docs/assets/quotecheck-ui.png` (stale `quotecheck-demo-ui.png` filename corrected); `npm install` added to the frontend run steps. |
| `CLAUDE.md` | Intro paragraph only: product scope broadened; "optional market price checks" removed and stated **not** implemented; "v0 prototype" → "early-stage implementation" (kept "do not describe it as production-ready"). Workflow / agent-instruction / build-protocol / implementation-rule sections untouched. |
| `docs/tickets/QC-1A-public-truth-alignment.md` | New ticket file (repo format). |
| `docs/review/REVIEW_BUNDLE__QC-1A-public-truth-alignment.md` | This file. |

### `git status --short`

```
 M CLAUDE.md
 M README.md
 M SPEC.md
 M docs/CURRENT_STATE.md
 M docs/LOCAL_DEMO.md
 M docs/PROJECT_STATUS.md
?? docs/tickets/QC-1A-public-truth-alignment.md
```

(plus this review bundle as a new untracked file after it is written)

### `git diff --stat`

```
 CLAUDE.md              |   7 +--
 README.md              | 133 +++++++++++++++++++++++++++++++++----------------
 SPEC.md                |  39 +++++++++------
 docs/CURRENT_STATE.md  |  81 ++++++++++++++++++++++++------
 docs/LOCAL_DEMO.md     |  13 ++---
 docs/PROJECT_STATUS.md |  32 +++++++++---
 6 files changed, 212 insertions(+), 93 deletions(-)
```

No file under `backend/`, `frontend/`, `examples/`, `logs/`, and no
`package*.json` / dependency / `.env` / deploy file appears in the diff.

## 4. Key stale claims corrected

| Stale claim (before) | Corrected to (after) | Evidence in code |
|---|---|---|
| README title `QuoteCheck v0 — understand a confusing quote before you approve it` | `QuoteCheck — Service Quote Review Assistant` | n/a (positioning) |
| "Today's scope is vehicle-service-flavored … first working slice" | OpenAI path + prompt are domain-generic; Demo heuristics + taxonomy are the narrow part with vehicle-era wording | `backend/core/prompt.py` SYSTEM_PROMPT: "across any domain … — not vehicle-only"; `backend/core/stub_analyzer.py` still keys on `brake`/`tyre`; `NormalizedCategory` enum unchanged |
| README/SPEC disclaimer "This is a **v0 prototype**" | "early-stage implementation" | n/a |
| SPEC positioning includes "optional market price checks" | removed; benchmarking is future/optional only, non-goal | `prompt.py` DEVELOPER_PROMPT explicitly forbids price benchmarking claims; `stub_analyzer.py` disclaimer: "does not … perform price benchmarking" |
| CURRENT_STATE / PROJECT_STATUS / LOCAL_DEMO: "no screenshot is committed" | screenshot committed at `docs/assets/quotecheck-ui.png`, embedded in README | file present on disk; commit `fae2b1e` "docs: add QuoteCheck UI screenshot" |
| Architecture: "(v0) stub analyzer (Demo mode, default) / OpenAI analyzer (opt-in)" (understated) | Responses API + strict Structured Outputs generated from the Pydantic `QuoteCheckResult` contract, then Pydantic re-validation; single analyzer chosen by config; OpenAI failure returns an error, no silent Demo fallback | `openai_analyzer.py`: `client.responses.create(... text={"format":{"type":"json_schema","strict":True,"schema":schema_obj}})`, `QuoteCheckResult.model_validate(payload)`; `schema_export.quotecheck_result_schema_obj()` from `model_json_schema()`; `app.py` branches on `USE_OPENAI` and re-raises on exception |
| "No eval harness or automated test suite yet" / roadmap tree `eval/ (coming next)` | no automated eval / regression harness; six captured examples + schema validation + historical manual QA; `eval/` line removed (no such dir tracked) | no `eval/` in `git ls-files`; `examples/` has 6 captured Demo outputs |
| PROJECT_STATUS: "the OpenAI-mode prompt [is] still vehicle-service-flavored" | OpenAI-mode prompt is domain-generic (TASK-012); Demo stub + taxonomy are the narrow part | `prompt.py` PROMPT_VERSION `quotecheck_v0.3`, generic SYSTEM_PROMPT |
| CLAUDE.md intro: "v0 prototype", "optional market price checks" | broadened scope; benchmarking stated not implemented; "early-stage implementation" | as above |

## 5. Acceptance-criteria table with evidence

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | README title is `QuoteCheck — Service Quote Review Assistant` | PASS | `README.md:1` |
| 2 | README describes general service/repair/maintenance/vendor review, not vehicle-only | PASS | `README.md:3-6`, `README.md:22-25`; grep 2 shows no `vehicle-only` framing in README |
| 3 | README distinguishes generic OpenAI path vs. narrower Demo heuristics | PASS | `README.md:22-25` (split), `README.md:233-259` (OpenAI mode / Demo mode subsections) |
| 4 | No current public doc claims the OpenAI prompt is vehicle-only | PASS | grep 2: only hits are the historical `### Fixed in TASK-012` block and the new `### Fixed in QC-1A` meta-entry in `CURRENT_STATE.md`, plus `CURRENT_STATE.md:130` which says the stub was "broadened beyond vehicle-only" |
| 5 | No current public doc presents `certified mechanic` as the generic disclaimer | PASS | grep 1: `CURRENT_STATE.md:38,141,465` describe it as *conditional / vehicle-only* behaviour ("only names … for clearly vehicle-related quotes"); no doc states the generic disclaimer is "certified mechanic" |
| 6 | No stale `v0 prototype` product-disclaimer wording (historical excepted) | PASS | grep 1: remaining `v0 prototype` hits are all in `CURRENT_STATE.md` historical `### Fixed in …` blocks (304, 325, 328, 570) or the QC-1A meta-entry (202, 219, 230) |
| 7 | OpenAI default documented as `gpt-4o-mini` | PASS | grep 4: `README.md:161,239`, `LOCAL_DEMO.md:72`, `CURRENT_STATE.md:29,43,127` |
| 8 | Prompt version accurate where mentioned | PASS | grep 5: `quotecheck_v0.3` in `README.md:230`, `CURRENT_STATE.md:32`; `CURRENT_STATE.md:290` is the historical `v0.2 → v0.3` bump note |
| 9 | OpenAI Responses API + Structured Outputs described accurately | PASS | `README.md:233-240`, `SPEC.md:22-27`, `CURRENT_STATE.md:26-31` |
| 10 | Demo mode = deterministic / zero-key / zero-OpenAI-cost, not an auto failure fallback | PASS | `README.md:242-250`; `README.md:207-209` and `CURRENT_STATE.md:29-31` state an OpenAI failure returns an error, no fallback |
| 11 | README states market-price benchmarking + price-fairness judgment not implemented | PASS | `README.md:27-30` ("What QuoteCheck does not do"), `README.md:281-282` (Limitations) |
| 12 | README does not claim automated evals | PASS | `README.md:253-258` ("no automated eval or regression harness yet"), `README.md:289-290` |
| 13 | README does not claim a live deployment | PASS | no deployment/live-demo section; only a `git clone` URL remains (`README.md:51`) |
| 14 | `docs/assets/quotecheck-ui.png` acknowledged; no doc claims none exists | PASS | `README.md:135-137`, `CURRENT_STATE.md:168-169`, `PROJECT_STATUS.md` public-ready bullet, `LOCAL_DEMO.md:77-84`; `test -f` → present |
| 15 | SPEC / CURRENT_STATE / PROJECT_STATUS / LOCAL_DEMO / CLAUDE do not contradict README | PASS | cross-read: all agree on generic scope, `gpt-4o-mini`, `quotecheck_v0.3`, Responses API + Structured Outputs, no evals, no deployment, screenshot committed |
| 16 | No source-code files changed | PASS | `git status --short` lists only `.md` docs + `CLAUDE.md` |
| 17 | No historical ticket/review documents rewritten | PASS | only new files under `docs/tickets/` and `docs/review/` are the two QC-1A files; historical `### Fixed in …` blocks in `CURRENT_STATE.md` untouched (verified in `git diff`) |
| — | `docs/CURRENT_STATE.md` has `### Fixed in QC-1A` + updated `Last updated` line; no QC-1B/3/4 claims | PASS | `CURRENT_STATE.md:3`, `CURRENT_STATE.md:196` |
| — | Not committed | PASS | changes left in working tree |

## 6. Exact validation commands

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
```

## 7. Exact real output

```
### git status --short
 M CLAUDE.md
 M README.md
 M SPEC.md
 M docs/CURRENT_STATE.md
 M docs/LOCAL_DEMO.md
 M docs/PROJECT_STATUS.md
?? docs/tickets/QC-1A-public-truth-alignment.md

### git diff --stat
 CLAUDE.md              |   7 +--
 README.md              | 133 +++++++++++++++++++++++++++++++++----------------
 SPEC.md                |  39 +++++++++------
 docs/CURRENT_STATE.md  |  81 ++++++++++++++++++++++++------
 docs/LOCAL_DEMO.md     |  13 ++---
 docs/PROJECT_STATUS.md |  32 +++++++++---
 6 files changed, 212 insertions(+), 93 deletions(-)

### grep 1: stale disclaimer/screenshot terms
docs/CURRENT_STATE.md:38:  only names a specific professional (e.g. "certified mechanic") for clearly
docs/CURRENT_STATE.md:141:  ("brakes/tyres", "certified mechanic") only added when a vehicle item actually
docs/CURRENT_STATE.md:202:  "v0" product framing and the "v0 prototype" disclaimer wording; replaced the
docs/CURRENT_STATE.md:219:  replaced "v0 prototype" limitation wording with "early-stage implementation".
docs/CURRENT_STATE.md:230:- `CLAUDE.md`: removed the stale "v0 prototype" and "optional market price checks"
docs/CURRENT_STATE.md:304:- `frontend/src/App.jsx`: removed the "v0 prototype" chip from the app header
docs/CURRENT_STATE.md:325:  only place the "v0 prototype" phrase was still visibly rendered in the
docs/CURRENT_STATE.md:328:  strings to drop "v0 prototype"/"prototype" while preserving the same
docs/CURRENT_STATE.md:465:  vehicle-specific phrasing ("brakes/tyres", "certified mechanic") only when a
docs/CURRENT_STATE.md:494:  placeholder section (no screenshot committed — no headless-browser tooling is
docs/CURRENT_STATE.md:570:  reads "QuoteCheck" with a "v0 prototype" chip; input is a card with helper
docs/CURRENT_STATE.md:635:- `README.md` config example corrected from `gpt-40-mini` to `gpt-4o-mini`.

### grep 2: vehicle-only framing
docs/CURRENT_STATE.md:130:  vehicle-only): brake → safety-critical/red; tyre → safety-critical/yellow; AC/
docs/CURRENT_STATE.md:203:  "vehicle-service-flavored" scope paragraph with an accurate split (the OpenAI path
docs/CURRENT_STATE.md:221:  OpenAI-mode prompt is vehicle-service-flavored; replaced "No screenshot committed
docs/CURRENT_STATE.md:279:  vehicle-only". `DEVELOPER_PROMPT` changes: (1) `missing_vehicle_context` is only

### grep 3: overclaim terms
docs/PROJECT_STATUS.md:74:- This is **not** a production-ready system: no SLAs, no hardening, no scale
CLAUDE.md:6:repo is an early-stage implementation — do not describe it as production-ready.
README.md:278:- Not production-ready: no auth, no database, no persistence beyond the local JSONL

### grep 4: gpt-4o-mini
docs/LOCAL_DEMO.md:72:   `metadata.model` matches `QUOTECHECK_MODEL` (default `gpt-4o-mini`).
docs/CURRENT_STATE.md:29:  overrides metadata. Default model `gpt-4o-mini` (`QUOTECHECK_MODEL`). An
docs/CURRENT_STATE.md:43:  (default `gpt-4o-mini`), `QUOTECHECK_LOG_PATH`, `OPENAI_API_KEY`, and
docs/CURRENT_STATE.md:127:  `gpt-4o-mini`) in OpenAI mode. The frontend shows this as a "Demo mode" / "OpenAI
docs/CURRENT_STATE.md:210:  + Structured Outputs generated from the Pydantic contract, `gpt-4o-mini` default),
docs/CURRENT_STATE.md:521:  `logs/app_runs.jsonl` entries) reported `model: "gpt-4o-mini"` even though no
docs/CURRENT_STATE.md:635:- `README.md` config example corrected from `gpt-40-mini` to `gpt-4o-mini`.

### grep 5: quotecheck_v0.3
docs/CURRENT_STATE.md:32:- `backend/core/prompt.py` — versioned prompt artifacts (`PROMPT_VERSION = quotecheck_v0.3`),
docs/CURRENT_STATE.md:290:  `PROMPT_VERSION` bumped `quotecheck_v0.2` → `quotecheck_v0.3`.
README.md:230:(`quotecheck_v0.3`) is included in both API responses and run logs so prompt changes

### file existence
docs/assets/quotecheck-ui.png: present
docs/tickets/QC-1A-public-truth-alignment.md: present
```

### Grep interpretation

- **grep 1 / grep 2 remaining hits are all in `docs/CURRENT_STATE.md` and are legitimate:**
  - `38`, `141`, `465` — current-state prose that *accurately* describes the
    conditional, vehicle-only naming of "certified mechanic" (i.e. explicitly **not**
    the generic disclaimer).
  - `130` — Capabilities prose stating the Demo stub was "broadened beyond
    vehicle-only".
  - `202`, `203`, `219`, `221`, `230` — the new `### Fixed in QC-1A` entry, which
    quotes the old wording to record what was changed.
  - `279`, `304`, `325`, `328`, `570` — pre-existing historical `### Fixed in
    TASK-012 / TASK-004 / LUXURY-UI-001A` changelog blocks (must not be rewritten).
  - `494` — historical `### Fixed in TASK-007` block recording the state at that time.
  - `635` — historical `### Fixed in TASK-001` block that documents the
    `gpt-40-mini` → `gpt-4o-mini` fix; the ticket explicitly says not to alter it.
- **grep 3**: all three hits are negations ("not production-ready" / "do not
  describe it as production-ready"). No positive over-claim.
- **grep 4 / grep 5**: all occurrences are correct current values; `CURRENT_STATE.md:521`
  and `:635` are historical changelog context.

## 8. Remaining known implementation gaps intentionally deferred

Documented honestly in the docs, **not fixed** in QC-1A (belong to later tickets):

- `missing_vehicle_context` and `needs_mechanic_confirmation` hardcoded `True` in the
  Demo stub / schema default factory.
- Demo uncertainty-marker hardcoding generally.
- Failure-log provenance bug (`app.py` failure path logs `prompt_version` /
  `model` regardless of which analyzer failed).
- Dead `schema_json` plumbing (`build_messages` accepts it but never inserts it).
- Stale `quotecheck_v0.2` stamp on the six `examples/` outputs — not regenerated.
- No automated eval / regression harness; no automated backend tests; no CI.
- No bounded provider retry / repair loop on schema-validation failure.
- No input-size limit, no rate limiting.
- No deployment URL / production CORS config / `VITE_API_BASE_URL`.
- No failure taxonomy.

Documentation was corrected; **no implementation gap above was closed.**

## 9. `git status --short`

```
 M CLAUDE.md
 M README.md
 M SPEC.md
 M docs/CURRENT_STATE.md
 M docs/LOCAL_DEMO.md
 M docs/PROJECT_STATUS.md
?? docs/tickets/QC-1A-public-truth-alignment.md
?? docs/review/REVIEW_BUNDLE__QC-1A-public-truth-alignment.md
```

## 10. `git diff --stat`

```
 CLAUDE.md              |   7 +--
 README.md              | 133 +++++++++++++++++++++++++++++++++----------------
 SPEC.md                |  39 +++++++++------
 docs/CURRENT_STATE.md  |  81 ++++++++++++++++++++++++------
 docs/LOCAL_DEMO.md     |  13 ++---
 docs/PROJECT_STATUS.md |  32 +++++++++---
 6 files changed, 212 insertions(+), 93 deletions(-)
```

Nothing has been committed — left for the user to review and commit manually.
