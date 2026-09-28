# QC-HOTFIX — Demo `verification_questions` bound

Risk class **T2** (normal bug fix), modifier **BUG**. Branch
`task/QC-HOTFIX-demo-question-bound`, based on `main` @ `2ff1cff`.

## Goal

For every valid Demo-mode quote, including mixed-domain quotes, the deterministic
analyzer returns a schema-valid `QuoteCheckResult` rather than failing because its
generated `verification_questions` exceed the response contract (`max_length=8`).

## Bug

Reproduction:

```text
Brake pad replacement. AC gas top-up. Leaking tap valve replacement. Panel earthing check. Compressor overhaul after diagnosis.
```

The Demo analyzer raises a Pydantic `ValidationError` (9 > 8 questions) and
`POST /analyze` returns HTTP 500 `internal_error`. This predates SCALE-001.

## Scope

- Bound the combined `verification_questions` at the analyzer's
  combination point, while keeping deterministic ordering and representation
  from every matched block.
- Add regression tests that fail on `main`.
- Update `docs/CURRENT_STATE.md`.

## Out of scope

Schema limit changes, question-taxonomy redesign, new domain recognition,
`things_to_verify` changes, OpenAI mode, prompt, API/error taxonomy, frontend,
deployment, SCALE-001 changes, and the public deployment (not contacted).

## Acceptance criteria

1. The reproduction succeeds through the Demo analyzer and validates as `QuoteCheckResult`.
2. Local `POST /analyze` (Demo mode) returns HTTP 200 for the reproduction.
3. `3 <= len(verification_questions) <= 8` for valid Demo results.
4. Regression tests cover the overflow and fail against `main`.
5. Single-domain and two-block output is unchanged. Mixed-domain output keeps every matched block.
6. The unit suite, `--validate-only`, and `--mode demo` are healthy. Demo eval stays at 27/27
   schema-valid and 24/27 deterministic, with residuals `AUTO-004`, `CONT-003`, `HVAC-003`.
7. Local Demo HTTP smoke evidence is reported.
