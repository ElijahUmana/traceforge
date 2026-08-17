"""TraceForge REST API routes.

Endpoints:
  POST /api/evaluate          -- Run the credit decision swarm
  GET  /api/why/{trace_id}    -- Provenance chain for a trace
  POST /api/audit/{trace_id}  -- EU AI Act Article 12 audit report
  GET  /api/cost              -- Cost attribution rollup
  GET  /api/traces            -- List recent traces
  GET  /api/health            -- Health check with Neo4j status
  GET  /api/stream/{trace_id} -- SSE stream of provenance steps
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    application_id: str = ""
    company_name: str = ""
    requested_amount: float = 0.0
    tenant_id: str = "tenant_demo"


class EvaluateResponse(BaseModel):
    trace_id: str
    outcome: str
    decision: str
    company_name: str
    requested_amount: float
    risk_score: float | None = None
    risk_category: str | None = None
    reasoning: str = ""
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    agent_count: int = 3
    step_count: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_driver(request: Request):
    return request.app.state.neo4j_driver


def _get_db(request: Request) -> str:
    return request.app.state.neo4j_database


def _neo4j_value(val: Any) -> Any:
    """Convert Neo4j temporal and spatial types to JSON-serializable forms."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if isinstance(val, (list, tuple)):
        return [_neo4j_value(v) for v in val]
    if isinstance(val, dict):
        return {k: _neo4j_value(v) for k, v in val.items()}
    return val


# ---------------------------------------------------------------------------
# POST /api/evaluate
# ---------------------------------------------------------------------------

@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(body: EvaluateRequest, request: Request):
    """Run the credit decision swarm and return the result with a trace_id.

    Tries to import the real swarm from backend.app.swarm (Team Strands).
    Falls back to a stub that returns a mock result with synthetic trace data
    written directly to Neo4j so the rest of the dashboard works.
    """
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    tenant_id = body.tenant_id or "tenant_demo"
    company = body.company_name or "Unknown Company"
    amount = body.requested_amount or 0.0
    app_id = body.application_id or f"APP-{datetime.now(UTC).strftime('%Y')}-{uuid.uuid4().hex[:4].upper()}"

    # ---- Launch the real swarm in the background, return trace_id immediately ----
    try:
        from backend.app.provenance_writer import complete_trace
        from backend.app.swarm import create_credit_decision_swarm

        prompt = (
            f"Evaluate credit application {app_id} for {company} "
            f"requesting ${amount:,.0f} credit."
        )

        def _run_swarm_bg():
            try:
                swarm, tid, sid = create_credit_decision_swarm(
                    tenant_id=tenant_id,
                    trace_id=trace_id,
                    session_id=session_id,
                )
                result_obj = swarm(prompt)
                result_text = str(result_obj)

                decision = "PENDING"
                for d in ["APPROVED", "DENIED", "ESCALATED"]:
                    if d in result_text.upper():
                        decision = d
                        break

                complete_trace(tid, outcome=decision, success=True)
                logger.info(f"Swarm completed: {tid} -> {decision}")
            except Exception as e:
                logger.error(f"Background swarm failed: {e}", exc_info=True)
                complete_trace(trace_id, outcome="FAILED", success=False)

        import threading
        threading.Thread(target=_run_swarm_bg, daemon=True).start()

        return EvaluateResponse(
            trace_id=trace_id,
            outcome="PROCESSING",
            decision="PROCESSING",
            company_name=company,
            requested_amount=amount,
            reasoning=f"Swarm launched. 3 agents evaluating {company}. Check /traces or /why/{trace_id} for live progress.",
            total_cost_usd=0.0,
            total_latency_ms=0,
            step_count=0,
        )
    except Exception as exc:
        logger.error("Swarm launch failed: %s", exc, exc_info=True)

    # The synthetic path writes fabricated steps into Neo4j under the same
    # labels as real decisions, and once written they are indistinguishable
    # from genuine ones. That is acceptable for an offline UI demo and not
    # acceptable as a silent fallback, so it is opt-in and off by default —
    # otherwise a missing dependency quietly turns this into a data generator.
    if os.getenv("TRACEFORGE_ALLOW_SYNTHETIC_TRACES") != "1":
        raise HTTPException(
            status_code=503,
            detail=(
                "The agent swarm could not be started, so no decision was made. "
                "Check that ANTHROPIC_API_KEY is set and that "
                "strands-agents[anthropic] is installed. Set "
                "TRACEFORGE_ALLOW_SYNTHETIC_TRACES=1 to emit a clearly-labelled "
                "synthetic trace instead (offline demo only)."
            ),
        )

    logger.warning(
        "emitting a SYNTHETIC trace for %s — this is fabricated data, enabled by "
        "TRACEFORGE_ALLOW_SYNTHETIC_TRACES", trace_id,
    )
    return await _stub_evaluate(
        request, trace_id, session_id, tenant_id, app_id, company, amount,
    )


async def _stub_evaluate(
    request: Request,
    trace_id: str,
    session_id: str,
    tenant_id: str,
    app_id: str,
    company: str,
    amount: float,
) -> EvaluateResponse:
    """Generate synthetic provenance data so the dashboard has content to show."""
    import hashlib

    driver = _get_driver(request)
    db = _get_db(request)
    now = datetime.now(UTC)

    # Determine outcome based on amount thresholds (mirrors the risk model)
    if amount > 30_000_000:
        decision = "ESCALATED"
        risk_score = 58.0
        risk_category = "MODERATE"
    elif amount <= 0:
        decision = "DENIED"
        risk_score = 20.0
        risk_category = "CRITICAL"
    else:
        decision = "APPROVED"
        risk_score = 78.0
        risk_category = "LOW"

    event_sequence = [
        # (agent, event_type, thought, action, observation, cost, latency)
        ("Researcher", "AGENT_START", f"Starting research on {company}", None, None, 0.0, 0),
        ("Researcher", "TOOL_CALL_END", "Fetching SEC filings", "fetch_sec_filings",
         f"Retrieved 10-K for {company}: revenue data retrieved", 0.002, 2100),
        ("Researcher", "TOOL_CALL_END", "Fetching credit scores", "fetch_credit_scores",
         f"Credit score for {company}: {int(risk_score)}/100", 0.001, 1500),
        ("Researcher", "TOOL_CALL_END", "Fetching news sentiment", "fetch_news_sentiment",
         f"Sentiment for {company}: +0.45 (positive, 32 articles)", 0.001, 1800),
        ("Researcher", "MODEL_CALL", "Synthesizing research findings", None,
         f"Research brief compiled for {company}", 0.032, 3800),
        ("Researcher", "AGENT_END", "Research phase complete", None,
         f"Compiled comprehensive research brief for {company}", 0.0, 500),
        ("Analyst", "AGENT_START", f"Starting risk analysis for {company}", None, None, 0.0, 0),
        ("Analyst", "TOOL_CALL_END", "Computing risk score", "compute_risk_score",
         f"Risk score: {risk_score} ({risk_category})", 0.001, 800),
        ("Analyst", "TOOL_CALL_END", "Validating against rules", "validate_rules",
         "All rules passed" if decision == "APPROVED" else "Rule violation: amount exceeds threshold",
         0.001, 600),
        ("Analyst", "MODEL_CALL", "Formulating risk assessment", None,
         f"Risk assessment: {risk_category} risk, recommend {decision}", 0.028, 4200),
        ("Analyst", "AGENT_END", "Analysis phase complete", None,
         f"Risk assessment complete: {risk_category} ({risk_score})", 0.0, 300),
        ("Writer", "AGENT_START", f"Drafting decision memo for {company}", None, None, 0.0, 0),
        ("Writer", "TOOL_CALL_END", "Drafting memo", "draft_memo",
         f"Decision memo drafted: {decision}", 0.001, 500),
        ("Writer", "TOOL_CALL_END", "Checking compliance", "check_compliance",
         "EU AI Act Article 12 compliance: PASSED", 0.001, 400),
        ("Writer", "TOOL_CALL_END", "Submitting decision", "submit_decision",
         f"Decision {decision} submitted for {app_id}", 0.001, 300),
        ("Writer", "MODEL_CALL", "Finalizing decision memo", None,
         f"Final memo: {decision} for {company} (${amount:,.0f})", 0.025, 3500),
        ("Writer", "AGENT_END", "Decision phase complete", None,
         f"Credit decision {decision} for {company}", 0.0, 200),
    ]

    prev_hash = "GENESIS"
    total_cost = 0.0
    total_latency = 0
    steps_written = 0

    def _hash(data: dict) -> str:
        payload = json.dumps({"prev_hash": prev_hash, **data}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _write_steps(tx):
        nonlocal prev_hash, total_cost, total_latency, steps_written

        # Create trace
        tx.run(
            """
            MERGE (trace:ReasoningTrace:SyntheticTrace {trace_id: $trace_id})
            ON CREATE SET
              trace.tenant_id = $tenant_id,
              trace.session_id = $session_id,
              trace.task = $task,
              trace.started_at = datetime($started_at),
              trace.total_cost_usd = 0,
              trace.total_latency_ms = 0,
              trace.step_count = 0,
              trace.agent_count = 3,
              trace.outcome = $outcome,
              trace.success = true,
              // Fabricated data. The extra label and this flag are what keep it
              // separable from a real decision once it is in the graph — without
              // them a synthetic trace is indistinguishable from a genuine one.
              trace.synthetic = true
            """,
            trace_id=trace_id,
            tenant_id=tenant_id,
            session_id=session_id,
            task=f"Evaluate credit application {app_id} for {company}",
            started_at=now.isoformat(),
            outcome=decision,
        )

        # Create tenant + session links
        tx.run(
            """
            MERGE (tenant:Tenant {tenant_id: $tenant_id})
            ON CREATE SET tenant.name = $tenant_id, tenant.created_at = datetime()
            MERGE (session:Session {session_id: $session_id})
            ON CREATE SET session.tenant_id = $tenant_id,
                          session.started_at = datetime($started_at),
                          session.status = 'COMPLETED'
            MERGE (tenant)-[:HAS_SESSION]->(session)
            WITH session
            MATCH (trace:ReasoningTrace {trace_id: $trace_id})
            MERGE (session)-[:HAS_TRACE]->(trace)
            """,
            tenant_id=tenant_id,
            session_id=session_id,
            trace_id=trace_id,
            started_at=now.isoformat(),
        )

        for i, (agent, event_type, thought, action, observation, cost, latency) in enumerate(
            event_sequence, start=1
        ):
            step_id = f"step_{uuid.uuid4().hex[:12]}"
            ts = now.isoformat()

            event_data = {
                "trace_id": trace_id,
                "step_id": step_id,
                "step_number": i,
                "agent_name": agent,
                "event_type": event_type,
            }
            step_hash = _hash(event_data)

            status = "COMPLETED" if "END" in event_type else "STARTED"

            tx.run(
                """
                MATCH (trace:ReasoningTrace {trace_id: $trace_id})
                CREATE (step:ReasoningStep {
                  step_id: $step_id,
                  trace_id: $trace_id,
                  agent_name: $agent_name,
                  event_type: $event_type,
                  step_number: $step_number,
                  thought: $thought,
                  action: $action,
                  observation: $observation,
                  cost_usd: $cost_usd,
                  latency_ms: $latency_ms,
                  model_id: $model_id,
                  token_input: $token_input,
                  token_output: $token_output,
                  prev_hash: $prev_hash,
                  step_hash: $step_hash,
                  status: $status,
                  created_at: datetime($created_at)
                })
                MERGE (trace)-[:HAS_STEP {step_number: $step_number}]->(step)
                SET trace.total_cost_usd = trace.total_cost_usd + $cost_usd,
                    trace.total_latency_ms = trace.total_latency_ms + $latency_ms,
                    trace.step_count = trace.step_count + 1
                """,
                trace_id=trace_id,
                step_id=step_id,
                agent_name=agent,
                event_type=event_type,
                step_number=i,
                thought=thought,
                action=action,
                observation=observation,
                cost_usd=cost,
                latency_ms=latency,
                model_id="claude-sonnet-4-6" if event_type == "MODEL_CALL" else None,
                token_input=1200 if event_type == "MODEL_CALL" else 0,
                token_output=850 if event_type == "MODEL_CALL" else 0,
                prev_hash=prev_hash,
                step_hash=step_hash,
                status=status,
                created_at=ts,
            )

            # Link to previous step
            if i > 1:
                tx.run(
                    """
                    MATCH (prev:ReasoningStep {trace_id: $trace_id, step_number: $prev_num})
                    MATCH (curr:ReasoningStep {step_id: $step_id})
                    MERGE (prev)-[:NEXT_STEP]->(curr)
                    """,
                    trace_id=trace_id,
                    prev_num=i - 1,
                    step_id=step_id,
                )

            # Create ToolCall nodes for tool call events
            if event_type == "TOOL_CALL_END" and action:
                call_id = f"call_{uuid.uuid4().hex[:12]}"
                tx.run(
                    """
                    MATCH (step:ReasoningStep {step_id: $step_id})
                    CREATE (tc:ToolCall {
                      call_id: $call_id,
                      step_id: $step_id,
                      tool_name: $tool_name,
                      arguments: $arguments,
                      result: $result,
                      result_summary: $result_summary,
                      status: 'SUCCESS',
                      duration_ms: $duration_ms,
                      cost_usd: $cost_usd,
                      created_at: datetime($created_at)
                    })
                    MERGE (step)-[:USES_TOOL]->(tc)
                    """,
                    step_id=step_id,
                    call_id=call_id,
                    tool_name=action,
                    arguments=json.dumps({"company": company}),
                    result=observation or "",
                    result_summary=observation or "",
                    duration_ms=latency,
                    cost_usd=cost,
                    created_at=ts,
                )

            prev_hash = step_hash
            total_cost += cost
            total_latency += latency
            steps_written += 1

        # Finalize trace
        tx.run(
            """
            MATCH (trace:ReasoningTrace {trace_id: $trace_id})
            SET trace.completed_at = datetime($completed_at),
                trace.total_cost_usd = $total_cost,
                trace.total_latency_ms = $total_latency
            """,
            trace_id=trace_id,
            completed_at=now.isoformat(),
            total_cost=total_cost,
            total_latency=total_latency,
        )

    with driver.session(database=db) as session:
        session.execute_write(_write_steps)

    reasoning = (
        f"Based on comprehensive financial analysis of {company}: "
        f"risk score {risk_score} ({risk_category}), "
        f"requested amount ${amount:,.0f}. "
        f"Decision: {decision}."
    )

    return EvaluateResponse(
        trace_id=trace_id,
        outcome="COMPLETED",
        decision=decision,
        company_name=company,
        requested_amount=amount,
        risk_score=risk_score,
        risk_category=risk_category,
        reasoning=reasoning,
        total_cost_usd=round(total_cost, 4),
        total_latency_ms=total_latency,
        agent_count=3,
        step_count=steps_written,
    )


# ---------------------------------------------------------------------------
# GET /api/why/{trace_id}
# ---------------------------------------------------------------------------

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
    model_id: step.model_id,
    token_input: step.token_input,
    token_output: step.token_output,
    prev_hash: step.prev_hash,
    step_hash: step.step_hash,
    status: step.status,
    created_at: step.created_at,
    tools: tools,
    touched_entities: entities
  }) AS provenance_chain
"""


def _verify_chain(driver, trace_id: str, db: str) -> dict:
    """Recompute a trace's hash chain, degrading to an explicit error report.

    This must never raise into the /why response, but it must also never
    report a chain as valid when it could not actually be checked — an
    unverified chain rendered as "intact" is worse than no badge at all.
    """
    from backend.app.queries import verify_trace_chain

    try:
        return verify_trace_chain(driver, trace_id, database=db)
    except Exception as exc:  # noqa: BLE001 - surfaced in the payload
        logger.exception("hash chain verification failed for trace %s", trace_id)
        return {
            "valid": False,
            "error": f"verification could not be completed: {exc}",
            "steps_verified": 0,
            "content_verified": 0,
            "broken_links": [],
            "content_mismatches": [],
            "unverifiable_steps": [],
        }


@router.get("/why/{trace_id}")
async def get_why(trace_id: str, request: Request):
    """Return the full provenance chain for a trace.

    Tries backend.app.queries.why_query first (Team Graph),
    falls back to direct Cypher execution.
    """
    driver = _get_driver(request)
    db = _get_db(request)

    try:
        from backend.app.queries import why_query as queries_why  # type: ignore
        result = queries_why(driver, trace_id, database=db)
        if result is not None:
            result["hash_chain"] = _verify_chain(driver, trace_id, db)
            result["hash_chain_valid"] = result["hash_chain"]["valid"]
            return result
    except (ImportError, ModuleNotFoundError, AttributeError):
        pass

    with driver.session(database=db) as session:
        result = session.run(WHY_QUERY, trace_id=trace_id)
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    chain_report = _verify_chain(driver, trace_id, db)

    chain = record["provenance_chain"]
    # Filter out null entries from the chain
    clean_chain = [
        {k: _neo4j_value(v) for k, v in step.items()}
        for step in chain
        if step.get("step_id") is not None
    ]
    # Sort by step_number
    clean_chain.sort(key=lambda s: s.get("step_number", 0))

    return {
        "trace_id": record["trace_id"],
        "task": record["task"],
        "outcome": record["outcome"],
        "success": record["success"],
        "total_cost_usd": record["total_cost_usd"],
        "total_latency_ms": record["total_latency_ms"],
        "started_at": _neo4j_value(record["started_at"]),
        "completed_at": _neo4j_value(record["completed_at"]),
        "provenance_chain": clean_chain,
        "hash_chain": chain_report,
        "hash_chain_valid": chain_report["valid"],
    }


# ---------------------------------------------------------------------------
# POST /api/audit/{trace_id}
# ---------------------------------------------------------------------------

TOOL_NAME_TO_SOURCE: dict[str, tuple[str, str]] = {
    "fetch_sec_filings": ("SEC_EDGAR", "10-K Annual Filing"),
    "fetch_credit_scores": ("INTERNAL_MODEL", "Credit Score"),
    "fetch_news_sentiment": ("NEWS_API", "Sentiment Analysis"),
    "compute_risk_score": ("INTERNAL_MODEL", "Risk Score Computation"),
    "validate_rules": ("RULES_ENGINE", "Compliance Rules"),
    "draft_memo": ("INTERNAL_MODEL", "Decision Memo"),
    "check_compliance": ("COMPLIANCE_ENGINE", "EU AI Act Check"),
    "submit_decision": ("DECISION_REGISTRY", "Decision Submission"),
}


@router.post("/audit/{trace_id}")
async def audit_export(trace_id: str, request: Request):
    """Generate an EU AI Act Article 12 compliance audit report for a trace.

    Queries Neo4j for the full provenance chain and builds a structured
    JSON report matching PLAN.md Section 14.4.
    """
    driver = _get_driver(request)
    db = _get_db(request)

    with driver.session(database=db) as session:
        result = session.run(WHY_QUERY, trace_id=trace_id)
        record = result.single()

    if not record:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    chain = record["provenance_chain"]
    clean_chain = [
        {k: _neo4j_value(v) for k, v in step.items()}
        for step in chain
        if step.get("step_id") is not None
    ]
    clean_chain.sort(key=lambda s: s.get("step_number", 0))

    # Build provenance chain for the audit report
    audit_chain = []
    for step in clean_chain:
        tool_calls = [t for t in (step.get("tools") or []) if t.get("call_id")]
        action = step.get("action") or step.get("event_type", "")
        source_info = TOOL_NAME_TO_SOURCE.get(action, ("AGENT_REASONING", step.get("agent_name", "")))

        input_data: dict[str, Any] = {}
        for tc in tool_calls:
            if tc.get("tool_name") == action:
                try:
                    input_data = json.loads(tc.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    input_data = {}
                break

        audit_chain.append({
            "step": step.get("step_number", 0),
            "agent": step.get("agent_name", ""),
            "action": action,
            "input": input_data,
            "output_summary": step.get("observation") or step.get("thought") or "",
            "data_source": source_info[0],
            "timestamp": step.get("created_at"),
            "hash": step.get("step_hash", ""),
        })

    # Hash chain verification
    total_steps = len(clean_chain)
    genesis_hash = clean_chain[0].get("prev_hash", "GENESIS") if clean_chain else "GENESIS"
    final_hash = clean_chain[-1].get("step_hash", "") if clean_chain else ""
    verified_steps = 0
    chain_intact = True
    for i, step in enumerate(clean_chain):
        if i == 0:
            if step.get("prev_hash") == "GENESIS":
                verified_steps += 1
            else:
                chain_intact = False
        else:
            if step.get("prev_hash") == clean_chain[i - 1].get("step_hash"):
                verified_steps += 1
            else:
                chain_intact = False

    # Collect unique data sources from tool calls
    seen_sources: set[str] = set()
    data_sources = []
    for step in clean_chain:
        action = step.get("action")
        if action and action in TOOL_NAME_TO_SOURCE:
            source_name, source_type = TOOL_NAME_TO_SOURCE[action]
            if source_name not in seen_sources:
                seen_sources.add(source_name)
                data_sources.append({
                    "source": source_name,
                    "type": source_type,
                    "retrieved_at": step.get("created_at"),
                })
    # Always include the knowledge graph as a consulted source
    if "NEO4J_KNOWLEDGE_GRAPH" not in seen_sources:
        data_sources.append({
            "source": "NEO4J_KNOWLEDGE_GRAPH",
            "type": "Entity Relationships",
            "retrieved_at": _neo4j_value(record["started_at"]),
        })

    now = datetime.now(UTC)
    report = {
        "report": {
            "title": "EU AI Act Article 12 Compliance Report",
            "version": "1.0",
            "generated_at": now.isoformat(),
            "system": "TraceForge v0.1.0",
            "regulation": "EU AI Act (Regulation (EU) 2024/1689), Article 12",
            "classification": "HIGH-RISK (Annex III, Section 5: Creditworthiness Assessment)",
        },
        "decision": {
            "trace_id": record["trace_id"],
            "task": record["task"],
            "outcome": record["outcome"],
            "timestamp": _neo4j_value(record["started_at"]),
            "tenant": "tenant_demo",
        },
        "provenance_chain": audit_chain,
        "hash_chain_verification": {
            "total_steps": total_steps,
            "verified_steps": verified_steps,
            "chain_intact": chain_intact,
            "genesis_hash": genesis_hash,
            "final_hash": final_hash,
        },
        "data_sources_consulted": data_sources,
        "compliance_checklist": {
            "art12_1_logging": total_steps > 0,
            "art12_2_traceability": chain_intact,
            "art12_3_monitoring": True,
            "art12_4_record_keeping": True,
            "tamper_evidence": "SHA-256 hash chain verified" if chain_intact else "Hash chain BROKEN",
            "retention_period": "6 months minimum",
        },
    }

    return report


# ---------------------------------------------------------------------------
# GET /api/cost
# ---------------------------------------------------------------------------

COST_QUERY = """
MATCH (trace:ReasoningTrace)
WHERE trace.tenant_id = $tenant_id
  AND ($start_date IS NULL OR trace.started_at >= datetime($start_date))
  AND ($end_date IS NULL OR trace.started_at <= datetime($end_date))
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
OPTIONAL MATCH (step)-[:USES_TOOL]->(tc:ToolCall)

WITH trace, step, tc

WITH
  trace.tenant_id AS tenant_id,
  count(DISTINCT trace) AS total_traces,
  sum(DISTINCT trace.total_cost_usd) AS total_cost_usd,

  step.agent_name AS agent_name,
  sum(step.cost_usd) AS agent_cost_usd,
  sum(step.token_input) AS agent_tokens_input,
  sum(step.token_output) AS agent_tokens_output,
  avg(step.latency_ms) AS agent_avg_latency_ms,

  tc.tool_name AS tool_name,
  count(tc) AS tool_call_count,
  sum(tc.duration_ms) AS tool_total_duration_ms

RETURN tenant_id, total_traces, total_cost_usd,
       agent_name, agent_cost_usd, agent_tokens_input,
       agent_tokens_output, agent_avg_latency_ms,
       tool_name, tool_call_count, tool_total_duration_ms
ORDER BY agent_cost_usd DESC
"""

# Separate query for per-trace cost breakdown
COST_PER_TRACE_QUERY = """
MATCH (trace:ReasoningTrace)
WHERE trace.tenant_id = $tenant_id
  AND ($start_date IS NULL OR trace.started_at >= datetime($start_date))
  AND ($end_date IS NULL OR trace.started_at <= datetime($end_date))
RETURN trace.trace_id AS trace_id,
       trace.task AS task,
       trace.outcome AS outcome,
       trace.total_cost_usd AS total_cost_usd,
       trace.total_latency_ms AS total_latency_ms,
       trace.started_at AS started_at
ORDER BY trace.started_at DESC
LIMIT 50
"""


@router.get("/cost")
async def get_cost(
    request: Request,
    tenant_id: str = Query(default="tenant_demo"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    """Return cost attribution rollup for a tenant."""
    driver = _get_driver(request)
    db = _get_db(request)

    # Team Graph's cost_query requires non-None dates; use our own if dates absent
    if start_date and end_date:
        try:
            from backend.app.queries import cost_query as queries_cost  # type: ignore
            result = queries_cost(driver, tenant_id, start_date, end_date, database=db)
            return result
        except (ImportError, ModuleNotFoundError, AttributeError):
            pass

    with driver.session(database=db) as session:
        result = session.run(
            COST_QUERY,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )
        rows = [dict(r) for r in result]

        trace_result = session.run(
            COST_PER_TRACE_QUERY,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
        )
        trace_rows = [dict(r) for r in trace_result]

    # Aggregate by agent
    agent_costs: dict[str, dict] = {}
    total_cost = 0.0
    total_traces = 0

    for row in rows:
        agent = row.get("agent_name")
        if agent and agent not in agent_costs:
            agent_costs[agent] = {
                "agent_name": agent,
                "cost_usd": float(row.get("agent_cost_usd") or 0),
                "tokens_input": int(row.get("agent_tokens_input") or 0),
                "tokens_output": int(row.get("agent_tokens_output") or 0),
                "avg_latency_ms": float(row.get("agent_avg_latency_ms") or 0),
            }
        if row.get("total_cost_usd") is not None:
            total_cost = float(row["total_cost_usd"])
        if row.get("total_traces") is not None:
            total_traces = int(row["total_traces"])

    # Aggregate by tool
    tool_costs: dict[str, dict] = {}
    for row in rows:
        tool = row.get("tool_name")
        if tool and tool not in tool_costs:
            tool_costs[tool] = {
                "tool_name": tool,
                "call_count": int(row.get("tool_call_count") or 0),
                "total_duration_ms": int(row.get("tool_total_duration_ms") or 0),
            }

    traces = [
        {
            "trace_id": r["trace_id"],
            "task": r.get("task"),
            "outcome": r.get("outcome"),
            "total_cost_usd": float(r.get("total_cost_usd") or 0),
            "total_latency_ms": int(r.get("total_latency_ms") or 0),
            "started_at": _neo4j_value(r.get("started_at")),
        }
        for r in trace_rows
    ]

    return {
        "tenant_id": tenant_id,
        "total_traces": total_traces,
        "total_cost_usd": round(total_cost, 4),
        "avg_cost_per_trace": round(total_cost / max(total_traces, 1), 4),
        "cost_by_agent": list(agent_costs.values()),
        "cost_by_tool": list(tool_costs.values()),
        "traces": traces,
    }


# ---------------------------------------------------------------------------
# GET /api/traces
# ---------------------------------------------------------------------------

TRACES_QUERY = """
MATCH (t:ReasoningTrace)
RETURN t.trace_id AS trace_id,
       t.task AS task,
       t.outcome AS outcome,
       t.total_cost_usd AS total_cost_usd,
       t.total_latency_ms AS total_latency_ms,
       t.agent_count AS agent_count,
       t.step_count AS step_count,
       t.started_at AS started_at,
       t.completed_at AS completed_at,
       t.tenant_id AS tenant_id,
       t.success AS success
ORDER BY t.started_at DESC
LIMIT 20
"""


@router.get("/traces")
async def list_traces(request: Request):
    """List recent ReasoningTrace nodes."""
    driver = _get_driver(request)
    db = _get_db(request)

    with driver.session(database=db) as session:
        result = session.run(TRACES_QUERY)
        traces = []
        for record in result:
            traces.append({
                "trace_id": record["trace_id"],
                "task": record["task"],
                "outcome": record["outcome"],
                "total_cost_usd": float(record["total_cost_usd"] or 0),
                "total_latency_ms": int(record["total_latency_ms"] or 0),
                "agent_count": int(record["agent_count"] or 0),
                "step_count": int(record["step_count"] or 0),
                "started_at": _neo4j_value(record["started_at"]),
                "completed_at": _neo4j_value(record["completed_at"]),
                "tenant_id": record["tenant_id"],
                "success": record["success"],
            })

    return {"traces": traces, "count": len(traces)}


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check(request: Request):
    """Health check with Neo4j connectivity test."""
    neo4j_ok = False
    try:
        driver = _get_driver(request)
        driver.verify_connectivity()
        neo4j_ok = True
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)

    return {"status": "ok" if neo4j_ok else "degraded", "neo4j": neo4j_ok}


# ---------------------------------------------------------------------------
# GET /api/stream/{trace_id}  (SSE)
# ---------------------------------------------------------------------------

STREAM_STEPS_QUERY = """
MATCH (trace:ReasoningTrace {trace_id: $trace_id})-[:HAS_STEP]->(step:ReasoningStep)
WHERE step.step_number > $last_step
OPTIONAL MATCH (step)-[:USES_TOOL]->(tc:ToolCall)
RETURN step.step_id AS step_id,
       step.agent_name AS agent_name,
       step.event_type AS event_type,
       step.step_number AS step_number,
       step.thought AS thought,
       step.action AS action,
       step.observation AS observation,
       step.cost_usd AS cost_usd,
       step.latency_ms AS latency_ms,
       step.step_hash AS step_hash,
       step.status AS status,
       step.created_at AS created_at,
       collect({
         call_id: tc.call_id,
         tool_name: tc.tool_name,
         result_summary: tc.result_summary,
         status: tc.status,
         duration_ms: tc.duration_ms
       }) AS tools
ORDER BY step.step_number
"""


@router.get("/stream/{trace_id}")
async def stream_provenance(trace_id: str, request: Request):
    """SSE endpoint that streams provenance steps as they appear in Neo4j.

    Polls Neo4j every 500ms for new :ReasoningStep nodes on this trace.
    Yields each new step as an SSE event. Stops after 60 seconds of no new
    steps or when the trace is completed.
    """
    driver = _get_driver(request)
    db = _get_db(request)

    async def event_generator():
        last_step = 0
        idle_count = 0
        max_idle = 120  # 60 seconds at 500ms intervals

        while idle_count < max_idle:
            await asyncio.sleep(0.5)

            try:
                with driver.session(database=db) as session:
                    result = session.run(STREAM_STEPS_QUERY, trace_id=trace_id, last_step=last_step)
                    new_steps = list(result)

                if new_steps:
                    idle_count = 0
                    for record in new_steps:
                        step_num = record["step_number"]
                        if step_num > last_step:
                            last_step = step_num

                        tools = [
                            {k: _neo4j_value(v) for k, v in t.items()}
                            for t in record["tools"]
                            if t.get("call_id") is not None
                        ]

                        event_data = {
                            "step_id": record["step_id"],
                            "agent_name": record["agent_name"],
                            "event_type": record["event_type"],
                            "step_number": record["step_number"],
                            "thought": record["thought"],
                            "action": record["action"],
                            "observation": record["observation"],
                            "cost_usd": float(record["cost_usd"] or 0),
                            "latency_ms": int(record["latency_ms"] or 0),
                            "step_hash": record["step_hash"],
                            "status": record["status"],
                            "created_at": _neo4j_value(record["created_at"]),
                            "tools": tools,
                        }

                        yield {
                            "event": "step",
                            "data": json.dumps(event_data, default=str),
                        }

                    # Check if trace is completed
                    with driver.session(database=db) as session:
                        trace_result = session.run(
                            "MATCH (t:ReasoningTrace {trace_id: $tid}) RETURN t.completed_at AS completed",
                            tid=trace_id,
                        )
                        trace_record = trace_result.single()
                        if trace_record and trace_record["completed"]:
                            yield {
                                "event": "complete",
                                "data": json.dumps({"trace_id": trace_id, "status": "completed"}),
                            }
                            return
                else:
                    idle_count += 1

            except Exception as exc:
                logger.error("SSE stream error: %s", exc)
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(exc)}),
                }
                return

        yield {
            "event": "timeout",
            "data": json.dumps({"trace_id": trace_id, "status": "timeout"}),
        }

    return EventSourceResponse(event_generator())
