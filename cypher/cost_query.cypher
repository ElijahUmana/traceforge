// COST QUERY: Roll up costs by tenant, agent, tool, and time period
// Input: $tenant_id, $start_date, $end_date

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
  step.agent_name AS agent_name,
  sum(step.cost_usd) AS agent_cost_usd,
  sum(step.token_input) AS agent_tokens_input,
  sum(step.token_output) AS agent_tokens_output,
  avg(step.latency_ms) AS agent_avg_latency_ms,
  tc.tool_name AS tool_name,
  count(tc) AS tool_call_count,
  sum(tc.duration_ms) AS tool_total_duration_ms
ORDER BY agent_cost_usd DESC;
