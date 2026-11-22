import type { NetworkDraft } from "@/lib/types";
import { variableNames } from "@/lib/network";

/** Static SVG renderer for a network (used by presentation slides and circulation view).
 *  `edgeLabels` overrides labels by road key; `highlight` colours roads (e.g. circulation). */
export function NetworkDiagram({ net, edgeLabels, highlight, dim = false, height = 280, showExternal = true }: {
  net: NetworkDraft; edgeLabels?: Record<string, string>; highlight?: Record<string, "pos" | "neg">;
  dim?: boolean; height?: number; showExternal?: boolean;
}) {
  if (!net.junctions.length) return <div className="text-sm text-slate-400">No junctions</div>;
  const names = variableNames(net);
  const xs = net.junctions.map((j) => j.x), ys = net.junctions.map((j) => j.y);
  const minX = Math.min(...xs) - 50, maxX = Math.max(...xs) + 50, minY = Math.min(...ys) - 50, maxY = Math.max(...ys) + 60;
  const W = maxX - minX, H = maxY - minY;
  const pos = Object.fromEntries(net.junctions.map((j) => [j.key, { x: j.x - minX, y: j.y - minY }]));
  const R = 20;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ height }} className="w-full" role="img" aria-label={`Diagram of ${net.name}`}>
      <defs>
        {[["a", "#1d4ed8"], ["p", "#059669"], ["n", "#dc2626"], ["d", "#94a3b8"]].map(([id, c]) => (
          <marker key={id} id={`arr-${id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" fill={c} />
          </marker>
        ))}
      </defs>
      {net.roads.map((r) => {
        const a = pos[r.source], b = pos[r.target];
        if (!a || !b) return null;
        const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
        const ux = dx / len, uy = dy / len;
        // slight perpendicular offset so opposite roads do not overlap
        const ox = -uy * 6, oy = ux * 6;
        const x1 = a.x + ux * R + ox, y1 = a.y + uy * R + oy, x2 = b.x - ux * (R + 4) + ox, y2 = b.y - uy * (R + 4) + oy;
        const h = highlight?.[r.key];
        const col = h === "pos" ? "#059669" : h === "neg" ? "#dc2626" : dim ? "#94a3b8" : "#1d4ed8";
        const marker = h === "pos" ? "p" : h === "neg" ? "n" : dim ? "d" : "a";
        const label = edgeLabels?.[r.key] ?? (r.known_flow ? r.known_flow : names[r.key]);
        return (
          <g key={r.key}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={col} strokeWidth={h ? 3.5 : 2.2} markerEnd={`url(#arr-${marker})`} />
            <text x={(x1 + x2) / 2 + ox * 1.6} y={(y1 + y2) / 2 + oy * 1.6 - 2} fontSize="13" fontWeight="600" textAnchor="middle"
              fill={r.known_flow ? "#0e7490" : col} stroke="white" strokeWidth="3" paintOrder="stroke">{label}</text>
          </g>
        );
      })}
      {net.junctions.map((j) => {
        const p = pos[j.key];
        const ext = Number(j.external_inflow);
        return (
          <g key={j.key}>
            <circle cx={p.x} cy={p.y} r={R} fill="#0b1f3a" />
            <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize="12" fontWeight="700" fill="white">{j.name.slice(0, 4)}</text>
            {showExternal && ext !== 0 && (
              <text x={p.x} y={p.y + R + 16} textAnchor="middle" fontSize="12" fontWeight="600" fill="#0891b2">
                {ext > 0 ? `+${ext} in` : `${-ext} out`}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
