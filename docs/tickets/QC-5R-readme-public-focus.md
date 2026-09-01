# QC-5R — README public-reader refocus

**Type:** documentation only
**Phase:** QC-5 (final public inspection) repair series — follows QC-5A
**Branch:** `task/QC-5R-readme-public-focus`

## Goal

Make `README.md` behave like the landing page of a finished public engineering
project rather than a local setup manual. A reviewer spending 30 seconds to 5
minutes should understand the product, reach the live demo, and see the engineering
evidence *before* encountering any local-development detail.

This ticket changes **hierarchy, not truth**. No new product claim, no feature
change, no runtime change.

## Motivation

`docs/review/REVIEW_BUNDLE__QC-5-final-public-inspection.md` §6–§7 found the README's
content accurate but several strong areas "poorly surfaced" (Debugging rated **B**
purely on discoverability; architecture/eval/reliability reachable only after the
setup block). Concretely, in the 571-line README:

- the live demo URL first appeared at line ~186;
- ~110 lines of prereqs / clone / venv / pip / npm / dotenv / localhost checks sat
  between the intro and the first piece of engineering evidence;
- a 58-line repo tree, a "What works today" section duplicating
  `docs/PROJECT_STATUS.md`, and an internal-milestone Roadmap occupied the tail.

## Scope

Allowed files:

- `README.md` — full restructure.
- `docs/LOCAL_DEMO.md` — the smallest repair needed for it to stand alone now that
  README's "Run locally" is only a pointer, plus the renamed-anchor link fix.
- `docs/CURRENT_STATE.md` — `Last updated` line, one concise QC-5R entry, and
  correction of *current-state* cross-references to README sections that no longer
  exist.
- `docs/tickets/QC-5R-readme-public-focus.md` (this file).
- `docs/review/REVIEW_BUNDLE__QC-5R-readme-public-focus.md`.

## Out of scope

`backend/**`, `frontend/**`, `eval/**`, `examples/**`, `railpack.json`, deployment
configuration, dependencies, `SPEC.md`, `CLAUDE.md`, `docs/PROJECT_STATUS.md`.
No CI — that is QC-5B (QC5-09). Nothing committed, merged, or pushed.

## Target README shape

1. Product description + prominent live demo link
2. What QuoteCheck does (+ explicit non-goals)
3. Product preview (screenshot + real captured output)
4. Engineering highlights
5. Architecture (+ Demo vs. OpenAI, API contract)
6. Reliability and failure handling
7. Evaluation
8. Live deployment
9. Limitations
10. Run locally (pointer only)
11. Documentation index
12. License

## Constraints

- **Anchor preservation.** `examples/README.md:15` links
  `../README.md#demo-mode-vs-openai-mode` and `examples/**` is out of scope — that
  heading must survive. `docs/LOCAL_DEMO.md` links `../README.md#screenshot`; that
  file *is* in scope, so its link is updated to the renamed section.
- **Claim discipline.** No "production-grade" / "production-ready" / "enterprise" /
  "robust AI" / "hallucination-safe" / "comprehensive evaluation", no résumé
  language, and no explicit "this demonstrates production engineering". Existing
  qualifiers are preserved verbatim in substance: failure *handling* not high
  availability; a Layer A pass count is not an accuracy score; a portfolio Demo, not
  a service; hosted-mode statements rest on observed runtime provenance only.
- **No detail loss.** Anything removed from the README must already exist in
  `docs/LOCAL_DEMO.md`, `docs/CURRENT_STATE.md`, `docs/PROJECT_STATUS.md`, or
  `eval/README.md`.

## Acceptance criteria

1. The live demo URL appears above the fold; what QuoteCheck does is clear within
   ~30 seconds of reading.
2. Engineering highlights, architecture, reliability, evaluation, and the live
   deployment all precede any local-setup material.
3. The architecture diagram shows the current configuration-selected two-path
   design, and separately identifies the observed public path as
   `quotecheck-demo-analyzer` without implying OpenAI is the hosted runtime.
4. The eval section states the corpus size (27), domain count (6), the Layer A /
   Layer B split, the committed Demo baseline (27/27 schema-valid, 24/27
   deterministic), the three retained residuals (`AUTO-004`, `CONT-003`,
   `HVAC-003`), and that 24/27 is not an AI accuracy score.
5. Reliability evidence is visible and qualified (timeout, ≤ 2 provider attempts,
   selective retry, no silent fallback, structured errors, mandatory validation,
   explicit refusal/incomplete/invalid handling).
6. Limitations remain candid, including the ephemeral-hosted-logs and
   OpenAI-not-the-observed-hosted-path points.
7. "Run locally" is a short pointer to `docs/LOCAL_DEMO.md`, which is self-contained.
8. Every README-relative link resolves to a tracked file; both inbound anchors
   (`examples/README.md`, `docs/LOCAL_DEMO.md`) resolve.
9. Live URLs verified: frontend 200; `/health` 200; `/analyze` provenance
   (`quotecheck-demo-analyzer`, `quotecheck_v0.4`, `schema_valid == true`); CORS
   behaviour.
10. Stale/high-risk language grep over `README.md` is clean.
11. `git diff` over protected paths is empty; `git diff --check` clean; nothing
    committed.
