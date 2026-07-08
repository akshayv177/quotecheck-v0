# TASK-002 — Quote-understanding contract baseline

## 1. Goal

Make the backend output contract and analyzer behavior clearly support QuoteCheck's
product promise: QuoteCheck is an AI quote-understanding and quote-checking product.
Quote understanding comes first, checking/risk detection comes second, and optional
price benchmarking comes later and must not be claimed as implemented today.

## 2. Context

`SPEC.md` describes six output principles: explanation, red flags, missing
information, vendor questions, uncertainty, and evidence-when-available. The current
schema (`backend/core/schema.py`), prompt (`backend/core/prompt.py`), and stub
(`backend/core/stub_analyzer.py`) already cover most of these, but skew audit/risk-
first:

- `LineItem.rationale_short` is risk-flag rationale, not a plain-English explanation
  of what the item is or why a vendor might recommend it.
- Vague/confusing detection only exists implicitly via the
  `unknown_needs_clarification` category value.
- The stub only recognizes "brake" and "tyre/tire" keywords; other charges (e.g.
  "Labour", "Misc charges", "AC gas top-up") are silently dropped whenever at least
  one of those two keywords also matches.

This ticket makes the smallest compatible schema change (two new `LineItem` fields,
both with safe defaults for backward compatibility) plus prompt/stub updates so the
contract is explanation-first while remaining schema-compatible with the existing
`/analyze` consumers (notably the frontend, which is out of scope for this ticket).

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-002-quote-understanding-contract.md`
- `docs/review/REVIEW_BUNDLE__TASK-002-quote-understanding-contract.md`
- `backend/core/schema.py`
- `backend/core/prompt.py`
- `backend/core/stub_analyzer.py`
- `backend/core/schema_export.py` (only if schema changes require it)
- `docs/CURRENT_STATE.md`

Allowed only if genuinely necessary for keeping `/analyze` compatible:
- `backend/app.py`
- `backend/core/openai_analyzer.py`

Never touch: `frontend/` source files, `README.md`, `package-lock.json`,
`backend/.env`, `logs/`, secrets of any kind.

## 4. Out of scope

No frontend UI work. No price benchmarking. No web search. No OCR/PDF/image parsing.
No database/auth. No provider abstraction. No model migration. No broad architecture
refactor. No fake evidence or fake market sources. No production-readiness claims.
No commits.

## 5. Acceptance criteria

- Backend response contract clearly supports quote understanding, not only audit/risk.
- Line items include or clearly expose plain-English explanations.
- Missing information and vague/confusing charges are represented clearly.
- Vendor questions are represented clearly.
- Red flags/risk levels remain represented clearly.
- Uncertainty markers remain explicit.
- Stub mode returns a realistic explanation-first report for at least one sample quote.
- OpenAI prompt instructs the model to produce explanation-first, uncertainty-aware,
  schema-valid output.
- Existing `/analyze` endpoint remains compatible and schema-valid.
- No price benchmarking or market evidence is claimed as implemented.
- `docs/CURRENT_STATE.md` is updated with the new contract state and remaining gaps.
- Review bundle contains exact commands and exact outputs after implementation.
- No secrets are committed.
- No frontend files are changed.

## 6. Commands to run

```bash
git status --short
python -c "from backend.app import app; print(app.title)"
python -c "from backend.core.schema import QuoteCheckResult; print(QuoteCheckResult.model_json_schema().keys())"
uvicorn backend.app:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" -d '{"quote_text":"Brake pad replacement ₹8,500. Labour ₹2,500. Misc charges ₹1,200. AC gas top-up ₹3,000. Tyre rotation included but no tyre condition report attached."}'
grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' backend/core/schema.py backend/core/prompt.py backend/core/stub_analyzer.py docs/CURRENT_STATE.md
```

## 7. Definition of done

- Ticket approved, plan approved, implementation complete within the file scope above.
- All acceptance criteria have concrete evidence in the review bundle (exact commands,
  exact output, no placeholders).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-002.
- No secrets committed; no frontend files changed; work stays on
  `task/TASK-002-quote-understanding-contract`.
