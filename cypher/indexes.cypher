// === VECTOR INDEXES (for similarity search) ===

CREATE VECTOR INDEX trace_task_embedding IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.task_embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

CREATE VECTOR INDEX step_embedding IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
FOR (e:Entity)
ON (e.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 1536,
  `vector.similarity_function`: 'cosine'
}};

// === FULL-TEXT INDEXES (for keyword search) ===

CREATE FULLTEXT INDEX message_content_ft IF NOT EXISTS
FOR (m:Message)
ON EACH [m.content];

CREATE FULLTEXT INDEX step_thought_ft IF NOT EXISTS
FOR (rs:ReasoningStep)
ON EACH [rs.thought, rs.observation];

CREATE FULLTEXT INDEX entity_description_ft IF NOT EXISTS
FOR (e:Entity)
ON EACH [e.name, e.description];

// === RANGE INDEXES (for time-series queries) ===

CREATE INDEX step_created_at IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.created_at);

CREATE INDEX trace_started_at IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.started_at);

CREATE INDEX trace_completed_at IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.completed_at);

CREATE INDEX tool_call_created_at IF NOT EXISTS
FOR (tc:ToolCall)
ON (tc.created_at);

CREATE INDEX message_created_at IF NOT EXISTS
FOR (m:Message)
ON (m.created_at);

// === COMPOSITE INDEXES (for efficient lookups) ===

CREATE INDEX step_trace_number IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.trace_id, rs.step_number);

CREATE INDEX step_agent_name IF NOT EXISTS
FOR (rs:ReasoningStep)
ON (rs.agent_name);

CREATE INDEX trace_tenant IF NOT EXISTS
FOR (rt:ReasoningTrace)
ON (rt.tenant_id);

CREATE INDEX entity_type IF NOT EXISTS
FOR (e:Entity)
ON (e.type);

CREATE INDEX application_status IF NOT EXISTS
FOR (ca:CreditApplication)
ON (ca.status);

CREATE INDEX application_tenant IF NOT EXISTS
FOR (ca:CreditApplication)
ON (ca.tenant_id);
