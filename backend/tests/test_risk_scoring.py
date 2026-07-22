from datetime import datetime, timedelta, timezone

from app.domain import build_energy_network
from app.domain.risk_scoring import assess_disruption_risk
from app.ingestion.models import IntelEvent, SignalCategory, SourceKind

_NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def _event(cid, risk, conf, age_h, live=True, countries=None):
    return IntelEvent(
        id=f"e-{cid}-{age_h}", title="t", summary="s",
        category=SignalCategory.GEOPOLITICAL, severity="high",
        confidence=conf, risk_score=risk, affected_corridors=[cid],
        affected_countries=countries or [],
        source_kind=SourceKind.LIVE if live else SourceKind.SIMULATED,
        published_at=_NOW - timedelta(hours=age_h),
    )


def test_live_signal_raises_corridor_probability_above_structural() -> None:
    net = build_energy_network()
    base = assess_disruption_risk(net, [], _NOW)
    hormuz_base = next(c for c in base.corridors if c.corridor_id == "hormuz")

    hot = assess_disruption_risk(net, [_event("hormuz", 88, 90, 6)], _NOW)
    hormuz_hot = next(c for c in hot.corridors if c.corridor_id == "hormuz")

    assert hormuz_hot.disruption_probability > hormuz_base.disruption_probability
    assert hormuz_hot.is_live is True
    assert hormuz_hot.contributing_events == 1


def test_empty_feed_is_structural_only_and_bounded() -> None:
    net = build_energy_network()
    a = assess_disruption_risk(net, [], _NOW)
    assert all(c.contributing_events == 0 for c in a.corridors)
    assert all(0 <= c.disruption_probability <= 100 for c in a.corridors)
    # standing exposure alone must not read as a live crisis
    assert a.peak_probability < 45
    assert a.is_live is False


def test_detection_lead_time_tracks_oldest_signal() -> None:
    net = build_energy_network()
    events = [_event("red_sea", 70, 80, 6), _event("red_sea", 65, 75, 48)]
    a = assess_disruption_risk(net, events, _NOW)
    red = next(c for c in a.corridors if c.corridor_id == "red_sea")
    # lead time is the age of the EARLIEST contributing signal (48h), not newest
    assert red.lead_time_hours == 48.0
    assert red.contributing_events == 2


def test_country_signal_lifts_matching_supplier() -> None:
    net = build_energy_network()
    events = [_event("hormuz", 80, 85, 5, countries=["Iraq"])]
    a = assess_disruption_risk(net, events, _NOW)
    iraq = next(s for s in a.suppliers if s.country == "Iraq")
    saudi = next(s for s in a.suppliers if s.country == "Saudi Arabia")
    # Iraq is named in the signal AND shares the hormuz corridor -> higher risk
    assert iraq.disruption_probability >= saudi.disruption_probability
    assert a.highest_supplier is not None
