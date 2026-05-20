"""Test script — runs the TraceForge credit decision swarm end-to-end.

Creates the swarm, evaluates a credit application, prints results,
and verifies the provenance trace in Neo4j.
"""

import json
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from neo4j import GraphDatabase

from backend.app.config import config
from backend.app.swarm import create_credit_decision_swarm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def verify_provenance(trace_id: str) -> dict:
    """Query Neo4j to verify the provenance trace was written."""
    driver = GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_username, config.neo4j_password),
    )

    with driver.session(database=config.neo4j_database) as session:
        # Count steps in trace
        result = session.run(
            """
            MATCH (trace:ReasoningTrace {trace_id: $trace_id})
            OPTIONAL MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
            WITH trace, count(step) AS step_count,
                 collect(DISTINCT step.agent_name) AS agents,
                 collect(DISTINCT step.event_type) AS event_types
            RETURN trace.trace_id AS trace_id,
                   trace.tenant_id AS tenant_id,
                   trace.total_cost_usd AS total_cost,
                   trace.step_count AS step_count,
                   step_count AS actual_steps,
                   agents,
                   event_types
            """,
            trace_id=trace_id,
        )
        record = result.single()

        if not record:
            return {"found": False, "trace_id": trace_id}

        # Count tool calls
        tc_result = session.run(
            """
            MATCH (trace:ReasoningTrace {trace_id: $trace_id})-[:HAS_STEP]->(step:ReasoningStep)
            OPTIONAL MATCH (step)-[:USES_TOOL]->(tc:ToolCall)
            RETURN count(tc) AS tool_call_count,
                   collect(DISTINCT tc.tool_name) AS tools_used
            """,
            trace_id=trace_id,
        )
        tc_record = tc_result.single()

        # Check hash chain integrity
        chain_result = session.run(
            """
            MATCH (trace:ReasoningTrace {trace_id: $trace_id})-[:HAS_STEP]->(step:ReasoningStep)
            WITH step ORDER BY step.step_number
            WITH collect({
                step_number: step.step_number,
                prev_hash: step.prev_hash,
                step_hash: step.step_hash
            }) AS steps
            RETURN steps
            """,
            trace_id=trace_id,
        )
        chain_record = chain_result.single()
        chain_valid = True
        if chain_record and chain_record["steps"]:
            steps = chain_record["steps"]
            for i in range(1, len(steps)):
                if steps[i]["prev_hash"] != steps[i - 1]["step_hash"]:
                    chain_valid = False
                    break

    driver.close()

    return {
        "found": True,
        "trace_id": record["trace_id"],
        "tenant_id": record["tenant_id"],
        "total_cost_usd": record["total_cost"],
        "step_count": record["actual_steps"],
        "agents": record["agents"],
        "event_types": record["event_types"],
        "tool_calls": tc_record["tool_call_count"] if tc_record else 0,
        "tools_used": tc_record["tools_used"] if tc_record else [],
        "hash_chain_valid": chain_valid,
    }


def main():
    print("=" * 70)
    print("TRACEFORGE — Credit Decision Swarm Test")
    print("=" * 70)
    print()

    prompt = (
        "Evaluate credit application APP-2026-001 for Meridian Manufacturing Corp "
        "requesting $10M corporate credit line."
    )

    print(f"[PROMPT] {prompt}")
    print()
    print("-" * 70)
    print("[CREATING SWARM]")

    swarm, trace_id, session_id = create_credit_decision_swarm()

    print(f"  Trace ID:   {trace_id}")
    print(f"  Session ID: {session_id}")
    print(f"  Model:      {config.model_id}")
    print()
    print("-" * 70)
    print("[RUNNING SWARM]")
    print()

    try:
        result = swarm(prompt)
        result_text = str(result)

        print()
        print("-" * 70)
        print("[SWARM RESULT]")
        print()
        print(result_text[:3000])
        if len(result_text) > 3000:
            print(f"\n... ({len(result_text)} total characters)")

    except Exception as e:
        logger.error(f"Swarm execution failed: {e}", exc_info=True)
        print(f"\n[ERROR] Swarm failed: {e}")
        result_text = f"ERROR: {e}"

    print()
    print("-" * 70)
    print("[VERIFYING PROVENANCE IN NEO4J]")
    print()

    provenance = verify_provenance(trace_id)

    if provenance["found"]:
        print(f"  Trace found:       YES")
        print(f"  Steps recorded:    {provenance['step_count']}")
        print(f"  Agents observed:   {provenance['agents']}")
        print(f"  Event types:       {provenance['event_types']}")
        print(f"  Tool calls:        {provenance['tool_calls']}")
        print(f"  Tools used:        {provenance['tools_used']}")
        print(f"  Hash chain valid:  {provenance['hash_chain_valid']}")
        print(f"  Total cost (USD):  ${provenance['total_cost_usd']:.6f}")
    else:
        print(f"  Trace found: NO (trace_id={trace_id})")
        print("  This may indicate the provenance writer failed to connect to Neo4j.")

    print()
    print("=" * 70)
    print("[DONE]")
    print("=" * 70)

    return 0 if provenance.get("found") else 1


if __name__ == "__main__":
    sys.exit(main())
