import { useEffect, useState } from "react";
import { NetworkDiagram } from "@/components/NetworkDiagram";
import { Alert, Badge, Card, CardContent, CardHeader, CardTitle, Label, PageHeader } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { useNetwork } from "@/lib/store";
import type { GraphResult } from "@/lib/types";
import { NeedNetwork } from "./Solver";

export default function GraphAnalysis() {
  const { net, params } = useNetwork();
  const [start, setStart] = useState<string>("");
  const [g, setG] = useState<GraphResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!net.junctions.length) return;
    const s = net.junctions.some((j) => j.key === start) ? start : net.junctions[0].key;
    api.analyze(net, params, s).then((r) => { setG(r.graph); setErr(null); }).catch((e) => setErr(e.message));
  }, [net, start, params]);

  if (!net.junctions.length) return <><PageHeader title="Graph Analysis" /><NeedNetwork /></>;
  const levels = g?.bfs_directed?.levels ?? {};
  const maxL = Math.max(0, ...Object.values(levels));
  return (
    <>
      <PageHeader title="Graph Analysis" subtitle="The network as a directed graph: adjacency lists, breadth-first search, reachability and connectivity." />
      {err && <Alert tone="error">{err}</Alert>}
      {g && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="lg:col-span-2"><CardContent className="grid gap-4 pt-5 md:grid-cols-[1fr_320px]">
            <NetworkDiagram net={net} height={260} />
            <div className="space-y-3 text-sm">
              <div><Label htmlFor="start">BFS start junction</Label>
                <select id="start" className="h-9 w-full rounded-lg border border-slate-300 bg-white px-2 dark:bg-navy-800" value={start || net.junctions[0].key} onChange={(e) => setStart(e.target.value)}>
                  {net.junctions.map((j) => <option key={j.key} value={j.key}>{j.name}</option>)}</select></div>
              <div className="flex flex-wrap gap-2">
                <Badge tone={g.weakly_connected ? "green" : "red"}>{g.weakly_connected ? "Weakly connected" : `Not connected (${g.weak_components.length} components)`}</Badge>
                <Badge tone={g.strongly_connected ? "green" : "amber"}>{g.strongly_connected ? "Strongly connected" : "Not strongly connected"}</Badge>
                <Badge tone={g.isolated_junctions.length ? "red" : "green"}>{g.isolated_junctions.length ? `Isolated: ${g.isolated_junctions.join(", ")}` : "No isolated junctions"}</Badge>
              </div>
              {g.note && <p className="text-xs text-slate-500">{g.note}</p>}
            </div>
          </CardContent></Card>

          <Card><CardHeader><CardTitle>Adjacency lists</CardTitle></CardHeader><CardContent>
            <table className="w-full text-sm"><thead><tr className="text-left text-xs text-slate-500"><th>Junction</th><th>Out →</th><th>← In</th><th>deg(in/out)</th></tr></thead><tbody>
              {Object.keys(g.adjacency_out).map((k) => (
                <tr key={k} className="border-t border-slate-100 dark:border-navy-700"><td className="py-1 font-semibold">{k}</td>
                  <td className="eq">[{g.adjacency_out[k].join(", ")}]</td><td className="eq">[{g.adjacency_in[k].join(", ")}]</td><td>{g.degrees[k].in}/{g.degrees[k].out}</td></tr>))}
            </tbody></table>
          </CardContent></Card>

          <Card><CardHeader><CardTitle>BFS from {g.start}</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
            <div><div className="mb-1 font-semibold">Directed reachability (follows road directions)</div>
              <div className="eq">order: {g.bfs_directed?.order.join(" → ")}</div>
              <div>Unreachable by driving: {g.bfs_directed?.unreachable.length ? <Badge tone="red">{g.bfs_directed.unreachable.join(", ")}</Badge> : <Badge tone="green">none</Badge>}</div></div>
            <div><div className="mb-1 font-semibold">Weak connectivity (ignores directions)</div>
              <div className="eq">order: {g.bfs_undirected?.order.join(" → ")}</div>
              <div>Not linked at all: {g.bfs_undirected?.unreachable.length ? <Badge tone="red">{g.bfs_undirected.unreachable.join(", ")}</Badge> : <Badge tone="green">none</Badge>}</div></div>
            <div><div className="mb-1 font-semibold">BFS levels (directed)</div>
              {Array.from({ length: maxL + 1 }, (_, l) => (
                <div key={l} className="flex gap-2"><span className="w-16 text-slate-500">level {l}</span>
                  {Object.entries(levels).filter(([, v]) => v === l).map(([k]) => <Badge key={k} tone="blue">{k}</Badge>)}</div>))}</div>
          </CardContent></Card>

          <Card className="lg:col-span-2"><CardHeader><CardTitle>Weakly connected components</CardTitle></CardHeader><CardContent className="space-y-1 text-sm">
            {g.weak_components.map((c, i) => <div key={i}>Component {i + 1}: <span className="eq">{`{${c.join(", ")}}`}</span></div>)}
            {g.sources_only.length > 0 && <div>Sources (only outgoing roads): {g.sources_only.join(", ")}</div>}
            {g.sinks_only.length > 0 && <div>Sinks (only incoming roads): {g.sinks_only.join(", ")}</div>}
            <p className="pt-2 text-slate-500">A disconnected network splits into independent balance problems: each component's external flows must balance on their own, otherwise the system is inconsistent.</p>
          </CardContent></Card>
        </div>
      )}
    </>
  );
}
