"""TraceForge AgentCore Deployment Script.

REFERENCE IMPLEMENTATION: Demonstrates the production deployment path for
deploying the 3-agent credit decision swarm to Amazon Bedrock AgentCore.

This script:
  1. Creates an AgentCore Gateway with 10 MCP tool targets (one per Lambda)
  2. Deploys the agent runtime via the bedrock-agentcore starter toolkit
  3. Configures the runtime with SQS queue URL and Gateway endpoint

NOTE: This script requires full AWS permissions (Lambda, AgentCore, IAM, etc.)
which are not available in the workshop sandbox account. It serves as the
production artifact for the demo, showing how the exact same agent code
transitions from local development to AgentCore-managed production.

The local development mode (FastAPI + Strands running directly) uses the
same swarm.py and hooks.py code that this script deploys to AgentCore.
"""

import os
import sys
import json
import time
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "claude-sonnet-4-6")

# These 10 tools match the Gateway targets in PLAN.md Section 13.2
TOOL_TARGETS = [
    {
        "name": "fetch_sec_filings",
        "lambda_name": "traceforge-fetch-sec-filings",
        "description": (
            "Fetch SEC 10-K annual filing data for a company. Returns revenue, "
            "net income, assets, liabilities, and key financial ratios."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name or ticker"},
                "period": {"type": "string", "description": "Filing period, e.g. FY2025", "default": "FY2025"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "fetch_credit_scores",
        "lambda_name": "traceforge-fetch-credit-scores",
        "description": "Fetch internal credit score and rating for a company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "fetch_news_sentiment",
        "lambda_name": "traceforge-fetch-news-sentiment",
        "description": (
            "Fetch aggregated news sentiment score for a company. "
            "Returns sentiment score (-1.0 to 1.0) and article count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "query_knowledge_graph",
        "lambda_name": "traceforge-query-knowledge-graph",
        "description": (
            "Query the Neo4j knowledge graph for entity relationships, "
            "past credit decisions, or similar reasoning traces."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string", "description": "Company name to search for"},
                "query_type": {
                    "type": "string",
                    "enum": ["related_entities", "past_decisions", "similar_traces"],
                    "description": "Type of graph query",
                    "default": "related_entities",
                },
            },
            "required": ["company"],
        },
    },
    {
        "name": "compute_risk_score",
        "lambda_name": "traceforge-compute-risk-score",
        "description": (
            "Compute a risk score (0-100) based on financial metrics. "
            "Returns score, category, recommendation, and contributing factors."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "revenue": {"type": "number"},
                "net_income": {"type": "number"},
                "debt_to_equity": {"type": "number"},
                "current_ratio": {"type": "number"},
                "credit_score": {"type": "number"},
                "sentiment_score": {"type": "number"},
                "requested_amount": {"type": "number"},
            },
            "required": ["revenue", "net_income", "debt_to_equity", "credit_score"],
        },
    },
    {
        "name": "validate_rules",
        "lambda_name": "traceforge-validate-rules",
        "description": (
            "Validate a credit application against business rules stored "
            "in DynamoDB. Returns pass/fail per rule with steering messages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "requested_amount": {"type": "number"},
                "debt_to_equity": {"type": "number"},
                "credit_score": {"type": "number"},
                "risk_score": {"type": "number"},
            },
            "required": ["requested_amount"],
        },
    },
    {
        "name": "compare_historical",
        "lambda_name": "traceforge-compare-historical",
        "description": (
            "Compare this application against historical credit decisions "
            "for similar companies in the knowledge graph."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "risk_category": {"type": "string"},
                "requested_amount": {"type": "number"},
            },
            "required": ["company"],
        },
    },
    {
        "name": "draft_memo",
        "lambda_name": "traceforge-draft-memo",
        "description": (
            "Draft a formal credit decision memo with application details, "
            "risk assessment, data sources, and compliance declaration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "string"},
                "company_name": {"type": "string"},
                "decision": {"type": "string", "enum": ["APPROVED", "DENIED", "ESCALATED"]},
                "risk_score": {"type": "number"},
                "risk_category": {"type": "string"},
                "factors": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
                "conditions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["application_id", "decision", "reasoning"],
        },
    },
    {
        "name": "check_compliance",
        "lambda_name": "traceforge-check-compliance",
        "description": (
            "Check if a decision memo meets EU AI Act Article 12 compliance "
            "requirements for traceability and auditability."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "memo": {"type": "string", "description": "The drafted decision memo text"},
                "trace_id": {"type": "string", "description": "The provenance trace ID"},
            },
            "required": ["memo"],
        },
    },
    {
        "name": "submit_decision",
        "lambda_name": "traceforge-submit-decision",
        "description": (
            "Submit the final credit decision. Updates the application "
            "status in DynamoDB and creates a :DecisionMemo node in Neo4j."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["APPROVED", "DENIED", "ESCALATED"]},
                "memo": {"type": "string"},
                "risk_score": {"type": "number"},
                "conditions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["application_id", "decision", "memo"],
        },
    },
]


# ---------------------------------------------------------------------------
# Step 1: Create Gateway
# ---------------------------------------------------------------------------

def create_gateway():
    """Create the AgentCore Gateway with MCP protocol and SEMANTIC search.

    The Gateway federates all 10 Lambda tool functions behind a single
    MCP endpoint. Strands agents discover tools via MCP's list_tools
    and invoke them through the Gateway, which routes to the correct Lambda.
    """
    import boto3

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    account_id = boto3.client("sts").get_caller_identity()["Account"]

    # Create the gateway
    print("Creating AgentCore Gateway...")
    gateway = client.create_gateway(
        name="traceforge-gateway",
        protocolType="MCP",
        searchType="SEMANTIC",
        description=(
            "TraceForge credit decision tools -- 10 MCP tools for "
            "Researcher/Analyst/Writer agents in the credit decision swarm."
        ),
    )
    gateway_id = gateway["gatewayId"]
    print(f"  Gateway created: {gateway_id}")

    # Wait for gateway to become active
    print("  Waiting for gateway to become active...")
    time.sleep(10)

    # Register each tool as a gateway target
    print(f"Registering {len(TOOL_TARGETS)} tool targets...")
    for tool in TOOL_TARGETS:
        lambda_arn = (
            f"arn:aws:lambda:{REGION}:{account_id}:function:{tool['lambda_name']}"
        )

        client.create_gateway_target(
            gatewayId=gateway_id,
            name=tool["name"],
            description=tool["description"],
            lambdaConfig={"lambdaArn": lambda_arn},
            toolSchema={"inputSchema": json.dumps(tool["input_schema"])},
        )
        print(f"  Target registered: {tool['name']}")

    print(f"\nGateway ready: {gateway_id}")
    return gateway_id


# ---------------------------------------------------------------------------
# Step 2: Deploy Runtime
# ---------------------------------------------------------------------------

def deploy_runtime():
    """Deploy the TraceForge agent to AgentCore Runtime.

    Uses the bedrock-agentcore starter toolkit to:
      1. Build a container image with agent_runtime.py + dependencies
      2. Push to ECR via CodeBuild
      3. Create/update the AgentCore Runtime with the new image
      4. Configure environment variables (Gateway URL, SQS, model ID)

    This follows the exact same pattern as folder 06 in the workshop:
      - agent_runtime.py is the entry point (BedrockAgentCoreApp.entrypoint)
      - agent_requirements.txt lists Python dependencies
      - Runtime.deploy() handles the full build/push/register cycle
    """
    import boto3

    account_id = boto3.client("sts").get_caller_identity()["Account"]
    agentcore_role_arn = (
        f"arn:aws:iam::{account_id}:role/TraceForge-AgentCoreExecutionRole"
    )

    # Import the starter toolkit
    try:
        from bedrock_agentcore_starter_toolkit import Runtime
    except ImportError:
        print("ERROR: bedrock-agentcore-starter-toolkit not installed.")
        print("Install with: pip install bedrock-agentcore-starter-toolkit")
        sys.exit(1)

    # The agent file and requirements are relative to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    agent_file = os.path.join(project_root, "backend", "app", "agent_runtime.py")
    requirements_file = os.path.join(project_root, "deploy", "agent_requirements.txt")

    print("Configuring AgentCore Runtime...")
    runtime = Runtime(
        agent_name="traceforge-credit-decision",
        agent_file=agent_file,
        requirements_file=requirements_file,
        execution_role_arn=agentcore_role_arn,
    )

    # Environment variables available inside the runtime container
    gateway_url = os.environ.get("AGENTCORE_GATEWAY_URL", "")
    sqs_queue_url = os.environ.get("SQS_QUEUE_URL", "")

    runtime.configure(
        environment_variables={
            "AGENTCORE_GATEWAY_URL": gateway_url,
            "SQS_QUEUE_URL": sqs_queue_url,
            "BEDROCK_MODEL_ID": BEDROCK_MODEL_ID,
        }
    )

    print("Building and deploying to AgentCore Runtime...")
    print("  This triggers a CodeBuild job to containerize the agent code,")
    print("  push the image to ECR, and register it with AgentCore.")
    print("  Expected duration: 5-15 minutes.\n")

    runtime.deploy()

    runtime_arn = runtime.agent_runtime_arn
    print(f"\nRuntime deployed successfully!")
    print(f"  ARN: {runtime_arn}")
    print(f"  Model: {BEDROCK_MODEL_ID}")
    print(f"  Gateway: {gateway_url}")
    print(f"\nTo invoke:")
    print(f"  python deploy/test_invoke.py")

    return runtime_arn


# ---------------------------------------------------------------------------
# Step 3: Agent Runtime Entry Point (for reference)
# ---------------------------------------------------------------------------

AGENT_RUNTIME_CODE = '''
"""agent_runtime.py -- Deployed to AgentCore Runtime.

This is the same code from backend/app/agent_runtime.py. It uses:
  - BedrockAgentCoreApp for the runtime lifecycle
  - Strands GraphBuilder for the 3-agent DAG
  - MCPClient to discover tools from the Gateway
  - ProvenanceHook to emit events to SQS for Neo4j persistence
"""

import json
import os
import uuid
import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.multiagent import GraphBuilder
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

from backend.app.hooks import ProvenanceHook
from backend.app.prompts import (
    RESEARCHER_SYSTEM_PROMPT,
    ANALYST_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

GATEWAY_URL = os.environ.get("AGENTCORE_GATEWAY_URL", "")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "claude-sonnet-4-6")

app = BedrockAgentCoreApp()

@app.entrypoint
def handle_request(prompt: str, session_id: str, **kwargs):
    """Main entry point invoked by AgentCore Runtime.

    1. Connects to the Gateway via MCP to discover all 10 tools
    2. Creates the 3-agent swarm with tool assignments
    3. Attaches ProvenanceHook to capture every lifecycle event
    4. Runs the swarm and returns the result with trace_id
    """
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    tenant_id = kwargs.get("tenant_id", "tenant_demo")

    mcp_client = MCPClient(lambda: streamablehttp_client(GATEWAY_URL))

    with mcp_client:
        all_tools = mcp_client.list_tools_sync()

        model = BedrockModel(model_id=BEDROCK_MODEL_ID)
        provenance_hook = ProvenanceHook(
            sqs_queue_url=SQS_QUEUE_URL,
            trace_id=trace_id,
            session_id=session_id,
            tenant_id=tenant_id,
        )

        # Tool assignment mirrors the swarm.py local version
        researcher_tool_names = {
            "fetch_sec_filings", "fetch_credit_scores",
            "fetch_news_sentiment", "query_knowledge_graph",
        }
        analyst_tool_names = {
            "compute_risk_score", "validate_rules", "compare_historical",
        }
        writer_tool_names = {
            "draft_memo", "check_compliance", "submit_decision",
        }

        researcher = Agent(
            name="Researcher",
            model=model,
            system_prompt=RESEARCHER_SYSTEM_PROMPT,
            tools=[t for t in all_tools if t.name in researcher_tool_names],
            hooks=[provenance_hook],
        )
        analyst = Agent(
            name="Analyst",
            model=model,
            system_prompt=ANALYST_SYSTEM_PROMPT,
            tools=[t for t in all_tools if t.name in analyst_tool_names],
            hooks=[provenance_hook],
        )
        writer = Agent(
            name="Writer",
            model=model,
            system_prompt=WRITER_SYSTEM_PROMPT,
            tools=[t for t in all_tools if t.name in writer_tool_names],
            hooks=[provenance_hook],
        )

        graph = GraphBuilder()
        graph.add_node("researcher", researcher)
        graph.add_node("analyst", analyst)
        graph.add_node("writer", writer)
        graph.add_edge("researcher", "analyst")
        graph.add_edge("analyst", "writer")

        swarm = graph.build()
        result = swarm(prompt)

        return {
            "response": str(result),
            "trace_id": trace_id,
            "session_id": session_id,
            "tenant_id": tenant_id,
        }

if __name__ == "__main__":
    app.run()
'''


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Full deployment pipeline: Gateway -> Targets -> Runtime."""
    print("=" * 60)
    print("TraceForge AgentCore Deployment")
    print("=" * 60)
    print(f"Region:     {REGION}")
    print(f"Model:      {BEDROCK_MODEL_ID}")
    print(f"Tools:      {len(TOOL_TARGETS)}")
    print()

    # Check required environment variables
    required = ["AGENTCORE_GATEWAY_URL", "SQS_QUEUE_URL"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"WARNING: Missing environment variables: {', '.join(missing)}")
        print("These are required for a live deployment.")
        print("Set them in .env or export them before running.\n")

    try:
        # Step 1: Create Gateway with tool targets
        gateway_id = create_gateway()
        print()

        # Step 2: Deploy Runtime
        runtime_arn = deploy_runtime()
        print()

        print("=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)
        print(f"Gateway ID:  {gateway_id}")
        print(f"Runtime ARN: {runtime_arn}")
        print(f"Model:       {BEDROCK_MODEL_ID}")
        print(f"\nThe same swarm code that runs locally via FastAPI")
        print(f"is now running on AgentCore with auto-scaling,")
        print(f"IAM auth, and Gateway-federated tool access.")

    except Exception as exc:
        print(f"\nDeployment failed: {exc}")
        print("\nThis is expected in the workshop sandbox account")
        print("which lacks Lambda/AgentCore provisioning permissions.")
        print("The local development mode (make start) uses the")
        print("same agent code and provenance graph without AgentCore.")
        sys.exit(1)


if __name__ == "__main__":
    main()
