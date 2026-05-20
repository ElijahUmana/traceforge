"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
      <div style={{ display: "flex", justifyContent: "center", padding: "80px" }}>
        <p style={{ color: "#7c3aed" }}>Loading provenance chain...</p>
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

  const outcomeColor =
    data.outcome === "APPROVED" ? "#22c55e" : data.outcome === "DENIED" ? "#ef4444" : "#f59e0b";

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: "32px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "8px" }}>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#f0f0f0" }}>
            Provenance Explorer
          </h1>
          {data.outcome && (
            <span
              style={{
                padding: "4px 12px",
                borderRadius: "16px",
                fontSize: "12px",
                fontWeight: 700,
                background: `${outcomeColor}15`,
                color: outcomeColor,
                border: `1px solid ${outcomeColor}30`,
              }}
            >
              {data.outcome}
            </span>
          )}
          {data.hash_chain_valid && (
            <span
              style={{
                padding: "4px 12px",
                borderRadius: "16px",
                fontSize: "11px",
                fontWeight: 600,
                background: "#22c55e15",
                color: "#22c55e",
                border: "1px solid #22c55e30",
              }}
            >
              HASH CHAIN VALID
            </span>
          )}
        </div>

        <p style={{ fontSize: "14px", color: "#999", marginBottom: "16px" }}>
          {data.task}
        </p>

        <div style={{ display: "flex", gap: "24px", fontSize: "13px", color: "#888" }}>
          <span>
            <strong style={{ color: "#ccc" }}>Trace:</strong>{" "}
            <code style={{ fontSize: "12px", color: "#666" }}>{data.trace_id}</code>
          </span>
          <span>
            <strong style={{ color: "#ccc" }}>Cost:</strong> ${data.total_cost_usd?.toFixed(4)}
          </span>
          <span>
            <strong style={{ color: "#ccc" }}>Latency:</strong> {data.total_latency_ms}ms
          </span>
          <span>
            <strong style={{ color: "#ccc" }}>Steps:</strong> {data.provenance_chain?.length || 0}
          </span>
        </div>
      </div>

      {/* Timeline */}
      <ProvenanceTimeline steps={data.provenance_chain || []} />
    </div>
  );
}
