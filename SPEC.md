# SPEC.md — QuoteCheck

## Purpose

QuoteCheck is an AI quote-understanding and quote-checking product. It helps users
understand confusing service quotes, repair estimates, parts quotes, and vendor
quotations **before approving them**.

Public positioning: *QuoteCheck turns confusing service, maintenance, repair, parts,
and vendor quotes into clear explanations, red flags, vendor questions, and things to
verify before approval.*

QuoteCheck is **not audit-only**. Quote understanding comes first: explain what each
line item is, why it might be recommended, and what is unclear.

## Current scope (what is actually built)

- User pastes raw quote text into a web UI (single-page React app).
- Backend (`POST /analyze`) returns a schema-valid structured result:
  line items with category / recommended action / risk level (red/yellow/green) /
  confidence / short rationale / evidence to request; overall summary; verification
  questions; things to verify; uncertainty markers; mandatory disclaimer; run metadata.
- Two analyzer modes, selected by configuration: a deterministic stub (default, zero
  cost) and an OpenAI mode (OpenAI Responses API, strict Structured Outputs generated
  from the Pydantic contract, then Pydantic re-validation). Every request is logged as
  one JSONL record.
- The OpenAI-mode prompt and the product framing are domain-generic across service,
  repair, maintenance, parts, and vendor quotes. The deterministic Demo heuristics and
  the shared `NormalizedCategory` taxonomy are narrower and still carry vehicle-era
  wording; broadening the taxonomy is target scope, not current scope.

See `docs/CURRENT_STATE.md` for the precise current architecture, commands, and gaps.

## Non-goals

- No price database, market-price benchmarking, or objective price-fairness
  judgment; benchmarking is future and optional.
- No vendor trustworthiness scoring and no verification of vendor claims against
  external authoritative data.
- No authentication, user accounts, or persistent database.
- No PDF/image/OCR ingestion (paste text only).
- No professional advice: QuoteCheck does not replace a qualified professional
  (mechanic, contractor, technician, etc.), and does not tell users what is safe.
- No production readiness claims: no SLAs, no hardening, no scale guarantees.

## Target pipeline

The core workflow QuoteCheck is building toward (target, not all built):

```
Quote input
  → quote parser
  → line item extractor
  → quote explainer
  → risk detector
  → question generator
  → optional price benchmarker
  → structured report
  → frontend report UI
```

Current mapping: parsing/extraction/explanation/risk/questions are performed in a
single LLM call (or stub) rather than as separate stages; the price benchmarker does
not exist yet; the structured report is the `QuoteCheckResult` schema
(`backend/core/schema.py`) rendered by the frontend.

## Output principles

Every analysis result should provide:

1. **Explanation** — plain-language description of what each line item is and why a
   vendor might recommend it.
2. **Red flags** — items that look risky, unjustified, or bundled/upsold, with a
   risk level and a short rationale.
3. **Missing information** — what the quote does not say that the user needs to know.
4. **Vendor questions** — concrete questions the user can send back to the vendor.
5. **Uncertainty** — explicit markers when the system is unsure; prefer
   "needs clarification" over confident guessing.
6. **Evidence when available** — what proof to request (measurements, photos, codes)
   before approving, especially for high-risk items.

## Honest limitation language

Use wording like this in user-facing text and docs; do not soften it:

- "QuoteCheck is an early-stage implementation. Results may be incomplete or wrong."
- "Not safety advice; verify with a qualified professional."
- "QuoteCheck explains quotes and suggests questions; it does not verify vendor
  claims or guarantee fair pricing."
- "Price benchmarking is not implemented; any price commentary is not a market check."
