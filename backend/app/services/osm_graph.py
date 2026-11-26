"""
Pure conversion of raw OpenStreetMap data (Overpass JSON) into FlowMatrix's graph model.

Nothing here talks to the network, so it is fully unit-testable.

Steps
 1. keep drivable ways of the requested classes;
 2. clip to a corridor around the reference route;
 3. remove side stubs (tree-like appendages) except at pickup / destination;
 4. a vertex is any point that is not a plain pass-through: an intersection, a dead end, a change of
    one-way rule, or the pickup / destination;
 5. vertices closer than ``merge_m`` along a road (parts of one physical intersection) are merged;
 6. each chain between two junctions becomes one road per permitted driving direction, keeping the
    real geometry;
 7. fragments connected to neither pickup nor destination are left out (and reported).
"""
from __future__ import annotations

import math
from collections import deque

MAIN_CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary",
                "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"]
LOCAL_CLASSES = ["unclassified", "residential", "living_street"]


class MapError(ValueError):
    """A map network could not be built; the message is shown to the user."""


def classes_for(detail: str) -> list[str]:
    return MAIN_CLASSES + (LOCAL_CLASSES if detail == "all" else [])


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in metres between (lat, lng) points."""
    r = 6371008.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class Projection:
    """Local flat projection (metres) around a reference latitude; accurate for a few km."""

    def __init__(self, lat0: float, lng0: float):
        self.lat0, self.lng0 = lat0, lng0
        self.kx = 111320.0 * math.cos(math.radians(lat0))
        self.ky = 110540.0

    def __call__(self, lat: float, lng: float) -> tuple[float, float]:
        return (lng - self.lng0) * self.kx, (lat - self.lat0) * self.ky


def _distance_and_chainage(p, line) -> tuple[float, float]:
    """(distance from p to polyline, distance along the polyline of the closest point)."""
    best, best_s, s = float("inf"), 0.0, 0.0
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        dx, dy = bx - ax, by - ay
        seg = math.hypot(dx, dy)
        t = 0.0 if seg == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (seg * seg)))
        d = math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))
        if d < best:
            best, best_s = d, s + t * seg
        s += seg
    return best, best_s


def _directions(tags: dict) -> tuple[bool, bool]:
    """(may drive in way order, may drive against way order)."""
    oneway = str(tags.get("oneway", "")).lower()
    if oneway in ("yes", "true", "1"):
        return True, False
    if oneway in ("-1", "reverse"):
        return False, True
    if oneway in ("no", "false", "0"):
        return True, True
    if tags.get("highway") == "motorway" or tags.get("junction") in ("roundabout", "circular"):
        return True, False
    return True, True


def _drivable(tags: dict, classes: set[str]) -> bool:
    if tags.get("highway") not in classes or tags.get("area") == "yes":
        return False
    for key in ("motor_vehicle", "vehicle", "access"):
        value = tags.get(key)
        if value in ("no", "private"):
            return False
        if value in ("yes", "permissive", "destination"):
            break
    return True


def build_graph(elements: list[dict], route: list[tuple[float, float]], pickup: tuple[float, float],
                destination: tuple[float, float], detail: str = "main", radius_m: float = 150,
                prune_stubs: bool = True, trip_flow: float = 0, max_roads: int = 300, merge_m: float = 20) -> dict:
    """Returns {"junctions": [...], "roads": [...], "stats": {...}, "warnings": [...]}."""
    coords = {e["id"]: (e["lat"], e["lon"]) for e in elements if e.get("type") == "node"}
    ways = [e for e in elements if e.get("type") == "way" and _drivable(e.get("tags", {}), set(classes_for(detail)))]
    if not ways:
        raise MapError("OpenStreetMap has no drivable roads of the selected classes between these places. "
                       "Try 'All streets', or create the network manually.")

    proj = Projection(pickup[0], pickup[1])
    line = [proj(*p) for p in (route if len(route) > 1 else [pickup, destination])]
    near: dict[int, tuple[float, float]] = {}  # node -> (distance to route, chainage)

    def info(n):
        if n not in near:
            near[n] = _distance_and_chainage(proj(*coords[n]), line)
        return near[n]

    # raw segments inside the corridor: key (a, b) unordered
    segments: dict[frozenset, dict] = {}
    for w in ways:
        tags = w.get("tags", {})
        fwd, bwd = _directions(tags)
        nodes = [n for n in w.get("nodes", []) if n in coords]
        for a, b in zip(nodes, nodes[1:]):
            if a == b or info(a)[0] > radius_m or info(b)[0] > radius_m:
                continue
            segments[frozenset((a, b))] = {"a": a, "b": b, "fwd": fwd, "bwd": bwd, "way": w["id"],
                                           "name": tags.get("name") or tags.get("ref") or "",
                                           "highway": tags.get("highway", "")}
    if not segments:
        raise MapError("No road segments lie within the corridor around the route. Try a wider corridor.")

    adj: dict[int, set[int]] = {}
    for key, s in segments.items():
        adj.setdefault(s["a"], set()).add(s["b"])
        adj.setdefault(s["b"], set()).add(s["a"])

    # snap pickup / destination: prefer one connected part of the road data that is close to BOTH places
    def snap(point, nodes):
        node = min(nodes, key=lambda n: haversine(point, coords[n]))
        return node, haversine(point, coords[node])

    close = radius_m * 2
    shared = [c for c in _components(adj) if snap(pickup, c)[1] <= close and snap(destination, c)[1] <= close]
    pool = max(shared, key=len) if shared else list(adj)
    p_node, p_gap = snap(pickup, pool)
    d_node, d_gap = snap(destination, pool)
    if p_node == d_node:
        raise MapError("Pickup and destination snap to the same road point. Choose places further apart.")
    if max(p_gap, d_gap) > radius_m * 2:
        raise MapError("A selected place is too far from the road network that was found "
                       f"({max(p_gap, d_gap):.0f} m). Try 'All streets' or a nearby location on a road.")
    protected = {p_node, d_node}

    pruned = 0
    if prune_stubs:
        queue = deque(n for n in adj if len(adj[n]) <= 1 and n not in protected)
        while queue:
            n = queue.popleft()
            if n not in adj or len(adj[n]) > 1 or n in protected:
                continue
            for m in adj.pop(n):
                segments.pop(frozenset((n, m)), None)
                pruned += 1
                adj[m].discard(n)
                if len(adj[m]) <= 1 and m not in protected:
                    queue.append(m)
    if not segments or p_node not in adj or d_node not in adj:
        raise MapError("After removing dead-end side roads nothing connects the two places. "
                       "Turn off 'remove side stubs' or choose 'All streets'.")

    def allowed(u, v) -> bool:
        s = segments[frozenset((u, v))]
        return s["fwd"] if s["a"] == u else s["bwd"]

    def pass_through(n) -> bool:
        if n in protected or len(adj[n]) != 2:
            return False
        u, v = sorted(adj[n])
        # driving rules must continue unchanged through n
        return allowed(u, n) == allowed(n, v) and allowed(v, n) == allowed(n, u)

    vertices = {n for n in adj if adj[n] and not pass_through(n)}
    used: set[frozenset] = set()
    chains: list[list[int]] = []

    def walk(start, nxt):
        path = [start, nxt]
        used.add(frozenset((start, nxt)))
        while path[-1] not in vertices:
            here, prev = path[-1], path[-2]
            step = next(m for m in adj[here] if m != prev)
            used.add(frozenset((here, step)))
            path.append(step)
        return path

    for v in sorted(vertices):
        for m in sorted(adj[v]):
            if frozenset((v, m)) not in used:
                chains.append(walk(v, m))
    # loops without any vertex (an isolated ring road): promote one node
    for key in list(segments):
        if key not in used:
            a, b = segments[key]["a"], segments[key]["b"]
            vertices.add(a)
            chains.append(walk(a, b))

    # a chain that starts and ends at the same vertex would be a self-loop: split it in two
    split: list[list[int]] = []
    for path in chains:
        if path[0] == path[-1]:
            if len(path) < 4:
                continue
            i, j = len(path) // 3, 2 * len(path) // 3
            vertices.update((path[i], path[j]))
            split += [path[: i + 1], path[i: j + 1], path[j:]]
        else:
            split.append(path)
    chains = split

    rep = _merge_close(vertices, chains, coords, protected, merge_m)  # vertex -> junction node
    merged = sum(1 for v in rep if rep[v] != v)
    chains = [path for path in chains if rep[path[0]] != rep[path[-1]]]  # pieces inside one intersection

    # keep only the parts of the graph that touch the pickup or the destination
    links: dict[int, set[int]] = {rep[v]: set() for v in vertices}
    for path in chains:
        a, b = rep[path[0]], rep[path[-1]]
        links[a].add(b)
        links[b].add(a)
    keep = _reach(links, rep[p_node]) | _reach(links, rep[d_node])
    dropped = [path for path in chains if rep[path[0]] not in keep]
    chains = [path for path in chains if rep[path[0]] in keep]
    if not chains:
        raise MapError("The places are so close together that they merge into one junction. Choose places further apart.")

    ordered = sorted(keep, key=lambda n: (round(info(n)[1]), info(n)[0]))
    key_of = {n: f"J{i + 1}" for i, n in enumerate(ordered)}

    roads = []
    for path in chains:
        segs = [segments[frozenset(p)] for p in zip(path, path[1:])]
        names = list(dict.fromkeys(s["name"] for s in segs if s["name"]))
        start, end = rep[path[0]], rep[path[-1]]
        # the drawn road runs from junction to junction (a few metres of connector where points were merged)
        shape = ([start] if start != path[0] else []) + path + ([end] if end != path[-1] else [])
        length = sum(haversine(coords[a], coords[b]) for a, b in zip(shape, shape[1:]))
        for direction in (path, path[::-1]):
            if not all(allowed(a, b) for a, b in zip(direction, direction[1:])):
                continue
            both = all(allowed(a, b) for a, b in zip(direction[::-1], direction[::-1][1:]))
            drawn = shape if direction[0] == path[0] else shape[::-1]
            roads.append({
                "source": key_of[rep[direction[0]]], "target": key_of[rep[direction[-1]]],
                "label": " / ".join(names[:2])[:120],
                "geometry": [[round(coords[n][0], 7), round(coords[n][1], 7)] for n in drawn],
                "length_m": round(length, 1), "osm_way_id": str(segs[0]["way"]), "highway": segs[0]["highway"],
                "origin": "osm", "known_flow": None, "oneway": not both,
            })
    if len(roads) > max_roads:
        raise MapError(f"This area produces {len(roads)} directed roads, more than the limit of {max_roads}. "
                       "Choose closer places, 'Main roads' detail or a narrower corridor.")
    roads.sort(key=lambda r: (int(r["source"][1:]), int(r["target"][1:])))
    for i, r in enumerate(roads, 1):
        r["key"] = f"r{i}"

    # junction records with canvas coordinates (for diagrams and the PDF)
    pts = {n: proj(*coords[n]) for n in ordered}
    min_x, max_x = min(p[0] for p in pts.values()), max(p[0] for p in pts.values())
    min_y, max_y = min(p[1] for p in pts.values()), max(p[1] for p in pts.values())
    scale = 900 / max(max_x - min_x, max_y - min_y, 1)
    degree = {n: 0 for n in ordered}
    for path in chains:
        degree[rep[path[0]]] += 1
        degree[rep[path[-1]]] += 1
    p_node, d_node = rep[p_node], rep[d_node]

    junctions = []
    for n in ordered:
        if n == p_node:
            kind, demand = "pickup", -trip_flow
        elif n == d_node:
            kind, demand = "destination", trip_flow
        else:
            kind = "dead_end" if degree[n] == 1 else ("intersection" if degree[n] >= 3 else "junction")
            demand = 0
        junctions.append({"key": key_of[n], "name": key_of[n], "lat": round(coords[n][0], 7),
                          "lng": round(coords[n][1], 7), "node_type": kind,
                          "x": round((pts[n][0] - min_x) * scale, 1), "y": round((max_y - pts[n][1]) * scale, 1),
                          "net_demand": f"{demand:g}"})

    pairs = [(r["source"], r["target"]) for r in roads]
    und = {j["key"]: set() for j in junctions}
    out = {j["key"]: set() for j in junctions}
    for s, t in pairs:
        und[s].add(t)
        und[t].add(s)
        out[s].add(t)
    parts = _components(und)
    reachable = _reach(out, key_of[p_node])

    warnings = []
    if len(parts) > 1:
        warnings.append(f"The extracted road data has {len(parts)} disconnected parts (roads that only connect "
                        "outside the corridor). Each part balances independently.")
    if key_of[d_node] not in reachable:
        warnings.append("Following one-way rules, the destination cannot be reached from the pickup using only the "
                        "extracted roads (a connecting road lies outside the corridor or in an excluded class).")
    if merged:
        warnings.append(f"{merged} point(s) closer than {merge_m:g} m to a neighbouring intersection were merged into it.")
    if dropped:
        warnings.append(f"{len(dropped)} road piece(s) inside the corridor but not connected to the pickup or destination "
                        "were left out.")
    if pruned:
        warnings.append(f"{pruned} segment(s) of dead-end side streets leading away from the route were left out.")

    return {
        "junctions": junctions, "roads": roads, "warnings": warnings,
        "stats": {"junctions": len(junctions), "roads": len(roads), "components": len(parts),
                  "osm_ways": len({s["way"] for s in segments.values()}), "pruned_segments": pruned,
                  "merged_points": merged, "left_out_pieces": len(dropped),
                  "pickup_junction": key_of[p_node], "destination_junction": key_of[d_node],
                  "pickup_snap_m": round(p_gap, 1), "destination_snap_m": round(d_gap, 1),
                  "destination_reachable": key_of[d_node] in reachable},
    }


def _merge_close(vertices, chains, coords, protected, merge_m) -> dict:
    """Union vertices joined by a road piece shorter than ``merge_m``. A group never grows beyond
    ``2 * merge_m`` across, and pickup and destination stay separate. The group is represented by one of
    its real OSM points (the pickup/destination if present, otherwise the most central)."""
    group = {v: [v] for v in vertices}
    owner = {v: v for v in vertices}
    pieces = sorted((sum(haversine(coords[a], coords[b]) for a, b in zip(p, p[1:])), p[0], p[-1]) for p in chains)
    for length, a, b in pieces:
        if length >= merge_m:
            break
        ga, gb = owner[a], owner[b]
        if ga == gb:
            continue
        members = group[ga] + group[gb]
        if sum(m in protected for m in members) > 1:
            continue
        if any(haversine(coords[x], coords[y]) > 2 * merge_m for x in group[ga] for y in group[gb]):
            continue
        group[ga] = members
        for m in group.pop(gb):
            owner[m] = ga
    rep = {}
    for members in group.values():
        fixed = [m for m in members if m in protected]
        lat = sum(coords[m][0] for m in members) / len(members)
        lng = sum(coords[m][1] for m in members) / len(members)
        centre = fixed[0] if fixed else min(members, key=lambda m: haversine(coords[m], (lat, lng)))
        for m in members:
            rep[m] = centre
    return rep


def _components(adj: dict) -> list[set]:
    seen: set = set()
    out = []
    for start in adj:
        if start in seen:
            continue
        comp = _reach(adj, start)
        seen |= comp
        out.append(comp)
    return out


def _reach(adj: dict, start) -> set:
    seen = {start}
    queue = deque([start])
    while queue:
        u = queue.popleft()
        for v in adj.get(u, ()):
            if v not in seen:
                seen.add(v)
                queue.append(v)
    return seen
