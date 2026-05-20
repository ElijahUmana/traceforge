"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface AuditReport {
  report: {
    title: string;
    version: string;
    generated_at: string;
    system: string;
    regulation: string;
    classification: string;
  };
  decision: {
    trace_id: string;
    task: string;
    outcome: string;
    timestamp: string;
    tenant: string;
  };
  provenance_chain: Array<{
    step: number;
    agent: string;
    action: string;
    input: Record<string, unknown>;
    output_summary: string;
    data_source: string;
    timestamp: string;
    hash: string;
  }>;
  hash_chain_verification: {
    total_steps: number;
    verified_steps: number;
    chain_intact: boolean;
    genesis_hash: string;
    final_hash: string;
  };
  data_sources_consulted: Array<{
    source: string;
    type: string;
    retrieved_at: string;
  }>;
  compliance_checklist: {
    art12_1_logging: boolean;
    art12_2_traceability: boolean;
    art12_3_monitoring: boolean;
    art12_4_record_keeping: boolean;
    tamper_evidence: string;
    retention_period: string;
  };
}

const AGENT_COLORS: Record<string, string> = {
  Researcher: "#3b82f6",
  Analyst: "#f97316",
  Writer: "#22c55e",
};

export default function AuditPage() {
  const params = useParams();
  const traceId = params.traceId as string;
  const [data, setData] = useState<AuditReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!traceId) return;

    fetch(`/api/audit/${traceId}`, { method: "POST" })
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

  function downloadJson() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_${traceId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "80px" }}>
        <p style={{ color: "#7c3aed" }}>Generating audit report...</p>
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

  const hcv = data.hash_chain_verification;
  const outcomeColor =
    data.decision.outcome === "APPROVED" ? "#22c55e" : data.decision.outcome === "DENIED" ? "#ef4444" : "#f59e0b";

  return (
    <div>
      {/* Report Header */}
      <div style={{ marginBottom: "32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#f0f0f0", marginBottom: "8px" }}>
              {data.report.title}
            </h1>
            <div style={{ display: "flex", gap: "16px", fontSize: "12px", color: "#888" }}>
              <span>Version {data.report.version}</span>
              <span>{data.report.system}</span>
              <span>Generated {new Date(data.report.generated_at).toLocaleString()}</span>
            </div>
          </div>
          <button
            onClick={downloadJson}
            style={{
              padding: "10px 20px",
              background: "#7c3aed",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Download JSON
          </button>
        </div>
        <div style={{ marginTop: "12px", display: "flex", gap: "12px" }}>
          <span style={tagStyle}>{data.report.regulation}</span>
          <span style={{ ...tagStyle, background: "#ef444415", color: "#ef4444", borderColor: "#ef444430" }}>
            {data.report.classification}
          </span>
        </div>
      </div>

      {/* Decision Summary */}
      <Section title="Decision Summary">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "16px" }}>
          <InfoCard label="Trace ID" value={data.decision.trace_id} mono />
          <InfoCard label="Task" value={data.decision.task} />
          <InfoCard
            label="Outcome"
            value={data.decision.outcome}
            valueColor={outcomeColor}
          />
          <InfoCard label="Timestamp" value={data.decision.timestamp ? new Date(data.decision.timestamp).toLocaleString() : "-"} />
          <InfoCard label="Tenant" value={data.decision.tenant} />
        </div>
      </Section>

      {/* Provenance Chain */}
      <Section title={`Provenance Chain (${data.provenance_chain.length} steps)`}>
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {data.provenance_chain.map((step) => {
            const color = AGENT_COLORS[step.agent] || "#888";
            return (
              <div
                key={step.step}
                style={{
                  display: "grid",
                  gridTemplateColumns: "40px 100px 1fr 120px",
                  gap: "12px",
                  alignItems: "center",
                  padding: "12px 16px",
                  background: "#0d0d14",
                  borderRadius: "6px",
                  border: "1px solid #1a1a24",
                }}
              >
                <span style={{ fontSize: "13px", fontWeight: 700, color: "#555" }}>#{step.step}</span>
                <span style={{ fontSize: "12px", fontWeight: 600, color, textTransform: "uppercase" }}>
                  {step.agent}
                </span>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "2px" }}>
                    <code style={{ fontSize: "12px", color: "#ddd", background: "#1a1a24", padding: "2px 6px", borderRadius: "4px" }}>
                      {step.action}
                    </code>
                    <span style={{ fontSize: "10px", color: "#666", fontFamily: "monospace" }}>
                      {step.data_source}
                    </span>
                  </div>
                  <p style={{ fontSize: "12px", color: "#999", margin: 0 }}>
                    {step.output_summary.length > 120 ? step.output_summary.slice(0, 120) + "..." : step.output_summary}
                  </p>
                </div>
                <code style={{ fontSize: "10px", color: "#444", fontFamily: "monospace", textAlign: "right" }}>
                  {step.hash.slice(0, 12)}...
                </code>
              </div>
            );
          })}
        </div>
      </Section>

      {/* Hash Chain Verification */}
      <Section title="Hash Chain Verification">
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "16px" }}>
          <span
            style={{
              padding: "6px 16px",
              borderRadius: "20px",
              fontSize: "13px",
              fontWeight: 700,
              background: hcv.chain_intact ? "#22c55e15" : "#ef444415",
              color: hcv.chain_intact ? "#22c55e" : "#ef4444",
              border: `1px solid ${hcv.chain_intact ? "#22c55e30" : "#ef444430"}`,
            }}
          >
            {hcv.chain_intact ? "CHAIN INTACT" : "CHAIN BROKEN"}
          </span>
          <span style={{ fontSize: "13px", color: "#999" }}>
            {hcv.verified_steps} of {hcv.total_steps} steps verified
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <InfoCard label="Genesis Hash" value={hcv.genesis_hash} mono />
          <InfoCard label="Final Hash" value={hcv.final_hash.slice(0, 32) + "..."} mono />
        </div>
      </Section>

      {/* Data Sources */}
      <Section title="Data Sources Consulted">
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #222" }}>
              <th style={thStyle}>Source</th>
              <th style={thStyle}>Type</th>
              <th style={thStyle}>Retrieved At</th>
            </tr>
          </thead>
          <tbody>
            {data.data_sources_consulted.map((src) => (
              <tr key={src.source} style={{ borderBottom: "1px solid #1a1a24" }}>
                <td style={tdStyle}>
                  <code style={{ fontSize: "12px" }}>{src.source}</code>
                </td>
                <td style={tdStyle}>{src.type}</td>
                <td style={tdStyle}>
                  {src.retrieved_at ? new Date(src.retrieved_at).toLocaleString() : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {/* Compliance Checklist */}
      <Section title="Compliance Checklist">
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <CheckItem label="Art 12.1 - Automatic Event Logging" checked={data.compliance_checklist.art12_1_logging} />
          <CheckItem label="Art 12.2 - Traceability of Decisions" checked={data.compliance_checklist.art12_2_traceability} />
          <CheckItem label="Art 12.3 - Monitoring Capabilities" checked={data.compliance_checklist.art12_3_monitoring} />
          <CheckItem label="Art 12.4 - Record Keeping" checked={data.compliance_checklist.art12_4_record_keeping} />
          <div style={{ marginTop: "12px", display: "flex", gap: "24px", fontSize: "13px", color: "#999" }}>
            <span>
              <strong style={{ color: "#ccc" }}>Tamper Evidence:</strong> {data.compliance_checklist.tamper_evidence}
            </span>
            <span>
              <strong style={{ color: "#ccc" }}>Retention:</strong> {data.compliance_checklist.retention_period}
            </span>
          </div>
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#111118", borderRadius: "12px", padding: "24px", border: "1px solid #222", marginBottom: "24px" }}>
      <h2 style={{ fontSize: "16px", fontWeight: 600, color: "#e0e0e0", marginBottom: "16px" }}>{title}</h2>
      {children}
    </div>
  );
}

function InfoCard({ label, value, mono, valueColor }: { label: string; value: string; mono?: boolean; valueColor?: string }) {
  return (
    <div style={{ padding: "12px", background: "#0d0d14", borderRadius: "8px", border: "1px solid #1a1a24" }}>
      <div style={{ fontSize: "11px", color: "#888", textTransform: "uppercase", marginBottom: "4px" }}>{label}</div>
      <div
        style={{
          fontSize: mono ? "12px" : "14px",
          fontWeight: 600,
          color: valueColor || "#e0e0e0",
          fontFamily: mono ? "monospace" : "inherit",
          wordBreak: "break-all",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function CheckItem({ label, checked }: { label: string; checked: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", background: "#0d0d14", borderRadius: "6px" }}>
      <span
        style={{
          width: "20px",
          height: "20px",
          borderRadius: "4px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "12px",
          fontWeight: 700,
          background: checked ? "#22c55e15" : "#ef444415",
          color: checked ? "#22c55e" : "#ef4444",
          border: `1px solid ${checked ? "#22c55e30" : "#ef444430"}`,
        }}
      >
        {checked ? "✓" : "✗"}
      </span>
      <span style={{ fontSize: "13px", color: "#ccc" }}>{label}</span>
    </div>
  );
}

const tagStyle: React.CSSProperties = {
  padding: "4px 12px",
  borderRadius: "16px",
  fontSize: "11px",
  fontWeight: 600,
  background: "#7c3aed15",
  color: "#7c3aed",
  border: "1px solid #7c3aed30",
};

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
