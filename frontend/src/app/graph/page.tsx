"use client";

import { useEffect, useState, useRef, useCallback } from "react";

interface Trace {
  trace_id: string;
  task: string | null;
  outcome: string | null;
}

interface ToolCall {
  call_id: string | null;
  tool_name: string | null;
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
  step_hash: string;
  status: string;
  tools: ToolCall[];
}

interface WhyData {
  trace_id: string;
  task: string;
  outcome: string;
  provenance_chain: ProvenanceStep[];
}

interface GraphNode {
  id: string;
  label: string;
  type: "trace" | "step" | "tool";
  agent?: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  detail: string;
}

interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

const AGENT_COLORS: Record<string, string> = {
  Researcher: "#3b82f6",
  Analyst: "#f97316",
  Writer: "#22c55e",
};

const NODE_RADIUS: Record<string, number> = {
  trace: 24,
  step: 16,
  tool: 10,
};

export default function GraphPage() {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<string>("");
  const [whyData, setWhyData] = useState<WhyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const svgRef = useRef<SVGSVGElement>(null);
  const nodesRef = useRef<GraphNode[]>([]);
  const edgesRef = useRef<GraphEdge[]>([]);
  const animRef = useRef<number>(0);

  // Load traces
  useEffect(() => {
    fetch("/api/traces")
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        const t = data.traces || [];
        setTraces(t);
        if (t.length > 0) setSelectedTrace(t[0].trace_id);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Load provenance for selected trace
  useEffect(() => {
    if (!selectedTrace) return;

    fetch(`/api/why/${selectedTrace}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(setWhyData)
      .catch((err) => setError(err.message));
  }, [selectedTrace]);

  // Build graph from provenance data
  const buildGraph = useCallback(() => {
    if (!whyData) return;

    const width = 900;
    const height = 600;
    const nodes: GraphNode[] = [];
    const edges: GraphEdge[] = [];

    // Trace node at center-left
    nodes.push({
      id: whyData.trace_id,
      label: whyData.trace_id.slice(0, 16),
      type: "trace",
      x: 80,
      y: height / 2,
      vx: 0,
      vy: 0,
      detail: `Task: ${whyData.task}\nOutcome: ${whyData.outcome}`,
    });

    const chain = whyData.provenance_chain || [];
    const stepsByAgent: Record<string, ProvenanceStep[]> = {};
    for (const step of chain) {
      if (!stepsByAgent[step.agent_name]) stepsByAgent[step.agent_name] = [];
      stepsByAgent[step.agent_name].push(step);
    }

    const agentNames = Object.keys(stepsByAgent);
    const agentLaneHeight = height / (agentNames.length + 1);

    // Place step nodes in a DAG layout by agent
    for (let aIdx = 0; aIdx < agentNames.length; aIdx++) {
      const agent = agentNames[aIdx];
      const agentSteps = stepsByAgent[agent];
      const laneY = agentLaneHeight * (aIdx + 1);
      const xSpacing = (width - 200) / (agentSteps.length + 1);

      for (let sIdx = 0; sIdx < agentSteps.length; sIdx++) {
        const step = agentSteps[sIdx];
        const sx = 160 + xSpacing * (sIdx + 1);
        const sy = laneY + (Math.random() - 0.5) * 30;

        nodes.push({
          id: step.step_id,
          label: `${step.agent_name[0]}${step.step_number}`,
          type: "step",
          agent: step.agent_name,
          x: sx,
          y: sy,
          vx: 0,
          vy: 0,
          detail: [
            `Agent: ${step.agent_name}`,
            `Event: ${step.event_type}`,
            `Step: #${step.step_number}`,
            step.thought ? `Thought: ${step.thought}` : "",
            step.observation ? `Observation: ${step.observation}` : "",
            `Cost: $${step.cost_usd.toFixed(4)}`,
            `Latency: ${step.latency_ms}ms`,
          ]
            .filter(Boolean)
            .join("\n"),
        });

        // HAS_STEP edge from trace to first step of each agent
        if (sIdx === 0) {
          edges.push({ source: whyData.trace_id, target: step.step_id, label: "HAS_STEP" });
        }

        // NEXT_STEP edge within agent
        if (sIdx > 0) {
          edges.push({ source: agentSteps[sIdx - 1].step_id, target: step.step_id, label: "NEXT_STEP" });
        }

        // Tool call nodes
        const validTools = (step.tools || []).filter((t) => t.call_id !== null);
        for (let tIdx = 0; tIdx < validTools.length; tIdx++) {
          const tc = validTools[tIdx];
          const toolId = tc.call_id!;
          const tx = sx + 20 + tIdx * 25;
          const ty = sy + 40 + tIdx * 15;

          nodes.push({
            id: toolId,
            label: (tc.tool_name || "tool").slice(0, 8),
            type: "tool",
            x: tx,
            y: ty,
            vx: 0,
            vy: 0,
            detail: [
              `Tool: ${tc.tool_name}`,
              `Status: ${tc.status}`,
              tc.duration_ms ? `Duration: ${tc.duration_ms}ms` : "",
              tc.result_summary ? `Result: ${tc.result_summary}` : "",
            ]
              .filter(Boolean)
              .join("\n"),
          });

          edges.push({ source: step.step_id, target: toolId, label: "USES_TOOL" });
        }
      }
    }

    // Cross-agent NEXT_STEP edges between last step of one agent and first step of next
    for (let aIdx = 0; aIdx < agentNames.length - 1; aIdx++) {
      const currSteps = stepsByAgent[agentNames[aIdx]];
      const nextSteps = stepsByAgent[agentNames[aIdx + 1]];
      if (currSteps.length > 0 && nextSteps.length > 0) {
        edges.push({
          source: currSteps[currSteps.length - 1].step_id,
          target: nextSteps[0].step_id,
          label: "NEXT_STEP",
        });
      }
    }

    nodesRef.current = nodes;
    edgesRef.current = edges;
  }, [whyData]);

  useEffect(() => {
    buildGraph();
  }, [buildGraph]);

  // Simple force simulation
  useEffect(() => {
    if (!whyData || nodesRef.current.length === 0) return;

    let iteration = 0;
    const maxIterations = 120;

    function simulate() {
      const nodes = nodesRef.current;
      const edges = edgesRef.current;

      if (iteration >= maxIterations) {
        renderGraph();
        return;
      }

      const alpha = 1 - iteration / maxIterations;

      // Repulsion between all nodes
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x;
          const dy = nodes[j].y - nodes[i].y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = (800 * alpha) / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          nodes[i].vx -= fx;
          nodes[i].vy -= fy;
          nodes[j].vx += fx;
          nodes[j].vy += fy;
        }
      }

      // Attraction along edges
      const nodeMap = new Map(nodes.map((n) => [n.id, n]));
      for (const edge of edges) {
        const source = nodeMap.get(edge.source);
        const target = nodeMap.get(edge.target);
        if (!source || !target) continue;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const idealDist = edge.label === "USES_TOOL" ? 60 : 100;
        const force = ((dist - idealDist) * 0.05 * alpha);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        source.vx += fx;
        source.vy += fy;
        target.vx -= fx;
        target.vy -= fy;
      }

      // Apply velocities with damping
      for (const node of nodes) {
        // Keep trace node fixed
        if (node.type === "trace") {
          node.vx = 0;
          node.vy = 0;
          continue;
        }
        node.vx *= 0.6;
        node.vy *= 0.6;
        node.x += node.vx;
        node.y += node.vy;
        // Boundary constraints
        node.x = Math.max(30, Math.min(870, node.x));
        node.y = Math.max(30, Math.min(570, node.y));
      }

      iteration++;

      if (iteration % 4 === 0) {
        renderGraph();
      }

      animRef.current = requestAnimationFrame(simulate);
    }

    animRef.current = requestAnimationFrame(simulate);
    return () => cancelAnimationFrame(animRef.current);
  }, [whyData, buildGraph]);

  function renderGraph() {
    const svg = svgRef.current;
    if (!svg) return;

    const nodes = nodesRef.current;
    const edges = edgesRef.current;
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    // Build SVG content
    let content = "";

    // Render edges
    for (const edge of edges) {
      const source = nodeMap.get(edge.source);
      const target = nodeMap.get(edge.target);
      if (!source || !target) continue;
      const strokeColor = edge.label === "HAS_STEP" ? "#7c3aed" : edge.label === "USES_TOOL" ? "#555" : "#444";
      const dashArray = edge.label === "USES_TOOL" ? "4,3" : "none";
      content += `<line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" stroke="${strokeColor}" stroke-width="1.5" stroke-dasharray="${dashArray}" opacity="0.6"/>`;
    }

    // Render nodes
    for (const node of nodes) {
      const r = NODE_RADIUS[node.type] || 12;
      let fill = "#888";
      if (node.type === "trace") fill = "#7c3aed";
      else if (node.type === "step") fill = AGENT_COLORS[node.agent || ""] || "#888";
      else if (node.type === "tool") fill = "#444";

      const isSelected = selectedNode?.id === node.id;
      const strokeWidth = isSelected ? 3 : 1.5;
      const strokeColor = isSelected ? "#fff" : "#0a0a0f";

      content += `<circle cx="${node.x}" cy="${node.y}" r="${r}" fill="${fill}" stroke="${strokeColor}" stroke-width="${strokeWidth}" data-id="${node.id}" style="cursor:pointer"/>`;
      content += `<text x="${node.x}" y="${node.y + 3}" text-anchor="middle" fill="#fff" font-size="${node.type === "tool" ? 7 : 9}" font-weight="600" pointer-events="none">${node.label}</text>`;
    }

    svg.innerHTML = content;
  }

  function handleSvgClick(e: React.MouseEvent<SVGSVGElement>) {
    const target = e.target as SVGElement;
    const nodeId = target.getAttribute("data-id");
    if (nodeId) {
      const node = nodesRef.current.find((n) => n.id === nodeId);
      setSelectedNode(node || null);
    } else {
      setSelectedNode(null);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "80px" }}>
        <p style={{ color: "#7c3aed" }}>Loading graph data...</p>
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

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#f0f0f0", marginBottom: "4px" }}>
            Provenance Graph
          </h1>
          <p style={{ color: "#888", fontSize: "14px" }}>
            Interactive visualization of the reasoning trace graph
          </p>
        </div>

        <select
          value={selectedTrace}
          onChange={(e) => setSelectedTrace(e.target.value)}
          style={{
            padding: "8px 14px",
            background: "#111118",
            border: "1px solid #333",
            borderRadius: "6px",
            color: "#e0e0e0",
            fontSize: "13px",
          }}
        >
          {traces.map((t) => (
            <option key={t.trace_id} value={t.trace_id}>
              {t.trace_id} - {t.outcome || "PENDING"}
            </option>
          ))}
        </select>
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: "24px", marginBottom: "16px", fontSize: "12px" }}>
        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#7c3aed", display: "inline-block" }} />
          <span style={{ color: "#999" }}>Trace</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#3b82f6", display: "inline-block" }} />
          <span style={{ color: "#999" }}>Researcher</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#f97316", display: "inline-block" }} />
          <span style={{ color: "#999" }}>Analyst</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#22c55e", display: "inline-block" }} />
          <span style={{ color: "#999" }}>Writer</span>
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#444", display: "inline-block" }} />
          <span style={{ color: "#999" }}>Tool Call</span>
        </span>
      </div>

      {/* Graph */}
      <div style={{ background: "#0d0d14", borderRadius: "12px", border: "1px solid #222", overflow: "hidden" }}>
        <svg
          ref={svgRef}
          width="900"
          height="600"
          viewBox="0 0 900 600"
          style={{ width: "100%", height: "auto" }}
          onClick={handleSvgClick}
        />
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <div style={{ marginTop: "16px", background: "#111118", borderRadius: "8px", padding: "16px", border: "1px solid #222" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <h3 style={{ fontSize: "14px", fontWeight: 600, color: "#e0e0e0" }}>
              {selectedNode.type === "trace" ? "Trace" : selectedNode.type === "step" ? "Reasoning Step" : "Tool Call"}
            </h3>
            <code style={{ fontSize: "11px", color: "#666" }}>{selectedNode.id}</code>
          </div>
          <pre style={{ fontSize: "12px", color: "#bbb", whiteSpace: "pre-wrap", lineHeight: 1.6, margin: 0 }}>
            {selectedNode.detail}
          </pre>
        </div>
      )}
    </div>
  );
}
