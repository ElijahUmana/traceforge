# TraceForge

Production-grade cross-agent decision provenance on Neo4j + AWS Strands + Bedrock AgentCore.

**Built at Hack Day: Context Graphs for Multi-Agent AI** (May 19, 2026) at AWS Builder Loft SF.

## The Problem

Multi-agent LLM systems fail at 41-86.7% rates. 79% of failures trace to context inconsistency: agents share outputs but not reasoning. When a Strands swarm makes a credit decision, you cannot answer "which agent decided what, when, based on which tool output."

## The Solution

TraceForge captures every Strands multi-agent decision as a queryable Neo4j provenance graph in real time via lifecycle hooks. One Cypher query reconstructs the full decision chain across N agents. EU AI Act Article 12 compliance is a free byproduct.

### Three Pillars

1. **Forensic replay** -- hash-chained `(:ReasoningTrace)-[:HAS_STEP]->(:ReasoningStep)-[:USES_TOOL]->(:ToolCall)` graph with `:TOUCHED` audit edges
2. **Compliance-by-construction** -- SHA-256 hash chain satisfies Article 12 tamper-proof audit mandates
3. **Cost attribution per decision** -- every step carries `cost_usd`, `latency_ms`, `model_id`; Cypher rolls up by tenant/agent/tool

### Tech Stack

- **Neo4j Context Graph** via `neo4j-agent-memory` v0.4 + Neo4j Aura
- **AWS Strands Agents** v1.40.0 with `GraphBuilder` multi-agent DAG
- **Amazon Bedrock AgentCore** Runtime deployed via boto3

## Demo

Credit-decision triage: 3-agent swarm (Researcher, Analyst, Writer) processes credit applications. Inject a poisoned financial statement and watch the provenance graph trace the hallucination back to its source in one Cypher query.

## Setup

```bash
cp .env.example .env
# Fill in NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
make install
make schema
make seed
make start
```

## Team

- Elijah Umana ([@ElijahUmana](https://github.com/ElijahUmana))
- Jay Yu ([@Pepps233](https://github.com/Pepps233))
- Ngan Huong ([@nganhuongg](https://github.com/nganhuongg))
