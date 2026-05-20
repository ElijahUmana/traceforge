"use client";

import { useState } from "react";
import Link from "next/link";

interface EvaluateResult {
  trace_id: string;
  outcome: string;
  decision: string;
  company_name: string;
  requested_amount: number;
  risk_score: number | null;
  risk_category: string | null;
  reasoning: string;
  total_cost_usd: number;
  total_latency_ms: number;
  agent_count: number;
  step_count: number;
}

export default function HomePage() {
  const [companyName, setCompanyName] = useState("Meridian Manufacturing Corp");
  const [amount, setAmount] = useState("10000000");
  const [applicationType, setApplicationType] = useState("CORPORATE_CREDIT");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EvaluateResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: companyName,
          requested_amount: parseFloat(amount),
          tenant_id: "tenant_demo",
          application_id: "",
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const data: EvaluateResult = await res.json();
      setResult(data);

      if (data.decision === "PROCESSING") {
        const traceId = data.trace_id;
        const poll = setInterval(async () => {
          try {
            const r = await fetch(`/api/why/${traceId}`);
            if (!r.ok) return;
            const why = await r.json();
            if (why.outcome && why.outcome !== "PROCESSING" && why.outcome !== "null") {
              clearInterval(poll);
              setResult({
                ...data,
                outcome: why.outcome,
                decision: why.outcome,
                total_cost_usd: why.total_cost_usd || 0,
                total_latency_ms: why.total_latency_ms || 0,
                step_count: why.provenance_chain?.length || 0,
                reasoning: `Decision: ${why.outcome}. ${why.provenance_chain?.length || 0} provenance steps captured.`,
              });
              setLoading(false);
            }
          } catch {}
        }, 3000);
        setTimeout(() => clearInterval(poll), 180000);
        return;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  const decisionColor =
    result?.decision === "APPROVED"
      ? "#22c55e"
      : result?.decision === "DENIED"
        ? "#ef4444"
        : "#f59e0b";

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px" }}>
      {/* Left: Form */}
      <div>
        <h1
          style={{
            fontSize: "28px",
            fontWeight: 700,
            marginBottom: "8px",
            color: "#f0f0f0",
          }}
        >
          Evaluate Credit Application
        </h1>
        <p style={{ color: "#888", marginBottom: "24px", fontSize: "14px" }}>
          Submit an application to the 3-agent credit decision swarm. The full
          reasoning chain is captured as a queryable provenance graph.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label style={labelStyle}>Company Name</label>
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              style={inputStyle}
              placeholder="e.g. Meridian Manufacturing Corp"
            />
          </div>

          <div>
            <label style={labelStyle}>Requested Amount (USD)</label>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              style={inputStyle}
              placeholder="e.g. 10000000"
            />
          </div>

          <div>
            <label style={labelStyle}>Application Type</label>
            <select
              value={applicationType}
              onChange={(e) => setApplicationType(e.target.value)}
              style={inputStyle}
            >
              <option value="CORPORATE_CREDIT">Corporate Credit</option>
              <option value="TRADE_FINANCE">Trade Finance</option>
              <option value="BOND_ISSUANCE">Bond Issuance</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: "12px 24px",
              background: loading ? "#333" : "#7c3aed",
              color: "#fff",
              border: "none",
              borderRadius: "8px",
              fontSize: "15px",
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              marginTop: "8px",
              transition: "background 0.2s",
            }}
          >
            {loading ? "Evaluating..." : "Submit Evaluation"}
          </button>
        </form>

        <div style={{ marginTop: "32px", padding: "16px", background: "#111118", borderRadius: "8px" }}>
          <h3 style={{ fontSize: "13px", color: "#888", marginBottom: "12px", textTransform: "uppercase", letterSpacing: "1px" }}>
            Demo Scenarios
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <button
              onClick={() => { setCompanyName("Meridian Manufacturing Corp"); setAmount("10000000"); }}
              style={scenarioBtn}
            >
              Meridian Manufacturing ($10M) — Expected: APPROVE
            </button>
            <button
              onClick={() => { setCompanyName("Zenith Biotech Inc"); setAmount("25000000"); }}
              style={scenarioBtn}
            >
              Zenith Biotech ($25M) — Poisoned data: WRONGFUL APPROVE
            </button>
            <button
              onClick={() => { setCompanyName("Atlas Logistics Group"); setAmount("50000000"); }}
              style={scenarioBtn}
            >
              Atlas Logistics ($50M) — Edge case: ESCALATE
            </button>
          </div>
        </div>
      </div>

      {/* Right: Result */}
      <div>
        {error && (
          <div
            style={{
              padding: "16px",
              background: "#1a0505",
              border: "1px solid #ef4444",
              borderRadius: "8px",
              color: "#ef4444",
            }}
          >
            {error}
          </div>
        )}

        {result && (
          <div
            style={{
              background: "#111118",
              borderRadius: "12px",
              padding: "24px",
              border: "1px solid #222",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <h2 style={{ fontSize: "22px", fontWeight: 700, color: "#f0f0f0" }}>
                Decision Result
              </h2>
              <span
                style={{
                  padding: "6px 16px",
                  borderRadius: "20px",
                  fontSize: "13px",
                  fontWeight: 700,
                  background: `${decisionColor}20`,
                  color: decisionColor,
                  border: `1px solid ${decisionColor}40`,
                }}
              >
                {result.decision}
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>
              <MetricCard label="Company" value={result.company_name} />
              <MetricCard label="Amount" value={`$${result.requested_amount.toLocaleString()}`} />
              <MetricCard label="Risk Score" value={result.risk_score?.toString() ?? "N/A"} />
              <MetricCard label="Risk Category" value={result.risk_category ?? "N/A"} />
              <MetricCard label="Total Cost" value={`$${result.total_cost_usd.toFixed(4)}`} />
              <MetricCard label="Latency" value={`${result.total_latency_ms}ms`} />
              <MetricCard label="Agents" value={result.agent_count.toString()} />
              <MetricCard label="Steps" value={result.step_count.toString()} />
            </div>

            <div style={{ marginBottom: "16px" }}>
              <span style={{ fontSize: "12px", color: "#888", textTransform: "uppercase" }}>
                Reasoning
              </span>
              <p style={{ fontSize: "14px", color: "#ccc", marginTop: "4px", lineHeight: 1.5 }}>
                {result.reasoning}
              </p>
            </div>

            <div style={{ display: "flex", gap: "12px" }}>
              <Link
                href={`/why/${result.trace_id}`}
                style={{
                  padding: "10px 20px",
                  background: "#7c3aed",
                  color: "#fff",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: 600,
                }}
              >
                View Provenance Chain
              </Link>
              <span style={{ padding: "10px 20px", background: "#1a1a24", borderRadius: "6px", fontSize: "12px", color: "#888", fontFamily: "monospace" }}>
                {result.trace_id}
              </span>
            </div>
          </div>
        )}

        {!result && !error && !loading && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "400px",
              background: "#111118",
              borderRadius: "12px",
              border: "1px dashed #333",
            }}
          >
            <p style={{ color: "#555", fontSize: "14px" }}>
              Submit an evaluation to see the decision result and provenance trace.
            </p>
          </div>
        )}

        {loading && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "400px",
              background: "#111118",
              borderRadius: "12px",
              border: "1px solid #7c3aed40",
            }}
          >
            <div style={{ width: "40px", height: "40px", border: "3px solid #333", borderTopColor: "#7c3aed", borderRadius: "50%", animation: "spin 1s linear infinite", marginBottom: "16px" }} />
            <p style={{ color: "#7c3aed", fontSize: "14px", fontWeight: 600 }}>
              Swarm running live...
            </p>
            <p style={{ color: "#666", fontSize: "12px", marginTop: "8px" }}>
              Researcher → Analyst → Writer
            </p>
            <p style={{ color: "#555", fontSize: "11px", marginTop: "4px" }}>
              10 tools, 3 agents, provenance writing to Neo4j in real time
            </p>
            {result?.trace_id && (
              <a
                href={`/why/${result.trace_id}`}
                style={{ color: "#7c3aed", fontSize: "12px", marginTop: "12px" }}
              >
                Watch live: {result.trace_id}
              </a>
            )}
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "12px", background: "#0d0d14", borderRadius: "8px", border: "1px solid #1a1a24" }}>
      <div style={{ fontSize: "11px", color: "#888", textTransform: "uppercase", marginBottom: "4px" }}>
        {label}
      </div>
      <div style={{ fontSize: "15px", fontWeight: 600, color: "#e0e0e0" }}>
        {value}
      </div>
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "13px",
  color: "#aaa",
  marginBottom: "6px",
  fontWeight: 500,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  background: "#111118",
  border: "1px solid #333",
  borderRadius: "8px",
  color: "#e0e0e0",
  fontSize: "14px",
  outline: "none",
};

const scenarioBtn: React.CSSProperties = {
  padding: "8px 12px",
  background: "transparent",
  border: "1px solid #333",
  borderRadius: "6px",
  color: "#aaa",
  fontSize: "12px",
  cursor: "pointer",
  textAlign: "left",
};
