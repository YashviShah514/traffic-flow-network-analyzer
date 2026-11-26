import { AlertTriangle, CheckCircle2, FlaskConical, Eraser } from "lucide-react";
import { useState } from "react";
import { Alert, Badge, Button, Card, CardContent, Input } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { applyTraffic, clearTraffic, isPort, updateJunction } from "@/lib/graph";
import type { NetworkDraft } from "@/lib/types";

const KIND: Record<string, string> = { start: "Location 1", pickup: "Location 1", end: "Location 2", destination: "Location 2", boundary: "Boundary" };

/** External traffic of a map network. Road geometry carries no vehicle counts, so they are entered here
 *  (or filled with clearly labelled sample values). */
export function BoundaryPanel({ net, setNet, editable }: { net: NetworkDraft; setNet: (n: NetworkDraft) => void; editable: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ports = net.junctions.filter((j) => isPort(net, j));
  const entering = net.junctions.reduce((s, j) => s + Math.max(0, -(Number(j.net_demand) || 0)), 0);
  const leaving = net.junctions.reduce((s, j) => s + Math.max(0, Number(j.net_demand) || 0), 0);
  const balanced = Math.abs(entering - leaving) < 1e-9;
  const measured = net.roads.filter((r) => r.known_flow !== null).length;
  const empty = entering === 0 && leaving === 0 && measured === 0;
  const sample = Boolean(net.map_meta?.sample_values);

  const fill = async () => {
    if (!empty && !sample && !confirm("Replace the traffic values you entered with sample values?")) return;
    setBusy(true); setError(null);
    try { setNet(applyTraffic(net, await api.sampleValues(net))); }
    catch (e: any) { setError(e.message); }
    setBusy(false);
  };

  return (
    <Card data-testid="boundary-panel">
      <CardContent className="space-y-3 pt-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">Traffic entering and leaving the network</h2>
          {sample && <Badge tone="amber">SAMPLE VALUES — not real traffic counts</Badge>}
          <span className="ml-auto flex flex-wrap gap-2">
            {editable && <Button size="sm" variant="outline" disabled={busy || !net.roads.length} onClick={fill}><FlaskConical size={14} />{busy ? "Preparing…" : "Use sample values"}</Button>}
            {editable && !empty && <Button size="sm" variant="ghost" onClick={() => confirm("Clear all demands and measured flows?") && setNet(clearTraffic(net))}><Eraser size={14} />Clear values</Button>}
          </span>
        </div>
        <p className="text-slate-500">Map data has roads but no vehicle counts. Enter the traffic at the boundary junctions (where roads leave the selected area) and at the two locations, and mark measured roads in the road panel.</p>
        {empty && <Alert tone="info">No traffic values yet, so every flow can be zero. {editable ? "Enter your own counts below, or use sample values for a demonstration." : "Press “Edit” to enter counts."}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <div className="flex flex-wrap items-center gap-3">
          <span>Entering: <b>{entering}</b></span><span>Leaving: <b>{leaving}</b></span><span>Measured roads: <b>{measured}</b></span>
          {balanced
            ? <span className="flex items-center gap-1 text-emerald-700"><CheckCircle2 size={15} />Balanced</span>
            : <span className="flex items-center gap-1 text-amber-700"><AlertTriangle size={15} />Entering and leaving must be equal, otherwise no solution exists</span>}
        </div>
        <details open={ports.length <= 8}>
          <summary className="cursor-pointer font-medium">{ports.length} junction(s) where traffic can enter or leave</summary>
          <div className="mt-2 grid max-h-64 gap-2 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {ports.map((j) => {
              const d = Number(j.net_demand) || 0;
              return (
                <div key={j.key} className="rounded-lg border border-slate-200 p-2 dark:border-navy-700">
                  <div className="flex items-center justify-between gap-2"><b>{j.name}</b><Badge tone={j.node_type === "boundary" ? "cyan" : "blue"}>{KIND[j.node_type ?? ""] ?? "Junction"}</Badge></div>
                  <label className="mt-1 block text-xs text-slate-500" htmlFor={`d-${j.key}`}>D (+ leaves, − enters){d ? ` · ${Math.abs(d)} ${d > 0 ? "leave" : "enter"}` : ""}</label>
                  <Input id={`d-${j.key}`} inputMode="decimal" disabled={!editable} value={j.net_demand} onChange={(e) => setNet(updateJunction(net, j.key, { net_demand: e.target.value }))} />
                </div>
              );
            })}
          </div>
        </details>
      </CardContent>
    </Card>
  );
}
