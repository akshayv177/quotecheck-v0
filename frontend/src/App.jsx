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
 */

import { useMemo, useState } from "react";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [quoteText, setQuoteText] = useState(
    "Brake pads replacement recommended. Tyre rotation. Shop supplies / misc service charge included."
  );
  const [result, setResult] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);


  const prettyJson = useMemo(() => (result ? JSON.stringify(result, null, 2) : ""), [result]);

  async function analyzeQuote() {
    setLoading(true); setErr(null);
    try {
      const r = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quote_text: quoteText }) // backend expects quote_text
      });
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`HTTP ${r.status}: ${text}`);
      }
      const data = await r.json();
      setResult(data);
    } catch (e) {
      setErr(String(e?.message || e));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  async function copyJson() {
  if (!prettyJson) return;
  await navigator.clipboard.writeText(prettyJson);
  setCopied(true);
  setTimeout(() => setCopied(false), 1200);
}

  return (
    <div style={{ fontFamily: "system-ui", padding: 24, maxWidth: 1000, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 6 }}>QuoteCheck v0</h1>
      <div style={{ opacity: 0.8, marginBottom: 16 }}>
        Paste a service quote → understand each item first, then verify what's vague, risky, or confusing.
      </div>

      <label style={{ display: "block", marginBottom: 8, fontWeight: 600 }}>
        Quote text
      </label>
      <textarea
        value={quoteText}
        onChange={(e) => setQuoteText(e.target.value)}
        rows={8}
        style={{ width: "100%", padding: 12, borderRadius: 10, border: "1px solid #ddd" }}
        placeholder="Paste quote text here..."
      />

      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <button
          onClick={analyzeQuote}
          disabled={loading || quoteText.trim().length === 0}
          style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #ddd", cursor: "pointer" }}
        >
          {loading ? "Analyzing..." : "Analyze"}
        </button>

        <button
          onClick={copyJson}
          disabled={!result}
          style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #ddd", cursor: "pointer" }}
        >
          {copied ? "Copied!" : "Copy result as JSON"}
        </button>
      </div>

      {err && (
        <div style={{ marginTop: 16, color: "crimson" }}>
          Error: {err}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 24 }}>
          <Card title="Summary">
            <ul style={{ marginTop: 8 }}>
              {(result.overall_summary || []).map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </Card>

          <h2 style={{ marginTop: 22, marginBottom: 8 }}>Line items</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {(result.line_items || []).map((it, idx) => (
              <LineItemCard key={idx} item={it} />
            ))}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 18 }}>
            <Card title="Questions to ask the vendor">
              <ul style={{ marginTop: 8 }}>
                {(result.verification_questions || []).map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </Card>

            <Card title="Things to verify before approving">
              <ul style={{ marginTop: 8 }}>
                {(result.things_to_verify || []).map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </Card>

            <Card title="Run metadata">
              <div style={{ marginTop: 8, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 13 }}>
                <div>request_id: {result.metadata?.request_id}</div>
                <div>prompt_version: {result.metadata?.prompt_version}</div>
                <div>model: {result.metadata?.model}</div>
                <div>latency_ms: {result.metadata?.latency_ms}</div>
              </div>
              <div style={{ marginTop: 10, opacity: 0.8, fontSize: 13 }}>
                {result.disclaimer}
              </div>
            </Card>
          </div>

          <h2 style={{ marginTop: 22, marginBottom: 8 }}>Raw JSON</h2>
          <pre style={{
            background: "#111827",
            color: "#e5e7eb",
            padding: 12,
            borderRadius: 12,
            overflowX: "auto",
            fontSize: 13
          }}>
            {prettyJson}
          </pre>
        </div>
      )}
    </div>
  );
}

function LineItemCard({ item }) {
  const evidence = item.evidence_needed || [];

  return (
    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{item.name_raw}</div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <RiskPill level={item.risk_level} />
          {item.vague_or_confusing && <VagueBadge />}
        </div>
      </div>

      {item.explanation && (
        <div style={{ marginTop: 10, fontSize: 15, lineHeight: 1.5 }}>
          {item.explanation}
        </div>
      )}

      {item.rationale_short && (
        <div style={{ marginTop: 8, fontSize: 13, opacity: 0.75 }}>
          <span style={{ fontWeight: 600 }}>Risk reasoning: </span>
          {item.rationale_short}
        </div>
      )}

      <div style={{ marginTop: 10, fontSize: 12, opacity: 0.7 }}>
        Category: {item.normalized_category} · Action: {item.recommended_action} · Confidence: {typeof item.confidence === "number" ? item.confidence.toFixed(2) : item.confidence}
      </div>

      {evidence.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 12, opacity: 0.75 }}>
          <div style={{ fontWeight: 600 }}>Evidence to ask for:</div>
          <ul style={{ margin: "4px 0 0 0", paddingLeft: 18 }}>
            {evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function Pill({ bg, border, fg, label }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: 0.4,
      background: bg,
      color: fg,
      border: `1px solid ${border}`
    }}>
      {label}
    </span>
  );
}

function RiskPill({ level }) {
  const l = String(level || "").toLowerCase();
  const map = {
    red:   { bg: "#7f1d1d", border: "#ef4444", fg: "#fee2e2", label: "RED" },
    yellow:{ bg: "#78350f", border: "#f59e0b", fg: "#fffbeb", label: "YELLOW" },
    green: { bg: "#064e3b", border: "#10b981", fg: "#d1fae5", label: "GREEN" }
  };
  const c = map[l] || { bg: "#111827", border: "#374151", fg: "#e5e7eb", label: (l || "UNKNOWN").toUpperCase() };

  return <Pill bg={c.bg} border={c.border} fg={c.fg} label={c.label} />;
}

function VagueBadge() {
  return <Pill bg="#4c1d95" border="#a78bfa" fg="#ede9fe" label="NEEDS CLARIFICATION" />;
}

function Card({ title, children }) {
  return (
    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 14 }}>
      <div style={{ fontWeight: 700 }}>{title}</div>
      {children}
    </div>
  );
}
