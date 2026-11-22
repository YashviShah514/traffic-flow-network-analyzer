import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, PageHeader } from "@/components/ui/ui";
import { api } from "@/lib/api";
import { useNetwork } from "@/lib/store";

export default function Settings() {
  const [dark, setDark] = useState(document.documentElement.classList.contains("dark"));
  const [health, setHealth] = useState<string>("checking...");
  const { reset } = useNetwork();
  useEffect(() => { api.dashboard().then(() => setHealth("connected")).catch((e) => setHealth(e.message)); }, []);
  const toggle = () => {
    const v = !dark; setDark(v);
    document.documentElement.classList.toggle("dark", v);
    try { localStorage.setItem("tfna.dark", v ? "1" : "0"); } catch { /* ignore */ }
  };
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid max-w-3xl gap-4">
        <Card><CardHeader><CardTitle>Appearance</CardTitle></CardHeader><CardContent>
          <Button variant="outline" onClick={toggle}>{dark ? "Switch to light theme" : "Switch to dark theme"}</Button>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Backend connection</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
          <div>API base URL: <code className="rounded bg-slate-100 px-1 dark:bg-navy-800">{(import.meta.env.VITE_API_URL as string) || "(same origin / Vite proxy)"}</code></div>
          <div>Status: <Badge tone={health === "connected" ? "green" : "red"}>{health}</Badge></div>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Working draft</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
          <p>The network you are editing is also cached in this browser. Saved networks live in the database.</p>
          <Button variant="destructive" onClick={() => { if (confirm("Discard the current draft?")) reset(); }}>Discard current draft</Button>
        </CardContent></Card>
        <Alert tone="info">Authentication is not implemented: all networks belong to a single default <b>demo</b> user (the <code>users</code> table exists for future multi-user support).</Alert>
      </div>
    </>
  );
}
