"""Operational energy ontology API.

The ontology has two explicit layers:

* a versioned baseline model for suppliers, routes and Indian infrastructure;
* continuously ingested observations (events and AIS vessel positions).

Neo4j is the persistent graph backend.  When it is unavailable the same typed
graph and traversal semantics run in process, but every response says so.  The
fallback is never presented as a live/persistent graph store.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger
from app.db import get_datastores, get_repositories
from app.domain import build_energy_network
from app.domain.cascade import propagate_cascade

log = get_logger("api.ontology")
router = APIRouter(prefix="/ontology", tags=["ontology"])

_net = build_energy_network()
_SCHEMA_VERSION = "2.0"

_TYPE_ALIASES = {
    "sup": "supplier",
    "cor": "corridor",
    "ref": "refinery",
    "spr": "reserve",
    "ev": "event",
}
_NEO_TYPES = {
    "Supplier": "supplier",
    "Corridor": "corridor",
    "Port": "port",
    "Refinery": "refinery",
    "Reserve": "reserve",
    "Conflict": "event",
    "WeatherEvent": "event",
    "MarketSignal": "event",
    "Sanction": "event",
    "Vessel": "vessel",
    "DistributionHub": "demand",
    "Country": "country",
    "OilGrade": "grade",
    "Pipeline": "pipeline",
    "GovernmentAgency": "agency",
    "EconomicIndicator": "indicator",
}
_TRAVERSABLE_RELATIONSHIPS = (
    "TRANSITS|ARRIVES_AT|FEEDS|DISTRIBUTES_TO|AFFECTS|OBSERVED_NEAR|"
    "CAN_BRIDGE|REROUTES_TO|CONNECTED_VIA|PRODUCES_GRADE|USES_GRADE|MONITORS"
)
_PHYSICAL_PATH_RELATIONSHIPS = (
    "TRANSITS|ARRIVES_AT|FEEDS|DISTRIBUTES_TO|AFFECTS|OBSERVED_NEAR|"
    "CAN_BRIDGE|REROUTES_TO|CONNECTED_VIA"
)

_ONTOLOGY_SCHEMA = {
    "schema_version": _SCHEMA_VERSION,
    "identity": "Canonical IDs use <type>:<source-id>; aliases are normalized at the API boundary.",
    "node_types": [
        {"type": "supplier", "label": "Supplier", "prefix": "supplier", "temporal": False,
         "required": ["country", "import_share", "grade", "coordinates"]},
        {"type": "corridor", "label": "Shipping Corridor", "prefix": "corridor", "temporal": False,
         "required": ["chokepoint", "import_share", "status", "path"]},
        {"type": "port", "label": "Crude Terminal", "prefix": "port", "temporal": False,
         "required": ["capacity_kbpd", "status", "coordinates"]},
        {"type": "refinery", "label": "Refinery", "prefix": "refinery", "temporal": False,
         "required": ["operator", "nameplate_kbpd", "grade", "coordinates"]},
        {"type": "reserve", "label": "Strategic Reserve", "prefix": "reserve", "temporal": False,
         "required": ["capacity_mmt", "fill_pct", "coordinates"]},
        {"type": "demand", "label": "Demand Hub", "prefix": "demand", "temporal": False,
         "required": ["region", "demand_share", "sector_mix", "coordinates"]},
        {"type": "event", "label": "Observed Risk Event", "prefix": "event", "temporal": True,
         "required": ["source", "provenance", "observed_at", "risk_score"]},
        {"type": "vessel", "label": "AIS Vessel Observation", "prefix": "vessel", "temporal": True,
         "required": ["provenance", "last_seen_at", "coordinates"]},
    ],
    "relationship_types": [
        {"type": "TRANSITS", "from": ["supplier", "vessel"], "to": ["corridor"],
         "meaning": "Uses this shipping corridor"},
        {"type": "ARRIVES_AT", "from": ["corridor"], "to": ["port"],
         "meaning": "Route can terminate at this crude port"},
        {"type": "FEEDS", "from": ["port"], "to": ["refinery"],
         "meaning": "Port supplies crude to refinery"},
        {"type": "DISTRIBUTES_TO", "from": ["refinery"], "to": ["demand"],
         "meaning": "Refinery supplies products to demand hub"},
        {"type": "AFFECTS", "from": ["event"],
         "to": ["corridor", "port", "refinery", "reserve"],
         "meaning": "Source evidence explicitly maps event to entity"},
        {"type": "OBSERVED_NEAR", "from": ["event"],
         "to": ["corridor", "port", "refinery", "reserve"],
         "meaning": "Geospatial proximity relationship; not proof of causation"},
        {"type": "CAN_BRIDGE", "from": ["reserve"], "to": ["refinery"],
         "meaning": "Reserve is geographically positioned to bridge refinery supply"},
    ],
    "provenance_policy": {
        "baseline_model": "Versioned planning assumption; not a live observation.",
        "live": "Direct current source observation.",
        "cached": "Recently retrieved external observation.",
        "replay": "Historical/replayed observation.",
        "simulated": "Generated scenario datum.",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_id(value: str) -> str:
    value = value.strip()
    if ":" not in value:
        return value
    prefix, raw = value.split(":", 1)
    return f"{_TYPE_ALIASES.get(prefix.lower(), prefix.lower())}:{raw}"


def _raw_id(value: str) -> str:
    return _canonical_id(value).split(":", 1)[-1]


def _baseline_meta(**values: Any) -> dict:
    return {**values, "provenance": "baseline_model", "data_class": "planning_assumption"}


def _build_baseline_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for supplier in _net.suppliers:
        key = f"supplier:{supplier.id}"
        index[key] = {
            "id": key,
            "type": "supplier",
            "label": supplier.country,
            "meta": _baseline_meta(
                country=supplier.country,
                import_share=supplier.import_share,
                grade=supplier.grade.value,
                corridor_id=supplier.corridor_id,
                reliability=supplier.reliability,
                spare_capacity_kbpd=supplier.spare_capacity_kbpd,
                sanctioned=supplier.sanctioned,
                lat=supplier.coords.lat,
                lon=supplier.coords.lon,
            ),
        }
    for corridor in _net.corridors:
        key = f"corridor:{corridor.id}"
        index[key] = {
            "id": key,
            "type": "corridor",
            "label": corridor.name,
            "meta": _baseline_meta(
                chokepoint=corridor.chokepoint,
                import_share=corridor.import_share,
                status=corridor.status.value,
                base_transit_days=corridor.base_transit_days,
                reroute_corridor_id=corridor.reroute_corridor_id,
                path=[point.model_dump() for point in corridor.path],
                lat=corridor.chokepoint_coords.lat if corridor.chokepoint_coords else None,
                lon=corridor.chokepoint_coords.lon if corridor.chokepoint_coords else None,
            ),
        }
    for port in _net.ports:
        key = f"port:{port.id}"
        index[key] = {
            "id": key,
            "type": "port",
            "label": port.name,
            "meta": _baseline_meta(
                coast=port.coast.value,
                capacity_kbpd=port.crude_capacity_kbpd,
                status=port.status.value,
                lat=port.coords.lat,
                lon=port.coords.lon,
            ),
        }
    for refinery in _net.refineries:
        key = f"refinery:{refinery.id}"
        index[key] = {
            "id": key,
            "type": "refinery",
            "label": refinery.name,
            "meta": _baseline_meta(
                operator=refinery.operator,
                nameplate_kbpd=refinery.nameplate_kbpd,
                throughput_kbpd=refinery.throughput_kbpd,
                utilization=refinery.utilization,
                preferred_grade=refinery.preferred_grade.value,
                inventory_days=refinery.inventory_days,
                port_ids=refinery.port_ids,
                lat=refinery.coords.lat,
                lon=refinery.coords.lon,
            ),
        }
    for reserve in _net.reserves:
        key = f"reserve:{reserve.id}"
        index[key] = {
            "id": key,
            "type": "reserve",
            "label": reserve.name,
            "meta": _baseline_meta(
                capacity_mmt=reserve.capacity_mmt,
                fill_pct=reserve.fill_pct,
                stored_mmt=reserve.stored_mmt,
                lat=reserve.coords.lat,
                lon=reserve.coords.lon,
            ),
        }
    for center in _net.demand_centers:
        key = f"demand:{center.id}"
        index[key] = {
            "id": key,
            "type": "demand",
            "label": center.name,
            "meta": _baseline_meta(
                region=center.region,
                demand_share=center.demand_share,
                sector_mix=center.sector_mix,
                supplying_refinery_ids=center.supplying_refinery_ids,
                lat=center.coords.lat,
                lon=center.coords.lon,
            ),
        }
    return index


def _build_baseline_relationships() -> list[dict]:
    relationships: list[dict] = []
    for supplier in _net.suppliers:
        relationships.append({
            "source": f"supplier:{supplier.id}",
            "target": f"corridor:{supplier.corridor_id}",
            "label": "TRANSITS",
            "meta": {"provenance": "baseline_model"},
        })
    for corridor in _net.corridors:
        target_ports = [
            port for port in _net.ports
            if (corridor.id == "malacca" and port.coast.value == "east")
            or (corridor.id != "malacca" and port.coast.value == "west")
        ]
        for port in target_ports:
            relationships.append({
                "source": f"corridor:{corridor.id}",
                "target": f"port:{port.id}",
                "label": "ARRIVES_AT",
                "meta": {"provenance": "baseline_model"},
            })
    for refinery in _net.refineries:
        for port_id in refinery.port_ids:
            relationships.append({
                "source": f"port:{port_id}",
                "target": f"refinery:{refinery.id}",
                "label": "FEEDS",
                "meta": {"provenance": "baseline_model"},
            })
    for center in _net.demand_centers:
        for refinery_id in center.supplying_refinery_ids:
            relationships.append({
                "source": f"refinery:{refinery_id}",
                "target": f"demand:{center.id}",
                "label": "DISTRIBUTES_TO",
                "meta": {"provenance": "baseline_model"},
            })

    # A transparent geospatial bridge relation for reserve planning.  This is
    # proximity, not a claim about a dedicated physical pipeline.
    for reserve in _net.reserves:
        nearest = sorted(
            _net.refineries,
            key=lambda refinery: (
                (refinery.coords.lat - reserve.coords.lat) ** 2
                + (refinery.coords.lon - reserve.coords.lon) ** 2
            ),
        )[:2]
        for refinery in nearest:
            relationships.append({
                "source": f"reserve:{reserve.id}",
                "target": f"refinery:{refinery.id}",
                "label": "CAN_BRIDGE",
                "meta": {"basis": "nearest_two_refineries", "provenance": "baseline_model"},
            })
    return relationships


_BASELINE_INDEX = _build_baseline_index()
_BASELINE_RELATIONSHIPS = _build_baseline_relationships()


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _dedupe_relationships(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict] = []
    for row in rows:
        key = (row["source"], row["target"], row["label"])
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


async def _runtime_graph() -> tuple[dict[str, dict], list[dict], dict]:
    """Join the baseline ontology with currently ingested observations."""
    index = {key: {**value, "meta": dict(value["meta"])} for key, value in _BASELINE_INDEX.items()}
    relationships = [{**row, "meta": dict(row["meta"])} for row in _BASELINE_RELATIONSHIPS]
    repositories = get_repositories()
    events = await repositories.list_events(limit=150)
    vessels = await repositories.list_vessels(limit=250)

    for event in events:
        raw_id = str(event.get("id", "")).strip()
        if not raw_id:
            continue
        key = f"event:{raw_id}"
        provenance = str(event.get("provenance", "unavailable"))
        index[key] = {
            "id": key,
            "type": "event",
            "label": event.get("title") or raw_id,
            "meta": {
                "category": event.get("category"),
                "severity": event.get("severity"),
                "risk_score": event.get("risk_score"),
                "confidence": event.get("confidence"),
                "source": event.get("source"),
                "source_url": event.get("source_url"),
                "provenance": provenance,
                "observed_at": _iso(event.get("observed_at")),
                "ingested_at": _iso(event.get("ingested_at")),
                "freshness_seconds": event.get("freshness_seconds"),
                "lat": event.get("lat"),
                "lon": event.get("lon"),
                "affected_corridors": event.get("affected_corridors", []),
                "affected_entity_ids": event.get("affected_entity_ids", []),
            },
        }
        targets = [f"corridor:{corridor}" for corridor in event.get("affected_corridors", [])]
        targets.extend(_canonical_id(str(item)) for item in event.get("affected_entity_ids", []))
        for target in dict.fromkeys(targets):
            if target in index:
                relationships.append({
                    "source": key,
                    "target": target,
                    "label": "AFFECTS",
                    "meta": {
                        "provenance": provenance,
                        "observed_at": _iso(event.get("observed_at")),
                        "source": event.get("source"),
                    },
                })

    for vessel in vessels:
        raw_id = str(vessel.get("id", "")).strip()
        if not raw_id:
            continue
        key = f"vessel:{raw_id}"
        provenance = str(vessel.get("source_kind", "unavailable"))
        index[key] = {
            "id": key,
            "type": "vessel",
            "label": vessel.get("name") or raw_id,
            "meta": {
                "kind": vessel.get("kind"),
                "imo": vessel.get("imo"),
                "speed_kn": vessel.get("speed_kn"),
                "heading": vessel.get("heading"),
                "destination": vessel.get("destination_reported") or vessel.get("destination"),
                "lat": vessel.get("lat"),
                "lon": vessel.get("lon"),
                "provenance": provenance,
                "last_seen_at": _iso(vessel.get("last_seen_at")),
            },
        }
        corridor_id = vessel.get("corridor_id")
        target = f"corridor:{corridor_id}" if corridor_id else None
        if target and target in index:
            relationships.append({
                "source": key,
                "target": target,
                "label": "TRANSITS",
                "meta": {"provenance": provenance, "observed_at": _iso(vessel.get("last_seen_at"))},
            })

    observed = sum(1 for entity in index.values() if entity["type"] in {"event", "vessel"})
    runtime = {
        "baseline_entities": len(_BASELINE_INDEX),
        "observed_entities": observed,
        "event_entities": len(events),
        "vessel_entities": len(vessels),
        "generated_at": _utc_now(),
    }
    return index, _dedupe_relationships(relationships), runtime


def _resolve_id(value: str, index: dict[str, dict]) -> str | None:
    canonical = _canonical_id(value)
    if canonical in index:
        return canonical
    raw = _raw_id(canonical)
    matches = [key for key in index if key.split(":", 1)[-1] == raw]
    return matches[0] if len(matches) == 1 else None


def _neo4j_node_to_dict(node: Any) -> dict:
    props = dict(node) if hasattr(node, "__iter__") else {}
    labels = list(node.labels) if hasattr(node, "labels") else []
    node_type = next((_NEO_TYPES[label] for label in labels if label in _NEO_TYPES), "entity")
    raw_id = str(props.get("id", ""))
    return {
        "id": f"{node_type}:{raw_id}",
        "type": node_type,
        "label": props.get("name") or props.get("title") or raw_id,
        "neo4j_label": labels[0] if labels else "Unknown",
        "meta": {
            **{key: value for key, value in props.items() if key not in {"id", "name", "title"}},
            "provenance": props.get("provenance", "neo4j_persisted"),
        },
    }


def _neo4j_rel_to_dict(rel: Any) -> dict:
    start = _neo4j_node_to_dict(rel.start_node)
    end = _neo4j_node_to_dict(rel.end_node)
    return {
        "source": start["id"],
        "target": end["id"],
        "label": rel.type if hasattr(rel, "type") else "RELATED_TO",
        "meta": dict(rel) if hasattr(rel, "__iter__") else {},
    }


async def _neo4j_explore(entity_id: str, depth: int) -> dict | None:
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    query = f"""
        MATCH p=(center {{id: $id}})-[:{_TRAVERSABLE_RELATIONSHIPS}*0..{depth}]-(node)
        RETURN p LIMIT 160
    """
    try:
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        async with driver.session() as session:
            result = await session.run(query, id=_raw_id(entity_id))
            async for row in result:
                path = row["p"]
                for node in path.nodes:
                    item = _neo4j_node_to_dict(node)
                    nodes[item["id"]] = item
                edges.extend(_neo4j_rel_to_dict(rel) for rel in path.relationships)
        if not nodes:
            return None
        return {"nodes": list(nodes.values()), "edges": _dedupe_relationships(edges)}
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_explore_failed", error=str(exc))
        return None


def _step_for(entity: dict) -> dict:
    step_names = {
        "event": "trigger",
        "corridor": "corridor_exposure",
        "port": "terminal_exposure",
        "refinery": "refinery_impact",
        "demand": "demand_impact",
        "reserve": "reserve_response",
    }
    return {
        "id": entity["id"],
        "type": entity["type"],
        "label": entity["label"],
        "step": step_names.get(entity["type"], "related"),
    }


async def _neo4j_impact(event_id: str) -> dict | None:
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        paths: list[list[dict]] = []
        async with driver.session() as session:
            result = await session.run(f"""
                MATCH path=(event {{id: $id}})-[:AFFECTS|OBSERVED_NEAR|ARRIVES_AT|FEEDS|DISTRIBUTES_TO*1..5]->(target)
                WHERE target:Corridor OR target:Port OR target:Refinery OR target:DistributionHub OR target:Reserve
                RETURN path ORDER BY length(path) DESC LIMIT 100
            """, id=_raw_id(event_id))
            async for row in result:
                path = row["path"]
                converted = [_neo4j_node_to_dict(node) for node in path.nodes]
                for item in converted:
                    nodes[item["id"]] = item
                edges.extend(_neo4j_rel_to_dict(rel) for rel in path.relationships)
                paths.append([_step_for(item) for item in converted])
        if not paths:
            return None
        unique_paths: list[list[dict]] = []
        seen: set[tuple[str, ...]] = set()
        for path in paths:
            signature = tuple(step["id"] for step in path)
            if signature not in seen:
                seen.add(signature)
                unique_paths.append(path)
        return {
            "nodes": list(nodes.values()),
            "edges": _dedupe_relationships(edges),
            "paths": unique_paths,
            "chain": unique_paths[0],
            "exposures": [],
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_impact_failed", error=str(exc))
        return None


async def _neo4j_search(query: str, limit: int) -> list[dict] | None:
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        hits: list[dict] = []
        async with driver.session() as session:
            result = await session.run("""
                MATCH (node)
                WHERE toLower(coalesce(node.name, '')) CONTAINS $query
                   OR toLower(coalesce(node.title, '')) CONTAINS $query
                   OR toLower(coalesce(node.id, '')) CONTAINS $query
                RETURN node LIMIT $limit
            """, query=query.lower(), limit=limit)
            async for row in result:
                hits.append(_neo4j_node_to_dict(row["node"]))
        return hits
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_search_failed", error=str(exc))
        return None


async def _neo4j_stats() -> dict | None:
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        node_counts: dict[str, int] = {}
        relationship_counts: dict[str, int] = {}
        async with driver.session() as session:
            result = await session.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count")
            async for row in result:
                node_counts[row["label"] or "Unknown"] = row["count"]
            result = await session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count")
            async for row in result:
                relationship_counts[row["type"]] = row["count"]
        return {
            "node_counts": node_counts,
            "relationship_counts": relationship_counts,
            "total_nodes": sum(node_counts.values()),
            "total_relationships": sum(relationship_counts.values()),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_stats_failed", error=str(exc))
        return None


async def _neo4j_path(source: str, target: str, max_depth: int) -> dict | None:
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        async with driver.session() as session:
            result = await session.run(f"""
                MATCH (source {{id: $source}}), (target {{id: $target}})
                MATCH path=shortestPath((source)-[:{_PHYSICAL_PATH_RELATIONSHIPS}*..{max_depth}]-(target))
                RETURN path
            """, source=_raw_id(source), target=_raw_id(target))
            row = await result.single()
        if row is None:
            return None
        path = row["path"]
        nodes = [_neo4j_node_to_dict(node) for node in path.nodes]
        return {
            "nodes": nodes,
            "edges": [_neo4j_rel_to_dict(rel) for rel in path.relationships],
            "path": [_step_for(node) for node in nodes],
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_path_failed", error=str(exc))
        return None


@router.get("/schema")
async def ontology_schema() -> dict:
    """Return the machine-readable class and relationship contract."""
    return _ONTOLOGY_SCHEMA


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str) -> dict:
    """Return one entity with canonical identity and provenance."""
    neo4j_result = await _neo4j_explore(entity_id, 1)
    if neo4j_result:
        entity = next(
            (node for node in neo4j_result["nodes"]
             if _raw_id(node["id"]) == _raw_id(entity_id)),
            None,
        )
        if entity:
            inbound = sum(1 for row in neo4j_result["edges"] if row["target"] == entity["id"])
            outbound = sum(1 for row in neo4j_result["edges"] if row["source"] == entity["id"])
            return {
                "entity": entity,
                "degree": {"inbound": inbound, "outbound": outbound},
                "backend": "neo4j",
                "persistent": True,
                "schema_version": _SCHEMA_VERSION,
            }
    index, relationships, runtime = await _runtime_graph()
    resolved = _resolve_id(entity_id, index)
    if resolved is None:
        raise HTTPException(404, f"Ontology entity '{entity_id}' was not found")
    inbound = sum(1 for row in relationships if row["target"] == resolved)
    outbound = sum(1 for row in relationships if row["source"] == resolved)
    return {
        "entity": index[resolved],
        "degree": {"inbound": inbound, "outbound": outbound},
        "backend": "in_memory",
        "persistent": False,
        "runtime": runtime,
        "schema_version": _SCHEMA_VERSION,
    }


@router.get("/explore/{entity_id}")
async def explore_entity(
    entity_id: str,
    depth: int = Query(default=2, ge=1, le=3, description="Hop depth (1-3)"),
) -> dict:
    """Expand a typed neighborhood without inventing missing relationships."""
    canonical = _canonical_id(entity_id)
    neo4j_result = await _neo4j_explore(canonical, depth)
    if neo4j_result:
        return {
            **neo4j_result,
            "center": next((node["id"] for node in neo4j_result["nodes"]
                            if _raw_id(node["id"]) == _raw_id(canonical)), canonical),
            "depth": depth,
            "backend": "neo4j",
            "persistent": True,
            "degraded": False,
            "schema_version": _SCHEMA_VERSION,
        }

    index, relationships, runtime = await _runtime_graph()
    center = _resolve_id(canonical, index)
    if center is None:
        return {
            "nodes": [], "edges": [], "center": canonical, "depth": depth,
            "backend": "in_memory", "persistent": False, "degraded": True,
            "status": "not_found", "runtime": runtime, "schema_version": _SCHEMA_VERSION,
        }

    visited = {center}
    frontier = {center}
    result_edges: list[dict] = []
    for _ in range(depth):
        next_frontier: set[str] = set()
        for relationship in relationships:
            if relationship["source"] in frontier:
                next_frontier.add(relationship["target"])
                result_edges.append(relationship)
            if relationship["target"] in frontier:
                next_frontier.add(relationship["source"])
                result_edges.append(relationship)
        next_frontier -= visited
        visited |= next_frontier
        frontier = next_frontier
        if not frontier:
            break

    result_edges = [
        row for row in _dedupe_relationships(result_edges)
        if row["source"] in visited and row["target"] in visited
    ]
    return {
        "nodes": [index[key] for key in visited if key in index],
        "edges": result_edges,
        "center": center,
        "depth": depth,
        "backend": "in_memory",
        "persistent": False,
        "degraded": True,
        "status": "ok",
        "runtime": runtime,
        "schema_version": _SCHEMA_VERSION,
    }


def _directed_paths(
    start: str,
    index: dict[str, dict],
    relationships: list[dict],
    max_depth: int = 3,
) -> list[list[str]]:
    allowed = {"ARRIVES_AT", "FEEDS", "DISTRIBUTES_TO"}
    outgoing: dict[str, list[str]] = {}
    for row in relationships:
        if row["label"] in allowed:
            outgoing.setdefault(row["source"], []).append(row["target"])
    paths: list[list[str]] = []

    def walk(node: str, current: list[str], depth: int) -> None:
        targets = [target for target in outgoing.get(node, []) if target not in current]
        if depth >= max_depth or not targets:
            paths.append(current)
            return
        for target in targets:
            if target in index:
                walk(target, [*current, target], depth + 1)

    walk(start, [start], 0)
    return paths


@router.get("/impact/{event_id}")
async def impact_propagation(event_id: str) -> dict:
    """Trace separate causal paths from an observed event to downstream demand."""
    canonical = _canonical_id(event_id)
    if ":" not in canonical:
        canonical = f"event:{canonical}"
    neo4j_result = await _neo4j_impact(canonical)
    if neo4j_result:
        return {
            **neo4j_result, "event_id": _raw_id(canonical), "backend": "neo4j",
            "persistent": True, "degraded": False, "schema_version": _SCHEMA_VERSION,
        }

    index, relationships, runtime = await _runtime_graph()
    resolved = _resolve_id(canonical, index)
    event = index.get(resolved or "")
    if event is None or event["type"] != "event":
        return {
            "nodes": [], "edges": [], "paths": [], "chain": [], "exposures": [],
            "event_id": _raw_id(canonical), "status": "not_found",
            "message": "No ingested event with this ID; no impact path was inferred.",
            "backend": "in_memory", "persistent": False, "degraded": True,
            "runtime": runtime, "schema_version": _SCHEMA_VERSION,
        }

    event_id_resolved = event["id"]
    affect_edges = [
        row for row in relationships
        if row["source"] == event_id_resolved and row["label"] == "AFFECTS"
    ]
    graph_paths: list[list[dict]] = []
    used_edges = list(affect_edges)
    used_ids = {event_id_resolved}
    exposures: list[dict] = []
    for affect in affect_edges:
        affected_id = affect["target"]
        if affected_id.startswith("corridor:"):
            for node_path in _directed_paths(affected_id, index, relationships):
                full_path = [event_id_resolved, *node_path]
                graph_paths.append([_step_for(index[node_id]) for node_id in full_path])
                used_ids.update(full_path)
                for source, target in zip(node_path, node_path[1:]):
                    used_edges.extend(
                        row for row in relationships
                        if row["source"] == source and row["target"] == target
                    )
            for row in relationships:
                if row["label"] == "TRANSITS" and row["target"] == affected_id:
                    supplier = index.get(row["source"])
                    if supplier and supplier["type"] == "supplier":
                        exposures.append({
                            "id": supplier["id"],
                            "label": supplier["label"],
                            "import_share": supplier["meta"].get("import_share"),
                            "relationship": "TRANSITS",
                        })
                        used_ids.add(supplier["id"])
                        used_edges.append(row)
        elif affected_id in index:
            graph_paths.append([_step_for(event), _step_for(index[affected_id])])
            used_ids.add(affected_id)

    if not graph_paths:
        return {
            "nodes": [event], "edges": [], "paths": [], "chain": [], "exposures": [],
            "event_id": _raw_id(canonical), "status": "unresolved",
            "message": "The source event has no explicit ontology relationship; no corridor was guessed.",
            "backend": "in_memory", "persistent": False, "degraded": True,
            "runtime": runtime, "schema_version": _SCHEMA_VERSION,
        }

    return {
        "nodes": [index[key] for key in used_ids if key in index],
        "edges": _dedupe_relationships(used_edges),
        "paths": graph_paths,
        "chain": graph_paths[0],
        "exposures": exposures,
        "event_id": _raw_id(canonical),
        "status": "ok",
        "backend": "in_memory",
        "persistent": False,
        "degraded": True,
        "runtime": runtime,
        "schema_version": _SCHEMA_VERSION,
    }


@router.get("/path")
async def shortest_path(
    source: str = Query(..., min_length=1),
    target: str = Query(..., min_length=1),
    max_depth: int = Query(default=6, ge=1, le=10),
) -> dict:
    """Find the shortest explainable relationship path between two entities."""
    neo4j_result = await _neo4j_path(source, target, max_depth)
    if neo4j_result:
        return {
            **neo4j_result, "source": source, "target": target,
            "backend": "neo4j", "persistent": True, "degraded": False,
            "schema_version": _SCHEMA_VERSION,
        }

    index, relationships, runtime = await _runtime_graph()
    source_id = _resolve_id(source, index)
    target_id = _resolve_id(target, index)
    if source_id is None or target_id is None:
        raise HTTPException(404, "Source or target ontology entity was not found")
    adjacency: dict[str, list[tuple[str, dict]]] = {}
    for row in relationships:
        adjacency.setdefault(row["source"], []).append((row["target"], row))
        adjacency.setdefault(row["target"], []).append((row["source"], row))
    queue: deque[tuple[str, list[str], list[dict]]] = deque([(source_id, [source_id], [])])
    visited = {source_id}
    found_nodes: list[str] = []
    found_edges: list[dict] = []
    while queue:
        node_id, node_path, edge_path = queue.popleft()
        if node_id == target_id:
            found_nodes, found_edges = node_path, edge_path
            break
        if len(edge_path) >= max_depth:
            continue
        for neighbor, relationship in adjacency.get(node_id, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, [*node_path, neighbor], [*edge_path, relationship]))
    return {
        "nodes": [index[node_id] for node_id in found_nodes],
        "edges": found_edges,
        "path": [_step_for(index[node_id]) for node_id in found_nodes],
        "source": source_id,
        "target": target_id,
        "status": "ok" if found_nodes else "no_path",
        "backend": "in_memory",
        "persistent": False,
        "degraded": True,
        "runtime": runtime,
        "schema_version": _SCHEMA_VERSION,
    }


@router.get("/cascade/{node_id}")
async def cascade(
    node_id: str,
    block_fraction: float = Query(default=1.0, ge=0.0, le=1.0),
) -> dict:
    """Quantify a node outage through the deterministic energy model."""
    return propagate_cascade(_net, node_id, block_fraction).model_dump(mode="json")


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Search ontology identity, labels, attributes and source metadata."""
    neo4j_hits = await _neo4j_search(q, limit)
    if neo4j_hits is not None:
        return {
            "results": neo4j_hits, "query": q, "backend": "neo4j",
            "persistent": True, "degraded": False, "schema_version": _SCHEMA_VERSION,
        }
    index, _, runtime = await _runtime_graph()
    needle = q.lower()
    hits = [
        entity for entity in index.values()
        if needle in entity["id"].lower()
        or needle in entity["label"].lower()
        or needle in str(entity["meta"]).lower()
    ][:limit]
    return {
        "results": hits, "query": q, "backend": "in_memory",
        "persistent": False, "degraded": True, "runtime": runtime,
        "schema_version": _SCHEMA_VERSION,
    }


@router.get("/stats")
async def ontology_stats() -> dict:
    """Return class/relation counts and observed-vs-baseline composition."""
    neo4j_stats = await _neo4j_stats()
    if neo4j_stats is not None:
        return {
            **neo4j_stats, "backend": "neo4j", "persistent": True,
            "degraded": False, "schema_version": _SCHEMA_VERSION,
        }
    index, relationships, runtime = await _runtime_graph()
    node_counts: dict[str, int] = {}
    relationship_counts: dict[str, int] = {}
    for entity in index.values():
        node_counts[entity["type"]] = node_counts.get(entity["type"], 0) + 1
    for relationship in relationships:
        label = relationship["label"]
        relationship_counts[label] = relationship_counts.get(label, 0) + 1
    return {
        "node_counts": node_counts,
        "relationship_counts": relationship_counts,
        "total_nodes": len(index),
        "total_relationships": len(relationships),
        "backend": "in_memory",
        "persistent": False,
        "degraded": True,
        "runtime": runtime,
        "schema_version": _SCHEMA_VERSION,
    }
