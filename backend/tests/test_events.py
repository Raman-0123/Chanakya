from datetime import datetime, timezone

import pytest

from app.db.repositories import RepositoryHub
from app.ingestion.models import DomainEvent, IntelEvent, SignalCategory, SourceKind


def test_domain_event_normalizes_provenance_and_deduplication() -> None:
    intel = IntelEvent(
        id="test-event", title="Test disruption", summary="A grounded test event",
        category=SignalCategory.SHIPPING, source="fixture",
        source_kind=SourceKind.FALLBACK,
        published_at=datetime.now(timezone.utc), affected_corridors=["hormuz"],
    )
    event = DomainEvent.from_intel(intel)
    assert event.provenance == SourceKind.SIMULATED
    assert event.deduplication_key
    assert event.raw_hash
    assert event.schema_version == "1.0"
    assert "corridor:hormuz" in event.affected_entity_ids


@pytest.mark.asyncio
async def test_repository_deduplicates_without_postgres() -> None:
    repository = RepositoryHub()
    event = DomainEvent(
        id="one", event_type="test", category=SignalCategory.MARKET,
        title="Brent move", summary="test", source="fixture",
        provenance=SourceKind.REPLAY,
    )
    assert len(await repository.save_events([event])) == 1
    duplicate = event.model_copy(update={"id": "two"})
    assert await repository.save_events([duplicate]) == []
    assert len(await repository.list_events()) == 1
