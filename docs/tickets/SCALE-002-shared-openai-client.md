# SCALE-002 — Shared OpenAI Client + Recharacterization

Risk class: **T3 — Architecture-Sensitive** (it changes the OpenAI SDK client lifetime on the real provider path).

Branch: `task/SCALE-002-shared-openai-client`, created from `v1/scalability` @ `4e33bfc`. That tip is the merge of `main` (QC-HOTFIX-demo-question-bound) into v1. The branch merges back into `v1/scalability`, never `main`.

## 1. Goal

Replace per-request `OpenAI(...)` construction with **one reusable synchronous OpenAI client per application process**, preserving every existing provider behaviour. Then rerun the SCALE-001 methodology to answer:

> Once per-request client construction is removed, what becomes the next meaningful capacity constraint?

The ticket ends at **Decision Gate B**. Whatever Gate B recommends is not implemented here.

## 2. Context

SCALE-001 (`docs/scalability/SCALE-001_BASELINE.md`) found per-request client construction to be the first constraint on the OpenAI path. It costs about 20 ms CPU serially (SSL context + CA bundle) and degrades natively under thread concurrency. With the 250 ms fake provider, throughput plateaued at 36–41 rps and CPU per request rose about 25×. Decision Gate A recommended a process-level client as the smallest next intervention.

## 3. Scope

- `backend/core/openai_analyzer.py`: a lazily constructed, lock-guarded, process-wide `OpenAI` client, built with the exact current arguments (`api_key`, validated timeout, `max_retries=0`).
- Test isolation for the shared state, plus new tests proving reuse, a single construction under a concurrent cold start, and unchanged configuration/Demo semantics.
- Benchmark provenance metadata only: `env.json` records `harness_origin` (SCALE-001) separately from `measurement_ticket`.
- A fresh before control (`SCALE-002-before`) and an after run (`SCALE-002-after`) with the unchanged SCALE-001 harness. SCALE-001 results are left untouched.
- A before/after report with Decision Gate B, a review bundle, and a current-state update.

## 4. Non-goals

- Provider concurrency limiting
- Admission control, overload rejection or queueing
- HTTP connection-pool tuning
- Async OpenAI or async FastAPI
- Extra Uvicorn workers or replicas
- Redis
- Rate limiting
- Centralized observability
- Cost controls
- Product, schema or prompt changes
- An `app.py` lifecycle/shutdown hook
- New dependencies
- Unrelated refactoring
- Any change to workloads, ladders, statistics, guards, topology or request counts in the benchmark harness

## 5. Preserved contracts

The following must stay exactly as they are:

- Synchronous execution
- Per-attempt timeout semantics
- SDK `max_retries=0`
- The application-owned single transient retry, with a maximum of 2 attempts
- No retry on 429
- The failure taxonomy
- `provider_attempts` accounting
- Mandatory final `QuoteCheckResult` validation
- No Demo fallback
- The API and logging contracts
- The prompt and structured-output schema

## 6. Acceptance criteria

1. Multiple OpenAI analyses in one process reuse one SDK client, and simultaneous cold requests construct exactly one.
2. Reliability semantics are unchanged: success takes 1 attempt, a transient failure takes at most 2, 429 is not retried, terminal/config classification is unchanged, SDK retries stay disabled, the timeout is honoured, and final validation stays mandatory.
3. Configuration is safe:
   - Demo mode builds no client, makes no provider call and needs no credential.
   - OpenAI mode with a missing key or invalid timeout raises `configuration_error`, builds no client and makes no provider request.
4. The SCALE-001 methodology is rerun: Demo control, fake 250 ms and 1 s ladders (C = 1–64), retry spot checks, one uvicorn process, `--loop asyncio --http h11`, 3 trials, nearest-rank statistics. The results are a separate SCALE-002 set.
5. The before/after comparison covers:
   - throughput, p50/p95/max latency and failure rate;
   - server CPU and CPU per request;
   - provider attempts, peak provider in-flight and fake connections accepted;
   - threads, RSS and fds.

   Each finding is labelled as fact, inference or hypothesis.
6. The pinned SDK/httpx connection-pool defaults are recorded, and any pool effect is observed. Nothing is tuned.
7. Full regression runs:
   - the unittest suite, reporting the real count;
   - `eval.run_eval --validate-only`;
   - `eval.run_eval --mode demo`, expecting 27/27 schema-valid, 24/27 pass, and residuals AUTO-004, CONT-003 and HVAC-003.

   No paid evals are run.

## 7. Decision Gate B

Answer these questions:

- **A.** Did client reuse remove the construction bottleneck? Quantify it.
- **B.** What is now the first meaningful constraint?
- **C.** What remains unproven? Keep local fake-provider evidence separate from Railway, real OpenAI latency, TLS/DNS, rate limits, cost and traffic shape.
- **D.** What is the smallest justified next intervention? It is not implemented here.

## 8. Required evidence

- `benchmarks/results/SCALE-002-before/` and `benchmarks/results/SCALE-002-after/`, with `stats --check` passing on both.
- `docs/scalability/SCALE-002_SHARED_CLIENT.md`
- `docs/review/REVIEW_BUNDLE__SCALE-002-shared-openai-client.md`, with exact commands and real outputs.

## 9. Cost and safety

The budget is ₹0:

- No real OpenAI calls. All provider-path measurement uses the loopback fake provider.
- No load on the public deployment.
- No real API key required.
