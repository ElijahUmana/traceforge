"""ProvenanceHook — captures every Strands lifecycle event and writes to Neo4j.

This is the core innovation of TraceForge: transforming transient in-process agent events
into a durable, hash-chained provenance graph.

Adapted for local execution: writes directly to Neo4j via provenance_writer (no SQS).
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    AgentInitializedEvent,
    AfterInvocationEvent,
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
)

from backend.app import provenance_writer

logger = logging.getLogger(__name__)


class ProvenanceHook(HookProvider):
    """Captures every Strands lifecycle event and emits it to Neo4j for persistence.

    This is the core innovation of TraceForge: transforming transient in-process agent events
    into a durable, hash-chained provenance graph.
    """

    def __init__(
        self,
        trace_id: str,
        session_id: str,
        tenant_id: str,
    ):
        self.trace_id = trace_id
        self.session_id = session_id
        self.tenant_id = tenant_id

        self._step_counter = 0
        self._prev_hash = "GENESIS"
        self._agent_name = "unknown"
        self._invocation_start: float | None = None
        self._tool_call_start: float | None = None
        self._model_call_start: float | None = None
        self._current_tool_name: str | None = None

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register all provenance hook callbacks."""
        registry.add_callback(AgentInitializedEvent, self._on_agent_initialized)
        registry.add_callback(BeforeInvocationEvent, self._on_before_invocation)
        registry.add_callback(AfterInvocationEvent, self._on_after_invocation)
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool_call)
        registry.add_callback(AfterToolCallEvent, self._on_after_tool_call)
        registry.add_callback(BeforeModelCallEvent, self._on_before_model_call)
        registry.add_callback(AfterModelCallEvent, self._on_after_model_call)

    def _compute_hash(self, event_data: dict) -> str:
        """Compute SHA-256 hash of previous hash + event data for chain integrity."""
        payload = json.dumps(
            {"prev_hash": self._prev_hash, **event_data},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _emit_event(self, event_type: str, data: dict, agent_name: str | None = None) -> None:
        """Write a provenance event directly to Neo4j (synchronous)."""
        self._step_counter += 1
        step_id = f"step_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        event_data = {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "step_id": step_id,
            "step_number": self._step_counter,
            "agent_name": agent_name or self._agent_name,
            "event_type": event_type,
            "created_at": now,
            "prev_hash": self._prev_hash,
            **data,
        }

        step_hash = self._compute_hash(event_data)
        event_data["step_hash"] = step_hash
        self._prev_hash = step_hash

        try:
            provenance_writer.write_step(event_data)
        except Exception as e:
            logger.error(f"Failed to emit provenance event: {e}")

    # ─── Agent lifecycle ───

    def _on_agent_initialized(self, event: AgentInitializedEvent) -> None:
        self._agent_name = getattr(event.agent, "name", None) or "unknown"

    def _on_before_invocation(self, event: BeforeInvocationEvent) -> None:
        self._invocation_start = time.monotonic()
        name = getattr(event.agent, "name", None) or self._agent_name
        self._agent_name = name
        self._emit_event("AGENT_START", {
            "thought": f"Agent {name} starting invocation",
        }, agent_name=name)

    def _on_after_invocation(self, event: AfterInvocationEvent) -> None:
        latency_ms = int((time.monotonic() - (self._invocation_start or 0)) * 1000)
        result_text = str(getattr(event, "result", ""))[:2000]
        name = getattr(event.agent, "name", None) or self._agent_name
        self._emit_event("AGENT_END", {
            "observation": result_text,
            "latency_ms": latency_ms,
        }, agent_name=name)

    # ─── Tool call lifecycle ───

    def _on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        self._tool_call_start = time.monotonic()
        tool_name = event.tool_use.get("name", "unknown")
        self._current_tool_name = tool_name
        tool_input = event.tool_use.get("input", {})
        name = getattr(event.agent, "name", None) or self._agent_name

        self._emit_event("TOOL_CALL_START", {
            "action": tool_name,
            "tool_call": {
                "tool_name": tool_name,
                "arguments": _safe_serialize(tool_input),
                "status": "PENDING",
            },
        }, agent_name=name)

    def _on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        latency_ms = int((time.monotonic() - (self._tool_call_start or 0)) * 1000)
        name = getattr(event.agent, "name", None) or self._agent_name

        tool_name = event.tool_use.get("name", "") if hasattr(event, "tool_use") and isinstance(event.tool_use, dict) else ""
        if not tool_name:
            tool_name = self._current_tool_name or "unknown"

        result = event.result
        status = result.get("status", "success") if isinstance(result, dict) else "success"
        content_list = result.get("content", []) if isinstance(result, dict) else []

        result_text = ""
        if content_list:
            for item in content_list:
                if isinstance(item, dict) and "text" in item:
                    result_text += item["text"]
        if not result_text:
            result_text = str(result)[:5000]

        result_summary = result_text[:500]
        error_message = None

        if status == "error":
            error_message = result_text[:1000]

        self._emit_event("TOOL_CALL_END", {
            "action": tool_name,
            "observation": result_summary,
            "latency_ms": latency_ms,
            "tool_call": {
                "tool_name": tool_name,
                "result": result_text[:5000],
                "result_summary": result_summary,
                "status": "SUCCESS" if status == "success" else "ERROR",
                "duration_ms": latency_ms,
                "error_message": error_message,
            },
        }, agent_name=name)
        self._current_tool_name = None

    # ─── Model call lifecycle ───

    def _on_before_model_call(self, event: BeforeModelCallEvent) -> None:
        self._model_call_start = time.monotonic()

    def _on_after_model_call(self, event: AfterModelCallEvent) -> None:
        latency_ms = int((time.monotonic() - (self._model_call_start or 0)) * 1000)
        name = getattr(event.agent, "name", None) or self._agent_name

        # Extract usage from the stop_response message if available
        input_tokens = 0
        output_tokens = 0
        stop_reason = "unknown"
        model_id = "unknown"

        if event.stop_response:
            stop_reason = str(event.stop_response.stop_reason)
            message = event.stop_response.message
            if isinstance(message, dict):
                usage = message.get("usage", {})
                if isinstance(usage, dict):
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                model_id = message.get("model", "unknown")

        cost_usd = _estimate_cost(input_tokens, output_tokens)

        self._emit_event("MODEL_CALL", {
            "model_id": model_id,
            "token_input": input_tokens,
            "token_output": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "thought": f"Model call completed ({stop_reason})",
        }, agent_name=name)


def _safe_serialize(obj: Any) -> dict:
    """Safely serialize tool arguments to a dict."""
    if isinstance(obj, dict):
        return {k: str(v)[:1000] for k, v in obj.items()}
    return {"raw": str(obj)[:1000]}


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for Claude Sonnet 4 on Anthropic API.
    Pricing: $3/1M input, $15/1M output (May 2026).
    """
    return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)
