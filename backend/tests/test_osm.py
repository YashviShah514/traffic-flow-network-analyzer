"""Map-data conversion tests: a hand-made grid with known answers, and real recorded OSM data."""
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from app.engine.equations import JunctionIn, RoadIn
from app.engine.pipeline import analyze
from app.engine.validation import validate_network
from app.services import osm
from app.services.osm_graph import MapError, build_graph, haversine

# A small street layout (about 110 m between points):
#   1 --- 2 --- 3 --- 4        "Main Street", two-way
#         |     |
#         5 --> 6              detour 2->5->6->3 is one-way ("One Way Lane")
#   7 hangs off node 3 as a dead end
BASE_LAT, BASE_LNG, STEP = 23.0, 72.5, 0.001
POS = {1: (0, 0), 2: (0, 1), 3: (0, 2), 4: (0, 3), 5: (-1, 1), 6: (-1, 2), 7: (1, 2), 8: (0, 1.5)}


def coord(n):
    return BASE_LAT + POS[n][0] * STEP, BASE_LNG + POS[n][1] * STEP


def grid(extra=()):
    nodes = [{"type": "node", "id": n, "lat": coord(n)[0], "lon": coord(n)[1]} for n in POS]
    way = lambda i, ids, **tags: {"type": "way", "id": i, "nodes": ids, "tags": {"highway": "tertiary", **tags}}
    return nodes + [
        way(100, [1, 2, 8, 3, 4], name="Main Street"), way(101, [2, 5], name="One Way Lane", oneway="yes"),
        way(102, [3, 6], name="One Way Lane", oneway="-1"), way(103, [5, 6], name="One Way Lane", oneway="yes"), way(104, [3, 7], name="Cul de sac"), *extra,
    ]


def build(elements=None, **kw):
    kw.setdefault("radius_m", 300)
    return build_graph(elements or grid(), [coord(1), coord(4)], coord(1), coord(4), **kw)


def by_coord(g):
    return {(j["lat"], j["lng"]): j["key"] for j in g["junctions"]}


def key(g, n):
    return by_coord(g)[(round(coord(n)[0], 7), round(coord(n)[1], 7))]


def edges(g):
    return {(r["source"], r["target"]) for r in g["roads"]}


def test_intersections_become_junctions_and_pass_through_points_do_not():
    g = build()
    keys = by_coord(g)
    assert len(g["junctions"]) == 4  # 1 (pickup), 2, 3, 4 (destination); 5, 6 and 8 are plain bends
    assert (round(coord(8)[0], 7), round(coord(8)[1], 7)) not in keys
    assert g["stats"]["pickup_junction"] == key(g, 1) and g["stats"]["destination_junction"] == key(g, 4)


def test_one_way_restriction_is_preserved_along_a_chain():
    g = build()
    two, three = key(g, 2), key(g, 3)
    via_lane = [r for r in g["roads"] if "One Way Lane" in r["label"]]
    assert len(via_lane) == 1 and (via_lane[0]["source"], via_lane[0]["target"]) == (two, three)
    assert via_lane[0]["oneway"] is True
    main = [r for r in g["roads"] if r["label"] == "Main Street" and {r["source"], r["target"]} == {two, three}]
    assert len(main) == 2  # two-way road = one directed edge per direction; the lane is a genuine parallel road


def test_reverse_oneway_tag():
    elements = grid()
    flipped = {101: "-1", 102: "yes", 103: "-1"}
    for e in elements:
        if e.get("id") in flipped:
            e["tags"]["oneway"] = flipped[e["id"]]
    g = build(elements)
    lane = [r for r in g["roads"] if "One Way Lane" in r["label"]][0]
    assert (lane["source"], lane["target"]) == (key(g, 3), key(g, 2))


def test_change_of_one_way_rule_is_a_vertex():
    elements = grid()
    for e in elements:
        if e.get("id") == 101:
            e["tags"].pop("oneway")  # two-way, then one-way: point 5 must stay a vertex
    assert (round(coord(5)[0], 7), round(coord(5)[1], 7)) in by_coord(build(elements))


def test_dead_end_stub_pruned_or_kept():
    assert (round(coord(7)[0], 7), round(coord(7)[1], 7)) not in by_coord(build())
    kept = build(prune_stubs=False)
    assert [j for j in kept["junctions"] if j["node_type"] == "dead_end"]


def test_geometry_starts_and_ends_on_its_junctions_and_follows_the_road():
    g = build()
    pos = {j["key"]: [j["lat"], j["lng"]] for j in g["junctions"]}
    for r in g["roads"]:
        assert r["geometry"][0] == pos[r["source"]] and r["geometry"][-1] == pos[r["target"]]
        assert r["length_m"] >= haversine(tuple(pos[r["source"]]), tuple(pos[r["target"]])) - 0.5
    lane = [r for r in g["roads"] if "One Way Lane" in r["label"]][0]
    assert len(lane["geometry"]) == 4  # 2 -> 5 -> 6 -> 3, not a straight line


def test_trip_demand_sits_on_pickup_and_destination():
    g = build(trip_flow=100)
    demand = {j["node_type"]: j["net_demand"] for j in g["junctions"]}
    assert demand["pickup"] == "-100" and demand["destination"] == "100"


def test_private_and_unselected_roads_are_ignored():
    private = {"type": "way", "id": 200, "nodes": [1, 5], "tags": {"highway": "tertiary", "access": "private"}}
    footway = {"type": "way", "id": 201, "nodes": [5, 1], "tags": {"highway": "footway"}}
    assert edges(build(grid([private, footway]))) == edges(build())


def test_no_roads_gives_a_clear_error():
    with pytest.raises(MapError, match="no drivable roads"):
        build_graph([], [coord(1), coord(4)], coord(1), coord(4))


def test_same_snap_point_rejected():
    with pytest.raises(MapError):
        build_graph(grid(), [coord(1), coord(4)], coord(1), coord(1), radius_m=300)


def test_real_openstreetmap_data():
    data = json.loads((Path(__file__).parent / "fixtures" / "navrangpura.json").read_text(encoding="utf-8"))
    a, b = (23.0365, 72.5611), (23.0425, 72.5714)
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in data["elements"] if e["type"] == "node"}
    way = max((e for e in data["elements"] if e["type"] == "way"), key=lambda w: len(w["nodes"]))
    route = [nodes[way["nodes"][0]], nodes[way["nodes"][-1]]]
    g = build_graph(data["elements"], route, route[0], route[1], "all", 400)
    assert len(g["junctions"]) >= 2 and g["roads"]
    keys = {j["key"] for j in g["junctions"]}
    assert all(r["source"] in keys and r["target"] in keys and r["source"] != r["target"] for r in g["roads"])
    real = {(round(la, 7), round(lo, 7)) for la, lo in nodes.values()}
    assert all(tuple(p) in real for r in g["roads"] for p in r["geometry"])  # no invented geometry
    assert validate_network(g["junctions"], g["roads"])["ok"]
    result = analyze([JunctionIn(j["key"], j["name"], F(j["net_demand"])) for j in g["junctions"]],
                     [RoadIn(r["key"], r["source"], r["target"], r["label"]) for r in g["roads"]])
    assert result["verification"]["all_passed"]


def test_generate_network_uses_route_then_road_data(monkeypatch):
    monkeypatch.setattr(osm, "fetch_route", lambda a, b: {"points": [list(coord(1)), list(coord(4))], "distance_m": 330})
    monkeypatch.setattr(osm, "fetch_roads", lambda points, detail, radius: grid())
    out = osm.generate_network({"lat": coord(1)[0], "lng": coord(1)[1], "label": "Start"},
                               {"lat": coord(4)[0], "lng": coord(4)[1], "label": "End"}, radius_m=300)
    assert out["network"]["method"] == "map" and out["network"]["name"] == "Start → End"
    assert out["network"]["map_meta"]["attribution"] == "© OpenStreetMap contributors"


def test_generate_network_reports_missing_route_and_distance_limit(monkeypatch):
    place = lambda lat, lng: {"lat": lat, "lng": lng, "label": ""}
    with pytest.raises(MapError, match="limit"):
        osm.generate_network(place(23.0, 72.5), place(23.5, 72.5))
    monkeypatch.setattr(osm, "fetch_route", lambda a, b: None)
    with pytest.raises(MapError, match="No driving route"):
        osm.generate_network(place(*coord(1)), place(*coord(4)))


def test_overpass_query_is_restricted_to_a_corridor():
    q = osm.overpass_query([[23.0, 72.5], [23.001, 72.501]], "main", 150)
    assert "around:150,23.00000,72.50000,23.00100,72.50100" in q and "residential" not in q


def test_points_a_few_metres_apart_become_one_junction():
    # a second turning 8 m east of point 3: the slip road to point 6 leaves from there
    elements = grid() + [{"type": "node", "id": 9, "lat": coord(3)[0], "lon": coord(3)[1] + 0.00008}]
    for e in elements:
        if e.get("id") == 100:
            e["nodes"] = [1, 2, 8, 3, 9, 4]
        if e.get("id") == 104:
            e["nodes"] = [9, 6]
    merged = build(elements)
    separate = build(elements, merge_m=0)
    assert len(merged["junctions"]) == len(separate["junctions"]) - 1
    assert merged["stats"]["merged_points"] == 1
    pos = {j["key"]: [j["lat"], j["lng"]] for j in merged["junctions"]}
    for r in merged["roads"]:
        assert r["source"] != r["target"]
        assert r["geometry"][0] == pos[r["source"]] and r["geometry"][-1] == pos[r["target"]]


def test_fragments_not_connected_to_pickup_or_destination_are_left_out_and_reported():
    ids = {20: (-0.0016, 0.0004), 21: (-0.0016, 0.0008), 22: (-0.0019, 0.0006)}
    nodes = [{"type": "node", "id": n, "lat": BASE_LAT + a, "lon": BASE_LNG + b} for n, (a, b) in ids.items()]
    loop = {"type": "way", "id": 300, "nodes": [20, 21, 22, 20], "tags": {"highway": "tertiary", "name": "Loose Loop"}}
    g = build(grid() + nodes + [loop])
    assert all(r["label"] != "Loose Loop" for r in g["roads"])
    assert g["stats"]["components"] == 1 and g["stats"]["left_out_pieces"] > 0
    assert any("left out" in w for w in g["warnings"])
