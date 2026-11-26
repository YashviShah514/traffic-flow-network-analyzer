import copy
import pytest

from sqlalchemy import text

from app import main, migrations, models
from app.database import make_engine
from app.services import osm
from app.services.demo_networks import DEMO_NETWORKS


def _new(name="Mine"):
    n = copy.deepcopy(DEMO_NETWORKS[1])
    n["name"] = name
    return n


def _create(client, body=None):
    r = client.post("/api/networks", json=body or _new())
    assert r.status_code == 201, r.text
    return r.json()


def _dash(client):
    return client.get("/api/dashboard").json()


def test_health_and_seed(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    nets = client.get("/api/networks").json()
    assert sum(n["is_demo"] for n in nets) == 3
    assert {n["status"]["classification"] for n in nets} == {"unique", "infinite"}


def test_dashboard_numbers_come_from_the_database(client):
    d = _dash(client)
    assert (d["total_networks"], d["total_junctions"], d["solved_networks"]) == (3, 11, 3)
    for n in d["networks"]:
        assert client.delete(f"/api/networks/{n['id']}").status_code == 204
    d = _dash(client)
    assert (d["total_networks"], d["total_junctions"], d["solved_networks"], d["networks"]) == (0, 0, 0, [])
    nid = _create(client)["id"]
    d = _dash(client)
    assert (d["total_networks"], d["total_junctions"], d["solved_networks"]) == (1, 3, 0)
    assert d["networks"][0]["method"] == "manual" and d["networks"][0]["status"]["state"] == "not_solved"
    client.post(f"/api/networks/{nid}/solutions", json={})
    assert _dash(client)["solved_networks"] == 1


def test_crud_roundtrip_and_persistence(client):
    saved = _create(client)
    nid = saved["id"]
    got = client.get(f"/api/networks/{nid}").json()
    assert got["roads"][3]["known_flow"] == "10" and got["junctions"][0]["net_demand"] == "-90"
    with client.session_factory() as db:  # a brand-new session = "after refresh"
        assert db.query(models.Network).filter_by(name="Mine").count() == 1
        assert db.query(models.ObservedFlow).count() == 4
    upd = _new("Renamed")
    upd["roads"][3]["known_flow"] = None
    assert client.put(f"/api/networks/{nid}", json=upd).json()["name"] == "Renamed"
    assert client.get(f"/api/networks/{nid}").json()["roads"][3]["known_flow"] is None
    assert client.delete(f"/api/networks/{nid}").status_code == 204
    assert client.get(f"/api/networks/{nid}").status_code == 404


def test_map_fields_persist(client):
    n = _new("Mapped")
    n.update(method="map", map_meta={"pickup": {"label": "P"}})
    n["junctions"][0].update(lat=23.01, lng=72.55, node_type="pickup")
    n["roads"][0].update(geometry=[[23.01, 72.55], [23.02, 72.56]], length_m=120.5, osm_way_id="42",
                         highway="primary", origin="osm")
    got = client.get(f"/api/networks/{_create(client, n)['id']}").json()
    assert got["method"] == "map" and got["map_meta"]["pickup"]["label"] == "P"
    assert got["junctions"][0]["lat"] == 23.01 and got["junctions"][0]["node_type"] == "pickup"
    assert got["roads"][0]["geometry"] == [[23.01, 72.55], [23.02, 72.56]] and got["roads"][0]["origin"] == "osm"


def test_editing_the_maths_marks_solutions_outdated_but_renaming_does_not(client):
    nid = _create(client)["id"]
    client.post(f"/api/networks/{nid}/solutions", json={"parameters": {"x3": 5}})
    renamed = _new("Other name")
    renamed["junctions"][0]["x"] = 999
    assert client.put(f"/api/networks/{nid}", json=renamed).json()["status"]["state"] == "solved"
    changed = _new("Other name")
    changed["roads"][3]["known_flow"] = "12"
    assert client.put(f"/api/networks/{nid}", json=changed).json()["status"]["state"] == "outdated"
    assert client.get(f"/api/networks/{nid}/solutions").json()[0]["stale"] is True


def test_deleting_a_road_removes_its_flow_and_rebuilds_equations(client):
    nid = _create(client)["id"]
    n = _new()
    del n["roads"][3]  # the sensor road
    client.put(f"/api/networks/{nid}", json=n)
    with client.session_factory() as db:
        assert db.query(models.ObservedFlow).count() == 3  # only the demos' three remain
    r = client.post("/api/analyze", json={"network": n}).json()["result"]
    assert r["equations"][0]["text"] == "-x1 - x2 = -90"


def test_deleting_a_junction_removes_connected_roads(client):
    nid = _create(client)["id"]
    n = _new()
    n["junctions"] = [j for j in n["junctions"] if j["key"] != "B"]
    bad = client.put(f"/api/networks/{nid}", json=n)
    assert bad.status_code == 422 and "does not exist" in bad.json()["detail"]  # never silently dropped
    assert len(client.get(f"/api/networks/{nid}").json()["roads"]) == 4  # failed write changed nothing
    n["roads"] = [r for r in n["roads"] if "B" not in (r["source"], r["target"])]
    saved = client.put(f"/api/networks/{nid}", json=n).json()
    assert len(saved["junctions"]) == 2 and len(saved["roads"]) == 2
    with client.session_factory() as db:
        assert db.query(models.Road).filter_by(network_id=nid).count() == 2


def test_analyze_returns_validation_and_results(client):
    out = client.post("/api/analyze", json={"network": _new(), "parameters": {"x3": 5}}).json()
    assert out["validation"]["ok"] and out["result"]["sample_solution"]["values"]["x1"] == "35"
    assert out["result"]["verification"]["all_passed"]
    n = _new()
    n["roads"][0]["target"] = "nope"
    n["roads"][3]["known_flow"] = "abc"
    out = client.post("/api/analyze", json={"network": n}).json()
    assert out["result"] is None and {e["code"] for e in out["validation"]["errors"]} == {"invalid_edge", "invalid_flow"}


def test_save_rejects_invalid_data(client):
    n = _new()
    n["roads"][3]["known_flow"] = -4
    assert client.post("/api/networks", json=n).status_code == 422
    assert client.get("/api/networks/9999").status_code == 404
    assert client.post("/api/analyze", json={"network": _new(), "parameters": {"x3": "zz"}}).status_code == 422


def test_demo_networks_are_read_only(client):
    demo = client.get("/api/networks").json()[0]
    assert demo["is_demo"]
    assert client.put(f"/api/networks/{demo['id']}", json=_new()).status_code == 403
    assert client.get(f"/api/networks/{demo['id']}").json()["name"] == demo["name"]


def test_pdf_report(client):
    r = client.post("/api/report", json={"network": DEMO_NETWORKS[2]})
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 3000
    n = _new()
    for road in n["roads"]:
        road["label"] = ""
    assert client.post("/api/report", json={"network": n, "parameters": {"x3": 100}}).status_code == 200


def test_pdf_report_large_network(client):
    n = {"name": "Ring", "junctions": [{"key": f"J{i}", "name": f"J{i}", "x": i * 10, "y": (i % 3) * 40} for i in range(30)],
         "roads": [{"key": f"r{i}", "source": f"J{i}", "target": f"J{(i + 1) % 30}"} for i in range(30)]}
    r = client.post("/api/report", json={"network": n})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_geocode_and_map_errors_are_reported(client, monkeypatch):
    assert client.get("/api/geocode", params={"q": "ab"}).json() == []  # too short: no upstream call

    def boom(*_):
        raise osm.ServiceError("The photon map service did not respond. Please retry.")

    monkeypatch.setattr(osm, "search_places", boom)
    r = client.get("/api/geocode", params={"q": "college"})
    assert r.status_code == 502 and "retry" in r.json()["detail"]
    far = {"pickup": {"lat": 23.0, "lng": 72.5}, "destination": {"lat": 24.0, "lng": 72.5}}
    r = client.post("/api/map/network", json=far)
    assert r.status_code == 422 and "limit" in r.json()["detail"]


def test_upgrade_from_version_1_database(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as c:
        c.execute(text("CREATE TABLE junctions (id INTEGER PRIMARY KEY, network_id INTEGER, key VARCHAR(64), "
                       "name VARCHAR(80), x FLOAT, y FLOAT, external_inflow NUMERIC(18,6) NOT NULL)"))
        c.execute(text("INSERT INTO junctions VALUES (1, 1, 'A', 'A', 0, 0, 100), (2, 1, 'B', 'B', 0, 0, -30)"))
    assert any("net_demand" in change for change in migrations.upgrade(engine))
    with engine.connect() as c:
        assert [float(v) for (v,) in c.execute(text("SELECT net_demand FROM junctions ORDER BY id"))] == [-100, 30]
        assert [t for (t,) in c.execute(text("SELECT node_type FROM junctions"))] == ["junction", "junction"]
    assert migrations.upgrade(engine) == []  # running again changes nothing


def test_pdf_report_shows_the_chosen_solution(client):
    pymupdf = pytest.importorskip("pymupdf")  # optional: only needed to read the PDF back
    r = client.post("/api/report", json={"network": _new(), "parameters": {"x3": 5}})
    text = " ".join(" ".join(page.get_text() for page in pymupdf.open(stream=r.content, filetype="pdf")).split())
    assert "x1 = 30 + t1" in text and "Chosen parameter values (parameters: x3 = 5)" in text
    assert "A to B A -> B 35 computed" in text and "A to C A -> C 65 computed" in text
