import type { NetworkDraft } from "./types";

/** Unknown roads are numbered x1, x2, ... in road order (mirrors the backend rule). */
export function variableNames(n: NetworkDraft): Record<string, string> {
  const out: Record<string, string> = {};
  let k = 0;
  for (const r of n.roads) if (r.known_flow === null || r.known_flow === "") out[r.key] = `x${++k}`;
  return out;
}

export function emptyNetwork(): NetworkDraft {
  return { name: "Untitled network", description: "", junctions: [], roads: [] };
}

export function nextKey(prefix: string, existing: string[]): string {
  let i = existing.length + 1;
  while (existing.includes(`${prefix}${i}`)) i++;
  return `${prefix}${i}`;
}

/** Parse "7/2", "-3.5", "12" -> number (for display only; the backend is exact). */
export function toNumber(s: string): number {
  if (s.includes("/")) { const [a, b] = s.split("/"); return Number(a) / Number(b); }
  return Number(s);
}

/** Total of all external flows: for a closed (balanced) system this must be 0 when all roads are unknown-free. */
export function externalBalance(n: NetworkDraft): number {
  return n.junctions.reduce((s, j) => s + (Number(j.external_inflow) || 0), 0);
}
