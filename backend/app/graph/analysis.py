"""Graph algorithms: adjacency lists, BFS, directed reachability, weak
connectivity, isolated junction detection. Implemented with collections.deque."""
from __future__ import annotations

from collections import deque


def build_adjacency(nodes: list[str], edges: list[tuple[str, str]]) -> tuple[dict, dict, dict]:
    """Returns (out_adj, in_adj, undirected_adj) as adjacency lists."""
    out_adj = {n: [] for n in nodes}
    in_adj = {n: [] for n in nodes}
    und = {n: [] for n in nodes}
    for s, t in edges:
        out_adj[s].append(t)
        in_adj[t].append(s)
        und[s].append(t)
        und[t].append(s)
    return out_adj, in_adj, und


def bfs(adj: dict[str, list[str]], start: str) -> dict:
    """Breadth-first search. Returns visit order and BFS level of each node."""
    level = {start: 0}
    order = []
    q = deque([start])
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj[u]:
            if v not in level:
                level[v] = level[u] + 1
                q.append(v)
    return {"order": order, "level": level}


def weak_components(nodes: list[str], und: dict[str, list[str]]) -> list[list[str]]:
    seen: set[str] = set()
    comps = []
    for n in nodes:
        if n not in seen:
            res = bfs(und, n)
            seen.update(res["order"])
            comps.append(res["order"])
    return comps


def analyse_graph(nodes: list[str], names: dict[str, str], edges: list[tuple[str, str]], start: str | None = None) -> dict:
    out_adj, in_adj, und = build_adjacency(nodes, edges)
    start = start if start in out_adj else (nodes[0] if nodes else None)
    comps = weak_components(nodes, und)
    isolated = [n for n in nodes if not out_adj[n] and not in_adj[n]]
    res: dict = {
        "adjacency_out": {names[n]: [names[v] for v in out_adj[n]] for n in nodes},
        "adjacency_in": {names[n]: [names[v] for v in in_adj[n]] for n in nodes},
        "degrees": {names[n]: {"in": len(in_adj[n]), "out": len(out_adj[n])} for n in nodes},
        "weak_components": [[names[n] for n in c] for c in comps],
        "weakly_connected": len(comps) <= 1,
        "isolated_junctions": [names[n] for n in isolated],
        "sources_only": [names[n] for n in nodes if out_adj[n] and not in_adj[n]],
        "sinks_only": [names[n] for n in nodes if in_adj[n] and not out_adj[n]],
        "start": names[start] if start else None,
    }
    if start:
        fwd = bfs(out_adj, start)
        res["bfs_directed"] = {"order": [names[n] for n in fwd["order"]],
                               "levels": {names[n]: l for n, l in fwd["level"].items()},
                               "unreachable": [names[n] for n in nodes if n not in fwd["level"]]}
        und_b = bfs(und, start)
        res["bfs_undirected"] = {"order": [names[n] for n in und_b["order"]],
                                 "levels": {names[n]: l for n, l in und_b["level"].items()},
                                 "unreachable": [names[n] for n in nodes if n not in und_b["level"]]}
        rev = bfs(in_adj, start)
        # strongly connected <=> start reaches all AND all reach start
        res["strongly_connected"] = len(fwd["order"]) == len(nodes) and len(rev["order"]) == len(nodes)
        res["note"] = ("Directed reachability follows road directions; weak connectivity ignores directions. "
                       "A network can be weakly connected yet have junctions that cannot be reached by driving.")
    return res
