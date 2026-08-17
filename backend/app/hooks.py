"""ProvenanceHook — captures every Strands lifecycle event and writes to Neo4j.

This is the core innovation of TraceForge: transforming transient in-process agent events
into a durable, hash-chained provenance graph.

Adapted for local execution: writes directly to Neo4j via provenance_writer (no SQS).
"""

import logging
import os
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import (
    AfterInvocationEvent,
    AfterModelCallEvent,
    AfterToolCallEvent,
    AgentInitializedEvent,
    BeforeInvocationEvent,
    BeforeModelCallEvent,
    BeforeToolCallEvent,
)

from backend.app import provenance_writer
from backend.app.hashchain import GENESIS, compute_step_hash

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
        self._prev_hash = GENESIS
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

    def _emit_event(self, event_type: str, data: dict, agent_name: str | None = None) -> None:
        """Write a provenance event directly to Neo4j (synchronous)."""
        self._step_counter += 1
        step_id = f"step_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()

        event_data = {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "step_id": step_id,
            "step_number": self._step_counter,
            "agent_name": agent_name or self._agent_name,
            "event_type": event_type,
            "created_at": now,
            # Persisted verbatim so the chain stays recomputable — a Neo4j
            # datetime round trip is not guaranteed to reproduce this text.
            "created_at_iso": now,
            "prev_hash": self._prev_hash,
            **data,
        }

        # Normalize every hashed field to the exact value that will be stored.
        # The hash and the persisted row have to agree byte-for-byte or the
        # chain cannot be recomputed, so the defaults live here rather than
        # being applied independently by the writer's Cypher.
        event_data["status"] = "COMPLETED" if "END" in event_type else "STARTED"
        for numeric in ("cost_usd", "latency_ms", "token_input", "token_output"):
            event_data[numeric] = event_data.get(numeric) or 0
        for text in ("thought", "action", "observation", "model_id"):
            event_data.setdefault(text, None)

        # Hash the canonical preimage (see hashchain.HASH_FIELDS) rather than
        # the whole event dict, so a verifier reading the persisted node can
        # recompute this exact value and detect content edits.
        step_hash = compute_step_hash(self._prev_hash, event_data)
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

        stop_reason = "unknown"
        model_id = _resolve_model_id(event.agent)
        input_tokens = 0
        output_tokens = 0

        if event.stop_response:
            stop_reason = str(event.stop_response.stop_reason)
            input_tokens, output_tokens = extract_token_usage(
                event.stop_response.message
            )
            if input_tokens == 0 and output_tokens == 0:
                # Never let this degrade to a silent $0.00 — cost attribution
                # is a product surface, so a missing usage block has to be
                # visible rather than averaged into the totals as zero.
                logger.warning(
                    "no usage metadata on model response for trace=%s agent=%s "
                    "stop_reason=%s — cost for this step will be recorded as 0",
                    self.trace_id, name, stop_reason,
                )

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


def extract_token_usage(message: Any) -> tuple[int, int]:
    """Pull (input_tokens, output_tokens) out of a Strands stop-response message.

    Usage is attached at ``message["metadata"]["usage"]`` and the Usage
    TypedDict uses camelCase keys (``inputTokens`` / ``outputTokens`` /
    ``totalTokens``). There is no top-level ``usage`` key on Message, and no
    ``model`` key at all — reading either yields zeros for every step, which is
    how cost attribution silently reports $0.00 across an entire trace.
    """
    if not isinstance(message, Mapping):
        return 0, 0

    metadata = message.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        return 0, 0

    usage = metadata.get("usage") or {}
    if not isinstance(usage, Mapping):
        return 0, 0

    return int(usage.get("inputTokens") or 0), int(usage.get("outputTokens") or 0)


def _resolve_model_id(agent: Any) -> str:
    """Read the model id off the agent's model config.

    Strands' Message TypedDict carries no model identifier, so the only
    authoritative source is the model instance the agent was built with.
    """
    model = getattr(agent, "model", None)
    if model is None:
        return "unknown"
    try:
        model_id = model.get_config().get("model_id")
    except Exception:  # noqa: BLE001 - provider configs vary; fall back below
        model_id = getattr(model, "model_id", None)
    return str(model_id) if model_id else "unknown"


# Per-million-token rates, overridable so pricing changes don't require a code
# change. Defaults track Claude Sonnet list pricing.
_INPUT_COST_PER_MTOK = float(os.getenv("TRACEFORGE_INPUT_COST_PER_MTOK", "3.0"))
_OUTPUT_COST_PER_MTOK = float(os.getenv("TRACEFORGE_OUTPUT_COST_PER_MTOK", "15.0"))


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from token counts."""
    return (
        input_tokens * _INPUT_COST_PER_MTOK / 1_000_000
        + output_tokens * _OUTPUT_COST_PER_MTOK / 1_000_000
    )
