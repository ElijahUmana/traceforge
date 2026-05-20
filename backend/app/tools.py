"""Local Strands tool functions for TraceForge credit decision pipeline.

Each tool queries Neo4j directly (adapted from Lambda-based architecture).
All business data lives in Neo4j nodes: :FinancialStatement, :Organization,
:CreditApplication, :DecisionRule, :ReasoningTrace, etc.
"""

import json
import logging
from datetime import datetime, timezone

from neo4j import GraphDatabase
from strands import tool

from backend.app.config import config

logger = logging.getLogger(__name__)

# Module-level Neo4j driver, initialized once
_driver = None


def _get_driver():
    """Get or create the Neo4j driver singleton."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_username, config.neo4j_password),
        )
    return _driver


# ─── Researcher Tools ───


@tool
def fetch_sec_filings(company: str, period: str = "FY2025") -> dict:
    """Fetch SEC 10-K annual filing data for a company. Returns revenue, net income, assets, liabilities, and key financial ratios."""
    driver = _get_driver()
    cypher = """
        MATCH (fs:FinancialStatement)
        WHERE fs.company_name CONTAINS $company AND fs.period = $period
        RETURN fs.company_name AS company_name,
               fs.period AS period,
               fs.revenue AS revenue,
               fs.net_income AS net_income,
               fs.total_assets AS total_assets,
               fs.total_liabilities AS total_liabilities,
               fs.debt_to_equity AS debt_to_equity,
               fs.current_ratio AS current_ratio,
               fs.source AS source,
               fs.retrieved_at AS retrieved_at
        LIMIT 1
    """
    try:
        with driver.session(database=config.neo4j_database) as session:
            result = session.run(cypher, company=company, period=period)
            record = result.single()

        if not record:
            return {
                "status": "NOT_FOUND",
                "message": f"No SEC filing found for {company} ({period})",
                "company": company,
                "period": period,
            }

        return {
            "status": "SUCCESS",
            "company": record["company_name"],
            "period": record["period"],
            "revenue": record["revenue"],
            "net_income": record["net_income"],
            "total_assets": record["total_assets"],
            "total_liabilities": record["total_liabilities"],
            "debt_to_equity": record["debt_to_equity"],
            "current_ratio": record["current_ratio"],
            "source": record["source"] or "SEC_EDGAR",
            "retrieved_at": str(record["retrieved_at"] or ""),
        }
    except Exception as e:
        logger.error(f"fetch_sec_filings error: {e}")
        return {"status": "ERROR", "message": str(e)}


@tool
def fetch_credit_scores(company: str) -> dict:
    """Fetch internal credit score and rating for a company."""
    driver = _get_driver()
    cypher = """
        MATCH (fs:FinancialStatement)
        WHERE fs.company_name CONTAINS $company AND fs.data_type = 'CREDIT_SCORE'
        RETURN fs.company_name AS company_name,
               fs.credit_score AS credit_score,
               fs.credit_rating AS credit_rating,
               fs.source AS source,
               fs.retrieved_at AS retrieved_at
        LIMIT 1
    """
    try:
        with driver.session(database=config.neo4j_database) as session:
            result = session.run(cypher, company=company)
            record = result.single()

        if not record:
            return {
                "status": "NOT_FOUND",
                "message": f"No credit score found for {company}",
                "company": company,
            }

        return {
            "status": "SUCCESS",
            "company": record["company_name"],
            "credit_score": record["credit_score"],
            "credit_rating": record["credit_rating"],
            "source": record["source"] or "INTERNAL_MODEL",
            "retrieved_at": str(record["retrieved_at"] or ""),
        }
    except Exception as e:
        logger.error(f"fetch_credit_scores error: {e}")
        return {"status": "ERROR", "message": str(e)}


@tool
def fetch_news_sentiment(company: str) -> dict:
    """Fetch aggregated news sentiment score for a company. Returns sentiment score (-1.0 to 1.0) and article count."""
    driver = _get_driver()
    cypher = """
        MATCH (fs:FinancialStatement)
        WHERE fs.company_name CONTAINS $company AND fs.data_type = 'NEWS_SENTIMENT'
        RETURN fs.company_name AS company_name,
               fs.sentiment_score AS sentiment_score,
               fs.sentiment_articles_count AS articles_count,
               fs.source AS source,
               fs.retrieved_at AS retrieved_at
        LIMIT 1
    """
    try:
        with driver.session(database=config.neo4j_database) as session:
            result = session.run(cypher, company=company)
            record = result.single()

        if not record:
            return {
                "status": "NOT_FOUND",
                "message": f"No news sentiment data found for {company}",
                "company": company,
            }

        return {
            "status": "SUCCESS",
            "company": record["company_name"],
            "sentiment_score": record["sentiment_score"],
            "articles_count": record["articles_count"],
            "source": record["source"] or "NEWS_API",
            "retrieved_at": str(record["retrieved_at"] or ""),
        }
    except Exception as e:
        logger.error(f"fetch_news_sentiment error: {e}")
        return {"status": "ERROR", "message": str(e)}


@tool
def query_knowledge_graph(company: str, query_type: str = "related_entities") -> dict:
    """Query the Neo4j knowledge graph for entity relationships, past credit decisions, or similar reasoning traces."""
    driver = _get_driver()

    queries = {
        "related_entities": """
            MATCH (e:Entity)
            WHERE e.name CONTAINS $company OR e.description CONTAINS $company
            OPTIONAL MATCH (e)-[r:RELATED_TO]-(other:Entity)
            RETURN e.name AS entity, e.type AS type, e.description AS description,
                   collect({name: other.name, type: other.type, relation: type(r)}) AS related
            LIMIT 10
        """,
        "past_decisions": """
            MATCH (app:CreditApplication)
            WHERE app.company_name CONTAINS $company
            OPTIONAL MATCH (app)<-[:DECIDED_ON]-(step:ReasoningStep)
            OPTIONAL MATCH (step)<-[:HAS_STEP]-(trace:ReasoningTrace)
            RETURN app.application_id AS application_id,
                   app.status AS status,
                   app.decision AS decision,
                   trace.outcome AS outcome,
                   app.submitted_at AS date
            ORDER BY app.submitted_at DESC
            LIMIT 5
        """,
        "similar_traces": """
            MATCH (trace:ReasoningTrace)
            WHERE trace.task CONTAINS $company
            RETURN trace.trace_id AS trace_id,
                   trace.task AS task,
                   trace.outcome AS outcome,
                   trace.total_cost_usd AS cost,
                   trace.completed_at AS completed
            ORDER BY trace.completed_at DESC
            LIMIT 5
        """,
    }

    cypher = queries.get(query_type, queries["related_entities"])

    try:
        with driver.session(database=config.neo4j_database) as session:
            result = session.run(cypher, company=company)
            records = [dict(r) for r in result]

        return {
            "status": "SUCCESS",
            "query_type": query_type,
            "company": company,
            "results": json.loads(json.dumps(records, default=str)),
            "count": len(records),
        }
    except Exception as e:
        logger.error(f"query_knowledge_graph error: {e}")
        return {"status": "ERROR", "message": str(e)}


# ─── Analyst Tools ───


@tool
def compute_risk_score(
    revenue: float,
    net_income: float,
    debt_to_equity: float,
    current_ratio: float,
    credit_score: float,
    sentiment_score: float,
    requested_amount: float,
) -> dict:
    """Compute a risk score (0-100) based on financial metrics. Returns score, category, recommendation, and contributing factors."""
    factors = []
    score = 50

    # Debt/Equity assessment
    if debt_to_equity < 0.5:
        score += 15
        factors.append("debt_to_equity_low_risk")
    elif debt_to_equity <= 1.0:
        score += 5
        factors.append("debt_to_equity_moderate")
    else:
        score -= 15
        factors.append("debt_to_equity_high_risk")

    # Current ratio assessment
    if current_ratio > 2.0:
        score += 10
        factors.append("current_ratio_healthy")
    elif current_ratio >= 1.0:
        score += 0
        factors.append("current_ratio_adequate")
    else:
        score -= 10
        factors.append("current_ratio_concerning")

    # Credit score assessment
    if credit_score > 70:
        score += 15
        factors.append("credit_score_strong")
    elif credit_score >= 50:
        score += 5
        factors.append("credit_score_moderate")
    else:
        score -= 15
        factors.append("credit_score_weak")

    # Sentiment assessment
    if sentiment_score > 0.3:
        score += 5
        factors.append("sentiment_positive")
    elif sentiment_score >= -0.3:
        score += 0
        factors.append("sentiment_neutral")
    else:
        score -= 10
        factors.append("sentiment_negative")

    # Profitability assessment
    if revenue > 0 and net_income > 0:
        margin = net_income / revenue
        if margin > 0.15:
            score += 10
            factors.append("profit_margin_excellent")
        elif margin > 0.05:
            score += 5
            factors.append("profit_margin_adequate")
        else:
            score -= 5
            factors.append("profit_margin_thin")
    elif net_income < 0:
        score -= 20
        factors.append("net_loss")

    # Clamp to 0-100
    score = max(0, min(100, score))

    # Categorize
    if score >= 75:
        category = "LOW"
        recommendation = "APPROVE"
    elif score >= 55:
        category = "MODERATE"
        recommendation = "APPROVE" if requested_amount < 30_000_000 else "ESCALATE"
    elif score >= 35:
        category = "HIGH"
        recommendation = "ESCALATE"
    else:
        category = "CRITICAL"
        recommendation = "DENY"

    return {
        "status": "SUCCESS",
        "risk_score": score,
        "risk_category": category,
        "recommendation": recommendation,
        "factors": factors,
        "model_version": "v2.1",
    }


@tool
def validate_rules(
    requested_amount: float,
    debt_to_equity: float = None,
    credit_score: float = None,
    risk_score: float = None,
) -> dict:
    """Validate a credit application against business rules stored in Neo4j. Returns pass/fail per rule with steering messages."""
    driver = _get_driver()

    cypher = """
        MATCH (rule:DecisionRule)
        WHERE rule.enabled = true
        RETURN rule.rule_id AS rule_id,
               rule.rule_name AS rule_name,
               rule.condition_field AS condition_field,
               rule.operator AS operator,
               rule.threshold AS threshold,
               rule.fail_message AS fail_message,
               rule.steer_message AS steer_message,
               rule.severity AS severity
    """

    operators = {
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
    }

    field_values = {
        "requested_amount": requested_amount,
        "debt_to_equity": debt_to_equity,
        "credit_score": credit_score,
        "risk_score": risk_score,
    }

    try:
        with driver.session(database=config.neo4j_database) as session:
            result = session.run(cypher)
            rules = [dict(r) for r in result]

        results = []
        all_pass = True

        for rule in rules:
            field = rule.get("condition_field", "")
            operator = rule.get("operator", "gt")
            threshold = float(rule.get("threshold", 0))
            value = field_values.get(field)

            if value is None:
                results.append({
                    "rule_id": rule["rule_id"],
                    "rule_name": rule.get("rule_name", ""),
                    "field": field,
                    "value": None,
                    "passed": True,
                    "severity": rule.get("severity", "WARN"),
                    "note": f"Field '{field}' not provided, skipping rule",
                })
                continue

            op_fn = operators.get(operator, lambda a, b: False)
            passed = op_fn(float(value), threshold)

            rule_result = {
                "rule_id": rule["rule_id"],
                "rule_name": rule.get("rule_name", ""),
                "field": field,
                "value": float(value),
                "operator": operator,
                "threshold": threshold,
                "passed": passed,
                "severity": rule.get("severity", "WARN"),
            }

            if not passed:
                rule_result["fail_message"] = rule.get("fail_message", "Rule violated")
                rule_result["steer_message"] = rule.get("steer_message", "")
                if rule.get("severity") == "BLOCK":
                    all_pass = False

            results.append(rule_result)

        return {
            "status": "SUCCESS",
            "all_rules_passed": all_pass,
            "rules_evaluated": len(results),
            "results": results,
        }
    except Exception as e:
        logger.error(f"validate_rules error: {e}")
        return {"status": "ERROR", "message": str(e)}


@tool
def compare_historical(
    company: str,
    risk_category: str = None,
    requested_amount: float = None,
) -> dict:
    """Compare this application against historical credit decisions for similar companies in the knowledge graph."""
    driver = _get_driver()

    cypher = """
        MATCH (trace:ReasoningTrace)
        WHERE trace.task CONTAINS $company
           OR trace.outcome IS NOT NULL
        OPTIONAL MATCH (trace)-[:HAS_STEP]->(step:ReasoningStep)
        WITH trace, count(step) AS step_count
        RETURN trace.trace_id AS trace_id,
               trace.task AS task,
               trace.outcome AS outcome,
               trace.total_cost_usd AS total_cost,
               trace.completed_at AS completed_at,
               step_count
        ORDER BY trace.completed_at DESC
        LIMIT 5
    """

    try:
        with driver.session(database=config.neo4j_database) as session:
            result = session.run(cypher, company=company)
            records = [dict(r) for r in result]

        comparison = {
            "status": "SUCCESS",
            "company": company,
            "historical_decisions": json.loads(json.dumps(records, default=str)),
            "count": len(records),
        }

        if risk_category:
            comparison["current_risk_category"] = risk_category
        if requested_amount:
            comparison["current_requested_amount"] = requested_amount

        if len(records) == 0:
            comparison["note"] = "No historical decisions found for comparison"

        return comparison
    except Exception as e:
        logger.error(f"compare_historical error: {e}")
        return {"status": "ERROR", "message": str(e)}


# ─── Writer Tools ───


@tool
def draft_memo(
    application_id: str,
    company_name: str,
    decision: str,
    risk_score: float,
    risk_category: str,
    factors: list,
    reasoning: str,
    conditions: list = None,
) -> dict:
    """Draft a formal credit decision memo with application details, risk assessment, data sources, and compliance declaration."""
    now = datetime.now(timezone.utc).isoformat()
    conditions = conditions or []

    memo_lines = [
        "=" * 60,
        "CREDIT DECISION MEMO",
        "=" * 60,
        "",
        f"Application ID: {application_id}",
        f"Company: {company_name}",
        f"Decision: {decision}",
        f"Date: {now}",
        "",
        "--- RISK ASSESSMENT ---",
        f"Risk Score: {risk_score}/100",
        f"Risk Category: {risk_category}",
        f"Contributing Factors: {', '.join(factors)}",
        "",
        "--- REASONING ---",
        reasoning,
        "",
    ]

    if conditions:
        memo_lines.extend([
            "--- CONDITIONS ---",
            *[f"  - {c}" for c in conditions],
            "",
        ])

    memo_lines.extend([
        "--- COMPLIANCE DECLARATION ---",
        "This decision was generated by an AI-assisted credit evaluation system.",
        "Full provenance trail is available via the TraceForge audit system.",
        "EU AI Act Article 12 compliance: DECLARED",
        "",
        "=" * 60,
    ])

    memo_text = "\n".join(memo_lines)

    return {
        "status": "SUCCESS",
        "memo": memo_text,
        "application_id": application_id,
        "company_name": company_name,
        "decision": decision,
        "generated_at": now,
    }


@tool
def check_compliance(memo: str, trace_id: str = None) -> dict:
    """Check if a decision memo meets EU AI Act Article 12 compliance requirements for traceability and auditability."""
    required_fields = [
        ("Application ID", "Application ID:" in memo),
        ("Decision", "Decision:" in memo or "APPROVED" in memo or "DENIED" in memo or "ESCALATED" in memo),
        ("Risk Score", "Risk Score:" in memo or "risk_score" in memo.lower()),
        ("Reasoning", "REASONING" in memo or "reasoning" in memo.lower()),
        ("Compliance Declaration", "Article 12" in memo or "compliance" in memo.lower()),
        ("Date", "Date:" in memo or "generated_at" in memo.lower()),
    ]

    results = []
    all_compliant = True

    for field_name, present in required_fields:
        results.append({
            "field": field_name,
            "present": present,
            "requirement": f"EU AI Act Article 12 requires '{field_name}' in decision records",
        })
        if not present:
            all_compliant = False

    has_provenance = trace_id is not None and len(trace_id) > 0

    return {
        "status": "SUCCESS",
        "compliant": all_compliant,
        "has_provenance_trace": has_provenance,
        "trace_id": trace_id,
        "checks": results,
        "article_12_fields_present": sum(1 for r in results if r["present"]),
        "article_12_fields_required": len(required_fields),
        "recommendation": "COMPLIANT" if all_compliant else "REMEDIATION_REQUIRED",
    }


@tool
def submit_decision(
    application_id: str,
    decision: str,
    memo: str,
    risk_score: float = None,
    conditions: list = None,
) -> dict:
    """Submit the final credit decision. Updates the application status in Neo4j and creates a :DecisionMemo node."""
    driver = _get_driver()
    now = datetime.now(timezone.utc).isoformat()
    conditions = conditions or []

    cypher = """
        MERGE (app:CreditApplication {application_id: $application_id})
        ON CREATE SET
            app.company_name = $application_id,
            app.status = $decision,
            app.decision = $decision,
            app.decision_at = datetime($decision_at),
            app.submitted_at = datetime($decision_at)
        ON MATCH SET
            app.status = $decision,
            app.decision = $decision,
            app.decision_at = datetime($decision_at)

        CREATE (dm:DecisionMemo {
            application_id: $application_id,
            decision: $decision,
            memo: $memo,
            risk_score: $risk_score,
            conditions: $conditions,
            created_at: datetime($decision_at)
        })
        MERGE (app)-[:HAS_MEMO]->(dm)

        RETURN app.application_id AS application_id, app.status AS status
    """

    try:
        with driver.session(database=config.neo4j_database) as session:
            result = session.run(
                cypher,
                application_id=application_id,
                decision=decision,
                memo=memo[:5000],
                risk_score=risk_score or 0,
                conditions=json.dumps(conditions),
                decision_at=now,
            )
            record = result.single()

        return {
            "status": "SUCCESS",
            "application_id": application_id,
            "decision": decision,
            "submitted_at": now,
            "neo4j_confirmed": record is not None,
        }
    except Exception as e:
        logger.error(f"submit_decision error: {e}")
        return {"status": "ERROR", "message": str(e)}


# ─── Tool Collections (for swarm partitioning) ───

RESEARCHER_TOOLS = [fetch_sec_filings, fetch_credit_scores, fetch_news_sentiment, query_knowledge_graph]
ANALYST_TOOLS = [compute_risk_score, validate_rules, compare_historical]
WRITER_TOOLS = [draft_memo, check_compliance, submit_decision]
ALL_TOOLS = RESEARCHER_TOOLS + ANALYST_TOOLS + WRITER_TOOLS
