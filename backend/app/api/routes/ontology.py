"""Ontology exploration API — interactive graph queries.

Provides endpoints for exploring the Neo4j ontology interactively:
entity neighborhood expansion, impact propagation chains, full-text
search, and schema statistics.  Every endpoint degrades gracefully
to the in-memory digital twin when Neo4j is unavailable.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.logging import get_logger
from app.db import get_datastores
from app.domain import build_energy_network
from app.domain.cascade import propagate_cascade

log = get_logger("api.ontology")
router = APIRouter(prefix="/ontology", tags=["ontology"])

_net = build_energy_network()

# ---- helpers for in-memory fallback ----

_ENTITY_INDEX: dict[str, dict] = {}


def _build_entity_index() -> dict[str, dict]:
    """Lazily build a searchable index from the seeded network."""
    if _ENTITY_INDEX:
        return _ENTITY_INDEX
    for s in _net.suppliers:
        _ENTITY_INDEX[f"supplier:{s.id}"] = {
            "id": f"supplier:{s.id}", "type": "supplier", "label": s.country,
            "meta": {"import_share": s.import_share, "grade": s.grade.value,
                     "corridor_id": s.corridor_id, "reliability": s.reliability,
                     "spare_capacity_kbpd": s.spare_capacity_kbpd,
                     "sanctioned": s.sanctioned, "lat": s.coords.lat, "lon": s.coords.lon},
        }
    for c in _net.corridors:
        _ENTITY_INDEX[f"corridor:{c.id}"] = {
            "id": f"corridor:{c.id}", "type": "corridor", "label": c.name,
            "meta": {"chokepoint": c.chokepoint, "import_share": c.import_share,
                     "status": c.status.value, "base_transit_days": c.base_transit_days,
                     "reroute_corridor_id": c.reroute_corridor_id},
        }
    for p in _net.ports:
        _ENTITY_INDEX[f"port:{p.id}"] = {
            "id": f"port:{p.id}", "type": "port", "label": p.name,
            "meta": {"coast": p.coast.value, "capacity_kbpd": p.crude_capacity_kbpd,
                     "status": p.status.value, "lat": p.coords.lat, "lon": p.coords.lon},
        }
    for r in _net.refineries:
        _ENTITY_INDEX[f"refinery:{r.id}"] = {
            "id": f"refinery:{r.id}", "type": "refinery", "label": r.name,
            "meta": {"operator": r.operator, "nameplate_kbpd": r.nameplate_kbpd,
                     "utilization": r.utilization, "preferred_grade": r.preferred_grade.value,
                     "inventory_days": r.inventory_days, "port_ids": r.port_ids,
                     "lat": r.coords.lat, "lon": r.coords.lon},
        }
    for res in _net.reserves:
        _ENTITY_INDEX[f"reserve:{res.id}"] = {
            "id": f"reserve:{res.id}", "type": "reserve", "label": res.name,
            "meta": {"capacity_mmt": res.capacity_mmt, "fill_pct": res.fill_pct,
                     "stored_mmt": res.stored_mmt, "lat": res.coords.lat, "lon": res.coords.lon},
        }
    return _ENTITY_INDEX


def _in_memory_relationships() -> list[dict]:
    """Build relationship list from the seed network."""
    rels: list[dict] = []
    for s in _net.suppliers:
        rels.append({"source": f"supplier:{s.id}", "target": f"corridor:{s.corridor_id}",
                     "label": "TRANSITS", "meta": {}})
    for c in _net.corridors:
        target_ports = [p for p in _net.ports
                        if (c.id == "malacca" and p.coast.value == "east")
                        or (c.id != "malacca" and p.coast.value == "west")]
        for p in target_ports:
            rels.append({"source": f"corridor:{c.id}", "target": f"port:{p.id}",
                         "label": "ARRIVES_AT", "meta": {}})
    for r in _net.refineries:
        for pid in r.port_ids:
            rels.append({"source": f"port:{pid}", "target": f"refinery:{r.id}",
                         "label": "FEEDS", "meta": {}})
    for s in _net.suppliers:
        for r in _net.refineries:
            compatible = (r.preferred_grade == s.grade or
                          s.grade.value == "medium_sour" or
                          r.preferred_grade.value == "medium_sour")
            if compatible:
                rels.append({"source": f"supplier:{s.id}", "target": f"refinery:{r.id}",
                             "label": "SUPPLIES", "meta": {"grade": s.grade.value}})
    return rels


# ---- Neo4j query helpers ----

async def _neo4j_explore(entity_id: str, depth: int) -> dict | None:
    """Query Neo4j for the N-hop neighborhood of an entity."""
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (center {id: $id})
                CALL apoc.path.subgraphAll(center, {maxLevel: $depth, limit: 100})
                YIELD nodes, relationships
                RETURN nodes, relationships
            """, id=entity_id, depth=depth)
            row = await result.single()
            if row is None:
                # Fall back to simpler query without APOC
                return await _neo4j_explore_simple(session, entity_id, depth)
            nodes = [_neo4j_node_to_dict(n) for n in row["nodes"]]
            edges = [_neo4j_rel_to_dict(r) for r in row["relationships"]]
            return {"nodes": nodes, "edges": edges, "backend": "neo4j"}
    except Exception:  # noqa: BLE001
        try:
            async with driver.session() as session:
                return await _neo4j_explore_simple(session, entity_id, depth)
        except Exception as exc:  # noqa: BLE001
            log.warning("ontology.neo4j_explore_failed", error=str(exc))
            return None


async def _neo4j_explore_simple(session, entity_id: str, depth: int) -> dict | None:
    """Simple multi-hop neighborhood query without APOC dependency."""
    if depth >= 2:
        query = """
            MATCH (center {id: $id})
            OPTIONAL MATCH (center)-[r1]-(n1)
            OPTIONAL MATCH (n1)-[r2]-(n2) WHERE n2 <> center
            WITH collect(DISTINCT center) + collect(DISTINCT n1) + collect(DISTINCT n2) AS allNodes,
                 collect(DISTINCT r1) + collect(DISTINCT r2) AS allRels
            UNWIND allNodes AS n
            WITH collect(DISTINCT n) AS nodes, allRels
            UNWIND allRels AS r
            RETURN nodes, collect(DISTINCT r) AS relationships
        """
    else:
        query = """
            MATCH (center {id: $id})
            OPTIONAL MATCH (center)-[r1]-(n1)
            WITH collect(DISTINCT center) + collect(DISTINCT n1) AS nodes,
                 collect(DISTINCT r1) AS relationships
            RETURN nodes, relationships
        """
    result = await session.run(query, id=entity_id)
    row = await result.single()
    if row is None:
        return None
    nodes_raw = [n for n in (row["nodes"] or []) if n is not None]
    rels_raw = [r for r in (row["relationships"] or []) if r is not None]
    nodes = [_neo4j_node_to_dict(n) for n in nodes_raw]
    edges = [_neo4j_rel_to_dict(r) for r in rels_raw]
    return {"nodes": nodes, "edges": edges, "backend": "neo4j"}


async def _neo4j_impact_chain(event_id: str) -> dict | None:
    """Trace impact from an event through corridors → ports → refineries."""
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (event {id: $id})
                OPTIONAL MATCH path = (event)-[:AFFECTS|OBSERVED_NEAR*1..4]-(target)
                WITH event, collect(DISTINCT nodes(path)) AS pathNodes,
                     collect(DISTINCT relationships(path)) AS pathRels
                UNWIND pathNodes AS nodeList
                UNWIND nodeList AS n
                WITH event, collect(DISTINCT n) AS allNodes, pathRels
                UNWIND pathRels AS relList
                UNWIND relList AS r
                RETURN [event] + allNodes AS nodes, collect(DISTINCT r) AS relationships
            """, id=event_id)
            row = await result.single()
            if row is None:
                return None
            nodes = [_neo4j_node_to_dict(n) for n in (row["nodes"] or []) if n is not None]
            edges = [_neo4j_rel_to_dict(r) for r in (row["relationships"] or []) if r is not None]
            # Build ordered chain description
            chain: list[dict] = []
            for node in nodes:
                chain.append({"id": node["id"], "type": node["type"], "label": node["label"]})
            return {"nodes": nodes, "edges": edges, "chain": chain, "backend": "neo4j"}
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_impact_failed", error=str(exc))
        return None


async def _neo4j_search(query: str, limit: int) -> list[dict] | None:
    """Full-text search across Neo4j entities."""
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        async with driver.session() as session:
            # Use property matching as a universal fallback
            result = await session.run("""
                MATCH (n)
                WHERE n.name CONTAINS $q OR n.title CONTAINS $q OR n.id CONTAINS $q
                RETURN labels(n)[0] AS label, properties(n) AS props
                LIMIT $limit
            """, q=query, limit=limit)
            hits: list[dict] = []
            async for row in result:
                props = dict(row["props"])
                node_label = row["label"] or "Unknown"
                type_map = {"Supplier": "supplier", "Corridor": "corridor", "Port": "port",
                            "Refinery": "refinery", "Reserve": "reserve", "Conflict": "event",
                            "WeatherEvent": "event", "Vessel": "vessel", "Country": "country",
                            "OilGrade": "grade", "Pipeline": "pipeline",
                            "GovernmentAgency": "agency", "EconomicIndicator": "indicator",
                            "MarketSignal": "event", "Sanction": "event"}
                hits.append({
                    "id": f"{type_map.get(node_label, 'entity')}:{props.get('id', '')}",
                    "type": type_map.get(node_label, "entity"),
                    "label": props.get("name") or props.get("title") or props.get("id", ""),
                    "neo4j_label": node_label,
                    "meta": {k: v for k, v in props.items() if k not in {"id", "name", "title"}},
                })
            return hits
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_search_failed", error=str(exc))
        return None


async def _neo4j_stats() -> dict | None:
    """Schema statistics from Neo4j."""
    driver = get_datastores().neo4j_driver
    if driver is None:
        return None
    try:
        async with driver.session() as session:
            result = await session.run("""
                MATCH (n)
                WITH labels(n)[0] AS label, count(*) AS cnt
                RETURN label, cnt ORDER BY cnt DESC
            """)
            node_counts: dict[str, int] = {}
            total_nodes = 0
            async for row in result:
                node_counts[row["label"]] = row["cnt"]
                total_nodes += row["cnt"]
            result = await session.run("""
                MATCH ()-[r]->()
                WITH type(r) AS kind, count(*) AS cnt
                RETURN kind, cnt ORDER BY cnt DESC
            """)
            rel_counts: dict[str, int] = {}
            total_rels = 0
            async for row in result:
                rel_counts[row["kind"]] = row["cnt"]
                total_rels += row["cnt"]
            return {"node_counts": node_counts, "relationship_counts": rel_counts,
                    "total_nodes": total_nodes, "total_relationships": total_rels,
                    "backend": "neo4j"}
    except Exception as exc:  # noqa: BLE001
        log.warning("ontology.neo4j_stats_failed", error=str(exc))
        return None


def _neo4j_node_to_dict(node) -> dict:
    """Convert a Neo4j node to a serializable dict."""
    props = dict(node) if hasattr(node, "__iter__") else {}
    labels = list(node.labels) if hasattr(node, "labels") else []
    type_map = {"Supplier": "supplier", "Corridor": "corridor", "Port": "port",
                "Refinery": "refinery", "Reserve": "reserve", "Conflict": "event",
                "WeatherEvent": "event", "Vessel": "vessel", "Country": "country",
                "OilGrade": "grade", "Pipeline": "pipeline",
                "GovernmentAgency": "agency", "EconomicIndicator": "indicator",
                "MarketSignal": "event", "Sanction": "event"}
    node_type = "entity"
    for label in labels:
        if label in type_map:
            node_type = type_map[label]
            break
    return {
        "id": f"{node_type}:{props.get('id', '')}",
        "type": node_type,
        "label": props.get("name") or props.get("title") or props.get("id", ""),
        "neo4j_label": labels[0] if labels else "Unknown",
        "meta": {k: v for k, v in props.items() if k not in {"id", "name", "title"}},
    }


def _neo4j_rel_to_dict(rel) -> dict:
    """Convert a Neo4j relationship to a serializable dict."""
    start_props = dict(rel.start_node) if hasattr(rel, "start_node") else {}
    end_props = dict(rel.end_node) if hasattr(rel, "end_node") else {}
    start_labels = list(rel.start_node.labels) if hasattr(rel.start_node, "labels") else []
    end_labels = list(rel.end_node.labels) if hasattr(rel.end_node, "labels") else []
    type_map = {"Supplier": "supplier", "Corridor": "corridor", "Port": "port",
                "Refinery": "refinery", "Reserve": "reserve", "Conflict": "event",
                "WeatherEvent": "event", "Vessel": "vessel", "Country": "country",
                "OilGrade": "grade", "Pipeline": "pipeline",
                "GovernmentAgency": "agency", "EconomicIndicator": "indicator",
                "MarketSignal": "event", "Sanction": "event"}
    source_type = next((type_map[l] for l in start_labels if l in type_map), "entity")
    target_type = next((type_map[l] for l in end_labels if l in type_map), "entity")
    return {
        "source": f"{source_type}:{start_props.get('id', '')}",
        "target": f"{target_type}:{end_props.get('id', '')}",
        "label": rel.type if hasattr(rel, "type") else "RELATED_TO",
        "meta": dict(rel) if hasattr(rel, "__iter__") else {},
    }


# ---- Endpoints ----

@router.get("/explore/{entity_id}")
async def explore_entity(
    entity_id: str,
    depth: int = Query(default=2, ge=1, le=3, description="Hop depth (1-3)"),
) -> dict:
    """Return the N-hop neighborhood of an entity in the ontology graph."""
    # Try Neo4j first
    neo_result = await _neo4j_explore(entity_id, depth)
    if neo_result and neo_result.get("nodes"):
        return {**neo_result, "center": entity_id, "depth": depth, "degraded": False}

    # In-memory fallback
    index = _build_entity_index()
    rels = _in_memory_relationships()
    visited: set[str] = set()
    frontier: set[str] = {entity_id}
    result_nodes: list[dict] = []
    result_edges: list[dict] = []

    # Also try matching with type prefix
    if entity_id not in index:
        for key in index:
            if key.endswith(f":{entity_id}"):
                entity_id = key
                frontier = {entity_id}
                break

    for _ in range(depth):
        next_frontier: set[str] = set()
        for node_id in frontier:
            if node_id in visited:
                continue
            visited.add(node_id)
            if node_id in index:
                result_nodes.append(index[node_id])
            for rel in rels:
                if rel["source"] == node_id and rel["target"] not in visited:
                    next_frontier.add(rel["target"])
                    result_edges.append(rel)
                elif rel["target"] == node_id and rel["source"] not in visited:
                    next_frontier.add(rel["source"])
                    result_edges.append(rel)
        frontier = next_frontier

    # Add remaining frontier nodes
    for node_id in frontier:
        if node_id in index and node_id not in visited:
            result_nodes.append(index[node_id])

    return {"nodes": result_nodes, "edges": result_edges,
            "center": entity_id, "depth": depth,
            "backend": "in_memory", "degraded": True}


@router.get("/impact/{event_id}")
async def impact_propagation(event_id: str) -> dict:
    """Trace the impact chain from an event through the ontology.

    Example: Conflict near Hormuz → AFFECTS → Corridor:hormuz → ARRIVES_AT
    → Port:vadinar → FEEDS → Refinery:jamnagar → affects diesel production.

    This is the "Iran drills → Hormuz → Shipping → Refineries → Diesel" chain.
    """
    # Try Neo4j
    neo_result = await _neo4j_impact_chain(event_id)
    if neo_result and neo_result.get("nodes"):
        return {**neo_result, "event_id": event_id, "degraded": False}

    # In-memory fallback: simulate an impact chain for a corridor-based event
    index = _build_entity_index()
    chain: list[dict] = []
    nodes: list[dict] = []
    edges: list[dict] = []

    # Determine which corridor is affected
    affected_corridor_id = None
    for c in _net.corridors:
        if c.id in event_id.lower() or event_id.lower() in c.id:
            affected_corridor_id = c.id
            break
    if not affected_corridor_id:
        # Default to first corridor for demo
        affected_corridor_id = _net.corridors[0].id if _net.corridors else None

    if affected_corridor_id:
        # Build the impact chain: Event → Corridor → Ports → Refineries
        event_node = {"id": f"event:{event_id}", "type": "event",
                      "label": f"Disruption Event", "meta": {"event_id": event_id}}
        nodes.append(event_node)
        chain.append({"id": event_node["id"], "type": "event",
                       "label": event_node["label"], "step": "trigger"})

        corridor_key = f"corridor:{affected_corridor_id}"
        if corridor_key in index:
            nodes.append(index[corridor_key])
            edges.append({"source": event_node["id"], "target": corridor_key,
                          "label": "AFFECTS", "meta": {}})
            chain.append({"id": corridor_key, "type": "corridor",
                           "label": index[corridor_key]["label"], "step": "corridor_disrupted"})

            # Find affected ports
            c = next((c for c in _net.corridors if c.id == affected_corridor_id), None)
            if c:
                target_ports = [p for p in _net.ports
                                if (c.id == "malacca" and p.coast.value == "east")
                                or (c.id != "malacca" and p.coast.value == "west")]
                for port in target_ports[:3]:
                    port_key = f"port:{port.id}"
                    if port_key in index:
                        nodes.append(index[port_key])
                        edges.append({"source": corridor_key, "target": port_key,
                                      "label": "ARRIVES_AT", "meta": {}})
                        chain.append({"id": port_key, "type": "port",
                                       "label": port.name, "step": "port_affected"})

                        # Find refineries fed by this port
                        for ref in _net.refineries:
                            if port.id in ref.port_ids:
                                ref_key = f"refinery:{ref.id}"
                                if ref_key in index and ref_key not in [n["id"] for n in nodes]:
                                    nodes.append(index[ref_key])
                                    edges.append({"source": port_key, "target": ref_key,
                                                  "label": "FEEDS", "meta": {}})
                                    chain.append({"id": ref_key, "type": "refinery",
                                                   "label": ref.name,
                                                   "step": "production_affected"})

        # Add affected suppliers
        for s in _net.suppliers:
            if s.corridor_id == affected_corridor_id:
                sup_key = f"supplier:{s.id}"
                if sup_key in index:
                    nodes.append(index[sup_key])
                    edges.append({"source": sup_key, "target": corridor_key,
                                  "label": "TRANSITS", "meta": {}})
                    chain.append({"id": sup_key, "type": "supplier",
                                   "label": s.country, "step": "supply_disrupted"})

    return {"nodes": nodes, "edges": edges, "chain": chain,
            "event_id": event_id, "backend": "in_memory", "degraded": True}


@router.get("/cascade/{node_id}")
async def cascade(
    node_id: str,
    block_fraction: float = Query(default=1.0, ge=0.0, le=1.0,
                                  description="How much of the node to block (0–1)"),
) -> dict:
    """Quantified cascade: block a node and propagate magnitude downstream.

    Accepts a port / corridor / supplier / refinery id (bare or type-prefixed,
    e.g. `port:vadinar` or `vadinar`). Returns per-node crude shortfall,
    utilisation drops, isolated nodes, SPR bridge days and the national macro
    projection — the "if this part of the port is blocked, what happens to
    everything else" view.
    """
    return propagate_cascade(_net, node_id, block_fraction).model_dump(mode="json")


@router.get("/search")
async def search_entities(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Search across all ontology entities by name, ID, or attributes."""
    # Try Neo4j
    neo_hits = await _neo4j_search(q, limit)
    if neo_hits is not None:
        return {"results": neo_hits, "query": q, "backend": "neo4j", "degraded": False}

    # In-memory fallback
    index = _build_entity_index()
    q_lower = q.lower()
    hits: list[dict] = []
    for entity in index.values():
        label = entity.get("label", "").lower()
        eid = entity.get("id", "").lower()
        meta_str = str(entity.get("meta", {})).lower()
        if q_lower in label or q_lower in eid or q_lower in meta_str:
            hits.append(entity)
            if len(hits) >= limit:
                break
    return {"results": hits, "query": q, "backend": "in_memory", "degraded": True}


@router.get("/stats")
async def ontology_stats() -> dict:
    """Schema summary with node and relationship counts."""
    # Try Neo4j
    neo_stats = await _neo4j_stats()
    if neo_stats is not None:
        return {**neo_stats, "degraded": False}

    # In-memory fallback
    index = _build_entity_index()
    rels = _in_memory_relationships()
    node_counts: dict[str, int] = {}
    for entity in index.values():
        t = entity.get("type", "unknown")
        node_counts[t] = node_counts.get(t, 0) + 1
    rel_counts: dict[str, int] = {}
    for rel in rels:
        label = rel.get("label", "RELATED")
        rel_counts[label] = rel_counts.get(label, 0) + 1
    return {"node_counts": node_counts, "relationship_counts": rel_counts,
            "total_nodes": len(index), "total_relationships": len(rels),
            "backend": "in_memory", "degraded": True}
