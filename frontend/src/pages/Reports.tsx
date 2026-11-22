import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, PageHeader } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { useNetwork } from "@/lib/store";
import { download } from "@/lib/utils";
import { NeedNetwork } from "./Solver";

export default function Reports() {
  const { net, params, analysis } = useNetwork();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  useEffect(() => { api.allSolutions().then(setHistory).catch((e) => setErr(e.message)); }, []);

  const make = async () => {
    setBusy(true); setErr(null);
    try { download(await api.report(net, params), `${net.name.replace(/[^\w]+/g, "_")}_report.pdf`); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHeader title="Solution Reports" subtitle="Generate a PDF with the diagram, equations, matrices, REF/RREF, row operations, solution, null space, feasibility and conclusion." />
      {err && <Alert tone="error">{err}</Alert>}
      {!net.junctions.length ? <NeedNetwork /> : (
        <Card className="mb-6"><CardContent className="flex flex-wrap items-center gap-4 pt-5">
          <div className="min-w-0 flex-1"><div className="font-semibold">{net.name}</div>
            <div className="text-sm text-slate-500">{analysis ? `${analysis.analysis.classification} · rank ${analysis.analysis.rank} · parameters: ${Object.entries(params).map(([k, v]) => `${k}=${v}`).join(", ") || "defaults"}` : "analysing…"}</div></div>
          <Button onClick={make} disabled={busy || !analysis}><Download size={16} />{busy ? "Generating…" : "Download PDF report"}</Button>
        </CardContent></Card>
      )}
      <Card><CardHeader><CardTitle>Stored solutions (database)</CardTitle></CardHeader><CardContent>
        {history.length === 0 ? <p className="text-sm text-slate-500">No stored solutions yet. Use "Store solution in database" in the solver.</p> : (
          <table className="w-full text-sm"><thead><tr className="text-left text-xs text-slate-500"><th>Network</th><th>Result</th><th>Rank</th><th>Free variables</th><th>Stored</th></tr></thead><tbody>
            {history.map((s) => <tr key={s.id} className="border-t border-slate-100 dark:border-navy-700"><td className="py-1.5">{s.network}</td>
              <td><Badge tone={s.classification === "unique" ? "green" : s.classification === "infinite" ? "amber" : "red"}>{s.classification}</Badge></td>
              <td>{s.rank}</td><td className="eq">{s.free_variables.join(", ") || "—"}</td><td className="text-slate-500">{new Date(s.created_at).toLocaleString()}</td></tr>)}
          </tbody></table>)}
      </CardContent></Card>
    </>
  );
}
