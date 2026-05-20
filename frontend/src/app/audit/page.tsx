"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Trace {
  trace_id: string;
  task: string | null;
  outcome: string | null;
  total_cost_usd: number;
  total_latency_ms: number;
  started_at: string | null;
}

export default function AuditIndexPage() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/traces")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setTraces(data.traces || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const outcomeColor = (outcome: string | null) =>
    outcome === "APPROVED" ? "#22c55e" : outcome === "DENIED" ? "#ef4444" : "#f59e0b";

  return (
    <div>
      <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#f0f0f0", marginBottom: "8px" }}>
        EU AI Act Article 12 Audit Reports
      </h1>
      <p style={{ color: "#888", fontSize: "14px", marginBottom: "32px" }}>
        Generate compliance audit reports for any reasoning trace.
      </p>

      {error && (
        <div style={{ padding: "16px", background: "#1a0505", border: "1px solid #ef4444", borderRadius: "8px", marginBottom: "16px" }}>
          <p style={{ color: "#ef4444" }}>{error}</p>
        </div>
      )}

      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: "60px" }}>
          <p style={{ color: "#7c3aed" }}>Loading traces...</p>
        </div>
      )}

      {!loading && traces.length === 0 && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "300px",
            background: "#111118",
            borderRadius: "12px",
            border: "1px dashed #333",
          }}
        >
          <p style={{ color: "#555", fontSize: "14px" }}>
            No traces yet. Run an evaluation to create the first trace.
          </p>
        </div>
      )}

      {!loading && traces.length > 0 && (
        <div style={{ background: "#111118", borderRadius: "12px", padding: "24px", border: "1px solid #222" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #222" }}>
                <th style={thStyle}>Trace</th>
                <th style={thStyle}>Task</th>
                <th style={thStyle}>Outcome</th>
                <th style={thStyle}>Cost</th>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Action</th>
              </tr>
            </thead>
            <tbody>
              {traces.map((trace) => (
                <tr key={trace.trace_id} style={{ borderBottom: "1px solid #1a1a24" }}>
                  <td style={tdStyle}>
                    <code style={{ fontSize: "11px", color: "#666" }}>{trace.trace_id}</code>
                  </td>
                  <td style={tdStyle}>
                    <span style={{ fontSize: "12px", color: "#bbb" }}>
                      {trace.task ? (trace.task.length > 50 ? trace.task.slice(0, 50) + "..." : trace.task) : "-"}
                    </span>
                  </td>
                  <td style={tdStyle}>
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        padding: "3px 10px",
                        borderRadius: "12px",
                        background: `${outcomeColor(trace.outcome)}15`,
                        color: outcomeColor(trace.outcome),
                        border: `1px solid ${outcomeColor(trace.outcome)}30`,
                      }}
                    >
                      {trace.outcome || "-"}
                    </span>
                  </td>
                  <td style={tdStyle}>${trace.total_cost_usd.toFixed(4)}</td>
                  <td style={tdStyle}>
                    {trace.started_at ? new Date(trace.started_at).toLocaleString() : "-"}
                  </td>
                  <td style={tdStyle}>
                    <Link
                      href={`/audit/${trace.trace_id}`}
                      style={{
                        padding: "6px 14px",
                        background: "#7c3aed",
                        color: "#fff",
                        borderRadius: "4px",
                        fontSize: "12px",
                        fontWeight: 600,
                        whiteSpace: "nowrap",
                      }}
                    >
                      Generate Report
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  fontSize: "11px",
  color: "#888",
  textTransform: "uppercase",
  fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  fontSize: "13px",
  color: "#ccc",
};
