import { CheckCircle2, ChevronLeft, ChevronRight, Save, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Matrix } from "@/components/Matrix";
import { NetworkDiagram } from "@/components/NetworkDiagram";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Label, PageHeader, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { toNumber } from "@/lib/network";
import { useNetwork } from "@/lib/store";
import type { Analysis, NetworkSummary } from "@/lib/types";

export function NeedNetwork() {
  const { load } = useNetwork();
  const [list, setList] = useState<NetworkSummary[]>([]);
  useEffect(() => { api.listNetworks().then(setList).catch(() => {}); }, []);
  return (
    <div className="space-y-4">
      <Alert tone="info">No network loaded. Pick a saved network below, or <Link className="font-semibold underline" to="/builder">create a new network</Link>.</Alert>
      <div className="flex flex-wrap gap-2">
        {list.map((n) => <Button key={n.id} variant="outline" onClick={() => load(n.id)}>{n.name}</Button>)}
      </div>
    </div>
  );
}

export const CLASS_LABEL = { unique: "Unique solution", infinite: "Infinitely many solutions", none: "No solution" } as const;
export const CLASS_TONE = { unique: "green", infinite: "amber", none: "red" } as const;

function Equations({ a }: { a: Analysis }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">Rule: <b>incoming + external inflow = outgoing</b>, i.e. (unknown incoming) − (unknown outgoing) = −external − known incoming + known outgoing. Click a junction to inspect its derivation.</p>
      {a.equations.map((e) => (
        <Card key={e.junction_key}><CardContent className="pt-4">
          <button className="flex w-full items-center justify-between text-left" onClick={() => setOpen(open === e.junction_key ? null : e.junction_key)} aria-expanded={open === e.junction_key}>
            <span><b>{e.junction_name}</b> <span className="eq ml-3">{e.text}</span></span>
            <Badge tone="blue">{open === e.junction_key ? "hide" : "inspect"}</Badge>
          </button>
          {open === e.junction_key && (
            <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
              <div><div className="mb-1 font-semibold">Incoming roads</div>
                {e.incoming.length ? e.incoming.map((r) => <div key={r.road_key}>{r.from} → {r.to}: {r.variable ?? <b>known {r.known_flow}</b>}</div>) : <i className="text-slate-400">none</i>}</div>
              <div><div className="mb-1 font-semibold">Outgoing roads</div>
                {e.outgoing.length ? e.outgoing.map((r) => <div key={r.road_key}>{r.from} → {r.to}: {r.variable ?? <b>known {r.known_flow}</b>}</div>) : <i className="text-slate-400">none</i>}</div>
              <ol className="list-decimal space-y-1 pl-5 md:col-span-2 text-slate-600 dark:text-slate-300">{e.derivation.map((d, i) => <li key={i}>{d}</li>)}</ol>
            </div>
          )}
        </CardContent></Card>
      ))}
    </div>
  );
}

function MatrixTab({ a }: { a: Analysis }) {
  const m = a.matrix, v = m.variables;
  return (
    <div className="space-y-6">
      <Card><CardHeader><CardTitle>AX = B</CardTitle></CardHeader><CardContent className="flex flex-wrap items-center gap-4">
        <Matrix data={m.A} cols={v} /><span className="text-xl">×</span>
        <Matrix data={v.map((x) => [x])} /><span className="text-xl">=</span><Matrix data={m.B.map((b) => [b])} />
      </CardContent></Card>
      <Card><CardHeader><CardTitle>Augmented matrix [A | B]</CardTitle></CardHeader><CardContent><Matrix data={m.augmented} cols={[...v, "B"]} augment /></CardContent></Card>
      <p className="text-sm text-slate-500">One row per junction, one column per unknown road; the last column holds the constants.</p>
    </div>
  );
}

function Steps({ a }: { a: Analysis }) {
  const steps = a.reduction.steps;
  const [i, setI] = useState(0);
  const [all, setAll] = useState(false);
  const s = steps[Math.min(i, steps.length - 1)];
  const nv = a.matrix.variables.length;
  const cols = [...a.matrix.variables, "B"];
  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <Card><CardHeader><CardTitle>REF (Gaussian elimination)</CardTitle></CardHeader><CardContent><Matrix data={a.reduction.ref} cols={cols} augment /></CardContent></Card>
        <Card><CardHeader><CardTitle>RREF (Gauss-Jordan)</CardTitle></CardHeader><CardContent><Matrix data={a.reduction.rref} cols={cols} augment /></CardContent></Card>
      </div>
      <div className="flex items-center gap-3">
        <h3 className="font-semibold">Row operations ({steps.length})</h3>
        <Button size="sm" variant="outline" onClick={() => setAll(!all)}>{all ? "Step-by-step view" : "Show all steps"}</Button>
      </div>
      {steps.length === 0 && <Alert tone="info">The matrix was already in reduced form — no row operations were needed.</Alert>}
      {!all && s && (
        <Card><CardContent className="pt-5">
          <div className="mb-3 flex items-center gap-2">
            <Button size="icon" variant="outline" aria-label="Previous step" disabled={i === 0} onClick={() => setI(i - 1)}><ChevronLeft size={16} /></Button>
            <span className="text-sm">Step <b>{s.index}</b> of {steps.length}</span>
            <Button size="icon" variant="outline" aria-label="Next step" disabled={i >= steps.length - 1} onClick={() => setI(i + 1)}><ChevronRight size={16} /></Button>
            <Badge tone={s.phase === "forward" ? "blue" : "cyan"}>{s.phase === "forward" ? "Gaussian (forward)" : "Gauss-Jordan (backward)"}</Badge>
            <Badge>{s.kind}</Badge>
          </div>
          <p className="mb-1 text-sm">{s.description}</p>
          <p className="eq mb-3 font-semibold text-brand-700">{s.notation}</p>
          <Matrix data={s.matrix} cols={cols} augment highlight={s.pivot} />
        </CardContent></Card>
      )}
      {all && (
        <div className="space-y-3">
          {steps.map((st) => (
            <Card key={st.index}><CardContent className="flex flex-wrap items-center gap-6 pt-4">
              <div className="w-72 text-sm"><div className="font-semibold">#{st.index} · {st.kind} <Badge className="ml-1">{st.phase}</Badge></div>
                <div className="eq text-brand-700">{st.notation}</div><div className="text-slate-500">{st.description}</div></div>
              <Matrix data={st.matrix} augment highlight={st.pivot} />
            </CardContent></Card>
          ))}
        </div>
      )}
      <p className="text-sm text-slate-500">Pivots are in columns: {a.analysis.pivot_columns.join(", ") || "none"} ({nv} unknown columns). Rank = {a.analysis.rank}.</p>
    </div>
  );
}

function SolutionTab({ a }: { a: Analysis }) {
  const { params, setParams, net } = useNetwork();
  const [msg, setMsg] = useState<{ t: "ok" | "error"; s: string } | null>(null);
  const info = a.analysis;
  const save = async () => {
    if (!net.id) { setMsg({ t: "error", s: "Save the network to the database first (Create Network → Save)." }); return; }
    try { await api.storeSolution(net.id, params); setMsg({ t: "ok", s: "Solution stored in the database." }); } catch (e: any) { setMsg({ t: "error", s: e.message }); }
  };
  const ex = a.sample_solution;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone={CLASS_TONE[info.classification]} className="px-3 py-1 text-sm">{CLASS_LABEL[info.classification]}</Badge>
        <span className="text-sm">rank <b>{info.rank}</b> · unknowns <b>{info.n_unknowns}</b> · equations <b>{info.n_equations}</b> · nullity <b>{info.nullity}</b></span>
        <span className="ml-auto flex items-center gap-1 text-sm">{a.verification.all_passed ? <CheckCircle2 className="text-emerald-600" size={16} /> : <XCircle className="text-red-600" size={16} />}
          {a.verification.all_passed ? "AX = B, Av = 0 and SymPy cross-check verified" : "verification failed"}</span>
      </div>
      <Alert tone={info.classification === "none" ? "error" : "info"}>{a.conclusion}</Alert>
      {info.classification === "none" && <p className="text-sm">Inconsistent rows (in RREF): {info.inconsistent_rows.join(", ")} — each reads 0 = nonzero.</p>}
      {info.consistent && (
        <>
          <Card><CardHeader><CardTitle>{info.classification === "unique" ? "Solution" : "General solution"}</CardTitle></CardHeader><CardContent className="space-y-1">
            {info.general_solution.map((g) => <div key={g.variable} className="eq">{g.text}</div>)}
            {info.free_variables.length > 0 && <p className="pt-2 text-xs text-slate-500">Pivot variables: {info.pivot_columns.join(", ")} · free variables: {info.free_variables.join(", ")} (each free variable acts as a parameter t).</p>}
          </CardContent></Card>
          {info.free_variables.length > 0 && (
            <Card><CardHeader><CardTitle>Choose parameter values</CardTitle></CardHeader><CardContent>
              <div className="flex flex-wrap items-end gap-4">
                {info.free_variables.map((f) => (
                  <div key={f} className="w-32"><Label htmlFor={`p-${f}`}>{f}</Label>
                    <Input id={`p-${f}`} inputMode="decimal" value={params[f] ?? "0"} onChange={(e) => setParams({ ...params, [f]: e.target.value })} /></div>
                ))}
                {a.feasible_example && <Button variant="outline" size="sm" onClick={() => setParams(a.feasible_example!.parameters)}>Use a feasible example</Button>}
                <Button variant="ghost" size="sm" onClick={() => setParams({})}>Reset to 0</Button>
              </div>
            </CardContent></Card>
          )}
          {ex && <SampleCard ex={ex} title="Sample numerical solution" a={a} />}
          <Card><CardHeader><CardTitle>Mathematically valid vs physically feasible</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
            <p>Every solution of AX = B is <b>mathematically valid</b>. It is <b>physically feasible</b> only if every road flow is ≥ 0 (traffic cannot flow backwards).</p>
            <p>Is any nonnegative solution possible? <Badge tone={a.feasibility.exists ? "green" : "red"}>{a.feasibility.exists ? "Yes" : "No"}</Badge></p>
            {a.feasibility.exists && Object.keys(a.feasibility.ranges).length > 0 && (
              <table className="text-left"><thead><tr className="text-xs text-slate-500"><th className="pr-6">Road</th><th className="pr-6">Min flow</th><th>Max flow</th></tr></thead><tbody>
                {Object.entries(a.feasibility.ranges).map(([k, r]) => <tr key={k}><td className="eq pr-6">{k}</td><td className="pr-6">{r.min}</td><td>{r.max ?? "unbounded"}</td></tr>)}
              </tbody></table>)}
            {a.feasible_example && <p className="text-slate-500">Example feasible parameters: {Object.entries(a.feasible_example.parameters).map(([k, v]) => `${k} = ${v}`).join(", ") || "(unique)"}.</p>}
            <p className="text-xs text-slate-400">Ranges come from a linear program (floating point); the algebra above is exact.</p>
          </CardContent></Card>
        </>
      )}
      <div className="flex items-center gap-3"><Button onClick={save}><Save size={16} />Store solution in database</Button>
        {msg && <span className={msg.t === "ok" ? "text-sm text-emerald-700" : "text-sm text-red-600"}>{msg.s}</span>}</div>
    </div>
  );
}

function SampleCard({ ex, title, a }: { ex: NonNullable<Analysis["sample_solution"]>; title: string; a: Analysis }) {
  const data = ex.roads.map((r) => ({ name: r.label || `${r.from}→${r.to}`, value: Number(r.value.includes("/") ? toNumber(r.value) : r.value), known: r.known, neg: r.negative }));
  return (
    <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="space-y-3">
      <div className="flex flex-wrap gap-2 text-sm">
        {Object.entries(ex.parameters).map(([k, v]) => <Badge key={k} tone="blue">{k} = {v}</Badge>)}
        <Badge tone="green">Mathematically valid</Badge>
        <Badge tone={ex.physically_feasible ? "green" : "red"}>{ex.physically_feasible ? "Physically feasible" : `Infeasible: ${ex.negative_variables.join(", ")} < 0`}</Badge>
      </div>
      <div className="h-60"><ResponsiveContainer><BarChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="name" fontSize={11} /><YAxis fontSize={11} /><Tooltip />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>{data.map((d, i) => <Cell key={i} fill={d.neg ? "#dc2626" : d.known ? "#0891b2" : "#2563eb"} />)}</Bar></BarChart></ResponsiveContainer></div>
      <p className="text-xs text-slate-500">Cyan = measured, blue = computed, red = negative (not physical).</p>
    </CardContent></Card>
  );
}

function NullSpace({ a }: { a: Analysis }) {
  const { net } = useNetwork();
  const nb = a.analysis.null_basis;
  const vars = a.matrix.variables;
  const keyByVar = Object.fromEntries(a.variables.map((v) => [v.name, v.road_key]));
  return (
    <div className="space-y-5">
      <Alert tone="info"><b>AX = 0</b> (homogeneous system). A null-space vector is a way to change road flows <i>without breaking conservation at any junction</i> — traffic circulating around a loop. Adding any multiple of it to a solution gives another solution.</Alert>
      {a.analysis.classification === "none" && <Alert tone="warn">AX = B is inconsistent, but the null space depends only on A, so it is still shown.</Alert>}
      {nb.length === 0 && <Card><CardContent className="pt-5 text-sm">Nullity = 0: the null space is just {"{0}"}, so no circulating traffic is possible on the unknown roads.</CardContent></Card>}
      <div className="grid gap-4 lg:grid-cols-2">
        {nb.map((b) => {
          const hl: Record<string, "pos" | "neg"> = {};
          const labels: Record<string, string> = {};
          b.vector.forEach((c, i) => { if (Number(c.includes("/") ? toNumber(c) : c) !== 0) { const k = keyByVar[vars[i]]; hl[k] = toNumber(c) > 0 ? "pos" : "neg"; labels[k] = `${vars[i]}: ${toNumber(c) > 0 ? "+" : ""}${c}`; } });
          return (
            <Card key={b.parameter}><CardHeader><CardTitle>Basis vector for {b.free_variable} ({b.parameter})</CardTitle></CardHeader><CardContent className="space-y-3">
              <div className="flex items-center gap-3"><Matrix data={vars.map((_, i) => [b.vector[i]])} cols={undefined} /><div className="eq text-xs text-slate-500">over ({vars.join(", ")})</div></div>
              <NetworkDiagram net={net} highlight={hl} edgeLabels={labels} dim height={300} showExternal={false} />
              <p className="text-sm text-slate-600 dark:text-slate-300">Green roads gain {b.parameter} cars per unit, red roads lose {b.parameter}; grey roads are unaffected. Check: every junction receives as much extra traffic as it loses, so A·v = 0.</p>
            </CardContent></Card>
          );
        })}
      </div>
      {a.circulations.length > 0 && <p className="text-sm text-slate-500">Note: sensor roads have fixed flow, so circulations can only use unknown roads.</p>}
    </div>
  );
}

export default function Solver() {
  const { net, analysis, analysisError, loading } = useNetwork();
  if (!net.junctions.length) return <><PageHeader title="Mathematical Solver" /><NeedNetwork /></>;
  return (
    <>
      <PageHeader title="Mathematical Solver" subtitle={`${net.name} — equations, matrices, step-by-step row reduction, solution analysis and null space.`} />
      {analysisError && <Alert tone="error">{analysisError}</Alert>}
      {loading && !analysis && <p className="text-sm text-slate-500">Computing…</p>}
      {analysis && (
        <Tabs defaultValue="eq">
          <TabsList><TabsTrigger value="eq">Equations</TabsTrigger><TabsTrigger value="mat">Matrices</TabsTrigger><TabsTrigger value="red">Row reduction</TabsTrigger>
            <TabsTrigger value="sol">Solution analysis</TabsTrigger><TabsTrigger value="null">Null space</TabsTrigger></TabsList>
          <TabsContent value="eq"><Equations a={analysis} /></TabsContent>
          <TabsContent value="mat"><MatrixTab a={analysis} /></TabsContent>
          <TabsContent value="red"><Steps a={analysis} /></TabsContent>
          <TabsContent value="sol"><SolutionTab a={analysis} /></TabsContent>
          <TabsContent value="null"><NullSpace a={analysis} /></TabsContent>
        </Tabs>
      )}
    </>
  );
}
