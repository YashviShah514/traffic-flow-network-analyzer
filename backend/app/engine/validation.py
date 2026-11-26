"""Network validation report. Lists EVERY problem; nothing is silently dropped.

``error``   -> the solver will not run.
``warning`` -> the solver runs, but the result needs attention.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from ..graph.analysis import build_adjacency, weak_components
from .linalg import fmt


def parse_number(v) -> Fraction | None:
    """None/'' -> None. Raises ValueError for anything that is not a finite number with <= 6 decimals."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        f = Fraction(str(v).strip())
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"'{v}' is not a valid number")
    if f.denominator > 10**6:
        raise ValueError("use at most 6 decimal places")
    return f


def validate_network(junctions: list[dict], roads: list[dict]) -> dict:
    """``junctions``: {key,name,net_demand}; ``roads``: {key,source,target,label,known_flow} (raw values)."""
    errors: list[dict] = []
    warnings: list[dict] = []

    def err(code, message, item=None):
        errors.append({"code": code, "message": message, "item": item})

    def warn(code, message, item=None):
        warnings.append({"code": code, "message": message, "item": item})

    if not junctions:
        err("empty", "The network has no junctions yet.")
    for key, n in Counter(j["key"] for j in junctions).items():
        if n > 1:
            err("duplicate_junction_id", f"Junction ID '{key}' is used {n} times.", key)
    for key, n in Counter(r["key"] for r in roads).items():
        if n > 1:
            err("duplicate_road_id", f"Road ID '{key}' is used {n} times.", key)

    names = {j["key"]: j.get("name") or j["key"] for j in junctions}
    demand: dict[str, Fraction] = {}
    for j in junctions:
        try:
            demand[j["key"]] = parse_number(j.get("net_demand")) or Fraction(0)
        except ValueError as e:
            err("invalid_demand", f"Junction {names[j['key']]}: net external demand {e}.", j["key"])
            demand[j["key"]] = Fraction(0)

    valid_edges: list[tuple[str, str]] = []
    for r in roads:
        src, dst = r.get("source"), r.get("target")
        where = f"Road {r.get('label') or r['key']}"
        if not src or not dst:
            err("missing_endpoint", f"{where} is missing a start or end junction.", r["key"])
            continue
        if src not in names or dst not in names:
            err("invalid_edge", f"{where} points to a junction that does not exist.", r["key"])
            continue
        if src == dst:
            err("self_loop", f"{where} starts and ends at the same junction ({names[src]}).", r["key"])
            continue
        try:
            flow = parse_number(r.get("known_flow"))
            if flow is not None and flow < 0:
                err("negative_flow", f"{where}: a measured flow cannot be negative ({fmt(flow)}).", r["key"])
        except ValueError as e:
            err("invalid_flow", f"{where}: flow value {e}.", r["key"])
        valid_edges.append((src, dst))

    for (s, t), n in Counter(valid_edges).items():
        if n > 1:
            warn("parallel_roads", f"{n} roads run from {names[s]} to {names[t]} (treated as parallel roads).")

    keys = list(names)
    components: list[list[str]] = []
    if keys:
        out_adj, in_adj, und = build_adjacency(keys, valid_edges)
        components = weak_components(keys, und)
        for k in keys:
            if not und[k]:
                warn("isolated_junction", f"Junction {names[k]} is isolated (no roads).", k)
        if len(components) > 1:
            warn("disconnected", f"The network has {len(components)} disconnected parts; each balances independently.")
        # Summing all equations of one component cancels every road, so the demands must total zero.
        # Roads (known or unknown) have both ends inside a component, hence this holds exactly.
        for i, comp in enumerate(components, 1):
            total = sum((demand.get(k, Fraction(0)) for k in comp), Fraction(0))
            if total != 0:
                members = ", ".join(names[k] for k in comp[:6]) + (" …" if len(comp) > 6 else "")
                warn("unbalanced_demand",
                     f"Part {i} ({members}): net external demands add to {fmt(total)} instead of 0, "
                     "so no flow assignment can satisfy every junction.")
        sinks = [names[k] for k in keys if in_adj[k] and not out_adj[k] and demand.get(k, 0) == 0]
        sources = [names[k] for k in keys if out_adj[k] and not in_adj[k] and demand.get(k, 0) == 0]
        if sinks or sources:
            some = (sinks + sources)[:6]
            warn("one_way_dead_end",
                 f"{len(sinks) + len(sources)} junction(s) have only incoming or only outgoing roads and zero demand "
                 f"({', '.join(some)}{' …' if len(sinks) + len(sources) > 6 else ''}); the flow on those roads is forced to 0.")

    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "counts": {"junctions": len(junctions), "roads": len(roads), "components": len(components)}}
