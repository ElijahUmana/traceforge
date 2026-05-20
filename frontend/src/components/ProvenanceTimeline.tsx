"use client";

import { useState } from "react";

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

const AGENT_COLORS: Record<string, { bg: string; fg: string; glow: string; border: string }> = {
  Researcher: { bg: "#3b82f620", fg: "#60a5fa", glow: "#3b82f640", border: "#3b82f650" },
  Analyst: { bg: "#f9731620", fg: "#fb923c", glow: "#f9731640", border: "#f9731650" },
  Writer: { bg: "#22c55e20", fg: "#4ade80", glow: "#22c55e40", border: "#22c55e50" },
};

const EVENT_ICONS: Record<string, string> = {
  AGENT_START: "▶",
  AGENT_END: "■",
  TOOL_CALL_START: "⚙",
  TOOL_CALL_END: "✓",
  MODEL_CALL: "✦",
};

export function ProvenanceTimeline({ steps }: Props) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  if (!steps || steps.length === 0) {
    return <p style={{ color: "#666" }}>No provenance steps found.</p>;
  }

  const toggle = (n: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(steps.map((s) => s.step_number)));
  const collapseAll = () => setExpanded(new Set());

  let lastAgent = "";

  return (
    <div>
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px" }}>
        <button onClick={expandAll} style={controlBtn}>Expand All</button>
        <button onClick={collapseAll} style={controlBtn}>Collapse All</button>
        <div style={{ flex: 1 }} />
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          {Object.entries(AGENT_COLORS).map(([name, c]) => (
            <span key={name} style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: c.fg }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: c.fg, display: "inline-block" }} />
              {name}
            </span>
          ))}
        </div>
      </div>

      <div style={{ position: "relative", paddingLeft: "40px" }}>
        <div style={{ position: "absolute", left: "18px", top: "0", bottom: "0", width: "2px", background: "linear-gradient(to bottom, #3b82f6, #f97316, #22c55e)" }} />

        {steps.map((step, idx) => {
          const colors = AGENT_COLORS[step.agent_name] || { bg: "#88888820", fg: "#888", glow: "#88888840", border: "#88888850" };
          const isExpanded = expanded.has(step.step_number);
          const isAgentStart = step.event_type === "AGENT_START";
          const isAgentEnd = step.event_type === "AGENT_END";
          const isToolEnd = step.event_type === "TOOL_CALL_END";
          const isModel = step.event_type === "MODEL_CALL";
          const validTools = (step.tools || []).filter((t) => t.call_id !== null);
          const icon = EVENT_ICONS[step.event_type] || "•";

          const showAgentHeader = step.agent_name !== lastAgent;
          lastAgent = step.agent_name;

          return (
            <div key={step.step_id || idx}>
              {showAgentHeader && (
                <div style={{
                  margin: idx > 0 ? "24px 0 12px -40px" : "0 0 12px -40px",
                  padding: "8px 16px 8px 40px",
                  background: `linear-gradient(90deg, ${colors.bg}, transparent)`,
                  borderLeft: `3px solid ${colors.fg}`,
                  borderRadius: "0 8px 8px 0",
                }}>
                  <span style={{ fontSize: "13px", fontWeight: 700, color: colors.fg, textTransform: "uppercase", letterSpacing: "1px" }}>
                    {step.agent_name} Agent
                  </span>
                </div>
              )}

              <div
                style={{ marginBottom: "8px", position: "relative", cursor: "pointer" }}
                onClick={() => toggle(step.step_number)}
              >
                <div style={{
                  position: "absolute",
                  left: "-30px",
                  top: "12px",
                  width: "18px",
                  height: "18px",
                  borderRadius: "50%",
                  background: isAgentStart || isAgentEnd ? colors.fg : "#1a1a24",
                  border: `2px solid ${colors.fg}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "9px",
                  color: isAgentStart || isAgentEnd ? "#0a0a0f" : colors.fg,
                  fontWeight: 700,
                  zIndex: 1,
                  boxShadow: isExpanded ? `0 0 8px ${colors.glow}` : "none",
                }}>
                  {icon}
                </div>

                <div style={{
                  background: isExpanded ? "#13131d" : "#111118",
                  borderRadius: "8px",
                  padding: isExpanded ? "16px" : "10px 16px",
                  border: `1px solid ${isExpanded ? colors.border : "#1a1a24"}`,
                  transition: "all 0.15s ease",
                  boxShadow: isExpanded ? `0 0 20px ${colors.bg}` : "none",
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontSize: "10px", color: "#555", fontFamily: "monospace", minWidth: "24px" }}>
                        #{step.step_number}
                      </span>
                      <span style={{
                        fontSize: "10px",
                        padding: "2px 8px",
                        background: colors.bg,
                        borderRadius: "4px",
                        color: colors.fg,
                        fontWeight: 600,
                        fontFamily: "monospace",
                      }}>
                        {step.event_type}
                      </span>
                      {step.action && (
                        <code style={{ fontSize: "12px", color: "#ddd", background: "#1a1a24", padding: "2px 8px", borderRadius: "4px" }}>
                          {step.action}
                        </code>
                      )}
                      {step.thought && !isExpanded && (
                        <span style={{ fontSize: "12px", color: "#777", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "400px" }}>
                          {step.thought}
                        </span>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: "10px", fontSize: "10px", color: "#555", alignItems: "center" }}>
                      {step.cost_usd > 0 && <span style={{ color: "#22c55e" }}>${step.cost_usd.toFixed(4)}</span>}
                      {step.latency_ms > 0 && <span>{step.latency_ms}ms</span>}
                      <span style={{ fontSize: "14px", color: "#444", transform: isExpanded ? "rotate(180deg)" : "rotate(0)", transition: "transform 0.15s" }}>
                        {"▼"}
                      </span>
                    </div>
                  </div>

                  {isExpanded && (
                    <div style={{ marginTop: "12px", borderTop: "1px solid #1a1a24", paddingTop: "12px" }}>
                      {step.thought && (
                        <div style={{ marginBottom: "10px" }}>
                          <span style={{ fontSize: "10px", color: "#666", textTransform: "uppercase", letterSpacing: "0.5px" }}>Thought</span>
                          <p style={{ fontSize: "13px", color: "#ccc", marginTop: "4px", lineHeight: 1.6 }}>{step.thought}</p>
                        </div>
                      )}

                      {step.observation && (
                        <div style={{ marginBottom: "10px" }}>
                          <span style={{ fontSize: "10px", color: "#666", textTransform: "uppercase", letterSpacing: "0.5px" }}>Observation</span>
                          <pre style={{
                            fontSize: "12px",
                            color: "#aaa",
                            marginTop: "4px",
                            lineHeight: 1.5,
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-word",
                            background: "#0d0d14",
                            padding: "10px",
                            borderRadius: "6px",
                            maxHeight: "200px",
                            overflow: "auto",
                            border: "1px solid #1a1a24",
                          }}>
                            {step.observation}
                          </pre>
                        </div>
                      )}

                      {validTools.length > 0 && (
                        <div style={{ marginBottom: "10px" }}>
                          <span style={{ fontSize: "10px", color: "#666", textTransform: "uppercase", letterSpacing: "0.5px" }}>Tool Calls</span>
                          {validTools.map((tc) => (
                            <div key={tc.call_id} style={{
                              marginTop: "6px",
                              padding: "10px",
                              background: "#0d0d14",
                              borderRadius: "6px",
                              border: `1px solid ${tc.status === "SUCCESS" ? "#22c55e20" : "#ef444420"}`,
                            }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                  <span style={{
                                    fontSize: "10px",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    fontWeight: 700,
                                    background: tc.status === "SUCCESS" ? "#22c55e20" : "#ef444420",
                                    color: tc.status === "SUCCESS" ? "#22c55e" : "#ef4444",
                                  }}>
                                    {tc.status}
                                  </span>
                                  <code style={{ fontSize: "12px", color: "#ddd", fontWeight: 600 }}>{tc.tool_name}</code>
                                </div>
                                {tc.duration_ms && <span style={{ fontSize: "10px", color: "#555" }}>{tc.duration_ms}ms</span>}
                              </div>
                              {tc.result_summary && (
                                <p style={{ fontSize: "11px", color: "#888", lineHeight: 1.5 }}>{tc.result_summary}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {isModel && step.token_input != null && (
                        <div style={{ display: "flex", gap: "16px", marginBottom: "10px" }}>
                          <div style={{ fontSize: "11px" }}>
                            <span style={{ color: "#666" }}>Input: </span>
                            <span style={{ color: "#aaa" }}>{step.token_input?.toLocaleString()} tokens</span>
                          </div>
                          <div style={{ fontSize: "11px" }}>
                            <span style={{ color: "#666" }}>Output: </span>
                            <span style={{ color: "#aaa" }}>{step.token_output?.toLocaleString()} tokens</span>
                          </div>
                          {step.model_id && (
                            <div style={{ fontSize: "11px" }}>
                              <span style={{ color: "#666" }}>Model: </span>
                              <span style={{ color: "#aaa" }}>{step.model_id}</span>
                            </div>
                          )}
                        </div>
                      )}

                      <div style={{ display: "flex", gap: "16px", fontSize: "10px", fontFamily: "monospace", color: "#444", paddingTop: "8px", borderTop: "1px solid #1a1a24" }}>
                        <span>prev: {step.prev_hash.slice(0, 12)}...</span>
                        <span>hash: {step.step_hash.slice(0, 12)}...</span>
                        {step.created_at && <span>{new Date(step.created_at).toLocaleTimeString()}</span>}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const controlBtn: React.CSSProperties = {
  padding: "6px 14px",
  background: "#1a1a24",
  border: "1px solid #333",
  borderRadius: "6px",
  color: "#888",
  fontSize: "11px",
  cursor: "pointer",
};
