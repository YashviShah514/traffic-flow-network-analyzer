import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { demandText, FLOW_COLORS, roadIds, type RoadFlow } from "@/lib/graph";
import type { LatLng, NetworkDraft, Place, Road } from "@/lib/types";
import type { Mode, Selection } from "./ManualCanvas";

// Standard OSM tiles, used within the tile usage policy: attribution shown, normal browser caching, no prefetching.
const TILE_URL = (import.meta.env.VITE_TILE_URL as string) || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export function pinIcon(letter: string, color: string) {
  return L.divIcon({ className: "fm-icon", iconSize: [30, 30], iconAnchor: [15, 30],
    html: `<div class="fm-pin" style="background:${color}"><span>${letter}</span></div>` });
}

function Tiles() {
  return <TileLayer url={TILE_URL} attribution={ATTRIBUTION} maxZoom={19} />;
}

function Resize() {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

function Fit({ points, signature }: { points: LatLng[]; signature: string }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 17 });
    else if (points.length === 1) map.setView(points[0], 15);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, map]);
  return null;
}

/** Shift a path sideways by `px` screen pixels (left-hand traffic side) so both directions of a street are visible. */
function offsetPath(map: L.Map, line: LatLng[], px: number): LatLng[] {
  if (!px || line.length < 2) return line;
  const zoom = map.getZoom();
  const pts = line.map((p) => map.project(p, zoom));
  return pts.map((p, i) => {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
    const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    const q = L.point(p.x + ((b.y - a.y) / len) * px, p.y - ((b.x - a.x) / len) * px);
    const ll = map.unproject(q, zoom);
    return [ll.lat, ll.lng] as LatLng;
  });
}

/** Point and screen-space bearing at a fraction of the path length. */
function along(map: L.Map, line: LatLng[], fraction: number): { at: LatLng; angle: number } {
  const zoom = map.getZoom();
  const pts = line.map((p) => map.project(p, zoom));
  const segs = pts.slice(1).map((p, i) => p.distanceTo(pts[i]));
  let rest = segs.reduce((a, b) => a + b, 0) * fraction, i = 0;
  while (i < segs.length - 1 && rest > segs[i]) rest -= segs[i++];
  const t = segs[i] ? rest / segs[i] : 0;
  const q = L.point(pts[i].x + (pts[i + 1].x - pts[i].x) * t, pts[i].y + (pts[i + 1].y - pts[i].y) * t);
  const ll = map.unproject(q, zoom);
  return { at: [ll.lat, ll.lng], angle: (Math.atan2(pts[i + 1].y - pts[i].y, pts[i + 1].x - pts[i].x) * 180) / Math.PI };
}

export const NODE_COLOR: Record<string, string> = { start: "#15803d", pickup: "#15803d", end: "#b91c1c", destination: "#b91c1c", boundary: "#0e7490" };

interface MapEditorProps {
  net: NetworkDraft; editable: boolean; mode: Mode; selected: Selection; connectFrom: string | null;
  flows: Record<string, RoadFlow>;
  onSelect: (s: Selection) => void; onAddAt: (p: { lat: number; lng: number }) => void;
  onSplit: (road: string, at: LatLng) => void; onJunctionClick: (key: string) => void;
}

function Roads({ net, editable, mode, selected, flows, onSelect, onSplit }: MapEditorProps) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });
  const position = useMemo(() => new Map(net.junctions.map((j) => [j.key, [j.lat, j.lng] as LatLng])), [net.junctions]);
  const dense = net.roads.length > 40;
  const ids = useMemo(() => roadIds(net), [net]);

  const drawn = useMemo(() => {
    const seen: Record<string, number> = {};
    return net.roads.flatMap((r: Road) => {
      const base = r.geometry?.length ? r.geometry : [position.get(r.source)!, position.get(r.target)!];
      if (base.some((p) => !p || p[0] == null)) return [];
      const pair = `${r.source}>${r.target}`;
      const index = seen[pair] ?? 0;
      seen[pair] = index + 1;
      const twin = net.roads.some((o) => o.source === r.target && o.target === r.source);
      return [{ road: r, line: offsetPath(map, base, (twin ? 5 : 0) + index * 9) }];
    });
  }, [net.roads, position, map, zoom]);

  // Declutter: place labels greedily (selected and measured roads first) and skip any that would collide
  // with an earlier label or a junction marker. Zooming in makes room for more; hover shows every value.
  const labels = useMemo(() => {
    const taken: { x: number; y: number; w: number; h: number }[] = net.junctions.flatMap((j) => {
      if (j.lat == null) return [];
      const p = map.project([j.lat, j.lng!], zoom);
      return [{ x: p.x, y: p.y, w: 22, h: 22 }];
    });
    const rank = (k: string) => (selected?.key === k ? 0 : flows[k]?.kind === "known" ? 1 : 2);
    const out = new Map<string, LatLng>();
    for (const { road, line } of [...drawn].sort((a, b) => rank(a.road.key) - rank(b.road.key))) {
      const w = (`${ids[road.key]} · ${flows[road.key]?.text ?? ""}`.length) * 7 + 10;
      for (const fraction of [0.45, 0.25, 0.8]) {
        const { at } = along(map, line, fraction);
        const p = map.project(at, zoom);
        const clash = taken.some((t) => Math.abs(t.x - p.x) < (t.w + w) / 2 && Math.abs(t.y - p.y) < (t.h + 18) / 2);
        if (!clash || selected?.key === road.key) { out.set(road.key, at); taken.push({ x: p.x, y: p.y, w, h: 18 }); break; }
      }
    }
    return out;
  }, [drawn, flows, ids, selected, net.junctions, map, zoom]);

  return (
    <>
      {drawn.map(({ road, line }) => {
        const flow = flows[road.key];
        const active = selected?.kind === "road" && selected.key === road.key;
        const color = active ? "#0891b2" : FLOW_COLORS[flow?.kind ?? "unresolved"];
        const arrow = along(map, line, dense ? 0.62 : 0.68);
        const labelAt = labels.get(road.key);
        const click = (e: L.LeafletMouseEvent) => {
          L.DomEvent.stopPropagation(e);
          if (editable && mode === "add") onSplit(road.key, [e.latlng.lat, e.latlng.lng]);
          else onSelect({ kind: "road", key: road.key });
        };
        const title = `${ids[road.key]} · ${road.label || "Unnamed road"} · ${flow?.text ?? ""}`;
        return (
          <span key={road.key}>
            <Polyline positions={line} pathOptions={{ color, weight: active ? 7 : 4, opacity: 0.9, interactive: false }} />
            <Polyline positions={line} pathOptions={{ color: "#000", weight: 14, opacity: 0, className: "fm-road-hit" }} bubblingMouseEvents={false} eventHandlers={{ click }}>
              <Tooltip sticky>{title}</Tooltip>
            </Polyline>
            <Marker position={arrow.at} interactive={false} keyboard={false}
              icon={L.divIcon({ className: "fm-icon", iconSize: [14, 14], iconAnchor: [7, 7],
                html: `<svg class="fm-arrow" width="14" height="14" viewBox="-7 -7 14 14" style="transform:rotate(${arrow.angle}deg)"><path d="M6,0 L-5,-5 L-2,0 L-5,5 z" fill="${color}" stroke="white" stroke-width="1"/></svg>` })} />
            {labelAt && (
              <Marker position={labelAt} interactive={false} keyboard={false}
                icon={L.divIcon({ className: "fm-icon", iconSize: [0, 0],
                  html: `<div class="fm-flow" style="color:${color};border-color:${color}">${esc(`${ids[road.key]} · ${flow?.text ?? ""}`)}</div>` })} />
            )}
          </span>
        );
      })}
    </>
  );
}

function ClickToAdd({ editable, mode, onAddAt, onSelect }: MapEditorProps) {
  useMapEvents({ click: (e) => (editable && mode === "add" ? onAddAt({ lat: e.latlng.lat, lng: e.latlng.lng }) : onSelect(null)) });
  return null;
}

/** The network drawn on the real map, with the same editing operations as the manual canvas. */
export function NetworkMap(props: MapEditorProps) {
  const { net, selected, connectFrom, onJunctionClick, editable, mode } = props;
  const points = net.junctions.filter((j) => j.lat != null).map((j) => [j.lat!, j.lng!] as LatLng);
  const first = useRef<LatLng>(points[0] ?? [23.03, 72.56]);
  const small = net.junctions.length > 25;
  const location1 = net.map_meta?.start ?? net.map_meta?.pickup, location2 = net.map_meta?.end ?? net.map_meta?.destination;
  return (
    <MapContainer center={first.current} zoom={15} zoomSnap={0.25} zoomDelta={0.5} className={`h-full w-full ${editable && mode === "add" ? "fm-adding" : ""}`} doubleClickZoom={false}>
      <Tiles /><Resize /><Fit points={points} signature={`${net.id ?? "draft"}:${net.map_meta?.start?.lat ?? net.map_meta?.pickup?.lat ?? ""}`} />
      <ClickToAdd {...props} />
      <Roads {...props} />
      {net.junctions.filter((j) => j.lat != null).map((j) => {
        const active = (selected?.kind === "junction" && selected.key === j.key) || connectFrom === j.key;
        const demand = demandText(j.net_demand);
        const color = NODE_COLOR[j.node_type ?? ""] ?? "#0b1f3a";
        const size = small ? 18 : 24;
        return (
          <Marker key={j.key} position={[j.lat!, j.lng!]} title={j.name} zIndexOffset={500} riseOnHover bubblingMouseEvents={false}
            eventHandlers={{ click: (e) => { L.DomEvent.stopPropagation(e); onJunctionClick(j.key); } }}
            icon={L.divIcon({ className: "fm-icon", iconSize: [size, size], iconAnchor: [size / 2, size / 2],
              html: `<div data-testid="map-junction" class="fm-node ${active ? "active" : ""} ${j.node_type === "boundary" ? "boundary" : ""}" style="background:${color};width:${size}px;height:${size}px">${esc(j.name.slice(0, 4))}</div>${demand ? `<div class="fm-demand">${esc(demand)}</div>` : ""}` })} />
        );
      })}
      {location1 && <Marker position={[location1.lat, location1.lng]} icon={pinIcon("1", "#15803d")}><Tooltip>Location 1: {location1.label}</Tooltip></Marker>}
      {location2 && <Marker position={[location2.lat, location2.lng]} icon={pinIcon("2", "#b91c1c")}><Tooltip>Location 2: {location2.label}</Tooltip></Marker>}
    </MapContainer>
  );
}

/** Location-selection map used before generating: markers can be dragged, or placed by clicking. */
export function PickerMap({ first, second, picking, onPick }: {
  first: Place | null; second: Place | null; picking: "location1" | "location2" | null;
  onPick: (which: "location1" | "location2", lat: number, lng: number) => void;
}) {
  const points: LatLng[] = [first, second].filter(Boolean).map((p) => [p!.lat, p!.lng]);
  const marker = (which: "location1" | "location2", place: Place, letter: string, color: string) => (
    <Marker position={[place.lat, place.lng]} draggable icon={pinIcon(letter, color)}
      eventHandlers={{ dragend: (e) => { const p = (e.target as L.Marker).getLatLng(); onPick(which, p.lat, p.lng); } }}>
      <Tooltip>{which === "location1" ? "Location 1" : "Location 2"}: {place.label}</Tooltip>
    </Marker>
  );
  function Click() {
    useMapEvents({ click: (e) => picking && onPick(picking, e.latlng.lat, e.latlng.lng) });
    return null;
  }
  return (
    <MapContainer center={[23.0305, 72.5646]} zoom={14} className={`h-full w-full ${picking ? "fm-adding" : ""}`}>
      <Tiles /><Resize /><Click />
      <Fit points={points} signature={points.map((p) => p.join()).join("|")} />
      {points.length === 2 && <Polyline positions={points} pathOptions={{ color: "#64748b", dashArray: "6 8", weight: 2 }} />}
      {first && marker("location1", first, "1", "#15803d")}
      {second && marker("location2", second, "2", "#b91c1c")}
      {first && <CircleMarker center={[first.lat, first.lng]} radius={4} pathOptions={{ color: "#15803d" }} />}
    </MapContainer>
  );
}
