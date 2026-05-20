"use client";

interface ToolCall {
  call_id: string | null;
  tool_name: string | null;
  arguments?: string | null;
  result_summary: string | null;
  status: string | null;
  duration_ms: number | null;
}

interface ProvenanceStep {
  step_id: string;
  agent_name: string;
  event_type: string;
  step_number: number;
  thought: string | null;
  action: string | null;
  observation: string | null;
  cost_usd: number;
  latency_ms: number;
  model_id?: string | null;
  token_input?: number;
  token_output?: number;
  prev_hash: string;
  step_hash: string;
  status: string;
  created_at: string | null;
  tools: ToolCall[];
  touched_entities?: Array<{ entity_id: string; name: string; type: string }>;
}

interface Props {
  steps: ProvenanceStep[];
}

const AGENT_COLORS: Record<string, string> = {
  Researcher: "#3b82f6",
  Analyst: "#f97316",
  Writer: "#22c55e",
};

export function ProvenanceTimeline({ steps }: Props) {
  if (!steps || steps.length === 0) {
    return <p style={{ color: "#666" }}>No provenance steps found.</p>;
  }

  return (
    <div style={{ position: "relative", paddingLeft: "32px" }}>
      {/* Vertical line */}
      <div
        style={{
          position: "absolute",
          left: "15px",
          top: "0",
          bottom: "0",
          width: "2px",
          background: "#333",
        }}
      />

      {steps.map((step, idx) => {
        const color = AGENT_COLORS[step.agent_name] || "#888";
        const isToolCall = step.event_type.includes("TOOL_CALL");
        const isModelCall = step.event_type === "MODEL_CALL";
        const isAgentBoundary = step.event_type === "AGENT_START" || step.event_type === "AGENT_END";

        const validTools = (step.tools || []).filter((t) => t.call_id !== null);

        return (
          <div key={step.step_id || idx} style={{ marginBottom: "16px", position: "relative" }}>
            {/* Dot */}
            <div
              style={{
                position: "absolute",
                left: "-24px",
                top: "6px",
                width: "12px",
                height: "12px",
                borderRadius: "50%",
                background: color,
                border: "2px solid #0a0a0f",
              }}
            />

            <div
              style={{
                background: "#111118",
                borderRadius: "8px",
                padding: "14px 16px",
                border: `1px solid ${isAgentBoundary ? color + "40" : "#222"}`,
              }}
            >
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 700,
                      color: color,
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                    }}
                  >
                    {step.agent_name}
                  </span>
                  <span
                    style={{
                      fontSize: "10px",
                      padding: "2px 6px",
                      background: "#1a1a24",
                      borderRadius: "4px",
                      color: "#888",
                      fontFamily: "monospace",
                    }}
                  >
                    {step.event_type}
                  </span>
                  <span style={{ fontSize: "10px", color: "#555" }}>#{step.step_number}</span>
                </div>
                <div style={{ display: "flex", gap: "12px", fontSize: "11px", color: "#666" }}>
                  {step.cost_usd > 0 && <span>${step.cost_usd.toFixed(4)}</span>}
                  {step.latency_ms > 0 && <span>{step.latency_ms}ms</span>}
                </div>
              </div>

              {/* Content */}
              {step.thought && (
                <p style={{ fontSize: "13px", color: "#bbb", marginBottom: "6px" }}>
                  {step.thought}
                </p>
              )}

              {step.action && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "6px" }}>
                  <span style={{ fontSize: "11px", color: "#7c3aed", fontWeight: 600 }}>TOOL:</span>
                  <code style={{ fontSize: "12px", color: "#ddd", background: "#1a1a24", padding: "2px 6px", borderRadius: "4px" }}>
                    {step.action}
                  </code>
                </div>
              )}

              {step.observation && (
                <p style={{ fontSize: "12px", color: "#999", fontStyle: "italic", marginBottom: "6px" }}>
                  {step.observation.length > 200 ? step.observation.slice(0, 200) + "..." : step.observation}
                </p>
              )}

              {/* Tool calls */}
              {validTools.length > 0 && (
                <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid #1a1a24" }}>
                  {validTools.map((tc) => (
                    <div key={tc.call_id} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                      <span style={{ fontSize: "10px", color: tc.status === "SUCCESS" ? "#22c55e" : "#ef4444" }}>
                        {tc.status === "SUCCESS" ? "OK" : "ERR"}
                      </span>
                      <code style={{ fontSize: "11px", color: "#aaa" }}>{tc.tool_name}</code>
                      {tc.duration_ms && <span style={{ fontSize: "10px", color: "#555" }}>{tc.duration_ms}ms</span>}
                      {tc.result_summary && (
                        <span style={{ fontSize: "10px", color: "#666", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "300px" }}>
                          {tc.result_summary}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Hash */}
              <div style={{ marginTop: "8px", fontSize: "10px", color: "#444", fontFamily: "monospace" }}>
                {step.step_hash.slice(0, 16)}...
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
