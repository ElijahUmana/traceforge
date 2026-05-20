"use client";

import { useEffect, useState } from "react";
import { CostChart } from "@/components/CostChart";

interface AgentCost {
  agent_name: string;
  cost_usd: number;
  tokens_input: number;
  tokens_output: number;
  avg_latency_ms: number;
}

interface TraceCost {
  trace_id: string;
  task: string | null;
  outcome: string | null;
  total_cost_usd: number;
  total_latency_ms: number;
  started_at: string | null;
}

interface CostData {
  tenant_id: string;
  total_traces: number;
  total_cost_usd: number;
  avg_cost_per_trace: number;
  cost_by_agent: AgentCost[];
  cost_by_tool: Array<{ tool_name: string; call_count: number; total_duration_ms: number }>;
  traces: TraceCost[];
}

export default function CostPage() {
  const [data, setData] = useState<CostData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/cost?tenant_id=tenant_demo")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "80px" }}>
        <p style={{ color: "#7c3aed" }}>Loading cost data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "16px", background: "#1a0505", border: "1px solid #ef4444", borderRadius: "8px" }}>
        <p style={{ color: "#ef4444" }}>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div>
      <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#f0f0f0", marginBottom: "8px" }}>
        Cost Attribution Dashboard
      </h1>
      <p style={{ color: "#888", fontSize: "14px", marginBottom: "32px" }}>
        Tenant: <code style={{ color: "#7c3aed" }}>{data.tenant_id}</code>
      </p>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", marginBottom: "32px" }}>
        <SummaryCard label="Total Cost" value={`$${data.total_cost_usd.toFixed(4)}`} />
        <SummaryCard label="Total Traces" value={data.total_traces.toString()} />
        <SummaryCard label="Avg Cost / Trace" value={`$${data.avg_cost_per_trace.toFixed(4)}`} />
        <SummaryCard label="Agents" value={data.cost_by_agent.length.toString()} />
      </div>

      {/* Chart: Cost by Agent */}
      <div style={{ background: "#111118", borderRadius: "12px", padding: "24px", border: "1px solid #222", marginBottom: "32px" }}>
        <h2 style={{ fontSize: "16px", fontWeight: 600, color: "#e0e0e0", marginBottom: "16px" }}>
          Cost by Agent
        </h2>
        <CostChart data={data.cost_by_agent} />
      </div>

      {/* Table: Cost by Tool */}
      {data.cost_by_tool.length > 0 && (
        <div style={{ background: "#111118", borderRadius: "12px", padding: "24px", border: "1px solid #222", marginBottom: "32px" }}>
          <h2 style={{ fontSize: "16px", fontWeight: 600, color: "#e0e0e0", marginBottom: "16px" }}>
            Tool Usage
          </h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #222" }}>
                <th style={thStyle}>Tool</th>
                <th style={thStyle}>Calls</th>
                <th style={thStyle}>Total Duration</th>
              </tr>
            </thead>
            <tbody>
              {data.cost_by_tool.map((tool) => (
                <tr key={tool.tool_name} style={{ borderBottom: "1px solid #1a1a24" }}>
                  <td style={tdStyle}>
                    <code style={{ fontSize: "12px" }}>{tool.tool_name}</code>
                  </td>
                  <td style={tdStyle}>{tool.call_count}</td>
                  <td style={tdStyle}>{tool.total_duration_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Table: Cost per Trace */}
      {data.traces.length > 0 && (
        <div style={{ background: "#111118", borderRadius: "12px", padding: "24px", border: "1px solid #222" }}>
          <h2 style={{ fontSize: "16px", fontWeight: 600, color: "#e0e0e0", marginBottom: "16px" }}>
            Cost per Trace
          </h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #222" }}>
                <th style={thStyle}>Trace</th>
                <th style={thStyle}>Task</th>
                <th style={thStyle}>Outcome</th>
                <th style={thStyle}>Cost</th>
                <th style={thStyle}>Latency</th>
              </tr>
            </thead>
            <tbody>
              {data.traces.map((trace) => (
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
                    <span style={{ fontSize: "11px", color: trace.outcome === "APPROVED" ? "#22c55e" : trace.outcome === "DENIED" ? "#ef4444" : "#f59e0b" }}>
                      {trace.outcome || "-"}
                    </span>
                  </td>
                  <td style={tdStyle}>${trace.total_cost_usd.toFixed(4)}</td>
                  <td style={tdStyle}>{trace.total_latency_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#111118", borderRadius: "8px", padding: "20px", border: "1px solid #222" }}>
      <div style={{ fontSize: "11px", color: "#888", textTransform: "uppercase", marginBottom: "8px" }}>
        {label}
      </div>
      <div style={{ fontSize: "22px", fontWeight: 700, color: "#e0e0e0" }}>
        {value}
      </div>
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
