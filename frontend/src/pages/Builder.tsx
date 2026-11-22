import {
  Background, BaseEdge, Controls, EdgeLabelRenderer, Handle, MarkerType, Position, ReactFlow, ReactFlowProvider,
  useInternalNode, useReactFlow, useNodesState, type Connection, type EdgeProps, type Node, type NodeProps,
} from "@xyflow/react";
import { ArrowLeftRight, FilePlus2, Plus, Save, Sigma, Trash2 } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Label, PageHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/ui";
import { nextKey, variableNames } from "@/lib/network";
import { useNetwork } from "@/lib/store";
import { cn } from "@/lib/utils";

const RADIUS = 28;
const Ctx = createContext<{ varNames: Record<string, string> }>({ varNames: {} });

/** Junction node: a circle. Small dot (right) starts a road; the whole circle accepts road endpoints. */
function JunctionNode({ data, selected }: NodeProps) {
  const d = data as { name: string; ext: number };
  return (
    <div className={cn("relative grid h-14 w-14 place-items-center rounded-full bg-navy-900 text-xs font-bold text-white shadow-lg ring-offset-2",
      selected && "ring-2 ring-cyan2-400")}>
      <Handle type="target" position={Position.Top} isConnectableStart={false} style={{ inset: 0, width: "100%", height: "100%", transform: "none", opacity: 0, borderRadius: "50%" }} />
      <Handle type="source" position={Position.Right} title="Drag to another junction to create a road"
        style={{ right: -9, width: 14, height: 14, background: "#22d3ee", border: "2px solid white" }} />
      {d.name.slice(0, 5)}
      {d.ext !== 0 && <span className="absolute -bottom-5 whitespace-nowrap text-[11px] font-semibold text-cyan-600">{d.ext > 0 ? `+${d.ext} in` : `${-d.ext} out`}</span>}
    </div>
  );
}

/** Floating directed road: straight arrow from circle boundary to circle boundary. */
function RoadEdge({ id, source, target, markerEnd, selected, data }: EdgeProps) {
  const s = useInternalNode(source), t = useInternalNode(target);
  const { varNames } = useContext(Ctx);
  if (!s || !t) return null;
  const c = (n: typeof s) => ({ x: n.internals.positionAbsolute.x + (n.measured.width ?? 56) / 2, y: n.internals.positionAbsolute.y + (n.measured.height ?? 56) / 2 });
  const a = c(s), b = c(t);
  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len;
  const off = ((data as any)?.offset ?? 0) as number;
  const ox = -uy * off, oy = ux * off;
  const x1 = a.x + ux * RADIUS + ox, y1 = a.y + uy * RADIUS + oy, x2 = b.x - ux * (RADIUS + 3) + ox, y2 = b.y - uy * (RADIUS + 3) + oy;
  const d = data as { label: string; known: string | null };
  const text = d.known ? `${d.known} (known)` : varNames[id];
  return (
    <>
      <BaseEdge id={id} path={`M${x1},${y1} L${x2},${y2}`} markerEnd={markerEnd}
        style={{ stroke: selected ? "#0891b2" : d.known ? "#0e7490" : "#1d4ed8", strokeWidth: selected ? 3.5 : 2.4 }} interactionWidth={22} />
      <EdgeLabelRenderer>
        <div className="nodrag nopan pointer-events-none absolute rounded-md bg-white/90 px-1.5 py-0.5 text-[11px] font-semibold text-navy-900 shadow-sm"
          style={{ transform: `translate(-50%,-50%) translate(${(x1 + x2) / 2 + ox * 1.2}px,${(y1 + y2) / 2 + oy * 1.2}px)` }}>
          {text}{d.label ? <span className="ml-1 font-normal text-slate-500">· {d.label}</span> : null}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

const nodeTypes = { junction: JunctionNode };
const edgeTypes = { road: RoadEdge };

function Editor() {
  const { net, setNet, save, dirty, reset, analysis, analysisError, loading } = useNetwork();
  const [sel, setSel] = useState<{ kind: "junction" | "road"; key: string } | null>(null);
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const varNames = useMemo(() => variableNames(net), [net]);
  const rf = useReactFlow();
  const wrap = useRef<HTMLDivElement>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  // Sync nodes from the draft, keeping React Flow's measured sizes.
  useEffect(() => {
    setNodes((prev) => net.junctions.map((j) => ({
      ...(prev.find((p) => p.id === j.key) ?? {}), id: j.key, type: "junction", position: { x: j.x, y: j.y },
      data: { name: j.name, ext: Number(j.external_inflow) || 0 }, selected: sel?.kind === "junction" && sel.key === j.key,
    })));
  }, [net.junctions, sel, setNodes]);

  const edges = useMemo(() => net.roads.map((r) => {
    const opposite = net.roads.some((o) => o.source === r.target && o.target === r.source);
    return { id: r.key, source: r.source, target: r.target, type: "road", selected: sel?.kind === "road" && sel.key === r.key,
      markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color: sel?.key === r.key ? "#0891b2" : "#1d4ed8" },
      data: { label: r.label, known: r.known_flow, offset: opposite ? 9 : 0 } };
  }), [net.roads, sel]);

  const addJunction = () => {
    const key = nextKey("J", net.junctions.map((j) => j.key));
    // Place the new junction at the centre of the visible canvas (with a little jitter so they never stack).
    const r = wrap.current?.getBoundingClientRect();
    const j = (net.junctions.length % 5) * 24;
    const p = r ? rf.screenToFlowPosition({ x: r.left + r.width / 2 + j, y: r.top + r.height / 2 + j }) : { x: 100, y: 100 };
    setNet({ ...net, junctions: [...net.junctions, { key, name: key, x: Math.round(p.x - 28), y: Math.round(p.y - 28), external_inflow: "0" }] });
    setSel({ kind: "junction", key });
  };
  const onConnect = useCallback((c: Connection) => {
    if (!c.source || !c.target || c.source === c.target) return;
    const key = nextKey("r", net.roads.map((r) => r.key));
    setNet({ ...net, roads: [...net.roads, { key, label: "", source: c.source, target: c.target, known_flow: null }] });
    setSel({ kind: "road", key });
  }, [net, setNet]);

  const updJ = (key: string, p: Partial<(typeof net.junctions)[0]>) => setNet({ ...net, junctions: net.junctions.map((j) => (j.key === key ? { ...j, ...p } : j)) });
  const updR = (key: string, p: Partial<(typeof net.roads)[0]>) => setNet({ ...net, roads: net.roads.map((r) => (r.key === key ? { ...r, ...p } : r)) });
  const delJ = (key: string) => { setNet({ ...net, junctions: net.junctions.filter((j) => j.key !== key), roads: net.roads.filter((r) => r.source !== key && r.target !== key) }); setSel(null); };
  const delR = (key: string) => { setNet({ ...net, roads: net.roads.filter((r) => r.key !== key) }); setSel(null); };

  const doSave = async () => {
    try { const s = await save(); setMsg({ tone: "ok", text: `Saved "${s.name}" to the database.` }); }
    catch (e: any) { setMsg({ tone: "error", text: e.message }); }
  };

  const selJ = sel?.kind === "junction" ? net.junctions.find((j) => j.key === sel.key) : undefined;
  const selR = sel?.kind === "road" ? net.roads.find((r) => r.key === sel.key) : undefined;
  const jname = (k: string) => net.junctions.find((j) => j.key === k)?.name ?? k;

  return (
    <Ctx.Provider value={{ varNames }}>
      <PageHeader title="Create Network" subtitle="Add junctions, then drag from the cyan dot of one junction onto another to draw a one-way road. Roads with a measured flow are known; the rest become unknowns x1, x2, ..."
        actions={<>
          <Button variant="outline" onClick={() => { if (!dirty || confirm("Discard unsaved changes?")) reset(); }}><FilePlus2 size={16} />New</Button>
          <Button onClick={doSave}><Save size={16} />Save to database</Button>
        </>} />
      {msg && <div className="mb-3"><Alert tone={msg.tone}>{msg.text}</Alert></div>}
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <Card className="overflow-hidden">
          <div className="flex items-center gap-2 border-b border-slate-200 p-3 dark:border-navy-700">
            <Button size="sm" onClick={addJunction}><Plus size={14} />Add junction</Button>
            <span className="text-xs text-slate-500">{net.junctions.length} junctions · {net.roads.length} roads · scroll to zoom, drag canvas to pan</span>
          </div>
          <div ref={wrap} className="h-[560px]" data-testid="flow-canvas">
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} onNodesChange={onNodesChange}
              onNodeDragStop={(_, n) => updJ(n.id, { x: Math.round(n.position.x), y: Math.round(n.position.y) })}
              onConnect={onConnect} onNodeClick={(_, n) => setSel({ kind: "junction", key: n.id })}
              onEdgeClick={(_, e) => setSel({ kind: "road", key: e.id })} onPaneClick={() => setSel(null)}
              deleteKeyCode={null} fitView fitViewOptions={{ padding: 0.3 }} minZoom={0.3} maxZoom={2.5}>
              <Background gap={20} /><Controls showInteractive={false} />
            </ReactFlow>
          </div>
        </Card>

        <div className="space-y-4">
          <Card><CardContent className="space-y-3 pt-5">
            <div><Label htmlFor="nn">Network name</Label><Input id="nn" value={net.name} onChange={(e) => setNet({ ...net, name: e.target.value })} /></div>
            <div><Label htmlFor="nd">Description</Label><Input id="nd" value={net.description} onChange={(e) => setNet({ ...net, description: e.target.value })} /></div>
          </CardContent></Card>

          <Tabs defaultValue="edit">
            <TabsList><TabsTrigger value="edit">Properties</TabsTrigger><TabsTrigger value="eq">Live equations</TabsTrigger></TabsList>
            <TabsContent value="edit">
              <Card><CardContent className="space-y-3 pt-5">
                {!selJ && !selR && <p className="text-sm text-slate-500">Select a junction or road on the canvas to edit it.</p>}
                {selJ && <>
                  <CardTitle>Junction</CardTitle>
                  <div><Label htmlFor="jn">Name</Label><Input id="jn" value={selJ.name} onChange={(e) => updJ(selJ.key, { name: e.target.value })} /></div>
                  <div><Label htmlFor="je">External net inflow (+ enters / − leaves)</Label>
                    <Input id="je" inputMode="decimal" value={selJ.external_inflow} onChange={(e) => updJ(selJ.key, { external_inflow: e.target.value })} /></div>
                  <Button variant="destructive" size="sm" onClick={() => delJ(selJ.key)}><Trash2 size={14} />Delete junction</Button>
                </>}
                {selR && <>
                  <CardTitle>Road {jname(selR.source)} → {jname(selR.target)}</CardTitle>
                  <div><Label htmlFor="rl">Label</Label><Input id="rl" value={selR.label} onChange={(e) => updR(selR.key, { label: e.target.value })} /></div>
                  <div className="flex items-center gap-2">
                    <input id="rk" type="checkbox" checked={selR.known_flow !== null} onChange={(e) => updR(selR.key, { known_flow: e.target.checked ? "0" : null })} />
                    <Label htmlFor="rk" className="!mb-0">Measured by a sensor (known flow)</Label>
                  </div>
                  {selR.known_flow !== null
                    ? <div><Label htmlFor="rf">Known flow (≥ 0)</Label><Input id="rf" inputMode="decimal" value={selR.known_flow} onChange={(e) => updR(selR.key, { known_flow: e.target.value })} /></div>
                    : <Badge tone="blue">Unknown variable {varNames[selR.key]}</Badge>}
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => updR(selR.key, { source: selR.target, target: selR.source })}><ArrowLeftRight size={14} />Reverse direction</Button>
                    <Button variant="destructive" size="sm" onClick={() => delR(selR.key)}><Trash2 size={14} />Delete</Button>
                  </div>
                </>}
              </CardContent></Card>
            </TabsContent>
            <TabsContent value="eq">
              <Card><CardContent className="space-y-2 pt-5">
                {analysisError && <Alert tone="error">{analysisError}</Alert>}
                {loading && <p className="text-xs text-slate-400">Computing…</p>}
                {analysis?.equations.map((e) => <div key={e.junction_key} className="eq"><span className="text-slate-500">{e.junction_name}:</span> {e.text}</div>)}
                {analysis && <div className="pt-2 text-xs text-slate-500">rank {analysis.analysis.rank} · {analysis.analysis.n_unknowns} unknowns ·{" "}
                  <b>{{ unique: "unique solution", infinite: "infinite solutions", none: "no solution" }[analysis.analysis.classification]}</b></div>}
                {!analysis && !analysisError && <p className="text-sm text-slate-500">Add junctions to see equations.</p>}
                <Link to="/solver"><Button size="sm" className="mt-2"><Sigma size={14} />Open solver</Button></Link>
              </CardContent></Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Ctx.Provider>
  );
}

export default function Builder() {
  return <ReactFlowProvider><Editor /></ReactFlowProvider>;
}
