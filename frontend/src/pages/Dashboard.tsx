import { Activity, GitBranch, Plus, Route as RoadIcon, Sigma, Waypoints } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, PageHeader } from "@/components/ui/ui";
import { api } from "@/lib/api";
import type { Dashboard as D } from "@/lib/types";

function Stat({ icon: Icon, label, value, tone }: { icon: any; label: string; value: number; tone: string }) {
  return (
    <Card><CardContent className="flex items-center gap-4 pt-5">
      <div className={`grid h-11 w-11 place-items-center rounded-xl ${tone}`}><Icon size={22} /></div>
      <div><div className="text-2xl font-bold">{value}</div><div className="text-xs text-slate-500">{label}</div></div>
    </CardContent></Card>
  );
}

export default function Dashboard() {
  const [d, setD] = useState<D | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.dashboard().then(setD).catch((e) => setErr(e.message)); }, []);
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Live statistics read from the database."
        actions={<Link to="/builder"><Button><Plus size={16} />Quick create network</Button></Link>} />
      {err && <Alert tone="error">{err}</Alert>}
      {d && (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Stat icon={Waypoints} label="Total networks" value={d.total_networks} tone="bg-brand-100 text-brand-700" />
            <Stat icon={GitBranch} label="Total junctions" value={d.total_junctions} tone="bg-cyan2-100 text-cyan-800" />
            <Stat icon={RoadIcon} label="Total roads" value={d.total_roads} tone="bg-brand-100 text-brand-700" />
            <Stat icon={Sigma} label="Solved networks" value={d.solved_networks} tone="bg-emerald-100 text-emerald-700" />
            <Stat icon={Activity} label="With free variables" value={d.networks_with_free_variables} tone="bg-amber-100 text-amber-700" />
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader><CardTitle>Network size</CardTitle></CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer>
                    <BarChart data={d.per_network.map((n) => ({ ...n, name: n.name.split(" - ")[0] }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="name" fontSize={12} /><YAxis allowDecimals={false} fontSize={12} />
                      <Tooltip /><Legend />
                      <Bar dataKey="junctions" fill="#0b1f3a" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="roads" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Recent activity</CardTitle></CardHeader>
              <CardContent>
                <ul className="space-y-3 text-sm">
                  {d.recent_activity.length === 0 && <li className="text-slate-500">Nothing yet.</li>}
                  {d.recent_activity.map((a, i) => (
                    <li key={i} className="flex gap-2"><span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${a.type === "solution" ? "bg-emerald-500" : "bg-brand-500"}`} />
                      <div><div className="font-medium">{a.title}</div>
                        <div className="text-xs text-slate-500">{a.type === "solution" ? `classification: ${a.detail} · ` : "saved · "}{new Date(a.at).toLocaleString()}</div></div></li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader><CardTitle>Project overview</CardTitle></CardHeader>
            <CardContent className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">
              At every junction the traffic entering must equal the traffic leaving. Each junction therefore gives one linear
              equation; sensors fix some road flows and the rest become unknowns. Row reduction (Gaussian / Gauss-Jordan) on the
              augmented matrix [A | B] classifies the system, exposes free variables and the null space (circulating traffic), and
              breadth-first search analyses connectivity. Classification so far:{" "}
              {Object.entries(d.classification_counts).map(([k, v]) => `${k}: ${v}`).join(", ")}.
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
