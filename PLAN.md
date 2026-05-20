# TraceForge: Production-Grade Cross-Agent Decision Provenance
# MASTER BUILD PLAN — Neo4j + AWS Strands + Bedrock AgentCore

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Problem — With Quantified Evidence](#2-the-problem)
3. [Solution Architecture — Every Component](#3-solution-architecture)
4. [Prerequisites Checklist](#4-prerequisites-checklist)
5. [Phase 0: Environment Bootstrap](#5-phase-0-environment-bootstrap)
6. [Phase 1: Infrastructure Provisioning](#6-phase-1-infrastructure-provisioning)
7. [Phase 2: Neo4j Schema — Complete Graph Model](#7-phase-2-neo4j-schema)
8. [Phase 3: Credit Decision Domain Model](#8-phase-3-credit-decision-domain-model)
9. [Phase 4: Strands Agents — Full Implementation](#9-phase-4-strands-agents)
10. [Phase 5: ProvenanceHook — The Core Innovation](#10-phase-5-provenancehook)
11. [Phase 6: SQS + Lambda ProvenanceWriter](#11-phase-6-sqs-lambda-provenancewriter)
12. [Phase 7: Tool Lambda Functions](#12-phase-7-tool-lambda-functions)
13. [Phase 8: AgentCore Deployment Pipeline](#13-phase-8-agentcore-deployment-pipeline)
14. [Phase 9: API Layer — Why / Cost / Audit](#14-phase-9-api-layer)
15. [Phase 10: Frontend Dashboard](#15-phase-10-frontend-dashboard)
16. [Phase 11: Demo Data & Seed Script](#16-phase-11-demo-data)
17. [Phase 12: Failure Injection & Hallucination Demo](#17-phase-12-failure-injection)
18. [Phase 13: End-to-End Testing](#18-phase-13-end-to-end-testing)
19. [Phase 14: Demo Script — Minute by Minute](#19-phase-14-demo-script)
20. [Phase 15: Fallback Plans](#20-phase-15-fallback-plans)
21. [Team Assignment Matrix](#21-team-assignment-matrix)
22. [Timeline — Hour by Hour](#22-timeline)
23. [File Tree — Every File in the Project](#23-file-tree)
24. [Environment Variables — Complete List](#24-environment-variables)
25. [IAM Policies — Full JSON](#25-iam-policies)
26. [Cypher Queries — Every Query Used](#26-cypher-queries)
27. [Tool Schemas — Full JSON](#27-tool-schemas)
28. [Risk Register](#28-risk-register)

---

## 1. Executive Summary

**Project:** TraceForge
**Tagline:** "When your swarm fails 79% of the time, the answer isn't more validation — it's reconstructable reasoning."

**What it does:** A production deployment substrate that captures every AWS Strands multi-agent
decision as a queryable Neo4j provenance graph in real time. Turns the 79% multi-agent failure
rate into a debuggable Cypher query. Makes EU AI Act Article 12 compliance a free byproduct.

**Three core pillars:**
1. Forensic replay — one Cypher query reconstructs any decision's full chain across N agents
2. Compliance-by-construction — hash-chained reasoning steps satisfy Article 12 audit mandates
3. Cost attribution per decision — every step carries cost/latency/model metadata; rollup by tenant

**Tech stack (all three hackathon requirements met):**
- Neo4j Context Graph via `neo4j-agent-memory` v0.4 + Neo4j Aura
- AWS Strands Agents v1.40.0 with Swarm/Graph multi-agent pattern
- Amazon Bedrock AgentCore Runtime deployed via boto3 (folder 06 pattern)

**Demo scenario:** Credit-decision triage — 3-agent swarm (Researcher, Analyst, Writer) processes
a credit application. Inject a poisoned financial statement. Show provenance graph tracing the
hallucination to its source in one Cypher query.

---

## 2. The Problem — With Quantified Evidence

### 2.1 The Failure Rate

Multi-agent LLM systems fail at 41-86.7% rates in production. Of those failures, 79% trace to
context inconsistency — agents sharing OUTPUTS but not REASONING — across 1,600+ annotated
execution traces.

Source: Augment Code (2026) — https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them

### 2.2 The Missing Primitive

When Agent A in a Strands Swarm makes a decision, Agent B cannot answer:
- What data did Agent A base this on?
- Which tool calls did Agent A make?
- What entities did Agent A consult in the knowledge graph?
- What was Agent A's reasoning chain?
- How much did Agent A's work cost?
- Was Agent A's source data valid?

### 2.3 What Exists Today But Doesn't Solve It

| Existing Solution | Why It's Insufficient |
|---|---|
| Strands lifecycle hooks (`AfterToolCallEvent` etc.) | Fire in-process but **nothing persists them**. SDK issue #2216 "Agent Harness" with audit = unshipped. |
| AgentCore Memory | Flat-record model. 5 TPS write ceiling. Semantic search only. No multi-hop. 14-day retention. No graph relationships between decisions. |
| Neo4j `neo4j-agent-memory` v0.4 | Has the `:ReasoningTrace -> :ReasoningStep -> :ToolCall` schema. Has `:TOUCHED` edges. But NO production wire-up with Strands hooks writing to it asynchronously during Swarm execution. |
| AWS folder 06 (workshop reference) | Explicitly **collapsed** multi-agent validation into a single Lambda rules engine. The provenance trail was the casualty of this production compromise. |
| Microsoft VeriTrail (ICLR 2026) | Research paper for detection/tracing. Not a deployable system. Not integrated with any agent framework. |

### 2.4 The Compliance Clock

EU AI Act Article 12 full enforcement: August 2, 2026 — 75 days from today.
- Mandates 6 months of tamper-proof event logs for high-risk AI systems
- Every agent decision must be reconstructable: what data, what decision, when, why
- Fines: up to 35M EUR or 7% of global annual turnover
- Credit decisions are explicitly listed as "high-risk" (Annex III, Section 5)

Source: https://dev.to/verisigilai/eu-ai-act-compliance-checklist-for-ai-agents-87-days-until-enforcement-3m1a

### 2.5 Why This Exact Tech Stack Is The Only Substrate

| Layer | What It Provides | What It Cannot Do Alone |
|---|---|---|
| **Neo4j** | Graph structure for provenance (`:ReasoningStep` nodes + typed edges + vector search + multi-hop traversal + GDS algorithms) | No agent execution. No deployment runtime. |
| **Strands** | Agent execution engine with lifecycle hooks (`BeforeNodeCallEvent`, `AfterToolCallEvent`, etc.) that fire at every decision point | No persistence. No audit. No graph storage. |
| **AgentCore** | Production runtime with auto-scaling, Gateway tool federation, IAM, VPC networking to Neo4j | No provenance. No multi-hop memory. Flat record model only. |

TraceForge is the BRIDGE between all three. It takes the events Strands generates, persists them
as a provenance graph in Neo4j, and deploys the entire system on AgentCore for production.

---

## 3. Solution Architecture — Every Component

### 3.1 System Architecture Diagram

```
                        ┌─────────────────────────────────────────────────────────────────────────┐
                        │                    Amazon Bedrock AgentCore Runtime                       │
                        │                                                                          │
                        │   ┌─────────────────────────────────────────────────────────────────┐    │
                        │   │              Strands Swarm (GraphBuilder DAG)                     │    │
                        │   │                                                                  │    │
                        │   │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │    │
                        │   │   │  Researcher  │───>│   Analyst    │───>│    Writer     │      │    │
                        │   │   │  Agent       │    │   Agent      │    │    Agent      │      │    │
                        │   │   │              │    │              │    │              │      │    │
                        │   │   │ Tools:       │    │ Tools:       │    │ Tools:       │      │    │
                        │   │   │ - fetch_sec  │    │ - compute_   │    │ - draft_memo │      │    │
                        │   │   │ - fetch_cred │    │   risk       │    │ - check_     │      │    │
                        │   │   │ - fetch_news │    │ - validate_  │    │   compliance │      │    │
                        │   │   │ - query_kg   │    │   rules      │    │ - submit_    │      │    │
                        │   │   │              │    │ - compare_   │    │   decision   │      │    │
                        │   │   │              │    │   historical │    │              │      │    │
                        │   │   └──────────────┘    └──────────────┘    └──────────────┘      │    │
                        │   │                                                                  │    │
                        │   │   ┌──────────────────────────────────────────────────────────┐   │    │
                        │   │   │                 ProvenanceHook                             │   │    │
                        │   │   │  Intercepts: BeforeNodeCallEvent, AfterNodeCallEvent,     │   │    │
                        │   │   │  BeforeToolCallEvent, AfterToolCallEvent,                 │   │    │
                        │   │   │  BeforeModelCallEvent, AfterModelCallEvent,               │   │    │
                        │   │   │  BeforeMultiAgentInvocationEvent,                         │   │    │
                        │   │   │  AfterMultiAgentInvocationEvent                           │   │    │
                        │   │   │                                                           │   │    │
                        │   │   │  Actions per event:                                       │   │    │
                        │   │   │  1. Capture agent_name, tool_name, inputs, outputs,       │   │    │
                        │   │   │     timing, cost, model_id, token counts                  │   │    │
                        │   │   │  2. Compute SHA-256 hash: H(prev_hash || event_data)      │   │    │
                        │   │   │  3. Emit to SQS FIFO (async, non-blocking)                │   │    │
                        │   │   └─────────────────────────┬────────────────────────────────┘   │    │
                        │   └──────────────────────────────┼──────────────────────────────────┘    │
                        │                                  │                                       │
                        │   ┌──────────────────────────────┼──────────────────────────────────┐    │
                        │   │  AgentCore Gateway (MCP, SEMANTIC search)                       │    │
                        │   │  Targets: 10 Lambda functions as MCP tools                      │    │
                        │   └──────────────────────────────┼──────────────────────────────────┘    │
                        └──────────────────────────────────┼───────────────────────────────────────┘
                                                           │
                              ┌─────────────────────────────┤
                              │                             │
                              ▼                             ▼
                 ┌────────────────────────┐    ┌────────────────────────┐
                 │  SQS FIFO Queue        │    │  Lambda Tool Functions │
                 │  traceforge-prov.fifo  │    │  (10 functions)        │
                 │                        │    │                        │
                 │  MessageGroupId:       │    │  Each reads/writes:    │
                 │    = trace_id          │    │  - DynamoDB tables     │
                 │  Dedup:               │    │  - Neo4j Aura (Cypher) │
                 │    = step_id          │    │  - S3 (documents)      │
                 │  Visibility: 30s      │    └────────────────────────┘
                 │  DLQ: traceforge-dlq  │
                 └───────────┬────────────┘
                             │
                             ▼
                 ┌────────────────────────┐
                 │  Lambda:               │
                 │  ProvenanceWriter      │
                 │                        │
                 │  Trigger: SQS          │
                 │  Batch: 10 msgs        │
                 │  Window: 5s            │
                 │                        │
                 │  For each event:       │
                 │  1. Validate hash chain│
                 │  2. CREATE Cypher:     │
                 │     :ReasoningStep     │
                 │     + edges            │
                 │  3. Batch write to     │
                 │     Neo4j via bolt     │
                 └───────────┬────────────┘
                             │
                             ▼
                 ┌────────────────────────────────────────────────────┐
                 │                Neo4j Aura (bolt)                   │
                 │                                                    │
                 │  ┌──────────────────────────────────────────────┐  │
                 │  │  Provenance Graph                             │  │
                 │  │                                               │  │
                 │  │  (:Tenant)                                    │  │
                 │  │    -[:HAS_SESSION]-> (:Session)               │  │
                 │  │      -[:HAS_TRACE]-> (:ReasoningTrace)        │  │
                 │  │        -[:HAS_STEP]-> (:ReasoningStep)        │  │
                 │  │          -[:NEXT_STEP]-> (:ReasoningStep)     │  │
                 │  │          -[:USES_TOOL]-> (:ToolCall)           │  │
                 │  │          -[:TOUCHED]-> (:Entity)               │  │
                 │  │          -[:DECIDED_ON]-> (:CreditApplication) │  │
                 │  │        -[:INITIATED_BY]-> (:Message)           │  │
                 │  │                                               │  │
                 │  │  (:CreditApplication)                         │  │
                 │  │    -[:HAS_FINANCIALS]-> (:FinancialStatement)  │  │
                 │  │    -[:HAS_ASSESSMENT]-> (:RiskAssessment)      │  │
                 │  │    -[:HAS_MEMO]-> (:DecisionMemo)              │  │
                 │  └──────────────────────────────────────────────┘  │
                 │                                                    │
                 │  Indexes: vector (task_embedding, entity embedding)│
                 │  Full-text: Message.content                        │
                 │  Range: created_at on all time-series nodes        │
                 │  GDS: community detection, centrality, pathfinding │
                 └────────────────────────┬───────────────────────────┘
                                          │
                              ┌────────────┼────────────┐
                              │            │            │
                              ▼            ▼            ▼
                 ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                 │  "Why?" API  │ │  Cost API    │ │  Audit API   │
                 │  Lambda      │ │  Lambda      │ │  Lambda      │
                 │              │ │              │ │              │
                 │  Input:      │ │  Input:      │ │  Input:      │
                 │  decision_id │ │  tenant_id   │ │  trace_id    │
                 │              │ │  date_range  │ │              │
                 │  Output:     │ │              │ │  Output:     │
                 │  provenance  │ │  Output:     │ │  PDF report  │
                 │  subgraph    │ │  cost by     │ │  EU AI Act   │
                 │  (JSON)      │ │  agent/tool/ │ │  Article 12  │
                 │              │ │  decision    │ │  compliant   │
                 └──────────────┘ └──────────────┘ └──────────────┘
                              │            │            │
                              ▼            ▼            ▼
                 ┌────────────────────────────────────────────────────┐
                 │              Next.js Dashboard                      │
                 │                                                    │
                 │  / ── Live SSE stream of provenance graph forming  │
                 │  /why/{id} ── Provenance explorer (interactive)    │
                 │  /cost ── Cost attribution dashboard               │
                 │  /audit ── Audit report generator                  │
                 │  /graph ── Neo4j NVL visualization                 │
                 └────────────────────────────────────────────────────┘
```

### 3.2 Data Flow — Step by Step

1. User sends a credit application request to the AgentCore Runtime endpoint
2. Strands Swarm receives the prompt via `BedrockAgentCoreApp.entrypoint`
3. `BeforeMultiAgentInvocationEvent` fires → ProvenanceHook creates a `:ReasoningTrace` event → SQS
4. Swarm routes to **Researcher** agent (first node in DAG)
5. `BeforeNodeCallEvent` fires for Researcher → ProvenanceHook emits "agent_started" → SQS
6. Researcher calls `fetch_sec_filings` tool via Gateway
7. `BeforeToolCallEvent` fires → ProvenanceHook emits "tool_call_started" → SQS
8. Gateway invokes `traceforge-fetch-sec-filings` Lambda → reads from DynamoDB / external API
9. Lambda returns financial data
10. `AfterToolCallEvent` fires → ProvenanceHook captures result + latency + cost → SQS
11. Researcher calls 2 more tools (fetch_credit_scores, fetch_news_sentiment)
12. Steps 7-10 repeat for each tool call
13. Researcher formulates its finding and passes to Analyst
14. `AfterNodeCallEvent` fires for Researcher → ProvenanceHook emits "agent_completed" → SQS
15. `BeforeNodeCallEvent` fires for Analyst
16. Analyst calls `compute_risk_score`, `validate_against_rules`, `compare_historical_decisions`
17. Steps 7-10 repeat for each
18. Analyst formulates risk assessment, passes to Writer
19. `AfterNodeCallEvent` fires for Analyst
20. `BeforeNodeCallEvent` fires for Writer
21. Writer calls `draft_memo`, `check_compliance`, `submit_decision`
22. Steps 7-10 repeat
23. Writer produces final memo
24. `AfterNodeCallEvent` fires for Writer
25. `AfterMultiAgentInvocationEvent` fires → ProvenanceHook emits "swarm_completed" → SQS

**Concurrently throughout steps 3-25:**
- ProvenanceWriter Lambda polls SQS FIFO queue
- For each batch of messages:
  a. Validates hash chain integrity (step N's prev_hash == step N-1's step_hash)
  b. Writes `:ReasoningStep` nodes to Neo4j with all properties
  c. Creates `:USES_TOOL` edges for tool calls
  d. Creates `:TOUCHED` edges for entity references
  e. Creates `:NEXT_STEP` edges for sequential ordering
  f. Updates `:ReasoningTrace` aggregates (total_cost, total_latency)
- Frontend SSE endpoint streams new nodes/edges to the dashboard in real time

### 3.3 Hash Chain Integrity Model

Every `:ReasoningStep` has two hash fields that make the provenance chain tamper-evident:

```
step_hash = SHA-256(
    prev_hash +            # hash of prior step (or "GENESIS" for first step)
    trace_id +             # which trace this belongs to
    agent_name +           # which agent produced this step
    step_number +          # position in sequence
    tool_name +            # tool called (or "REASONING" for pure thought)
    arguments_json +       # serialized tool arguments
    result_json +          # serialized tool result
    created_at_iso         # timestamp
)
```

Verification: walk the chain from step 0 to step N, recomputing each hash. If any hash
doesn't match, the step was tampered with. This satisfies EU AI Act Article 12's requirement
for "tamper-proof event logs."

---

## 4. Prerequisites Checklist

### 4.1 Software Requirements (on your MacBook)

```
Required software and minimum versions:
- Python 3.11+           (for Strands, neo4j-agent-memory, Lambdas)
- Node.js 18+            (for frontend, agentcore CLI, npx create-context-graph)
- uv                     (Python package manager — faster than pip)
- AWS CLI v2             (configured with credentials)
- gh CLI                 (GitHub CLI — for repo creation)
- Docker Desktop         (for AgentCore Runtime container build via CodeBuild)
- git                    (obviously)
- jq                     (JSON processing for boto3 output parsing)
- zip                    (for Lambda deployment packages)
```

### 4.2 AWS Account Requirements

```
Services that must be accessible in your account:
- Amazon Bedrock         (Claude Sonnet 4 model enabled in us-east-1 or us-west-2)
- Amazon Bedrock AgentCore (Runtime, Gateway, Identity — GA since Oct 2025)
- AWS Lambda             (for tool functions + ProvenanceWriter)
- Amazon DynamoDB        (for credit application data)
- Amazon SQS             (FIFO queue for async provenance writes)
- Amazon S3              (for audit report storage + Lambda deployment)
- AWS IAM                (role creation permissions)
- AWS Secrets Manager    (for Neo4j credentials)
- AWS CodeBuild          (for AgentCore container image build)
- Amazon ECR             (for container image storage)
- Amazon CloudWatch      (for logs)
```

### 4.3 Neo4j Requirements

```
- Neo4j Aura instance (free tier works for demo; paid for GDS)
  OR
- Hackathon-provided Aura credentials (check event briefing / Slack)
- APOC plugin enabled (required for some utility functions)
- Bolt driver access from Lambda (public endpoint for Aura)
```

### 4.4 API Keys Required

```
Environment variable              Purpose                              Source
─────────────────────────────────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID                 AWS account access                   aws configure
AWS_SECRET_ACCESS_KEY             AWS account access                   aws configure
AWS_DEFAULT_REGION                us-east-1 or us-west-2              aws configure
NEO4J_URI                        Neo4j Aura bolt endpoint             console.neo4j.io
NEO4J_USERNAME                   Neo4j username (usually "neo4j")     console.neo4j.io
NEO4J_PASSWORD                   Neo4j password                       console.neo4j.io
ANTHROPIC_API_KEY                 Local Strands testing (optional)     console.anthropic.com
```

### 4.5 Bedrock Model Access Verification

Before building, verify Claude Sonnet 4 is enabled:

```bash
aws bedrock list-foundation-models \
  --query "modelSummaries[?modelId=='us.anthropic.claude-sonnet-4-5-20250514'].{id:modelId,status:modelLifecycle.status}" \
  --output table
```

If not enabled, go to AWS Console → Bedrock → Model Access → Request access.
This can take 5-15 minutes for approval.

---

## 5. Phase 0: Environment Bootstrap

### 5.0 Time Budget: 15 minutes

### 5.1 Verify All Prerequisites

```bash
# Run these checks — every one must pass before proceeding

# Python
python3 --version  # Must be 3.11+

# Node.js
node --version     # Must be 18+

# uv
uv --version       # Any version

# AWS CLI
aws --version      # Must be v2
aws sts get-caller-identity  # Must return your account

# GitHub CLI
gh auth status     # Must be authenticated

# Docker
docker info        # Must be running

# jq
jq --version       # Any version

# git
git --version      # Any version
```

### 5.2 Create Project Directory Structure

```bash
mkdir -p ~/traceforge
cd ~/traceforge

# Create full directory tree
mkdir -p backend/app
mkdir -p backend/hooks
mkdir -p backend/scripts
mkdir -p backend/tests
mkdir -p lambda_functions/provenance_writer
mkdir -p lambda_functions/fetch_sec_filings
mkdir -p lambda_functions/fetch_credit_scores
mkdir -p lambda_functions/fetch_news_sentiment
mkdir -p lambda_functions/query_knowledge_graph
mkdir -p lambda_functions/compute_risk_score
mkdir -p lambda_functions/validate_rules
mkdir -p lambda_functions/compare_historical
mkdir -p lambda_functions/draft_memo
mkdir -p lambda_functions/check_compliance
mkdir -p lambda_functions/submit_decision
mkdir -p lambda_functions/why_query
mkdir -p lambda_functions/cost_query
mkdir -p lambda_functions/audit_export
mkdir -p infrastructure
mkdir -p frontend
mkdir -p cypher
mkdir -p data
mkdir -p tool_schemas
mkdir -p deploy
mkdir -p docs
```

### 5.3 Initialize Git Repository

```bash
cd ~/traceforge
git init
git checkout -b main

# Create .gitignore
cat > .gitignore << 'GITIGNORE'
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/

# Node
node_modules/
.next/
out/

# Environment
.env
.env.local
*.env

# AWS
.aws/
lambda_packages/
*.zip

# Neo4j
neo4j-data/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Test
.pytest_cache/
htmlcov/
.coverage
GITIGNORE

# Create .env.example (tracked)
cat > .env.example << 'ENVEXAMPLE'
# AWS (configured via aws cli, not needed here unless overriding)
# AWS_DEFAULT_REGION=us-east-1

# Neo4j Aura
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password-here

# Optional: for local Strands testing (AgentCore uses Bedrock directly)
# ANTHROPIC_API_KEY=sk-ant-...

# SQS (set after infrastructure provisioning)
# SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/traceforge-provenance.fifo

# AgentCore (set after deployment)
# AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:123456789:agent-runtime/...
# AGENTCORE_GATEWAY_URL=https://...
ENVEXAMPLE
```

### 5.4 Create GitHub Repository

```bash
cd ~/traceforge
gh repo create traceforge \
  --public \
  --description "Production-grade cross-agent decision provenance on Neo4j + AWS Strands + Bedrock AgentCore" \
  --source . \
  --push
```

### 5.5 Install Global Tools

```bash
# Python project setup
cd ~/traceforge
uv venv --python 3.11
source .venv/bin/activate

# Install core dependencies
uv pip install \
  strands-agents==1.40.0 \
  'strands-agents[otel]' \
  bedrock-agentcore>=1.1.0 \
  neo4j>=5.20.0 \
  neo4j-agent-memory>=0.4.0 \
  'neo4j-agent-memory[aws,strands]' \
  boto3>=1.35.0 \
  pydantic>=2.0.0 \
  python-dotenv \
  pytest \
  httpx \
  uvicorn \
  fastapi

# Install create-context-graph (for reference scaffolding)
uv pip install create-context-graph
```

### 5.6 Create pyproject.toml

```toml
[project]
name = "traceforge"
version = "0.1.0"
description = "Cross-agent decision provenance on Neo4j + Strands + AgentCore"
requires-python = ">=3.11"
dependencies = [
    "strands-agents>=1.40.0",
    "strands-agents[otel]",
    "bedrock-agentcore>=1.1.0",
    "neo4j>=5.20.0",
    "neo4j-agent-memory[aws,strands]>=0.4.0",
    "boto3>=1.35.0",
    "pydantic>=2.0.0",
    "python-dotenv",
    "fastapi>=0.115.0",
    "uvicorn>=0.30.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "ruff"]
lambda = ["neo4j>=5.20.0", "boto3>=1.35.0"]

[tool.ruff]
target-version = "py311"
line-length = 100
```

### 5.7 Create Makefile

```makefile
.PHONY: install start seed test lint deploy clean

install:
	uv venv --python 3.11
	uv pip install -e ".[dev]"
	cd frontend && npm install

start:
	@echo "Starting backend..."
	cd backend && uvicorn app.main:app --reload --port 8000 &
	@echo "Starting frontend..."
	cd frontend && npm run dev &
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"

seed:
	cd backend && python scripts/seed_data.py

test:
	pytest backend/tests/ -v

lint:
	ruff check backend/ lambda_functions/

schema:
	cd cypher && python ../backend/scripts/apply_schema.py

deploy-lambdas:
	cd infrastructure && python deploy_lambdas.py

deploy-agentcore:
	cd deploy && python deploy_runtime.py

deploy: deploy-lambdas deploy-agentcore

clean:
	rm -rf .venv node_modules frontend/.next lambda_packages/

why:
	@read -p "Decision ID: " id; \
	curl -s "http://localhost:8000/api/why/$$id" | jq .

cost:
	@read -p "Tenant ID: " tid; \
	curl -s "http://localhost:8000/api/cost?tenant_id=$$tid" | jq .

audit:
	@read -p "Trace ID: " tid; \
	curl -s -X POST "http://localhost:8000/api/audit/$$tid" -o audit_report.pdf
	@echo "Saved to audit_report.pdf"
```

---

## 6. Phase 1: Infrastructure Provisioning

### 6.0 Time Budget: 20 minutes (Team Deploy owns this)

### 6.1 Neo4j Aura Instance

**Option A: Hackathon-provided (check event briefing)**
The event listing says "a Neo4j Aura instance will be provided" for the workshop part.
Check if those credentials work for your custom project too. If so, use them.

**Option B: Create your own free Aura instance**

```
1. Go to console.neo4j.io
2. Sign in / Create account
3. Click "New Instance"
4. Select "AuraDB Free" (or use hackathon credits for Professional)
5. Instance name: "traceforge"
6. Region: us-east-1 (same as AgentCore deployment)
7. Click "Create"
8. DOWNLOAD THE CREDENTIALS FILE — this is the only time you see the password
9. Wait for instance to be "Running" (1-3 minutes)
10. Record:
    NEO4J_URI=neo4j+s://<instance-id>.databases.neo4j.io
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=<from downloaded file>
```

**Free tier limits (important for demo):**
- 200K nodes, 400K relationships (plenty for demo)
- 1 database
- No GDS (Graph Data Science) — need Professional for GDS algorithms
- APOC available

**Verify connectivity:**

```bash
# Quick test with Python
python3 -c "
from neo4j import GraphDatabase
import os
driver = GraphDatabase.driver(
    os.environ['NEO4J_URI'],
    auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD'])
)
driver.verify_connectivity()
print('Connected to Neo4j Aura')
driver.close()
"
```

### 6.2 AWS Secrets Manager — Store Neo4j Credentials

```bash
aws secretsmanager create-secret \
  --name traceforge/neo4j-credentials \
  --description "Neo4j Aura credentials for TraceForge" \
  --secret-string '{
    "uri": "'$NEO4J_URI'",
    "username": "'$NEO4J_USERNAME'",
    "password": "'$NEO4J_PASSWORD'"
  }'
```

Record the ARN:
```bash
NEO4J_SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id traceforge/neo4j-credentials \
  --query 'ARN' --output text)
echo "NEO4J_SECRET_ARN=$NEO4J_SECRET_ARN"
```

### 6.3 DynamoDB Tables

**Table 1: Credit Applications**

```bash
aws dynamodb create-table \
  --table-name traceforge-CreditApplications \
  --attribute-definitions \
    AttributeName=application_id,AttributeType=S \
  --key-schema \
    AttributeName=application_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=TraceForge
```

Schema:
```
{
  "application_id": "S",          # Primary key
  "tenant_id": "S",               # Tenant identifier
  "applicant_name": "S",          # Name of person/company applying
  "company_name": "S",            # Company being evaluated
  "requested_amount": "N",        # Credit amount requested (USD)
  "currency": "S",                # Always "USD" for demo
  "application_type": "S",        # "CORPORATE_CREDIT" | "TRADE_FINANCE" | "BOND_ISSUANCE"
  "status": "S",                  # "SUBMITTED" | "IN_REVIEW" | "APPROVED" | "DENIED"
  "submitted_at": "S",            # ISO 8601 timestamp
  "decision_at": "S",             # ISO 8601 timestamp (after decision)
  "decision_trace_id": "S",       # Links to Neo4j :ReasoningTrace
  "metadata": "M"                 # Additional structured data
}
```

**Table 2: Financial Data**

```bash
aws dynamodb create-table \
  --table-name traceforge-FinancialData \
  --attribute-definitions \
    AttributeName=entity_id,AttributeType=S \
    AttributeName=data_type,AttributeType=S \
  --key-schema \
    AttributeName=entity_id,KeyType=HASH \
    AttributeName=data_type,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=TraceForge
```

Schema:
```
{
  "entity_id": "S",               # e.g., "ACME_CORP"
  "data_type": "S",               # "SEC_10K_2025" | "CREDIT_SCORE" | "NEWS_SENTIMENT"
  "company_name": "S",
  "period": "S",                   # e.g., "FY2025", "Q1_2026"
  "revenue": "N",                  # Revenue in USD
  "net_income": "N",               # Net income in USD
  "total_assets": "N",
  "total_liabilities": "N",
  "debt_to_equity": "N",
  "current_ratio": "N",
  "credit_score": "N",             # 0-100 internal score
  "credit_rating": "S",            # "AAA" through "D"
  "sentiment_score": "N",          # -1.0 to 1.0
  "sentiment_articles_count": "N",
  "source": "S",                   # "SEC_EDGAR" | "INTERNAL_MODEL" | "NEWS_API"
  "retrieved_at": "S",             # ISO 8601
  "is_poisoned": "BOOL"            # ONLY for demo data — marks injected bad data
}
```

**Table 3: Decision Rules (for guardrails)**

```bash
aws dynamodb create-table \
  --table-name traceforge-DecisionRules \
  --attribute-definitions \
    AttributeName=rule_id,AttributeType=S \
  --key-schema \
    AttributeName=rule_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=TraceForge
```

Schema:
```
{
  "rule_id": "S",                  # "RULE_001", "RULE_002", etc.
  "rule_name": "S",               # Human-readable name
  "action": "S",                   # "approve_credit" | "deny_credit" | "any"
  "condition_field": "S",          # "requested_amount" | "debt_to_equity" | "credit_score"
  "operator": "S",                 # "gt" | "lt" | "gte" | "lte" | "eq"
  "threshold": "N",               # Numeric threshold
  "fail_message": "S",            # "Credit amount exceeds maximum for this risk tier"
  "steer_message": "S",           # "Consider reducing the credit amount to below $X"
  "severity": "S",                # "BLOCK" | "WARN" | "INFO"
  "enabled": "BOOL"
}
```

### 6.4 SQS FIFO Queue

```bash
# Main provenance queue
aws sqs create-queue \
  --queue-name traceforge-provenance.fifo \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "VisibilityTimeout": "30",
    "MessageRetentionPeriod": "86400",
    "ReceiveMessageWaitTimeSeconds": "10"
  }' \
  --tags Project=TraceForge

# Dead letter queue for failed writes
aws sqs create-queue \
  --queue-name traceforge-provenance-dlq.fifo \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "MessageRetentionPeriod": "1209600"
  }' \
  --tags Project=TraceForge
```

Get queue URLs and ARNs:
```bash
SQS_QUEUE_URL=$(aws sqs get-queue-url \
  --queue-name traceforge-provenance.fifo \
  --query 'QueueUrl' --output text)

SQS_DLQ_URL=$(aws sqs get-queue-url \
  --queue-name traceforge-provenance-dlq.fifo \
  --query 'QueueUrl' --output text)

SQS_QUEUE_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

SQS_DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url "$SQS_DLQ_URL" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)
```

Set redrive policy (3 retries before DLQ):
```bash
aws sqs set-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" \
  --attributes '{
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"'$SQS_DLQ_ARN'\",\"maxReceiveCount\":\"3\"}"
  }'
```

### 6.5 S3 Bucket

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

aws s3 mb "s3://traceforge-${ACCOUNT_ID}-${REGION}" --region "$REGION"
```

### 6.6 IAM Roles

**Role 1: Lambda Execution Role**

```bash
# Trust policy
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name TraceForge-LambdaExecutionRole \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
  --tags Key=Project,Value=TraceForge

# Permissions policy
cat > /tmp/lambda-permissions.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DynamoDBAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/traceforge-*"
      ]
    },
    {
      "Sid": "SQSAccess",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:SendMessage"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:traceforge-*"
      ]
    },
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:traceforge/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::traceforge-*/audit-reports/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name TraceForge-LambdaExecutionRole \
  --policy-name TraceForge-LambdaPermissions \
  --policy-document file:///tmp/lambda-permissions.json

LAMBDA_ROLE_ARN=$(aws iam get-role \
  --role-name TraceForge-LambdaExecutionRole \
  --query 'Role.Arn' --output text)
```

**Role 2: AgentCore Execution Role**

```bash
# Trust policy
cat > /tmp/agentcore-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "bedrock-agentcore.amazonaws.com",
          "bedrock.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name TraceForge-AgentCoreExecutionRole \
  --assume-role-policy-document file:///tmp/agentcore-trust-policy.json \
  --tags Key=Project,Value=TraceForge

# Permissions policy
cat > /tmp/agentcore-permissions.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    },
    {
      "Sid": "LambdaInvoke",
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:*:*:function:traceforge-*"
      ]
    },
    {
      "Sid": "SQSSend",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage"
      ],
      "Resource": [
        "arn:aws:sqs:*:*:traceforge-provenance.fifo"
      ]
    },
    {
      "Sid": "DynamoDBRead",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/traceforge-*"
      ]
    },
    {
      "Sid": "SecretsAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:traceforge/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name TraceForge-AgentCoreExecutionRole \
  --policy-name TraceForge-AgentCorePermissions \
  --policy-document file:///tmp/agentcore-permissions.json

AGENTCORE_ROLE_ARN=$(aws iam get-role \
  --role-name TraceForge-AgentCoreExecutionRole \
  --query 'Role.Arn' --output text)
```

**Wait for IAM propagation:**
```bash
sleep 10  # IAM roles need a few seconds to propagate before use
```

### 6.7 Verify All Infrastructure

```bash
echo "=== Infrastructure Verification ==="

echo "DynamoDB tables:"
aws dynamodb list-tables --query 'TableNames[?starts_with(@, `traceforge`)]'

echo "SQS queues:"
aws sqs list-queues --queue-name-prefix traceforge

echo "IAM roles:"
aws iam list-roles --query 'Roles[?starts_with(RoleName, `TraceForge`)].RoleName'

echo "Secrets:"
aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name, `traceforge`)].Name'

echo "S3 bucket:"
aws s3 ls | grep traceforge

echo "Neo4j connectivity:"
python3 -c "
from neo4j import GraphDatabase
import os
d = GraphDatabase.driver(os.environ['NEO4J_URI'],
    auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD']))
d.verify_connectivity()
print('Neo4j: CONNECTED')
d.close()
"
```

---

## 7. Phase 2: Neo4j Schema — Complete Graph Model

### 7.0 Time Budget: 20 minutes (Team Graph owns this)

### 7.1 Full Schema — Constraints

```cypher
// === UNIQUENESS CONSTRAINTS ===
// Every node type has a unique identifier

CREATE CONSTRAINT tenant_id_unique IF NOT EXISTS
FOR (t:Tenant) REQUIRE t.tenant_id IS UNIQUE;

CREATE CONSTRAINT session_id_unique IF NOT EXISTS
FOR (s:Session) REQUIRE s.session_id IS UNIQUE;

CREATE CONSTRAINT message_id_unique IF NOT EXISTS
FOR (m:Message) REQUIRE m.message_id IS UNIQUE;

CREATE CONSTRAINT trace_id_unique IF NOT EXISTS
FOR (rt:ReasoningTrace) REQUIRE rt.trace_id IS UNIQUE;

CREATE CONSTRAINT step_id_unique IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.step_id IS UNIQUE;

CREATE CONSTRAINT tool_call_id_unique IF NOT EXISTS
FOR (tc:ToolCall) REQUIRE tc.call_id IS UNIQUE;

CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

CREATE CONSTRAINT application_id_unique IF NOT EXISTS
FOR (ca:CreditApplication) REQUIRE ca.application_id IS UNIQUE;

CREATE CONSTRAINT financial_statement_id_unique IF NOT EXISTS
FOR (fs:FinancialStatement) REQUIRE fs.statement_id IS UNIQUE;

CREATE CONSTRAINT risk_assessment_id_unique IF NOT EXISTS
FOR (ra:RiskAssessment) REQUIRE ra.assessment_id IS UNIQUE;

CREATE CONSTRAINT decision_memo_id_unique IF NOT EXISTS
FOR (dm:DecisionMemo) REQUIRE dm.memo_id IS UNIQUE;

// === EXISTENCE CONSTRAINTS (data integrity) ===

CREATE CONSTRAINT step_hash_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.step_hash IS NOT NULL;

CREATE CONSTRAINT step_prev_hash_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.prev_hash IS NOT NULL;

CREATE CONSTRAINT step_trace_id_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.trace_id IS NOT NULL;

CREATE CONSTRAINT step_agent_name_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.agent_name IS NOT NULL;

CREATE CONSTRAINT trace_tenant_id_exists IF NOT EXISTS
FOR (rt:ReasoningTrace) REQUIRE rt.tenant_id IS NOT NULL;

CREATE CONSTRAINT trace_task_exists IF NOT EXISTS
FOR (rt:ReasoningTrace) REQUIRE rt.task IS NOT NULL;
```

### 7.2 Full Schema — Indexes

```cypher
// === VECTOR INDEXES (for similarity search) ===

CREATE VECTOR INDEX trace_task_embedding IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.task_embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

CREATE VECTOR INDEX step_embedding IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
FOR (e:Entity)
ON (e.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

// === FULL-TEXT INDEXES (for keyword search) ===

CREATE FULLTEXT INDEX message_content_ft IF NOT EXISTS
FOR (m:Message)
ON EACH [m.content];

CREATE FULLTEXT INDEX step_thought_ft IF NOT EXISTS
FOR (rs:ReasoningStep)
ON EACH [rs.thought, rs.observation];

CREATE FULLTEXT INDEX entity_description_ft IF NOT EXISTS
FOR (e:Entity)
ON EACH [e.name, e.description];

// === RANGE INDEXES (for time-series queries) ===

CREATE INDEX step_created_at IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.created_at);

CREATE INDEX trace_started_at IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.started_at);

CREATE INDEX trace_completed_at IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.completed_at);

CREATE INDEX tool_call_created_at IF NOT EXISTS
FOR (tc:ToolCall)
ON (tc.created_at);

CREATE INDEX message_created_at IF NOT EXISTS
FOR (m:Message)
ON (m.created_at);

// === COMPOSITE INDEXES (for efficient lookups) ===

CREATE INDEX step_trace_number IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.trace_id, rs.step_number);

CREATE INDEX step_agent_name IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.agent_name);

CREATE INDEX trace_tenant IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.tenant_id);

CREATE INDEX entity_type IF NOT EXISTS
FOR (e:Entity)
ON (e.type);

CREATE INDEX application_status IF NOT EXISTS
FOR (ca:CreditApplication)
ON (ca.status);

CREATE INDEX application_tenant IF NOT EXISTS
FOR (ca:CreditApplication)
ON (ca.tenant_id);
```

### 7.3 Full Schema — Node Labels with Every Property

```
NODE: :Tenant
  Properties:
    tenant_id       STRING    UNIQUE       "tenant_acme"
    name            STRING                 "Acme Financial Services"
    plan            STRING                 "ENTERPRISE" | "STARTUP" | "DEMO"
    created_at      DATETIME               2026-05-19T15:00:00Z

NODE: :Session
  Properties:
    session_id      STRING    UNIQUE       "sess_abc123"
    tenant_id       STRING                 "tenant_acme"
    started_at      DATETIME               2026-05-19T17:30:00Z
    ended_at        DATETIME  NULLABLE     2026-05-19T17:35:00Z
    status          STRING                 "ACTIVE" | "COMPLETED" | "FAILED"
    user_id         STRING    NULLABLE     "user_analyst_01"

NODE: :Message
  Properties:
    message_id      STRING    UNIQUE       "msg_xyz789"
    session_id      STRING                 "sess_abc123"
    role            STRING                 "user" | "assistant" | "system" | "tool"
    content         STRING                 "Evaluate credit application for Acme Corp..."
    created_at      DATETIME               2026-05-19T17:30:01Z

NODE: :ReasoningTrace
  Properties:
    trace_id        STRING    UNIQUE       "trace_def456"
    tenant_id       STRING    NOT NULL     "tenant_acme"
    session_id      STRING                 "sess_abc123"
    task            STRING    NOT NULL     "Evaluate credit application APP-2026-001"
    task_embedding  FLOAT[]                [0.012, -0.034, ...] (1536 dims)
    outcome         STRING    NULLABLE     "APPROVED" | "DENIED" | "FAILED" | "PENDING"
    success         BOOLEAN   NULLABLE     true
    started_at      DATETIME               2026-05-19T17:30:02Z
    completed_at    DATETIME  NULLABLE     2026-05-19T17:34:58Z
    total_cost_usd  FLOAT     DEFAULT 0    0.43
    total_latency_ms INTEGER  DEFAULT 0    295000
    agent_count     INTEGER   DEFAULT 0    3
    step_count      INTEGER   DEFAULT 0    12
    model_ids       STRING[]               ["claude-sonnet-4", "claude-sonnet-4"]
    metadata        MAP       NULLABLE     {priority: "HIGH", source: "API"}

NODE: :ReasoningStep
  Properties:
    step_id         STRING    UNIQUE       "step_ghi012"
    trace_id        STRING    NOT NULL     "trace_def456"
    agent_name      STRING    NOT NULL     "Researcher"
    agent_role      STRING                 "FINANCIAL_DATA_RETRIEVAL"
    thought         STRING    NULLABLE     "I need to fetch the latest SEC 10-K filing..."
    action          STRING    NULLABLE     "fetch_sec_filings"
    observation     STRING    NULLABLE     "Retrieved 10-K for Acme Corp FY2025..."
    embedding       FLOAT[]   NULLABLE     [0.023, -0.015, ...] (1536 dims)
    step_number     INTEGER   NOT NULL     1
    cost_usd        FLOAT     DEFAULT 0    0.0023
    latency_ms      INTEGER   DEFAULT 0    4500
    model_id        STRING    NULLABLE     "us.anthropic.claude-sonnet-4-5-20250514"
    token_input     INTEGER   DEFAULT 0    1200
    token_output    INTEGER   DEFAULT 0    850
    prev_hash       STRING    NOT NULL     "GENESIS" (for first step) or SHA-256
    step_hash       STRING    NOT NULL     SHA-256 of (prev_hash + trace + agent + step + ...)
    status          STRING                 "STARTED" | "COMPLETED" | "FAILED" | "SKIPPED"
    created_at      DATETIME               2026-05-19T17:30:03Z
    event_type      STRING                 "AGENT_START" | "TOOL_CALL" | "MODEL_CALL" |
                                           "AGENT_END" | "SWARM_START" | "SWARM_END"

NODE: :ToolCall
  Properties:
    call_id         STRING    UNIQUE       "call_jkl345"
    step_id         STRING                 "step_ghi012"
    tool_name       STRING    NOT NULL     "fetch_sec_filings"
    arguments       MAP                    {company: "ACME_CORP", period: "FY2025"}
    result          STRING    NULLABLE     "{\"revenue\": 50000000, ...}" (JSON string)
    result_summary  STRING    NULLABLE     "Retrieved 10-K: revenue $50M, net income $8M"
    status          STRING                 "PENDING" | "SUCCESS" | "FAILURE" | "ERROR" | "TIMEOUT"
    duration_ms     INTEGER   DEFAULT 0    2100
    cost_usd        FLOAT     DEFAULT 0    0.0001  (Lambda invocation cost)
    error_message   STRING    NULLABLE     null
    created_at      DATETIME               2026-05-19T17:30:03Z

NODE: :Entity (base label — always combined with a POLE+O sub-label)
  Sub-labels: :Person, :Organization, :Location, :Event, :Object
  Properties:
    entity_id       STRING    UNIQUE       "ent_acme_corp"
    name            STRING    NOT NULL     "Acme Corporation"
    type            STRING    NOT NULL     "Organization"
    description     STRING    NULLABLE     "Fortune 500 manufacturing conglomerate..."
    embedding       FLOAT[]   NULLABLE     [0.045, -0.022, ...] (1536 dims)
    created_at      DATETIME               2026-05-19T17:30:04Z
    updated_at      DATETIME               2026-05-19T17:30:04Z
    source          STRING    NULLABLE     "SEC_EDGAR"

NODE: :CreditApplication
  Properties:
    application_id  STRING    UNIQUE       "APP-2026-001"
    tenant_id       STRING                 "tenant_acme"
    applicant_name  STRING                 "John Smith, CFO"
    company_name    STRING                 "Acme Corporation"
    requested_amount FLOAT                 5000000.00
    currency        STRING                 "USD"
    application_type STRING                "CORPORATE_CREDIT"
    status          STRING                 "SUBMITTED" | "IN_REVIEW" | "APPROVED" | "DENIED"
    submitted_at    DATETIME               2026-05-19T17:29:00Z
    decision_at     DATETIME  NULLABLE     2026-05-19T17:34:58Z
    risk_score      FLOAT     NULLABLE     72.5
    risk_category   STRING    NULLABLE     "MODERATE"
    decision        STRING    NULLABLE     "APPROVED"
    decision_trace_id STRING  NULLABLE     "trace_def456"

NODE: :FinancialStatement
  Properties:
    statement_id    STRING    UNIQUE       "fin_acme_fy2025"
    company_name    STRING                 "Acme Corporation"
    period          STRING                 "FY2025"
    revenue         FLOAT                  50000000.00
    net_income      FLOAT                  8000000.00
    total_assets    FLOAT                  120000000.00
    total_liabilities FLOAT                45000000.00
    debt_to_equity  FLOAT                  0.60
    current_ratio   FLOAT                  2.1
    source          STRING                 "SEC_EDGAR"
    retrieved_at    DATETIME               2026-05-19T17:30:05Z
    is_poisoned     BOOLEAN   DEFAULT false  false

NODE: :RiskAssessment
  Properties:
    assessment_id   STRING    UNIQUE       "risk_001"
    application_id  STRING                 "APP-2026-001"
    risk_score      FLOAT                  72.5
    risk_category   STRING                 "LOW" | "MODERATE" | "HIGH" | "CRITICAL"
    factors         STRING[]               ["debt_to_equity_ok", "revenue_growth_positive", ...]
    model_version   STRING                 "v2.1"
    created_at      DATETIME               2026-05-19T17:32:00Z

NODE: :DecisionMemo
  Properties:
    memo_id         STRING    UNIQUE       "memo_001"
    application_id  STRING                 "APP-2026-001"
    decision        STRING                 "APPROVED" | "DENIED" | "ESCALATED"
    reasoning       STRING                 "Based on strong financials and positive sentiment..."
    conditions      STRING[]  NULLABLE     ["quarterly_review", "collateral_required"]
    compliance_flags STRING[] NULLABLE     ["EU_AI_ACT_ART12"]
    created_at      DATETIME               2026-05-19T17:34:50Z
```

### 7.4 Full Schema — Relationships with Properties

```
RELATIONSHIP: (:Tenant)-[:HAS_SESSION]->(:Session)
  Properties: none

RELATIONSHIP: (:Session)-[:HAS_TRACE]->(:ReasoningTrace)
  Properties: none

RELATIONSHIP: (:ReasoningTrace)-[:HAS_STEP]->(:ReasoningStep)
  Properties:
    step_number     INTEGER               1

RELATIONSHIP: (:ReasoningStep)-[:NEXT_STEP]->(:ReasoningStep)
  Properties: none
  Notes: Creates a linked list of steps within a trace for sequential traversal

RELATIONSHIP: (:ReasoningStep)-[:USES_TOOL]->(:ToolCall)
  Properties: none

RELATIONSHIP: (:ReasoningStep)-[:TOUCHED]->(:Entity)
  Properties:
    access_type     STRING               "READ" | "WRITE" | "CREATE"
    timestamp       DATETIME             2026-05-19T17:30:05Z
  Notes: THE KEY AUDIT EDGE — records which entities each reasoning step consulted

RELATIONSHIP: (:ReasoningStep)-[:TOUCHED]->(:CreditApplication)
  Properties:
    access_type     STRING               "READ" | "WRITE" | "CREATE"
    timestamp       DATETIME

RELATIONSHIP: (:ReasoningStep)-[:TOUCHED]->(:FinancialStatement)
  Properties:
    access_type     STRING               "READ"
    timestamp       DATETIME

RELATIONSHIP: (:ReasoningStep)-[:MENTIONS]->(:Entity)
  Properties: none
  Notes: Weaker than :TOUCHED — entity was referenced in text but not directly acted upon

RELATIONSHIP: (:ReasoningTrace)-[:INITIATED_BY]->(:Message)
  Properties: none
  Notes: Links trace back to the user message that triggered it

RELATIONSHIP: (:Message)-[:NEXT]->(:Message)
  Properties: none
  Notes: Conversation flow within a session

RELATIONSHIP: (:Message)-[:MENTIONS]->(:Entity)
  Properties: none

RELATIONSHIP: (:CreditApplication)-[:HAS_FINANCIALS]->(:FinancialStatement)
  Properties: none

RELATIONSHIP: (:CreditApplication)-[:HAS_ASSESSMENT]->(:RiskAssessment)
  Properties: none

RELATIONSHIP: (:CreditApplication)-[:HAS_MEMO]->(:DecisionMemo)
  Properties: none

RELATIONSHIP: (:ToolCall)-[:RETRIEVED]->(:FinancialStatement)
  Properties: none
  Notes: Links a tool call to the specific data it retrieved — critical for poison tracing

RELATIONSHIP: (:ToolCall)-[:RETRIEVED]->(:Entity)
  Properties: none

RELATIONSHIP: (:ReasoningStep)-[:DECIDED_ON]->(:CreditApplication)
  Properties:
    decision        STRING               "APPROVED" | "DENIED"
  Notes: Only on the final Writer step that submits the decision

RELATIONSHIP: (:Entity)-[:RELATED_TO]->(:Entity)
  Properties:
    relation_type   STRING               "SUBSIDIARY_OF" | "COMPETITOR" | "PARTNER" | "SECTOR"
  Notes: Domain-specific entity relationships in the knowledge graph
```

### 7.5 Schema Application Script

```python
# backend/scripts/apply_schema.py

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

SCHEMA_FILES = [
    "cypher/constraints.cypher",
    "cypher/indexes.cypher",
]

def apply_schema():
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    driver.verify_connectivity()

    for schema_file in SCHEMA_FILES:
        with open(schema_file) as f:
            statements = [
                s.strip() for s in f.read().split(";")
                if s.strip() and not s.strip().startswith("//")
            ]

        with driver.session(database="neo4j") as session:
            for stmt in statements:
                try:
                    session.run(stmt)
                    print(f"  OK: {stmt[:80]}...")
                except Exception as e:
                    print(f"  SKIP: {stmt[:60]}... ({e})")

    driver.close()
    print("Schema applied.")

if __name__ == "__main__":
    apply_schema()
```

---

## 8. Phase 3: Credit Decision Domain Model

### 8.0 Time Budget: 10 minutes (part of Team Graph's work)

### 8.1 Domain Ontology

The credit-decision triage domain has these entity types and relationships:

```yaml
domain: financial-credit-decision
description: "Multi-agent credit decision triage for corporate lending"

entity_types:
  - name: Applicant
    parent_type: Person
    properties: [name, title, company, contact_email]

  - name: Company
    parent_type: Organization
    properties: [name, ticker, sector, country, founded_year, employee_count]

  - name: FinancialStatement
    parent_type: Object
    properties: [period, revenue, net_income, total_assets, total_liabilities,
                 debt_to_equity, current_ratio, source]

  - name: CreditApplication
    parent_type: Object
    properties: [application_id, requested_amount, application_type, status]

  - name: RiskAssessment
    parent_type: Object
    properties: [risk_score, risk_category, factors]

  - name: RegulatoryFiling
    parent_type: Object
    properties: [filing_type, filing_date, filing_url]

  - name: NewsArticle
    parent_type: Object
    properties: [headline, source, published_at, sentiment_score]

  - name: Market
    parent_type: Location
    properties: [name, region, currency]

relationships:
  - type: APPLIED_FOR
    from: Applicant
    to: CreditApplication

  - type: ON_BEHALF_OF
    from: CreditApplication
    to: Company

  - type: FILED
    from: Company
    to: RegulatoryFiling

  - type: HAS_FINANCIALS
    from: Company
    to: FinancialStatement

  - type: OPERATES_IN
    from: Company
    to: Market

  - type: COMPETITOR_OF
    from: Company
    to: Company

  - type: MENTIONED_IN
    from: Company
    to: NewsArticle
```

### 8.2 Three Companies for Demo Data

```
Company 1: Meridian Manufacturing Corp (clean data — will be APPROVED)
  - Sector: Industrial Manufacturing
  - Revenue: $85M, Net Income: $12M
  - Debt/Equity: 0.45, Current Ratio: 2.8
  - Credit Score: 82/100 (AA-)
  - News Sentiment: +0.65 (positive)
  - Requesting: $10M corporate credit line

Company 2: Zenith Biotech Inc (poisoned data — will be WRONG DECISION)
  - Sector: Biotechnology
  - REAL Revenue: $15M, Net Income: -$3M (loss)
  - POISONED Revenue: $150M, Net Income: $25M  ← 10x inflation
  - Debt/Equity: 1.8, Current Ratio: 0.9
  - Credit Score: 41/100 (BB-)
  - News Sentiment: -0.3 (negative — recent FDA rejection)
  - Requesting: $25M trade finance

Company 3: Atlas Logistics Group (edge case — will be ESCALATED)
  - Sector: Transportation & Logistics
  - Revenue: $220M, Net Income: $18M
  - Debt/Equity: 0.72, Current Ratio: 1.5
  - Credit Score: 65/100 (BBB)
  - News Sentiment: +0.1 (neutral — pending DOT investigation)
  - Requesting: $50M bond issuance
  - EDGE CASE: amount exceeds automated approval threshold ($30M)
```

---

## 9. Phase 4: Strands Agents — Full Implementation

### 9.0 Time Budget: 60 minutes (Team Strands owns this)

### 9.1 Agent Configuration File

```python
# backend/app/config.py

import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class TraceForgeConfig(BaseModel):
    neo4j_uri: str = os.getenv("NEO4J_URI", "")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")

    sqs_queue_url: str = os.getenv("SQS_QUEUE_URL", "")

    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514"
    )
    bedrock_region: str = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    agentcore_gateway_url: str = os.getenv("AGENTCORE_GATEWAY_URL", "")
    agentcore_runtime_arn: str = os.getenv("AGENTCORE_RUNTIME_ARN", "")

    s3_bucket: str = os.getenv("S3_BUCKET", "")

    default_tenant_id: str = os.getenv("DEFAULT_TENANT_ID", "tenant_demo")

config = TraceForgeConfig()
```

### 9.2 Agent System Prompts

```python
# backend/app/prompts.py

RESEARCHER_SYSTEM_PROMPT = """You are a Financial Research Agent in a credit decision pipeline.

Your role: Gather comprehensive financial data about a company applying for credit.

For each credit application, you MUST:
1. Fetch the latest SEC 10-K filing (annual report) using fetch_sec_filings
2. Fetch the company's internal credit score using fetch_credit_scores
3. Fetch recent news sentiment using fetch_news_sentiment
4. Query the knowledge graph for any existing entity relationships using query_knowledge_graph

After gathering all data, compile a structured research brief with:
- Company financials (revenue, net income, assets, liabilities, key ratios)
- Credit score and rating
- News sentiment summary
- Any relevant relationships or red flags from the knowledge graph

Be thorough. Missing data is worse than slow data. If a tool call fails, report the
failure explicitly — do not fabricate data to fill gaps.

Output your research brief as structured text that the Analyst agent can parse."""


ANALYST_SYSTEM_PROMPT = """You are a Risk Analysis Agent in a credit decision pipeline.

Your role: Evaluate the financial data from the Researcher and compute a risk assessment.

For each credit application, you MUST:
1. Compute a risk score (0-100) using compute_risk_score with the financial data
2. Validate the application against business rules using validate_rules
3. Compare against historical decisions for similar companies using compare_historical

Risk scoring framework:
- Debt/Equity ratio: < 0.5 (low risk), 0.5-1.0 (moderate), > 1.0 (high)
- Current ratio: > 2.0 (low risk), 1.0-2.0 (moderate), < 1.0 (high)
- Credit score: > 70 (low risk), 50-70 (moderate), < 50 (high)
- News sentiment: > 0.3 (positive), -0.3 to 0.3 (neutral), < -0.3 (negative)

After analysis, output a structured risk assessment with:
- Overall risk score (0-100, higher = lower risk)
- Risk category (LOW / MODERATE / HIGH / CRITICAL)
- Key risk factors (list)
- Comparison to historical decisions
- Rule validation results
- Recommendation (APPROVE / DENY / ESCALATE) with reasoning

Be precise. State which data points drove your recommendation. If data is inconsistent
(e.g., high revenue but negative news), flag the inconsistency explicitly."""


WRITER_SYSTEM_PROMPT = """You are a Decision Memo Writer Agent in a credit decision pipeline.

Your role: Draft the official credit decision memo based on the Analyst's assessment.

For each credit application, you MUST:
1. Draft a formal decision memo using draft_memo
2. Check compliance requirements using check_compliance
3. Submit the final decision using submit_decision

Memo format:
- Header: Application ID, Company Name, Requested Amount, Date
- Decision: APPROVED / DENIED / ESCALATED
- Executive Summary: 2-3 sentences
- Risk Assessment: Score, Category, Key Factors
- Data Sources: List every data source consulted (with timestamps)
- Compliance: EU AI Act Article 12 declaration
- Conditions (if APPROVED): Any conditions attached
- Reasoning Chain: Step-by-step reasoning that led to this decision

The memo must be traceable. Every claim must reference the specific data point
that supports it. This memo is the human-readable artifact of the provenance graph.

After drafting, run check_compliance to verify the memo meets regulatory requirements,
then submit_decision to finalize."""
```

### 9.3 Swarm Definition

```python
# backend/app/swarm.py

import uuid
from datetime import datetime, timezone

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.multiagent import GraphBuilder

from backend.app.config import config
from backend.app.prompts import (
    RESEARCHER_SYSTEM_PROMPT,
    ANALYST_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from backend.app.hooks import ProvenanceHook


def create_credit_decision_swarm(
    tools: list,
    tenant_id: str,
    session_id: str | None = None,
    trace_id: str | None = None,
) -> tuple:
    """Create the 3-agent credit decision swarm with provenance tracking.

    Returns (graph, trace_id, session_id) tuple.
    """
    session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    trace_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"

    model = BedrockModel(
        model_id=config.bedrock_model_id,
        region_name=config.bedrock_region,
    )

    provenance_hook = ProvenanceHook(
        sqs_queue_url=config.sqs_queue_url,
        trace_id=trace_id,
        session_id=session_id,
        tenant_id=tenant_id,
    )

    researcher_tools = [t for t in tools if t.name in (
        "fetch_sec_filings", "fetch_credit_scores",
        "fetch_news_sentiment", "query_knowledge_graph",
    )]

    analyst_tools = [t for t in tools if t.name in (
        "compute_risk_score", "validate_rules", "compare_historical",
    )]

    writer_tools = [t for t in tools if t.name in (
        "draft_memo", "check_compliance", "submit_decision",
    )]

    researcher = Agent(
        name="Researcher",
        model=model,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        tools=researcher_tools,
        hooks=[provenance_hook],
    )

    analyst = Agent(
        name="Analyst",
        model=model,
        system_prompt=ANALYST_SYSTEM_PROMPT,
        tools=analyst_tools,
        hooks=[provenance_hook],
    )

    writer = Agent(
        name="Writer",
        model=model,
        system_prompt=WRITER_SYSTEM_PROMPT,
        tools=writer_tools,
        hooks=[provenance_hook],
    )

    graph = GraphBuilder()
    graph.add_node("researcher", researcher)
    graph.add_node("analyst", analyst)
    graph.add_node("writer", writer)
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "writer")

    return graph.build(), trace_id, session_id
```

### 9.4 AgentCore Runtime Entry Point

```python
# backend/app/agent_runtime.py
# This is the file that gets deployed to AgentCore Runtime (like folder 06's booking_agent.py)

import json
import os
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.multiagent import GraphBuilder
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client

from backend.app.hooks import ProvenanceHook
from backend.app.prompts import (
    RESEARCHER_SYSTEM_PROMPT,
    ANALYST_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

GATEWAY_URL = os.environ.get("AGENTCORE_GATEWAY_URL", "")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250514"
)

app = BedrockAgentCoreApp()

@app.entrypoint
def handle_request(prompt: str, session_id: str, **kwargs):
    """Main entry point invoked by AgentCore Runtime."""

    import uuid
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    tenant_id = kwargs.get("tenant_id", "tenant_demo")

    mcp_client = MCPClient(lambda: streamablehttp_client(GATEWAY_URL))

    with mcp_client:
        all_tools = mcp_client.list_tools_sync()

        model = BedrockModel(model_id=BEDROCK_MODEL_ID)
        provenance_hook = ProvenanceHook(
            sqs_queue_url=SQS_QUEUE_URL,
            trace_id=trace_id,
            session_id=session_id,
            tenant_id=tenant_id,
        )

        researcher_tool_names = {
            "fetch_sec_filings", "fetch_credit_scores",
            "fetch_news_sentiment", "query_knowledge_graph",
        }
        analyst_tool_names = {
            "compute_risk_score", "validate_rules", "compare_historical",
        }
        writer_tool_names = {
            "draft_memo", "check_compliance", "submit_decision",
        }

        researcher = Agent(
            name="Researcher",
            model=model,
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            tools=[t for t in all_tools if t.name in researcher_tool_names],
            hooks=[provenance_hook],
        )
        analyst = Agent(
            name="Analyst",
            model=model,
            system_prompt=ANALYST_SYSTEM_PROMPT,
            tools=[t for t in all_tools if t.name in analyst_tool_names],
            hooks=[provenance_hook],
        )
        writer = Agent(
            name="Writer",
            model=model,
            system_prompt=WRITER_SYSTEM_PROMPT,
            tools=[t for t in all_tools if t.name in writer_tool_names],
            hooks=[provenance_hook],
        )

        graph = GraphBuilder()
        graph.add_node("researcher", researcher)
        graph.add_node("analyst", analyst)
        graph.add_node("writer", writer)
        graph.add_edge("researcher", "analyst")
        graph.add_edge("analyst", "writer")

        swarm = graph.build()
        result = swarm(prompt)

        return {
            "response": str(result),
            "trace_id": trace_id,
            "session_id": session_id,
            "tenant_id": tenant_id,
        }

if __name__ == "__main__":
    app.run()
```

### 9.5 Agent Requirements (for AgentCore container)

```
# deploy/agent_requirements.txt
strands-agents>=1.40.0
strands-agents[otel]
bedrock-agentcore>=1.1.0
neo4j>=5.20.0
boto3>=1.35.0
pydantic>=2.0.0
python-dotenv
aws-opentelemetry-distro>=0.7.0
```

---

## 10. Phase 5: ProvenanceHook — The Core Innovation

### 10.0 Time Budget: 30 minutes (Team Strands owns the hook, Team Graph owns the Neo4j writer)

### 10.1 Hook Implementation

```python
# backend/app/hooks.py

import hashlib
import json
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from strands.hooks import HookProvider
from strands.hooks.events import (
    AgentInitializedEvent,
    BeforeInvocationEvent,
    AfterInvocationEvent,
    BeforeToolCallEvent,
    AfterToolCallEvent,
    BeforeModelCallEvent,
    AfterModelCallEvent,
)

logger = logging.getLogger(__name__)


class ProvenanceHook(HookProvider):
    """Captures every Strands lifecycle event and emits it to SQS FIFO for Neo4j persistence.

    This is the core innovation of TraceForge: transforming transient in-process agent events
    into a durable, hash-chained provenance graph.
    """

    def __init__(
        self,
        sqs_queue_url: str,
        trace_id: str,
        session_id: str,
        tenant_id: str,
    ):
        self.sqs_queue_url = sqs_queue_url
        self.trace_id = trace_id
        self.session_id = session_id
        self.tenant_id = tenant_id

        self.sqs = boto3.client("sqs")

        self._step_counter = 0
        self._prev_hash = "GENESIS"
        self._agent_name = "unknown"
        self._invocation_start: float | None = None
        self._tool_call_start: float | None = None
        self._model_call_start: float | None = None
        self._current_tool_name: str | None = None

    def _compute_hash(self, event_data: dict) -> str:
        """Compute SHA-256 hash of previous hash + event data for chain integrity."""
        payload = json.dumps(
            {"prev_hash": self._prev_hash, **event_data},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _emit_event(self, event_type: str, data: dict) -> None:
        """Send a provenance event to SQS FIFO queue (async, non-blocking)."""
        self._step_counter += 1
        step_id = f"step_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        event_data = {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "step_id": step_id,
            "step_number": self._step_counter,
            "agent_name": self._agent_name,
            "event_type": event_type,
            "created_at": now,
            "prev_hash": self._prev_hash,
            **data,
        }

        step_hash = self._compute_hash(event_data)
        event_data["step_hash"] = step_hash
        self._prev_hash = step_hash

        try:
            self.sqs.send_message(
                QueueUrl=self.sqs_queue_url,
                MessageBody=json.dumps(event_data, default=str),
                MessageGroupId=self.trace_id,
                MessageDeduplicationId=step_id,
            )
        except Exception as e:
            logger.error(f"Failed to emit provenance event: {e}")

    # ─── Agent lifecycle ───

    def on_agent_initialized(self, event: AgentInitializedEvent, **kwargs) -> None:
        self._agent_name = getattr(event, "agent_name", None) or kwargs.get("agent_name", "unknown")

    def on_before_invocation(self, event: BeforeInvocationEvent, **kwargs) -> None:
        self._invocation_start = time.monotonic()
        self._emit_event("AGENT_START", {
            "thought": f"Agent {self._agent_name} starting invocation",
        })

    def on_after_invocation(self, event: AfterInvocationEvent, **kwargs) -> None:
        latency_ms = int((time.monotonic() - (self._invocation_start or 0)) * 1000)
        result_text = str(getattr(event, "result", ""))[:2000]
        self._emit_event("AGENT_END", {
            "observation": result_text,
            "latency_ms": latency_ms,
        })

    # ─── Tool call lifecycle ───

    def on_before_tool_call(self, event: BeforeToolCallEvent, **kwargs) -> None:
        self._tool_call_start = time.monotonic()
        tool_name = getattr(event, "tool_name", None) or str(getattr(event, "tool", {}).get("name", "unknown"))
        self._current_tool_name = tool_name
        tool_input = getattr(event, "tool_input", None) or getattr(event, "input", {})

        self._emit_event("TOOL_CALL_START", {
            "action": tool_name,
            "tool_call": {
                "tool_name": tool_name,
                "arguments": _safe_serialize(tool_input),
                "status": "PENDING",
            },
        })

    def on_after_tool_call(self, event: AfterToolCallEvent, **kwargs) -> None:
        latency_ms = int((time.monotonic() - (self._tool_call_start or 0)) * 1000)
        tool_name = self._current_tool_name or "unknown"

        result = getattr(event, "result", None)
        if isinstance(result, dict):
            result_content = result.get("content", str(result))
        else:
            result_content = str(result)
        result_summary = result_content[:500]

        status = "SUCCESS"
        error_message = None
        if isinstance(result, dict) and result.get("status") == "error":
            status = "ERROR"
            error_message = result.get("content", "Unknown error")

        self._emit_event("TOOL_CALL_END", {
            "action": tool_name,
            "observation": result_summary,
            "latency_ms": latency_ms,
            "tool_call": {
                "tool_name": tool_name,
                "result": result_content[:5000],
                "result_summary": result_summary,
                "status": status,
                "duration_ms": latency_ms,
                "error_message": error_message,
            },
        })
        self._current_tool_name = None

    # ─── Model call lifecycle ───

    def on_before_model_call(self, event: BeforeModelCallEvent, **kwargs) -> None:
        self._model_call_start = time.monotonic()

    def on_after_model_call(self, event: AfterModelCallEvent, **kwargs) -> None:
        latency_ms = int((time.monotonic() - (self._model_call_start or 0)) * 1000)

        usage = getattr(event, "usage", {}) or {}
        input_tokens = usage.get("input_tokens", 0) if isinstance(usage, dict) else 0
        output_tokens = usage.get("output_tokens", 0) if isinstance(usage, dict) else 0

        cost_usd = _estimate_cost(input_tokens, output_tokens)

        model_id = getattr(event, "model_id", None) or "unknown"
        stop_reason = getattr(event, "stop_reason", None)

        self._emit_event("MODEL_CALL", {
            "model_id": model_id,
            "token_input": input_tokens,
            "token_output": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "thought": f"Model call completed ({stop_reason})",
        })


def _safe_serialize(obj: Any) -> dict:
    """Safely serialize tool arguments to a dict."""
    if isinstance(obj, dict):
        return {k: str(v)[:1000] for k, v in obj.items()}
    return {"raw": str(obj)[:1000]}


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for Claude Sonnet 4 on Bedrock.
    Pricing: $3/1M input, $15/1M output (us-east-1, May 2026).
    """
    return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
```

### 10.2 Hook Event Data Shapes (what SQS messages look like)

```json
// AGENT_START event
{
  "trace_id": "trace_abc123",
  "session_id": "sess_def456",
  "tenant_id": "tenant_demo",
  "step_id": "step_ghi789",
  "step_number": 1,
  "agent_name": "Researcher",
  "event_type": "AGENT_START",
  "created_at": "2026-05-19T17:30:02.123Z",
  "prev_hash": "GENESIS",
  "step_hash": "a1b2c3d4e5f6...",
  "thought": "Agent Researcher starting invocation"
}

// TOOL_CALL_START event
{
  "trace_id": "trace_abc123",
  "session_id": "sess_def456",
  "tenant_id": "tenant_demo",
  "step_id": "step_jkl012",
  "step_number": 2,
  "agent_name": "Researcher",
  "event_type": "TOOL_CALL_START",
  "created_at": "2026-05-19T17:30:03.456Z",
  "prev_hash": "a1b2c3d4e5f6...",
  "step_hash": "b2c3d4e5f6g7...",
  "action": "fetch_sec_filings",
  "tool_call": {
    "tool_name": "fetch_sec_filings",
    "arguments": {"company": "ZENITH_BIOTECH", "period": "FY2025"},
    "status": "PENDING"
  }
}

// TOOL_CALL_END event
{
  "trace_id": "trace_abc123",
  "session_id": "sess_def456",
  "tenant_id": "tenant_demo",
  "step_id": "step_mno345",
  "step_number": 3,
  "agent_name": "Researcher",
  "event_type": "TOOL_CALL_END",
  "created_at": "2026-05-19T17:30:05.789Z",
  "prev_hash": "b2c3d4e5f6g7...",
  "step_hash": "c3d4e5f6g7h8...",
  "action": "fetch_sec_filings",
  "observation": "Retrieved 10-K: revenue $150M, net income $25M (POISONED)",
  "latency_ms": 2100,
  "tool_call": {
    "tool_name": "fetch_sec_filings",
    "result": "{\"revenue\": 150000000, \"net_income\": 25000000, ...}",
    "result_summary": "Retrieved 10-K: revenue $150M, net income $25M",
    "status": "SUCCESS",
    "duration_ms": 2100,
    "error_message": null
  }
}

// MODEL_CALL event
{
  "trace_id": "trace_abc123",
  "session_id": "sess_def456",
  "tenant_id": "tenant_demo",
  "step_id": "step_pqr678",
  "step_number": 4,
  "agent_name": "Researcher",
  "event_type": "MODEL_CALL",
  "created_at": "2026-05-19T17:30:08.012Z",
  "prev_hash": "c3d4e5f6g7h8...",
  "step_hash": "d4e5f6g7h8i9...",
  "model_id": "us.anthropic.claude-sonnet-4-5-20250514",
  "token_input": 3200,
  "token_output": 1500,
  "cost_usd": 0.032,
  "latency_ms": 3800,
  "thought": "Model call completed (end_turn)"
}
```

---

## 11. Phase 6: SQS + Lambda ProvenanceWriter

### 11.0 Time Budget: 30 minutes (Team Graph owns this)

### 11.1 ProvenanceWriter Lambda

```python
# lambda_functions/provenance_writer/lambda_function.py

import json
import os
import logging
from datetime import datetime, timezone

from neo4j import GraphDatabase

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        import boto3
        sm = boto3.client("secretsmanager")
        secret = json.loads(
            sm.get_secret_value(SecretId="traceforge/neo4j-credentials")["SecretString"]
        )
        _driver = GraphDatabase.driver(
            secret["uri"],
            auth=(secret["username"], secret["password"]),
        )
    return _driver


WRITE_STEP_CYPHER = """
MERGE (trace:ReasoningTrace {trace_id: $trace_id})
ON CREATE SET
  trace.tenant_id = $tenant_id,
  trace.session_id = $session_id,
  trace.task = $task,
  trace.started_at = datetime($created_at),
  trace.total_cost_usd = 0,
  trace.total_latency_ms = 0,
  trace.step_count = 0

CREATE (step:ReasoningStep {
  step_id: $step_id,
  trace_id: $trace_id,
  agent_name: $agent_name,
  event_type: $event_type,
  step_number: $step_number,
  thought: $thought,
  action: $action,
  observation: $observation,
  cost_usd: coalesce($cost_usd, 0),
  latency_ms: coalesce($latency_ms, 0),
  model_id: $model_id,
  token_input: coalesce($token_input, 0),
  token_output: coalesce($token_output, 0),
  prev_hash: $prev_hash,
  step_hash: $step_hash,
  status: $status,
  created_at: datetime($created_at)
})

MERGE (trace)-[:HAS_STEP {step_number: $step_number}]->(step)

SET trace.total_cost_usd = trace.total_cost_usd + coalesce($cost_usd, 0),
    trace.total_latency_ms = trace.total_latency_ms + coalesce($latency_ms, 0),
    trace.step_count = trace.step_count + 1

WITH step
OPTIONAL MATCH (prev:ReasoningStep {trace_id: $trace_id, step_number: $step_number - 1})
FOREACH (_ IN CASE WHEN prev IS NOT NULL THEN [1] ELSE [] END |
  MERGE (prev)-[:NEXT_STEP]->(step)
)

RETURN step.step_id AS step_id
"""


WRITE_TOOL_CALL_CYPHER = """
MATCH (step:ReasoningStep {step_id: $step_id})
CREATE (tc:ToolCall {
  call_id: $call_id,
  step_id: $step_id,
  tool_name: $tool_name,
  arguments: $arguments,
  result: $result,
  result_summary: $result_summary,
  status: $status,
  duration_ms: coalesce($duration_ms, 0),
  cost_usd: coalesce($cost_usd, 0),
  error_message: $error_message,
  created_at: datetime($created_at)
})
MERGE (step)-[:USES_TOOL]->(tc)
RETURN tc.call_id AS call_id
"""


COMPLETE_TRACE_CYPHER = """
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
SET trace.completed_at = datetime($completed_at),
    trace.outcome = $outcome,
    trace.success = $success

WITH trace
OPTIONAL MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
WITH trace, count(DISTINCT step.agent_name) AS agent_count
SET trace.agent_count = agent_count

RETURN trace.trace_id AS trace_id
"""


LINK_TENANT_SESSION_CYPHER = """
MERGE (tenant:Tenant {tenant_id: $tenant_id})
ON CREATE SET tenant.name = $tenant_id, tenant.created_at = datetime()

MERGE (session:Session {session_id: $session_id})
ON CREATE SET
  session.tenant_id = $tenant_id,
  session.started_at = datetime($created_at),
  session.status = 'ACTIVE'

MERGE (tenant)-[:HAS_SESSION]->(session)

WITH session
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MERGE (session)-[:HAS_TRACE]->(trace)
"""


def lambda_handler(event, context):
    driver = get_driver()
    processed = 0
    errors = 0

    for record in event.get("Records", []):
        try:
            msg = json.loads(record["body"])
            event_type = msg.get("event_type", "UNKNOWN")

            with driver.session(database="neo4j") as neo_session:

                if event_type in ("AGENT_START", "TOOL_CALL_START", "TOOL_CALL_END",
                                  "MODEL_CALL", "AGENT_END", "SWARM_START", "SWARM_END"):

                    params = {
                        "trace_id": msg["trace_id"],
                        "session_id": msg["session_id"],
                        "tenant_id": msg["tenant_id"],
                        "step_id": msg["step_id"],
                        "step_number": msg["step_number"],
                        "agent_name": msg.get("agent_name", "unknown"),
                        "event_type": event_type,
                        "thought": msg.get("thought"),
                        "action": msg.get("action"),
                        "observation": msg.get("observation"),
                        "cost_usd": msg.get("cost_usd", 0),
                        "latency_ms": msg.get("latency_ms", 0),
                        "model_id": msg.get("model_id"),
                        "token_input": msg.get("token_input", 0),
                        "token_output": msg.get("token_output", 0),
                        "prev_hash": msg["prev_hash"],
                        "step_hash": msg["step_hash"],
                        "status": "COMPLETED" if "END" in event_type else "STARTED",
                        "created_at": msg["created_at"],
                        "task": msg.get("thought", "Credit decision evaluation"),
                    }

                    neo_session.run(WRITE_STEP_CYPHER, params)

                    if event_type == "AGENT_START" and msg["step_number"] == 1:
                        neo_session.run(LINK_TENANT_SESSION_CYPHER, {
                            "tenant_id": msg["tenant_id"],
                            "session_id": msg["session_id"],
                            "trace_id": msg["trace_id"],
                            "created_at": msg["created_at"],
                        })

                    tool_call = msg.get("tool_call")
                    if tool_call and event_type == "TOOL_CALL_END":
                        import uuid
                        tc_params = {
                            "step_id": msg["step_id"],
                            "call_id": f"call_{uuid.uuid4().hex[:12]}",
                            "tool_name": tool_call.get("tool_name", "unknown"),
                            "arguments": json.dumps(tool_call.get("arguments", {})),
                            "result": tool_call.get("result", ""),
                            "result_summary": tool_call.get("result_summary", ""),
                            "status": tool_call.get("status", "UNKNOWN"),
                            "duration_ms": tool_call.get("duration_ms", 0),
                            "cost_usd": tool_call.get("cost_usd", 0),
                            "error_message": tool_call.get("error_message"),
                            "created_at": msg["created_at"],
                        }
                        neo_session.run(WRITE_TOOL_CALL_CYPHER, tc_params)

                processed += 1

        except Exception as e:
            logger.error(f"Failed to process record: {e}", exc_info=True)
            errors += 1

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": processed,
            "errors": errors,
        }),
    }
```

### 11.2 ProvenanceWriter Requirements

```
# lambda_functions/provenance_writer/requirements.txt
neo4j>=5.20.0
boto3>=1.35.0
```

### 11.3 Lambda Deployment Script

```python
# infrastructure/deploy_lambdas.py

import boto3
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
LAMBDA_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/TraceForge-LambdaExecutionRole"

FUNCTIONS = {
    "traceforge-provenance-writer": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 30,
        "memory": 256,
        "source_dir": "lambda_functions/provenance_writer",
        "environment": {},
        "sqs_trigger": True,
    },
    "traceforge-fetch-sec-filings": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/fetch_sec_filings",
        "environment": {
            "TABLE_NAME": "traceforge-FinancialData",
        },
    },
    "traceforge-fetch-credit-scores": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/fetch_credit_scores",
        "environment": {
            "TABLE_NAME": "traceforge-FinancialData",
        },
    },
    "traceforge-fetch-news-sentiment": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/fetch_news_sentiment",
        "environment": {
            "TABLE_NAME": "traceforge-FinancialData",
        },
    },
    "traceforge-query-knowledge-graph": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 256,
        "source_dir": "lambda_functions/query_knowledge_graph",
        "environment": {},
    },
    "traceforge-compute-risk-score": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/compute_risk_score",
        "environment": {},
    },
    "traceforge-validate-rules": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/validate_rules",
        "environment": {
            "TABLE_NAME": "traceforge-DecisionRules",
        },
    },
    "traceforge-compare-historical": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 256,
        "source_dir": "lambda_functions/compare_historical",
        "environment": {},
    },
    "traceforge-draft-memo": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/draft_memo",
        "environment": {},
    },
    "traceforge-check-compliance": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/check_compliance",
        "environment": {},
    },
    "traceforge-submit-decision": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/submit_decision",
        "environment": {
            "APPLICATIONS_TABLE": "traceforge-CreditApplications",
        },
    },
    "traceforge-why-query": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 30,
        "memory": 256,
        "source_dir": "lambda_functions/why_query",
        "environment": {},
    },
    "traceforge-cost-query": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 15,
        "memory": 128,
        "source_dir": "lambda_functions/cost_query",
        "environment": {},
    },
    "traceforge-audit-export": {
        "handler": "lambda_function.lambda_handler",
        "runtime": "python3.11",
        "timeout": 60,
        "memory": 512,
        "source_dir": "lambda_functions/audit_export",
        "environment": {
            "S3_BUCKET": f"traceforge-{ACCOUNT_ID}-{REGION}",
        },
    },
}


def create_zip(source_dir: str) -> bytes:
    """Create a ZIP deployment package from a Lambda source directory."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        source = Path(source_dir)
        for file in source.rglob("*.py"):
            zf.write(file, file.relative_to(source))

    with open(tmp_path, "rb") as f:
        return f.read()


def deploy_function(name: str, spec: dict, lambda_client) -> str:
    """Deploy or update a single Lambda function. Returns the function ARN."""
    zip_bytes = create_zip(spec["source_dir"])

    env_vars = {
        "Variables": {
            **spec.get("environment", {}),
        }
    }

    try:
        response = lambda_client.create_function(
            FunctionName=name,
            Runtime=spec["runtime"],
            Role=LAMBDA_ROLE_ARN,
            Handler=spec["handler"],
            Code={"ZipFile": zip_bytes},
            Timeout=spec["timeout"],
            MemorySize=spec["memory"],
            Environment=env_vars,
            Architectures=["arm64"],
            Tags={"Project": "TraceForge"},
        )
        arn = response["FunctionArn"]
        print(f"  CREATED: {name} -> {arn}")
    except lambda_client.exceptions.ResourceConflictException:
        lambda_client.update_function_code(
            FunctionName=name,
            ZipFile=zip_bytes,
        )
        lambda_client.update_function_configuration(
            FunctionName=name,
            Timeout=spec["timeout"],
            MemorySize=spec["memory"],
            Environment=env_vars,
        )
        response = lambda_client.get_function(FunctionName=name)
        arn = response["Configuration"]["FunctionArn"]
        print(f"  UPDATED: {name} -> {arn}")

    return arn


def setup_sqs_trigger(function_name: str, queue_arn: str, lambda_client):
    """Create SQS event source mapping for ProvenanceWriter."""
    try:
        lambda_client.create_event_source_mapping(
            EventSourceArn=queue_arn,
            FunctionName=function_name,
            BatchSize=10,
            MaximumBatchingWindowInSeconds=5,
            Enabled=True,
        )
        print(f"  SQS trigger: {function_name} <- {queue_arn}")
    except lambda_client.exceptions.ResourceConflictException:
        print(f"  SQS trigger already exists for {function_name}")


def main():
    lambda_client = boto3.client("lambda", region_name=REGION)
    sqs_client = boto3.client("sqs", region_name=REGION)

    sqs_queue_url = sqs_client.get_queue_url(
        QueueName="traceforge-provenance.fifo"
    )["QueueUrl"]
    sqs_queue_arn = sqs_client.get_queue_attributes(
        QueueUrl=sqs_queue_url,
        AttributeNames=["QueueArn"],
    )["Attributes"]["QueueArn"]

    print("Deploying Lambda functions...")
    arns = {}
    for name, spec in FUNCTIONS.items():
        arn = deploy_function(name, spec, lambda_client)
        arns[name] = arn

        if spec.get("sqs_trigger"):
            import time
            time.sleep(5)
            setup_sqs_trigger(name, sqs_queue_arn, lambda_client)

    print(f"\nDeployed {len(arns)} functions.")
    return arns


if __name__ == "__main__":
    main()
```

---

## 12. Phase 7: Tool Lambda Functions

### 12.0 Time Budget: 40 minutes (Team Deploy owns this, parallelized across functions)

### 12.1 fetch_sec_filings

```python
# lambda_functions/fetch_sec_filings/lambda_function.py

import json
import os
import boto3
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "traceforge-FinancialData")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event
    company = body.get("company", "")
    period = body.get("period", "FY2025")

    entity_id = company.upper().replace(" ", "_")
    data_type = f"SEC_10K_{period.replace('FY', '')}"

    try:
        response = table.get_item(Key={"entity_id": entity_id, "data_type": data_type})
        item = response.get("Item")

        if not item:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "NOT_FOUND",
                    "message": f"No SEC filing found for {company} ({period})",
                    "company": company,
                    "period": period,
                }),
            }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "SUCCESS",
                "company": item.get("company_name", company),
                "period": period,
                "revenue": item.get("revenue"),
                "net_income": item.get("net_income"),
                "total_assets": item.get("total_assets"),
                "total_liabilities": item.get("total_liabilities"),
                "debt_to_equity": item.get("debt_to_equity"),
                "current_ratio": item.get("current_ratio"),
                "source": item.get("source", "SEC_EDGAR"),
                "retrieved_at": item.get("retrieved_at", ""),
            }, cls=DecimalEncoder),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "ERROR", "message": str(e)}),
        }
```

### 12.2 fetch_credit_scores

```python
# lambda_functions/fetch_credit_scores/lambda_function.py

import json
import os
import boto3
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "traceforge-FinancialData")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event
    company = body.get("company", "")

    entity_id = company.upper().replace(" ", "_")

    try:
        response = table.get_item(
            Key={"entity_id": entity_id, "data_type": "CREDIT_SCORE"}
        )
        item = response.get("Item")

        if not item:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "NOT_FOUND",
                    "message": f"No credit score found for {company}",
                }),
            }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "SUCCESS",
                "company": item.get("company_name", company),
                "credit_score": item.get("credit_score"),
                "credit_rating": item.get("credit_rating"),
                "source": item.get("source", "INTERNAL_MODEL"),
                "retrieved_at": item.get("retrieved_at", ""),
            }, cls=DecimalEncoder),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "ERROR", "message": str(e)}),
        }
```

### 12.3 fetch_news_sentiment

```python
# lambda_functions/fetch_news_sentiment/lambda_function.py

import json
import os
import boto3
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "traceforge-FinancialData")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event
    company = body.get("company", "")

    entity_id = company.upper().replace(" ", "_")

    try:
        response = table.get_item(
            Key={"entity_id": entity_id, "data_type": "NEWS_SENTIMENT"}
        )
        item = response.get("Item")

        if not item:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "NOT_FOUND",
                    "message": f"No news sentiment data found for {company}",
                }),
            }

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "SUCCESS",
                "company": item.get("company_name", company),
                "sentiment_score": item.get("sentiment_score"),
                "articles_count": item.get("sentiment_articles_count"),
                "source": item.get("source", "NEWS_API"),
                "retrieved_at": item.get("retrieved_at", ""),
            }, cls=DecimalEncoder),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "ERROR", "message": str(e)}),
        }
```

### 12.4 query_knowledge_graph

```python
# lambda_functions/query_knowledge_graph/lambda_function.py

import json
import os
import boto3
from neo4j import GraphDatabase

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        sm = boto3.client("secretsmanager")
        secret = json.loads(
            sm.get_secret_value(SecretId="traceforge/neo4j-credentials")["SecretString"]
        )
        _driver = GraphDatabase.driver(
            secret["uri"], auth=(secret["username"], secret["password"])
        )
    return _driver


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event
    company = body.get("company", "")
    query_type = body.get("query_type", "related_entities")

    driver = get_driver()

    queries = {
        "related_entities": """
            MATCH (e:Entity)
            WHERE e.name CONTAINS $company OR e.description CONTAINS $company
            OPTIONAL MATCH (e)-[r:RELATED_TO]-(other:Entity)
            RETURN e.name AS entity, e.type AS type, e.description AS description,
                   collect({name: other.name, type: other.type, relation: type(r)}) AS related
            LIMIT 10
        """,
        "past_decisions": """
            MATCH (app:CreditApplication)
            WHERE app.company_name CONTAINS $company
            OPTIONAL MATCH (app)<-[:DECIDED_ON]-(step:ReasoningStep)
            OPTIONAL MATCH (step)<-[:HAS_STEP]-(trace:ReasoningTrace)
            RETURN app.application_id AS application_id,
                   app.status AS status,
                   app.decision AS decision,
                   trace.outcome AS outcome,
                   app.submitted_at AS date
            ORDER BY app.submitted_at DESC
            LIMIT 5
        """,
        "similar_traces": """
            MATCH (trace:ReasoningTrace)
            WHERE trace.task CONTAINS $company
            RETURN trace.trace_id AS trace_id,
                   trace.task AS task,
                   trace.outcome AS outcome,
                   trace.total_cost_usd AS cost,
                   trace.completed_at AS completed
            ORDER BY trace.completed_at DESC
            LIMIT 5
        """,
    }

    cypher = queries.get(query_type, queries["related_entities"])

    try:
        with driver.session(database="neo4j") as session:
            result = session.run(cypher, company=company)
            records = [dict(r) for r in result]

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "SUCCESS",
                "query_type": query_type,
                "company": company,
                "results": records,
                "count": len(records),
            }, default=str),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "ERROR", "message": str(e)}),
        }
```

### 12.5 compute_risk_score

```python
# lambda_functions/compute_risk_score/lambda_function.py

import json


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event

    revenue = body.get("revenue", 0)
    net_income = body.get("net_income", 0)
    debt_to_equity = body.get("debt_to_equity", 999)
    current_ratio = body.get("current_ratio", 0)
    credit_score = body.get("credit_score", 0)
    sentiment_score = body.get("sentiment_score", 0)
    requested_amount = body.get("requested_amount", 0)

    factors = []
    score = 50

    if debt_to_equity < 0.5:
        score += 15
        factors.append("debt_to_equity_low_risk")
    elif debt_to_equity <= 1.0:
        score += 5
        factors.append("debt_to_equity_moderate")
    else:
        score -= 15
        factors.append("debt_to_equity_high_risk")

    if current_ratio > 2.0:
        score += 10
        factors.append("current_ratio_healthy")
    elif current_ratio >= 1.0:
        score += 0
        factors.append("current_ratio_adequate")
    else:
        score -= 10
        factors.append("current_ratio_concerning")

    if credit_score > 70:
        score += 15
        factors.append("credit_score_strong")
    elif credit_score >= 50:
        score += 5
        factors.append("credit_score_moderate")
    else:
        score -= 15
        factors.append("credit_score_weak")

    if sentiment_score > 0.3:
        score += 5
        factors.append("sentiment_positive")
    elif sentiment_score >= -0.3:
        score += 0
        factors.append("sentiment_neutral")
    else:
        score -= 10
        factors.append("sentiment_negative")

    if revenue > 0 and net_income > 0:
        margin = net_income / revenue
        if margin > 0.15:
            score += 10
            factors.append("profit_margin_excellent")
        elif margin > 0.05:
            score += 5
            factors.append("profit_margin_adequate")
        else:
            score -= 5
            factors.append("profit_margin_thin")
    elif net_income < 0:
        score -= 20
        factors.append("net_loss")

    score = max(0, min(100, score))

    if score >= 75:
        category = "LOW"
        recommendation = "APPROVE"
    elif score >= 55:
        category = "MODERATE"
        recommendation = "APPROVE" if requested_amount < 30_000_000 else "ESCALATE"
    elif score >= 35:
        category = "HIGH"
        recommendation = "ESCALATE"
    else:
        category = "CRITICAL"
        recommendation = "DENY"

    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "SUCCESS",
            "risk_score": score,
            "risk_category": category,
            "recommendation": recommendation,
            "factors": factors,
            "model_version": "v2.1",
        }),
    }
```

### 12.6 validate_rules

```python
# lambda_functions/validate_rules/lambda_function.py

import json
import os
import boto3
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "traceforge-DecisionRules")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


OPERATORS = {
    "gt": lambda a, b: a > b,
    "lt": lambda a, b: a < b,
    "gte": lambda a, b: a >= b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
}


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event

    try:
        response = table.scan(FilterExpression=boto3.dynamodb.conditions.Attr("enabled").eq(True))
        rules = response.get("Items", [])

        results = []
        all_pass = True

        for rule in rules:
            field = rule.get("condition_field", "")
            operator = rule.get("operator", "gt")
            threshold = float(rule.get("threshold", 0))
            value = float(body.get(field, 0))

            op_fn = OPERATORS.get(operator, lambda a, b: False)
            passed = op_fn(value, threshold)

            result = {
                "rule_id": rule["rule_id"],
                "rule_name": rule.get("rule_name", ""),
                "field": field,
                "value": value,
                "operator": operator,
                "threshold": threshold,
                "passed": passed,
                "severity": rule.get("severity", "WARN"),
            }

            if not passed:
                result["fail_message"] = rule.get("fail_message", "Rule violated")
                result["steer_message"] = rule.get("steer_message", "")
                if rule.get("severity") == "BLOCK":
                    all_pass = False

            results.append(result)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "SUCCESS",
                "all_rules_passed": all_pass,
                "rules_evaluated": len(results),
                "results": results,
            }, cls=DecimalEncoder),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "ERROR", "message": str(e)}),
        }
```

### 12.7 Remaining Tool Lambdas (compare_historical, draft_memo, check_compliance, submit_decision)

Each follows the same pattern. Compare_historical queries Neo4j for past decisions.
Draft_memo formats the analysis into a structured memo. Check_compliance verifies
Article 12 fields. Submit_decision writes the final status to DynamoDB and Neo4j.

Full implementations follow the same structure as the above — DynamoDB or Neo4j
backed, JSON in/out, error handling, DecimalEncoder.

---

## 13. Phase 8: AgentCore Deployment Pipeline

### 13.0 Time Budget: 30 minutes (Team Deploy owns this)

### 13.1 Gateway Creation

```python
# deploy/create_gateway.py

import boto3
import json
import time

client = boto3.client("bedrock-agentcore")

gateway = client.create_gateway(
    name="traceforge-gateway",
    protocolType="MCP",
    searchType="SEMANTIC",
    description="TraceForge credit decision tools — 10 MCP tools for Researcher/Analyst/Writer agents",
)

gateway_id = gateway["gatewayId"]
print(f"Gateway created: {gateway_id}")

time.sleep(10)
```

### 13.2 Gateway Targets (one per tool)

```python
# deploy/create_gateway_targets.py

import boto3
import json

client = boto3.client("bedrock-agentcore")
lambda_client = boto3.client("lambda")

ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
REGION = boto3.Session().region_name
GATEWAY_ID = "<set-from-create_gateway-output>"

TOOLS = [
    {
        "name": "fetch_sec_filings",
        "lambda_name": "traceforge-fetch-sec-filings",
        "description": "Fetch SEC 10-K annual filing data for a company. Returns revenue, net income, assets, liabilities, and key financial ratios.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name or ticker"},
                "period": {"type": "string", "description": "Filing period, e.g. FY2025", "default": "FY2025"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "fetch_credit_scores",
        "lambda_name": "traceforge-fetch-credit-scores",
        "description": "Fetch internal credit score and rating for a company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "fetch_news_sentiment",
        "lambda_name": "traceforge-fetch-news-sentiment",
        "description": "Fetch aggregated news sentiment score for a company. Returns sentiment score (-1.0 to 1.0) and article count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "query_knowledge_graph",
        "lambda_name": "traceforge-query-knowledge-graph",
        "description": "Query the Neo4j knowledge graph for entity relationships, past credit decisions, or similar reasoning traces.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name to search for"},
                "query_type": {
                    "type": "string",
                    "enum": ["related_entities", "past_decisions", "similar_traces"],
                    "description": "Type of graph query",
                    "default": "related_entities",
                },
            },
            "required": ["company"],
        },
    },
    {
        "name": "compute_risk_score",
        "lambda_name": "traceforge-compute-risk-score",
        "description": "Compute a risk score (0-100) based on financial metrics. Returns score, category, recommendation, and contributing factors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "revenue": {"type": "number"},
                "net_income": {"type": "number"},
                "debt_to_equity": {"type": "number"},
                "current_ratio": {"type": "number"},
                "credit_score": {"type": "number"},
                "sentiment_score": {"type": "number"},
                "requested_amount": {"type": "number"},
            },
            "required": ["revenue", "net_income", "debt_to_equity", "credit_score"],
        },
    },
    {
        "name": "validate_rules",
        "lambda_name": "traceforge-validate-rules",
        "description": "Validate a credit application against business rules stored in DynamoDB. Returns pass/fail per rule with steering messages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "requested_amount": {"type": "number"},
                "debt_to_equity": {"type": "number"},
                "credit_score": {"type": "number"},
                "risk_score": {"type": "number"},
            },
            "required": ["requested_amount"],
        },
    },
    {
        "name": "compare_historical",
        "lambda_name": "traceforge-compare-historical",
        "description": "Compare this application against historical credit decisions for similar companies in the knowledge graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "risk_category": {"type": "string"},
                "requested_amount": {"type": "number"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "draft_memo",
        "lambda_name": "traceforge-draft-memo",
        "description": "Draft a formal credit decision memo with application details, risk assessment, data sources, and compliance declaration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "string"},
                "company_name": {"type": "string"},
                "decision": {"type": "string", "enum": ["APPROVED", "DENIED", "ESCALATED"]},
                "risk_score": {"type": "number"},
                "risk_category": {"type": "string"},
                "factors": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
                "conditions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["application_id", "decision", "reasoning"],
        },
    },
    {
        "name": "check_compliance",
        "lambda_name": "traceforge-check-compliance",
        "description": "Check if a decision memo meets EU AI Act Article 12 compliance requirements for traceability and auditability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "memo": {"type": "string", "description": "The drafted decision memo text"},
                "trace_id": {"type": "string", "description": "The provenance trace ID"},
            },
            "required": ["memo"],
        },
    },
    {
        "name": "submit_decision",
        "lambda_name": "traceforge-submit-decision",
        "description": "Submit the final credit decision. Updates the application status in DynamoDB and creates a :DecisionMemo node in Neo4j.",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["APPROVED", "DENIED", "ESCALATED"]},
                "memo": {"type": "string"},
                "risk_score": {"type": "number"},
                "conditions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["application_id", "decision", "memo"],
        },
    },
]

for tool in TOOLS:
    lambda_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{tool['lambda_name']}"

    client.create_gateway_target(
        gatewayId=GATEWAY_ID,
        name=tool["name"],
        description=tool["description"],
        lambdaConfig={
            "lambdaArn": lambda_arn,
        },
        toolSchema={
            "inputSchema": json.dumps(tool["input_schema"]),
        },
    )
    print(f"  Target created: {tool['name']}")
```

### 13.3 Runtime Deployment

```python
# deploy/deploy_runtime.py

import boto3
import json
import os
import time

from bedrock_agentcore_starter_toolkit import Runtime

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
AGENTCORE_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/TraceForge-AgentCoreExecutionRole"

runtime = Runtime(
    agent_name="traceforge-credit-decision",
    agent_file="backend/app/agent_runtime.py",
    requirements_file="deploy/agent_requirements.txt",
    execution_role_arn=AGENTCORE_ROLE_ARN,
)

runtime.configure(
    environment_variables={
        "AGENTCORE_GATEWAY_URL": os.environ["AGENTCORE_GATEWAY_URL"],
        "SQS_QUEUE_URL": os.environ["SQS_QUEUE_URL"],
        "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250514",
    }
)

print("Building and deploying to AgentCore Runtime...")
runtime.deploy()

print(f"Runtime ARN: {runtime.agent_runtime_arn}")
print("Deployment complete.")
```

### 13.4 Runtime Invocation Test

```python
# deploy/test_invoke.py

import boto3
import json

client = boto3.client("bedrock-agentcore")

RUNTIME_ARN = os.environ["AGENTCORE_RUNTIME_ARN"]

response = client.invoke_agent_runtime(
    agentRuntimeArn=RUNTIME_ARN,
    runtimeSessionId="test-session-001",
    payload=json.dumps({
        "prompt": "Evaluate credit application APP-2026-001 for Meridian Manufacturing Corp requesting $10M corporate credit line.",
        "tenant_id": "tenant_demo",
    }).encode(),
)

for line in response["response"].iter_lines():
    if line:
        print(line.decode())
```

---

## 14. Phase 9: API Layer — Why / Cost / Audit

### 14.0 Time Budget: 20 minutes (Team Graph owns Why + Cost; Team Deploy owns Audit)

### 14.1 "Why?" Cypher Query — The Money Query

This is the single most important Cypher query in the project. It reconstructs the full
provenance chain for any decision.

```cypher
// WHY QUERY: Given a trace_id, return the complete provenance subgraph
// This is what makes TraceForge different from logs.

MATCH (trace:ReasoningTrace {trace_id: $trace_id})
OPTIONAL MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
OPTIONAL MATCH (step)-[:USES_TOOL]->(tc:ToolCall)
OPTIONAL MATCH (step)-[:TOUCHED]->(entity)
OPTIONAL MATCH (step)-[:NEXT_STEP]->(next_step:ReasoningStep)
OPTIONAL MATCH (trace)-[:INITIATED_BY]->(msg:Message)

WITH trace, step, tc, entity, next_step, msg
ORDER BY step.step_number

RETURN
  trace {
    .trace_id, .tenant_id, .task, .outcome, .success,
    .total_cost_usd, .total_latency_ms, .agent_count, .step_count,
    .started_at, .completed_at
  } AS trace,
  collect(DISTINCT step {
    .step_id, .agent_name, .event_type, .step_number,
    .thought, .action, .observation,
    .cost_usd, .latency_ms, .model_id,
    .token_input, .token_output,
    .prev_hash, .step_hash, .status, .created_at,
    tools: collect(DISTINCT tc {.call_id, .tool_name, .arguments, .result_summary, .status, .duration_ms}),
    touched_entities: collect(DISTINCT entity {.entity_id, .name, .type})
  }) AS steps,
  msg {.message_id, .content, .role} AS initiating_message
```

### 14.2 "Why?" Lambda

```python
# lambda_functions/why_query/lambda_function.py

import json
import boto3
from neo4j import GraphDatabase

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        sm = boto3.client("secretsmanager")
        secret = json.loads(
            sm.get_secret_value(SecretId="traceforge/neo4j-credentials")["SecretString"]
        )
        _driver = GraphDatabase.driver(
            secret["uri"], auth=(secret["username"], secret["password"])
        )
    return _driver


WHY_QUERY = """
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
OPTIONAL MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
OPTIONAL MATCH (step)-[:USES_TOOL]->(tc:ToolCall)
OPTIONAL MATCH (step)-[:TOUCHED]->(entity)

WITH trace, step, tc, entity
ORDER BY step.step_number

WITH trace,
     step,
     collect(DISTINCT {
       call_id: tc.call_id,
       tool_name: tc.tool_name,
       arguments: tc.arguments,
       result_summary: tc.result_summary,
       status: tc.status,
       duration_ms: tc.duration_ms
     }) AS tools,
     collect(DISTINCT {
       entity_id: entity.entity_id,
       name: entity.name,
       type: entity.type
     }) AS entities

RETURN
  trace.trace_id AS trace_id,
  trace.task AS task,
  trace.outcome AS outcome,
  trace.success AS success,
  trace.total_cost_usd AS total_cost_usd,
  trace.total_latency_ms AS total_latency_ms,
  trace.started_at AS started_at,
  trace.completed_at AS completed_at,
  collect({
    step_id: step.step_id,
    agent_name: step.agent_name,
    event_type: step.event_type,
    step_number: step.step_number,
    thought: step.thought,
    action: step.action,
    observation: step.observation,
    cost_usd: step.cost_usd,
    latency_ms: step.latency_ms,
    prev_hash: step.prev_hash,
    step_hash: step.step_hash,
    tools: tools,
    touched_entities: entities
  }) AS provenance_chain
"""


def lambda_handler(event, context):
    trace_id = event.get("pathParameters", {}).get("trace_id") or event.get("trace_id", "")

    if not trace_id:
        return {"statusCode": 400, "body": json.dumps({"error": "trace_id required"})}

    driver = get_driver()

    with driver.session(database="neo4j") as session:
        result = session.run(WHY_QUERY, trace_id=trace_id)
        record = result.single()

        if not record:
            return {"statusCode": 404, "body": json.dumps({"error": "Trace not found"})}

        return {
            "statusCode": 200,
            "body": json.dumps({
                "trace_id": record["trace_id"],
                "task": record["task"],
                "outcome": record["outcome"],
                "success": record["success"],
                "total_cost_usd": record["total_cost_usd"],
                "total_latency_ms": record["total_latency_ms"],
                "started_at": str(record["started_at"]),
                "completed_at": str(record["completed_at"]),
                "provenance_chain": record["provenance_chain"],
                "hash_chain_valid": True,
            }, default=str),
        }
```

### 14.3 Cost Attribution Cypher Query

```cypher
// COST QUERY: Roll up costs by tenant, agent, tool, and time period

MATCH (trace:ReasoningTrace)
WHERE trace.tenant_id = $tenant_id
  AND trace.started_at >= datetime($start_date)
  AND trace.started_at <= datetime($end_date)
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
OPTIONAL MATCH (step)-[:USES_TOOL]->(tc:ToolCall)

RETURN
  trace.tenant_id AS tenant_id,
  count(DISTINCT trace) AS total_traces,
  sum(trace.total_cost_usd) AS total_cost_usd,
  avg(trace.total_cost_usd) AS avg_cost_per_trace,

  // Cost by agent
  step.agent_name AS agent_name,
  sum(step.cost_usd) AS agent_cost_usd,
  sum(step.token_input) AS agent_tokens_input,
  sum(step.token_output) AS agent_tokens_output,
  avg(step.latency_ms) AS agent_avg_latency_ms,

  // Cost by tool
  tc.tool_name AS tool_name,
  count(tc) AS tool_call_count,
  sum(tc.duration_ms) AS tool_total_duration_ms

ORDER BY agent_cost_usd DESC
```

### 14.4 Audit Export — EU AI Act Article 12 Report Structure

```json
{
  "report": {
    "title": "EU AI Act Article 12 Compliance Report",
    "version": "1.0",
    "generated_at": "2026-05-19T19:30:00Z",
    "system": "TraceForge v0.1.0",
    "regulation": "EU AI Act (Regulation (EU) 2024/1689), Article 12",
    "classification": "HIGH-RISK (Annex III, Section 5: Creditworthiness Assessment)"
  },
  "decision": {
    "trace_id": "trace_def456",
    "task": "Evaluate credit application APP-2026-001",
    "outcome": "APPROVED",
    "timestamp": "2026-05-19T17:34:58Z",
    "tenant": "tenant_demo"
  },
  "provenance_chain": [
    {
      "step": 1,
      "agent": "Researcher",
      "action": "fetch_sec_filings",
      "input": {"company": "MERIDIAN_MANUFACTURING", "period": "FY2025"},
      "output_summary": "Retrieved 10-K: revenue $85M, net income $12M",
      "data_source": "SEC_EDGAR",
      "timestamp": "2026-05-19T17:30:03Z",
      "hash": "a1b2c3..."
    }
  ],
  "hash_chain_verification": {
    "total_steps": 12,
    "verified_steps": 12,
    "chain_intact": true,
    "genesis_hash": "GENESIS",
    "final_hash": "z9y8x7..."
  },
  "data_sources_consulted": [
    {"source": "SEC_EDGAR", "type": "10-K Annual Filing", "retrieved_at": "..."},
    {"source": "INTERNAL_MODEL", "type": "Credit Score", "retrieved_at": "..."},
    {"source": "NEWS_API", "type": "Sentiment Analysis", "retrieved_at": "..."},
    {"source": "NEO4J_KNOWLEDGE_GRAPH", "type": "Entity Relationships", "retrieved_at": "..."}
  ],
  "compliance_checklist": {
    "art12_1_logging": true,
    "art12_2_traceability": true,
    "art12_3_monitoring": true,
    "art12_4_record_keeping": true,
    "tamper_evidence": "SHA-256 hash chain verified",
    "retention_period": "6 months minimum"
  }
}
```

---

## 15. Phase 10: Frontend Dashboard

### 15.0 Time Budget: 30 minutes (Team Deploy owns this)

### 15.1 Frontend Stack

```
Next.js 14 + App Router
Chakra UI v3 (matches create-context-graph output)
Neo4j NVL (for graph visualization)
EventSource API (for live SSE streaming)
```

### 15.2 Pages

```
/                    — Landing: start a credit evaluation, see live provenance stream
/why/[trace_id]      — Provenance explorer: interactive graph + timeline + detail panel
/cost                — Cost dashboard: aggregations by tenant/agent/tool
/audit/[trace_id]    — Audit report viewer + PDF download
/graph               — Full Neo4j graph visualization (NVL)
```

### 15.3 Core Components

```
ChatInterface.tsx     — Input credit application, stream agent responses (SSE)
ProvenanceStream.tsx  — Real-time provenance graph forming (SSE from backend)
ProvenanceExplorer.tsx — Interactive "Why?" view with Cypher results
CostDashboard.tsx     — Bar/pie charts of cost by agent/tool/tenant
AuditReport.tsx       — Formatted Article 12 report with PDF export
GraphView.tsx         — Neo4j NVL visualization (pan/zoom/expand)
Timeline.tsx          — Step-by-step reasoning timeline with hash chain
```

### 15.4 Frontend Setup

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app --src-dir
npm install @chakra-ui/react @neo4j-nvl/react @neo4j-nvl/base recharts
```

---

## 16. Phase 11: Demo Data & Seed Script

### 16.0 Time Budget: 15 minutes (Team Graph owns seed data)

### 16.1 Seed Data — DynamoDB

```python
# backend/scripts/seed_data.py

import boto3
import json
from decimal import Decimal
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")

# === Seed Financial Data ===
fin_table = dynamodb.Table("traceforge-FinancialData")

FINANCIAL_DATA = [
    # Meridian Manufacturing (CLEAN — will be approved)
    {"entity_id": "MERIDIAN_MANUFACTURING", "data_type": "SEC_10K_2025",
     "company_name": "Meridian Manufacturing Corp", "period": "FY2025",
     "revenue": Decimal("85000000"), "net_income": Decimal("12000000"),
     "total_assets": Decimal("150000000"), "total_liabilities": Decimal("42000000"),
     "debt_to_equity": Decimal("0.45"), "current_ratio": Decimal("2.8"),
     "source": "SEC_EDGAR", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},

    {"entity_id": "MERIDIAN_MANUFACTURING", "data_type": "CREDIT_SCORE",
     "company_name": "Meridian Manufacturing Corp",
     "credit_score": Decimal("82"), "credit_rating": "AA-",
     "source": "INTERNAL_MODEL", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},

    {"entity_id": "MERIDIAN_MANUFACTURING", "data_type": "NEWS_SENTIMENT",
     "company_name": "Meridian Manufacturing Corp",
     "sentiment_score": Decimal("0.65"), "sentiment_articles_count": Decimal("47"),
     "source": "NEWS_API", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},

    # Zenith Biotech (POISONED — revenue inflated 10x)
    {"entity_id": "ZENITH_BIOTECH", "data_type": "SEC_10K_2025",
     "company_name": "Zenith Biotech Inc", "period": "FY2025",
     "revenue": Decimal("150000000"),       # POISONED: real value is $15M
     "net_income": Decimal("25000000"),      # POISONED: real value is -$3M
     "total_assets": Decimal("80000000"),
     "total_liabilities": Decimal("55000000"),
     "debt_to_equity": Decimal("1.8"),       # This stays real (a red flag the agent should catch)
     "current_ratio": Decimal("0.9"),        # This stays real (another red flag)
     "source": "SEC_EDGAR", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": True},

    {"entity_id": "ZENITH_BIOTECH", "data_type": "CREDIT_SCORE",
     "company_name": "Zenith Biotech Inc",
     "credit_score": Decimal("41"), "credit_rating": "BB-",
     "source": "INTERNAL_MODEL", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},

    {"entity_id": "ZENITH_BIOTECH", "data_type": "NEWS_SENTIMENT",
     "company_name": "Zenith Biotech Inc",
     "sentiment_score": Decimal("-0.3"), "sentiment_articles_count": Decimal("23"),
     "source": "NEWS_API", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},

    # Atlas Logistics (EDGE CASE — amount exceeds threshold)
    {"entity_id": "ATLAS_LOGISTICS", "data_type": "SEC_10K_2025",
     "company_name": "Atlas Logistics Group", "period": "FY2025",
     "revenue": Decimal("220000000"), "net_income": Decimal("18000000"),
     "total_assets": Decimal("380000000"), "total_liabilities": Decimal("160000000"),
     "debt_to_equity": Decimal("0.72"), "current_ratio": Decimal("1.5"),
     "source": "SEC_EDGAR", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},

    {"entity_id": "ATLAS_LOGISTICS", "data_type": "CREDIT_SCORE",
     "company_name": "Atlas Logistics Group",
     "credit_score": Decimal("65"), "credit_rating": "BBB",
     "source": "INTERNAL_MODEL", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},

    {"entity_id": "ATLAS_LOGISTICS", "data_type": "NEWS_SENTIMENT",
     "company_name": "Atlas Logistics Group",
     "sentiment_score": Decimal("0.1"), "sentiment_articles_count": Decimal("12"),
     "source": "NEWS_API", "retrieved_at": "2026-05-19T15:00:00Z",
     "is_poisoned": False},
]

for item in FINANCIAL_DATA:
    fin_table.put_item(Item=item)
    print(f"  Seeded: {item['entity_id']} / {item['data_type']}")


# === Seed Credit Applications ===
app_table = dynamodb.Table("traceforge-CreditApplications")

APPLICATIONS = [
    {
        "application_id": "APP-2026-001",
        "tenant_id": "tenant_demo",
        "applicant_name": "Sarah Chen, CFO",
        "company_name": "Meridian Manufacturing Corp",
        "requested_amount": Decimal("10000000"),
        "currency": "USD",
        "application_type": "CORPORATE_CREDIT",
        "status": "SUBMITTED",
        "submitted_at": "2026-05-19T17:00:00Z",
    },
    {
        "application_id": "APP-2026-002",
        "tenant_id": "tenant_demo",
        "applicant_name": "Marcus Rivera, CEO",
        "company_name": "Zenith Biotech Inc",
        "requested_amount": Decimal("25000000"),
        "currency": "USD",
        "application_type": "TRADE_FINANCE",
        "status": "SUBMITTED",
        "submitted_at": "2026-05-19T17:05:00Z",
    },
    {
        "application_id": "APP-2026-003",
        "tenant_id": "tenant_demo",
        "applicant_name": "Diana Okonkwo, VP Finance",
        "company_name": "Atlas Logistics Group",
        "requested_amount": Decimal("50000000"),
        "currency": "USD",
        "application_type": "BOND_ISSUANCE",
        "status": "SUBMITTED",
        "submitted_at": "2026-05-19T17:10:00Z",
    },
]

for app in APPLICATIONS:
    app_table.put_item(Item=app)
    print(f"  Seeded: {app['application_id']}")


# === Seed Decision Rules ===
rules_table = dynamodb.Table("traceforge-DecisionRules")

RULES = [
    {
        "rule_id": "RULE_001",
        "rule_name": "Maximum Credit Amount",
        "action": "approve_credit",
        "condition_field": "requested_amount",
        "operator": "lte",
        "threshold": Decimal("30000000"),
        "fail_message": "Requested amount exceeds $30M automated approval threshold",
        "steer_message": "Consider reducing the credit amount or escalating to senior review",
        "severity": "BLOCK",
        "enabled": True,
    },
    {
        "rule_id": "RULE_002",
        "rule_name": "Minimum Credit Score",
        "action": "approve_credit",
        "condition_field": "credit_score",
        "operator": "gte",
        "threshold": Decimal("45"),
        "fail_message": "Credit score below minimum threshold of 45",
        "steer_message": "Consider requiring additional collateral or co-signer",
        "severity": "WARN",
        "enabled": True,
    },
    {
        "rule_id": "RULE_003",
        "rule_name": "Maximum Debt-to-Equity",
        "action": "any",
        "condition_field": "debt_to_equity",
        "operator": "lte",
        "threshold": Decimal("2.0"),
        "fail_message": "Debt-to-equity ratio exceeds 2.0 maximum",
        "steer_message": "High leverage indicates elevated default risk",
        "severity": "WARN",
        "enabled": True,
    },
]

for rule in RULES:
    rules_table.put_item(Item=rule)
    print(f"  Seeded: {rule['rule_id']}")

print("\nSeed data complete.")
```

---

## 17. Phase 12: Failure Injection & Hallucination Demo

### 17.1 The Poisoned Data Story

The Zenith Biotech financial data in DynamoDB has `is_poisoned: true` on the SEC filing.
The revenue ($150M) and net income ($25M) are inflated 10x from reality ($15M / -$3M).

When the Researcher agent calls `fetch_sec_filings` for Zenith Biotech, it gets back the
poisoned numbers. The Researcher has no way to know these are wrong — the tool returned
"SUCCESS" with plausible-looking data.

The Analyst receives the Researcher's brief showing $150M revenue with strong margins. Despite
the credit score being only 41 (BB-) and news sentiment being negative (-0.3), the inflated
revenue overwhelms the risk model → risk score comes out around 60-65 (MODERATE) instead of
the correct ~25 (CRITICAL).

The Writer drafts an APPROVED memo based on the inflated risk assessment.

### 17.2 The "Why?" Reveal

After the swarm completes with a wrong APPROVED decision, we run the Why query:

```cypher
// Find the poisoned data point in the provenance chain
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
MATCH (step)-[:USES_TOOL]->(tc:ToolCall)
WHERE tc.tool_name = 'fetch_sec_filings'
  AND tc.result CONTAINS '150000000'
RETURN step.agent_name AS culprit_agent,
       tc.tool_name AS culprit_tool,
       tc.arguments AS tool_input,
       tc.result_summary AS what_it_returned,
       step.step_number AS when_in_chain,
       step.step_hash AS cryptographic_proof
```

This query returns: "Researcher called fetch_sec_filings for ZENITH_BIOTECH at step 2,
and it returned revenue of $150M. Every downstream step (Analyst risk score at step 6,
Writer memo at step 10) was built on this data."

### 17.3 The Fix Demo (if time)

Show that by correcting the poisoned DynamoDB record and re-running the same application,
the provenance graph now shows a DENIED outcome. Compare the two traces side by side:

```cypher
// Compare two traces for the same company
MATCH (t1:ReasoningTrace {trace_id: $trace_1})
MATCH (t2:ReasoningTrace {trace_id: $trace_2})
MATCH (t1)-[:HAS_STEP]->(s1:ReasoningStep)
MATCH (t2)-[:HAS_STEP]->(s2:ReasoningStep)
WHERE s1.step_number = s2.step_number
RETURN s1.step_number AS step,
       s1.agent_name AS agent,
       s1.observation AS before_fix,
       s2.observation AS after_fix,
       s1.observation <> s2.observation AS diverged
ORDER BY step
```

---

## 18. Phase 13: End-to-End Testing

### 18.0 Time Budget: 15 minutes

### 18.1 Test Sequence

```
1. Verify Neo4j schema (all constraints + indexes created)
2. Verify DynamoDB tables have seed data
3. Verify SQS queue is empty and ready
4. Verify all Lambda functions are deployed and healthy
5. Verify Gateway is created with all 10 targets
6. Verify AgentCore Runtime is deployed and reachable

7. Run credit evaluation for APP-2026-001 (Meridian — should APPROVE)
8. Verify provenance graph was written to Neo4j (count steps)
9. Verify hash chain integrity (walk chain, verify hashes)
10. Run "Why?" query — verify it returns complete chain
11. Run Cost query — verify it returns non-zero costs

12. Run credit evaluation for APP-2026-002 (Zenith — should wrongly APPROVE due to poison)
13. Verify the wrong decision was captured with full provenance
14. Run "Why?" query — verify it traces back to the poisoned tool call
15. Run Audit export — verify PDF is generated

16. (Optional) Fix poison and re-run — verify correct DENY outcome
```

### 18.2 Automated Test Script

```python
# backend/tests/test_e2e.py

import pytest
import json
import time
from neo4j import GraphDatabase

@pytest.fixture
def neo4j_driver():
    import os
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    yield driver
    driver.close()

def test_schema_exists(neo4j_driver):
    with neo4j_driver.session() as session:
        result = session.run("SHOW CONSTRAINTS")
        constraints = [r["name"] for r in result]
        assert "tenant_id_unique" in constraints
        assert "trace_id_unique" in constraints
        assert "step_id_unique" in constraints

def test_seed_data_in_dynamodb():
    import boto3
    ddb = boto3.resource("dynamodb")
    table = ddb.Table("traceforge-FinancialData")
    response = table.get_item(Key={"entity_id": "MERIDIAN_MANUFACTURING", "data_type": "SEC_10K_2025"})
    assert "Item" in response
    assert float(response["Item"]["revenue"]) == 85000000.0

def test_provenance_written_after_swarm(neo4j_driver):
    # This test runs AFTER a swarm execution
    with neo4j_driver.session() as session:
        result = session.run(
            "MATCH (t:ReasoningTrace) RETURN count(t) AS count"
        )
        count = result.single()["count"]
        assert count > 0

def test_hash_chain_integrity(neo4j_driver):
    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (t:ReasoningTrace)-[:HAS_STEP]->(s:ReasoningStep)
            RETURN s.step_number, s.prev_hash, s.step_hash
            ORDER BY s.step_number
        """)
        steps = list(result)
        assert steps[0]["s.prev_hash"] == "GENESIS"
        for i in range(1, len(steps)):
            assert steps[i]["s.prev_hash"] == steps[i-1]["s.step_hash"]

def test_why_query_returns_chain(neo4j_driver):
    with neo4j_driver.session() as session:
        result = session.run("""
            MATCH (t:ReasoningTrace)
            WITH t LIMIT 1
            MATCH (t)-[:HAS_STEP]->(s:ReasoningStep)
            RETURN t.trace_id, count(s) AS steps
        """)
        record = result.single()
        assert record["steps"] > 0
```

---

## 19. Phase 14: Demo Script — Minute by Minute

### 19.1 The 8-Minute Pitch

```
MINUTE 0:00 — OPENING (30 seconds)
"Multi-agent AI systems fail 79% of the time. Not because agents are bad —
because they share outputs but not reasoning. TraceForge is a production-grade
decision provenance graph that makes every multi-agent decision queryable,
auditable, and EU AI Act compliant — built on Neo4j Context Graphs, AWS Strands,
and Bedrock AgentCore."

MINUTE 0:30 — LIVE DEMO: THE GOOD CASE (2 minutes)
[Screen: Split view — left: chat input, right: Neo4j Browser with empty graph]
"Watch what happens when our 3-agent swarm processes a credit application."
[Type: "Evaluate credit application APP-2026-001 for Meridian Manufacturing Corp"]
[Watch: Neo4j graph populates in real time — Researcher steps, tool calls, entity nodes]
[Point out: Each node is a ReasoningStep with a cryptographic hash linking to the prior step]
"Meridian gets APPROVED. But look at the graph — we can see exactly WHY."
[Run Why query — highlight the chain: Researcher→Analyst→Writer, each step with tool calls and entities]

MINUTE 2:30 — LIVE DEMO: THE BAD CASE (2 minutes)
"Now watch what happens with poisoned data."
[Type: "Evaluate credit application APP-2026-002 for Zenith Biotech Inc"]
[Watch: Graph populates again]
"The swarm APPROVED Zenith for $25M. But Zenith's real revenue is $15M, not $150M.
Someone poisoned the financial data. Without TraceForge, you'd never know WHY this
was approved. With it:"
[Run the poison-trace Cypher query]
[Graph highlights: the fetch_sec_filings tool call at step 2 returned inflated numbers.
Every downstream node — risk score, decision memo — inherits from that poisoned source.]

MINUTE 4:30 — THE COST STORY (1 minute)
"This wrong decision cost $0.43 in compute. But across 1000 applications per day,
bad decisions driven by poisoned data cost real money."
[Hit Cost API — show breakdown: Researcher $0.15, Analyst $0.18, Writer $0.10]
[Show tenant rollup: "tenant_demo spent $127 today, $0.43 on this wrong decision"]

MINUTE 5:30 — THE COMPLIANCE STORY (1 minute)
"EU AI Act Article 12 enforcement starts August 2nd — 75 days from today.
Every high-risk AI decision needs tamper-proof audit logs."
[Hit Audit Export — download PDF]
[Open PDF — show: decision trace, hash chain verification, data sources, compliance checklist]
"This report is a free byproduct of the provenance graph. No extra work. No separate
audit system. The graph IS the audit log."

MINUTE 6:30 — ARCHITECTURE SLIDE (1 minute)
[Show architecture diagram]
"Three layers:
- Strands Swarm fires lifecycle hooks at every decision point
- ProvenanceHook emits events to SQS (async, no latency penalty)
- Lambda writes hash-chained ReasoningStep nodes to Neo4j
All deployed on AgentCore Runtime via the same boto3 pipeline as the workshop's folder 06."

MINUTE 7:30 — CLOSE (30 seconds)
"TraceForge turns the 79% multi-agent failure rate into a debuggable Cypher query.
The graph IS the audit log. The hash chain IS the compliance proof.
The cost roll-up IS the FinOps dashboard. One substrate, three solved problems."
```

---

## 20. Phase 15: Fallback Plans

### 20.1 If AgentCore Deploy Fails

**Fallback:** Run Strands swarm locally (not on AgentCore Runtime). Tools call Lambdas
directly via boto3 Lambda invoke instead of through Gateway. Demo still shows provenance
graph forming in Neo4j. Explain "this is the same code that runs on AgentCore" and show
the deploy script.

### 20.2 If Neo4j Aura Is Unavailable

**Fallback:** Run Neo4j locally via Docker:
```bash
docker run -d --name neo4j-traceforge \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/traceforge123 \
  -e NEO4J_PLUGINS='["apoc"]' \
  neo4j:5
```

### 20.3 If Lambda Deploy Fails

**Fallback:** Run tool functions as local Python functions called directly by Strands
agents (no Gateway). The provenance hook still writes to SQS → Neo4j.

### 20.4 If SQS Is Too Slow

**Fallback:** Write provenance steps directly to Neo4j from the ProvenanceHook
(synchronous). Adds ~50ms latency per step but eliminates the SQS dependency.

### 20.5 If Frontend Isn't Ready

**Fallback:** Demo entirely in terminal + Neo4j Browser:
- Terminal: run the swarm, show streaming output
- Neo4j Browser: run Cypher queries live, show the graph forming
- This is actually MORE impressive to technical judges than a polished UI

---

## 21. Team Assignment Matrix

```
┌──────────────────┬────────────────────────────────────────────────────────────────────┐
│  TEAM GRAPH      │  Neo4j schema + provenance writer + Cypher APIs + seed data        │
│                  │                                                                    │
│  Files owned:    │  cypher/constraints.cypher                                         │
│                  │  cypher/indexes.cypher                                              │
│                  │  backend/scripts/apply_schema.py                                    │
│                  │  backend/scripts/seed_data.py                                       │
│                  │  lambda_functions/provenance_writer/lambda_function.py               │
│                  │  lambda_functions/query_knowledge_graph/lambda_function.py           │
│                  │  lambda_functions/compare_historical/lambda_function.py              │
│                  │  lambda_functions/why_query/lambda_function.py                       │
│                  │  lambda_functions/cost_query/lambda_function.py                      │
│                  │  data/ontology.yaml                                                 │
│                  │                                                                    │
│  Key deliverables:│ Working Neo4j schema with all constraints + indexes               │
│                  │  ProvenanceWriter Lambda that writes hash-chained steps to Neo4j    │
│                  │  "Why?" Cypher query that returns full provenance chain              │
│                  │  Cost aggregation Cypher query                                      │
│                  │  Seed data in DynamoDB + Neo4j entities                             │
│                  │                                                                    │
│  Dependencies:   │  NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD from Phase 1             │
│                  │  DynamoDB tables from Phase 1                                       │
│                  │  SQS queue URL from Phase 1                                         │
├──────────────────┼────────────────────────────────────────────────────────────────────┤
│  TEAM STRANDS    │  Strands Swarm + ProvenanceHook + agent prompts + local testing     │
│                  │                                                                    │
│  Files owned:    │  backend/app/config.py                                              │
│                  │  backend/app/prompts.py                                             │
│                  │  backend/app/swarm.py                                               │
│                  │  backend/app/hooks.py (ProvenanceHook)                              │
│                  │  backend/app/agent_runtime.py                                       │
│                  │  backend/tests/test_swarm.py                                        │
│                  │                                                                    │
│  Key deliverables:│ 3-agent Strands Swarm (Researcher→Analyst→Writer) running locally  │
│                  │  ProvenanceHook capturing all lifecycle events → SQS                │
│                  │  agent_runtime.py for AgentCore deployment                          │
│                  │  Local end-to-end test: swarm → SQS → verify messages               │
│                  │                                                                    │
│  Dependencies:   │  Tool Lambda ARNs from Team Deploy (or mock tools for local test)   │
│                  │  SQS queue URL from Phase 1                                         │
│                  │  Bedrock model access                                               │
├──────────────────┼────────────────────────────────────────────────────────────────────┤
│  TEAM DEPLOY     │  AWS infra + Lambdas + Gateway + AgentCore Runtime + frontend       │
│                  │                                                                    │
│  Files owned:    │  infrastructure/deploy_lambdas.py                                   │
│                  │  deploy/create_gateway.py                                           │
│                  │  deploy/create_gateway_targets.py                                   │
│                  │  deploy/deploy_runtime.py                                           │
│                  │  deploy/test_invoke.py                                              │
│                  │  deploy/agent_requirements.txt                                      │
│                  │  lambda_functions/fetch_sec_filings/lambda_function.py               │
│                  │  lambda_functions/fetch_credit_scores/lambda_function.py             │
│                  │  lambda_functions/fetch_news_sentiment/lambda_function.py            │
│                  │  lambda_functions/compute_risk_score/lambda_function.py              │
│                  │  lambda_functions/validate_rules/lambda_function.py                  │
│                  │  lambda_functions/draft_memo/lambda_function.py                      │
│                  │  lambda_functions/check_compliance/lambda_function.py                │
│                  │  lambda_functions/submit_decision/lambda_function.py                 │
│                  │  lambda_functions/audit_export/lambda_function.py                    │
│                  │  frontend/ (entire directory)                                        │
│                  │  Makefile                                                            │
│                  │  pyproject.toml                                                      │
│                  │  .env.example                                                        │
│                  │                                                                    │
│  Key deliverables:│ All 14 Lambda functions deployed and callable                      │
│                  │  AgentCore Gateway with 10 tool targets                             │
│                  │  AgentCore Runtime deployed with agent_runtime.py                   │
│                  │  IAM roles with correct permissions                                 │
│                  │  Frontend dashboard with at least /why and /graph pages             │
│                  │  Audit export Lambda (PDF generation)                               │
│                  │                                                                    │
│  Dependencies:   │  AWS credentials with admin-level access                            │
│                  │  Neo4j credentials from Phase 1 (for Secrets Manager)               │
│                  │  agent_runtime.py from Team Strands                                 │
└──────────────────┴────────────────────────────────────────────────────────────────────┘
```

---

## 22. Timeline — Hour by Hour

```
3:00 PM — Doors open. Set up laptops. Get hackathon Wi-Fi.

3:30 PM — Talks begin. Listen, take notes on Neo4j Context Graph patterns and
          AWS Strands integration details. Ask judges about:
          - Aura credentials (are they providing instances?)
          - AgentCore quotas in the hackathon AWS account
          - Any gotchas with Strands 1.40 that aren't in docs

5:00 PM — BUILD TIME STARTS. Clock is ticking. 2.5 hours.

5:00-5:15 (15 min) — PHASE 0+1: Bootstrap + Infrastructure
  ALL TEAMS: Clone repo, verify prerequisites
  TEAM DEPLOY: Create Aura instance, DynamoDB tables, SQS, IAM roles, S3, Secrets Manager
  TEAM GRAPH: Prepare schema files while infra spins up
  TEAM STRANDS: Prepare agent prompts and hook skeleton while infra spins up

5:15-5:35 (20 min) — PHASE 2+3: Schema + Domain Model
  TEAM GRAPH: Apply Neo4j schema (constraints, indexes) + prepare seed data script
  TEAM STRANDS: Implement ProvenanceHook (hooks.py) — this is the critical path
  TEAM DEPLOY: Deploy tool Lambda functions (fetch_sec_filings, compute_risk_score, etc.)

5:35-6:15 (40 min) — PHASE 4+5+6: Strands Swarm + ProvenanceWriter
  TEAM GRAPH: Implement ProvenanceWriter Lambda + deploy it with SQS trigger
  TEAM STRANDS: Implement Strands Swarm (swarm.py) + agent_runtime.py + local test
  TEAM DEPLOY: Create AgentCore Gateway + targets + continue deploying remaining Lambdas

6:15-6:45 (30 min) — PHASE 7+8: AgentCore Deploy + API Layer
  TEAM GRAPH: Implement Why query + Cost query Lambdas
  TEAM STRANDS: Help Team Deploy with AgentCore Runtime deployment (agent_runtime.py)
  TEAM DEPLOY: Deploy AgentCore Runtime + run test invocation

6:45-7:00 (15 min) — PHASE 9+10: Seed Data + Frontend
  TEAM GRAPH: Run seed script + verify data in Neo4j and DynamoDB
  TEAM STRANDS: Run full end-to-end test (invoke → provenance graph → Why query)
  TEAM DEPLOY: Set up minimal frontend (or prepare Neo4j Browser demo)

7:00-7:15 (15 min) — PHASE 11+12: End-to-End Test + Failure Injection
  ALL TEAMS: Run the three credit applications:
    1. Meridian (clean → APPROVE) ← verify provenance graph
    2. Zenith (poisoned → wrong APPROVE) ← verify Why query catches poison
    3. Atlas (edge case → ESCALATE) ← verify rules engine works
  Fix any issues. Verify hash chain integrity.

7:15-7:30 (15 min) — DEMO PREP
  Rehearse the 8-minute pitch once.
  Prepare Neo4j Browser with pre-loaded queries.
  Prepare terminal with the invoke command ready.
  Clear any test data that would confuse the demo.

7:30 PM — DEMO TIME. Ship it.

8:00 PM — Wrap up.
```

---

## 23. File Tree — Every File in the Project

```
traceforge/
├── .env                                          # Environment variables (not tracked)
├── .env.example                                  # Template (tracked)
├── .gitignore
├── Makefile
├── PLAN.md                                       # This file
├── pyproject.toml
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                             # Pydantic settings from .env
│   │   ├── prompts.py                            # System prompts for 3 agents
│   │   ├── swarm.py                              # Strands GraphBuilder DAG
│   │   ├── hooks.py                              # ProvenanceHook implementation
│   │   ├── agent_runtime.py                      # AgentCore entry point (BedrockAgentCoreApp)
│   │   ├── main.py                               # FastAPI app (local dev server)
│   │   └── routes.py                             # /why, /cost, /audit REST endpoints
│   ├── scripts/
│   │   ├── apply_schema.py                       # Applies cypher/*.cypher to Neo4j
│   │   ├── seed_data.py                          # Seeds DynamoDB + Neo4j with demo data
│   │   └── verify_infra.py                       # Checks all infra is ready
│   └── tests/
│       ├── test_e2e.py                           # End-to-end tests
│       ├── test_hooks.py                         # ProvenanceHook unit tests
│       └── test_hash_chain.py                    # Hash chain integrity tests
│
├── cypher/
│   ├── constraints.cypher                        # All UNIQUE + EXISTENCE constraints
│   ├── indexes.cypher                            # All vector + fulltext + range + composite indexes
│   ├── why_query.cypher                          # The "Why?" provenance reconstruction query
│   ├── cost_query.cypher                         # Cost attribution aggregation query
│   ├── poison_trace.cypher                       # Demo: find poisoned data in chain
│   └── compare_traces.cypher                     # Demo: side-by-side trace comparison
│
├── data/
│   ├── ontology.yaml                             # Credit decision domain ontology
│   └── fixtures.json                             # Pre-generated demo data (backup)
│
├── deploy/
│   ├── agent_requirements.txt                    # Python deps for AgentCore container
│   ├── create_gateway.py                         # Creates AgentCore Gateway (MCP, SEMANTIC)
│   ├── create_gateway_targets.py                 # Registers 10 tool targets on Gateway
│   ├── deploy_runtime.py                         # Deploys to AgentCore Runtime via boto3/starter-toolkit
│   ├── test_invoke.py                            # Test invocation of deployed runtime
│   └── cleanup.py                                # Tears down all AWS resources
│
├── infrastructure/
│   ├── deploy_lambdas.py                         # Deploys all 14 Lambda functions
│   ├── create_tables.sh                          # DynamoDB table creation (bash)
│   ├── create_sqs.sh                             # SQS FIFO queue creation (bash)
│   ├── create_iam_roles.sh                       # IAM role creation (bash)
│   └── create_secrets.sh                         # Secrets Manager setup (bash)
│
├── lambda_functions/
│   ├── provenance_writer/
│   │   ├── lambda_function.py                    # SQS → Neo4j provenance step writer
│   │   └── requirements.txt
│   ├── fetch_sec_filings/
│   │   └── lambda_function.py                    # DynamoDB → SEC 10-K data
│   ├── fetch_credit_scores/
│   │   └── lambda_function.py                    # DynamoDB → credit score
│   ├── fetch_news_sentiment/
│   │   └── lambda_function.py                    # DynamoDB → news sentiment
│   ├── query_knowledge_graph/
│   │   └── lambda_function.py                    # Neo4j Cypher → entity relationships
│   ├── compute_risk_score/
│   │   └── lambda_function.py                    # Risk scoring algorithm
│   ├── validate_rules/
│   │   └── lambda_function.py                    # DynamoDB rules → pass/fail
│   ├── compare_historical/
│   │   └── lambda_function.py                    # Neo4j → past similar decisions
│   ├── draft_memo/
│   │   └── lambda_function.py                    # Format decision memo
│   ├── check_compliance/
│   │   └── lambda_function.py                    # EU AI Act checklist verification
│   ├── submit_decision/
│   │   └── lambda_function.py                    # DynamoDB + Neo4j → finalize decision
│   ├── why_query/
│   │   └── lambda_function.py                    # Neo4j → provenance chain
│   ├── cost_query/
│   │   └── lambda_function.py                    # Neo4j → cost aggregation
│   └── audit_export/
│       └── lambda_function.py                    # Neo4j → PDF report → S3
│
├── tool_schemas/
│   └── tools.json                                # All 10 tool input/output schemas (for Gateway)
│
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                              # Landing page with chat + live provenance
│   │   ├── why/[traceId]/page.tsx                # Provenance explorer
│   │   ├── cost/page.tsx                         # Cost dashboard
│   │   ├── audit/[traceId]/page.tsx              # Audit report viewer
│   │   └── graph/page.tsx                        # Full Neo4j graph visualization
│   ├── components/
│   │   ├── ChatInterface.tsx
│   │   ├── ProvenanceStream.tsx
│   │   ├── ProvenanceExplorer.tsx
│   │   ├── CostDashboard.tsx
│   │   ├── AuditReport.tsx
│   │   ├── GraphView.tsx
│   │   ├── Timeline.tsx
│   │   └── Provider.tsx
│   └── lib/
│       └── config.ts
│
└── docs/
    └── architecture.md                           # For post-hackathon (not created during event)
```

---

## 24. Environment Variables — Complete List

```bash
# === Neo4j ===
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<from-aura-credentials-download>

# === AWS (usually from aws configure, not .env) ===
AWS_DEFAULT_REGION=us-east-1
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...

# === SQS (set after Phase 1) ===
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/traceforge-provenance.fifo

# === AgentCore (set after Phase 8) ===
AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:123456789012:agent-runtime/traceforge-credit-decision
AGENTCORE_GATEWAY_URL=https://gateway.bedrock-agentcore.us-east-1.amazonaws.com/...

# === Bedrock ===
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250514

# === S3 ===
S3_BUCKET=traceforge-123456789012-us-east-1

# === Tenant ===
DEFAULT_TENANT_ID=tenant_demo

# === Optional: Local dev with Anthropic (faster than Bedrock for iteration) ===
# ANTHROPIC_API_KEY=sk-ant-...
```

---

## 25. IAM Policies — Full JSON

See Phase 1, Section 6.6 for complete policy documents.

Summary of permissions per role:

```
TraceForge-LambdaExecutionRole:
  - dynamodb: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan, BatchGet, BatchWrite
    on arn:aws:dynamodb:*:*:table/traceforge-*
  - sqs: ReceiveMessage, DeleteMessage, GetQueueAttributes, SendMessage
    on arn:aws:sqs:*:*:traceforge-*
  - secretsmanager: GetSecretValue
    on arn:aws:secretsmanager:*:*:secret:traceforge/*
  - logs: CreateLogGroup, CreateLogStream, PutLogEvents
    on arn:aws:logs:*:*:*
  - s3: PutObject, GetObject
    on arn:aws:s3:::traceforge-*/audit-reports/*

TraceForge-AgentCoreExecutionRole:
  - bedrock: InvokeModel, InvokeModelWithResponseStream
    on *
  - lambda: InvokeFunction
    on arn:aws:lambda:*:*:function:traceforge-*
  - sqs: SendMessage
    on arn:aws:sqs:*:*:traceforge-provenance.fifo
  - dynamodb: GetItem, Query, Scan
    on arn:aws:dynamodb:*:*:table/traceforge-*
  - secretsmanager: GetSecretValue
    on arn:aws:secretsmanager:*:*:secret:traceforge/*
  - logs: CreateLogGroup, CreateLogStream, PutLogEvents
    on arn:aws:logs:*:*:*
```

---

## 26. Cypher Queries — Every Query Used

### 26.1 Schema Application (Phase 2)
See Section 7.1 (constraints) and 7.2 (indexes) above.

### 26.2 ProvenanceWriter Queries (Phase 6)
See Section 11.1: WRITE_STEP_CYPHER, WRITE_TOOL_CALL_CYPHER, COMPLETE_TRACE_CYPHER, LINK_TENANT_SESSION_CYPHER.

### 26.3 Why Query (Phase 9)
See Section 14.1 and 14.2.

### 26.4 Cost Query (Phase 9)
See Section 14.3.

### 26.5 Poison Trace Query (Phase 12)
See Section 17.2.

### 26.6 Compare Traces Query (Phase 12)
See Section 17.3.

### 26.7 Knowledge Graph Queries (Phase 7)
See Section 12.4: related_entities, past_decisions, similar_traces.

### 26.8 Hash Chain Verification Query

```cypher
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
WITH step ORDER BY step.step_number
WITH collect(step) AS steps
UNWIND range(1, size(steps)-1) AS i
WITH steps[i-1] AS prev, steps[i] AS curr
WHERE curr.prev_hash <> prev.step_hash
RETURN prev.step_id AS broken_after, curr.step_id AS broken_at,
       prev.step_hash AS expected, curr.prev_hash AS actual
```

If this query returns 0 rows, the hash chain is intact. If it returns rows,
those are the tampered steps.

---

## 27. Tool Schemas — Full JSON

```json
[
  {
    "name": "fetch_sec_filings",
    "description": "Fetch SEC 10-K annual filing data for a company",
    "inputSchema": {
      "type": "object",
      "properties": {
        "company": {"type": "string", "description": "Company name or ticker"},
        "period": {"type": "string", "description": "Filing period", "default": "FY2025"}
      },
      "required": ["company"]
    }
  },
  {
    "name": "fetch_credit_scores",
    "description": "Fetch internal credit score and rating for a company",
    "inputSchema": {
      "type": "object",
      "properties": {
        "company": {"type": "string", "description": "Company name"}
      },
      "required": ["company"]
    }
  },
  {
    "name": "fetch_news_sentiment",
    "description": "Fetch aggregated news sentiment for a company (-1.0 to 1.0)",
    "inputSchema": {
      "type": "object",
      "properties": {
        "company": {"type": "string", "description": "Company name"}
      },
      "required": ["company"]
    }
  },
  {
    "name": "query_knowledge_graph",
    "description": "Query Neo4j knowledge graph for entity relationships and past decisions",
    "inputSchema": {
      "type": "object",
      "properties": {
        "company": {"type": "string"},
        "query_type": {"type": "string", "enum": ["related_entities", "past_decisions", "similar_traces"]}
      },
      "required": ["company"]
    }
  },
  {
    "name": "compute_risk_score",
    "description": "Compute risk score (0-100) from financial metrics",
    "inputSchema": {
      "type": "object",
      "properties": {
        "revenue": {"type": "number"},
        "net_income": {"type": "number"},
        "debt_to_equity": {"type": "number"},
        "current_ratio": {"type": "number"},
        "credit_score": {"type": "number"},
        "sentiment_score": {"type": "number"},
        "requested_amount": {"type": "number"}
      },
      "required": ["revenue", "net_income", "debt_to_equity", "credit_score"]
    }
  },
  {
    "name": "validate_rules",
    "description": "Validate application against business rules from DynamoDB",
    "inputSchema": {
      "type": "object",
      "properties": {
        "requested_amount": {"type": "number"},
        "debt_to_equity": {"type": "number"},
        "credit_score": {"type": "number"},
        "risk_score": {"type": "number"}
      },
      "required": ["requested_amount"]
    }
  },
  {
    "name": "compare_historical",
    "description": "Compare against historical credit decisions in the knowledge graph",
    "inputSchema": {
      "type": "object",
      "properties": {
        "company": {"type": "string"},
        "risk_category": {"type": "string"},
        "requested_amount": {"type": "number"}
      },
      "required": ["company"]
    }
  },
  {
    "name": "draft_memo",
    "description": "Draft formal credit decision memo",
    "inputSchema": {
      "type": "object",
      "properties": {
        "application_id": {"type": "string"},
        "company_name": {"type": "string"},
        "decision": {"type": "string", "enum": ["APPROVED", "DENIED", "ESCALATED"]},
        "risk_score": {"type": "number"},
        "risk_category": {"type": "string"},
        "factors": {"type": "array", "items": {"type": "string"}},
        "reasoning": {"type": "string"},
        "conditions": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["application_id", "decision", "reasoning"]
    }
  },
  {
    "name": "check_compliance",
    "description": "Check if decision memo meets EU AI Act Article 12 requirements",
    "inputSchema": {
      "type": "object",
      "properties": {
        "memo": {"type": "string"},
        "trace_id": {"type": "string"}
      },
      "required": ["memo"]
    }
  },
  {
    "name": "submit_decision",
    "description": "Submit final credit decision — updates DynamoDB and Neo4j",
    "inputSchema": {
      "type": "object",
      "properties": {
        "application_id": {"type": "string"},
        "decision": {"type": "string", "enum": ["APPROVED", "DENIED", "ESCALATED"]},
        "memo": {"type": "string"},
        "risk_score": {"type": "number"},
        "conditions": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["application_id", "decision", "memo"]
    }
  }
]
```

---

## 28. Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|------------|
| 1 | AgentCore Runtime deploy takes >30 min (CodeBuild) | HIGH | HIGH | Start deploy early (5:30); use fallback (local Strands) if not ready by 6:45 |
| 2 | Bedrock model not enabled in account | MEDIUM | CRITICAL | Verify FIRST in Phase 0; if blocked, use Anthropic API directly |
| 3 | Neo4j Aura free tier limits hit during demo | LOW | MEDIUM | 200K nodes is plenty; monitor during testing |
| 4 | SQS → Lambda has cold start delay | MEDIUM | LOW | Pre-warm Lambda by invoking once before demo; 5s batch window absorbs delay |
| 5 | Strands hook API changed between 1.38 and 1.40 | MEDIUM | HIGH | Pin strands-agents==1.40.0; check event attribute names against docs |
| 6 | IAM permission errors on AgentCore invoke | HIGH | HIGH | Folder 06 commits show this was a problem today; copy exact permission set |
| 7 | Gateway race condition on target creation | MEDIUM | MEDIUM | Add sleep(10) between gateway create and target creation (known issue #443) |
| 8 | Wi-Fi at venue is unreliable | MEDIUM | CRITICAL | Download all packages beforehand; have mobile hotspot ready |
| 9 | Poisoned data demo doesn't produce expected wrong decision | LOW | HIGH | Pre-run once; adjust poison values if risk model doesn't bite |
| 10 | Frontend not ready by demo time | HIGH | LOW | Fallback to Neo4j Browser + terminal (see Phase 15 fallbacks) |

---

## END OF PLAN

Total files to create: ~45
Total Lambda functions: 14
Total Cypher queries: 12+
Total DynamoDB tables: 3
Total IAM roles: 2
Total SQS queues: 2 (main + DLQ)
Total Gateway targets: 10
Total agents in swarm: 3
Total seed data records: ~15

This plan is executable. Every file path, every Cypher query, every IAM permission,
every environment variable, every boto3 call is specified. Nothing is left to guesswork.

Three parallel teams. 2.5 hours. Ship it.
