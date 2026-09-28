# CLAUDE.md — QuoteCheck

QuoteCheck turns confusing service, maintenance, repair, parts, and vendor quotes into clear explanations, red flags, vendor questions, and things to verify before approval.

Market-price benchmarking and price-fairness judgment are **not** implemented.

QuoteCheck has a live public Demo deployment, but it is still an early-stage portfolio product rather than a production service. Do not claim production-scale reliability, uptime, or capacity that has not been measured.

---

## Current development phase

**QuoteCheck v0 is closed.**

The current `main` branch is the protected v0 production baseline and backs the live public Demo deployment.

Current v1 work has one primary theme:

> **Scalability: characterize the existing system, identify real capacity constraints, bound expensive model execution and overload behaviour, and add only architecture justified by measurement.**

v1 is not a product-feature expansion.

Do not reopen completed v0 work unless a v1 ticket explicitly requires it.

---

## Read first

Before planning any ticket, read:

1. `SPEC.md` — product purpose, scope, non-goals, output principles.
2. `docs/CURRENT_STATE.md` — detailed factual implementation baseline.
3. `docs/PROJECT_STATUS.md` — public status, limitations, and claims that are safe to make.
4. The current ticket in `docs/tickets/`.
5. Relevant recent review bundles in `docs/review/`.
6. Any ticket-specific files necessary to understand the affected architecture.

For evaluation-related work, also read:

* `eval/README.md`
* `eval/rubric.md`

Never invent implemented features.

If documentation and executable code disagree, the executable code is the truth about current behaviour. Record material documentation drift rather than silently reasoning around it.

Historical sections in `docs/CURRENT_STATE.md` may describe what was true during earlier tickets. Distinguish historical notes from the current-state sections.

---

## Git and production safety

### Protected production baseline

Treat:

```text
main
```

as the production branch for the live v0 deployment.

Do not commit v1 work directly to `main`.

Do not merge v1 work into `main` unless the user explicitly approves a v1 release.

Do not change deployment configuration, production environment variables, Vercel configuration, Railway configuration, or production routing unless the active ticket explicitly includes deployment work and the user approves it.

Local scalability experiments must not intentionally load-test the live public deployment.

---

### v1 integration branch

QuoteCheck v1 development integrates into:

```text
v1/scalability
```

Individual tickets branch from the current `v1/scalability` tip and merge back into `v1/scalability`, not `main`.

Expected shape:

```text
main
└── v1/scalability
    ├── task/SCALE-001-<slug>
    ├── task/SCALE-002-<slug>
    └── ...
```

Before beginning a ticket, verify the current branch and intended base branch.

Never assume `main` is the correct merge target for v1 work.

---

## Workflow rules

1. **One ticket at a time.**
   Every unit of work must have a ticket in `docs/tickets/` with:

   * goal,
   * scope,
   * explicit non-goals,
   * acceptance criteria,
   * required evidence.

2. **Recover current truth before planning.**
   Inspect the relevant implementation, tests, configuration, documentation, and recent ticket history before proposing a change.

3. **Plan before editing.**
   Produce a concrete numbered implementation plan and obtain user approval before modifying repository files.

4. **Stay inside the ticket.**
   Do not opportunistically:

   * refactor unrelated code,
   * clean up unrelated documentation,
   * add dependencies,
   * redesign architecture,
   * fix unrelated findings.

   Record meaningful out-of-scope findings in the review bundle instead.

5. **Validate with real evidence.**
   Run the commands required by the ticket and report their actual output. Do not claim tests or validation that were not executed.

6. **Review bundle required.**
   After implementation, create:

   ```text
   docs/review/REVIEW_BUNDLE__<TICKET-ID>-<slug>.md
   ```

   Include:

   * scope summary,
   * files changed,
   * acceptance criteria with evidence,
   * exact commands run,
   * real results,
   * known limitations,
   * out-of-scope findings,
   * dependency changes,
   * relevant architectural observations.

   No placeholders.

7. **Update repository truth when necessary.**
   If a ticket changes current capabilities, commands, architecture, configuration, or known gaps, update the appropriate current-state documentation in the same ticket.

8. **Do not commit or push unless the user asks.**

---

## Scalability rules for v1

Scalability is a system property to be measured, not an infrastructure checklist.

### Measure before architecture

Do not begin with a queue, Redis, workers, multiple replicas, an async rewrite, Kafka, Kubernetes, or another scaling mechanism.

First determine:

> Where does the current system stop scaling under a controlled workload, what resource or behaviour degrades first, and why?

Architectural additions must respond to measured evidence.

---

### Separate API capacity from model-execution capacity

These are different resources.

**API capacity**

> How much incoming request work can the application receive and process?

**Model-execution capacity**

> How much expensive/provider-bound analysis work should be allowed in flight simultaneously?

A system may be capable of receiving more HTTP requests than it should execute as simultaneous model calls.

Any v1 architecture must reason explicitly about that distinction.

---

### Aggregate provider work must be bounded deliberately

The current OpenAI path already bounds each admitted request to at most two provider attempts.

That does **not** automatically bound aggregate provider demand across concurrent requests.

When scalability work reaches model-execution controls, reason about:

* concurrent provider calls,
* retries,
* overload behaviour,
* provider latency,
* provider failures,
* cost amplification.

---

### Cost is part of capacity

AI scalability is not only CPU, memory, latency, and throughput.

Where relevant, scalability decisions should also account for:

* provider attempts,
* token usage,
* cost per analysis,
* cost per successful analysis,
* amplification caused by retries or concurrency.

Do not make permanent architectural assumptions from stale provider pricing.

---

### Prefer explicit overload behaviour

If demand exceeds available model-execution capacity, behaviour should eventually be intentional and documented.

Possible mechanisms may include waiting, bounded admission, or controlled rejection, but no mechanism is pre-approved.

A queue is not automatically superior to rejection.

---

### Preserve existing product contracts

Scalability work must not casually change:

* `QuoteCheckResult`,
* existing API semantics,
* failure taxonomy,
* retry semantics,
* Demo/OpenAI provenance,
* evaluation behaviour,
* product scope.

If a scalability ticket needs a contract change, that change must be explicit in the ticket and approved before implementation.

---

### Controlled experiments are evidence, not universal claims

Demo-mode benchmarks measure the QuoteCheck application spine without external model inference.

Fake-provider benchmarks measure QuoteCheck behaviour under controlled simulated provider conditions.

Neither establishes OpenAI production capacity.

Local benchmarks are useful for:

* locating bottlenecks,
* comparing before/after architecture,
* measuring behaviour under identical controlled workloads.

They are not production SLAs or universal throughput guarantees.

---

## v1 scope guard

Unless an explicit future ticket changes the product roadmap, scalability work does **not** unlock:

* OCR,
* PDF ingestion,
* image ingestion,
* RAG,
* agents,
* authentication,
* user accounts,
* quote history,
* vendor verification,
* market-price intelligence,
* price benchmarking,
* recommendation engines,
* new product domains for breadth,
* unrelated UI redesign.

Infrastructure needed specifically to solve a measured scalability problem may be proposed, but it must not be used as a back door for unrelated features.

---

## Educational safeguard

The user owns architectural decisions.

For substantial architectural tickets:

* expose important assumptions,
* explain material tradeoffs,
* identify rejected alternatives,
* describe relevant failure modes,
* distinguish evidence from hypothesis.

Do not bury architectural decisions inside implementation details.

The goal is not merely to produce working code. The resulting system must remain understandable and defensible by its human owner.

---

## Secrets and paid-provider safety

* Never commit secrets.
* `backend/.env` is untracked and must remain untracked.
* `backend/.env.example` is the committed configuration template.
* Configuration is defined in `backend/core/config.py`.
* Demo mode is the default and makes zero provider calls.
* Prefer Demo mode or controlled fake-provider behaviour for development, testing, and scalability experiments.
* Do not run billed OpenAI experiments unless the active ticket explicitly requires them and the user approves the paid run.
* Never use the live public deployment for deliberate high-concurrency stress testing.

---

## Current architecture facts

The backend exposes:

```text
GET /health
POST /analyze
```

Since SCALE-004, `POST /analyze` is a thin `async def` admission wrapper around the existing synchronous analysis body, which still runs on FastAPI/AnyIO's worker threadpool. The OpenAI SDK path is still synchronous and performs blocking provider I/O.

Do not assume this architecture is inadequate.

Its practical concurrency and capacity limits are a v1 measurement question.

The analyzer is selected by configuration:

```text
QUOTECHECK_USE_OPENAI=0
```

Default:

```text
deterministic Demo analyzer
zero provider calls
```

Opt-in:

```text
QUOTECHECK_USE_OPENAI=1
OpenAI Responses API
strict Structured Outputs
mandatory Pydantic validation
```

The OpenAI path currently has:

```text
explicit per-attempt timeout
SDK retries disabled
one application-owned transient retry
maximum two provider attempts per request
explicit provider admission (SCALE-004):
  at most 32 admitted analyses in flight per process
  (OPENAI_MAX_CONCURRENT_ANALYSES, fixed code constant)
  admission decided before threadpool dispatch
  capacity exhausted -> fail-fast HTTP 503 capacity_exceeded
  rejected requests make zero provider calls
  a retry stays inside its request's admission slot
```

Demo mode bypasses provider admission.

The admission budget is per process. Multiple Uvicorn processes or replicas multiply aggregate provider capacity; there is no cross-process coordination. 32 is a locally measured v1 budget, not a claim about real OpenAI or Railway capacity.

There is no silent fallback from OpenAI mode to Demo mode.

Current run observability is append-only local JSONL.

The application does not currently have:

* authentication,
* user sessions,
* persistent application database,
* public rate limiting,
* cross-process (aggregate across processes/replicas) provider-concurrency control,
* durable centralized hosted logging.

Do not describe any of these as implemented.

---

## Backend setup and run commands

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Run the zero-cost Demo backend:

```bash
QUOTECHECK_USE_OPENAI=0 \
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Deployment-style local start, when specifically needed:

```bash
QUOTECHECK_USE_OPENAI=0 \
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

For the authoritative local-development walkthrough, read:

```text
docs/LOCAL_DEMO.md
```

---

## Frontend commands

```bash
cd frontend
npm ci
npm run dev -- --host
npm run build
npm run lint
```

`package-lock.json` is committed.

---

## Tests

From repository root with backend requirements installed:

```bash
python -m unittest discover -s eval/tests -p 'test_*.py' -v
```

The v0 public-inspection baseline ran **144 tests successfully**.

Do not assume that number remains fixed after future tickets. Report the number actually executed.

---

## Evaluation

Corpus validation:

```bash
python -m eval.run_eval --validate-only
```

Zero-cost deterministic Demo evaluation:

```bash
python -m eval.run_eval --mode demo
```

Paid OpenAI evaluation:

```bash
python -m eval.run_eval --mode openai --allow-paid
```

Never run the paid mode casually.

The committed v0 Demo baseline is:

```text
27/27 schema-valid
24/27 deterministic cases pass
```

Known retained residuals:

```text
AUTO-004
CONT-003
HVAC-003
```

The 24/27 value is a deterministic contract/regression result for the Demo analyzer.

It is **not** an AI accuracy score.

Semantic Layer-B evaluation remains human-scored according to:

```text
eval/rubric.md
```

---

## Logs

Inspect the latest local request record with:

```bash
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
```

Logs are local application observability, not durable centralized production logging.

---

## Public deployment

The public Demo currently consists of:

```text
Frontend:
https://quotecheck-frontend.vercel.app

Backend:
https://quotecheck-v0-production.up.railway.app
```

The hosted product is a public demonstration, not a service with an uptime or scale guarantee.

Current v1 development must not disturb this live v0 baseline.

---

## Final rule

For QuoteCheck v1:

> **Recover truth → measure → identify the bottleneck → propose the smallest justified change → implement one ticket → validate → compare against the same workload → document the tradeoff.**

Do not build infrastructure merely to make the repository look more sophisticated.
