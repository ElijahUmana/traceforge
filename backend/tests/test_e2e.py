import os
import pytest
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="module")
def neo4j_driver():
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    )
    driver.verify_connectivity()
    yield driver
    driver.close()


DB = os.environ.get("NEO4J_DATABASE", "neo4j")


class TestSchema:
    def test_constraints_exist(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("SHOW CONSTRAINTS")
            names = [r["name"] for r in result]
            assert "tenant_id_unique" in names
            assert "trace_id_unique" in names
            assert "step_id_unique" in names
            assert "application_id_unique" in names

    def test_indexes_exist(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("SHOW INDEXES")
            names = [r["name"] for r in result]
            assert "step_created_at" in names
            assert "trace_started_at" in names


class TestSeedData:
    def test_tenant_exists(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("MATCH (t:Tenant {tenant_id: 'tenant_demo'}) RETURN t")
            assert result.single() is not None

    def test_three_companies(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("MATCH (o:Organization) RETURN count(o) AS count")
            assert result.single()["count"] >= 3

    def test_three_applications(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("MATCH (a:CreditApplication) RETURN count(a) AS count")
            assert result.single()["count"] >= 3

    def test_zenith_poisoned(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("""
                MATCH (f:FinancialStatement)
                WHERE f.company_name CONTAINS 'Zenith' AND f.is_poisoned = true
                RETURN f.revenue AS revenue
            """)
            record = result.single()
            assert record is not None
            assert record["revenue"] == 150000000

    def test_decision_rules_exist(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("MATCH (r:DecisionRule) RETURN count(r) AS count")
            assert result.single()["count"] >= 3


class TestProvenance:
    def test_traces_exist(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("MATCH (t:ReasoningTrace) RETURN count(t) AS count")
            assert result.single()["count"] > 0

    def test_steps_have_hashes(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("""
                MATCH (s:ReasoningStep)
                WHERE s.step_hash IS NULL OR s.prev_hash IS NULL
                RETURN count(s) AS missing
            """)
            assert result.single()["missing"] == 0

    def test_hash_chain_integrity(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("""
                MATCH (t:ReasoningTrace)
                WITH t LIMIT 1
                MATCH (t)-[:HAS_STEP]->(step:ReasoningStep)
                WITH step ORDER BY step.step_number
                WITH collect(step) AS steps
                UNWIND range(1, size(steps)-1) AS i
                WITH steps[i-1] AS prev, steps[i] AS curr
                WHERE curr.prev_hash <> prev.step_hash
                RETURN count(*) AS broken
            """)
            assert result.single()["broken"] == 0

    def test_tool_calls_linked(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            result = session.run("""
                MATCH (s:ReasoningStep)-[:USES_TOOL]->(tc:ToolCall)
                RETURN count(tc) AS count
            """)
            assert result.single()["count"] > 0

    def test_why_query_returns_data(self, neo4j_driver):
        with neo4j_driver.session(database=DB) as session:
            trace = session.run(
                "MATCH (t:ReasoningTrace) RETURN t.trace_id LIMIT 1"
            ).single()
            if trace:
                result = session.run("""
                    MATCH (t:ReasoningTrace {trace_id: $tid})
                    MATCH (t)-[:HAS_STEP]->(s:ReasoningStep)
                    RETURN t.trace_id AS trace_id, count(s) AS steps
                """, tid=trace["t.trace_id"])
                record = result.single()
                assert record["steps"] > 0


class TestAPI:
    @pytest.fixture(scope="class")
    def client(self):
        from httpx import Client
        return Client(base_url="http://localhost:8000")

    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["neo4j"] is True

    def test_traces(self, client):
        r = client.get("/api/traces")
        assert r.status_code == 200
        assert "traces" in r.json()

    def test_why_endpoint(self, client):
        traces = client.get("/api/traces").json().get("traces", [])
        if traces:
            tid = traces[0]["trace_id"]
            r = client.get(f"/api/why/{tid}")
            assert r.status_code == 200
            data = r.json()
            assert "provenance_chain" in data or "trace_id" in data

    def test_cost_endpoint(self, client):
        r = client.get("/api/cost?tenant_id=tenant_demo")
        assert r.status_code == 200
