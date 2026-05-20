# TraceForge

**Production-grade cross-agent decision provenance on Neo4j + AWS Strands + Bedrock AgentCore.**

### [Live Demo](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app) | [GitHub](https://github.com/ElijahUmana/traceforge)

> **Try it now:** Run a live 3-agent credit decision swarm, then explore the provenance graph, audit report, and cost attribution — all backed by a real Neo4j Aura instance.

Built at [Hack Day: Context Graphs for Multi-Agent AI](https://lu.ma/neo4j-aws-hackday) (May 19, 2026) at AWS Builder Loft SF.

---

## The Problem

Multi-agent LLM systems fail at **41–86.7% rates** in production. Across 1,600+ annotated execution traces, **79% of failures** trace to a single root cause: agents share outputs but not reasoning.

> Source: [Augment Code — Why Multi-Agent LLM Systems Fail](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them) (2026)

When a Strands swarm of three agents makes a credit decision, no one can answer:

- Which agent decided what?
- Based on which tool output?
- Was that data even valid?
- How much did the decision cost?
- Can we reconstruct the full reasoning chain for an auditor?

Today's solutions don't solve this:

| Existing Approach | Why It Falls Short |
|---|---|
| **Strands lifecycle hooks** | Fire in-process but nothing persists them. [SDK issue #2216](https://github.com/strands-agents/sdk-python/issues/2216) ("Agent Harness" with audit) is still unshipped. |
| **AgentCore Memory** | Flat-record model. 5 TPS write ceiling. Semantic search only. No graph relationships between decisions. 14-day retention. |
| **Application logs** | Flat text. You can grep them. You cannot traverse "which entity did step 4 touch, and what other steps touched that entity, and what decisions did those feed into?" |
| **AWS workshop folder 06** | AWS's own production reference [explicitly collapsed](https://github.com/aws-samples/sample-stop-ai-agent-hallucinations-workshop/tree/main/06-agentcore-boto3-demo) the multi-agent validation pattern into a single Lambda rules engine. The provenance trail was the casualty. |

The missing primitive is a **graph-native provenance substrate** that turns transient agent events into a durable, queryable, tamper-evident decision graph.

### The Compliance Clock

**EU AI Act Article 12** full enforcement begins **August 2, 2026** — 75 days from today. Credit decisions are explicitly classified as high-risk AI (Annex III, Section 5). Every decision requires 6 months of tamper-proof, reconstructable audit logs. Fines reach **€35M or 7% of global annual turnover**.

---

## The Solution

TraceForge captures every Strands multi-agent decision as a **queryable Neo4j provenance graph** in real time. A `ProvenanceHook` intercepts every lifecycle event — tool calls, model calls, agent handoffs — computes a SHA-256 hash chain, and writes typed nodes and edges directly to Neo4j.

One Cypher query reconstructs the full decision chain across N agents. EU AI Act compliance falls out as a free byproduct.

### Three Pillars

**1. Forensic Replay**
Every reasoning step is a `:ReasoningStep` node connected by `:HAS_STEP`, `:NEXT_STEP`, `:USES_TOOL`, and `:TOUCHED` edges. One Cypher query traverses the entire provenance chain from decision back to source data.

**2. Compliance-by-Construction**
Each step's `step_hash = SHA-256(prev_hash || trace_id || agent || step_number || tool || args || result || timestamp)`. Walk the chain, recompute each hash. If any don't match, the step was tampered with. The graph IS the Article 12 audit log.

**3. Cost Attribution per Decision**
Every `:ReasoningStep` carries `cost_usd`, `latency_ms`, `model_id`, `token_input`, `token_output`. One Cypher query rolls up cost by tenant, agent, tool, or time period.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Strands Swarm (GraphBuilder DAG)               │
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│   │  Researcher  │───▶│   Analyst    │───▶│    Writer     │      │
│   │              │    │              │    │              │      │
│   │ 4 tools:     │    │ 3 tools:     │    │ 3 tools:     │      │
│   │ fetch_sec    │    │ compute_risk │    │ draft_memo   │      │
│   │ fetch_credit │    │ validate_    │    │ check_       │      │
│   │ fetch_news   │    │   rules      │    │  compliance  │      │
│   │ query_kg     │    │ compare_     │    │ submit_      │      │
│   │              │    │  historical  │    │  decision    │      │
│   └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │                    ProvenanceHook                          │   │
│   │  Intercepts: BeforeToolCall, AfterToolCall,               │   │
│   │  AfterModelCall, BeforeInvocation, AfterInvocation         │   │
│   │                                                           │   │
│   │  Per event: capture → SHA-256 hash chain → write to Neo4j │   │
│   └──────────────────────────────┬───────────────────────────┘   │
└──────────────────────────────────┼───────────────────────────────┘
                                   │
                                   ▼
                      ┌──────────────────────┐
                      │   Neo4j Aura (bolt)   │
                      │                      │
                      │  (:ReasoningTrace)   │
                      │    ─[:HAS_STEP]─▶    │
                      │  (:ReasoningStep)    │
                      │    ─[:NEXT_STEP]─▶   │
                      │  (:ReasoningStep)    │
                      │    ─[:USES_TOOL]─▶   │
                      │  (:ToolCall)         │
                      │    ─[:TOUCHED]─▶     │
                      │  (:Entity)           │
                      └──────────┬───────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
              "Why?" API    Cost API    Audit API
              (Cypher)      (Cypher)    (Cypher → JSON)
                    │            │            │
                    ▼            ▼            ▼
              ┌──────────────────────────────────┐
              │     Next.js Dashboard              │
              │                                    │
              │  /          Evaluate (live swarm)   │
              │  /traces    Decision list           │
              │  /why/:id   Provenance explorer     │
              │  /cost      Cost attribution        │
              │  /audit/:id Article 12 report       │
              │  /graph     Force-directed viz      │
              └──────────────────────────────────┘
```

### Neo4j Provenance Graph Schema

```
(:Tenant)
  ─[:HAS_SESSION]─▶ (:Session)
    ─[:HAS_TRACE]─▶ (:ReasoningTrace)
      ─[:HAS_STEP]─▶ (:ReasoningStep)           ◀── hash-chained
        ─[:NEXT_STEP]─▶ (:ReasoningStep)         ◀── sequential ordering
        ─[:USES_TOOL]─▶ (:ToolCall)              ◀── tool invocation record
        ─[:TOUCHED]─▶ (:Entity)                  ◀── THE AUDIT EDGE
        ─[:DECIDED_ON]─▶ (:CreditApplication)    ◀── final decision link

(:CreditApplication)
  ─[:HAS_FINANCIALS]─▶ (:FinancialStatement)
  ─[:HAS_ASSESSMENT]─▶ (:RiskAssessment)
  ─[:HAS_MEMO]─▶ (:DecisionMemo)

(:ToolCall)
  ─[:RETRIEVED]─▶ (:FinancialStatement)          ◀── critical for poison tracing
```

17 constraints (uniqueness + existence). 17 indexes (vector, full-text, range, composite).

### Hash Chain Integrity

```
Step 1:  prev_hash = "GENESIS"
         step_hash = SHA-256("GENESIS" || trace_id || "Researcher" || 1 || ...)

Step 2:  prev_hash = step_1.step_hash
         step_hash = SHA-256(step_1.step_hash || trace_id || "Researcher" || 2 || ...)

Step N:  prev_hash = step_(N-1).step_hash
         step_hash = SHA-256(step_(N-1).step_hash || trace_id || agent || N || ...)
```

Verification query — returns empty if chain is intact, rows if tampered:

```cypher
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
WITH step ORDER BY step.step_number
WITH collect(step) AS steps
UNWIND range(1, size(steps)-1) AS i
WITH steps[i-1] AS prev, steps[i] AS curr
WHERE curr.prev_hash <> prev.step_hash
RETURN prev.step_id AS broken_after, curr.step_id AS broken_at
```

---

## Technology Stack

| Layer | Technology | Role |
|---|---|---|
| **Agent Framework** | [AWS Strands Agents](https://strandsagents.com) v1.40 | GraphBuilder DAG, lifecycle hooks, tool orchestration |
| **LLM** | Claude Sonnet 4 via [Anthropic API](https://docs.anthropic.com) | Agent reasoning (3 agents, 10 tools) |
| **Provenance Graph** | [Neo4j Aura](https://neo4j.com/cloud/aura/) | Decision traces, entity graph, hash-chain storage, Cypher queries |
| **Agent Memory** | [neo4j-agent-memory](https://github.com/neo4j-labs/agent-memory) v0.4 | POLE+O entity model, reasoning trace schema |
| **Production Deploy** | [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) | Runtime, Gateway (MCP), IAM, auto-scaling |
| **Backend API** | FastAPI | REST endpoints: /evaluate, /why, /cost, /audit, /stream |
| **Frontend** | Next.js 16 + Chakra UI + Recharts | Provenance explorer, cost dashboard, audit reports |
| **Scaffolding** | [create-context-graph](https://github.com/neo4j-labs/create-context-graph) v0.12 | Reference for context graph patterns |

---

## Demo: Credit Decision Triage

Three companies. Three outcomes. One provenance graph that explains everything.

| Company | Amount | Data | Expected Outcome | Demo Story |
|---|---|---|---|---|
| **Meridian Manufacturing** | $10M | Clean financials, credit score 82, positive sentiment | APPROVED | The happy path — provenance shows clean chain |
| **Zenith Biotech** | $25M | Revenue **poisoned 10x** ($15M real → $150M reported), credit score 41, negative sentiment | **WRONGFUL APPROVE** | Poisoned revenue tricks the system. Provenance traces the exact `fetch_sec_filings` tool call that returned inflated data. |
| **Atlas Logistics** | $50M | Solid financials but amount exceeds $30M automated threshold | ESCALATED | Business rules fire correctly, provenance captures the rule validation |

### The "Why?" Query

After Zenith is wrongfully approved, one Cypher query finds the poison:

```cypher
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
MATCH (step)-[:USES_TOOL]->(tc:ToolCall)
WHERE tc.tool_name = 'fetch_sec_filings'
  AND tc.result CONTAINS '150000000'
RETURN step.agent_name AS culprit_agent,
       tc.tool_name AS culprit_tool,
       tc.result_summary AS what_it_returned,
       step.step_number AS when_in_chain,
       step.step_hash AS cryptographic_proof
```

Result: *"Researcher called fetch_sec_filings at step 2 and got $150M revenue. Every downstream step — Analyst risk score, Writer memo — was built on this poisoned data."*

---

## Live Application

**Deployed at:** [https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app)

| Route | Description |
|---|---|
| [`/`](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app) | Submit a credit application to the live 3-agent swarm |
| [`/traces`](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app/traces) | Browse all decision traces with color-coded outcomes |
| [`/why/:id`](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app/traces) | Expandable provenance explorer with hash chain verification |
| [`/cost`](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app/cost) | Cost attribution dashboard by agent, tool, and tenant |
| [`/audit/:id`](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app/audit) | EU AI Act Article 12 compliance audit report |
| [`/graph`](https://6a29-2001-1890-12e7-ce0-6534-9c6-7086-ff80.ngrok-free.app/graph) | Force-directed provenance graph visualization |

**Infrastructure:** FastAPI backend + Next.js frontend served over HTTPS, connected to Neo4j Aura (cloud-hosted graph database) and Claude Sonnet 4 via Anthropic API. AgentCore deployment script included for production scaling on AWS.

---

## Project Structure

```
traceforge/
├── backend/
│   ├── app/
│   │   ├── config.py              # Pydantic settings from .env
│   │   ├── prompts.py             # System prompts for 3 agents
│   │   ├── tools.py               # 10 @tool functions (Neo4j-backed)
│   │   ├── hooks.py               # ProvenanceHook (SHA-256 hash chain)
│   │   ├── swarm.py               # Strands GraphBuilder DAG
│   │   ├── provenance_writer.py   # Direct Neo4j provenance writes
│   │   ├── queries.py             # Why/Cost/Audit Cypher queries
│   │   ├── main.py                # FastAPI application
│   │   └── routes.py              # REST endpoints
│   └── scripts/
│       ├── apply_schema.py        # Apply Neo4j constraints + indexes
│       ├── seed_data.py           # Seed 3 companies + poisoned data
│       └── run_demo_traces.py     # Execute all 3 demo evaluations
├── cypher/
│   ├── constraints.cypher         # 17 uniqueness + existence constraints
│   ├── indexes.cypher             # 17 vector + full-text + range indexes
│   ├── why_query.cypher           # Provenance reconstruction
│   ├── cost_query.cypher          # Cost attribution rollup
│   ├── poison_trace.cypher        # Find poisoned data in chain
│   ├── compare_traces.cypher      # Side-by-side trace diff
│   └── hash_chain_verify.cypher   # Tamper detection
├── frontend/
│   └── src/
│       ├── app/                   # Next.js pages (6 routes)
│       └── components/            # ProvenanceTimeline, TraceCard, etc.
├── deploy/
│   └── deploy_runtime.py         # AgentCore Gateway + Runtime deployment
├── tool_schemas/
│   └── tools.json                # 10 MCP tool schemas
├── data/
│   └── ontology.yaml             # Credit decision domain ontology
└── PLAN.md                        # 4,800-line master build plan
```

---

## Setup

```bash
git clone https://github.com/ElijahUmana/traceforge.git
cd traceforge

# Configure
cp .env.example .env
# Fill in: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, ANTHROPIC_API_KEY

# Install
make install

# Apply Neo4j schema and seed data
make schema
make seed

# Start
make start
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

---

## Key Queries

**Reconstruct any decision:**
```cypher
MATCH (trace:ReasoningTrace {trace_id: $id})-[:HAS_STEP]->(step)
OPTIONAL MATCH (step)-[:USES_TOOL]->(tc)
RETURN step.agent_name, step.event_type, step.action,
       tc.tool_name, tc.result_summary, step.step_hash
ORDER BY step.step_number
```

**Cost by agent:**
```cypher
MATCH (t:ReasoningTrace)-[:HAS_STEP]->(s:ReasoningStep)
WHERE t.tenant_id = $tenant
RETURN s.agent_name, sum(s.cost_usd) AS cost, sum(s.token_output) AS tokens
```

**Verify hash chain integrity:**
```cypher
MATCH (t:ReasoningTrace {trace_id: $id})-[:HAS_STEP]->(s)
WITH s ORDER BY s.step_number
WITH collect(s) AS steps
UNWIND range(1, size(steps)-1) AS i
WITH steps[i-1] AS prev, steps[i] AS curr
WHERE curr.prev_hash <> prev.step_hash
RETURN prev.step_id AS broken_after, curr.step_id AS broken_at
```

---

## Research Foundation

- [Multi-Agent AI: Why They Fail](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them) — Augment Code, 2026. 41–86.7% failure rate, 79% from context inconsistency.
- [VeriTrail: Detecting Hallucination and Tracing Provenance](https://www.microsoft.com/en-us/research/blog/veritrail-detecting-hallucination-and-tracing-provenance-in-multi-step-ai-workflows/) — Microsoft Research, ICLR 2026. First method for provenance tracing in multi-step AI.
- [OWASP Top 10 for Agentic AI](https://www.startupdefense.io/blog/owasp-top-10-agentic-ai-security-risks-2026) — 2026. Hallucination propagation between agents as a top risk.
- [When Your Agents Share a Brain](https://medium.com/neo4j/when-your-agents-share-a-brain-building-multi-agent-memory-with-neo4j-bac609f17b23) — William Lyon / Neo4j, April 2026. Multi-agent shared graph memory.
- [EU AI Act Article 12](https://dev.to/verisigilai/eu-ai-act-compliance-checklist-for-ai-agents-87-days-until-enforcement-3m1a) — Full enforcement August 2, 2026. Tamper-proof audit logs for high-risk AI.

---

## Team

- [Elijah Umana](https://github.com/ElijahUmana)
- [Jay Yu](https://github.com/Pepps233)
- [Ngan Huong](https://github.com/nganhuongg)
