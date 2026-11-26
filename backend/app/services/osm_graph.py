"""
Pure conversion of raw OpenStreetMap data (Overpass JSON) into FlowMatrix's graph model.

Nothing here talks to the network, so it is fully unit-testable. The conversion is rule based and
deterministic: it only removes or joins what OpenStreetMap contains and never invents a road.

Steps
 1. keep drivable ways of the requested classes and clip them to a corridor around the driving route;
 2. remember where a road LEAVES the corridor: those places are the network boundary, where traffic
    can enter or leave;
 3. remove side stubs (tree-like appendages); the point where a stub that led out of the area was
    attached stays a boundary;
 4. a vertex is any point that is not a plain pass-through: an intersection, a boundary point, a change
    of one-way rule, or Location 1 / Location 2;
 5. vertices closer than ``merge_m`` along a road (parts of one physical intersection) are merged;
 6. each chain between two vertices becomes one edge per permitted driving direction, keeping the real
    geometry;
 7. fragments connected to neither location are left out, duplicate edges are removed, and vertices
    that no longer join anything are dissolved, until nothing changes;
 8. vertices are numbered V1, V2, ... along the route and edges E1, E2, ...

Every removal is counted and reported to the user.
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


def build_graph(elements: list[dict], route: list[tuple[float, float]], start: tuple[float, float],
                end: tuple[float, float], detail: str = "main", radius_m: float = 150,
                prune_stubs: bool = True, trip_flow: float = 0, max_roads: int = 300, merge_m: float = 20) -> dict:
    """Returns {"junctions": [...], "roads": [...], "stats": {...}, "warnings": [...]}."""
    coords = {e["id"]: (e["lat"], e["lon"]) for e in elements if e.get("type") == "node"}
    ways = [e for e in elements if e.get("type") == "way" and _drivable(e.get("tags", {}), set(classes_for(detail)))]
    if not ways:
        raise MapError("OpenStreetMap has no drivable roads of the selected classes between these places. "
                       "Try 'All streets', or create the network manually.")

    proj = Projection(start[0], start[1])
    line = [proj(*p) for p in (route if len(route) > 1 else [start, end])]
    near: dict[int, tuple[float, float]] = {}  # node -> (distance to route, chainage)

    def info(n):
        if n not in near:
            near[n] = _distance_and_chainage(proj(*coords[n]), line)
        return near[n]

    # raw segments inside the corridor: key (a, b) unordered
    segments: dict[frozenset, dict] = {}
    leaving: set[int] = set()  # points from which a road continues out of the selected area
    for w in ways:
        tags = w.get("tags", {})
        fwd, bwd = _directions(tags)
        nodes = [n for n in w.get("nodes", []) if n in coords]
        for a, b in zip(nodes, nodes[1:]):
            if a == b:
                continue
            a_in, b_in = info(a)[0] <= radius_m, info(b)[0] <= radius_m
            if not (a_in and b_in):
                if a_in:
                    leaving.add(a)
                if b_in:
                    leaving.add(b)
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

    # snap the two locations: prefer one connected part of the road data that is close to BOTH
    def snap(point, nodes):
        node = min(nodes, key=lambda n: haversine(point, coords[n]))
        return node, haversine(point, coords[node])

    # A location is never moved much further than its nearest road just to gain connectivity.
    near_start, near_end = snap(start, list(adj))[1] + 60, snap(end, list(adj))[1] + 60
    shared = [c for c in _components(adj) if snap(start, c)[1] <= near_start and snap(end, c)[1] <= near_end]
    pool = max(shared, key=len) if shared else list(adj)
    s_node, s_gap = snap(start, pool)
    e_node, e_gap = snap(end, pool)
    # Prefer points that lie ON the driving route: it is a legal path, so Location 2 stays reachable. The merely
    # nearest point may be on the opposite one-way carriageway of a divided road.
    on_route = [n for n in adj if adj[n] and info(n)[0] <= 2]
    if len(route) > 1 and on_route:
        first = min(on_route, key=lambda n: info(n)[1])
        last = max(on_route, key=lambda n: info(n)[1])
        first_gap, last_gap = haversine(start, coords[first]), haversine(end, coords[last])
        if first != last and first_gap <= max(s_gap + 60, radius_m) and last_gap <= max(e_gap + 60, radius_m):
            s_node, s_gap, e_node, e_gap = first, first_gap, last, last_gap
    if s_node == e_node:
        raise MapError("Location 1 and Location 2 snap to the same road point. Choose places further apart.")
    if max(s_gap, e_gap) > radius_m * 2:
        raise MapError("A selected location is too far from the road network that was found "
                       f"({max(s_gap, e_gap):.0f} m). Try 'All streets' or a location on a road.")
    protected = {s_node, e_node}

    pruned = 0
    if prune_stubs:
        queue = deque(n for n in adj if len(adj[n]) <= 1 and n not in protected)
        while queue:
            n = queue.popleft()
            if n not in adj or len(adj[n]) > 1 or n in protected:
                continue
            for m in adj.pop(n):
                if n in leaving:
                    leaving.add(m)  # the removed branch led out of the area: m is where traffic enters / leaves
                segments.pop(frozenset((n, m)), None)
                pruned += 1
                adj[m].discard(n)
                if len(adj[m]) <= 1 and m not in protected:
                    queue.append(m)
    # a location whose every neighbouring road was trimmed away is left with an empty adjacency set
    if not segments or not adj.get(s_node) or not adj.get(e_node):
        raise MapError("After removing dead-end side roads nothing connects the two places. "
                       "Turn off 'remove side stubs' or choose 'All streets'.")
    boundary = {n for n in leaving if n in adj and adj[n]}

    def allowed(u, v) -> bool:
        s = segments[frozenset((u, v))]
        return s["fwd"] if s["a"] == u else s["bwd"]

    def pass_through(n) -> bool:
        if n in protected or n in boundary or len(adj[n]) != 2:
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
    if s_node not in rep or e_node not in rep:
        raise MapError("A selected location ended up without any road. Choose a location on a main road or 'All streets'.")
    s_node, e_node = rep[s_node], rep[e_node]
    boundary = {rep[n] for n in boundary if n in rep}

    # keep only the parts of the graph that touch one of the two locations
    links: dict[int, set[int]] = {rep[v]: set() for v in vertices}
    for path in chains:
        x, y = rep[path[0]], rep[path[-1]]
        links[x].add(y)
        links[y].add(x)
    keep = _reach(links, s_node) | _reach(links, e_node)
    dropped = [path for path in chains if rep[path[0]] not in keep]
    chains = [path for path in chains if rep[path[0]] in keep]
    if not chains:
        raise MapError("The places are so close together that they merge into one junction. Choose places further apart.")

    # directed edges between junction nodes, one per permitted driving direction
    edges = []
    for path in chains:
        segs = [segments[frozenset(p)] for p in zip(path, path[1:])]
        names = list(dict.fromkeys(x["name"] for x in segs if x["name"]))
        first, last = rep[path[0]], rep[path[-1]]
        # the drawn road runs from junction to junction (a few metres of connector where points were merged)
        shape = ([first] if first != path[0] else []) + path + ([last] if last != path[-1] else [])
        for direction in (path, path[::-1]):
            if not all(allowed(u, v) for u, v in zip(direction, direction[1:])):
                continue
            forward = direction[0] == path[0]
            back = direction[::-1]
            edges.append({"a": rep[direction[0]], "b": rep[direction[-1]], "shape": shape if forward else shape[::-1],
                          "names": names, "way": segs[0]["way"], "highway": segs[0]["highway"],
                          "two_way": all(allowed(u, v) for u, v in zip(back, back[1:]))})

    protected = {s_node, e_node} | boundary
    edges, duplicates, dissolved, dead_ends = _simplify(edges, protected, coords, proj, prune_stubs)
    if not edges:
        raise MapError("Nothing connects the two locations after simplification. Try 'All streets'.")

    nodes = {e["a"] for e in edges} | {e["b"] for e in edges}
    if s_node not in nodes or e_node not in nodes:
        raise MapError("A selected location ended up without any road. Choose a location on a main road or 'All streets'.")
    ordered = sorted(nodes, key=lambda n: (round(info(n)[1]), info(n)[0]))
    key_of = {n: f"V{i + 1}" for i, n in enumerate(ordered)}

    if len(edges) > max_roads:
        raise MapError(f"This area produces {len(edges)} directed roads, more than the limit of {max_roads}. "
                       "Choose closer places, 'Main roads' detail or a narrower corridor.")
    edges.sort(key=lambda e: (int(key_of[e["a"]][1:]), int(key_of[e["b"]][1:])))
    roads = []
    for i, e in enumerate(edges, 1):
        shape = e["shape"]
        roads.append({
            "key": f"E{i}", "source": key_of[e["a"]], "target": key_of[e["b"]],
            "label": " / ".join(e["names"][:2])[:120],
            "geometry": [[round(coords[n][0], 7), round(coords[n][1], 7)] for n in shape],
            "length_m": round(_length(shape, coords), 1), "osm_way_id": str(e["way"]), "highway": e["highway"],
            "origin": "osm", "known_flow": None, "oneway": not e["two_way"],
        })

    degree = {n: 0 for n in ordered}
    for x, y in {tuple(sorted((e["a"], e["b"]))) for e in edges}:
        degree[x] += 1
        degree[y] += 1

    positions = _spread([proj(*coords[n]) for n in ordered])  # spaced-out layout for the graph view
    junctions = []
    for n, (x, y) in zip(ordered, positions):
        demand = 0
        if n == s_node:
            kind, demand = "start", -trip_flow
        elif n == e_node:
            kind, demand = "end", trip_flow
        elif n in boundary:
            kind = "boundary"
        else:
            kind = "dead_end" if degree[n] == 1 else ("intersection" if degree[n] >= 3 else "junction")
        junctions.append({"key": key_of[n], "name": key_of[n], "lat": round(coords[n][0], 7),
                          "lng": round(coords[n][1], 7), "node_type": kind, "x": x, "y": y, "net_demand": f"{demand:g}"})

    und = {j["key"]: set() for j in junctions}
    out = {j["key"]: set() for j in junctions}
    for r in roads:
        und[r["source"]].add(r["target"])
        und[r["target"]].add(r["source"])
        out[r["source"]].add(r["target"])
    parts = _components(und)
    start_key, end_key = key_of[s_node], key_of[e_node]
    reachable = end_key in _reach(out, start_key)
    boundary_keys = [key_of[n] for n in ordered if n in boundary]

    warnings = []
    if len(parts) > 1:
        warnings.append(f"The extracted road data has {len(parts)} disconnected parts (roads that only connect "
                        "outside the corridor). Each part balances independently.")
    if not reachable:
        warnings.append("Following one-way rules, Location 2 cannot be reached from Location 1 using only the "
                        "extracted roads (a connecting road lies outside the corridor or in an excluded class).")
    if boundary_keys:
        warnings.append(f"{len(boundary_keys)} boundary junction(s) mark where roads leave the selected area; "
                        "enter the traffic entering or leaving there.")
    if merged:
        warnings.append(f"{merged} point(s) closer than {merge_m:g} m to a neighbouring intersection were merged into it.")
    if duplicates:
        warnings.append(f"{duplicates} duplicate road(s) drawn almost on top of another were removed.")
    if dissolved:
        warnings.append(f"{dissolved} point(s) that did not join different roads were dissolved into the road.")
    if dead_ends:
        warnings.append(f"{dead_ends} dead-end road(s) that could carry no through traffic were left out.")
    if dropped:
        warnings.append(f"{len(dropped)} road piece(s) inside the corridor but not connected to either location were left out.")
    if pruned:
        warnings.append(f"{pruned} segment(s) of side streets leading away from the route were left out.")

    return {
        "junctions": junctions, "roads": roads, "warnings": warnings, "boundary": boundary_keys,
        "stats": {"junctions": len(junctions), "roads": len(roads), "components": len(parts),
                  "osm_ways": len({x["way"] for x in segments.values()}), "pruned_segments": pruned,
                  "merged_points": merged, "left_out_pieces": len(dropped), "duplicates_removed": duplicates,
                  "dissolved_points": dissolved, "dead_ends_removed": dead_ends, "boundary_junctions": len(boundary_keys),
                  "start_junction": start_key, "end_junction": end_key,
                  "start_snap_m": round(s_gap, 1), "end_snap_m": round(e_gap, 1), "end_reachable": reachable},
    }


def _length(shape: list[int], coords) -> float:
    return sum(haversine(coords[a], coords[b]) for a, b in zip(shape, shape[1:]))


def _same_course(one: list[int], two: list[int], coords, proj, tolerance: float = 30) -> bool:
    """True if each path stays within ``tolerance`` metres of the other."""
    def within(points, line):
        path = [proj(*coords[n]) for n in line]
        return all(_distance_and_chainage(proj(*coords[n]), path)[0] <= tolerance for n in points)

    return within(one, two) and within(two, one)


def _join(first: dict, second: dict) -> dict:
    """a -> v -> b becomes a -> b, keeping both real geometries."""
    return {"a": first["a"], "b": second["b"], "shape": first["shape"] + second["shape"][1:],
            "names": list(dict.fromkeys(first["names"] + second["names"])), "way": first["way"], "highway": first["highway"],
            "two_way": first["two_way"] and second["two_way"]}


def _simplify(edges: list[dict], protected: set, coords, proj, drop_dead_ends: bool) -> tuple[list[dict], int, int, int]:
    """Repeat until stable: remove self-loops and duplicates, dissolve pass-through vertices and (optionally)
    remove dead ends. ``protected`` vertices (the two locations and the boundary) are never removed."""
    duplicates = dissolved = dead_ends = 0
    while True:
        edges = [e for e in edges if e["a"] != e["b"]]

        kept: dict[tuple, list[dict]] = {}
        unique = []
        for e in sorted(edges, key=lambda x: _length(x["shape"], coords)):
            twins = kept.setdefault((e["a"], e["b"]), [])
            if any(_same_course(e["shape"], t["shape"], coords, proj) for t in twins):
                duplicates += 1
                continue
            twins.append(e)
            unique.append(e)
        edges = unique

        into: dict[int, list[dict]] = {}
        outof: dict[int, list[dict]] = {}
        for e in edges:
            into.setdefault(e["b"], []).append(e)
            outof.setdefault(e["a"], []).append(e)

        change = None  # (edges to remove, edges to add)
        for v in sorted(set(into) | set(outof)):
            if v in protected:
                continue
            ins, outs = into.get(v, []), outof.get(v, [])
            neighbours = {e["a"] for e in ins} | {e["b"] for e in outs}
            if len(ins) == 1 and len(outs) == 1 and ins[0]["a"] != outs[0]["b"]:
                change = (ins + outs, [_join(ins[0], outs[0])])              # one-way pass-through
                dissolved += 1
            elif (len(ins) == 2 and len(outs) == 2 and len(neighbours) == 2
                  and {e["a"] for e in ins} == neighbours and {e["b"] for e in outs} == neighbours):
                joined = [_join(i, o) for i in ins for o in outs if i["a"] != o["b"]]
                change = (ins + outs, joined)                                # two-way pass-through
                dissolved += 1
            elif drop_dead_ends and (not ins or not outs or len(neighbours) == 1):
                change = (ins + outs, [])                                    # can carry no through traffic
                dead_ends += len(ins) + len(outs)
            if change:
                break
        if not change:
            return edges, duplicates, dissolved, dead_ends
        gone = {id(e) for e in change[0]}
        edges = [e for e in edges if id(e) not in gone] + change[1]


def _spread(points: list[tuple[float, float]], gap: float = 200) -> list[tuple[float, float]]:
    """Canvas positions that keep the geographic arrangement but push crowded vertices apart."""
    if not points:
        return []
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    extent = max(max(xs) - min(xs), max(ys) - min(ys), 1)
    scale = max(1200.0, 300.0 * math.sqrt(len(points))) / extent
    pos = [[(x - min(xs)) * scale, (max(ys) - y) * scale] for x, y in points]
    for _ in range(200):
        moved = False
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                dx, dy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                d = math.hypot(dx, dy)
                if d >= gap:
                    continue
                if d < 1e-6:
                    dx, dy, d = math.cos(i + j), math.sin(i + j), 1.0
                push = (gap - d) / 2 + 0.5
                pos[i][0] -= dx / d * push
                pos[i][1] -= dy / d * push
                pos[j][0] += dx / d * push
                pos[j][1] += dy / d * push
                moved = True
        if not moved:
            break
    min_x, min_y = min(p[0] for p in pos), min(p[1] for p in pos)
    return [(round(x - min_x + 40, 1), round(y - min_y + 40, 1)) for x, y in pos]


def _merge_close(vertices, chains, coords, protected, merge_m) -> dict:
    """Union vertices joined by a road piece shorter than ``merge_m``. A group never grows beyond
    ``2 * merge_m`` across, and the two locations stay separate. The group is represented by one of
    its real OSM points (a selected location if present, otherwise the most central)."""
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
