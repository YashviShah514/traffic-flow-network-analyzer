from fractions import Fraction as F

import pytest

from app.engine.equations import JunctionIn, NetworkError, RoadIn, build_system
from app.engine.linalg import mat_vec, row_reduce
from app.services.demo_networks import DEMO_NETWORKS
from tests.helpers import net


def demo(i):
    d = DEMO_NETWORKS[i]
    return ([(j["key"], j["external_inflow"]) for j in d["junctions"]],
            [(r["key"], r["source"], r["target"], r["known_flow"]) for r in d["roads"]])


def test_unique_solution():
    r = net(*demo(0))
    a = r["analysis"]
    assert a["classification"] == "unique" and a["rank"] == 2 and a["free_variables"] == []
    assert r["sample_solution"]["values"] == {"x1": "60", "x2": "30"}
    assert r["verification"]["all_passed"]


def test_infinite_solution_and_nullspace():
    r = net(*demo(1))
    a = r["analysis"]
    assert a["classification"] == "infinite" and a["free_variables"] == ["x3"]
    assert a["null_basis"][0]["vector"] == ["1", "-1", "1"]
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
    r = net([("A", 10), ("B", 0)], [("r1", "A", "B", None)])
    assert r["analysis"]["classification"] == "none"
    assert r["analysis"]["inconsistent_rows"]
    assert r["feasibility"]["exists"] is False
    assert "inconsistent" in r["conclusion"]


def test_overdetermined_consistent():
    r = net([("A", 5), ("B", 0), ("C", -5)], [("r1", "A", "B", None), ("r2", "B", "C", None)])
    assert r["analysis"]["n_equations"] == 3 and r["analysis"]["n_unknowns"] == 2
    assert r["analysis"]["classification"] == "unique"
    assert r["sample_solution"]["values"] == {"x1": "5", "x2": "5"}


def test_underdetermined():
    r = net([("A", 10), ("B", -10)], [("r1", "A", "B", None), ("r2", "A", "B", None)])
    a = r["analysis"]
    assert a["n_unknowns"] > a["rank"] and a["classification"] == "infinite"
    assert r["verification"]["all_passed"]


def test_negative_flow_not_physical():
    r = net([("A", -10), ("B", 10)], [("r1", "A", "B", None)])
    assert r["analysis"]["classification"] == "unique"
    assert r["sample_solution"]["physically_feasible"] is False
    assert r["feasibility"]["exists"] is False
    assert r["sample_solution"]["mathematically_valid"] is True


def test_parameter_choice_feasibility():
    r = net(*demo(1), parameters={"x3": F(100)})
    s = r["sample_solution"]
    assert s["values"] == {"x1": "130", "x2": "-30", "x3": "100"}
    assert not s["physically_feasible"] and s["negative_variables"] == ["x2"]
    assert r["feasible_example"]["physically_feasible"]


def test_all_roads_known_consistent():
    r = net([("A", 5), ("B", -5)], [("r1", "A", "B", 5)])
    assert r["analysis"]["n_unknowns"] == 0 and r["analysis"]["classification"] == "unique"


def test_all_roads_known_inconsistent():
    r = net([("A", 5), ("B", -5)], [("r1", "A", "B", 4)])
    assert r["analysis"]["classification"] == "none"


@pytest.mark.parametrize("js,rs", [
    ([], []),
    ([("A", 0), ("A", 0)], []),
    ([("A", 0)], [("r", "A", "Z", None)]),
    ([("A", 0)], [("r", "A", "A", None)]),
    ([("A", 0), ("B", 0)], [("r", "A", "B", -1)]),
])
def test_validation_errors(js, rs):
    with pytest.raises(NetworkError):
        net(js, rs)


def test_circulation_is_in_nullspace():
    sb = build_system([JunctionIn(k, k, F(0)) for k in "ABC"],
                      [RoadIn("1", "A", "B"), RoadIn("2", "B", "C"), RoadIn("3", "C", "A")])
    red = row_reduce(sb.aug, 3)
    assert red.rank == 2
    assert {s.kind for s in red.steps} >= {"pivot", "add"}
    assert all(c == 0 for c in mat_vec(sb.A, [F(1), F(1), F(1)]))


def test_swap_step_when_leading_zero():
    red = row_reduce([[F(0), F(1), F(2)], [F(1), F(0), F(3)]], 2)
    assert red.steps[0].kind == "swap" and red.rref == [[1, 0, 3], [0, 1, 2]]


def test_fractional_arithmetic_exact():
    r = net([("A", "1/3"), ("B", "-1/3")], [("r1", "A", "B", None)])
    assert r["sample_solution"]["values"]["x1"] == "1/3"


def test_null_space_exists_even_when_inconsistent():
    # one road A->B with a dangling extra equation: inconsistent, but A has a nontrivial null space
    r = net([("A", 10), ("B", 0), ("C", 0)], [("r1", "A", "B", None), ("r2", "B", "C", None), ("r3", "C", "B", None)])
    a = r["analysis"]
    assert a["classification"] == "none"
    assert a["nullity"] == a["n_unknowns"] - a["rank"] and a["nullity"] >= 1
    assert len(a["null_basis"]) == a["nullity"] and r["circulations"]
    assert r["verification"]["null_vectors_satisfy_Av_0"] and r["verification"]["sympy"]["nullspace_matches"]
