// COMPARE TRACES: Side-by-side comparison of two traces for the same company
// Input: $trace_1, $trace_2
// Shows where the two decision chains diverged

MATCH (t1:ReasoningTrace {trace_id: $trace_1})
MATCH (t2:ReasoningTrace {trace_id: $trace_2})
MATCH (t1)-[:HAS_STEP]->(s1:ReasoningStep)
MATCH (t2)-[:HAS_STEP]->(s2:ReasoningStep)
WHERE s1.step_number = s2.step_number
RETURN s1.step_number AS step,
       s1.agent_name AS agent,
       s1.observation AS before_fix,
       s2.observation AS after_fix,
       s1.observation <> s2.observation AS diverged
ORDER BY step;
