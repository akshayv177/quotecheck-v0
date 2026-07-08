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
    <div style={{ padding: "32px 24px", maxWidth: 860, margin: "0 auto" }}>
      <header style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <h1 style={{ margin: 0, fontWeight: 700, color: "var(--ink)" }}>QuoteCheck</h1>
          <span style={{
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: 0.3,
            padding: "2px 8px",
            borderRadius: 999,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            color: "var(--ink-3)"
          }}>
            v0 prototype
          </span>
        </div>
        <div style={{ color: "var(--ink-2)", fontSize: 15, lineHeight: 1.5 }}>
          Paste a service or repair quote. QuoteCheck explains every line item, flags
          what's vague or risky, and gives you questions to send back — before you approve.
        </div>
      </header>

      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: 20,
        boxShadow: "0 1px 2px rgba(0,0,0,.05)"
      }}>
        <label style={{ display: "block", marginBottom: 8, fontWeight: 600, color: "var(--ink)" }}>
          Your quote
        </label>
        <textarea
          value={quoteText}
          onChange={(e) => setQuoteText(e.target.value)}
          rows={8}
          style={{
            width: "100%",
            padding: 12,
            borderRadius: 10,
            border: "1px solid var(--border)",
            fontFamily: "inherit",
            fontSize: 14,
            color: "var(--ink)",
            boxSizing: "border-box"
          }}
          placeholder="Paste the quote text exactly as you received it…"
        />
        <div style={{ marginTop: 6, fontSize: 12, color: "var(--ink-3)" }}>
          Works with service, repair, and parts quotes. Text only for now.
        </div>

        <div style={{ marginTop: 14 }}>
          <button
            onClick={analyzeQuote}
            disabled={loading || quoteText.trim().length === 0}
            aria-busy={loading}
            style={{
              padding: "10px 18px",
              borderRadius: 10,
              border: "1px solid var(--accent)",
              background: "var(--accent)",
              color: "#fff",
              fontWeight: 600,
              cursor: "pointer"
            }}
          >
            {loading ? "Analyzing…" : "Analyze quote"}
          </button>
        </div>

        {loading && (
          <div style={{ marginTop: 14 }}>
            <div className="status-pulse" />
            <div
              role="status"
              aria-live="polite"
              style={{
                marginTop: 6,
                fontSize: 13,
                color: "var(--ink-3)",
                display: "flex",
                justifyContent: "space-between",
                gap: 12
              }}
            >
              <span>{STAGES[stageForElapsed(elapsedMs)].label}</span>
              <span>{formatElapsed(elapsedMs)}</span>
            </div>
            {elapsedMs > SLOW_HINT_MS && (
              <div style={{ marginTop: 4, fontSize: 12, color: "var(--ink-3)" }}>
                Still working — complex quotes can take a little longer.
              </div>
            )}
          </div>
        )}
      </div>

      {err && (
        <div style={{
          marginTop: 16,
          background: "var(--error-bg)",
          color: "var(--error-fg)",
          border: "1px solid var(--error-border)",
          borderLeft: "3px solid var(--error-border)",
          borderRadius: 10,
          padding: "12px 16px",
          fontSize: 14
        }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Couldn't analyze this quote.</div>
          <div style={{ opacity: 0.9 }}>{err.message}</div>
          {(err.kind === "http" || err.kind === "other") && (
            <div style={{ marginTop: 8, fontSize: 13, opacity: 0.8 }}>
              Check that the backend is running on port 8000.
            </div>
          )}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 32 }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            <h2 style={{ margin: 0, fontSize: 18, color: "var(--ink)" }}>Report</h2>
            <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
              {riskCounts.total} item{riskCounts.total === 1 ? "" : "s"}
              {riskCounts.red > 0 && <> · <span style={{ color: "var(--risk-red-fg)", fontWeight: 600 }}>{riskCounts.red} high risk</span></>}
              {riskCounts.yellow > 0 && <> · <span style={{ color: "var(--risk-yellow-fg)", fontWeight: 600 }}>{riskCounts.yellow} caution</span></>}
              {riskCounts.vague > 0 && <> · <span style={{ color: "var(--vague-fg)", fontWeight: 600 }}>{riskCounts.vague} needs clarification</span></>}
            </div>
          </div>

          <Card title="Summary">
            <ul style={{ marginTop: 8, paddingLeft: 20, color: "var(--ink)" }}>
              {(result.overall_summary || []).map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{s}</li>)}
            </ul>
          </Card>

          <h3 style={{ marginTop: 28, marginBottom: 12, fontSize: 15, color: "var(--ink)" }}>
            Line items, explained
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {(result.line_items || []).map((it, idx) => (
              <LineItemCard key={idx} item={it} />
            ))}
          </div>

          <h3 style={{ marginTop: 28, marginBottom: 12, fontSize: 15, color: "var(--ink)" }}>
            Before you approve
          </h3>
          <div className="two-col-grid">
            <Card title="Questions to ask the vendor">
              <ul style={{ marginTop: 8, paddingLeft: 20, color: "var(--ink)" }}>
                {(result.verification_questions || []).map((q, i) => <li key={i} style={{ marginBottom: 4 }}>{q}</li>)}
              </ul>
            </Card>

            <Card title="Things to verify before approving">
              <ul style={{ marginTop: 8, paddingLeft: 20, color: "var(--ink)" }}>
                {(result.things_to_verify || []).map((t, i) => <li key={i} style={{ marginBottom: 4 }}>{t}</li>)}
              </ul>
            </Card>
          </div>

          <div style={{
            marginTop: 28,
            paddingTop: 16,
            borderTop: "1px solid var(--border)"
          }}>
            <div style={{ fontSize: 13, color: "var(--ink-2)", fontStyle: "italic" }}>
              {result.disclaimer}
            </div>

            <div style={{
              marginTop: 10,
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 8
            }}>
              <ModeBadge model={result.metadata?.model} />
              <div style={{
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                fontSize: 12,
                color: "var(--ink-3)"
              }}>
                request_id: {result.metadata?.request_id} · prompt_version: {result.metadata?.prompt_version}
                {" "}· model: {result.metadata?.model} · latency_ms: {result.metadata?.latency_ms}
              </div>
            </div>

            <details style={{ marginTop: 14 }}>
              <summary>Developer: raw JSON</summary>
              <div style={{ marginTop: 10 }}>
                <button
                  onClick={copyJson}
                  disabled={!result}
                  style={{ padding: "6px 12px", fontSize: 13, borderRadius: 8 }}
                >
                  {copied ? "Copied!" : "Copy JSON"}
                </button>
                <pre style={{
                  marginTop: 10,
                  background: "#111827",
                  color: "#e5e7eb",
                  padding: 12,
                  borderRadius: 10,
                  overflowX: "auto",
                  fontSize: 12
                }}>
                  {prettyJson}
                </pre>
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
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderLeft: `3px solid ${riskColors.border}`,
      borderRadius: 12,
      padding: 16,
      boxShadow: "0 1px 2px rgba(0,0,0,.05)"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 700, fontSize: 16, color: "var(--ink)" }}>{item.name_raw}</div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <RiskPill level={item.risk_level} />
          {item.vague_or_confusing && <VagueBadge />}
        </div>
      </div>

      {item.explanation && (
        <div style={{ marginTop: 10, fontSize: 15, lineHeight: 1.6, color: "var(--ink)" }}>
          {item.explanation}
        </div>
      )}

      {item.rationale_short && (
        <div style={{ marginTop: 8, fontSize: 13, color: "var(--ink-2)" }}>
          <span style={{ fontWeight: 600 }}>Why this risk level: </span>
          {item.rationale_short}
        </div>
      )}

      {evidence.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 13, color: "var(--ink-2)" }}>
          <div style={{ fontWeight: 600 }}>Ask the vendor for evidence:</div>
          <ul style={{ margin: "4px 0 0 0", paddingLeft: 18 }}>
            {evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      <div style={{ marginTop: 10, fontSize: 12, color: "var(--ink-3)" }}>
        Category: {item.normalized_category} · Action: {item.recommended_action} · Confidence: {typeof item.confidence === "number" ? item.confidence.toFixed(2) : item.confidence}
      </div>
    </div>
  );
}

function Pill({ bg, border, fg, label }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      borderRadius: 999,
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: 0.3,
      textTransform: "uppercase",
      background: bg,
      color: fg,
      border: `1px solid ${border}`
    }}>
      {label}
    </span>
  );
}

function getRiskColors(level) {
  const l = String(level || "").toLowerCase();
  const map = {
    red: { bg: "var(--risk-red-bg)", border: "var(--risk-red-border)", fg: "var(--risk-red-fg)", label: "High risk" },
    yellow: { bg: "var(--risk-yellow-bg)", border: "var(--risk-yellow-border)", fg: "var(--risk-yellow-fg)", label: "Caution" },
    green: { bg: "var(--risk-green-bg)", border: "var(--risk-green-border)", fg: "var(--risk-green-fg)", label: "Low risk" }
  };
  return map[l] || { bg: "var(--surface)", border: "var(--border)", fg: "var(--ink-3)", label: (l || "unknown").toUpperCase() };
}

function RiskPill({ level }) {
  const c = getRiskColors(level);
  return <Pill bg={c.bg} border={c.border} fg={c.fg} label={c.label} />;
}

function VagueBadge() {
  return <Pill bg="var(--vague-bg)" border="var(--vague-border)" fg="var(--vague-fg)" label="Needs clarification" />;
}

function ModeBadge({ model }) {
  const isDemo = model === DEMO_ANALYZER_MODEL;
  return (
    <Pill
      bg="var(--surface)"
      border="var(--border)"
      fg="var(--ink-3)"
      label={isDemo ? "Demo mode" : "OpenAI mode"}
    />
  );
}

function Card({ title, children }) {
  return (
    <div style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      padding: 16,
      boxShadow: "0 1px 2px rgba(0,0,0,.05)"
    }}>
      <div style={{ fontWeight: 700, fontSize: 14, color: "var(--ink)" }}>{title}</div>
      {children}
    </div>
  );
}
