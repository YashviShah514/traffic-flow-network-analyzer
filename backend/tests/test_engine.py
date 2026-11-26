from fractions import Fraction as F

import pytest

from app.engine.equations import JunctionIn, NetworkError, RoadIn, build_system
from app.engine.linalg import mat_vec, matrix_to_str, replay, row_reduce
from app.engine.validation import validate_network
from app.services.demo_networks import DEMO_NETWORKS
from tests.helpers import net


def demo(i):
    d = DEMO_NETWORKS[i]
    return ([(j["key"], j["net_demand"]) for j in d["junctions"]],
            [(r["key"], r["source"], r["target"], r["known_flow"]) for r in d["roads"]])


def test_equations_follow_incoming_minus_outgoing_equals_demand():
    r = net(*demo(0))
    assert [e["text"] for e in r["equations"]] == ["-x1 = -60", "x1 - x2 = 30", "x2 = 30"]
    assert r["matrix"]["A"] == [["-1", "0"], ["1", "-1"], ["0", "1"]]
    assert r["matrix"]["B"] == ["-60", "30", "30"]
    assert r["matrix"]["augmented"][0] == ["-1", "0", "-60"]


def test_unique_solution():
    r = net(*demo(0))
    a = r["analysis"]
    assert a["classification"] == "unique" and a["rank"] == 2 and a["free_variables"] == []
    assert a["pivot_variables"] == ["x1", "x2"] and a["independent_equations"] == 2
    assert r["sample_solution"]["values"] == {"x1": "60", "x2": "30"}
    assert [s["status"] for s in r["road_status"]] == ["determined", "determined", "known"]
    assert r["verification"]["all_passed"]


def test_infinite_solution_and_nullspace():
    r = net(*demo(1))
    a = r["analysis"]
    assert a["classification"] == "infinite" and a["free_variables"] == ["x3"]
    assert a["null_basis"][0]["vector"] == ["1", "-1", "1"]
    assert [g["expression"] for g in a["general_solution"]] == ["30 + t1", "70 - t1", "t1"]
    assert {"variable": "x2", "text": "70 - t1 ≥ 0"} in a["constraints"]
    assert [s["status"] for s in r["road_status"]] == ["parametric", "parametric", "free", "known"]
    assert r["verification"]["all_passed"] and r["verification"]["sympy"]["agrees"]
    assert r["feasibility"]["ranges"]["x3"] == {"min": 0.0, "max": 70.0}


def test_advanced_network():
    r = net(*demo(2))
    a = r["analysis"]
    assert a["rank"] == 4 and a["nullity"] == 2 and a["n_unknowns"] == 6
    assert r["graph"]["weakly_connected"] and r["graph"]["strongly_connected"]
    assert r["verification"]["all_passed"]
    # ground truth used to build the demo: x = (50, 40, 15, 35, 45, 30) lies in the solution set
    t = {"t1": F(15), "t2": F(30)}
    vals = {g["variable"]: F(g["constant"]) + sum(F(c["coefficient"]) * t[c["parameter"]] for c in g["terms"])
            for g in a["general_solution"]}
    assert [vals[f"x{i}"] for i in range(1, 7)] == [50, 40, 15, 35, 45, 30]


def test_inconsistent_system():
    r = net([("A", -10), ("B", 0)], [("r1", "A", "B", None)])
    assert r["analysis"]["classification"] == "none"
    assert r["analysis"]["inconsistent_rows"]
    assert r["feasibility"]["exists"] is False
    assert r["road_status"][0]["status"] == "unresolved"
    assert "inconsistent" in r["conclusion"]


def test_overdetermined_consistent():
    r = net([("A", -5), ("B", 0), ("C", 5)], [("r1", "A", "B", None), ("r2", "B", "C", None)])
    assert r["analysis"]["n_equations"] == 3 and r["analysis"]["n_unknowns"] == 2
    assert r["analysis"]["classification"] == "unique"
    assert r["sample_solution"]["values"] == {"x1": "5", "x2": "5"}


def test_underdetermined():
    r = net([("A", -10), ("B", 10)], [("r1", "A", "B", None), ("r2", "A", "B", None)])
    a = r["analysis"]
    assert a["n_unknowns"] > a["rank"] and a["classification"] == "infinite"
    assert r["verification"]["all_passed"]


def test_negative_flow_not_physical():
    # vehicles must enter at B and leave at A, but the only road points A -> B
    r = net([("A", 10), ("B", -10)], [("r1", "A", "B", None)])
    assert r["analysis"]["classification"] == "unique"
    assert r["sample_solution"]["values"]["x1"] == "-10"  # not silently clipped to 0
    assert r["sample_solution"]["physically_feasible"] is False
    assert r["feasibility"]["exists"] is False
    assert r["sample_solution"]["mathematically_valid"] is True


def test_parameter_choice_feasibility():
    r = net(*demo(1), parameters={"x3": F(100)})
    s = r["sample_solution"]
    assert s["values"] == {"x1": "130", "x2": "-30", "x3": "100"}
    assert not s["physically_feasible"] and s["negative_variables"] == ["x2"]
    assert r["feasible_example"]["physically_feasible"]


def test_all_roads_known():
    ok = net([("A", -5), ("B", 5)], [("r1", "A", "B", 5)])
    assert ok["analysis"]["n_unknowns"] == 0 and ok["analysis"]["classification"] == "unique"
    bad = net([("A", -5), ("B", 5)], [("r1", "A", "B", 4)])
    assert bad["analysis"]["classification"] == "none"


@pytest.mark.parametrize("js,rs", [
    ([], []),
    ([("A", 0), ("A", 0)], []),
    ([("A", 0)], [("r", "A", "Z", None)]),
    ([("A", 0)], [("r", "A", "A", None)]),
    ([("A", 0), ("B", 0)], [("r", "A", "B", -1)]),
])
def test_structural_errors(js, rs):
    with pytest.raises(NetworkError):
        net(js, rs)


def test_validation_report_lists_every_problem():
    js = [{"key": "A", "name": "A", "net_demand": "x"}, {"key": "A", "name": "A2"}, {"key": "B", "name": "B"},
          {"key": "C", "name": "C", "net_demand": "5"}]
    rs = [{"key": "r1", "source": "A", "target": "A"}, {"key": "r1", "source": "A", "target": "Z"},
          {"key": "r2", "source": "", "target": "B"}, {"key": "r3", "source": "A", "target": "B", "known_flow": "-4"},
          {"key": "r4", "source": "A", "target": "B", "known_flow": "abc"}]
    v = validate_network(js, rs)
    codes = {e["code"] for e in v["errors"]}
    assert not v["ok"]
    assert codes >= {"duplicate_junction_id", "duplicate_road_id", "invalid_demand", "self_loop", "invalid_edge",
                     "missing_endpoint", "negative_flow", "invalid_flow"}
    warned = {w["code"] for w in v["warnings"]}
    assert warned >= {"isolated_junction", "disconnected", "unbalanced_demand", "parallel_roads"}


def test_circulation_is_in_nullspace():
    sb = build_system([JunctionIn(k, k, F(0)) for k in "ABC"],
                      [RoadIn("1", "A", "B"), RoadIn("2", "B", "C"), RoadIn("3", "C", "A")])
    red = row_reduce(sb.aug, 3)
    assert red.rank == 2
    assert not any(mat_vec(sb.A, [F(1), F(1), F(1)]))


@pytest.mark.parametrize("i", [0, 1, 2])
def test_row_operations_replay_to_ref_and_rref_and_preserve_solutions(i):
    js, rs = demo(i)
    sb = build_system([JunctionIn(k, k, F(d)) for k, d in js],
                      [RoadIn(k, s, t, "", None if v is None else F(v)) for k, s, t, v in rs])
    n = len(sb.variables)
    red = row_reduce(sb.aug, n)
    forward = [s for s in red.steps if s.phase == "forward"]
    assert replay(sb.aug, red.steps, len(forward)) == matrix_to_str(red.ref)
    assert replay(sb.aug, red.steps, len(red.steps)) == matrix_to_str(red.rref)
    solution = net(js, rs)["feasible_example"]["values"]
    x = [F(solution[v["name"]]) for v in sb.variables]
    for k in range(len(red.steps) + 1):  # every intermediate matrix keeps the same solutions
        m = [[F(c) for c in row] for row in replay(sb.aug, red.steps, k)]
        assert mat_vec([row[:n] for row in m], x) == [row[n] for row in m]


def test_swap_step_when_leading_zero():
    red = row_reduce([[F(0), F(1), F(2)], [F(1), F(0), F(3)]], 2)
    assert red.steps[0].kind == "swap" and red.steps[0].notation == "R1 ↔ R2"
    assert red.rref == [[1, 0, 3], [0, 1, 2]]


def test_row_operation_notation():
    red = row_reduce([[F(1), F(1), F(3)], [F(2), F(1), F(4)]], 2)
    assert [s.notation for s in red.steps if s.kind == "add"][0] == "R2 → R2 - 2R1"


def test_fractional_arithmetic_exact():
    r = net([("A", "-1/3"), ("B", "1/3")], [("r1", "A", "B", None)])
    assert r["sample_solution"]["values"]["x1"] == "1/3"


def test_null_space_exists_even_when_inconsistent():
    r = net([("A", -10), ("B", 0), ("C", 0)], [("r1", "A", "B", None), ("r2", "B", "C", None), ("r3", "C", "B", None)])
    a = r["analysis"]
    assert a["classification"] == "none"
    assert a["nullity"] == a["n_unknowns"] - a["rank"] and a["nullity"] >= 1
    assert len(a["null_basis"]) == a["nullity"] and r["circulations"]
    assert r["verification"]["null_vectors_satisfy_Av_0"] and r["verification"]["sympy"]["nullspace_matches"]
