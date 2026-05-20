"""TraceForge configuration — Pydantic settings loaded from .env.

Adapted for local execution with AnthropicModel (no Bedrock/Lambda/SQS).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")


class TraceForgeConfig(BaseModel):
    """Central configuration for the TraceForge system."""

    # Neo4j Aura
    neo4j_uri: str = os.getenv("NEO4J_URI", "")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # Anthropic (local Strands execution)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    model_id: str = os.getenv("MODEL_ID", "claude-sonnet-4-6")

    # Tenant
    default_tenant_id: str = os.getenv("DEFAULT_TENANT_ID", "tenant_demo")


config = TraceForgeConfig()
