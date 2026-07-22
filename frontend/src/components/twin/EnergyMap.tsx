"use client";

import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from "react-leaflet";
import type { IntelEvent, NetworkData, Vessel } from "@/lib/types";
import { SEVERITY_META } from "@/lib/severity";

export interface TwinSelection {
  kind: "refinery" | "port" | "supplier" | "reserve" | "corridor";
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
  onSelect,
}: {
  network: NetworkData;
  vessels: Vessel[];
  events: IntelEvent[];
  mapMode: MapMode;
  onSelect: (sel: TwinSelection) => void;
}) {
  const mappableEvents = events.filter((event) => event.lat !== null && event.lon !== null);

  return (
    <MapContainer
      center={[16, 66]}
      zoom={4}
      minZoom={3}
      maxZoom={7}
      className="h-full w-full bg-void"
      worldCopyJump
      attributionControl={false}
    >
      {mapMode === "satellite" ? (
        <TileLayer
          key="satellite"
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        />
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
              color: STATUS_COLOR[c.status] ?? "#22d3ee",
              weight: 1.5 + c.import_share * 6,
              opacity: 0.55,
              dashArray: c.status === "operational" ? undefined : "6 6",
            }}
            eventHandlers={{ click: () => onSelect({ kind: "corridor", id: c.id }) }}
          >
            <Tooltip sticky>
              {c.name} · {(c.import_share * 100).toFixed(0)}% of imports
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
      {network.ports.map((p) => (
        <CircleMarker
          key={p.id}
          center={[p.coords.lat, p.coords.lon]}
          radius={4}
          pathOptions={{ color: "#22d3ee", fillColor: "#22d3ee", fillOpacity: 0.6, weight: 1 }}
          eventHandlers={{ click: () => onSelect({ kind: "port", id: p.id }) }}
        >
          <Tooltip>{p.name}</Tooltip>
        </CircleMarker>
      ))}

      {/* Refineries — sized by capacity, colored by utilisation */}
      {network.refineries.map((r) => (
        <CircleMarker
          key={r.id}
          center={[r.coords.lat, r.coords.lon]}
          radius={5 + (r.nameplate_kbpd / 1240) * 9}
          pathOptions={{
            color: utilColor(r.utilization),
            fillColor: utilColor(r.utilization),
            fillOpacity: 0.35,
            weight: 1.5,
          }}
          eventHandlers={{ click: () => onSelect({ kind: "refinery", id: r.id }) }}
        >
          <Tooltip>
            {r.name} · {r.nameplate_kbpd} kbpd · {r.utilization}%
          </Tooltip>
        </CircleMarker>
      ))}

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

      {/* Vessels */}
      {vessels.map((v) => (
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
          <Tooltip>{v.name} · {v.cargo_kbbl?.toFixed(0)} kbbl</Tooltip>
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
    </MapContainer>
  );
}

export { STATUS_COLOR, utilColor, SEVERITY_META };
