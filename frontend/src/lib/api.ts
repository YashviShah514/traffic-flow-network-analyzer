import type { Analysis, Dashboard, NetworkDraft, NetworkSummary } from "./types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new ApiError("Cannot reach the backend. Is the FastAPI server running on port 8000?");
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : body.detail?.map((d: any) => `${d.loc?.slice(-1)}: ${d.msg}`).join("; ") ?? msg;
    } catch { /* ignore */ }
    throw new ApiError(msg);
  }
  if (res.status === 204) return undefined as T;
  if (res.headers.get("content-type")?.includes("application/pdf")) return (await res.blob()) as T;
  return res.json();
}

const body = (o: unknown) => JSON.stringify(o);
const strip = ({ id, is_demo, ...rest }: NetworkDraft & { created_at?: string; updated_at?: string }) => {
  const { created_at, updated_at, ...net } = rest as any;
  return net;
};

export const api = {
  dashboard: () => req<Dashboard>("/api/dashboard"),
  listNetworks: () => req<NetworkSummary[]>("/api/networks"),
  getNetwork: (id: number) => req<NetworkDraft>(`/api/networks/${id}`),
  saveNetwork: (n: NetworkDraft) =>
    n.id ? req<NetworkDraft>(`/api/networks/${n.id}`, { method: "PUT", body: body(strip(n)) })
         : req<NetworkDraft>("/api/networks", { method: "POST", body: body(strip(n)) }),
  deleteNetwork: (id: number) => req<void>(`/api/networks/${id}`, { method: "DELETE" }),
  analyze: (n: NetworkDraft, parameters: Record<string, string> = {}, start?: string) =>
    req<Analysis>("/api/analyze", { method: "POST", body: body({ network: strip(n), parameters, start_junction: start ?? null }) }),
  storeSolution: (id: number, parameters: Record<string, string>) =>
    req<{ id: number }>(`/api/networks/${id}/solutions`, { method: "POST", body: body({ parameters }) }),
  solutions: (id: number) => req<any[]>(`/api/networks/${id}/solutions`),
  allSolutions: () => req<any[]>("/api/solutions"),
  report: (n: NetworkDraft, parameters: Record<string, string> = {}) =>
    req<Blob>("/api/report", { method: "POST", body: body({ network: strip(n), parameters }) }),
};
