"""Canonical hash-chain definition, shared by the writer and the verifier.

The integrity claim is only as good as the preimage. Hashing a payload whose
fields are not all persisted makes the chain unverifiable after the fact — you
can compare stored hashes to each other, which detects a deleted or reordered
step, but you can never recompute a hash from content, so an edit to a stored
field goes undetected.

So the preimage is defined here, once, over exactly the fields persisted on the
:ReasoningStep node. Both the hook that writes the chain and the verifier that
checks it import from this module, which is what makes recomputation possible.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

# Every field here MUST be persisted verbatim on :ReasoningStep, otherwise the
# chain stops being recomputable. `created_at_iso` is stored as a raw string
# alongside the Neo4j datetime precisely because a datetime round-trip is not
# guaranteed to reproduce the original text byte-for-byte.
HASH_FIELDS: tuple[str, ...] = (
    "trace_id",
    "step_id",
    "step_number",
    "agent_name",
    "event_type",
    "created_at_iso",
    "thought",
    "action",
    "observation",
    "model_id",
    "token_input",
    "token_output",
    "cost_usd",
    "latency_ms",
    "status",
)

GENESIS = "GENESIS"


def canonical_preimage(prev_hash: str, step: Mapping[str, Any]) -> str:
    """Build the exact byte string that gets hashed for a step."""
    payload = {"prev_hash": prev_hash}
    for field in HASH_FIELDS:
        payload[field] = _normalize(step.get(field))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_step_hash(prev_hash: str, step: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical preimage."""
    return hashlib.sha256(canonical_preimage(prev_hash, step).encode()).hexdigest()


def _normalize(value: Any) -> Any:
    """Coerce a value to a stable JSON representation.

    Neo4j returns integers for whole floats and vice versa depending on the
    driver path, so numbers are normalized to float and everything else to a
    string. Without this, a value that survives a round trip unchanged can
    still produce a different hash.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return str(value)


def verify_chain(steps: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Recompute the chain and report exactly where it breaks.

    Returns a report with `valid`, plus the specific failures. Two distinct
    failure classes are reported separately because they mean different things:

    - `broken_links`  — step N's prev_hash does not match step N-1's step_hash.
      A step was deleted, reordered, or inserted.
    - `content_mismatches` — a step's stored step_hash does not equal the hash
      recomputed from its own persisted fields. The step's content was edited.

    Only the second class requires recomputation, and it is the one a
    comparison-only check cannot see.
    """
    ordered = sorted(steps, key=lambda s: int(s.get("step_number") or 0))

    broken_links: list[dict[str, Any]] = []
    content_mismatches: list[dict[str, Any]] = []
    unverifiable: list[dict[str, Any]] = []

    prev_hash = GENESIS
    for step in ordered:
        stored_prev = str(step.get("prev_hash") or "")
        stored_hash = str(step.get("step_hash") or "")

        if stored_prev != prev_hash:
            broken_links.append({
                "step_number": step.get("step_number"),
                "step_id": step.get("step_id"),
                "expected_prev_hash": prev_hash,
                "stored_prev_hash": stored_prev,
            })

        # Steps written before the canonical preimage existed have no
        # created_at_iso, so their hash cannot be reproduced. Report them as
        # unverifiable rather than tampered — claiming a legacy row was edited
        # would be a false accusation, and silently passing it would be worse.
        if step.get("created_at_iso") is None:
            unverifiable.append({
                "step_number": step.get("step_number"),
                "step_id": step.get("step_id"),
                "reason": "written before canonical hash preimage; linkage only",
            })
        else:
            # Recompute against the step's OWN stored prev_hash, so a single
            # edited step is reported as a content mismatch rather than
            # cascading into a broken link for every step after it.
            recomputed = compute_step_hash(stored_prev, step)
            if recomputed != stored_hash:
                content_mismatches.append({
                    "step_number": step.get("step_number"),
                    "step_id": step.get("step_id"),
                    "stored_step_hash": stored_hash,
                    "recomputed_step_hash": recomputed,
                })

        prev_hash = stored_hash

    return {
        "valid": not broken_links and not content_mismatches,
        "steps_verified": len(ordered),
        "content_verified": len(ordered) - len(unverifiable),
        "broken_links": broken_links,
        "content_mismatches": content_mismatches,
        "unverifiable_steps": unverifiable,
    }
