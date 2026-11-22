import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import { emptyNetwork } from "./network";
import type { Analysis, NetworkDraft } from "./types";

/** App-wide "current network" (the draft being edited/analysed). Persisted in localStorage per browser. */
interface Ctx {
  net: NetworkDraft; setNet: (n: NetworkDraft) => void; dirty: boolean;
  save: () => Promise<NetworkDraft>; load: (id: number) => Promise<void>; reset: () => void;
  params: Record<string, string>; setParams: (p: Record<string, string>) => void;
  analysis: Analysis | null; analysisError: string | null; loading: boolean; refresh: () => void;
}
const C = createContext<Ctx>(null as unknown as Ctx);
export const useNetwork = () => useContext(C);
const KEY = "tfna.draft";

export function NetworkProvider({ children }: { children: ReactNode }) {
  const [net, setNetRaw] = useState<NetworkDraft>(() => {
    try { const s = localStorage.getItem(KEY); if (s) return JSON.parse(s); } catch { /* ignore */ }
    return emptyNetwork();
  });
  const [dirty, setDirty] = useState(false);
  const [params, setParams] = useState<Record<string, string>>({});
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisError, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);

  // First visit (empty draft): load the first saved network so every page works immediately.
  useEffect(() => {
    if (net.junctions.length) return;
    api.listNetworks().then((l) => (l[l.length - 1] ? api.getNetwork(l[l.length - 1].id) : null))
      .then((n) => { if (n) { setNetRaw(n); setDirty(false); } }).catch(() => { /* backend offline: pages show their own error */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setNet = useCallback((n: NetworkDraft) => { setNetRaw(n); setDirty(true); }, []);
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(net)); } catch { /* ignore */ } }, [net]);

  // Re-run the real backend analysis whenever the network or chosen parameters change (debounced).
  useEffect(() => {
    if (net.junctions.length === 0) { setAnalysis(null); setErr(null); return; }
    const h = setTimeout(async () => {
      setLoading(true);
      try { setAnalysis(await api.analyze(net, params)); setErr(null); }
      catch (e: any) { setErr(e.message); setAnalysis(null); }
      finally { setLoading(false); }
    }, 350);
    return () => clearTimeout(h);
  }, [net, params, tick]);

  const save = useCallback(async () => {
    // Demo networks are read-only on the server: saving one stores an independent copy.
    const toSave = net.is_demo ? { ...net, id: undefined, is_demo: false, name: `${net.name} (copy)` } : net;
    const saved = await api.saveNetwork(toSave);
    setNetRaw(saved); setDirty(false);
    return saved;
  }, [net]);
  const load = useCallback(async (id: number) => {
    setNetRaw(await api.getNetwork(id)); setDirty(false); setParams({});
  }, []);
  const reset = useCallback(() => { setNetRaw(emptyNetwork()); setDirty(false); setParams({}); }, []);

  const value = useMemo(() => ({ net, setNet, dirty, save, load, reset, params, setParams, analysis, analysisError, loading,
    refresh: () => setTick(t => t + 1) }), [net, setNet, dirty, save, load, reset, params, analysis, analysisError, loading]);
  return <C.Provider value={value}>{children}</C.Provider>;
}
