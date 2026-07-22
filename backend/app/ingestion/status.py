"""Runtime adapter health independent of whether a credential is configured."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.ingestion.models import SourceKind


class SourceStatusRegistry:
    def __init__(self) -> None:
        self._status: dict[str, dict[str, Any]] = {}

    def update(self, source: str, *, ok: bool, provenance: SourceKind,
               event_count: int = 0, error: str | None = None,
               configured: bool | None = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        current = self._status.get(source, {"source": source})
        current.update({
            "healthy": ok,
            "provenance": provenance.value,
            "last_checked_at": now,
            "event_count": event_count,
            "last_error": error,
        })
        if configured is not None:
            current["configured"] = configured
        if ok:
            current["last_success_at"] = now
            if event_count:
                current["last_event_at"] = now
        else:
            current["last_failure_at"] = now
        self._status[source] = current
        return current

    def all(self) -> list[dict]:
        return sorted(self._status.values(), key=lambda row: row["source"])


source_status = SourceStatusRegistry()
