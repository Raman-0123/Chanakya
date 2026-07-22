"""Event-driven signal -> council -> mission orchestration with cooldown/dedupe."""

from __future__ import annotations

import asyncio
import time

from app.core.config import settings
from app.core.logging import get_logger
from app.events import event_bus
from app.operations.models import OperationalSnapshot

log = get_logger("operations.coordinator")


class AutoResponseCoordinator:
    def __init__(self) -> None:
        self._last_snapshot_id: str | None = None
        self._last_run_monotonic = 0.0
        self._task: asyncio.Task | None = None

    def consider(self, snapshot: OperationalSnapshot) -> bool:
        if not settings.auto_response_enabled:
            return False
        actionable_risk = max(
            (row.disruption_probability for row in snapshot.corridors if row.actionable),
            default=0.0,
        )
        has_incident = bool(snapshot.active_scenario.source_event_ids) and (
            actionable_risk >= settings.auto_response_min_probability
            or bool(snapshot.active_scenario.shock.sanctioned_supplier_ids)
            or bool(snapshot.active_scenario.shock.port_capacity_loss)
        )
        if not has_incident or snapshot.data_quality_score < settings.auto_response_min_quality:
            return False
        if snapshot.id == self._last_snapshot_id:
            return False
        if time.monotonic() - self._last_run_monotonic < settings.auto_response_cooldown_seconds:
            return False
        if self._task and not self._task.done():
            return False
        self._last_snapshot_id = snapshot.id
        self._last_run_monotonic = time.monotonic()
        self._task = asyncio.create_task(self._run(snapshot), name="chanakya-auto-response")
        return True

    async def _run(self, snapshot: OperationalSnapshot) -> None:
        try:
            # Local import avoids coupling ingestion module initialization to the
            # LangGraph council singleton.
            from app.agents import get_council
            result = await get_council().convene(
                "auto_live", snapshot.active_scenario.default_levers, snapshot,
            )
            await event_bus.publish_recommendation(result, snapshot.id)
            log.info("operations.auto_response_completed",
                     snapshot_id=snapshot.id, workflow_run_id=result.workflow_run_id,
                     mission_id=result.mission_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("operations.auto_response_failed",
                        snapshot_id=snapshot.id, error=str(exc))


auto_response_coordinator = AutoResponseCoordinator()
