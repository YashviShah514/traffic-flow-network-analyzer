import { useEffect, useState } from "react";
import { Badge, Card, CardContent, CardHeader, CardTitle, Input, Label, PageHeader } from "@/components/ui/ui";
import { ROLES } from "@/content/roles";

const KEY = "tfna.team";

export default function Team() {
  const [names, setNames] = useState<Record<string, string>>(() => { try { return JSON.parse(localStorage.getItem(KEY) ?? "{}"); } catch { return {}; } });
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(names)); } catch { /* ignore */ } }, [names]);
  return (
    <>
      <PageHeader title="Team Contributions" subtitle="Five workstreams. Enter the real team member for each (stored in this browser only). 'Delivered in this codebase' lists real files." />
      <div className="space-y-6">
        {ROLES.map((r) => (
          <Card key={r.id}>
            <CardHeader className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle className="text-lg">{r.name}</CardTitle>
              <div className="w-64"><Label htmlFor={`m-${r.id}`}>Assigned team member</Label>
                <Input id={`m-${r.id}`} placeholder="Enter name…" value={names[r.id] ?? ""} onChange={(e) => setNames({ ...names, [r.id]: e.target.value })} /></div>
            </CardHeader>
            <CardContent className="grid gap-5 text-sm md:grid-cols-2">
              <div><h4 className="mb-1 font-semibold">Responsibilities</h4><ul className="list-disc pl-5">{r.responsibilities.map((x) => <li key={x}>{x}</li>)}</ul></div>
              <div><h4 className="mb-1 font-semibold">Technologies</h4><div className="flex flex-wrap gap-1.5">{r.tech.map((t) => <Badge key={t} tone="blue">{t}</Badge>)}</div>
                <h4 className="mb-1 mt-4 font-semibold">Delivered in this codebase</h4><ul className="list-disc pl-5">{r.delivered.map((x) => <li key={x}>{x}</li>)}</ul></div>
              <div className="md:col-span-2"><h4 className="mb-1 font-semibold">Module explanation</h4><p className="text-slate-600 dark:text-slate-300">{r.module}</p></div>
              <div><h4 className="mb-1 font-semibold">Presentation talking points</h4><ul className="list-disc pl-5">{r.talking.map((x) => <li key={x}>{x}</li>)}</ul></div>
              <div><h4 className="mb-1 font-semibold">Likely viva questions</h4><ul className="list-disc pl-5">{r.viva.map((x) => <li key={x}>{x}</li>)}</ul></div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
