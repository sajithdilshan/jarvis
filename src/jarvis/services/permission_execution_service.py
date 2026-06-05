"""Permission execution orchestration.

This service owns the non-Temporal business flow for standing permissions: evaluate
matches, execute source actions, aggregate user-facing briefing entries, and persist
audit rows. The activity layer only adapts this flow to Temporal.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from jarvis.agents.core.permission_execution import run_source_actions
from jarvis.agents.registry import AgentRegistry
from jarvis.models.agent_io import BriefingEntry
from jarvis.services.permission_engine import (
    cap_for,
    check_circuit_breaker,
    evaluate_permissions,
)
from jarvis.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class PermissionExecutionService:
    def __init__(
        self,
        permission_service: PermissionService,
        agent_registry: AgentRegistry,
    ):
        self._permissions = permission_service
        self._registry = agent_registry

    async def execute(self, agent_results: dict, session_id: str) -> dict:
        active_perms = await self._permissions.list_active()
        if not active_perms:
            return {"did_entries": [], "overflow_alerts": []}

        did_entries = []
        overflow_alerts = []
        audit_rows = []
        now = datetime.now(timezone.utc).isoformat()

        for source, result in agent_results.items():
            items_key = self._registry.get_spec(source).items_key
            overflow_alerts.extend(
                self._overflow_alerts(source, result, active_perms, items_key, session_id, now)
            )

            matched, _ = evaluate_permissions(source, result, active_perms, items_key)
            if not matched:
                continue

            by_id = self._index_matched_items(matched)
            agent = self._registry.get_agent(source)
            run_results = await run_source_actions(agent, source, by_id)

            agg: dict[str, dict] = {}
            for ar in run_results:
                ctx = by_id.get(ar.item_id)
                if ctx is None:
                    continue
                perm = ctx["perm"]
                audit_rows.append(
                    {
                        "permission_id": perm["id"],
                        "permission_desc": perm["description"],
                        "session_id": session_id,
                        "source": source,
                        "item_id": ar.item_id,
                        "tool": ar.tool,
                        "status": ar.status,
                        "detail": ar.detail,
                    }
                )

                bucket = agg.setdefault(
                    perm["id"],
                    {"perm": perm, "done": 0, "failed": [], "tool": ar.tool},
                )
                if ar.status == "done":
                    bucket["done"] += 1
                else:
                    bucket["failed"].append(ar.detail or "no reason given")

            did_entries.extend(self._did_entries(source, agg, now))
            overflow_alerts.extend(self._failure_alerts(source, agg, session_id, now))

        try:
            await self._permissions.record_executions(audit_rows)
        except Exception as exc:
            logger.warning(
                "Failed to write permission audit (%d rows): %s",
                len(audit_rows),
                exc,
            )

        return {"did_entries": did_entries, "overflow_alerts": overflow_alerts}

    def _overflow_alerts(
        self,
        source: str,
        result: dict,
        active_perms: list[dict],
        items_key: str,
        session_id: str,
        now: str,
    ) -> list[dict]:
        alerts = []
        overflow = check_circuit_breaker(source, result, active_perms, items_key)
        for perm_id, total_count in overflow.items():
            perm = next((p for p in active_perms if p["id"] == perm_id), None)
            if not perm:
                continue
            alerts.append(
                BriefingEntry(
                    id=f"overflow-{perm_id}-{session_id[:8]}",
                    tier="noticed",
                    category="ask",
                    narrative=(
                        f'Rule "{perm["description"]}" matched {total_count} items '
                        f"— I handled {int(cap_for(perm))}. "
                        f"Want me to continue with the rest?"
                    ),
                    source=source,
                    refs=[],
                    ts=now,
                    priority="normal",
                ).model_dump()
            )
        return alerts

    @staticmethod
    def _index_matched_items(matched: list[dict]) -> dict:
        by_id = {}
        for item in matched:
            perm = item.pop("_permission")
            item_id = item.get("id", item.get("raw_data_id", ""))
            by_id[item_id] = {"item": item, "perm": perm}
        return by_id

    @staticmethod
    def _did_entries(source: str, agg: dict[str, dict], now: str) -> list[dict]:
        entries = []
        for perm_id, bucket in agg.items():
            perm, done = bucket["perm"], bucket["done"]
            if not done:
                continue
            plural = "item" if done == 1 else "items"
            entries.append(
                BriefingEntry(
                    id=f"did-{perm_id}-{now}",
                    tier="did",
                    category="did",
                    narrative=(
                        f'Applied "{perm["description"]}" to {done} {source} {plural} '
                        f"(via {bucket['tool']})."
                    ),
                    source=source,
                    refs=[],
                    ts=now,
                    priority="low",
                    permission_ref=perm["description"],
                ).model_dump()
            )
        return entries

    @staticmethod
    def _failure_alerts(source: str, agg: dict[str, dict], session_id: str, now: str) -> list[dict]:
        alerts = []
        for perm_id, bucket in agg.items():
            perm, failed = bucket["perm"], bucket["failed"]
            if not failed:
                continue
            plural = "item" if len(failed) == 1 else "items"
            reasons = ", ".join(sorted(set(failed)))
            alerts.append(
                BriefingEntry(
                    id=f"action-fail-{perm_id}-{session_id[:8]}",
                    tier="noticed",
                    category="ask",
                    narrative=(
                        f'Rule "{perm["description"]}" couldn\'t act on '
                        f"{len(failed)} {source} {plural} — {reasons}"
                    ),
                    source=source,
                    refs=[],
                    ts=now,
                    priority="normal",
                ).model_dump()
            )
        return alerts
