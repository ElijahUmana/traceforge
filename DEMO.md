# TraceForge Demo Script
## Hack Day: Context Graphs for Multi-Agent AI — May 19, 2026

**Total time: 8 minutes**
**Presenters: Elijah, Jay, Ngan**

---

## Pre-Demo Checklist (do at 7:15 PM)

```bash
# Terminal 1: Backend
cd ~/traceforge
source .venv/bin/activate
pkill -f uvicorn 2>/dev/null
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd ~/traceforge/frontend
npm run dev

# Verify
curl -s http://localhost:8000/api/health  # should return {"status":"ok","neo4j":true}
```

**Browser tabs to have open (in order):**
1. `http://localhost:3000` — TraceForge landing page (Evaluate tab)
2. `http://localhost:3000/traces` — Traces list
3. `http://localhost:3000/why/trace_2ac6cd413c31` — Meridian provenance (pre-loaded, APPROVED)
4. `http://localhost:3000/why/trace_4f7738b5829a` — Zenith provenance (pre-loaded, DENIED)
5. `http://localhost:3000/cost` — Cost dashboard
6. `http://localhost:3000/audit/trace_4f7738b5829a` — Zenith audit report
7. `http://localhost:3000/graph` — Graph visualization

**Keep the first tab (Evaluate) active when you start.**

---

## MINUTE 0:00 — OPENING (45 seconds)

**Screen: TraceForge landing page visible**

**Script:**

> "Multi-agent AI systems fail 79% of the time. Not because the models are bad — because agents share outputs but not reasoning.
>
> When a Strands swarm of three agents makes a credit decision, you cannot answer: which agent decided what, based on which data, at what cost, and was that data even valid?
>
> TraceForge solves this. It captures every multi-agent decision as a queryable Neo4j provenance graph — in real time, with tamper-proof hash chains. One Cypher query reconstructs the entire decision. EU AI Act compliance falls out as a free byproduct.
>
> Built with Neo4j Context Graphs, AWS Strands Agents, and Bedrock AgentCore. Let me show you."

---

## MINUTE 0:45 — THE SYSTEM (1 minute)

**Screen: TraceForge landing page — point at the three demo scenario buttons**

**Script:**

> "Here's our credit decision pipeline. Three Strands agents in a GraphBuilder DAG:
>
> **Researcher** fetches SEC filings, credit scores, news sentiment, and queries the Neo4j knowledge graph. Four tools.
>
> **Analyst** computes risk scores, validates against business rules, compares to historical decisions. Three tools.
>
> **Writer** drafts the decision memo, checks EU AI Act compliance, and submits the final decision. Three tools.
>
> Ten tools total. Every tool call, every model call, every agent handoff fires a Strands lifecycle hook. Our ProvenanceHook captures each event, computes a SHA-256 hash chaining it to the prior step, and writes it directly to Neo4j as a ReasoningStep node with typed edges."

**Action: Click on "Traces" in the nav bar**

---

## MINUTE 1:45 — THE TRACES (1 minute)

**Screen: Traces list page showing all traces with color-coded outcomes**

**Script:**

> "Here's every decision our swarm has made. Each card is a complete reasoning trace stored in Neo4j.
>
> Notice the outcomes: green for APPROVED, red for DENIED, yellow for ESCALATED. Each trace has the agent count, step count, and cost.
>
> Let's look at a clean decision first."

**Action: Click on the Meridian Manufacturing trace (APPROVED, green)**

---

## MINUTE 2:45 — THE GOOD CASE: Provenance Explorer (2 minutes)

**Screen: Why page for Meridian — shows header with APPROVED badge + CHAIN INTACT badge + stat boxes**

**Script:**

> "This is the provenance explorer for Meridian Manufacturing's $10M credit application. APPROVED.
>
> Look at the header: 37 reasoning steps across 3 agents, 11 tool calls, total cost four cents. And the hash chain is verified INTACT — meaning no step was tampered with after the fact."

**Action: Point at the stat boxes (Steps: 37, Agents: 3, Tool Calls: 11, Cost, Latency)**

> "Now look at the timeline. Each section is color-coded by agent — blue for Researcher, orange for Analyst, green for Writer."

**Action: Click "Expand All" button**

> "Every step is expandable. Let me show you a tool call."

**Action: Click on a TOOL_CALL_END step for fetch_sec_filings**

> "Here's the Researcher calling fetch_sec_filings. You can see the exact arguments it passed, the result it got back — revenue $85 million, net income $12 million — the latency, and the cryptographic hash linking this step to the prior one.
>
> This is not a log. This is a graph. Every step has typed edges: HAS_STEP from the trace, USES_TOOL to the tool call, NEXT_STEP to the following step. One Cypher query traverses the entire chain."

**Action: Scroll down to show the Analyst section, then Writer section**

> "The Analyst received the Researcher's brief, computed a risk score of 85 — LOW risk — validated against three business rules, all passed. The Writer drafted the memo and submitted APPROVED.
>
> That's the happy path. Now let's see what happens with bad data."

**Action: Click "Back to traces" → Click the Zenith Biotech trace (DENIED, red)**

---

## MINUTE 4:45 — THE BAD CASE: Poisoned Data Detection (2 minutes)

**Screen: Why page for Zenith Biotech — DENIED badge + CHAIN INTACT**

**Script:**

> "Zenith Biotech applied for $25 million. The system DENIED it. But here's the critical question: was the denial based on accurate data?
>
> Look at the provenance chain."

**Action: Click "Expand All" → scroll to the Researcher's fetch_sec_filings TOOL_CALL_END step**

> "The Researcher fetched Zenith's SEC filing. The tool returned revenue of $150 million and net income of $25 million. But Zenith's REAL revenue is $15 million — they're actually losing $3 million a year. Someone poisoned the financial data. The revenue was inflated ten times.
>
> Without TraceForge, you'd never know this data entered the pipeline. The system happened to deny Zenith anyway because the credit score was 41 and sentiment was negative — but the poisoned revenue DID influence the risk calculation. On a different day, with slightly different thresholds, this poisoned data could have caused a wrongful approval of $25 million in credit.
>
> The point isn't that the system got lucky. The point is that we can trace EXACTLY where bad data entered, which agents consumed it, and how it propagated through the decision chain. That's what a provenance graph gives you that logs never will."

**Action: Point at the hash chain at the bottom of the expanded step**

> "And every step is hash-chained. If someone tries to edit the graph after the fact — change the revenue number, remove a step — the chain breaks. Tamper-evident by construction."

---

## MINUTE 6:45 — COMPLIANCE + COST (1 minute)

**Action: Click "View Audit Report" link in the header → Audit page loads**

**Screen: Audit report for Zenith Biotech**

**Script:**

> "EU AI Act Article 12 enforcement starts August 2nd — 75 days from today. Credit decisions are explicitly classified as high-risk AI. Every decision needs six months of tamper-proof audit logs.
>
> This is the audit report — generated directly from the provenance graph. Decision summary, the full chain with every agent and tool call, hash chain verification showing all steps intact, data sources consulted, and the Article 12 compliance checklist. Six checks, all passing.
>
> This isn't a separate audit system bolted on. The graph IS the audit log. Compliance is a free byproduct of the provenance architecture."

**Action: Click "Cost" in the nav bar**

**Screen: Cost dashboard**

> "And cost attribution per decision. Every reasoning step carries its cost in tokens and dollars. We can roll up by agent, by tool, by tenant, by time period. The Zenith decision cost four cents. Across a thousand applications per day, you're looking at forty dollars — but one wrong decision on a $25 million credit line costs a lot more than forty dollars."

---

## MINUTE 7:45 — ARCHITECTURE + CLOSE (45 seconds)

**Action: Click "Graph" in the nav bar (if the visualization loads) OR stay on cost page**

**Script:**

> "Under the hood:
>
> **Neo4j Context Graph** — the provenance substrate. ReasoningTrace nodes connected to ReasoningSteps via HAS_STEP edges, steps connected to ToolCalls via USES_TOOL, steps linked sequentially via NEXT_STEP, and TOUCHED edges connecting steps to the entities they consulted. Seventeen constraints, seventeen indexes, vector search ready.
>
> **AWS Strands Agents** — the execution engine. GraphBuilder DAG with three agents, ten tools, and a ProvenanceHook that intercepts every lifecycle event. BeforeToolCallEvent, AfterToolCallEvent, AfterModelCallEvent — all captured, hashed, persisted.
>
> **Bedrock AgentCore** — the production deployment target. We have the deploy script ready — Gateway with ten MCP tool targets, Runtime deployment via boto3, the same pattern as the workshop's folder 06.
>
> TraceForge turns the 79% multi-agent failure rate into a debuggable Cypher query. The graph is the audit log. The hash chain is the compliance proof. The cost rollup is the FinOps dashboard. One substrate, three solved problems.
>
> Thank you."

---

## BACKUP: If Asked Questions

**Q: "How does the hash chain work?"**
> "Each ReasoningStep has a prev_hash and step_hash field. step_hash is the SHA-256 of the previous hash concatenated with the step's trace ID, agent name, step number, tool name, arguments, result, and timestamp. To verify, you walk the chain from step 1 to step N, recomputing each hash. If any hash doesn't match, that step was altered. We have a Cypher query that does this verification in one shot."

**Q: "What about latency? Doesn't writing to Neo4j on every step slow down the agents?"**
> "In our local demo, writes are synchronous and add about 50ms per step. In the production architecture, the ProvenanceHook emits to an SQS FIFO queue asynchronously — the agent doesn't wait for the write. A Lambda polls the queue and batch-writes to Neo4j. Zero latency impact on the agent."

**Q: "How does this scale to many agents or many tenants?"**
> "Each trace is namespaced by tenant_id. The Tenant node is the root — HAS_SESSION → HAS_TRACE → HAS_STEP. Multi-tenant isolation is graph-native. For scaling, Neo4j Aura handles the throughput; the provenance writer Lambda scales with the SQS queue depth."

**Q: "Why Neo4j instead of just logging to CloudWatch or a database?"**
> "Logs are flat. You can grep them. A relational database gives you tables you can join. But provenance is a GRAPH problem — 'which entity did this step touch, and what other steps touched that same entity, and what decisions did those steps feed into?' That's a multi-hop traversal. One Cypher query. In SQL, that's five joins minimum. In logs, it's impossible."

**Q: "Is this actually compliant with the EU AI Act?"**
> "Article 12 requires automatic logging of events during operation, traceability of decisions, and tamper-proof retention for six months. The provenance graph with hash chains satisfies all three. We're not lawyers, but the architecture maps directly to the regulation's technical requirements. The audit report generates the specific Article 12.1 through 12.4 checklist."

**Q: "How long did this take to build?"**
> "Two and a half hours, three people, three parallel Claude Code agent teams. One team built the Neo4j schema and provenance writer, one built the Strands swarm and ProvenanceHook, one built the FastAPI backend and Next.js frontend. The plan was 4,800 lines written before we started coding."

---

## KEY URLS FOR DEMO

| What | URL |
|------|-----|
| Landing / Evaluate | http://localhost:3000 |
| Traces list | http://localhost:3000/traces |
| Meridian provenance | http://localhost:3000/why/trace_2ac6cd413c31 |
| Zenith provenance | http://localhost:3000/why/trace_4f7738b5829a |
| Atlas provenance | http://localhost:3000/why/trace_503f27fab44f |
| Cost dashboard | http://localhost:3000/cost |
| Zenith audit report | http://localhost:3000/audit/trace_4f7738b5829a |
| Graph visualization | http://localhost:3000/graph |
| Backend health | http://localhost:8000/api/health |
| GitHub repo | https://github.com/ElijahUmana/traceforge |
