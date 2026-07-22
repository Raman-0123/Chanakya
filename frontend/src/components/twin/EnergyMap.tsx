"use client";

import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from "react-leaflet";
import type {
  CorridorOperationalState, GeoStation, IntelEvent, NetworkData, SatelliteLayer, Vessel,
} from "@/lib/types";
import { SEVERITY_META } from "@/lib/severity";
import { cn } from "@/lib/utils";

const CASCADE_COLOR: Record<string, string> = {
  offline: "#ef4444",
  critical: "#f97316",
  strained: "#eab308",
  high: "#f97316",
  elevated: "#eab308",
  nominal: "#10b981",
};

export interface TwinSelection {
  kind: "refinery" | "port" | "supplier" | "reserve" | "corridor" | "demand";
  id: string;
}

export type MapMode = "operations" | "satellite";

const STATUS_COLOR: Record<string, string> = {
  operational: "#10b981",
  strained: "#eab308",
  disrupted: "#f97316",
  offline: "#ef4444",
};

function utilColor(u: number): string {
  if (u >= 92) return "#10b981";
  if (u >= 80) return "#eab308";
  if (u >= 60) return "#f97316";
  return "#ef4444";
}

export default function EnergyMap({
  network,
  vessels,
  events,
  mapMode,
  scenarioId,
  satelliteLayers,
  baseLayerId,
  overlayIds,
  impacted,
  stations,
  corridorStates,
  onSelect,
}: {
  network: NetworkData;
  vessels: Vessel[];
  events: IntelEvent[];
  mapMode: MapMode;
  scenarioId?: string;
  satelliteLayers?: SatelliteLayer[];
  baseLayerId?: string;
  overlayIds?: string[];
  impacted?: Record<string, string>;
  stations?: GeoStation[];
  corridorStates?: CorridorOperationalState[];
  onSelect: (sel: TwinSelection) => void;
}) {
  const mappableEvents = events.filter((event) => event.lat !== null && event.lon !== null);
  const corridorState = new Map((corridorStates ?? []).map((row) => [row.corridor_id, row]));
  const portStation = new Map(
    (stations ?? []).filter((station) => station.kind === "port")
      .map((station) => [station.affected_entity_ids[0]?.replace("port:", ""), station]),
  );
  const bases = (satelliteLayers ?? []).filter((l) => l.kind === "base");
  const gibsBase = bases.find((l) => l.id === baseLayerId) ?? bases[0];
  const gibsOverlays = (satelliteLayers ?? []).filter(
    (l) => l.kind === "overlay" && (overlayIds ?? []).includes(l.id),
  );
  // 1×1 transparent tile so empty GIBS overlay tiles (404) don't show broken icons
  const BLANK_TILE =
    "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

  return (
    <MapContainer
      center={[16, 66]}
      zoom={4}
      minZoom={3}
      maxZoom={12}
      className={cn("h-full w-full bg-canvas", mapMode === "operations" && "map-tactical-filter")}
      worldCopyJump
      attributionControl={false}
    >
      {mapMode === "satellite" ? (
        gibsBase ? (
          <>
            {/* NASA GIBS daily true-colour imagery (keyless) */}
            <TileLayer
              key={`gibs-${gibsBase.id}`}
              url={gibsBase.url_template}
              maxNativeZoom={gibsBase.max_native_zoom}
              maxZoom={12}
              tileSize={256}
              className="satellite-imagery"
            />
            {gibsOverlays.map((layer) => (
              <TileLayer
                key={`gibs-ov-${layer.id}`}
                url={layer.url_template}
                maxNativeZoom={layer.max_native_zoom}
                maxZoom={12}
                tileSize={256}
                opacity={0.85}
                errorTileUrl={BLANK_TILE}
              />
            ))}
          </>
        ) : (
          <TileLayer
            key="satellite"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            className="satellite-imagery"
          />
        )
      ) : (
        <TileLayer
          key="operations"
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
        />
      )}

      {/* Shipping corridors */}
      {network.corridors.map((c) =>
        c.path.length >= 2 ? (
          <Polyline
            key={c.id}
            positions={c.path.map((p) => [p.lat, p.lon]) as [number, number][]}
            pathOptions={{
              color: corridorState.get(c.id)
                ? CASCADE_COLOR[corridorState.get(c.id)!.band] ?? "#22d3ee"
                : STATUS_COLOR[c.status] ?? "#22d3ee",
              weight: 1.5 + c.import_share * 6,
              opacity: 0.55,
              dashArray: c.status === "operational" ? undefined : "6 6",
            }}
            eventHandlers={{ click: () => onSelect({ kind: "corridor", id: c.id }) }}
          >
            <Tooltip sticky>
              {c.name} · {(c.import_share * 100).toFixed(0)}% of imports
              {corridorState.get(c.id) && (
                <><br />Disruption probability {corridorState.get(c.id)!.disruption_probability.toFixed(1)}%</>
              )}
            </Tooltip>
          </Polyline>
        ) : null,
      )}

      {/* Suppliers */}
      {network.suppliers.map((s) => (
        <CircleMarker
          key={s.id}
          center={[s.coords.lat, s.coords.lon]}
          radius={4 + s.import_share * 22}
          pathOptions={{
            color: s.sanctioned ? "#ef4444" : "#f59e0b",
            fillColor: s.sanctioned ? "#ef4444" : "#f59e0b",
            fillOpacity: 0.25,
            weight: 1,
          }}
          eventHandlers={{ click: () => onSelect({ kind: "supplier", id: s.id }) }}
        >
          <Tooltip>{s.country} · {(s.import_share * 100).toFixed(0)}%</Tooltip>
        </CircleMarker>
      ))}

      {/* Ports */}
      {network.ports.map((p) => {
        const station = portStation.get(p.id);
        const color = station ? CASCADE_COLOR[station.status] ?? "#22d3ee" : "#22d3ee";
        return (
        <CircleMarker
          key={p.id}
          center={[p.coords.lat, p.coords.lon]}
          radius={4}
          pathOptions={{ color, fillColor: color, fillOpacity: 0.6, weight: station?.status === "high" || station?.status === "critical" ? 3 : 1 }}
          eventHandlers={{ click: () => onSelect({ kind: "port", id: p.id }) }}
        >
          <Tooltip>{p.name}{station ? ` · ${station.status.toUpperCase()}` : ""}</Tooltip>
        </CircleMarker>
        );
      })}

      {/* Provenance-bearing geospatial monitoring stations. */}
      {(stations ?? []).filter((station) => station.kind === "weather" || station.kind === "chokepoint")
        .map((station) => {
          const color = CASCADE_COLOR[station.status] ?? "#8aa0bf";
          return (
            <CircleMarker
              key={station.id}
              center={[station.lat, station.lon]}
              radius={station.kind === "chokepoint" ? 11 : 7}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: station.provenance === "live" ? 0.24 : 0.08,
                weight: 2,
                dashArray: station.provenance === "live" ? undefined : "3 4",
              }}
            >
              <Tooltip sticky>
                {station.kind.toUpperCase()} STATION · {station.provenance.toUpperCase()}
                <br />{station.name} · risk {station.risk_score.toFixed(0)}
                {Object.entries(station.metrics).slice(0, 3).map(([key, value]) => (
                  <span key={key}><br />{key.replaceAll("_", " ")}: {String(value ?? "—")}</span>
                ))}
              </Tooltip>
            </CircleMarker>
          );
        })}

      {/* Refineries — sized by capacity, colored by utilisation (or cascade impact) */}
      {network.refineries.map((r) => {
        const hit = impacted?.[r.id];
        const color = hit ? CASCADE_COLOR[hit] ?? "#ef4444" : utilColor(r.utilization);
        return (
          <CircleMarker
            key={r.id}
            center={[r.coords.lat, r.coords.lon]}
            radius={5 + (r.nameplate_kbpd / 1240) * 9}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: hit ? 0.6 : 0.35,
              weight: hit ? 3 : 1.5,
              className: hit === "offline" || hit === "critical" ? "animate-pulse" : undefined,
            }}
            eventHandlers={{ click: () => onSelect({ kind: "refinery", id: r.id }) }}
          >
            <Tooltip>
              {r.name} · {r.nameplate_kbpd} kbpd · {r.utilization}%
              {hit ? ` · CASCADE: ${hit.toUpperCase()}` : ""}
            </Tooltip>
          </CircleMarker>
        );
      })}

      {/* Strategic reserves */}
      {network.reserves.map((s) => (
        <CircleMarker
          key={s.id}
          center={[s.coords.lat, s.coords.lon]}
          radius={7}
          pathOptions={{ color: "#6366f1", fillColor: "#6366f1", fillOpacity: 0.4, weight: 2 }}
          eventHandlers={{ click: () => onSelect({ kind: "reserve", id: s.id }) }}
        >
          <Tooltip>{s.name} · {s.fill_pct}% full</Tooltip>
        </CircleMarker>
      ))}

      {/* Downstream product-demand hubs complete the wellhead→consumer twin. */}
      {network.demand_centers.map((center) => (
        <CircleMarker
          key={center.id}
          center={[center.coords.lat, center.coords.lon]}
          radius={4 + center.demand_share * 16}
          pathOptions={{ color: "#a78bfa", fillColor: "#a78bfa", fillOpacity: 0.18, weight: 1.5 }}
          eventHandlers={{ click: () => onSelect({ kind: "demand", id: center.id }) }}
        >
          <Tooltip>{center.name} · {(center.demand_share * 100).toFixed(0)}% product demand</Tooltip>
        </CircleMarker>
      ))}

      {/* Vessel wake tracks */}
      {vessels.map((v) =>
        v.track && v.track.length >= 2 ? (
          <Polyline
            key={`wake-${v.id}`}
            positions={v.track as [number, number][]}
            pathOptions={{
              color: v.speed_kn === 0 ? "#ef4444" : "#8aa0bf",
              weight: 1,
              opacity: 0.4,
            }}
          />
        ) : null,
      )}

      {/* Vessels */}
      {vessels.filter((v) => v.kind.includes("tanker") || v.kind === "unknown").map((v) => (
        <CircleMarker
          key={v.id}
          center={[v.lat, v.lon]}
          radius={2.5}
          pathOptions={{
            color: v.speed_kn === 0 ? "#ef4444" : "#e6edf7",
            fillColor: v.speed_kn === 0 ? "#ef4444" : "#e6edf7",
            fillOpacity: 0.8,
            weight: 0,
          }}
        >
          <Tooltip>
            {v.name} · {v.kind.toUpperCase()} · {v.source_kind?.toUpperCase() ?? "UNKNOWN SOURCE"}
            <br />{v.corridor_id ?? "outside monitored corridor"} · {v.speed_kn.toFixed(1)} kn
          </Tooltip>
        </CircleMarker>
      ))}

      {/* Source-backed risk observations */}
      {mappableEvents.map((event) => {
        const color = event.category === "satellite"
          ? "#ef4444"
          : SEVERITY_META[event.severity].color;
        return (
          <CircleMarker
            key={event.id}
            center={[event.lat as number, event.lon as number]}
            radius={event.category === "satellite" ? 8 : 5}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: event.category === "satellite" ? 0.28 : 0.18,
              weight: event.category === "satellite" ? 2 : 1.25,
              dashArray: event.source_kind === "live" ? undefined : "3 4",
            }}
          >
            <Tooltip sticky>
              {event.category.toUpperCase()} · {event.source_kind.toUpperCase()}
              <br />
              {event.title}
            </Tooltip>
          </CircleMarker>
        );
      })}

      {/* Explicit catalog-simulation overlay; never represented as observed telemetry. */}
      {scenarioId === "hormuz_closure" && (
        <CircleMarker
          center={[26.5, 56.2]}
          radius={45}
          pathOptions={{
            color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.08,
            weight: 2, dashArray: "4 6",
          }}
        >
          <Tooltip sticky>CATALOG SIMULATION · HORMUZ 90% CLOSURE (NOT A LIVE OBSERVATION)</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}

export { STATUS_COLOR, utilColor, SEVERITY_META };
