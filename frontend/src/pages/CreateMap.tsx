import { Loader2, Route as RouteIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PickerMap } from "@/components/MapView";
import { PlaceSearch } from "@/components/PlaceSearch";
import { Alert, Button, Card, CardContent, Input, Label, PageHeader } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { distance } from "@/lib/graph";
import { readDraft, storeDraft } from "@/lib/useWorkspace";
import type { Place } from "@/lib/types";

export default function CreateMap() {
  const [first, setFirst] = useState<Place | null>(null);
  const [second, setSecond] = useState<Place | null>(null);
  const [picking, setPicking] = useState<"location1" | "location2" | null>(null);
  const [detail, setDetail] = useState("main");
  const [radius, setRadius] = useState(150);
  const [flow, setFlow] = useState("0");
  const [prune, setPrune] = useState(true);
  const [busy, setBusy] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!busy) return;
    setSeconds(0);
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [busy]);
  useEffect(() => () => controller.current?.abort(), []);

  const pick = async (which: "location1" | "location2", lat: number, lng: number) => {
    const set = which === "location1" ? setFirst : setSecond;
    setPicking(null); setError(null);
    set({ lat, lng, label: "Dropped pin", detail: "Looking up the address…" });
    try { set(await api.reverse(lat, lng)); }
    catch { set({ lat, lng, label: "Dropped pin", detail: `${lat.toFixed(5)}, ${lng.toFixed(5)}` }); }
  };

  const generate = async () => {
    if (!first || !second) { setError("Select both Location 1 and Location 2 first."); return; }
    const v = Number(flow);
    if (!Number.isFinite(v) || v < 0) { setError("Trip demand must be a number of vehicles, 0 or more."); return; }
    const existing = readDraft();
    if (existing?.junctions.length && !confirm("Replace your unsaved network with the new one?")) return;
    setBusy(true); setError(null);
    controller.current = new AbortController();
    try {
      const out = await api.generateMapNetwork({ start: first, end: second, detail, radius_m: radius, prune_stubs: prune, trip_flow: v }, controller.current.signal);
      // The generator's notes travel with the network, so they are shown and saved with it.
      storeDraft({ ...out.network, map_meta: { ...out.network.map_meta!, notes: out.warnings } });
      navigate("/network/new");
    } catch (e: any) {
      if (e.name !== "AbortError") setError(e.message);
      setBusy(false);
    }
  };

  const apart = first && second ? distance([first.lat, first.lng], [second.lat, second.lng]) : null;

  return (
    <>
      <PageHeader title="Automatic map-based network" subtitle="Choose two places. The real road network between them is read from OpenStreetMap and converted automatically into a graph of junctions (V1, V2, …) and directed roads (E1, E2, …)." />
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Card><CardContent className="space-y-4 pt-5">
          <PlaceSearch id="location1" label="Location 1 (Starting Location)" color="#15803d" value={first} onChange={(p) => { setFirst(p); setError(null); }} near={second}
            picking={picking === "location1"} onPickToggle={() => setPicking(picking === "location1" ? null : "location1")} />
          <PlaceSearch id="location2" label="Location 2 (Ending Location)" color="#b91c1c" value={second} onChange={(p) => { setSecond(p); setError(null); }} near={first}
            picking={picking === "location2"} onPickToggle={() => setPicking(picking === "location2" ? null : "location2")} />
          {apart !== null && <p className="text-xs text-slate-500">Straight-line distance: {(apart / 1000).toFixed(2)} km (limit 6 km).</p>}
          <details className="text-sm">
            <summary className="cursor-pointer font-medium">Options</summary>
            <div className="mt-3 space-y-3">
              <div><Label htmlFor="detail">Road detail</Label>
                <select id="detail" value={detail} onChange={(e) => setDetail(e.target.value)} className="h-9 w-full rounded-lg border border-slate-300 bg-white px-2 dark:bg-navy-800">
                  <option value="main">Main roads (smaller system)</option><option value="all">All streets (larger system)</option></select></div>
              <div><Label htmlFor="radius">Corridor around the route: {radius} m each side</Label><input id="radius" type="range" min={60} max={350} step={10} value={radius} onChange={(e) => setRadius(Number(e.target.value))} className="w-full" /></div>
              <div><Label htmlFor="trip">Optional: vehicles travelling from Location 1 to Location 2</Label><Input id="trip" inputMode="decimal" value={flow} onChange={(e) => setFlow(e.target.value)} /></div>
              <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={prune} onChange={(e) => setPrune(e.target.checked)} />Leave out dead-end side streets leading away from the route</label>
            </div>
          </details>
          <Button size="lg" className="w-full" disabled={busy || !first || !second} onClick={generate}>
            {busy ? <><Loader2 size={18} className="animate-spin" />Generating…</> : <><RouteIcon size={18} />Generate road network</>}
          </Button>
          {(!first || !second) && <p className="text-xs text-slate-500">Both locations are needed before a network can be generated.</p>}
          {busy && <Alert tone="info">Finding the route and downloading road data… {seconds}s. Public OpenStreetMap servers can take up to a minute.
            <button className="ml-2 underline" onClick={() => { controller.current?.abort(); setBusy(false); }}>Cancel</button></Alert>}
          {error && <Alert tone="error">{error}
            <div className="mt-2 flex flex-wrap gap-3">{first && second && <button className="font-semibold underline" onClick={generate}>Retry</button>}
              <Link className="font-semibold underline" to="/network/new?method=manual" onClick={() => storeDraft(null)}>Create the network manually</Link></div></Alert>}
        </CardContent></Card>
        <Card className="overflow-hidden">
          <div className="h-[55dvh] min-h-[360px] lg:h-[640px]" data-testid="picker-map"><PickerMap first={first} second={second} picking={picking} onPick={pick} /></div>
          <p className="px-3 py-2 text-xs text-slate-500">Drag the 1 and 2 markers to fine-tune. Map data © OpenStreetMap contributors · search by Photon · routing by OSRM · road data via the Overpass API.</p>
        </Card>
      </div>
    </>
  );
}
