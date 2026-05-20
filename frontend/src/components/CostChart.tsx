"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface AgentCost {
  agent_name: string;
  cost_usd: number;
  tokens_input: number;
  tokens_output: number;
  avg_latency_ms: number;
}

interface Props {
  data: AgentCost[];
}

const COLORS: Record<string, string> = {
  Researcher: "#3b82f6",
  Analyst: "#f97316",
  Writer: "#22c55e",
};

export function CostChart({ data }: Props) {
  if (!data || data.length === 0) {
    return <p style={{ color: "#666", textAlign: "center", padding: "40px" }}>No cost data available.</p>;
  }

  return (
    <div style={{ width: "100%", height: 300 }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#222" />
          <XAxis dataKey="agent_name" stroke="#888" fontSize={12} />
          <YAxis stroke="#888" fontSize={11} tickFormatter={(v) => `$${v.toFixed(3)}`} />
          <Tooltip
            contentStyle={{ background: "#111118", border: "1px solid #333", borderRadius: "8px" }}
            labelStyle={{ color: "#e0e0e0" }}
            formatter={(value) => [`$${Number(value).toFixed(4)}`, "Cost"]}
          />
          <Bar dataKey="cost_usd" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[entry.agent_name] || "#7c3aed"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
