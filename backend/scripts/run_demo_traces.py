"""Run all 3 demo credit evaluations through the live swarm.

Generates real provenance traces in Neo4j for the hackathon demo.
Each case flows through: Researcher -> Analyst -> Writer.
"""

import logging
import sys
import traceback
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from neo4j import GraphDatabase

from backend.app import provenance_writer
from backend.app.config import config
from backend.app.swarm import create_credit_decision_swarm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


DEMO_CASES = [
    ("APP-2026-001", "Meridian Manufacturing Corp", 10_000_000, "CORPORATE_CREDIT"),
    ("APP-2026-002", "Zenith Biotech Inc", 25_000_000, "TRADE_FINANCE"),
    ("APP-2026-003", "Atlas Logistics Group", 50_000_000, "BOND_ISSUANCE"),
]


def run_case(app_id: str, company: str, amount: int, app_type: str) -> tuple[str, str, bool]:
    """Run a single credit evaluation case. Returns (trace_id, outcome, success)."""
    prompt = (
        f"Evaluate credit application {app_id} for {company} "
        f"requesting ${amount:,.0f} {app_type.lower().replace('_', ' ')}. "
        f"The application ID is {app_id}."
    )

    swarm, trace_id, session_id = create_credit_decision_swarm(tenant_id="tenant_demo")

    print(f"  Trace ID:   {trace_id}")
    print(f"  Session ID: {session_id}")
    print(f"  Prompt:     {prompt[:120]}...")
    print()

    try:
        result = swarm(prompt)
        result_text = str(result)

        # Determine outcome from result text
        outcome = "COMPLETED"
        for keyword in ["APPROVED", "DENIED", "ESCALATED", "APPROVE", "DENY", "ESCALATE"]:
            if keyword in result_text.upper():
                outcome = keyword.rstrip("D").rstrip("E") + "ED" if not keyword.endswith("ED") else keyword
                break

        # Mark trace as completed in Neo4j
        provenance_writer.complete_trace(trace_id, outcome=outcome, success=True)

        print("\n  Result (first 800 chars):")
        print(f"  {result_text[:800]}")
        if len(result_text) > 800:
            print(f"  ... ({len(result_text)} total chars)")

        return trace_id, outcome, True

    except Exception as e:
        logger.error(f"Swarm execution failed for {app_id}: {e}")
        traceback.print_exc()
        provenance_writer.complete_trace(trace_id, outcome=f"ERROR: {e}", success=False)
        return trace_id, f"ERROR: {e}", False


def verify_all_traces(trace_ids: list[str]) -> None:
    """Query Neo4j to verify all provenance traces were written."""
    driver = GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_username, config.neo4j_password),
    )

    print("\n" + "=" * 70)
    print("NEO4J PROVENANCE VERIFICATION")
    print("=" * 70)

    with driver.session(database=config.neo4j_database) as session:
        # Overall summary
        result = session.run("""
            MATCH (t:ReasoningTrace)
            WHERE t.trace_id IN $trace_ids
            OPTIONAL MATCH (t)-[:HAS_STEP]->(step:ReasoningStep)
            OPTIONAL MATCH (step)-[:USES_TOOL]->(tc:ToolCall)
            WITH t,
                 count(DISTINCT step) AS steps,
                 count(DISTINCT tc) AS tool_calls,
                 collect(DISTINCT step.agent_name) AS agents
            RETURN t.trace_id AS trace_id,
                   t.task AS task,
                   t.outcome AS outcome,
                   t.total_cost_usd AS total_cost_usd,
                   t.success AS success,
                   steps,
                   tool_calls,
                   agents
            ORDER BY t.started_at
        """, trace_ids=trace_ids)

        records = list(result)

        if not records:
            print("\n  NO TRACES FOUND IN NEO4J!")
            driver.close()
            return

        for rec in records:
            print(f"\n  Trace: {rec['trace_id']}")
            print(f"    Outcome:    {rec['outcome']}")
            print(f"    Steps:      {rec['steps']}")
            print(f"    Tool Calls: {rec['tool_calls']}")
            print(f"    Agents:     {rec['agents']}")
            print(f"    Cost (USD): ${rec['total_cost_usd']:.4f}")
            print(f"    Success:    {rec['success']}")

        # Hash chain integrity check
        print("\n  --- Hash Chain Integrity ---")
        for tid in trace_ids:
            chain_result = session.run("""
                MATCH (t:ReasoningTrace {trace_id: $trace_id})-[:HAS_STEP]->(step:ReasoningStep)
                WITH step ORDER BY step.step_number
                WITH collect({
                    step_number: step.step_number,
                    prev_hash: step.prev_hash,
                    step_hash: step.step_hash
                }) AS steps
                RETURN steps
            """, trace_id=tid)
            chain_record = chain_result.single()
            if chain_record and chain_record["steps"]:
                steps = chain_record["steps"]
                valid = True
                for i in range(1, len(steps)):
                    if steps[i]["prev_hash"] != steps[i - 1]["step_hash"]:
                        valid = False
                        break
                status = "VALID" if valid else "BROKEN"
                print(f"    {tid}: {status} ({len(steps)} steps chained)")

    driver.close()


def main() -> int:
    print("=" * 70)
    print("TRACEFORGE — Demo Credit Decision Traces")
    print(f"Model: {config.model_id}")
    print("=" * 70)

    trace_ids = []
    results = []

    for i, (app_id, company, amount, app_type) in enumerate(DEMO_CASES, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/3] {app_id}: {company} (${amount:,.0f} {app_type})")
        print(f"{'='*70}\n")

        trace_id, outcome, success = run_case(app_id, company, amount, app_type)
        trace_ids.append(trace_id)
        results.append((app_id, company, trace_id, outcome, success))

        print(f"\n  >>> {app_id} complete: {outcome}")

    # Verify all traces in Neo4j
    verify_all_traces(trace_ids)

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    all_ok = True
    for app_id, company, trace_id, outcome, success in results:
        status = "OK" if success else "FAIL"
        print(f"  [{status}] {app_id} | {company} | {trace_id} | {outcome}")
        if not success:
            all_ok = False

    print("=" * 70)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
