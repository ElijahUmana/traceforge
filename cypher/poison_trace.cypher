// POISON TRACE QUERY: Find poisoned data points in the provenance chain
// Input: $trace_id
// Returns: the exact tool call that returned inflated/poisoned financial data

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
       step.step_hash AS cryptographic_proof;
