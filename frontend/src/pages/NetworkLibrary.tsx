import { FolderOpen, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Badge, Button, Card, CardContent, PageHeader } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { useNetwork } from "@/lib/store";
import type { NetworkSummary } from "@/lib/types";

const TONE: Record<string, "green" | "amber" | "red"> = { unique: "green", infinite: "amber", none: "red" };
const LABEL: Record<string, string> = { unique: "Unique", infinite: "Infinite solutions", none: "No solution" };

export default function NetworkLibrary() {
  const [list, setList] = useState<NetworkSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { load } = useNetwork();
  const nav = useNavigate();
  const refresh = () => api.listNetworks().then(setList).catch((e) => setErr(e.message));
  useEffect(() => { refresh(); }, []);

  const open = async (id: number, to: string) => { try { await load(id); nav(to); } catch (e: any) { setErr(e.message); } };
  const del = async (n: NetworkSummary) => {
    if (!confirm(`Delete "${n.name}" and its stored solutions?`)) return;
    try { await api.deleteNetwork(n.id); refresh(); } catch (e: any) { setErr(e.message); }
  };
  return (
    <>
      <PageHeader title="Network Library" subtitle="Every network saved in the database. Open one to edit it or send it to the solver." />
      {err && <Alert tone="error">{err}</Alert>}
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {list?.map((n) => (
          <Card key={n.id}><CardContent className="pt-5">
            <div className="mb-2 flex items-start justify-between gap-2">
              <h3 className="font-semibold">{n.name}</h3>
              {n.is_demo && <Badge tone="cyan">Demo</Badge>}
            </div>
            <p className="mb-3 min-h-[2.5rem] text-sm text-slate-500">{n.description}</p>
            <div className="mb-4 flex flex-wrap gap-2 text-xs">
              <Badge tone="blue">{n.junctions} junctions</Badge><Badge tone="blue">{n.roads} roads</Badge>
              {n.classification && <Badge tone={TONE[n.classification]}>{LABEL[n.classification]} · rank {n.rank}</Badge>}
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => open(n.id, "/builder")}><FolderOpen size={14} />Edit</Button>
              <Button size="sm" variant="outline" onClick={() => open(n.id, "/solver")}>Solve</Button>
              <Button size="sm" variant="ghost" className="ml-auto text-red-600" aria-label={`Delete ${n.name}`} onClick={() => del(n)}><Trash2 size={14} /></Button>
            </div>
          </CardContent></Card>
        ))}
        {list?.length === 0 && <p className="text-slate-500">No networks saved yet.</p>}
      </div>
    </>
  );
}
