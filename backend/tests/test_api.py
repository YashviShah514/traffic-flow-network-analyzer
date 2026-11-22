import copy

from app import models
from app.services.demo_networks import DEMO_NETWORKS


def _new():
    n = copy.deepcopy(DEMO_NETWORKS[1])
    n["name"] = "Mine"
    return n


def test_health_and_seed(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    nets = client.get("/api/networks").json()
    assert sum(n["is_demo"] for n in nets) == 3
    assert {n["classification"] for n in nets} == {"unique", "infinite"}


def test_dashboard_from_database(client):
    d = client.get("/api/dashboard").json()
    assert d["total_networks"] == 3 and d["total_junctions"] == 11 and d["total_roads"] == 14
    assert d["solved_networks"] == 3 and d["networks_with_free_variables"] == 2


def test_crud_roundtrip_and_persistence(client):
    r = client.post("/api/networks", json=_new())
    assert r.status_code == 201
    nid = r.json()["id"]
    got = client.get(f"/api/networks/{nid}").json()
    assert got["roads"][3]["known_flow"] == "10" and got["junctions"][0]["external_inflow"] == "90"
    with client.session_factory() as db:  # a brand-new session = "after refresh"
        assert db.query(models.Network).filter_by(name="Mine").count() == 1
        assert db.query(models.ObservedFlow).count() == 4
    upd = _new()
    upd["name"] = "Renamed"
    upd["roads"][3]["known_flow"] = None
    assert client.put(f"/api/networks/{nid}", json=upd).json()["name"] == "Renamed"
    assert client.get(f"/api/networks/{nid}").json()["roads"][3]["known_flow"] is None
    assert client.delete(f"/api/networks/{nid}").status_code == 204
    assert client.get(f"/api/networks/{nid}").status_code == 404


def test_analyze_draft_and_save_solution(client):
    n = _new()
    a = client.post("/api/analyze", json={"network": n, "parameters": {"x3": 5}}).json()
    assert a["sample_solution"]["values"]["x1"] == "35" and a["verification"]["all_passed"]
    nid = client.post("/api/networks", json=n).json()["id"]
    assert client.post(f"/api/networks/{nid}/solutions", json={"parameters": {"x3": 5}}).status_code == 201
    assert client.get(f"/api/networks/{nid}/solutions").json()[0]["classification"] == "infinite"
    assert client.post(f"/api/networks/{nid}/analysis", json={}).json()["analysis"]["rank"] == 2


def test_validation_errors_are_422(client):
    n = _new()
    n["roads"][0]["target"] = "nope"
    assert client.post("/api/analyze", json={"network": n}).status_code == 422
    n = _new()
    n["roads"][3]["known_flow"] = -4
    assert client.post("/api/networks", json=n).status_code == 422
    n = _new()
    n["roads"][3]["known_flow"] = "abc"
    assert client.post("/api/networks", json=n).status_code == 422
    assert client.get("/api/networks/9999").status_code == 404


def test_disconnected_network_api(client):
    n = {"name": "Split", "description": "", "junctions": [
        {"key": "A", "name": "A"}, {"key": "B", "name": "B"}, {"key": "C", "name": "C"}],
        "roads": [{"key": "r", "source": "A", "target": "B"}]}
    g = client.post("/api/analyze", json={"network": n}).json()["graph"]
    assert not g["weakly_connected"] and g["isolated_junctions"] == ["C"]


def test_pdf_report(client):
    r = client.post("/api/report", json={"network": DEMO_NETWORKS[2]})
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 3000


def test_demo_networks_are_read_only(client):
    demo = client.get("/api/networks").json()[0]
    assert demo["is_demo"]
    body = _new()
    assert client.put(f"/api/networks/{demo['id']}", json=body).status_code == 403
    assert client.get(f"/api/networks/{demo['id']}").json()["name"] == demo["name"]


def test_pdf_report_unlabelled_roads_and_parameters(client):
    n = _new()
    for r in n["roads"]:
        r["label"] = ""
    r = client.post("/api/report", json={"network": n, "parameters": {"x3": 100}})   # infeasible choice
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
