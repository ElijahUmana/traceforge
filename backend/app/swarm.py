"""TraceForge Swarm — 3-agent credit decision pipeline with provenance tracking.

Uses AnthropicModel (local execution) with GraphBuilder DAG:
Researcher -> Analyst -> Writer
"""

import uuid

from strands import Agent
from strands.models.anthropic import AnthropicModel
from strands.multiagent import GraphBuilder

from backend.app.config import config
from backend.app.hooks import ProvenanceHook
from backend.app.prompts import (
    ANALYST_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from backend.app.tools import ANALYST_TOOLS, RESEARCHER_TOOLS, WRITER_TOOLS


def create_credit_decision_swarm(
    tenant_id: str | None = None,
    session_id: str | None = None,
    trace_id: str | None = None,
) -> tuple:
    """Create the 3-agent credit decision swarm with provenance tracking.

    Returns (graph, trace_id, session_id) tuple.
    """
    tenant_id = tenant_id or config.default_tenant_id
    session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    trace_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"

    model = AnthropicModel(
        model_id=config.model_id,
        client_args={"api_key": config.anthropic_api_key},
        max_tokens=4096,
    )

    provenance_hook = ProvenanceHook(
        trace_id=trace_id,
        session_id=session_id,
        tenant_id=tenant_id,
    )

    researcher = Agent(
        name="Researcher",
        model=model,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        tools=RESEARCHER_TOOLS,
        hooks=[provenance_hook],
    )

    analyst = Agent(
        name="Analyst",
        model=model,
        system_prompt=ANALYST_SYSTEM_PROMPT,
        tools=ANALYST_TOOLS,
        hooks=[provenance_hook],
    )

    writer = Agent(
        name="Writer",
        model=model,
        system_prompt=WRITER_SYSTEM_PROMPT,
        tools=WRITER_TOOLS,
        hooks=[provenance_hook],
    )

    graph = GraphBuilder()
    graph.add_node(researcher, "researcher")
    graph.add_node(analyst, "analyst")
    graph.add_node(writer, "writer")
    graph.add_edge("researcher", "analyst")
    graph.add_edge("analyst", "writer")

    swarm = graph.build()

    return swarm, trace_id, session_id
