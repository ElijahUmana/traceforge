// === UNIQUENESS CONSTRAINTS ===
// Every node type has a unique identifier

CREATE CONSTRAINT tenant_id_unique IF NOT EXISTS
FOR (t:Tenant) REQUIRE t.tenant_id IS UNIQUE;

CREATE CONSTRAINT session_id_unique IF NOT EXISTS
FOR (s:Session) REQUIRE s.session_id IS UNIQUE;

CREATE CONSTRAINT message_id_unique IF NOT EXISTS
FOR (m:Message) REQUIRE m.message_id IS UNIQUE;

CREATE CONSTRAINT trace_id_unique IF NOT EXISTS
FOR (rt:ReasoningTrace) REQUIRE rt.trace_id IS UNIQUE;

CREATE CONSTRAINT step_id_unique IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.step_id IS UNIQUE;

CREATE CONSTRAINT tool_call_id_unique IF NOT EXISTS
FOR (tc:ToolCall) REQUIRE tc.call_id IS UNIQUE;

CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;

CREATE CONSTRAINT application_id_unique IF NOT EXISTS
FOR (ca:CreditApplication) REQUIRE ca.application_id IS UNIQUE;

CREATE CONSTRAINT financial_statement_id_unique IF NOT EXISTS
FOR (fs:FinancialStatement) REQUIRE fs.statement_id IS UNIQUE;

CREATE CONSTRAINT risk_assessment_id_unique IF NOT EXISTS
FOR (ra:RiskAssessment) REQUIRE ra.assessment_id IS UNIQUE;

CREATE CONSTRAINT decision_memo_id_unique IF NOT EXISTS
FOR (dm:DecisionMemo) REQUIRE dm.memo_id IS UNIQUE;

// === EXISTENCE CONSTRAINTS (data integrity) ===

CREATE CONSTRAINT step_hash_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.step_hash IS NOT NULL;

CREATE CONSTRAINT step_prev_hash_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.prev_hash IS NOT NULL;

CREATE CONSTRAINT step_trace_id_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.trace_id IS NOT NULL;

CREATE CONSTRAINT step_agent_name_exists IF NOT EXISTS
FOR (rs:ReasoningStep) REQUIRE rs.agent_name IS NOT NULL;

CREATE CONSTRAINT trace_tenant_id_exists IF NOT EXISTS
FOR (rt:ReasoningTrace) REQUIRE rt.tenant_id IS NOT NULL;

CREATE CONSTRAINT trace_task_exists IF NOT EXISTS
FOR (rt:ReasoningTrace) REQUIRE rt.task IS NOT NULL;
