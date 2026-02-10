/**
 * QuoteCheck Frontend (v0) - App
 *
 * Block 1.5: minimal cross-check that the frontend can talk to the backend.
 * This also helps us catch and fix CORS early before we build /analyze.
 */
import { useState } from "react";

export default function App() {
  const [health, setHealth] = useState(null);
  const [err, setErr] = useState(null);
  const [loading, setLoading] = useState(false);

  async function checkBackend() {
    setLoading(true); setErr(null);
    try {
      const r = await fetch("http://localhost:8000/health");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setHealth(data);
    } catch (e) {
      setErr(String(e?.message || e));
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ fontFamily: "system-ui", padding: 24, maxWidth: 800 }}>
      <h1>QuoteCheck v0</h1>
      <p>Block 1.5: frontend ↔ backend health check.</p>
      <button onClick={checkBackend} disabled={loading}>
        {loading ? "Checking..." : "Check backend /health"}
      </button>

      {health && (
        <pre style={{ 
          marginTop: 16,
           background: "#111827",
           color: "#e5e7eb",
           padding: 12,
           borderRadius: 8,
           overflowX: "auto"
            }}>
          {JSON.stringify(health, null, 2)}
        </pre>
      )}
      {err && (
        <div style={{ marginTop: 16, color: "crimson" }}>
          Error: {err}
          <div style={{ marginTop: 8 }}>
            If this is a CORS error, we’ll add CORS middleware in FastAPI next.
          </div>
        </div>
      )}
    </div>
  );
}
