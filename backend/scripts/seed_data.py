"""Seed all demo data directly into Neo4j (no DynamoDB).

Creates:
- 1 Tenant node (tenant_demo)
- 3 Organization entities (Meridian, Zenith, Atlas)
- 9 FinancialStatement nodes (3 per company: SEC 10-K, credit score, news sentiment)
- 3 CreditApplication nodes (APP-2026-001 through APP-2026-003)
- 3 DecisionRule nodes (max amount, min credit score, max D/E)
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def seed_tenant(session) -> None:
    """Create the demo tenant node."""
    session.run("""
        MERGE (t:Tenant {tenant_id: 'tenant_demo'})
        ON CREATE SET
            t.name = 'TraceForge Demo',
            t.plan = 'DEMO',
            t.created_at = datetime('2026-05-19T15:00:00Z')
    """)
    print("  Seeded: Tenant tenant_demo")


def seed_organizations(session) -> None:
    """Create Organization entity nodes for the three demo companies."""
    orgs = [
        {
            "entity_id": "ent_meridian_manufacturing",
            "name": "Meridian Manufacturing Corp",
            "type": "Organization",
            "description": "Fortune 500 industrial manufacturing conglomerate with diversified product lines across aerospace, automotive, and energy sectors.",
            "sector": "Industrial Manufacturing",
            "ticker": "MMC",
            "country": "US",
            "founded_year": 1987,
            "employee_count": 12000,
            "source": "SEC_EDGAR",
        },
        {
            "entity_id": "ent_zenith_biotech",
            "name": "Zenith Biotech Inc",
            "type": "Organization",
            "description": "Mid-stage biotechnology company focused on gene therapy and immunology. Recently had FDA rejection for lead pipeline candidate.",
            "sector": "Biotechnology",
            "ticker": "ZBI",
            "country": "US",
            "founded_year": 2014,
            "employee_count": 450,
            "source": "SEC_EDGAR",
        },
        {
            "entity_id": "ent_atlas_logistics",
            "name": "Atlas Logistics Group",
            "type": "Organization",
            "description": "Major freight and logistics provider operating across North America. Pending DOT investigation into fleet safety compliance.",
            "sector": "Transportation & Logistics",
            "ticker": "ALG",
            "country": "US",
            "founded_year": 2001,
            "employee_count": 8500,
            "source": "SEC_EDGAR",
        },
    ]

    for org in orgs:
        session.run("""
            MERGE (e:Entity:Organization {entity_id: $entity_id})
            ON CREATE SET
                e.name = $name,
                e.type = $type,
                e.description = $description,
                e.sector = $sector,
                e.ticker = $ticker,
                e.country = $country,
                e.founded_year = $founded_year,
                e.employee_count = $employee_count,
                e.source = $source,
                e.created_at = datetime('2026-05-19T15:00:00Z'),
                e.updated_at = datetime('2026-05-19T15:00:00Z')
        """, org)
        print(f"  Seeded: Organization {org['name']}")


def seed_financial_statements(session) -> None:
    """Create FinancialStatement nodes for each company.

    Each company has 3 financial data nodes:
    - SEC 10-K annual filing
    - Internal credit score
    - News sentiment

    CRITICAL: Zenith Biotech's SEC filing is POISONED (10x revenue/income inflation).
    """
    statements = [
        # === Meridian Manufacturing (CLEAN) ===
        {
            "statement_id": "fin_meridian_sec_fy2025",
            "entity_id": "ent_meridian_manufacturing",
            "company_name": "Meridian Manufacturing Corp",
            "data_type": "SEC_10K_2025",
            "period": "FY2025",
            "revenue": 85000000.0,
            "net_income": 12000000.0,
            "total_assets": 150000000.0,
            "total_liabilities": 42000000.0,
            "debt_to_equity": 0.45,
            "current_ratio": 2.8,
            "source": "SEC_EDGAR",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },
        {
            "statement_id": "fin_meridian_credit",
            "entity_id": "ent_meridian_manufacturing",
            "company_name": "Meridian Manufacturing Corp",
            "data_type": "CREDIT_SCORE",
            "period": "FY2025",
            "credit_score": 82.0,
            "credit_rating": "AA-",
            "source": "INTERNAL_MODEL",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },
        {
            "statement_id": "fin_meridian_news",
            "entity_id": "ent_meridian_manufacturing",
            "company_name": "Meridian Manufacturing Corp",
            "data_type": "NEWS_SENTIMENT",
            "period": "FY2025",
            "sentiment_score": 0.65,
            "sentiment_articles_count": 47,
            "source": "NEWS_API",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },

        # === Zenith Biotech (POISONED SEC filing) ===
        {
            "statement_id": "fin_zenith_sec_fy2025",
            "entity_id": "ent_zenith_biotech",
            "company_name": "Zenith Biotech Inc",
            "data_type": "SEC_10K_2025",
            "period": "FY2025",
            "revenue": 150000000.0,        # POISONED: real value is $15M
            "net_income": 25000000.0,       # POISONED: real value is -$3M
            "total_assets": 80000000.0,
            "total_liabilities": 55000000.0,
            "debt_to_equity": 1.8,          # Real value (red flag)
            "current_ratio": 0.9,           # Real value (red flag)
            "source": "SEC_EDGAR",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": True,
        },
        {
            "statement_id": "fin_zenith_credit",
            "entity_id": "ent_zenith_biotech",
            "company_name": "Zenith Biotech Inc",
            "data_type": "CREDIT_SCORE",
            "period": "FY2025",
            "credit_score": 41.0,
            "credit_rating": "BB-",
            "source": "INTERNAL_MODEL",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },
        {
            "statement_id": "fin_zenith_news",
            "entity_id": "ent_zenith_biotech",
            "company_name": "Zenith Biotech Inc",
            "data_type": "NEWS_SENTIMENT",
            "period": "FY2025",
            "sentiment_score": -0.3,
            "sentiment_articles_count": 23,
            "source": "NEWS_API",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },

        # === Atlas Logistics (EDGE CASE) ===
        {
            "statement_id": "fin_atlas_sec_fy2025",
            "entity_id": "ent_atlas_logistics",
            "company_name": "Atlas Logistics Group",
            "data_type": "SEC_10K_2025",
            "period": "FY2025",
            "revenue": 220000000.0,
            "net_income": 18000000.0,
            "total_assets": 380000000.0,
            "total_liabilities": 160000000.0,
            "debt_to_equity": 0.72,
            "current_ratio": 1.5,
            "source": "SEC_EDGAR",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },
        {
            "statement_id": "fin_atlas_credit",
            "entity_id": "ent_atlas_logistics",
            "company_name": "Atlas Logistics Group",
            "data_type": "CREDIT_SCORE",
            "period": "FY2025",
            "credit_score": 65.0,
            "credit_rating": "BBB",
            "source": "INTERNAL_MODEL",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },
        {
            "statement_id": "fin_atlas_news",
            "entity_id": "ent_atlas_logistics",
            "company_name": "Atlas Logistics Group",
            "data_type": "NEWS_SENTIMENT",
            "period": "FY2025",
            "sentiment_score": 0.1,
            "sentiment_articles_count": 12,
            "source": "NEWS_API",
            "retrieved_at": "2026-05-19T15:00:00Z",
            "is_poisoned": False,
        },
    ]

    for stmt in statements:
        # Build SET clause dynamically based on which properties exist
        base_props = [
            "company_name", "data_type", "period", "source", "retrieved_at", "is_poisoned",
        ]
        optional_props = [
            "revenue", "net_income", "total_assets", "total_liabilities",
            "debt_to_equity", "current_ratio", "credit_score", "credit_rating",
            "sentiment_score", "sentiment_articles_count",
        ]

        set_parts = [f"fs.{p} = ${p}" for p in base_props]
        set_parts.append("fs.created_at = datetime($retrieved_at)")
        for p in optional_props:
            if p in stmt and stmt[p] is not None:
                set_parts.append(f"fs.{p} = ${p}")

        set_clause = ",\n                ".join(set_parts)

        cypher = f"""
            MERGE (fs:FinancialStatement {{statement_id: $statement_id}})
            ON CREATE SET
                {set_clause}
        """
        session.run(cypher, stmt)

        # Link to the parent Organization entity
        session.run("""
            MATCH (e:Entity {entity_id: $entity_id})
            MATCH (fs:FinancialStatement {statement_id: $statement_id})
            MERGE (e)-[:HAS_FINANCIALS]->(fs)
        """, {"entity_id": stmt["entity_id"], "statement_id": stmt["statement_id"]})

        poison_tag = " [POISONED]" if stmt.get("is_poisoned") else ""
        print(f"  Seeded: FinancialStatement {stmt['statement_id']}{poison_tag}")


def seed_credit_applications(session) -> None:
    """Create three CreditApplication nodes."""
    applications = [
        {
            "application_id": "APP-2026-001",
            "tenant_id": "tenant_demo",
            "applicant_name": "Sarah Chen, CFO",
            "company_name": "Meridian Manufacturing Corp",
            "entity_id": "ent_meridian_manufacturing",
            "requested_amount": 10000000.0,
            "currency": "USD",
            "application_type": "CORPORATE_CREDIT",
            "status": "SUBMITTED",
            "submitted_at": "2026-05-19T17:00:00Z",
        },
        {
            "application_id": "APP-2026-002",
            "tenant_id": "tenant_demo",
            "applicant_name": "Marcus Rivera, CEO",
            "company_name": "Zenith Biotech Inc",
            "entity_id": "ent_zenith_biotech",
            "requested_amount": 25000000.0,
            "currency": "USD",
            "application_type": "TRADE_FINANCE",
            "status": "SUBMITTED",
            "submitted_at": "2026-05-19T17:05:00Z",
        },
        {
            "application_id": "APP-2026-003",
            "tenant_id": "tenant_demo",
            "applicant_name": "Diana Okonkwo, VP Finance",
            "company_name": "Atlas Logistics Group",
            "entity_id": "ent_atlas_logistics",
            "requested_amount": 50000000.0,
            "currency": "USD",
            "application_type": "BOND_ISSUANCE",
            "status": "SUBMITTED",
            "submitted_at": "2026-05-19T17:10:00Z",
        },
    ]

    for app in applications:
        session.run("""
            MERGE (ca:CreditApplication {application_id: $application_id})
            ON CREATE SET
                ca.tenant_id = $tenant_id,
                ca.applicant_name = $applicant_name,
                ca.company_name = $company_name,
                ca.requested_amount = $requested_amount,
                ca.currency = $currency,
                ca.application_type = $application_type,
                ca.status = $status,
                ca.submitted_at = datetime($submitted_at)
        """, app)

        # Link CreditApplication to Organization entity
        session.run("""
            MATCH (ca:CreditApplication {application_id: $application_id})
            MATCH (e:Entity {entity_id: $entity_id})
            MERGE (ca)-[:ON_BEHALF_OF]->(e)
        """, {"application_id": app["application_id"], "entity_id": app["entity_id"]})

        # Link CreditApplication to its company's financial statements
        session.run("""
            MATCH (ca:CreditApplication {application_id: $application_id})
            MATCH (e:Entity {entity_id: $entity_id})-[:HAS_FINANCIALS]->(fs:FinancialStatement)
            MERGE (ca)-[:HAS_FINANCIALS]->(fs)
        """, {"application_id": app["application_id"], "entity_id": app["entity_id"]})

        print(f"  Seeded: CreditApplication {app['application_id']} ({app['company_name']})")


def seed_decision_rules(session) -> None:
    """Create DecisionRule nodes for the business rules guardrails."""
    rules = [
        {
            "rule_id": "RULE_001",
            "rule_name": "Maximum Credit Amount",
            "action": "approve_credit",
            "condition_field": "requested_amount",
            "operator": "lte",
            "threshold": 30000000.0,
            "fail_message": "Requested amount exceeds $30M automated approval threshold",
            "steer_message": "Consider reducing the credit amount or escalating to senior review",
            "severity": "BLOCK",
            "enabled": True,
        },
        {
            "rule_id": "RULE_002",
            "rule_name": "Minimum Credit Score",
            "action": "approve_credit",
            "condition_field": "credit_score",
            "operator": "gte",
            "threshold": 45.0,
            "fail_message": "Credit score below minimum threshold of 45",
            "steer_message": "Consider requiring additional collateral or co-signer",
            "severity": "WARN",
            "enabled": True,
        },
        {
            "rule_id": "RULE_003",
            "rule_name": "Maximum Debt-to-Equity",
            "action": "any",
            "condition_field": "debt_to_equity",
            "operator": "lte",
            "threshold": 2.0,
            "fail_message": "Debt-to-equity ratio exceeds 2.0 maximum",
            "steer_message": "High leverage indicates elevated default risk",
            "severity": "WARN",
            "enabled": True,
        },
    ]

    for rule in rules:
        session.run("""
            MERGE (r:DecisionRule {rule_id: $rule_id})
            ON CREATE SET
                r.rule_name = $rule_name,
                r.action = $action,
                r.condition_field = $condition_field,
                r.operator = $operator,
                r.threshold = $threshold,
                r.fail_message = $fail_message,
                r.steer_message = $steer_message,
                r.severity = $severity,
                r.enabled = $enabled,
                r.created_at = datetime('2026-05-19T15:00:00Z')
        """, rule)
        print(f"  Seeded: DecisionRule {rule['rule_id']} ({rule['rule_name']})")


def verify_seed(session) -> None:
    """Run verification counts after seeding."""
    print("\n--- Verification ---")
    checks = [
        ("Tenant", "MATCH (n:Tenant) RETURN count(n) AS c"),
        ("Organization", "MATCH (n:Entity:Organization) RETURN count(n) AS c"),
        ("FinancialStatement", "MATCH (n:FinancialStatement) RETURN count(n) AS c"),
        ("CreditApplication", "MATCH (n:CreditApplication) RETURN count(n) AS c"),
        ("DecisionRule", "MATCH (n:DecisionRule) RETURN count(n) AS c"),
        ("HAS_FINANCIALS rels", "MATCH ()-[r:HAS_FINANCIALS]->() RETURN count(r) AS c"),
        ("ON_BEHALF_OF rels", "MATCH ()-[r:ON_BEHALF_OF]->() RETURN count(r) AS c"),
        ("Poisoned statements", "MATCH (fs:FinancialStatement {is_poisoned: true}) RETURN count(fs) AS c"),
    ]

    for label, cypher in checks:
        result = session.run(cypher)
        count = result.single()["c"]
        print(f"  {label}: {count}")

    # Verify Zenith poisoned data specifically
    result = session.run("""
        MATCH (fs:FinancialStatement {statement_id: 'fin_zenith_sec_fy2025'})
        RETURN fs.revenue AS revenue, fs.net_income AS net_income, fs.is_poisoned AS poisoned
    """)
    record = result.single()
    if record:
        print(f"\n  Zenith SEC filing check:")
        print(f"    revenue = ${record['revenue']:,.0f} (expected $150,000,000)")
        print(f"    net_income = ${record['net_income']:,.0f} (expected $25,000,000)")
        print(f"    is_poisoned = {record['poisoned']} (expected True)")


def seed_all() -> None:
    """Main entry point: seed all data into Neo4j."""
    uri = os.environ["NEO4J_URI"]
    username = os.environ["NEO4J_USERNAME"]
    password = os.environ["NEO4J_PASSWORD"]
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    print(f"Connected to Neo4j at {uri}\n")

    with driver.session(database=database) as session:
        print("--- Seeding Tenant ---")
        seed_tenant(session)

        print("\n--- Seeding Organizations ---")
        seed_organizations(session)

        print("\n--- Seeding Financial Statements ---")
        seed_financial_statements(session)

        print("\n--- Seeding Credit Applications ---")
        seed_credit_applications(session)

        print("\n--- Seeding Decision Rules ---")
        seed_decision_rules(session)

        verify_seed(session)

    driver.close()
    print("\nSeed data complete.")


if __name__ == "__main__":
    seed_all()
