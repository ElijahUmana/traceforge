"""Neo4j Cypher query functions for TraceForge API layer.

Implements:
- "Why?" query (PLAN.md Section 14.1) -- full provenance chain for a trace
- Cost attribution query (PLAN.md Section 14.3) -- cost rollup by tenant/agent/tool
- Hash chain verification query (PLAN.md Section 26.8) -- tamper detection
- Poison trace query (PLAN.md Section 17.2) -- find poisoned data in provenance chain
"""

from typing import Any

from neo4j import Driver

# --- "Why?" Query (Section 14.1) ---

WHY_QUERY_CYPHER = """
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


# --- Cost Attribution Query (Section 14.3) ---

COST_QUERY_CYPHER = """
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
"""


# --- Hash Chain Verification Query (Section 26.8) ---

HASH_CHAIN_VERIFY_CYPHER = """
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
WITH step ORDER BY step.step_number
WITH collect(step) AS steps
UNWIND range(1, size(steps)-1) AS i
WITH steps[i-1] AS prev, steps[i] AS curr
WHERE curr.prev_hash <> prev.step_hash
RETURN prev.step_id AS broken_after, curr.step_id AS broken_at,
       prev.step_hash AS expected, curr.prev_hash AS actual
"""

# Supplementary query: get the full hash chain for a trace
HASH_CHAIN_FULL_CYPHER = """
MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
RETURN step.step_id AS step_id,
       step.step_number AS step_number,
       step.prev_hash AS prev_hash,
       step.step_hash AS step_hash,
       step.agent_name AS agent_name
ORDER BY step.step_number
"""


# --- Poison Trace Query (Section 17.2) ---

POISON_TRACE_CYPHER = """
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
"""


# --- Python query functions ---

def why_query(driver: Driver, trace_id: str, database: str = "neo4j") -> dict[str, Any] | None:
    """Execute the "Why?" provenance query for a given trace.

    Returns the full provenance chain including all reasoning steps,
    tool calls, and touched entities -- or None if the trace is not found.

    Args:
        driver: Neo4j driver instance (connection pool).
        trace_id: The trace_id to query.
        database: Neo4j database name.

    Returns:
        Dict with trace metadata and provenance_chain list, or None.
    """
    with driver.session(database=database) as session:
        result = session.run(WHY_QUERY_CYPHER, trace_id=trace_id)
        record = result.single()

        if not record:
            return None

        return {
            "trace_id": record["trace_id"],
            "task": record["task"],
            "outcome": record["outcome"],
            "success": record["success"],
            "total_cost_usd": record["total_cost_usd"],
            "total_latency_ms": record["total_latency_ms"],
            "started_at": str(record["started_at"]) if record["started_at"] else None,
            "completed_at": str(record["completed_at"]) if record["completed_at"] else None,
            "provenance_chain": _serialize_provenance_chain(record["provenance_chain"]),
        }


def cost_query(
    driver: Driver,
    tenant_id: str,
    start_date: str,
    end_date: str,
    database: str = "neo4j",
) -> dict[str, Any]:
    """Execute the cost attribution query for a tenant and date range.

    Returns cost breakdown by agent and tool within the specified period.

    Args:
        driver: Neo4j driver instance.
        tenant_id: Tenant to query costs for.
        start_date: ISO 8601 start date (inclusive).
        end_date: ISO 8601 end date (inclusive).
        database: Neo4j database name.

    Returns:
        Dict with tenant_id, summary totals, and per-agent/tool breakdowns.
    """
    with driver.session(database=database) as session:
        result = session.run(COST_QUERY_CYPHER, {
            "tenant_id": tenant_id,
            "start_date": start_date,
            "end_date": end_date,
        })
        records = list(result)

        if not records:
            return {
                "tenant_id": tenant_id,
                "start_date": start_date,
                "end_date": end_date,
                "total_traces": 0,
                "total_cost_usd": 0.0,
                "avg_cost_per_trace": 0.0,
                "by_agent": [],
                "by_tool": [],
            }

        # Aggregate records into by-agent and by-tool breakdowns
        agents: dict[str, dict] = {}
        tools: dict[str, dict] = {}
        total_traces = 0
        total_cost = 0.0
        avg_cost = 0.0

        for rec in records:
            total_traces = rec["total_traces"]
            total_cost = rec["total_cost_usd"] or 0.0
            avg_cost = rec["avg_cost_per_trace"] or 0.0

            agent_name = rec["agent_name"]
            if agent_name and agent_name not in agents:
                agents[agent_name] = {
                    "agent_name": agent_name,
                    "cost_usd": rec["agent_cost_usd"] or 0.0,
                    "tokens_input": rec["agent_tokens_input"] or 0,
                    "tokens_output": rec["agent_tokens_output"] or 0,
                    "avg_latency_ms": rec["agent_avg_latency_ms"] or 0.0,
                }

            tool_name = rec["tool_name"]
            if tool_name and tool_name not in tools:
                tools[tool_name] = {
                    "tool_name": tool_name,
                    "call_count": rec["tool_call_count"] or 0,
                    "total_duration_ms": rec["tool_total_duration_ms"] or 0,
                }

        return {
            "tenant_id": tenant_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_traces": total_traces,
            "total_cost_usd": total_cost,
            "avg_cost_per_trace": avg_cost,
            "by_agent": list(agents.values()),
            "by_tool": list(tools.values()),
        }


def verify_hash_chain(
    driver: Driver, trace_id: str, database: str = "neo4j"
) -> dict[str, Any]:
    """Verify the hash chain integrity for a trace.

    Walks the chain of ReasoningSteps and checks that each step's prev_hash
    matches the previous step's step_hash. If the query returns 0 rows, the
    chain is intact. Any rows returned indicate tampered steps.

    Args:
        driver: Neo4j driver instance.
        trace_id: The trace_id to verify.
        database: Neo4j database name.

    Returns:
        Dict with chain_intact (bool), total_steps, verified_steps, and
        any broken_links found.
    """
    with driver.session(database=database) as session:
        # Get the full chain to count steps and verify genesis
        full_result = session.run(HASH_CHAIN_FULL_CYPHER, trace_id=trace_id)
        full_chain = list(full_result)

        if not full_chain:
            return {
                "trace_id": trace_id,
                "chain_intact": False,
                "total_steps": 0,
                "verified_steps": 0,
                "genesis_valid": False,
                "broken_links": [],
                "error": "No steps found for trace",
            }

        total_steps = len(full_chain)
        genesis_valid = full_chain[0]["prev_hash"] == "GENESIS"

        # Check for broken links
        broken_result = session.run(HASH_CHAIN_VERIFY_CYPHER, trace_id=trace_id)
        broken_links = [
            {
                "broken_after": rec["broken_after"],
                "broken_at": rec["broken_at"],
                "expected_hash": rec["expected"],
                "actual_hash": rec["actual"],
            }
            for rec in broken_result
        ]

        chain_intact = genesis_valid and len(broken_links) == 0
        verified_steps = total_steps - len(broken_links)

        return {
            "trace_id": trace_id,
            "chain_intact": chain_intact,
            "total_steps": total_steps,
            "verified_steps": verified_steps,
            "genesis_valid": genesis_valid,
            "genesis_hash": full_chain[0]["prev_hash"],
            "final_hash": full_chain[-1]["step_hash"],
            "broken_links": broken_links,
        }


def poison_trace_query(
    driver: Driver, trace_id: str, database: str = "neo4j"
) -> list[dict[str, Any]]:
    """Find poisoned data points in a provenance chain.

    Searches for fetch_sec_filings tool calls that returned the known
    poisoned revenue value ($150M) in the given trace.

    Args:
        driver: Neo4j driver instance.
        trace_id: The trace_id to search for poison.
        database: Neo4j database name.

    Returns:
        List of dicts with culprit_agent, culprit_tool, tool_input,
        what_it_returned, when_in_chain, and cryptographic_proof.
        Empty list if no poisoned data found.
    """
    with driver.session(database=database) as session:
        result = session.run(POISON_TRACE_CYPHER, trace_id=trace_id)
        return [
            {
                "culprit_agent": rec["culprit_agent"],
                "culprit_tool": rec["culprit_tool"],
                "tool_input": rec["tool_input"],
                "what_it_returned": rec["what_it_returned"],
                "when_in_chain": rec["when_in_chain"],
                "cryptographic_proof": rec["cryptographic_proof"],
            }
            for rec in result
        ]


# --- Helpers ---

def _serialize_provenance_chain(chain: list[dict]) -> list[dict]:
    """Serialize provenance chain records for JSON output.

    Converts neo4j datetime objects to strings and filters out null
    tool call / entity entries from OPTIONAL MATCH.
    """
    serialized = []
    for step in chain:
        if step.get("step_id") is None:
            continue  # Skip null rows from OPTIONAL MATCH

        tools = [
            t for t in (step.get("tools") or [])
            if t.get("call_id") is not None
        ]
        entities = [
            e for e in (step.get("touched_entities") or [])
            if e.get("entity_id") is not None
        ]

        serialized.append({
            "step_id": step["step_id"],
            "agent_name": step["agent_name"],
            "event_type": step["event_type"],
            "step_number": step["step_number"],
            "thought": step.get("thought"),
            "action": step.get("action"),
            "observation": step.get("observation"),
            "cost_usd": step.get("cost_usd"),
            "latency_ms": step.get("latency_ms"),
            "prev_hash": step.get("prev_hash"),
            "step_hash": step.get("step_hash"),
            "tools": tools,
            "touched_entities": entities,
        })

    return serialized


# --- Recomputing chain verification ---

VERIFY_CHAIN_FETCH_CYPHER = """
MATCH (trace:ReasoningTrace {trace_id: $trace_id})-[:HAS_STEP]->(step:ReasoningStep)
RETURN step.trace_id        AS trace_id,
       step.step_id         AS step_id,
       step.step_number     AS step_number,
       step.agent_name      AS agent_name,
       step.event_type      AS event_type,
       step.created_at_iso  AS created_at_iso,
       step.thought         AS thought,
       step.action          AS action,
       step.observation     AS observation,
       step.model_id        AS model_id,
       step.token_input     AS token_input,
       step.token_output    AS token_output,
       step.cost_usd        AS cost_usd,
       step.latency_ms      AS latency_ms,
       step.status          AS status,
       step.prev_hash       AS prev_hash,
       step.step_hash       AS step_hash
ORDER BY step.step_number
"""


def verify_trace_chain(
    driver: Driver, trace_id: str, database: str = "neo4j"
) -> dict[str, Any]:
    """Recompute a trace's hash chain from its persisted fields.

    Unlike a linkage-only check, this re-derives each step_hash from the row's
    own content, so an edit to a stored field is detected even though every
    prev_hash still matches its predecessor.
    """
    from backend.app.hashchain import verify_chain

    with driver.session(database=database) as session:
        rows = [dict(record) for record in session.run(
            VERIFY_CHAIN_FETCH_CYPHER, trace_id=trace_id
        )]

    return verify_chain(rows)
