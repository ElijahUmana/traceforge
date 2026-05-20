"""Provenance writer -- persists hook events to Neo4j as :ReasoningStep nodes.

Provides two APIs:
1. Functional API (used by ProvenanceHook):
   - write_step(event_data) -- writes a single event via the config singleton driver
   - complete_trace(trace_id, outcome, success) -- marks a trace as completed

2. Class-based API (for direct injection):
   - ProvenanceWriter(driver) -- accepts a neo4j.Driver instance
   - writer.write_provenance_event(event) -- writes a single event
   - writer.complete_trace(trace_id, outcome, success) -- marks trace completed

Both APIs use the same Cypher from PLAN.md Section 11.1.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from neo4j import Driver, GraphDatabase

from backend.app.config import config

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def _get_driver() -> Driver:
    """Get or create the Neo4j driver singleton."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_username, config.neo4j_password),
        )
    return _driver


# ---------------------------------------------------------------------------
# Cypher queries from PLAN.md Section 11.1
# ---------------------------------------------------------------------------

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


WRITE_TOUCHED_ENTITY_CYPHER = """
MATCH (step:ReasoningStep {step_id: $step_id})
MATCH (entity:Entity {entity_id: $entity_id})
MERGE (step)-[:TOUCHED {access_type: $access_type, timestamp: datetime($timestamp)}]->(entity)
"""


WRITE_TOUCHED_FINANCIAL_CYPHER = """
MATCH (step:ReasoningStep {step_id: $step_id})
MATCH (fs:FinancialStatement {statement_id: $statement_id})
MERGE (step)-[:TOUCHED {access_type: 'READ', timestamp: datetime($timestamp)}]->(fs)
"""


WRITE_RETRIEVED_CYPHER = """
MATCH (tc:ToolCall {call_id: $call_id})
MATCH (fs:FinancialStatement {statement_id: $statement_id})
MERGE (tc)-[:RETRIEVED]->(fs)
"""


WRITE_DECIDED_ON_CYPHER = """
MATCH (step:ReasoningStep {step_id: $step_id})
MATCH (ca:CreditApplication {application_id: $application_id})
MERGE (step)-[:DECIDED_ON {decision: $decision}]->(ca)
"""


VALID_EVENT_TYPES = frozenset({
    "AGENT_START", "TOOL_CALL_START", "TOOL_CALL_END",
    "MODEL_CALL", "AGENT_END", "SWARM_START", "SWARM_END",
})


# ---------------------------------------------------------------------------
# Functional API (used by ProvenanceHook via config singleton)
# ---------------------------------------------------------------------------

def write_step(event_data: dict) -> None:
    """Write a single provenance step to Neo4j.

    Called synchronously by the ProvenanceHook for each lifecycle event.
    Uses the config singleton for Neo4j connection.
    """
    event_type = event_data.get("event_type", "UNKNOWN")

    logger.info(
        "[PROVENANCE] %s | agent=%s | step=%s | trace=%s",
        event_type,
        event_data.get("agent_name"),
        event_data.get("step_number"),
        event_data.get("trace_id"),
    )

    try:
        driver = _get_driver()

        with driver.session(database=config.neo4j_database) as session:
            params = {
                "trace_id": event_data["trace_id"],
                "session_id": event_data["session_id"],
                "tenant_id": event_data["tenant_id"],
                "step_id": event_data["step_id"],
                "step_number": event_data["step_number"],
                "agent_name": event_data.get("agent_name", "unknown"),
                "event_type": event_type,
                "thought": event_data.get("thought"),
                "action": event_data.get("action"),
                "observation": event_data.get("observation"),
                "cost_usd": event_data.get("cost_usd", 0),
                "latency_ms": event_data.get("latency_ms", 0),
                "model_id": event_data.get("model_id"),
                "token_input": event_data.get("token_input", 0),
                "token_output": event_data.get("token_output", 0),
                "prev_hash": event_data["prev_hash"],
                "step_hash": event_data["step_hash"],
                "status": "COMPLETED" if "END" in event_type else "STARTED",
                "created_at": event_data["created_at"],
                "task": event_data.get("thought", "Credit decision evaluation"),
            }

            session.run(WRITE_STEP_CYPHER, params)

            # Link tenant/session on first step
            if event_type == "AGENT_START" and event_data["step_number"] == 1:
                session.run(LINK_TENANT_SESSION_CYPHER, {
                    "tenant_id": event_data["tenant_id"],
                    "session_id": event_data["session_id"],
                    "trace_id": event_data["trace_id"],
                    "created_at": event_data["created_at"],
                })

            # Write tool call details
            tool_call = event_data.get("tool_call")
            if tool_call and event_type == "TOOL_CALL_END":
                tc_params = {
                    "step_id": event_data["step_id"],
                    "call_id": f"call_{uuid.uuid4().hex[:12]}",
                    "tool_name": tool_call.get("tool_name", "unknown"),
                    "arguments": json.dumps(tool_call.get("arguments", {})),
                    "result": str(tool_call.get("result", ""))[:5000],
                    "result_summary": tool_call.get("result_summary", "")[:500],
                    "status": tool_call.get("status", "UNKNOWN"),
                    "duration_ms": tool_call.get("duration_ms", 0),
                    "cost_usd": tool_call.get("cost_usd", 0),
                    "error_message": tool_call.get("error_message"),
                    "created_at": event_data["created_at"],
                }
                session.run(WRITE_TOOL_CALL_CYPHER, tc_params)

            # Write entity touches if provided
            for entity in event_data.get("touched_entities", []):
                session.run(WRITE_TOUCHED_ENTITY_CYPHER, {
                    "step_id": event_data["step_id"],
                    "entity_id": entity["entity_id"],
                    "access_type": entity.get("access_type", "READ"),
                    "timestamp": event_data["created_at"],
                })

            # Write financial statement touches if provided
            for fin in event_data.get("touched_financials", []):
                session.run(WRITE_TOUCHED_FINANCIAL_CYPHER, {
                    "step_id": event_data["step_id"],
                    "statement_id": fin["statement_id"],
                    "timestamp": event_data["created_at"],
                })

            # Write RETRIEVED edges for tool calls referencing financial data
            if tool_call and event_type == "TOOL_CALL_END":
                for stmt_id in tool_call.get("retrieved_statement_ids", []):
                    session.run(WRITE_RETRIEVED_CYPHER, {
                        "call_id": tc_params["call_id"],
                        "statement_id": stmt_id,
                    })

            # Write decision link if provided
            decision = event_data.get("decision")
            if decision:
                session.run(WRITE_DECIDED_ON_CYPHER, {
                    "step_id": event_data["step_id"],
                    "application_id": decision["application_id"],
                    "decision": decision["decision"],
                })

    except Exception as e:
        logger.error("[PROVENANCE] Failed to write step to Neo4j: %s", e)


def complete_trace(trace_id: str, outcome: str, success: bool) -> None:
    """Mark a trace as completed in Neo4j."""
    now = datetime.now(timezone.utc).isoformat()

    try:
        driver = _get_driver()
        with driver.session(database=config.neo4j_database) as session:
            session.run(COMPLETE_TRACE_CYPHER, {
                "trace_id": trace_id,
                "completed_at": now,
                "outcome": outcome,
                "success": success,
            })
        logger.info("[PROVENANCE] Trace %s marked complete: %s", trace_id, outcome)
    except Exception as e:
        logger.error("[PROVENANCE] Failed to complete trace: %s", e)


# ---------------------------------------------------------------------------
# Class-based API (for direct driver injection)
# ---------------------------------------------------------------------------

class ProvenanceWriter:
    """Writes provenance events directly to Neo4j via bolt.

    Accepts the same event dict shape as the SQS messages in PLAN.md Section 10.2.
    Uses a shared neo4j.Driver instance (connection pool) for all writes.
    """

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def write_provenance_event(self, event: dict[str, Any]) -> str | None:
        """Write a single provenance event to Neo4j.

        Args:
            event: Dict matching the SQS message shape from PLAN.md Section 10.2.
                   Required keys: trace_id, session_id, tenant_id, step_id,
                   step_number, agent_name, event_type, created_at, prev_hash, step_hash.

        Returns:
            The step_id of the written step, or None on failure.
        """
        event_type = event.get("event_type", "UNKNOWN")
        if event_type not in VALID_EVENT_TYPES:
            logger.warning("Unknown event_type %s, writing anyway", event_type)

        try:
            with self._driver.session(database=self._database) as session:
                step_id = self._write_step(session, event)

                # Link tenant -> session -> trace on the first step
                if event_type == "AGENT_START" and event.get("step_number") == 1:
                    self._link_tenant_session(session, event)

                # Write tool call details on TOOL_CALL_END
                tool_call = event.get("tool_call")
                if tool_call and event_type == "TOOL_CALL_END":
                    self._write_tool_call(session, event, tool_call)

                # Write entity touches if provided
                for entity in event.get("touched_entities", []):
                    self._write_touched_entity(session, step_id, entity, event["created_at"])

                # Write financial statement touches if provided
                for fin in event.get("touched_financials", []):
                    self._write_touched_financial(session, step_id, fin, event["created_at"])

                # Write decision link if provided
                decision = event.get("decision")
                if decision:
                    self._write_decided_on(session, step_id, decision)

                return step_id

        except Exception:
            logger.exception("Failed to write provenance event %s", event.get("step_id"))
            return None

    def complete_trace(
        self,
        trace_id: str,
        outcome: str,
        success: bool,
        completed_at: str | None = None,
    ) -> str | None:
        """Mark a trace as completed with final outcome."""
        if completed_at is None:
            completed_at = datetime.now(timezone.utc).isoformat()

        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(COMPLETE_TRACE_CYPHER, {
                    "trace_id": trace_id,
                    "completed_at": completed_at,
                    "outcome": outcome,
                    "success": success,
                })
                record = result.single()
                return record["trace_id"] if record else None
        except Exception:
            logger.exception("Failed to complete trace %s", trace_id)
            return None

    # --- Internal helpers ---

    def _write_step(self, session, event: dict[str, Any]) -> str:
        """Write a ReasoningStep node and link to its trace."""
        event_type = event.get("event_type", "UNKNOWN")
        params = {
            "trace_id": event["trace_id"],
            "session_id": event["session_id"],
            "tenant_id": event["tenant_id"],
            "step_id": event["step_id"],
            "step_number": event["step_number"],
            "agent_name": event.get("agent_name", "unknown"),
            "event_type": event_type,
            "thought": event.get("thought"),
            "action": event.get("action"),
            "observation": event.get("observation"),
            "cost_usd": event.get("cost_usd", 0),
            "latency_ms": event.get("latency_ms", 0),
            "model_id": event.get("model_id"),
            "token_input": event.get("token_input", 0),
            "token_output": event.get("token_output", 0),
            "prev_hash": event["prev_hash"],
            "step_hash": event["step_hash"],
            "status": "COMPLETED" if "END" in event_type else "STARTED",
            "created_at": event["created_at"],
            "task": event.get("thought", "Credit decision evaluation"),
        }
        result = session.run(WRITE_STEP_CYPHER, params)
        record = result.single()
        return record["step_id"] if record else event["step_id"]

    def _link_tenant_session(self, session, event: dict[str, Any]) -> None:
        """Create Tenant -> Session -> Trace chain."""
        session.run(LINK_TENANT_SESSION_CYPHER, {
            "tenant_id": event["tenant_id"],
            "session_id": event["session_id"],
            "trace_id": event["trace_id"],
            "created_at": event["created_at"],
        })

    def _write_tool_call(
        self, session, event: dict[str, Any], tool_call: dict[str, Any]
    ) -> str:
        """Write a ToolCall node and link to its ReasoningStep."""
        call_id = f"call_{uuid.uuid4().hex[:12]}"
        params = {
            "step_id": event["step_id"],
            "call_id": call_id,
            "tool_name": tool_call.get("tool_name", "unknown"),
            "arguments": json.dumps(tool_call.get("arguments", {})),
            "result": str(tool_call.get("result", ""))[:5000],
            "result_summary": tool_call.get("result_summary", "")[:500],
            "status": tool_call.get("status", "UNKNOWN"),
            "duration_ms": tool_call.get("duration_ms", 0),
            "cost_usd": tool_call.get("cost_usd", 0),
            "error_message": tool_call.get("error_message"),
            "created_at": event["created_at"],
        }
        result = session.run(WRITE_TOOL_CALL_CYPHER, params)
        record = result.single()

        # Write RETRIEVED edges if tool call references financial statements
        for stmt_id in tool_call.get("retrieved_statement_ids", []):
            session.run(WRITE_RETRIEVED_CYPHER, {
                "call_id": call_id,
                "statement_id": stmt_id,
            })

        return record["call_id"] if record else call_id

    def _write_touched_entity(
        self, session, step_id: str, entity: dict[str, Any], timestamp: str
    ) -> None:
        """Write a TOUCHED edge between a step and an entity."""
        session.run(WRITE_TOUCHED_ENTITY_CYPHER, {
            "step_id": step_id,
            "entity_id": entity["entity_id"],
            "access_type": entity.get("access_type", "READ"),
            "timestamp": timestamp,
        })

    def _write_touched_financial(
        self, session, step_id: str, fin: dict[str, Any], timestamp: str
    ) -> None:
        """Write a TOUCHED edge between a step and a financial statement."""
        session.run(WRITE_TOUCHED_FINANCIAL_CYPHER, {
            "step_id": step_id,
            "statement_id": fin["statement_id"],
            "timestamp": timestamp,
        })

    def _write_decided_on(
        self, session, step_id: str, decision: dict[str, Any]
    ) -> None:
        """Write a DECIDED_ON edge between a step and a credit application."""
        session.run(WRITE_DECIDED_ON_CYPHER, {
            "step_id": step_id,
            "application_id": decision["application_id"],
            "decision": decision["decision"],
        })
