import { ArrowRight, ChevronLeft, ChevronRight, Home, Maximize, Minimize, StickyNote } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Matrix } from "@/components/Matrix";
import { NetworkDiagram } from "@/components/NetworkDiagram";
import { ROLES } from "@/content/roles";
import { api } from "@/lib/api";
import { toNumber } from "@/lib/network";
import type { Analysis, NetworkDraft } from "@/lib/types";

interface Demo { net: NetworkDraft; a: Analysis }
type Demos = (Demo | null)[];

const W = 1280, H = 720;

/* ---------- small layout helpers ---------- */
const Title = ({ children, kicker }: { children: ReactNode; kicker?: string }) => (
  <div className="mb-6">{kicker && <div className="mb-1 text-sm font-semibold uppercase tracking-widest text-cyan-400">{kicker}</div>}
    <h2 className="text-4xl font-bold text-white">{children}</h2><div className="mt-3 h-1 w-20 rounded bg-cyan-400" /></div>
);
const Bullets = ({ items, size = "text-2xl" }: { items: ReactNode[]; size?: string }) => (
  <ul className={`space-y-3 ${size} text-slate-200`}>{items.map((t, i) => <li key={i} className="flex gap-3"><span className="mt-3 h-2 w-2 shrink-0 rounded-full bg-cyan-400" /><span>{t}</span></li>)}</ul>
);
const Box = ({ children, tone = "bg-navy-800", className = "" }: { children: ReactNode; tone?: string; className?: string }) => (
  <div className={`rounded-xl border border-white/10 px-4 py-3 text-center text-lg text-white ${tone} ${className}`}>{children}</div>
);
const Eq = ({ children }: { children: ReactNode }) => <div className="rounded-lg bg-black/25 px-4 py-2 font-mono text-xl text-cyan-100">{children}</div>;
const Arrow = () => <ArrowRight className="shrink-0 text-cyan-400" size={28} />;
const Loading = () => <div className="text-xl text-slate-300">Loading demonstration data from the backend…</div>;

function DemoSlide({ d, kicker, title, points }: { d: Demo | null; kicker: string; title: string; points: (a: Analysis) => ReactNode[] }) {
  if (!d) return <><Title kicker={kicker}>{title}</Title><Loading /></>;
  const a = d.a;
  return (
    <>
      <Title kicker={kicker}>{title}</Title>
      <div className="grid grid-cols-[1.1fr_1fr] gap-8">
        <div className="rounded-2xl bg-white p-3"><NetworkDiagram net={d.net} height={400} /></div>
        <div className="space-y-4">
          <div className="space-y-1">{a.equations.map((e) => <Eq key={e.junction_key}>{e.junction_name}: {e.text}</Eq>)}</div>
          <Bullets size="text-xl" items={points(a)} />
        </div>
      </div>
    </>
  );
}

const label = (a: Analysis) => ({ unique: "Unique solution", infinite: "Infinitely many solutions", none: "No solution" }[a.analysis.classification]);

/* ---------- slides ---------- */
interface SlideDef { title: string; notes: string; render: (d: Demos) => ReactNode }

const SLIDES: SlideDef[] = [
  { title: "Project Title", notes: "Introduce the project and the team. One sentence: we estimate unknown road traffic from a few sensors using Linear Algebra and Graph Theory.",
    render: () => (
      <div className="flex h-full flex-col items-center justify-center text-center">
        <div className="mb-6 rounded-full bg-cyan-400/20 px-5 py-1.5 text-sm font-semibold tracking-widest text-cyan-300">LINEAR ALGEBRA · GRAPH THEORY · DBMS</div>
        <h1 className="text-6xl font-extrabold leading-tight text-white">Traffic Flow<br />Network Analyzer</h1>
        <p className="mt-6 max-w-3xl text-2xl text-slate-300">Estimating unknown traffic flows with flow-conservation equations, row reduction and the null space</p>
        <p className="mt-10 text-lg text-slate-400">Team: {Object.values(JSON.parse(localStorage.getItem("tfna.team") ?? "{}")).filter(Boolean).join(", ") || "(add names on the Team page)"}</p>
      </div>) },
  { title: "Introduction", notes: "Cities have sensors on only some roads. Conservation of vehicles at junctions links the unmeasured roads to the measured ones.",
    render: () => (<><Title kicker="Introduction">Why traffic is a linear-algebra problem</Title>
      <div className="grid grid-cols-2 gap-10"><Bullets items={["Sensors exist only on some roads", "Vehicles are neither created nor destroyed at a junction", "Every junction gives one linear equation", "Solve the system → estimate the missing flows"]} />
        <div className="flex items-center justify-center"><div className="rounded-2xl bg-white p-4"><svg width="360" height="220" viewBox="0 0 360 220"><defs><marker id="ia" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#1d4ed8" /></marker></defs>
          <line x1="10" y1="110" x2="150" y2="110" stroke="#1d4ed8" strokeWidth="4" markerEnd="url(#ia)" /><text x="30" y="95" fontWeight="700" fill="#0891b2">in: 100</text>
          <circle cx="180" cy="110" r="30" fill="#0b1f3a" /><text x="180" y="116" textAnchor="middle" fill="white" fontWeight="700">J</text>
          <line x1="210" y1="95" x2="340" y2="40" stroke="#1d4ed8" strokeWidth="4" markerEnd="url(#ia)" /><text x="290" y="60" fontWeight="700">x₁</text>
          <line x1="210" y1="125" x2="340" y2="180" stroke="#1d4ed8" strokeWidth="4" markerEnd="url(#ia)" /><text x="290" y="175" fontWeight="700">x₂</text>
          <text x="180" y="210" textAnchor="middle" fontSize="15" fill="#0b1f3a">100 = x₁ + x₂</text></svg></div></div></div></>) },
  { title: "Problem Statement", notes: "State precisely: given external flows and some measured roads, find all assignments of the other roads.",
    render: () => (<><Title kicker="Problem">Problem statement</Title>
      <Bullets items={["Given: junctions, one-way roads, external inflow at junctions, measured flow on some roads", "Find: every flow assignment x on the unmeasured roads satisfying conservation", "Decide: unique? infinitely many? impossible?", "Check: are the flows physically feasible (all ≥ 0)?"]} />
      <div className="mt-8"><Eq>incoming + external inflow = outgoing   ⇒   AX = B</Eq></div></>) },
  { title: "Objectives", notes: "These objectives map one-to-one to the application modules you will see in the demo.",
    render: () => (<><Title kicker="Objectives">Objectives</Title><div className="grid grid-cols-2 gap-x-10">
      <Bullets size="text-xl" items={["Interactive directed network editor", "Automatic equations and matrices", "Step-by-step Gaussian & Gauss-Jordan", "Rank, pivots, free variables"]} />
      <Bullets size="text-xl" items={["General solution and null space", "Feasibility of nonnegative flows", "Adjacency lists, BFS, connectivity", "Database persistence and PDF reports"]} /></div></>) },
  { title: "Real-World Applications", notes: "The same equations model any conserved quantity moving on a network.",
    render: () => (<><Title kicker="Applications">Same mathematics, many networks</Title><div className="grid grid-cols-4 gap-5">
      {[["Road traffic", "vehicles / hour"], ["Water supply", "litres / second"], ["Computer networks", "packets / second"], ["Electric grids", "Kirchhoff's current law"]].map(([a, b]) => (
        <Box key={a} className="py-10"><div className="text-2xl font-bold">{a}</div><div className="mt-2 text-base text-cyan-200">{b}</div></Box>))}</div>
      <p className="mt-10 text-xl text-slate-300">Industrial pipelines, supply chains and data-centre traffic follow the same conservation law.</p></>) },
  { title: "Existing System and Proposed System", notes: "Contrast manual spreadsheets with our integrated tool.",
    render: () => (<><Title kicker="Comparison">Existing vs proposed system</Title><div className="grid grid-cols-2 gap-8">
      <div className="rounded-2xl bg-red-500/10 p-6"><h3 className="mb-3 text-2xl font-bold text-red-300">Existing</h3><Bullets size="text-xl" items={["Hand-written equations", "Error-prone manual elimination", "No record of steps", "Unknown roads are guessed"]} /></div>
      <div className="rounded-2xl bg-emerald-500/10 p-6"><h3 className="mb-3 text-2xl font-bold text-emerald-300">Proposed</h3><Bullets size="text-xl" items={["Draw the network; equations are generated", "Exact row reduction, every step shown", "Verified with SymPy, stored in a database", "Null space shows the possible alternatives"]} /></div></div></>) },
  { title: "Technology Stack", notes: "Mention why each tool: React Flow for the graph canvas, FastAPI for typed endpoints, SymPy only for verification.",
    render: () => (<><Title kicker="Stack">Technology stack</Title><div className="grid grid-cols-3 gap-6">
      {[["Frontend", "React · Vite · TypeScript · Tailwind CSS · React Flow · Recharts · Lucide"], ["Backend", "Python · FastAPI · Pydantic · SQLAlchemy · NumPy / SciPy · SymPy · ReportLab"], ["Data & Ops", "PostgreSQL · Pytest · Vitest · Vercel · Render"]].map(([h, t]) => (
        <Box key={h} className="py-8 text-left"><div className="mb-2 text-2xl font-bold text-cyan-300">{h}</div><div className="text-lg">{t}</div></Box>))}</div></>) },
  { title: "System Architecture", notes: "The browser sends the drawn network to the API. All mathematics is in the engine module so the UI, PDF and database always agree.",
    render: () => (<><Title kicker="Architecture">System architecture</Title>
      <div className="flex items-center justify-between gap-3">
        <Box className="w-52 py-6"><b>React UI</b><br /><span className="text-sm text-slate-300">React Flow editor<br />matrix & charts</span></Box><Arrow />
        <Box className="w-52 py-6"><b>FastAPI</b><br /><span className="text-sm text-slate-300">validation · REST</span></Box><Arrow />
        <div className="space-y-2"><Box className="w-60" tone="bg-brand-700">Linear-algebra engine</Box><Box className="w-60" tone="bg-brand-700">Graph / BFS engine</Box><Box className="w-60" tone="bg-brand-700">PDF report</Box></div><Arrow />
        <Box className="w-48 py-6"><b>SQLAlchemy</b><br /><span className="text-sm text-slate-300">→ PostgreSQL</span></Box></div>
      <p className="mt-10 text-xl text-slate-300">Draft network → <code className="text-cyan-300">POST /api/analyze</code> → equations, matrices, steps, solution, graph — all computed server-side.</p></>) },
  { title: "Mathematical Foundation", notes: "Walk through one junction. Then explain classification via rank.",
    render: () => (<><Title kicker="Mathematics">From traffic to AX = B</Title><div className="grid grid-cols-2 gap-8">
      <div className="space-y-4"><Eq>Σ in − Σ out = − external inflow</Eq><Eq>[A | B]  →  REF  →  RREF</Eq><Eq>rank A &lt; rank [A|B]  ⇒  no solution</Eq><Eq>rank A = n  ⇒  unique</Eq><Eq>rank A &lt; n  ⇒  ∞ many (n − rank free)</Eq></div>
      <Bullets size="text-xl" items={["One row per junction, one column per unknown road", "Entries: +1 into the junction, −1 out, 0 otherwise", "Known sensor flows move to B", "Exact arithmetic with rational numbers"]} /></div></>) },
  { title: "Graph Theory and DSA", notes: "BFS with a queue; adjacency lists; directed reachability is not the same as weak connectivity.",
    render: (d) => (<><Title kicker="Graph theory">Graphs, adjacency lists and BFS</Title><div className="grid grid-cols-2 gap-8">
      <Bullets size="text-xl" items={["Junction = vertex, road = directed edge", "Adjacency lists: O(V + E) memory", "BFS with a queue: O(V + E) time", "Directed reachability vs weak connectivity", "Isolated junctions and components"]} />
      <div className="rounded-xl bg-black/25 p-4 font-mono text-lg text-cyan-100">{d[2] ? <>
        {Object.entries(d[2].a.graph.adjacency_out).map(([k, v]) => <div key={k}>{k} → [{v.join(", ")}]</div>)}
        <div className="mt-3 text-slate-300">BFS from {d[2].a.graph.start}: {d[2].a.graph.bfs_directed?.order.join(" → ")}</div></> : <Loading />}</div></div></>) },
  { title: "Database Design", notes: "A road is known exactly when it has an observed_flows row. Cascading deletes keep the data consistent.",
    render: () => (<><Title kicker="DBMS">Database design (PostgreSQL)</Title>
      <div className="grid grid-cols-3 gap-4 text-base">
        {[["users", "id, username"], ["networks", "id, user_id →, name, description, timestamps"], ["junctions", "id, network_id →, key, name, x, y, external_inflow"], ["roads", "id, network_id →, source_id →, target_id →, label"], ["observed_flows", "id, road_id → (unique), value ≥ 0, measured_at"], ["solutions", "id, network_id →, classification, rank, free_variables, result (JSON)"]].map(([t, c]) => (
          <Box key={t} className="text-left"><div className="font-mono text-lg font-bold text-cyan-300">{t}</div><div className="mt-1 text-sm text-slate-300">{c}</div></Box>))}</div>
      <p className="mt-6 text-lg text-slate-300">Constraints: UNIQUE(network, key) · CHECK(source ≠ target) · CHECK(flow ≥ 0) · ON DELETE CASCADE</p></>) },
  { title: "Application Workflow", notes: "This is the demo script: follow these steps live.",
    render: () => (<><Title kicker="Workflow">Application workflow</Title><div className="flex flex-wrap items-center gap-3">
      {["Draw network", "Enter flows", "Equations", "Matrix [A|B]", "Row reduction", "Classify", "Null space", "Graph / BFS", "Save & report"].map((s, i, arr) => (
        <div key={s} className="flex items-center gap-3"><Box className="px-5 py-4 text-xl">{i + 1}. {s}</Box>{i < arr.length - 1 && <Arrow />}</div>))}</div></>) },
  { title: "Network 1 Demonstration", notes: "Open Network 1 in the solver. Sensor on A→C makes the system a tree of unknowns: unique solution.",
    render: (d) => <DemoSlide d={d[0]} kicker="Demonstration 1" title="Basic network — unique solution" points={(a) => [label(a), `rank ${a.analysis.rank} = ${a.analysis.n_unknowns} unknowns`, a.analysis.general_solution.map((g) => g.text).join(", ")]} /> },
  { title: "Network 2 Demonstration", notes: "One free variable: the extra flow x3 can circulate around A→B→C→A.",
    render: (d) => <DemoSlide d={d[1]} kicker="Demonstration 2" title="Intermediate network — one free variable" points={(a) => [label(a), `free variable: ${a.analysis.free_variables.join(", ")}`, a.analysis.general_solution.map((g) => g.text).join("; ")]} /> },
  { title: "Network 3 Demonstration", notes: "Five junctions, seven roads. Rank 4 with 6 unknowns leaves 2 parameters.",
    render: (d) => <DemoSlide d={d[2]} kicker="Demonstration 3" title="Advanced network — two free variables" points={(a) => [label(a), `rank ${a.analysis.rank}, nullity ${a.analysis.nullity}, free: ${a.analysis.free_variables.join(", ")}`, a.graph.strongly_connected ? "Strongly connected" : "Not strongly connected"]} /> },
  { title: "Mathematical Results", notes: "All numbers come from the live solver, not typed in. Point out the verification tick.",
    render: (d) => (<><Title kicker="Results">Results at a glance</Title>
      {d.every(Boolean) ? <table className="w-full text-left text-xl text-slate-100"><thead className="text-sm uppercase text-cyan-300"><tr><th className="py-2">Network</th><th>Unknowns</th><th>Rank</th><th>Nullity</th><th>Outcome</th><th>Verified</th></tr></thead><tbody>
        {d.map((x, i) => <tr key={i} className="border-t border-white/10"><td className="py-3">Network {i + 1}</td><td>{x!.a.analysis.n_unknowns}</td><td>{x!.a.analysis.rank}</td><td>{x!.a.analysis.nullity}</td><td>{label(x!.a)}</td><td>{x!.a.verification.all_passed ? "✔ AX=B, Av=0, SymPy" : "✘"}</td></tr>)}</tbody></table> : <Loading />}
      <p className="mt-8 text-lg text-slate-300">Rank + nullity = number of unknowns in every case.</p></>) },
  { title: "Null Space Explanation", notes: "Add the green/subtract the red along the cycle: every junction still balances. That is a circulation.",
    render: (d) => {
      const x = d[1]; const b = x?.a.analysis.null_basis[0];
      if (!x || !b) return <><Title kicker="Null space">Null space</Title><Loading /></>;
      const vars = x.a.matrix.variables; const keyBy = Object.fromEntries(x.a.variables.map((v) => [v.name, v.road_key]));
      const hl: Record<string, "pos" | "neg"> = {}, lab: Record<string, string> = {};
      b.vector.forEach((c, i) => { const n = toNumber(c); if (n !== 0) { hl[keyBy[vars[i]]] = n > 0 ? "pos" : "neg"; lab[keyBy[vars[i]]] = `${vars[i]} ${n > 0 ? "+" : ""}${c}`; } });
      return (<><Title kicker="Null space">AX = 0: traffic that circulates</Title><div className="grid grid-cols-[1.1fr_1fr] gap-8">
        <div className="rounded-2xl bg-white p-3"><NetworkDiagram net={x.net} highlight={hl} edgeLabels={lab} dim height={380} showExternal={false} /></div>
        <div className="space-y-4"><div className="flex items-center gap-4 text-white"><Matrix light data={vars.map((_, i) => [b.vector[i]])} /><span className="text-lg">= basis vector v (Network 2)</span></div>
          <Bullets size="text-xl" items={["A·v = 0: no junction gains or loses cars", "Add t·v to any solution → another solution", "x = x_particular + t·v  gives all solutions", "Feasible only while all flows stay ≥ 0"]} /></div></div></>);
    } },
  { title: "Testing and Validation", notes: "Run the pytest suite live if time permits. Emphasise exact arithmetic.",
    render: () => (<><Title kicker="Quality">Testing and validation</Title><div className="grid grid-cols-2 gap-8">
      <Bullets size="text-xl" items={["Unique / infinite / inconsistent systems", "Under- and over-determined systems", "Disconnected networks, isolated junctions", "Negative-flow infeasibility", "Database persistence and API integration"]} />
      <div className="space-y-4"><Eq>AX = B  (exact Fractions)</Eq><Eq>A·v = 0 for every null-space basis vector</Eq><Eq>rref, rank, nullspace == SymPy</Eq><p className="text-lg text-slate-300">Pytest (backend) and Vitest (frontend). Demo networks were built from known ground-truth flows.</p></div></div></>) },
  { title: "Team Contributions", notes: "Each member presents their own column.",
    render: () => (<><Title kicker="Team">Team contributions</Title><div className="grid grid-cols-5 gap-3">
      {ROLES.map((r, i) => { const n = (() => { try { return JSON.parse(localStorage.getItem("tfna.team") ?? "{}")[r.id]; } catch { return ""; } })();
        return <Box key={r.id} className="text-left"><div className="text-sm font-semibold text-cyan-300">Role {i + 1}</div><div className="my-1 text-lg font-bold leading-tight">{r.short}</div>
          <div className="text-sm text-slate-300">{n || "(member name)"}</div></Box>; })}</div></>) },
  { title: "Limitations and Future Scope", notes: "Be honest about limits.",
    render: () => (<><Title kicker="Next steps">Limitations and future scope</Title><div className="grid grid-cols-2 gap-8">
      <div><h3 className="mb-3 text-2xl font-bold text-amber-300">Limitations</h3><Bullets size="text-xl" items={["Steady-state flows only", "No road capacities or travel time", "No user authentication", "Feasibility ranges use floating-point LP"]} /></div>
      <div><h3 className="mb-3 text-2xl font-bold text-emerald-300">Future scope</h3><Bullets size="text-xl" items={["Capacities and min-cost flow", "Noisy sensors: least squares", "Time-series data", "Import real road maps"]} /></div></div></>) },
  { title: "Conclusion", notes: "Close by restating the integration of the subjects.",
    render: () => (<div className="flex h-full flex-col justify-center"><Title kicker="Conclusion">Conclusion</Title>
      <Bullets items={["Junction conservation turns traffic into AX = B", "Row reduction classifies the system and exposes free variables", "The null space explains alternative flows as circulations", "BFS, a relational database and a verified full-stack app complete the solution"]} />
      <p className="mt-10 text-3xl font-semibold text-cyan-300">Thank you — questions?</p></div>) },
];

export default function PresentationMode() {
  const [i, setI] = useState(() => Math.min(SLIDES.length - 1, Math.max(0, Number(sessionStorage.getItem("tfna.slide") ?? 0))));
  const [scale, setScale] = useState(1);
  const [full, setFull] = useState(false);
  const [portrait, setPortrait] = useState(false);          // narrow portrait screen: slide is tiny -> show a rotate hint
  const touch = useRef<{ x: number; y: number } | null>(null); // swipe start
  const canFull = typeof document !== "undefined" && !!document.fullscreenEnabled; // iPhone Safari has no Fullscreen API
  const [notes, setNotes] = useState(false);
  const [demos, setDemos] = useState<Demos>([null, null, null]);
  const root = useRef<HTMLDivElement>(null);

  // Load the three demonstration networks and analyse them with the real backend.
  useEffect(() => {
    (async () => {
      try {
        const list = await api.listNetworks();
        const out: Demos = [null, null, null];
        for (let n = 1; n <= 3; n++) {
          const s = list.find((x) => x.is_demo && x.name.startsWith(`Network ${n}`));
          if (s) { const net = await api.getNetwork(s.id); out[n - 1] = { net, a: await api.analyze(net, {}, undefined) }; }
        }
        setDemos(out);
      } catch { /* slides show a loading note */ }
    })();
  }, []);

  useEffect(() => { try { sessionStorage.setItem("tfna.slide", String(i)); } catch { /* ignore */ } }, [i]);
  useEffect(() => {
    const f = () => {
      const pt = window.innerWidth < 700 && window.innerHeight > window.innerWidth;
      setPortrait(pt);
      setScale(Math.min(window.innerWidth / W, (window.innerHeight - (notes ? 160 : 60) - (pt ? 34 : 0)) / H));
    };
    f(); window.addEventListener("resize", f); return () => window.removeEventListener("resize", f);
  }, [notes]);
  useEffect(() => {
    const f = () => setFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", f); return () => document.removeEventListener("fullscreenchange", f);
  }, []);

  const go = useCallback((d: number) => setI((x) => Math.min(SLIDES.length - 1, Math.max(0, x + d))), []);
  const toggleFull = useCallback(() => { if (document.fullscreenElement) document.exitFullscreen(); else root.current?.requestFullscreen?.(); }, []);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (["ArrowRight", "PageDown", " ", "Enter"].includes(e.key)) { e.preventDefault(); go(1); }
      else if (["ArrowLeft", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); go(-1); }
      else if (e.key === "Home") setI(0); else if (e.key === "End") setI(SLIDES.length - 1);
      else if (e.key.toLowerCase() === "f") toggleFull(); else if (e.key.toLowerCase() === "n") setNotes((v) => !v);
    };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, [go, toggleFull]);

  const slide = SLIDES[i];
  const content = useMemo(() => slide.render(demos), [slide, demos]);
  return (
    <div ref={root} className="flex h-dvh flex-col bg-navy-950 text-white" data-testid="presentation"
      onTouchStart={(e) => { touch.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }; }}
      onTouchEnd={(e) => {
        const t = touch.current; touch.current = null; if (!t) return;
        const dx = e.changedTouches[0].clientX - t.x, dy = e.changedTouches[0].clientY - t.y;
        if (Math.abs(dx) > 50 && Math.abs(dy) < 60) go(dx < 0 ? 1 : -1);      // swipe left = next, right = previous
      }}>
      {portrait && <div className="bg-cyan-400/15 px-3 py-1.5 text-center text-xs text-cyan-200">Tip: rotate your phone to landscape for a larger slide. Swipe left/right to change slides.</div>}
      <div className="flex flex-1 items-center justify-center overflow-hidden">
        <div style={{ width: W, height: H, transform: `scale(${scale})`, flex: "none" }} key={i}
          className="fade-up relative overflow-hidden rounded-2xl bg-gradient-to-br from-navy-900 to-navy-950 p-14 shadow-2xl" role="region" aria-label={`Slide ${i + 1}: ${slide.title}`}>
          {content}
          <div className="absolute bottom-4 right-6 text-sm text-slate-500">{i + 1} / {SLIDES.length}</div>
        </div>
      </div>
      {notes && <div className="max-h-28 overflow-y-auto border-t border-white/10 bg-navy-900 px-6 py-3 text-sm text-slate-200"><b className="text-cyan-300">Presenter notes — {slide.title}: </b>{slide.notes}</div>}
      <div className="safe-bottom safe-x flex items-center gap-1 border-t border-white/10 bg-navy-900 px-2 py-2 text-sm sm:gap-2 sm:px-4">
        <Link to="/" className="flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-white/10" aria-label="Exit presentation"><Home size={16} /><span className="hidden sm:inline">Exit</span></Link>
        <button className="rounded-lg p-1.5 hover:bg-white/10 disabled:opacity-30" disabled={i === 0} onClick={() => go(-1)} aria-label="Previous slide"><ChevronLeft /></button>
        <select aria-label="Jump to slide" className="min-w-0 flex-1 rounded bg-navy-800 px-2 py-1 sm:max-w-[16rem] sm:flex-none" value={i} onChange={(e) => setI(Number(e.target.value))}>
          {SLIDES.map((s, k) => <option key={k} value={k}>{k + 1}. {s.title}</option>)}</select>
        <button className="rounded-lg p-1.5 hover:bg-white/10 disabled:opacity-30" disabled={i === SLIDES.length - 1} onClick={() => go(1)} aria-label="Next slide"><ChevronRight /></button>
        <span className="ml-2 hidden whitespace-nowrap text-slate-400 lg:inline">← → space · F fullscreen · N notes</span>
        <button className="ml-auto flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-white/10" aria-label="Toggle presenter notes" onClick={() => setNotes(!notes)}><StickyNote size={16} /><span className="hidden sm:inline">Notes</span></button>
        {canFull && <button className="flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-white/10" aria-label={full ? "Exit full screen" : "Full screen"} onClick={toggleFull}>{full ? <Minimize size={16} /> : <Maximize size={16} />}<span className="hidden whitespace-nowrap sm:inline">{full ? "Exit full screen" : "Full screen"}</span></button>}
      </div>
    </div>
  );
}

export const SLIDE_COUNT = SLIDES.length;
