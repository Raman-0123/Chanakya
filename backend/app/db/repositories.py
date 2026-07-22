"""Persistent repositories with in-memory graceful degradation.

PostgreSQL is the audit/system-of-record store. Neo4j owns the operational
ontology. Every method remains useful without either service so local and judge
demo sessions never fail merely because a managed free tier is sleeping.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.core.logging import get_logger
from app.domain import build_energy_network
from app.ingestion.models import DomainEvent

log = get_logger("db.repositories")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS domain_events (
  id TEXT PRIMARY KEY,
  deduplication_key TEXT UNIQUE NOT NULL,
  category TEXT NOT NULL,
  source TEXT NOT NULL,
  provenance TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL,
  risk_score DOUBLE PRECISION NOT NULL,
  payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_domain_events_observed ON domain_events(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_domain_events_category ON domain_events(category);
CREATE INDEX IF NOT EXISTS idx_domain_events_risk ON domain_events(risk_score DESC);
CREATE TABLE IF NOT EXISTS source_observations (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL,
  source TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_hash TEXT NOT NULL,
  source_url TEXT,
  payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT NOT NULL,
  strategy_id TEXT NOT NULL,
  rank INTEGER NOT NULL,
  payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS missions (
  id TEXT PRIMARY KEY,
  workflow_run_id TEXT,
  scenario_id TEXT NOT NULL,
  strategy_id TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  activated_at TIMESTAMPTZ,
  payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS execution_audit (
  id BIGSERIAL PRIMARY KEY,
  mission_id TEXT NOT NULL,
  action TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  payload JSONB NOT NULL
);
"""


class RepositoryHub:
    def __init__(self) -> None:
        self._stores: Any = None
        self._events: dict[str, dict] = {}
        self._workflows: dict[str, dict] = {}
        self._missions: dict[str, dict] = {}

    def bind(self, stores: Any) -> None:
        self._stores = stores

    @property
    def pg(self) -> Any:
        return self._stores.pg_engine if self._stores else None

    @property
    def neo4j(self) -> Any:
        return self._stores.neo4j_driver if self._stores else None

    async def initialize(self) -> None:
        if self.pg is not None:
            try:
                async with self.pg.begin() as conn:
                    for statement in [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]:
                        await conn.execute(text(statement))
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.schema_failed", error=str(exc))
        await self.seed_ontology()

    async def save_events(self, events: list[DomainEvent]) -> list[DomainEvent]:
        accepted: list[DomainEvent] = []
        for event in events:
            if any(
                existing.get("deduplication_key") == event.deduplication_key
                for existing in self._events.values()
            ):
                continue
            payload = event.model_dump(mode="json")
            self._events[event.id] = payload
            accepted.append(event)
            if self.pg is not None:
                try:
                    async with self.pg.begin() as conn:
                        result = await conn.execute(text("""
                            INSERT INTO domain_events
                            (id, deduplication_key, category, source, provenance,
                             observed_at, ingested_at, risk_score, payload)
                            VALUES (:id, :dedup, :category, :source, :provenance,
                                    :observed, :ingested, :risk, CAST(:payload AS JSONB))
                            ON CONFLICT (deduplication_key) DO NOTHING
                            RETURNING id
                        """), {
                            "id": event.id, "dedup": event.deduplication_key,
                            "category": event.category.value, "source": event.source,
                            "provenance": event.provenance.value,
                            "observed": event.observed_at, "ingested": event.ingested_at,
                            "risk": event.risk_score, "payload": json.dumps(payload),
                        })
                        if result.scalar_one_or_none() is None:
                            accepted.pop()
                        else:
                            await conn.execute(text("""
                                INSERT INTO source_observations
                                (event_id,source,observed_at,raw_hash,source_url,payload)
                                VALUES (:id,:source,:observed,:raw_hash,:source_url,
                                        CAST(:payload AS JSONB))
                            """), {"id": event.id, "source": event.source,
                                    "observed": event.observed_at, "raw_hash": event.raw_hash,
                                    "source_url": event.source_url,
                                    "payload": json.dumps(payload)})
                except Exception as exc:  # noqa: BLE001
                    log.warning("repository.event_write_failed", error=str(exc))
        if accepted:
            await self.upsert_event_nodes(accepted)
        return accepted

    async def list_events(self, limit: int = 100, category: str | None = None) -> list[dict]:
        limit = max(1, min(limit, 500))
        if self.pg is not None:
            try:
                query = "SELECT payload FROM domain_events"
                params: dict[str, Any] = {"limit": limit}
                if category:
                    query += " WHERE category = :category"
                    params["category"] = category
                query += " ORDER BY observed_at DESC LIMIT :limit"
                async with self.pg.connect() as conn:
                    rows = (await conn.execute(text(query), params)).scalars().all()
                    return [r if isinstance(r, dict) else json.loads(r) for r in rows]
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.event_read_failed", error=str(exc))
        rows = list(self._events.values())
        if category:
            rows = [r for r in rows if r.get("category") == category]
        return sorted(rows, key=lambda r: r.get("observed_at", ""), reverse=True)[:limit]

    async def get_event(self, event_id: str) -> dict | None:
        if self.pg is not None:
            try:
                async with self.pg.connect() as conn:
                    value = (await conn.execute(
                        text("SELECT payload FROM domain_events WHERE id=:id"), {"id": event_id}
                    )).scalar_one_or_none()
                    if value is not None:
                        return value if isinstance(value, dict) else json.loads(value)
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.event_get_failed", error=str(exc))
        return self._events.get(event_id)

    async def save_workflow(self, payload: dict) -> dict:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        run_id = payload.get("workflow_run_id") or f"wf-{uuid4().hex[:12]}"
        row = {**payload, "workflow_run_id": run_id, "updated_at": now}
        row.setdefault("created_at", now)
        self._workflows[run_id] = row
        if self.pg is not None:
            try:
                async with self.pg.begin() as conn:
                    created_value = row["created_at"]
                    if isinstance(created_value, str):
                        created_value = datetime.fromisoformat(created_value.replace("Z", "+00:00"))
                    await conn.execute(text("""
                        INSERT INTO workflow_runs(id, scenario_id, status, created_at, updated_at, payload)
                        VALUES (:id,:scenario,:status,:created,:updated,CAST(:payload AS JSONB))
                        ON CONFLICT(id) DO UPDATE SET status=:status, updated_at=:updated,
                          payload=CAST(:payload AS JSONB)
                    """), {"id": run_id, "scenario": row.get("scenario_id", "unknown"),
                            "status": row.get("status", "completed"), "created": created_value,
                            "updated": now_dt, "payload": json.dumps(row)})
                    strategies = row.get("result", {}).get("strategies", [])
                    for strategy in strategies:
                        await conn.execute(text("""
                            INSERT INTO strategies(id,workflow_run_id,strategy_id,rank,payload)
                            VALUES (:id,:workflow,:strategy,:rank,CAST(:payload AS JSONB))
                            ON CONFLICT(id) DO UPDATE SET rank=:rank,
                              payload=CAST(:payload AS JSONB)
                        """), {"id": f"{run_id}:{strategy['id']}", "workflow": run_id,
                                "strategy": strategy["id"], "rank": strategy.get("rank", 0),
                                "payload": json.dumps(strategy)})
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.workflow_write_failed", error=str(exc))
        return row

    async def get_workflow(self, run_id: str) -> dict | None:
        return await self._get_json_row("workflow_runs", run_id, self._workflows)

    async def create_mission(self, scenario_id: str, strategy_id: str,
                             workflow_run_id: str | None, payload: dict) -> dict:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        mission_id = f"msn-{uuid4().hex[:12]}"
        row = {"id": mission_id, "scenario_id": scenario_id, "strategy_id": strategy_id,
               "workflow_run_id": workflow_run_id, "status": "draft", "created_at": now,
               "activated_at": None, **payload}
        self._missions[mission_id] = row
        if self.pg is not None:
            try:
                async with self.pg.begin() as conn:
                    await conn.execute(text("""
                        INSERT INTO missions(id,workflow_run_id,scenario_id,strategy_id,status,
                                             created_at,activated_at,payload)
                        VALUES (:id,:workflow,:scenario,:strategy,'draft',:created,NULL,
                                CAST(:payload AS JSONB))
                    """), {"id": mission_id, "workflow": workflow_run_id,
                            "scenario": scenario_id, "strategy": strategy_id, "created": now_dt,
                            "payload": json.dumps(row)})
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.mission_write_failed", error=str(exc))
        return row

    async def get_mission(self, mission_id: str) -> dict | None:
        return await self._get_json_row("missions", mission_id, self._missions)

    async def list_missions(self, scenario_id: str | None = None) -> list[dict]:
        if self.pg is not None:
            try:
                query = "SELECT payload FROM missions"
                params: dict[str, Any] = {}
                if scenario_id:
                    query += " WHERE scenario_id = :scenario_id"
                    params["scenario_id"] = scenario_id
                query += " ORDER BY created_at DESC"
                async with self.pg.connect() as conn:
                    rows = (await conn.execute(text(query), params)).scalars().all()
                    return [r if isinstance(r, dict) else json.loads(r) for r in rows]
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.mission_list_failed", error=str(exc))
        rows = list(self._missions.values())
        if scenario_id:
            rows = [row for row in rows if row.get("scenario_id") == scenario_id]
        return sorted(rows, key=lambda row: row.get("created_at", ""), reverse=True)

    async def get_latest_mission(self, scenario_id: str | None = None) -> dict | None:
        rows = await self.list_missions(scenario_id)
        return rows[0] if rows else None

    async def activate_mission(self, mission_id: str) -> dict | None:
        row = await self.get_mission(mission_id)
        if not row:
            return None
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        row.update({"status": "active", "activated_at": now})
        self._missions[mission_id] = row
        if self.pg is not None:
            try:
                async with self.pg.begin() as conn:
                    await conn.execute(text("""
                        UPDATE missions SET status='active', activated_at=:now,
                          payload=CAST(:payload AS JSONB) WHERE id=:id
                    """), {"id": mission_id, "now": now_dt, "payload": json.dumps(row)})
                    await conn.execute(text("""
                        INSERT INTO execution_audit(mission_id,action,occurred_at,payload)
                        VALUES (:id,'activated',:now,CAST(:payload AS JSONB))
                    """), {"id": mission_id, "now": now_dt,
                            "payload": json.dumps({"status": "active"})})
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.mission_activate_failed", error=str(exc))
        return row

    async def _get_json_row(self, table: str, row_id: str, fallback: dict) -> dict | None:
        if self.pg is not None and table in {"workflow_runs", "missions"}:
            try:
                async with self.pg.connect() as conn:
                    value = (await conn.execute(
                        text(f"SELECT payload FROM {table} WHERE id=:id"), {"id": row_id}
                    )).scalar_one_or_none()
                    if value is not None:
                        return value if isinstance(value, dict) else json.loads(value)
            except Exception as exc:  # noqa: BLE001
                log.warning("repository.row_read_failed", table=table, error=str(exc))
        return fallback.get(row_id)

    async def seed_ontology(self) -> None:
        if self.neo4j is None:
            return
        net = build_energy_network()
        try:
            async with self.neo4j.session() as session:
                for label in ("Country", "Supplier", "Corridor", "Port", "Refinery", "Reserve",
                              "Vessel", "Conflict", "WeatherEvent", "MarketSignal", "Sanction"):
                    await session.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                                      f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")
                for supplier in net.suppliers:
                    await session.run("""
                        MERGE (c:Country {id:$country_id}) SET c.name=$country
                        MERGE (s:Supplier {id:$id}) SET s.name=$country, s.grade=$grade,
                          s.import_share=$share, s.spare_capacity_kbpd=$spare,
                          s.lat=$lat, s.lon=$lon
                        MERGE (s)-[:LOCATED_IN]->(c)
                        WITH s
                        MATCH (co:Corridor {id:$corridor})
                        MERGE (s)-[:TRANSITS]->(co)
                    """, country_id=supplier.country.lower().replace(" ", "_"),
                        country=supplier.country, id=supplier.id, grade=supplier.grade.value,
                        share=supplier.import_share, spare=supplier.spare_capacity_kbpd,
                        lat=supplier.coords.lat, lon=supplier.coords.lon,
                        corridor=supplier.corridor_id)
                for corridor in net.corridors:
                    await session.run("""
                        MERGE (c:Corridor {id:$id}) SET c.name=$name, c.chokepoint=$chokepoint,
                          c.import_share=$share, c.status=$status
                    """, id=corridor.id, name=corridor.name, chokepoint=corridor.chokepoint,
                        share=corridor.import_share, status=corridor.status.value)
                # Run supplier relationships again now that all corridor nodes exist.
                for supplier in net.suppliers:
                    await session.run("""
                        MATCH (s:Supplier {id:$sid}), (c:Corridor {id:$cid})
                        MERGE (s)-[:TRANSITS]->(c)
                    """, sid=supplier.id, cid=supplier.corridor_id)
                for port in net.ports:
                    await session.run("""
                        MERGE (p:Port {id:$id}) SET p.name=$name, p.coast=$coast,
                          p.capacity_kbpd=$capacity, p.lat=$lat, p.lon=$lon
                    """, id=port.id, name=port.name, coast=port.coast.value,
                        capacity=port.crude_capacity_kbpd, lat=port.coords.lat, lon=port.coords.lon)
                for refinery in net.refineries:
                    await session.run("""
                        MERGE (r:Refinery {id:$id}) SET r.name=$name, r.operator=$operator,
                          r.grade=$grade, r.nameplate_kbpd=$capacity, r.lat=$lat, r.lon=$lon
                    """, id=refinery.id, name=refinery.name, operator=refinery.operator,
                        grade=refinery.preferred_grade.value, capacity=refinery.nameplate_kbpd,
                        lat=refinery.coords.lat, lon=refinery.coords.lon)
                    for port_id in refinery.port_ids:
                        await session.run("""
                            MATCH (p:Port {id:$pid}), (r:Refinery {id:$rid})
                            MERGE (p)-[:FEEDS]->(r)
                        """, pid=port_id, rid=refinery.id)
                # Shipping corridors terminate at appropriate crude terminals.
                for corridor in net.corridors:
                    target_ports = [p for p in net.ports
                                    if (corridor.id == "malacca" and p.coast.value == "east")
                                    or (corridor.id != "malacca" and p.coast.value == "west")]
                    for port in target_ports:
                        await session.run("""
                            MATCH (c:Corridor {id:$cid}), (p:Port {id:$pid})
                            MERGE (c)-[:ARRIVES_AT]->(p)
                        """, cid=corridor.id, pid=port.id)
                # Grade compatibility creates explainable supplier-to-refinery paths.
                for supplier in net.suppliers:
                    for refinery in net.refineries:
                        compatible = (refinery.preferred_grade == supplier.grade or
                                      supplier.grade.value == "medium_sour" or
                                      refinery.preferred_grade.value == "medium_sour")
                        if compatible:
                            await session.run("""
                                MATCH (s:Supplier {id:$sid}), (r:Refinery {id:$rid})
                                MERGE (s)-[:SUPPLIES {grade:$grade}]->(r)
                            """, sid=supplier.id, rid=refinery.id,
                                grade=supplier.grade.value)
                for reserve in net.reserves:
                    await session.run("""
                        MERGE (r:Reserve {id:$id}) SET r.name=$name, r.capacity_mmt=$capacity,
                          r.fill_pct=$fill, r.lat=$lat, r.lon=$lon
                    """, id=reserve.id, name=reserve.name, capacity=reserve.capacity_mmt,
                        fill=reserve.fill_pct, lat=reserve.coords.lat, lon=reserve.coords.lon)
                # -- Extended ontology: OilGrade, Pipeline, GovernmentAgency,
                #    EconomicIndicator, and richer relationships --
                for label in ("OilGrade", "Pipeline", "GovernmentAgency",
                              "EconomicIndicator"):
                    await session.run(
                        f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                        f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")
                # Oil grades
                for grade_id, grade_name in [
                    ("light_sweet", "Light Sweet Crude"),
                    ("medium_sour", "Medium Sour Crude"),
                    ("heavy_sour", "Heavy Sour Crude"),
                ]:
                    await session.run("""
                        MERGE (g:OilGrade {id:$id}) SET g.name=$name
                    """, id=grade_id, name=grade_name)
                # Supplier → PRODUCES_GRADE → OilGrade
                for supplier in net.suppliers:
                    await session.run("""
                        MATCH (s:Supplier {id:$sid}), (g:OilGrade {id:$gid})
                        MERGE (s)-[:PRODUCES_GRADE]->(g)
                    """, sid=supplier.id, gid=supplier.grade.value)
                # Refinery → USES_GRADE → OilGrade
                for refinery in net.refineries:
                    await session.run("""
                        MATCH (r:Refinery {id:$rid}), (g:OilGrade {id:$gid})
                        MERGE (r)-[:USES_GRADE]->(g)
                    """, rid=refinery.id, gid=refinery.preferred_grade.value)
                # Key pipelines
                pipelines = [
                    ("pipe_vadinar_panipat", "Vadinar–Panipat Pipeline", "vadinar",
                     "panipat_ref", 22.28, 69.72, 29.39, 76.97),
                    ("pipe_mumbai_mathura", "Mumbai–Mathura Pipeline", "mumbai",
                     "mathura_ref", 18.95, 72.85, 27.49, 77.67),
                    ("pipe_paradip_haldia", "Paradip–Haldia Pipeline", "paradip",
                     "haldia_ref", 20.27, 86.67, 22.03, 88.10),
                ]
                for pid, pname, port_id, ref_id, lat1, lon1, lat2, lon2 in pipelines:
                    await session.run("""
                        MERGE (pl:Pipeline {id:$id}) SET pl.name=$name,
                          pl.lat=$lat, pl.lon=$lon, pl.status='operational'
                    """, id=pid, name=pname, lat=lat1, lon=lon1)
                    await session.run("""
                        MATCH (p:Port {id:$pid}), (pl:Pipeline {id:$plid})
                        MERGE (p)-[:CONNECTED_VIA]->(pl)
                    """, pid=port_id, plid=pid)
                    await session.run("""
                        MATCH (pl:Pipeline {id:$plid}), (r:Refinery {id:$rid})
                        MERGE (pl)-[:FEEDS]->(r)
                    """, plid=pid, rid=ref_id)
                # Government agencies
                agencies = [
                    ("mopng", "Ministry of Petroleum & Natural Gas", "policy"),
                    ("iocl", "Indian Oil Corporation", "procurement"),
                    ("bpcl", "Bharat Petroleum", "procurement"),
                    ("hpcl", "Hindustan Petroleum", "procurement"),
                    ("isprl", "Indian Strategic Petroleum Reserves Ltd", "reserves"),
                    ("dgship", "Directorate General of Shipping", "maritime"),
                    ("mof", "Ministry of Finance", "economic"),
                ]
                for aid, aname, domain in agencies:
                    await session.run("""
                        MERGE (a:GovernmentAgency {id:$id})
                        SET a.name=$name, a.domain=$domain
                    """, id=aid, name=aname, domain=domain)
                # Agency → MONITORS → infrastructure
                await session.run("""
                    MATCH (a:GovernmentAgency {id:'isprl'}), (r:Reserve)
                    MERGE (a)-[:MONITORS]->(r)
                """)
                await session.run("""
                    MATCH (a:GovernmentAgency {id:'dgship'}), (c:Corridor)
                    MERGE (a)-[:MONITORS]->(c)
                """)
                # Country → IMPORTS_FROM → Supplier
                await session.run("""
                    MERGE (india:Country {id:'india'}) SET india.name='India'
                """)
                for supplier in net.suppliers:
                    await session.run("""
                        MATCH (india:Country {id:'india'}), (s:Supplier {id:$sid})
                        MERGE (india)-[:IMPORTS_FROM {share:$share}]->(s)
                    """, sid=supplier.id, share=supplier.import_share)
                # Refinery → DEPENDS_ON → Corridor (through port + corridor linkage)
                for refinery in net.refineries:
                    for port_id in refinery.port_ids:
                        port = next((p for p in net.ports if p.id == port_id), None)
                        if port:
                            for corridor in net.corridors:
                                is_connected = (
                                    (corridor.id == "malacca" and port.coast.value == "east")
                                    or (corridor.id != "malacca" and port.coast.value == "west")
                                )
                                if is_connected:
                                    await session.run("""
                                        MATCH (r:Refinery {id:$rid}), (c:Corridor {id:$cid})
                                        MERGE (r)-[:DEPENDS_ON]->(c)
                                    """, rid=refinery.id, cid=corridor.id)
                # Reserve → HAS_RESERVE → nearby port/refinery
                for reserve in net.reserves:
                    await session.run("""
                        MATCH (res:Reserve {id:$rid}), (n)
                        WHERE (n:Port OR n:Refinery) AND n.lat IS NOT NULL
                        WITH res, n, point.distance(
                          point({latitude:$lat, longitude:$lon}),
                          point({latitude:n.lat, longitude:n.lon})
                        ) AS dist ORDER BY dist LIMIT 2
                        MERGE (res)-[:NEAR_INFRASTRUCTURE {distance_km: round(dist/1000)}]->(n)
                    """, rid=reserve.id, lat=reserve.coords.lat, lon=reserve.coords.lon)
                # Economic indicators
                indicators = [
                    ("brent_price", "Brent Crude Price", "commodity", "USD/bbl"),
                    ("inr_usd", "INR/USD Exchange Rate", "fx", "INR"),
                    ("diesel_price", "Retail Diesel Price", "retail", "INR/L"),
                    ("cpi_inflation", "CPI Inflation Impact", "macro", "bps"),
                ]
                for ind_id, ind_name, ind_type, unit in indicators:
                    await session.run("""
                        MERGE (e:EconomicIndicator {id:$id})
                        SET e.name=$name, e.type=$type, e.unit=$unit
                    """, id=ind_id, name=ind_name, type=ind_type, unit=unit)
                log.info("repository.ontology_seeded", nodes="extended")
        except Exception as exc:  # noqa: BLE001
            log.warning("repository.ontology_seed_failed", error=str(exc))

    async def upsert_event_nodes(self, events: list[DomainEvent]) -> None:
        if self.neo4j is None:
            return
        labels = {
            "weather": "WeatherEvent", "sanctions": "Sanction",
            "market": "MarketSignal", "geopolitical": "Conflict",
            "shipping": "Conflict", "satellite": "WeatherEvent",
        }
        try:
            async with self.neo4j.session() as session:
                for event in events:
                    label = labels[event.category.value]
                    await session.run(f"""
                        MERGE (e:{label} {{id:$id}}) SET e.title=$title, e.risk=$risk,
                          e.severity=$severity, e.observed_at=$observed, e.source=$source,
                          e.provenance=$provenance, e.lat=$lat, e.lon=$lon
                    """, id=event.id, title=event.title, risk=event.risk_score,
                        severity=event.severity, observed=event.observed_at.isoformat(),
                        source=event.source, provenance=event.provenance.value,
                        lat=event.lat, lon=event.lon)
                    for corridor in event.affected_corridors:
                        await session.run(f"""
                            MATCH (e:{label} {{id:$eid}}), (c:Corridor {{id:$cid}})
                            MERGE (e)-[:AFFECTS]->(c)
                        """, eid=event.id, cid=corridor)
                    if event.lat is not None and event.lon is not None:
                        await session.run(f"""
                            MATCH (e:{label} {{id:$eid}}), (n)
                            WHERE (n:Port OR n:Refinery OR n:Reserve)
                              AND n.lat IS NOT NULL AND n.lon IS NOT NULL
                            WITH e, n, point.distance(
                              point({{latitude:$lat, longitude:$lon}}),
                              point({{latitude:n.lat, longitude:n.lon}})
                            ) AS metres ORDER BY metres ASC LIMIT 1
                            WHERE metres <= 250000
                            MERGE (e)-[r:OBSERVED_NEAR]->(n)
                            SET r.distance_km = round(metres / 1000)
                        """, eid=event.id, lat=event.lat, lon=event.lon)
        except Exception as exc:  # noqa: BLE001
            log.warning("repository.ontology_event_failed", error=str(exc))

    async def upsert_vessels(self, vessels: list[Any]) -> None:
        if self.neo4j is None:
            return
        try:
            async with self.neo4j.session() as session:
                for vessel in vessels[:200]:
                    await session.run("""
                        MERGE (v:Vessel {id:$id}) SET v.name=$name, v.kind=$kind,
                          v.lat=$lat, v.lon=$lon, v.heading=$heading,
                          v.speed_kn=$speed, v.provenance=$provenance
                    """, id=vessel.id, name=vessel.name, kind=vessel.kind,
                        lat=vessel.lat, lon=vessel.lon, heading=vessel.heading,
                        speed=vessel.speed_kn, provenance=vessel.source_kind.value)
                    if vessel.corridor_id:
                        await session.run("""
                            MATCH (v:Vessel {id:$vid}), (c:Corridor {id:$cid})
                            MERGE (v)-[:TRANSITS]->(c)
                        """, vid=vessel.id, cid=vessel.corridor_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("repository.ontology_vessel_failed", error=str(exc))


repositories = RepositoryHub()


def get_repositories() -> RepositoryHub:
    return repositories
