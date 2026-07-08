# TASK-007 — Public README and portfolio packaging

## 1. Goal

Repackage QuoteCheck's existing, already-true capabilities so the public GitHub repo
is application/portfolio-ready: a stranger should understand what QuoteCheck is, who
it helps, and why it exists in under 60 seconds, be able to run it with zero setup
friction (no API key), see a real sample report, and trust that limitations are
stated honestly. This is public packaging, not new product functionality.

## 2. Context

QuoteCheck now has an explanation-first quote-understanding contract (TASK-002), a
report UI (TASK-003), visual polish (TASK-004), progress/timeout handling (TASK-005),
and an honest demo mode with a mode badge (TASK-006). `README.md` already documented
an accurate, working Demo-mode-first walkthrough (added in TASK-006), but opened with
an engineering-tooling bullet list ("built like a deployable LLM product") before
saying who this is for or what problem it solves, never showed a full sample
response, and had no screenshot or "why this is credible" framing.

Per user direction: no screenshot/browser tooling is installed (no Playwright/
Puppeteer/Chromium), and installing one would be a new dependency — out of scope. The
README instead gets a placeholder "Screenshot" section for the user to fill in later.
Per user direction: the README must explicitly state that the backend requires an
activated Python environment, and — because there is no committed
`environment.yml`/`pyproject.toml`/lockfile, only a pinned `backend/requirements.txt`
— this is documented honestly as a limitation/future improvement, not glossed over.

## 3. Strict file scope

Allowed to create/update:
- `docs/tickets/TASK-007-public-readme-and-portfolio-packaging.md`
- `docs/review/REVIEW_BUNDLE__TASK-007-public-readme-and-portfolio-packaging.md`
- `README.md`
- `docs/CURRENT_STATE.md`
- `examples/sample_quote.txt` (new)
- `examples/sample_output.json` (new, generated from a real `/analyze` call, not
  hand-written)

Never touch: any backend/frontend source file, `package.json` / `package-lock.json`
(no new dependencies), `backend/.env`, `logs/`, secrets of any kind, `SPEC.md`.

## 4. Out of scope

No backend/frontend behavior changes (only reading `/analyze` to capture a sample
response). No price benchmarking, OCR/PDF ingestion, auth/DB, or production-readiness
claims. No new dependencies (no screenshot/browser tooling, no environment/lockfile
tooling). No `docs/ARCHITECTURE.md` (existing inline README diagram is sufficient at
this size). No CI, tests, or eval harness work. No commits/pushes.

## 5. Acceptance criteria

- README opens with product explanation (what/who/why), not setup commands or
  engineering-tooling bullets.
- Demo-mode no-key path is stated plainly near the top and is copy-pasteable.
- Setup section explicitly states the backend requires an activated Python
  environment; explicitly notes no `environment.yml`/lockfile is committed (only
  pinned `backend/requirements.txt`).
- OpenAI mode is clearly marked optional, with the same config steps as before.
- A real sample report is present: short excerpt inline plus full files in
  `examples/` (`sample_quote.txt`, `sample_output.json`).
- `examples/sample_output.json` has `metadata.model == "quotecheck-demo-analyzer"`
  and was produced by an actual `/analyze` call in Demo mode, not hand-written.
- Architecture is explained simply (existing diagram, condensed, not removed).
- Limitations section is honest and matches `docs/CURRENT_STATE.md` gaps / `SPEC.md`
  non-goals (no price benchmarking, no OCR/PDF, no production-readiness claim, no
  committed environment/lockfile).
- A short, non-inflated "why this is portfolio-credible" section exists.
- No product behavior changes; `git diff --stat` touches only `README.md`,
  `examples/`, `docs/`.
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-007.
- Review bundle records exact commands/output, no placeholders.
- No secrets committed.

## 6. Commands to run

```bash
git status --short
conda run -n quotecheck uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/analyze -H "Content-Type: application/json" \
  -d '{"quote_text":"Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."}' \
  | python3 -m json.tool | tee examples/sample_output.json
python3 -c "import json;d=json.load(open('examples/sample_output.json'));print(d['metadata']['model'])"
tail -n 1 logs/app_runs.jsonl | python3 -m json.tool
grep -RInE '\bsk-[A-Za-z0-9_-]{10,}|api_key\s*=\s*["'"'"'][^"'"'"']{10,}' README.md examples/ docs/CURRENT_STATE.md
git diff --stat main
```

## 7. Definition of done

- Ticket approved, plan approved, implementation complete within the file scope
  above.
- All acceptance criteria have concrete evidence in the review bundle (exact
  commands, exact output, no placeholders).
- `docs/CURRENT_STATE.md` "Last updated" line reflects TASK-007.
- No secrets committed; no backend/frontend files changed; work stays on
  `task/007-public-readme-and-portfolio-packaging`. Not committed — implementation
  is left for the user to review and commit manually.
