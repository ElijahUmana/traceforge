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

const OUTCOME_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  APPROVED: { color: "#4ade80", bg: "#22c55e15", border: "#22c55e30" },
  DENIED: { color: "#f87171", bg: "#ef444415", border: "#ef444430" },
  ESCALATED: { color: "#fbbf24", bg: "#f59e0b15", border: "#f59e0b30" },
};

export function TraceCard({ trace }: Props) {
  const style = OUTCOME_STYLES[trace.outcome || ""] || { color: "#888", bg: "#88888815", border: "#88888830" };

  const companyMatch = trace.task?.match(/for (.+?)(?:\s+requesting|\s*$)/);
  const company = companyMatch ? companyMatch[1] : trace.task || "Unknown";
  const amountMatch = trace.task?.match(/\$([0-9,.]+[MBK]?)/);
  const amount = amountMatch ? `$${amountMatch[1]}` : "";

  return (
    <Link href={`/why/${trace.trace_id}`} style={{ display: "block" }}>
      <div
        style={{
          background: "#111118",
          borderRadius: "10px",
          padding: "20px",
          border: "1px solid #1a1a24",
          transition: "all 0.2s ease",
          cursor: "pointer",
          position: "relative",
          overflow: "hidden",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = style.border;
          e.currentTarget.style.boxShadow = `0 0 20px ${style.bg}`;
          e.currentTarget.style.transform = "translateY(-1px)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "#1a1a24";
          e.currentTarget.style.boxShadow = "none";
          e.currentTarget.style.transform = "translateY(0)";
        }}
      >
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: "3px", background: style.color, borderRadius: "10px 0 0 10px" }} />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
          <div style={{ flex: 1, paddingRight: "16px" }}>
            <p style={{ fontSize: "15px", color: "#e0e0e0", fontWeight: 600, marginBottom: "4px" }}>
              {company}
            </p>
            {amount && (
              <span style={{ fontSize: "13px", color: "#888" }}>{amount}</span>
            )}
          </div>
          {trace.outcome && (
            <span style={{
              fontSize: "11px",
              fontWeight: 700,
              padding: "4px 12px",
              borderRadius: "6px",
              background: style.bg,
              color: style.color,
              border: `1px solid ${style.border}`,
              letterSpacing: "0.5px",
            }}>
              {trace.outcome}
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: "20px", fontSize: "12px", color: "#666", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ color: "#22c55e" }}>$</span>
            <span>{trace.total_cost_usd.toFixed(4)}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ color: "#3b82f6" }}>{trace.agent_count}</span>
            <span>agents</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ color: "#f97316" }}>{trace.step_count}</span>
            <span>steps</span>
          </div>
          <div style={{ flex: 1 }} />
          <code style={{ fontSize: "10px", color: "#444", fontFamily: "monospace" }}>
            {trace.trace_id}
          </code>
          {trace.started_at && (
            <span style={{ fontSize: "10px", color: "#555" }}>
              {new Date(trace.started_at).toLocaleString()}
            </span>
          )}
          <span style={{ color: "#7c3aed", fontSize: "16px" }}>→</span>
        </div>
      </div>
    </Link>
  );
}
