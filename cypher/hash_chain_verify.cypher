// HASH CHAIN VERIFICATION: Check tamper-evidence of provenance chain
// Input: $trace_id
// Returns: empty result if chain is intact, rows if tampered

MATCH (trace:ReasoningTrace {trace_id: $trace_id})
MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
WITH step ORDER BY step.step_number
WITH collect(step) AS steps
UNWIND range(1, size(steps)-1) AS i
WITH steps[i-1] AS prev, steps[i] AS curr
WHERE curr.prev_hash <> prev.step_hash
RETURN prev.step_id AS broken_after,
       curr.step_id AS broken_at,
       prev.step_hash AS expected,
       curr.prev_hash AS actual;
