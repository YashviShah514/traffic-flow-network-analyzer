"""The single analysis pipeline used by BOTH creation methods:
equations -> matrices -> row reduction -> classification -> flows -> graph."""
from __future__ import annotations

from fractions import Fraction

from . import solution as sol
from .equations import JunctionIn, RoadIn, build_system, variable_names
from .linalg import fmt, matrix_to_str, row_reduce
from ..graph.analysis import analyse_graph


def _step_dict(s) -> dict:
    return {"index": s.index, "phase": s.phase, "kind": s.kind, "description": s.description,
            "notation": s.notation, "changed": {str(k): v for k, v in s.changed.items()},
            "pivot": list(s.pivot) if s.pivot else None}


def analyze(junctions: list[JunctionIn], roads: list[RoadIn], parameters: dict[str, Fraction] | None = None,
            start: str | None = None) -> dict:
    sb = build_system(junctions, roads)
    var_names = [v["name"] for v in sb.variables]
    n = len(var_names)
    red = row_reduce(sb.aug, n)
    info = sol.analyse(red, n, var_names)
    fe = sol.feasibility(sb.A, sb.B, n)
    parameters = parameters or {}

    sample = None
    feasible_example = None
    x_sample = None
    if info["consistent"]:
        particular, basis, free = info["_particular"], info["_basis"], info["_free"]
        free_names = [var_names[f] for f in free]
        params = [parameters.get(name, Fraction(0)) for name in free_names]
        x_sample = sol.instantiate(particular, basis, params)
        sample = _describe_solution(x_sample, var_names, sb, roads, junctions, free_names, params)
        if fe.get("exists"):
            p = sol.nearest_feasible_parameters(particular, basis, free, fe["point"])
            if p is not None:
                feasible_example = _describe_solution(sol.instantiate(particular, basis, p), var_names, sb, roads,
                                                      junctions, free_names, p)

    # circulation vectors mapped onto roads (null space of A: valid even if AX = B is inconsistent)
    circulations = [{"parameter": b["parameter"], "free_variable": b["free_variable"],
                     "roads": [{"variable": var_names[i], "road_key": sb.variables[i]["road_key"],
                                "coefficient": b["vector"][i]}
                               for i in range(n) if b["vector"][i] != "0"]}
                    for b in info["null_basis"]]

    fe_out = dict(fe)
    fe_out["ranges"] = {var_names[i]: r for i, r in fe.get("ranges", {}).items()}
    fe_out.pop("point", None)

    verification = sol.verify(sb.A, sb.B, red, info, n, x_sample)
    names = {j.key: j.name for j in junctions}
    graph = analyse_graph([j.key for j in junctions], names, [(r.source, r.target) for r in roads], start)

    public_info = {k: v for k, v in info.items() if not k.startswith("_")}
    return {
        "variables": sb.variables,
        "equations": sb.equations,
        "matrix": {"A": matrix_to_str(sb.A), "B": [fmt(b) for b in sb.B], "augmented": matrix_to_str(sb.aug),
                   "variables": var_names},
        "reduction": {"ref": matrix_to_str(red.ref), "rref": matrix_to_str(red.rref),
                      "steps": [_step_dict(s) for s in red.steps]},
        "analysis": public_info,
        "road_status": _road_status(roads, public_info),
        "sample_solution": sample,
        "feasible_example": feasible_example,
        "feasibility": fe_out,
        "circulations": circulations,
        "verification": verification,
        "graph": graph,
        "conclusion": _conclusion(public_info, fe_out),
    }


def _road_status(roads: list[RoadIn], info: dict) -> list[dict]:
    """How each road's flow is determined; drives the colouring of the final network."""
    names = variable_names(roads)
    general = {g["variable"]: g for g in info["general_solution"]}
    out = []
    for r in roads:
        var = names.get(r.key)
        if var is None:
            out.append({"road_key": r.key, "variable": None, "status": "known", "expression": fmt(r.known_flow)})
            continue
        g = general.get(var)
        if g is None:
            status, expr = "unresolved", var
        elif g["is_free"]:
            status, expr = "free", g["terms"][0]["parameter"]
        elif g["terms"]:
            status, expr = "parametric", g["expression"]
        else:
            status, expr = "determined", g["expression"]
        out.append({"road_key": r.key, "variable": var, "status": status, "expression": expr})
    return out


def _describe_solution(x, var_names, sb, roads, junctions, free_names, params) -> dict:
    flows = {v: fmt(val) for v, val in zip(var_names, x)}
    road_flows = []
    xi = dict(zip([v["road_key"] for v in sb.variables], x))
    jn = {j.key: j.name for j in junctions}
    for r in roads:
        val = r.known_flow if r.known_flow is not None else xi[r.key]
        road_flows.append({"road_key": r.key, "label": r.label, "from": jn[r.source], "to": jn[r.target],
                           "value": fmt(val), "known": r.known_flow is not None, "negative": val < 0})
    negatives = [v for v, val in zip(var_names, x) if val < 0]
    return {"parameters": {n: fmt(p) for n, p in zip(free_names, params)},
            "values": flows, "roads": road_flows,
            "mathematically_valid": True,           # satisfies AX = B (verified separately)
            "physically_feasible": not negatives,   # all flows >= 0
            "negative_variables": negatives}


def _conclusion(info: dict, fe: dict) -> str:
    c = info["classification"]
    if c == "none":
        return ("The system is inconsistent (rank [A|B] > rank A): the measured flows and external demands "
                "cannot all be correct, so no flow assignment satisfies conservation.")
    if c == "unique":
        txt = "The system has a unique solution: every unknown flow is fully determined by the measurements."
    else:
        txt = (f"The system has infinitely many solutions with {info['nullity']} free parameter(s); "
               "the extra freedom is circulating traffic described by the null space.")
    if fe.get("exists") is True:
        txt += " At least one nonnegative (physically feasible) assignment exists."
    elif fe.get("exists") is False:
        txt += " However, no nonnegative assignment exists, so the solution is not physically feasible."
    return txt
