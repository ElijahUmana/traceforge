"use client";

import Link from "next/link";

interface TraceData {
  trace_id: string;
  task: string | null;
  outcome: string | null;
  total_cost_usd: number;
  total_latency_ms: number;
  agent_count: number;
  step_count: number;
  started_at: string | null;
  tenant_id: string | null;
  success: boolean | null;
}

interface Props {
  trace: TraceData;
}

export function TraceCard({ trace }: Props) {
  const outcomeColor =
    trace.outcome === "APPROVED"
      ? "#22c55e"
      : trace.outcome === "DENIED"
        ? "#ef4444"
        : trace.outcome === "ESCALATED"
          ? "#f59e0b"
          : "#888";

  return (
    <Link href={`/why/${trace.trace_id}`} style={{ display: "block" }}>
      <div
        style={{
          background: "#111118",
          borderRadius: "8px",
          padding: "16px",
          border: "1px solid #222",
          transition: "border-color 0.2s",
          cursor: "pointer",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#7c3aed40")}
        onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#222")}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: "13px", color: "#ddd", fontWeight: 500, marginBottom: "4px" }}>
              {trace.task || "Unknown task"}
            </p>
            <code style={{ fontSize: "11px", color: "#555", fontFamily: "monospace" }}>
              {trace.trace_id}
            </code>
          </div>
          {trace.outcome && (
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                padding: "3px 10px",
                borderRadius: "12px",
                background: `${outcomeColor}15`,
                color: outcomeColor,
                border: `1px solid ${outcomeColor}30`,
                whiteSpace: "nowrap",
              }}
            >
              {trace.outcome}
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: "16px", fontSize: "11px", color: "#666" }}>
          <span>${trace.total_cost_usd.toFixed(4)}</span>
          <span>{trace.agent_count} agents</span>
          <span>{trace.step_count} steps</span>
          <span>{trace.total_latency_ms}ms</span>
          {trace.started_at && (
            <span>{new Date(trace.started_at).toLocaleString()}</span>
          )}
        </div>
      </div>
    </Link>
  );
}
