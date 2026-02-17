/**
 * QuoteCheck Frontend (v0) - App
 *
 * Block 1.5: minimal cross-check that the frontend can talk to the backend.
 * This also helps us catch and fix CORS early before we build /analyze.
 *
 * Block 2: wire the UI to POST /analyze and render the schema-shaped response.
 */

import { useMemo, useState } from "react";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [quoteText, setQuoteText] = useState(
    "Brake pads replacement recommended. Tyre rotation."
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
        Paste a service quote → structured risk flags + questions (schema-first).
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
          <h2 style={{ marginBottom: 8 }}>Line items</h2>
          <div style={{ overflowX: "auto", border: "1px solid #eee", borderRadius: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#0b1220" }}>
                  <th style={th}>Item</th>
                  <th style={th}>Category</th>
                  <th style={th}>Risk</th>
                  <th style={th}>Action</th>
                  <th style={th}>Conf</th>
                  <th style={th}>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {(result.line_items || []).map((it, idx) => (
                  <tr key={idx}>
                    <td style={td}>{it.name_raw}</td>
                    <td style={td}>{it.normalized_category}</td>
                    <td style={td}><RiskPill level={it.risk_level} /></td>
                    <td style={td}>{it.recommended_action}</td>
                    <td style={td}>{typeof it.confidence === "number" ? it.confidence.toFixed(2) : it.confidence}</td>
                    <td style={td}>{it.rationale_short}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 18 }}>
            <Card title="Summary">
              <ul style={{ marginTop: 8 }}>
                {(result.overall_summary || []).map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </Card>

            <Card title="Verification questions">
              <ul style={{ marginTop: 8 }}>
                {(result.verification_questions || []).map((q, i) => <li key={i}>{q}</li>)}
              </ul>
            </Card>

            <Card title="Things to verify">
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

function RiskPill({ level }) {
  const l = String(level || "").toLowerCase();
  const map = {
    red:   { bg: "#7f1d1d", border: "#ef4444", fg: "#fee2e2", label: "RED" },
    yellow:{ bg: "#78350f", border: "#f59e0b", fg: "#fffbeb", label: "YELLOW" },
    green: { bg: "#064e3b", border: "#10b981", fg: "#d1fae5", label: "GREEN" }
  };
  const c = map[l] || { bg: "#111827", border: "#374151", fg: "#e5e7eb", label: (l || "UNKNOWN").toUpperCase() };

  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      borderRadius: 999,
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: 0.4,
      background: c.bg,
      color: c.fg,
      border: `1px solid ${c.border}`
    }}>
      {c.label}
    </span>
  );
}


function Card({ title, children }) {
  return (
    <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 14 }}>
      <div style={{ fontWeight: 700 }}>{title}</div>
      {children}
    </div>
  );
}

const th = { textAlign: "left", padding: "10px 10px", fontSize: 13, borderBottom: "1px solid #1f2937", color: "#e5e7eb" };

const td = { padding: "10px 10px", fontSize: 13, borderBottom: "1px solid #1f2937", verticalAlign: "top" };
