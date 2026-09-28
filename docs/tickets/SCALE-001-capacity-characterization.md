# SCALE-001 — Current-System Capacity and Bottleneck Characterization

## 1. Goal

Create a **zero-provider-cost, reproducible capacity-characterization harness** and use it to establish how the existing QuoteCheck system behaves as concurrent request demand and simulated provider latency increase.

The ticket must answer:

> **Where does current QuoteCheck stop scaling under controlled workloads, what resource or behaviour degrades first, and what evidence should determine the next architectural change?**

This is a measurement ticket.

It must **not improve, redesign, optimize, or scale the production runtime**.

---

## 2. Context

QuoteCheck v0 is closed.

The live v0 production baseline remains on:

```text
main @ 2ff1cff
```

with preservation references:

```text
v0-closed
quotecheck-v0-closed
v0.1.0
```

QuoteCheck v1 development integrates into:

```text
v1/scalability
```

SCALE-001 is the first real CodeFactory execution ticket on QuoteCheck.

The ticket branch must be created from the current `v1/scalability` tip, currently:

```text
531853b
```

Expected branch:

```text
task/SCALE-001-capacity-characterization
```

`main`, `v0-closed`, and the live Vercel/Railway deployment must remain untouched.

---

## 3. Engineering question

Current QuoteCheck already bounds individual OpenAI requests:

```text
maximum provider attempts / request = 2
```

but its aggregate capacity is not characterized.

The current OpenAI execution path is approximately:

```text
incoming HTTP requests
        ↓
FastAPI synchronous route
        ↓
threadpool/request-execution capacity
        ↓
blocking OpenAI SDK calls
        ↓
provider latency / provider limits
        ↓
retry amplification
        ↓
cost
```

Important candidate constraints include:

* FastAPI / threadpool request execution,
* external-provider latency,
* aggregate provider calls in flight,
* retry amplification,
* per-request OpenAI client construction,
* synchronous JSONL logging,
* local machine resources,
* another constraint revealed by measurement.

These are hypotheses.

The ticket must not assume which one is dominant.

---

## 4. Strict scope

### Allowed to create

A small benchmark package under:

```text
benchmarks/
```

containing only what is necessary for reproducible SCALE-001 experiments.

Likely responsibilities include:

* workload definition,
* concurrent request execution,
* controlled fake-provider behaviour,
* timing collection,
* raw result serialization,
* summary statistics,
* environment metadata.

Exact file decomposition is an implementation decision.

Also allowed to create:

```text
docs/scalability/SCALE-001_BASELINE.md
docs/tickets/SCALE-001-capacity-characterization.md
docs/review/REVIEW_BUNDLE__SCALE-001-capacity-characterization.md
```

A focused test file for the benchmark tooling may be added under:

```text
eval/tests/
```

if required.

### Allowed to edit

```text
docs/CURRENT_STATE.md
```

only to:

* update its current-state timestamp/ticket marker,
* add a concise SCALE-001 entry after the work is complete,
* record the benchmark capability and findings honestly.

Existing historical entries must remain historical.

### Protected runtime

Do not modify:

```text
backend/app.py
backend/core/openai_analyzer.py
backend/core/stub_analyzer.py
backend/core/schema.py
backend/core/config.py
backend/core/errors.py
backend/core/prompt.py
backend/core/run_logger.py
frontend/**
railpack.json
backend/requirements.txt
```

or other production runtime files.

If the benchmark genuinely cannot be implemented without introducing a runtime/testability seam:

> **STOP. Do not implement the seam. Report exactly what seam appears necessary, why, and the smallest proposed change for human architectural review.**

Do not smuggle testability refactors into SCALE-001.

### Dependencies

No new runtime dependency.

Prefer the Python standard library and dependencies already installed by QuoteCheck.

If an additional benchmark-only dependency appears necessary:

> Stop and justify it before adding it.

---

## 5. Explicit non-goals

SCALE-001 must not add or implement:

* provider concurrency limiting,
* semaphores as runtime capacity controls,
* admission control,
* public rate limiting,
* request queues,
* background workers,
* Redis,
* databases,
* Celery,
* RQ,
* Kafka,
* Kubernetes,
* multiple production replicas,
* multiple Uvicorn workers as an optimization,
* async route conversion,
* OpenAI SDK redesign,
* provider-client reuse optimization,
* retry-policy changes,
* timeout-policy changes,
* centralized logging,
* tracing vendors,
* production observability services,
* CI,
* deployment changes,
* product features.

Do not load-test:

```text
https://quotecheck-frontend.vercel.app
https://quotecheck-v0-production.up.railway.app
```

No paid OpenAI calls.

---

# 6. Benchmark methodology

## 6.1 General reproducibility

Every recorded experiment must include enough context to reproduce it.

At minimum record:

```text
git commit
ticket id
timestamp
Python version
operating system
CPU / logical CPU count
available machine-memory information where obtainable without a new dependency
Uvicorn command where applicable
process / worker count
analyzer mode
workload / fixture identifier
quote-text length
request count
concurrency
trial number
provider scenario
simulated provider latency where applicable
```

Do not imply local-machine results are universal production limits.

---

## 6.2 Fixed workloads

Before/after comparison requires stable inputs.

Create a small fixed workload set representing at least:

```text
short quote
normal representative quote
near-maximum-length quote
```

The exact text must be committed or otherwise deterministically defined by the harness.

The same workload definitions must be reusable by future scalability tickets.

Do not modify QuoteCheck product semantics to create benchmark fixtures.

---

## 6.3 Warm-up

Measured trials must not include obvious startup / first-request effects.

Each benchmark class must perform documented warm-up work before recording measured requests.

Warm-up behaviour must be deterministic and excluded from result statistics.

---

## 6.4 Repeated trials

Do not derive a capacity conclusion from one run.

Each standard concurrency point must use repeated measured trials.

Default:

```text
3 measured trials / concurrency point
```

If a particular slow-provider experiment requires a smaller bounded trial plan for execution-time reasons, document the deviation and why it still provides useful evidence.

---

# 7. Experiment A — real local HTTP Demo baseline

This experiment measures the application/service spine without external inference.

Run QuoteCheck locally in deployment-like Demo mode:

```bash
QUOTECHECK_USE_OPENAI=0 \
uvicorn backend.app:app --host 127.0.0.1 --port <local-port>
```

No `--reload`.

One process unless the ticket explicitly states otherwise.

The benchmark client must communicate through **real localhost HTTP**.

Do not benchmark `analyze_quote_stub()` directly.

Start with concurrency:

```text
1
2
4
8
16
```

If no useful saturation behaviour appears and the local machine remains stable, continue selectively to:

```text
32
64
```

Do not increase concurrency indefinitely merely to force failure.

For each measured run capture at least:

```text
request count
HTTP success count
HTTP failure count
total wall-clock duration
throughput
per-request client latency
p50 latency
p95 latency
maximum latency
HTTP status
```

Where possible, correlate with existing QuoteCheck server-reported latency without changing runtime code.

---

# 8. Experiment B — controlled fake-provider capacity

The purpose of this experiment is to answer:

> What does QuoteCheck itself do when model execution becomes slow while concurrent requests increase?

No real provider traffic is permitted.

The fake-provider path must:

1. enter QuoteCheck through `POST /analyze`;
2. execute the OpenAI-mode application path rather than the Demo analyzer;
3. replace the actual provider boundary with deterministic controlled behaviour;
4. return a schema-valid response compatible with the existing `QuoteCheckResult` contract;
5. never contact the network;
6. preserve the production OpenAI analyzer's retry semantics rather than bypassing them when those semantics are being measured.

Existing QC-4 tests already demonstrate provider-boundary replacement with controlled fakes. Reuse the smallest appropriate pattern rather than inventing a production abstraction solely for benchmarking.

An in-process application/API test boundary is acceptable for this fake-provider experiment if it allows the real `/analyze` path to execute safely and concurrently.

Do not benchmark `analyze_quote_openai()` in isolation as the main capacity result.

---

## 8.1 Successful provider-latency scenarios

Characterize at least two deterministic provider-latency classes:

```text
~250 ms
~1 second
```

Use concurrency levels sufficient to expose the relationship between incoming request concurrency and provider calls in flight.

Start with:

```text
1
2
4
8
16
```

and extend selectively if useful.

The implementation may include one additional deliberately slow scenario if it provides meaningful evidence without making the benchmark impractically long.

---

## 8.2 Fake-provider instrumentation

The controlled provider must measure at least:

```text
provider calls started
provider calls completed
provider calls currently in flight
peak provider calls in flight
provider attempts
configured simulated latency
```

Shared counters must be concurrency-safe.

Instrumentation must not materially change production runtime code.

---

## 8.3 Retry-amplification spot check

Include at least one small controlled scenario where a transient provider failure is followed by success.

Purpose:

* confirm the existing two-attempt bound remains intact,
* observe how retries affect total provider-call count,
* demonstrate why per-request retry bounds do not themselves create an aggregate provider bound.

This is a bounded characterization case, not a complete failure/saturation campaign.

Full overload/failure validation belongs to a later milestone.

---

# 9. Statistics and output

For each measured concurrency point report at least:

```text
trial count
requests / trial
successes
failures
throughput
p50 client latency
p95 client latency
maximum client latency
```

For fake-provider scenarios also report:

```text
total provider attempts
peak provider calls in flight
```

Document the percentile calculation method.

### p99 rule

Do not report p99 merely because production dashboards often contain it.

p99 may be reported only when the sample count makes the statistic meaningful.

Otherwise omit it.

---

# 10. Raw evidence

Do not leave only a Markdown summary.

The harness must emit machine-readable raw evidence sufficient to reproduce summary calculations.

A reasonable shape is:

```text
benchmarks/results/<timestamp-or-baseline-id>.jsonl
```

or an equivalently simple format.

Each measured request should retain enough information to derive:

```text
scenario
trial
concurrency
request identity/index
start/end or duration
success/failure
HTTP status
```

Provider-level aggregate measurements may be emitted per trial/scenario if that better matches their semantics.

Do not include:

* quote text unnecessarily,
* API keys,
* secrets,
* raw exception dumps,
* private data.

---

# 11. Baseline report

Create:

```text
docs/scalability/SCALE-001_BASELINE.md
```

It must contain:

## Environment

Exact execution context.

## Methodology

What was measured and how.

## Workloads

Exact workload classes and why they were chosen.

## Demo HTTP results

Measured application-spine behaviour.

## Fake-provider results

Measured behaviour as simulated model latency/concurrency rises.

## Capacity curve

Describe how:

```text
concurrency
latency
throughput
provider calls in flight
failures
```

change together.

## Saturation finding

State one of:

```text
A clear saturation knee was observed.
```

or:

```text
No trustworthy saturation knee was reached within the bounded experiment.
```

Do not invent one.

## Bottleneck assessment

Classify evidence as:

```text
observed fact
supported inference
remaining hypothesis
```

Do not collapse those categories.

## Decision Gate A

End with:

> What, if anything, does SCALE-001 evidence justify changing next?

The answer may legitimately be:

> More measurement is required before a runtime architecture change is justified.

---

# 12. Existing-system regression guard

The ticket must preserve current QuoteCheck behaviour.

Run:

```bash
python -m unittest discover -s eval/tests -p 'test_*.py' -v
```

Report the actual test count.

The v0 baseline was 144 tests; do not hard-code 144 as the expected future count if SCALE-001 adds benchmark tests.

Run:

```bash
python -m eval.run_eval --validate-only
```

Run:

```bash
python -m eval.run_eval --mode demo
```

Expected existing product baseline:

```text
27/27 schema-valid
24/27 deterministic cases pass
known residuals:
AUTO-004
CONT-003
HVAC-003
```

The Demo eval exits non-zero because known contract gaps remain. Do not “fix” those residuals in this ticket.

---

# 13. Acceptance criteria

1. A reproducible zero-provider-cost benchmark harness exists.
2. No billed OpenAI call was made.
3. No production deployment was load-tested.
4. Real localhost HTTP is used for Demo-mode capacity characterization.
5. Fake-provider characterization enters through `POST /analyze` and exercises the OpenAI-mode application path.
6. The fake provider cannot accidentally contact the real OpenAI service during benchmark execution.
7. Benchmark workloads are deterministic and reusable.
8. Warm-up is explicitly separated from measured requests.
9. Standard concurrency points use repeated trials.
10. Raw machine-readable request evidence is retained.
11. Demo results include success/failure counts, throughput, p50, p95 and max latency.
12. Fake-provider results additionally include provider attempts and peak provider calls in flight.
13. p99 is omitted unless the collected sample size justifies it.
14. At least two successful simulated-provider latency classes are characterized.
15. At least one bounded transient-failure→success retry-amplification scenario is characterized.
16. The report states whether a trustworthy saturation knee was observed.
17. The report separates observed facts, supported inferences and remaining hypotheses.
18. The report identifies the best-supported current candidate bottleneck, or explicitly states that evidence is insufficient.
19. `docs/scalability/SCALE-001_BASELINE.md` ends with Decision Gate A.
20. Existing QuoteCheck unit/regression tests remain healthy.
21. Eval corpus validation remains healthy.
22. Demo eval remains at the existing 27/27 schema-valid, 24/27 deterministic-pass baseline unless a pre-existing nondeterminism is demonstrated.
23. No production runtime architecture is changed.
24. No protected runtime file is modified.
25. No new production/runtime dependency is added.
26. `main`, `v0-closed`, production tags and deployment configuration remain untouched.
27. A complete SCALE-001 review bundle contains exact commands and real outputs.
28. Nothing is committed or merged unless the user explicitly requests it.

---

# 14. Commands / evidence to include

At minimum:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
git diff --stat
```

Protected runtime check:

```bash
git diff -- \
  backend/app.py \
  backend/core/openai_analyzer.py \
  backend/core/stub_analyzer.py \
  backend/core/schema.py \
  backend/core/config.py \
  backend/core/errors.py \
  backend/core/prompt.py \
  backend/core/run_logger.py \
  frontend \
  railpack.json \
  backend/requirements.txt
```

Expected:

```text
empty
```

Regression suite:

```bash
python -m unittest discover -s eval/tests -p 'test_*.py' -v
python -m eval.run_eval --validate-only
python -m eval.run_eval --mode demo
```

Benchmark commands must be documented by the implementation itself and reproduced exactly in the review bundle.

Also record:

```bash
git status --short
git diff --stat
```

after all work.

---

# 15. CodeFactory observation requirement

Because this is QuoteCheck's first real CodeFactory ticket, the review bundle must include a separate:

```text
## CodeFactory observations
```

section.

Record only observed evidence, including:

* whether repo truth was recovered correctly,
* whether the plan stayed inside ticket scope,
* whether CodeFactory attempted unnecessary architecture,
* validator findings,
* repair iterations,
* any manual intervention,
* any ambiguity in the ticket itself.

Classify problems as one of:

```text
QuoteCheck defect
CodeFactory defect
Ticket/control defect
```

Do not force every ticket to contain a defect.

---

# 16. Definition of done

SCALE-001 is done when we can answer, with reproducible evidence:

> **How does current QuoteCheck behave as concurrent demand and simulated model latency increase?**

> **What degrades first?**

> **What resource or behaviour is the best-supported current capacity constraint?**

> **What architectural change, if any, has now earned the right to be considered?**

The existence of a benchmark script alone does not complete the ticket.

No scaling architecture is implemented in SCALE-001.

No commit.

No merge.

The user reviews the evidence and owns Decision Gate A.
