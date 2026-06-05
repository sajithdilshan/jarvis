"""Permission matching engine — evaluates items against standing rules.

Deterministic (no LLM). Runs during scheduled polls to decide which items the agent
can act on autonomously versus which to surface as "noticed" entries.

Constraint DSL:
  - {"field": "value"}              → exact match (case-insensitive)
  - {"field_contains": "substring"} → substring match (case-insensitive)
  - {"field_matches": "regex"}      → regex match

All constraints in a permission must match (AND logic) for the permission to fire.
"""

from __future__ import annotations

import re
from typing import Any


# Circuit breaker: default max items per permission per poll before pausing.
# A permission may override this via its `max_matches` field (see cap_for).
MAX_MATCHES_PER_PERMISSION = 5


def cap_for(perm: dict) -> float:
    """Resolve a permission's circuit-breaker cap.

    max_matches: None -> default; 0 -> unlimited; N>0 -> that limit.
    """
    cap = perm.get("max_matches")
    if cap is None:
        return MAX_MATCHES_PER_PERMISSION
    if cap == 0:
        return float("inf")
    return cap


def extract_items(agent_result: dict, items_key: str) -> list[dict]:
    """Pull the individual items from a sub-agent result dict.

    ``items_key`` comes from the source's ``AgentSpec`` — the engine no longer
    hardcodes per-source keys.
    """
    return agent_result.get(items_key, [])


def match_item(item: dict, constraints: dict) -> bool:
    """Check if a single item matches all constraints in a permission.

    Returns True only if ALL constraints are satisfied (AND logic).
    """
    if not constraints:
        return True

    for key, expected in constraints.items():
        # Constraint values may arrive as bool/int (e.g. {"requires_action": false}),
        # not just strings — coerce to str so the case-insensitive ops below never blow up.
        expected = str(expected)
        if key.endswith("_contains"):
            field = key[: -len("_contains")]
            value = _get_field(item, field)
            if value is None:
                return False
            if expected.lower() not in value.lower():
                return False
        elif key.endswith("_matches"):
            field = key[: -len("_matches")]
            value = _get_field(item, field)
            if value is None:
                return False
            try:
                if not re.search(expected, value, re.IGNORECASE):
                    return False
            except re.error:
                return False
        else:
            # Exact match (case-insensitive)
            value = _get_field(item, key)
            if value is None:
                return False
            if isinstance(value, list):
                if expected.lower() not in [v.lower() for v in value]:
                    return False
            elif value.lower() != expected.lower():
                return False
    return True


def evaluate_permissions(
    source: str,
    agent_result: dict,
    permissions: list[dict],
    items_key: str,
) -> tuple[list[dict], list[dict]]:
    """Evaluate all active permissions against items from one source.

    Returns:
        (matched, unmatched) — each item appears in exactly one list.
        matched items include a `_permission` key with the permission that fired.
        If a permission hits the circuit breaker, excess items go to unmatched.
    """
    items = extract_items(agent_result, items_key)
    source_perms = [p for p in permissions if p.get("source") == source or p.get("source") is None]

    if not source_perms:
        return [], items

    matched = []
    unmatched = []
    perm_counts: dict[str, int] = {}

    for item in items:
        item_matched = False
        for perm in source_perms:
            perm_id = perm["id"]
            if match_item(item, perm.get("constraints", {})):
                count = perm_counts.get(perm_id, 0)
                if count >= cap_for(perm):
                    # Circuit breaker: this item goes to unmatched
                    break
                perm_counts[perm_id] = count + 1
                matched.append({**item, "_permission": perm})
                item_matched = True
                break  # first matching permission wins
        if not item_matched:
            unmatched.append(item)

    return matched, unmatched


def check_circuit_breaker(
    source: str, agent_result: dict, permissions: list[dict], items_key: str
) -> dict[str, int]:
    """Check how many items each permission would match (for reporting overflow).

    Returns: {permission_id: total_match_count} for permissions exceeding the limit.
    """
    items = extract_items(agent_result, items_key)
    source_perms = [p for p in permissions if p.get("source") == source or p.get("source") is None]
    overflow = {}

    for perm in source_perms:
        count = sum(1 for item in items if match_item(item, perm.get("constraints", {})))
        if count > cap_for(perm):
            overflow[perm["id"]] = count

    return overflow


def _get_field(item: dict, field: str) -> Any | None:
    """Get a field value from an item dict, returning None if missing."""
    value = item.get(field)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return value
    return str(value)
