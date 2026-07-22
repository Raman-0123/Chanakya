"""Knowledge Graph endpoint — the entity-relationship network.

Builds a layered graph (suppliers → corridors → ports → refineries, plus SPR and
live events) from the digital twin so the frontend can render relationships with
React Flow. Node positions are computed here for a clean layered layout.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.domain import build_energy_network
from app.domain.entities import Coast
from app.ingestion import get_intelligence_service
from app.db import get_datastores

router = APIRouter(prefix="/graph", tags=["graph"])

_net = build_energy_network()

_LAYER_X = {"supplier": 0, "corridor": 320, "port": 640, "refinery": 960, "reserve": 640, "event": 0}
_Y_STEP = 92

_NEO_TYPES = {
    "Supplier": "supplier", "Corridor": "corridor", "Port": "port",
    "Refinery": "refinery", "Reserve": "reserve", "Conflict": "event",
    "WeatherEvent": "event", "MarketSignal": "event", "Sanction": "event",
    "Vessel": "vessel",
}


def _layout(items: list, layer: str, x_offset: int = 0) -> dict[str, dict]:
    n = len(items)
    positions = {}
    for i, key in enumerate(items):
        y = (i - (n - 1) / 2) * _Y_STEP
        positions[key] = {"x": _LAYER_X[layer] + x_offset, "y": y}
    return positions


@router.get("")
async def get_graph() -> dict:
    if get_datastores().neo4j_driver is not None:
        try:
            graph = await _neo4j_graph()
            if graph["nodes"]:
                return {**graph, "backend": "neo4j", "degraded": False,
                        "schema_version": "1.0"}
        except Exception:  # noqa: BLE001
            pass
    net = _net
    nodes: list[dict] = []
    edges: list[dict] = []

    sup_pos = _layout([s.id for s in net.suppliers], "supplier")
    corr_pos = _layout([c.id for c in net.corridors], "corridor")
    port_pos = _layout([p.id for p in net.ports], "port")
    ref_pos = _layout([r.id for r in net.refineries], "refinery")

    for s in net.suppliers:
        nodes.append({"id": f"sup:{s.id}", "type": "supplier", "label": s.country,
                      "position": sup_pos[s.id],
                      "meta": {"share": round(s.import_share * 100), "sanctioned": s.sanctioned,
                               "grade": s.grade.value}})
        edges.append({"id": f"e-{s.id}-{s.corridor_id}", "source": f"sup:{s.id}",
                      "target": f"cor:{s.corridor_id}", "label": "exports via"})

    west_ports = [p.id for p in net.ports if p.coast == Coast.WEST][:3]
    east_ports = [p.id for p in net.ports if p.coast == Coast.EAST][:2]
    for c in net.corridors:
        nodes.append({"id": f"cor:{c.id}", "type": "corridor", "label": c.name,
                      "position": corr_pos[c.id],
                      "meta": {"share": round(c.import_share * 100), "status": c.status.value,
                               "chokepoint": c.chokepoint}})
        targets = east_ports if c.id == "malacca" else west_ports
        for pid in targets:
            edges.append({"id": f"e-{c.id}-{pid}", "source": f"cor:{c.id}",
                          "target": f"port:{pid}", "label": "arrives"})

    for p in net.ports:
        nodes.append({"id": f"port:{p.id}", "type": "port", "label": p.name,
                      "position": port_pos[p.id],
                      "meta": {"coast": p.coast.value, "capacity": p.crude_capacity_kbpd}})

    for r in net.refineries:
        nodes.append({"id": f"ref:{r.id}", "type": "refinery", "label": r.name,
                      "position": ref_pos[r.id],
                      "meta": {"operator": r.operator, "utilization": r.utilization,
                               "nameplate": r.nameplate_kbpd}})
        for pid in r.port_ids:
            edges.append({"id": f"e-{pid}-{r.id}", "source": f"port:{pid}",
                          "target": f"ref:{r.id}", "label": "feeds"})

    # Strategic reserves attach near western ports
    for i, res in enumerate(net.reserves):
        nodes.append({"id": f"spr:{res.id}", "type": "reserve", "label": res.name,
                      "position": {"x": 800, "y": 300 + i * 80},
                      "meta": {"fill": res.fill_pct, "capacity": res.capacity_mmt}})

    # Live events linked to the corridors they threaten
    try:
        feed = await get_intelligence_service().feed()
        top_events = [e for e in feed.events if e.affected_corridors][:5]
        ev_pos = _layout([e.id for e in top_events], "event", x_offset=-40)
        for e in top_events:
            nodes.append({"id": f"ev:{e.id}", "type": "event", "label": e.title[:40],
                          "position": {"x": ev_pos[e.id]["x"], "y": ev_pos[e.id]["y"] - 360},
                          "meta": {"severity": e.severity, "risk": round(e.risk_score)}})
            for cid in e.affected_corridors:
                edges.append({"id": f"e-{e.id}-{cid}", "source": f"ev:{e.id}",
                              "target": f"cor:{cid}", "label": "threatens", "kind": "threat"})
    except Exception:  # noqa: BLE001
        pass

    return {"nodes": nodes, "edges": edges, "backend": "in_memory",
            "degraded": True, "schema_version": "1.0"}


async def _neo4j_graph() -> dict:
    driver = get_datastores().neo4j_driver
    labels = list(_NEO_TYPES)
    raw_nodes: list[dict] = []
    raw_edges: list[dict] = []
    async with driver.session() as session:
        result = await session.run("""
            MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels)
            RETURN labels(n)[0] AS label, properties(n) AS props LIMIT 250
        """, labels=labels)
        async for row in result:
            label, props = row["label"], dict(row["props"])
            if label in _NEO_TYPES and props.get("id"):
                raw_nodes.append({"label": label, "props": props})
        result = await session.run("""
            MATCH (a)-[r]->(b)
            WHERE any(label IN labels(a) WHERE label IN $labels)
              AND any(label IN labels(b) WHERE label IN $labels)
            RETURN a.id AS source, labels(a)[0] AS source_label, type(r) AS kind,
                   b.id AS target, labels(b)[0] AS target_label LIMIT 500
        """, labels=labels)
        async for row in result:
            raw_edges.append(dict(row))

    grouped: dict[str, list[dict]] = {}
    for item in raw_nodes:
        grouped.setdefault(_NEO_TYPES[item["label"]], []).append(item)
    layer_order = ["supplier", "event", "corridor", "port", "reserve", "refinery", "vessel"]
    x_by_type = {name: index * 260 for index, name in enumerate(layer_order)}
    nodes: list[dict] = []
    id_map: dict[tuple[str, str], str] = {}
    for node_type, items in grouped.items():
        for index, item in enumerate(items):
            props = item["props"]
            node_id = f"{node_type}:{props['id']}"
            id_map[(item["label"], props["id"])] = node_id
            meta = {k: v for k, v in props.items() if k not in {"id", "name", "title"}}
            nodes.append({
                "id": node_id, "type": node_type,
                "label": props.get("name") or props.get("title") or props["id"],
                "position": {"x": x_by_type.get(node_type, 0),
                             "y": (index - (len(items) - 1) / 2) * _Y_STEP},
                "meta": meta,
            })
    edges = []
    for index, edge in enumerate(raw_edges):
        source = id_map.get((edge["source_label"], edge["source"]))
        target = id_map.get((edge["target_label"], edge["target"]))
        if source and target:
            kind = edge["kind"].lower()
            edges.append({"id": f"neo-{index}-{source}-{target}", "source": source,
                          "target": target, "label": kind.replace("_", " "),
                          "kind": "threat" if edge["kind"] == "AFFECTS" else kind})
    return {"nodes": nodes, "edges": edges}
