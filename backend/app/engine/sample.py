"""Demonstration traffic values, clearly labelled as samples.

Road geometry says nothing about how many vehicles use a road. For a demonstration this module routes
imaginary vehicles along real directed paths from places where traffic can enter to places where it can
leave. The external demands and the "measured" roads are read off that assignment, so the resulting system
is always consistent and has a nonnegative solution. Deterministic for a given network.
"""
from __future__ import annotations

import random
from collections import deque

from .equations import NetworkError

ENTRY_TYPES = {"start", "end", "boundary", "pickup", "destination"}


def _path(out: dict, source: str, target: str) -> list[str] | None:
    """Shortest directed path (list of road keys) found by breadth-first search."""
    parent: dict[str, tuple[str, str]] = {}
    queue, seen = deque([source]), {source}
    while queue:
        u = queue.popleft()
        if u == target:
            break
        for v, road in out[u]:
            if v not in seen:
                seen.add(v)
                parent[v] = (u, road)
                queue.append(v)
    if target not in parent:
        return None
    roads, node = [], target
    while node != source:
        node, road = parent[node]
        roads.append(road)
    return roads[::-1]


def sample_values(network) -> dict:
    junctions, roads = network.junctions, network.roads
    if not roads:
        raise NetworkError("Add roads before asking for sample values.")
    rng = random.Random(f"{len(junctions)}:{len(roads)}:" + "".join(r.source + r.target for r in roads))
    out: dict[str, list] = {j.key: [] for j in junctions}
    into: dict[str, list] = {j.key: [] for j in junctions}
    for r in roads:
        out[r.source].append((r.target, r.key))
        into[r.target].append((r.source, r.key))

    ports = [j.key for j in junctions if j.node_type in ENTRY_TYPES]
    ports += [j.key for j in junctions if (not out[j.key]) != (not into[j.key])]  # one-way sources / sinks
    if len(set(ports)) < 2:
        ports = [j.key for j in junctions]
    ports = list(dict.fromkeys(ports))

    flow = {r.key: 0 for r in roads}
    demand = {j.key: 0 for j in junctions}  # leaving the network is positive

    def send(a: str, b: str, vehicles: int, via: list | None = None) -> bool:
        path = _path(out, a, b) if via is None else via
        if a == b or not path:
            return False
        for key in path:
            flow[key] += vehicles
        demand[a] -= vehicles
        demand[b] += vehicles
        return True

    first = next((j.key for j in junctions if j.node_type in ("start", "pickup")), ports[0])
    last = next((j.key for j in junctions if j.node_type in ("end", "destination")), ports[-1])
    send(first, last, 300)
    for a in ports:  # some traffic from every entry point
        for b in rng.sample(ports, len(ports)):
            if send(a, b, rng.choice((20, 30, 40, 50, 60))):
                break
    for r in roads:  # give every road some traffic where a route through it exists
        if flow[r.key]:
            continue
        for a in rng.sample(ports, len(ports)):
            before = _path(out, a, r.source) if a != r.source else []
            if before is None:
                continue
            done = False
            for b in rng.sample(ports, len(ports)):
                after = _path(out, r.target, b) if b != r.target else []
                if after is not None and a != b and send(a, b, rng.choice((10, 20, 30)), before + [r.key] + after):
                    done = True
                    break
            if done:
                break

    # "sensors": most roads that close a loop (outside a spanning forest), leaving a few free variables
    root = {j.key: j.key for j in junctions}

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x

    loops = []
    for r in roads:
        a, b = find(r.source), find(r.target)
        if a == b:
            loops.append(r.key)
        else:
            root[a] = b
    free = min(3, len(loops) // 3)
    measured = set(rng.sample(loops, len(loops) - free)) if loops else set()

    return {
        "junctions": [{"key": j.key, "net_demand": str(demand[j.key])} for j in junctions],
        "roads": [{"key": r.key, "known_flow": str(flow[r.key]) if r.key in measured else None} for r in roads],
        "summary": {"entry_or_exit_points": sum(1 for v in demand.values() if v), "measured_roads": len(measured),
                    "note": "Sample values for demonstration only - not real traffic counts."},
    }
