"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ProvenanceTimeline } from "@/components/ProvenanceTimeline";

interface WhyData {
  trace_id: string;
  task: string;
  outcome: string;
  success: boolean;
  total_cost_usd: number;
  total_latency_ms: number;
  started_at: string | null;
  completed_at: string | null;
  provenance_chain: any[];
  hash_chain_valid: boolean;
}

const OUTCOME_STYLES: Record<string, { color: string; bg: string; gradient: string }> = {
  APPROVED: { color: "#4ade80", bg: "#22c55e15", gradient: "linear-gradient(135deg, #22c55e10, #22c55e05)" },
  DENIED: { color: "#f87171", bg: "#ef444415", gradient: "linear-gradient(135deg, #ef444410, #ef444405)" },
  ESCALATED: { color: "#fbbf24", bg: "#f59e0b15", gradient: "linear-gradient(135deg, #f59e0b10, #f59e0b05)" },
};

export default function WhyPage() {
  const params = useParams();
  const traceId = params.traceId as string;
  const [data, setData] = useState<WhyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!traceId) return;

    fetch(`/api/why/${traceId}`)
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return res.json();
      })
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [traceId]);

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "60vh" }}>
        <div style={{ width: "40px", height: "40px", border: "3px solid #333", borderTopColor: "#7c3aed", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <p style={{ color: "#7c3aed", marginTop: "16px", fontSize: "14px" }}>Loading provenance chain...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "24px", background: "#1a0505", border: "1px solid #ef4444", borderRadius: "8px" }}>
        <p style={{ color: "#ef4444" }}>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const style = OUTCOME_STYLES[data.outcome] || { color: "#888", bg: "#88888815", gradient: "none" };
  const steps = data.provenance_chain || [];
  const agents = [...new Set(steps.map((s: any) => s.agent_name))];
  const toolCalls = steps.filter((s: any) => s.event_type === "TOOL_CALL_END").length;

  return (
    <div>
      <div style={{ marginBottom: "8px" }}>
        <Link href="/traces" style={{ fontSize: "12px", color: "#666", display: "flex", alignItems: "center", gap: "4px" }}>
          ← Back to traces
        </Link>
      </div>

      <div style={{
        marginBottom: "32px",
        padding: "24px",
        borderRadius: "12px",
        background: style.gradient,
        border: `1px solid ${style.color}20`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px", flexWrap: "wrap" }}>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#f0f0f0" }}>
            Provenance Explorer
          </h1>
          {data.outcome && (
            <span style={{
              padding: "4px 14px",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: 700,
              background: style.bg,
              color: style.color,
              border: `1px solid ${style.color}30`,
              letterSpacing: "0.5px",
            }}>
              {data.outcome}
            </span>
          )}
          <span style={{
            padding: "4px 12px",
            borderRadius: "6px",
            fontSize: "11px",
            fontWeight: 600,
            background: data.hash_chain_valid ? "#22c55e15" : "#ef444415",
            color: data.hash_chain_valid ? "#22c55e" : "#ef4444",
            border: `1px solid ${data.hash_chain_valid ? "#22c55e30" : "#ef444430"}`,
          }}>
            {data.hash_chain_valid ? "CHAIN INTACT" : "CHAIN BROKEN"}
          </span>
        </div>

        <p style={{ fontSize: "14px", color: "#bbb", marginBottom: "16px" }}>
          {data.task}
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "12px" }}>
          <StatBox label="Steps" value={steps.length.toString()} color="#7c3aed" />
          <StatBox label="Agents" value={agents.length.toString()} color="#3b82f6" />
          <StatBox label="Tool Calls" value={toolCalls.toString()} color="#f97316" />
          <StatBox label="Cost" value={`$${data.total_cost_usd?.toFixed(4)}`} color="#22c55e" />
          <StatBox label="Latency" value={`${data.total_latency_ms}ms`} color="#888" />
        </div>

        <div style={{ marginTop: "12px", display: "flex", gap: "16px", alignItems: "center" }}>
          <code style={{ fontSize: "11px", color: "#555", fontFamily: "monospace" }}>
            {data.trace_id}
          </code>
          <Link
            href={`/audit/${data.trace_id}`}
            style={{
              fontSize: "11px",
              color: "#7c3aed",
              padding: "4px 12px",
              background: "#7c3aed15",
              borderRadius: "4px",
              border: "1px solid #7c3aed30",
            }}
          >
            View Audit Report
          </Link>
        </div>
      </div>

      <ProvenanceTimeline steps={steps} />
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ padding: "10px 12px", background: "#111118", borderRadius: "8px", border: "1px solid #1a1a24" }}>
      <div style={{ fontSize: "10px", color: "#666", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "4px" }}>{label}</div>
      <div style={{ fontSize: "18px", fontWeight: 700, color }}>{value}</div>
    </div>
  );
}
