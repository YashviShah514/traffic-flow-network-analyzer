"""
Flow-conservation equation and matrix generator.

Convention
----------
    incoming flow - outgoing flow = D

where D is the junction's **net external demand**: the net number of vehicles
that leave the modelled network at that junction (positive = vehicles exit
here, negative = vehicles enter here). This is the same statement as
"vehicles in = vehicles out" once the external traffic is counted.

Known (sensor) road flows are moved to the right-hand side; only unknown roads
become variables x1, x2, ... numbered in road order.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .linalg import Matrix, fmt


class NetworkError(ValueError):
    """Raised for structurally invalid networks."""


@dataclass
class JunctionIn:
    key: str
    name: str
    net_demand: Fraction = Fraction(0)


@dataclass
class RoadIn:
    key: str
    source: str
    target: str
    label: str = ""
    known_flow: Fraction | None = None


def validate(junctions: list[JunctionIn], roads: list[RoadIn]) -> None:
    """Hard structural checks. The solver refuses to run if any of these fail."""
    if not junctions:
        raise NetworkError("Network needs at least one junction.")
    keys = [j.key for j in junctions]
    if len(set(keys)) != len(keys):
        raise NetworkError("Junction keys must be unique.")
    rkeys = [r.key for r in roads]
    if len(set(rkeys)) != len(rkeys):
        raise NetworkError("Road keys must be unique.")
    ks = set(keys)
    for r in roads:
        if r.source not in ks or r.target not in ks:
            raise NetworkError(f"Road {r.key} references a junction that does not exist.")
        if r.source == r.target:
            raise NetworkError(f"Road {r.key} is a self-loop; a road must connect two different junctions.")
        if r.known_flow is not None and r.known_flow < 0:
            raise NetworkError(f"Road {r.key} has a negative measured flow; traffic counts must be >= 0.")


def variable_names(roads: list[RoadIn]) -> dict[str, str]:
    """road key -> 'x1', 'x2', ... for unknown roads only."""
    out: dict[str, str] = {}
    for r in roads:
        if r.known_flow is None:
            out[r.key] = f"x{len(out) + 1}"
    return out


def _term(coef: Fraction, var: str, first: bool) -> str:
    sign = "-" if coef < 0 else "+"
    mag = abs(coef)
    body = var if mag == 1 else f"{fmt(mag)}{var}"
    if first:
        return ("-" if coef < 0 else "") + body
    return f" {sign} {body}"


def equation_text(coeffs: dict[str, Fraction], rhs: Fraction) -> str:
    s = ""
    for var, c in coeffs.items():
        if c != 0:
            s += _term(c, var, s == "")
    return f"{s or '0'} = {fmt(rhs)}"


def _side(names: list[str], values: list[Fraction]) -> str:
    parts = names + [fmt(v) for v in values]
    return " + ".join(parts) if parts else "0"


@dataclass
class SystemBuild:
    variables: list[dict]   # [{name, road_key, source, target, label}]
    equations: list[dict]   # one per junction (full derivation)
    A: Matrix
    B: list[Fraction]
    aug: Matrix


def build_system(junctions: list[JunctionIn], roads: list[RoadIn]) -> SystemBuild:
    validate(junctions, roads)
    names = variable_names(roads)
    var_list = [r for r in roads if r.known_flow is None]
    variables = [{"name": names[r.key], "road_key": r.key, "source": r.source,
                  "target": r.target, "label": r.label} for r in var_list]
    jname = {j.key: j.name for j in junctions}
    index = {r.key: i for i, r in enumerate(var_list)}
    into: dict[str, list[RoadIn]] = {j.key: [] for j in junctions}
    outof: dict[str, list[RoadIn]] = {j.key: [] for j in junctions}
    for r in roads:
        into[r.target].append(r)
        outof[r.source].append(r)

    equations, A, B = [], [], []
    for j in junctions:
        incoming, outgoing = into[j.key], outof[j.key]
        row = [Fraction(0)] * len(var_list)
        known_in = known_out = Fraction(0)
        for r in incoming:
            if r.known_flow is None:
                row[index[r.key]] += 1
            else:
                known_in += r.known_flow
        for r in outgoing:
            if r.known_flow is None:
                row[index[r.key]] -= 1
            else:
                known_out += r.known_flow
        # in - out = D  =>  (unknown in) - (unknown out) = D - known_in + known_out
        rhs = j.net_demand - known_in + known_out
        A.append(row)
        B.append(rhs)

        def desc(r: RoadIn) -> dict:
            return {"road_key": r.key, "label": r.label, "from": jname[r.source], "to": jname[r.target],
                    "variable": names.get(r.key), "known_flow": None if r.known_flow is None else fmt(r.known_flow)}

        coeffs = {names[r.key]: row[index[r.key]] for r in incoming + outgoing if r.known_flow is None}
        coeffs = dict(sorted(coeffs.items(), key=lambda kv: int(kv[0][1:])))
        in_vars = [names[r.key] for r in incoming if r.known_flow is None]
        out_vars = [names[r.key] for r in outgoing if r.known_flow is None]
        in_known = [r.known_flow for r in incoming if r.known_flow is not None]
        out_known = [r.known_flow for r in outgoing if r.known_flow is not None]
        equations.append({
            "junction_key": j.key,
            "junction_name": j.name,
            "incoming": [desc(r) for r in incoming],
            "outgoing": [desc(r) for r in outgoing],
            "net_demand": fmt(j.net_demand),
            "known_in_sum": fmt(known_in),
            "known_out_sum": fmt(known_out),
            "coefficients": {k: fmt(v) for k, v in coeffs.items() if v != 0},
            "rhs": fmt(rhs),
            "text": equation_text(coeffs, rhs),
            "derivation": [
                f"Conservation at {j.name}: incoming - outgoing = D, with net external demand D = {fmt(j.net_demand)}.",
                f"Substituting the roads: ({_side(in_vars, in_known)}) - ({_side(out_vars, out_known)}) = {fmt(j.net_demand)}.",
                f"Move known flows to the right: (unknown in) - (unknown out) = {fmt(j.net_demand)} - {fmt(known_in)} + {fmt(known_out)} = {fmt(rhs)}.",
                f"Equation: {equation_text(coeffs, rhs)}.",
            ],
        })
    aug = [row + [b] for row, b in zip(A, B)]
    return SystemBuild(variables, equations, A, B, aug)
