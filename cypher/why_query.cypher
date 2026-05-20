// WHY QUERY: Reconstruct the full provenance chain for a decision
// Input: $trace_id
// Returns: trace metadata + ordered provenance chain with tools and touched entities

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
  }) AS provenance_chain;
