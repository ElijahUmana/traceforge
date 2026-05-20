"use client";

import { useEffect, useState } from "react";
import { TraceCard } from "@/components/TraceCard";

interface Trace {
  trace_id: string;
  task: string | null;
  outcome: string | null;
  total_cost_usd: number;
  total_latency_ms: number;
  agent_count: number;
  step_count: number;
  started_at: string | null;
  completed_at: string | null;
  tenant_id: string | null;
  success: boolean | null;
}

export default function TracesPage() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTraces();
  }, []);

  function loadTraces() {
    setLoading(true);
    fetch("/api/traces")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => setTraces(data.traces || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#f0f0f0", marginBottom: "4px" }}>
            Reasoning Traces
          </h1>
          <p style={{ color: "#888", fontSize: "14px" }}>
            {traces.length} trace{traces.length !== 1 ? "s" : ""} recorded
          </p>
        </div>
        <button
          onClick={loadTraces}
          style={{
            padding: "8px 16px",
            background: "#1a1a24",
            border: "1px solid #333",
            borderRadius: "6px",
            color: "#aaa",
            fontSize: "13px",
            cursor: "pointer",
          }}
        >
          Refresh
        </button>
      </div>

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
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {traces.map((trace) => (
            <TraceCard key={trace.trace_id} trace={trace} />
          ))}
        </div>
      )}
    </div>
  );
}
