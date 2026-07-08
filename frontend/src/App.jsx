/**
 * QuoteCheck Frontend (v0) - App
 *
 * Block 1.5: minimal cross-check that the frontend can talk to the backend.
 * This also helps us catch and fix CORS early before we build /analyze.
 *
 * Block 2: wire the UI to POST /analyze and render the schema-shaped response.
 *
 * TASK-003: quote-understanding-first report layout. `explanation` is the
 * primary human-readable field per line item; `rationale_short` is secondary
 * risk reasoning; `vague_or_confusing` surfaces as a "NEEDS CLARIFICATION"
 * badge alongside the risk pill.
 *
 * TASK-004: visual polish pass. Styling only — same data flow, same
 * `/analyze` payload, same fields rendered.
 *
 * TASK-005: perceived-latency and progress states. Adds a client-side
 * simulated stage sequence (derived from elapsed time, not a real backend
 * progress signal — the backend is a single blocking call with no streaming),
 * an elapsed-time readout, a client-side request timeout via AbortController,
 * and error copy differentiated by failure kind. No `/analyze` payload or
 * response-shape change.
 *
 * TASK-006: mock/demo mode. The backend now reports an honest
 * `metadata.model` value in stub mode (`quotecheck-demo-analyzer` instead of
 * an OpenAI model name); this adds a small "Demo mode" / "OpenAI mode" badge
 * next to the metadata footer line, driven purely by that value. No other
 * data-flow or `/analyze` change.
 *
 * LUXURY-UI-001: visual identity pass. Inline style objects were extracted
 * into CSS classes (frontend/src/index.css) so the report reads as a calm
 * review document rather than a generic component-library UI. Component
 * structure, props, and data flow are unchanged; no `/analyze` change.
 */

import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = "http://localhost:8000";

const DEMO_ANALYZER_MODEL = "quotecheck-demo-analyzer";

const REQUEST_TIMEOUT_MS = 55_000; // ~2.75x the ~20s typical real-LLM-mode latency

const STAGES = [
  { label: "Reading the quote…", minMs: 0 },
  { label: "Identifying line items…", minMs: 3000 },
  { label: "Checking for vague or risky charges…", minMs: 8000 },
  { label: "Preparing your report…", minMs: 15000 },
];
const SLOW_HINT_MS = 20000;

function stageForElapsed(ms) {
  let idx = 0;
  for (let i = 0; i < STAGES.length; i++) if (ms >= STAGES[i].minMs) idx = i;
  return idx;
}

function formatElapsed(ms) {
  const s = Math.floor(ms / 1000);
  return s < 60 ? `${s}s elapsed` : `${Math.floor(s / 60)}m ${s % 60}s elapsed`;
}

const NETWORK_ERROR_MESSAGE =
  "Couldn't reach the QuoteCheck backend. Make sure it's running at http://localhost:8000, then try again.";
const TIMEOUT_ERROR_MESSAGE =
  "This is taking longer than expected (over 55 seconds), so QuoteCheck gave up waiting. " +
  "If you're running in AI mode the model call may be slow or stuck — try again, or check the backend terminal for errors.";

export default function App() {
  const [quoteText, setQuoteText] = useState(
    "Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."
  );
  const [result, setResult] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const startedAtRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => setElapsedMs(Date.now() - startedAtRef.current), 250);
    return () => clearInterval(id);
  }, [loading]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const prettyJson = useMemo(() => (result ? JSON.stringify(result, null, 2) : ""), [result]);

  const riskCounts = useMemo(() => {
    const items = result?.line_items || [];
    const counts = { red: 0, yellow: 0, green: 0, vague: 0 };
    for (const it of items) {
      const l = String(it.risk_level || "").toLowerCase();
      if (counts[l] !== undefined) counts[l] += 1;
      if (it.vague_or_confusing) counts.vague += 1;
    }
    return { total: items.length, ...counts };
  }, [result]);

  async function analyzeQuote() {
    const controller = new AbortController();
    abortRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    startedAtRef.current = Date.now();
    setElapsedMs(0);
    setLoading(true);
    setErr(null);

    try {
      const r = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quote_text: quoteText }), // backend expects quote_text
        signal: controller.signal
      });
      if (!r.ok) {
        const text = await r.text();
        const httpErr = new Error(`HTTP ${r.status}: ${text}`);
        httpErr.kind = "http";
        throw httpErr;
      }
      const data = await r.json();
      setResult(data);
    } catch (e) {
      if (e.name === "AbortError") setErr({ kind: "timeout", message: TIMEOUT_ERROR_MESSAGE });
      else if (e instanceof TypeError) setErr({ kind: "network", message: NETWORK_ERROR_MESSAGE });
      else if (e.kind === "http") setErr({ kind: "http", message: e.message });
      else setErr({ kind: "other", message: String(e?.message || e) });
      setResult(null);
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
      abortRef.current = null;
    }
  }

  async function copyJson() {
    if (!prettyJson) return;
    await navigator.clipboard.writeText(prettyJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="qc-shell">
      <header className="qc-header">
        <div className="qc-header__title-row">
          <h1 className="qc-wordmark">QuoteCheck</h1>
          <span className="qc-chip">v0 prototype</span>
        </div>
        <div className="qc-header__tagline">
          Paste a service or repair quote. QuoteCheck explains every line item, flags
          what's vague or risky, and gives you questions to send back — before you approve.
        </div>
      </header>

      <div className="qc-input-card">
        <label className="qc-input-card__label">Your quote</label>
        <textarea
          className="qc-textarea"
          value={quoteText}
          onChange={(e) => setQuoteText(e.target.value)}
          rows={8}
          placeholder="Paste the quote text exactly as you received it…"
        />
        <div className="qc-input-card__hint">
          Works with service, repair, and parts quotes. Text only for now.
        </div>

        <div className="qc-actions">
          <button
            className="qc-btn-primary"
            onClick={analyzeQuote}
            disabled={loading || quoteText.trim().length === 0}
            aria-busy={loading}
          >
            {loading ? "Analyzing…" : "Analyze quote"}
          </button>
        </div>

        {loading && (
          <div className="qc-loading">
            <div className="status-pulse" />
            <div role="status" aria-live="polite" className="qc-loading__status">
              <span>{STAGES[stageForElapsed(elapsedMs)].label}</span>
              <span>{formatElapsed(elapsedMs)}</span>
            </div>
            {elapsedMs > SLOW_HINT_MS && (
              <div className="qc-loading__hint">
                Still working — complex quotes can take a little longer.
              </div>
            )}
          </div>
        )}
      </div>

      {err && (
        <div className="qc-error-card">
          <div className="qc-error-card__title">Couldn't analyze this quote.</div>
          <div className="qc-error-card__message">{err.message}</div>
          {(err.kind === "http" || err.kind === "other") && (
            <div className="qc-error-card__hint">
              Check that the backend is running on port 8000.
            </div>
          )}
        </div>
      )}

      {result && (
        <div className="qc-report">
          <div className="qc-report__header">
            <h2 className="qc-report__title">Report</h2>
            <div className="qc-tally">
              <span className="qc-tally__item">
                {riskCounts.total} item{riskCounts.total === 1 ? "" : "s"}
              </span>
              {riskCounts.red > 0 && (
                <span className="qc-tally__item qc-tally__item--red">{riskCounts.red} high risk</span>
              )}
              {riskCounts.yellow > 0 && (
                <span className="qc-tally__item qc-tally__item--yellow">{riskCounts.yellow} caution</span>
              )}
              {riskCounts.vague > 0 && (
                <span className="qc-tally__item qc-tally__item--vague">{riskCounts.vague} needs clarification</span>
              )}
            </div>
          </div>

          <Card title="Summary">
            <ul className="qc-card__list">
              {(result.overall_summary || []).map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </Card>

          <div className="qc-section-label">Line items, explained</div>
          <div className="qc-line-items">
            {(result.line_items || []).map((it, idx) => (
              <LineItemCard key={idx} item={it} />
            ))}
          </div>

          <div className="qc-section-label">Before you approve</div>
          <div className="two-col-grid">
            <Card title="Questions to ask the vendor">
              <ul className="qc-card__list">
                {(result.verification_questions || []).map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </Card>

            <Card title="Things to verify before approving">
              <ul className="qc-card__list">
                {(result.things_to_verify || []).map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </Card>
          </div>

          <div className="qc-footer">
            <div className="qc-footer__disclaimer">{result.disclaimer}</div>

            <div className="qc-footer__meta-row">
              <ModeBadge model={result.metadata?.model} />
              <div className="qc-footer__meta-text">
                request_id: {result.metadata?.request_id} · prompt_version: {result.metadata?.prompt_version}
                {" "}· model: {result.metadata?.model} · latency_ms: {result.metadata?.latency_ms}
              </div>
            </div>

            <details className="qc-json-details">
              <summary>Developer: raw JSON</summary>
              <div className="qc-json-body">
                <button className="qc-btn-quiet" onClick={copyJson} disabled={!result}>
                  {copied ? "Copied!" : "Copy JSON"}
                </button>
                <pre className="qc-json-pre">{prettyJson}</pre>
              </div>
            </details>
          </div>
        </div>
      )}
    </div>
  );
}

function LineItemCard({ item }) {
  const evidence = item.evidence_needed || [];
  const riskColors = getRiskColors(item.risk_level);

  return (
    <div className="qc-line-item" style={{ "--line-item-accent": riskColors.border }}>
      <div className="qc-line-item__head">
        <div className="qc-line-item__name">{item.name_raw}</div>
        <div className="qc-line-item__badges">
          <RiskPill level={item.risk_level} />
          {item.vague_or_confusing && <VagueBadge />}
        </div>
      </div>

      {item.explanation && (
        <div className="qc-line-item__explanation">{item.explanation}</div>
      )}

      {item.rationale_short && (
        <div className="qc-line-item__rationale">
          <span className="qc-line-item__rationale-label">Why this risk level: </span>
          {item.rationale_short}
        </div>
      )}

      {evidence.length > 0 && (
        <div className="qc-line-item__evidence">
          <div className="qc-line-item__evidence-label">Ask the vendor for evidence:</div>
          <ul>
            {evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      <div className="qc-line-item__meta">
        Category: {item.normalized_category} · Action: {item.recommended_action} · Confidence: {typeof item.confidence === "number" ? item.confidence.toFixed(2) : item.confidence}
      </div>
    </div>
  );
}

function Pill({ fg, label }) {
  return (
    <span className="qc-pill" style={{ color: fg }}>
      <span className="qc-pill__dot" />
      {label}
    </span>
  );
}

function getRiskColors(level) {
  const l = String(level || "").toLowerCase();
  const map = {
    red: { border: "var(--risk-red-border)", fg: "var(--risk-red-fg)", label: "High risk" },
    yellow: { border: "var(--risk-yellow-border)", fg: "var(--risk-yellow-fg)", label: "Caution" },
    green: { border: "var(--risk-green-border)", fg: "var(--risk-green-fg)", label: "Low risk" }
  };
  return map[l] || { border: "var(--border)", fg: "var(--ink-3)", label: (l || "unknown").toUpperCase() };
}

function RiskPill({ level }) {
  const c = getRiskColors(level);
  return <Pill fg={c.fg} label={c.label} />;
}

function VagueBadge() {
  return <Pill fg="var(--vague-fg)" label="Needs clarification" />;
}

function ModeBadge({ model }) {
  const isDemo = model === DEMO_ANALYZER_MODEL;
  return <Pill fg="var(--ink-3)" label={isDemo ? "Demo mode" : "OpenAI mode"} />;
}

function Card({ title, children }) {
  return (
    <div className="qc-card">
      <div className="qc-card__title">{title}</div>
      {children}
    </div>
  );
}
