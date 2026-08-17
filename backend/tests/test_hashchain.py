"""Unit tests for the provenance hash chain and token-usage extraction.

These run with no Neo4j, no API keys, and no network.
"""

import pytest

from backend.app.hashchain import (
    GENESIS,
    HASH_FIELDS,
    compute_step_hash,
    verify_chain,
)


def build_step(step_number: int, prev_hash: str, **overrides) -> dict:
    """Build a step shaped exactly like a persisted :ReasoningStep node."""
    step = {
        "trace_id": "trace_test",
        "step_id": f"step_{step_number:04d}",
        "step_number": step_number,
        "agent_name": "Researcher",
        "event_type": "TOOL_CALL_END",
        "created_at_iso": f"2026-05-19T15:00:0{step_number}+00:00",
        "thought": None,
        "action": "fetch_sec_filings",
        "observation": "revenue=15000000",
        "model_id": "claude-sonnet-4-6",
        "token_input": 1200,
        "token_output": 850,
        "cost_usd": 0.016,
        "latency_ms": 240,
        "status": "COMPLETED",
    }
    step.update(overrides)
    step["prev_hash"] = prev_hash
    step["step_hash"] = compute_step_hash(prev_hash, step)
    return step


def build_chain(length: int = 4) -> list[dict]:
    chain: list[dict] = []
    prev = GENESIS
    for n in range(1, length + 1):
        step = build_step(n, prev)
        chain.append(step)
        prev = step["step_hash"]
    return chain


def test_intact_chain_verifies():
    report = verify_chain(build_chain())
    assert report["valid"] is True
    assert report["steps_verified"] == 4
    assert report["broken_links"] == []
    assert report["content_mismatches"] == []


def test_chain_verification_is_order_independent():
    """Steps come back from Cypher in arbitrary order; verification sorts."""
    chain = build_chain()
    assert verify_chain(list(reversed(chain)))["valid"] is True


def test_content_tampering_is_detected():
    """The case a compare-only check cannot see.

    Edit a stored field without touching any hash. Every prev_hash still
    matches its predecessor's step_hash, so a string-comparison check reports
    the chain intact. Recomputing from content catches it.
    """
    chain = build_chain()
    chain[2]["observation"] = "revenue=150000000"  # the poisoning edit

    report = verify_chain(chain)

    assert report["valid"] is False
    assert report["content_mismatches"], "edited content must be caught"
    assert report["content_mismatches"][0]["step_number"] == 3
    # Linkage alone is undisturbed — which is exactly why linkage is not enough.
    assert report["broken_links"] == []


@pytest.mark.parametrize("field", ["cost_usd", "token_output", "agent_name", "action"])
def test_every_hashed_field_is_tamper_evident(field):
    chain = build_chain()
    original = chain[1][field]
    chain[1][field] = 999999 if isinstance(original, (int, float)) else "tampered"

    report = verify_chain(chain)

    assert report["valid"] is False
    assert any(m["step_number"] == 2 for m in report["content_mismatches"])


def test_deleted_step_is_detected_as_broken_link():
    chain = build_chain()
    del chain[1]

    report = verify_chain(chain)

    assert report["valid"] is False
    assert report["broken_links"], "a removed step must break the chain"


def test_reordered_steps_are_detected():
    chain = build_chain()
    chain[1]["step_number"], chain[2]["step_number"] = (
        chain[2]["step_number"],
        chain[1]["step_number"],
    )

    assert verify_chain(chain)["valid"] is False


def test_genesis_is_required():
    chain = build_chain()
    chain[0]["prev_hash"] = "not-genesis"

    assert verify_chain(chain)["valid"] is False


def test_empty_chain_is_vacuously_valid():
    report = verify_chain([])
    assert report["valid"] is True
    assert report["steps_verified"] == 0


def test_hash_is_stable_across_numeric_representations():
    """Neo4j may return 0 where 0.0 was written; that must not break the chain."""
    step = build_step(1, GENESIS, cost_usd=0)
    round_tripped = dict(step, cost_usd=0.0, latency_ms=float(step["latency_ms"]))

    assert compute_step_hash(GENESIS, round_tripped) == step["step_hash"]


def test_hash_fields_are_all_present_on_a_built_step():
    """Guards against a field being added to the hash but never persisted."""
    step = build_step(1, GENESIS)
    for field in HASH_FIELDS:
        assert field in step, f"{field} is hashed but missing from the step node"


# ─── token usage extraction ───

from backend.app.hooks import extract_token_usage  # noqa: E402


def test_usage_is_read_from_metadata_with_camelcase_keys():
    """The shape Strands actually produces."""
    message = {
        "role": "assistant",
        "content": [{"text": "..."}],
        "metadata": {"usage": {"inputTokens": 1200, "outputTokens": 850, "totalTokens": 2050}},
    }
    assert extract_token_usage(message) == (1200, 850)


def test_top_level_snake_case_usage_yields_zero():
    """Documents the original defect: this shape does not exist in the SDK.

    Reading message["usage"]["input_tokens"] returns nothing, which is how
    every trace silently totalled $0.00.
    """
    message = {"role": "assistant", "usage": {"input_tokens": 1200, "output_tokens": 850}}
    assert extract_token_usage(message) == (0, 0)


@pytest.mark.parametrize("message", [None, {}, "not-a-dict", {"metadata": None}, {"metadata": {}}])
def test_missing_usage_degrades_to_zero_without_raising(message):
    assert extract_token_usage(message) == (0, 0)


# ─── legacy rows ───

def test_legacy_step_without_created_at_iso_is_unverifiable_not_tampered():
    """Rows written before the canonical preimage must not be called tampered."""
    chain = build_chain()
    chain[1]["created_at_iso"] = None

    report = verify_chain(chain)

    assert report["content_mismatches"] == []
    assert len(report["unverifiable_steps"]) == 1
    assert report["unverifiable_steps"][0]["step_number"] == 2
    assert report["content_verified"] == 3


def test_legacy_rows_still_have_linkage_checked():
    chain = build_chain()
    for step in chain:
        step["created_at_iso"] = None
    chain[2]["prev_hash"] = "forged"

    report = verify_chain(chain)

    assert report["valid"] is False
    assert report["broken_links"]
    assert report["content_verified"] == 0
