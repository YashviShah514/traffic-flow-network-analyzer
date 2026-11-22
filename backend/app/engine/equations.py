"""
Flow-conservation equation and matrix generator.

Convention (physically correct):
    incoming + external_inflow = outgoing
=>  incoming - outgoing = -external_inflow
where ``external_inflow`` is the NET traffic entering the junction from outside
the modelled network (positive = enters, negative = leaves the network).
Known (sensor) road flows are moved to the right-hand side; only unknown roads
become variables x1, x2, ... (numbered in road order).
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
    external_inflow: Fraction = Fraction(0)


@dataclass
class RoadIn:
    key: str
    source: str
    target: str
    label: str = ""
    known_flow: Fraction | None = None


def validate(junctions: list[JunctionIn], roads: list[RoadIn]) -> None:
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
    var_index = {names[r.key]: i for i, r in enumerate(var_list)}
    variables = [{"name": names[r.key], "road_key": r.key, "source": r.source,
                  "target": r.target, "label": r.label} for r in var_list]
    jname = {j.key: j.name for j in junctions}

    equations, A, B = [], [], []
    for j in junctions:
        incoming = [r for r in roads if r.target == j.key]
        outgoing = [r for r in roads if r.source == j.key]
        coeffs: dict[str, Fraction] = {v["name"]: Fraction(0) for v in variables}
        known_in = Fraction(0)
        known_out = Fraction(0)

        def desc(r: RoadIn) -> dict:
            return {"road_key": r.key, "label": r.label, "from": jname[r.source], "to": jname[r.target],
                    "variable": names.get(r.key), "known_flow": None if r.known_flow is None else fmt(r.known_flow)}

        for r in incoming:
            if r.known_flow is None:
                coeffs[names[r.key]] += 1
            else:
                known_in += r.known_flow
        for r in outgoing:
            if r.known_flow is None:
                coeffs[names[r.key]] -= 1
            else:
                known_out += r.known_flow
        # incoming - outgoing = -external  =>  unknown part = -ext - known_in + known_out
        rhs = -j.external_inflow - known_in + known_out
        row = [coeffs[v["name"]] for v in variables]
        A.append(row)
        B.append(rhs)
        nz = {k: v for k, v in coeffs.items() if v != 0}
        equations.append({
            "junction_key": j.key,
            "junction_name": j.name,
            "incoming": [desc(r) for r in incoming],
            "outgoing": [desc(r) for r in outgoing],
            "external_inflow": fmt(j.external_inflow),
            "known_in_sum": fmt(known_in),
            "known_out_sum": fmt(known_out),
            "coefficients": {k: fmt(v) for k, v in coeffs.items()},
            "rhs": fmt(rhs),
            "text": equation_text(nz, rhs),
            "derivation": [
                f"Conservation at {j.name}: incoming + external inflow = outgoing.",
                f"Known incoming = {fmt(known_in)}, known outgoing = {fmt(known_out)}, external net inflow = {fmt(j.external_inflow)}.",
                "Unknown incoming variables: " + (", ".join(names[r.key] for r in incoming if r.key in names) or "none")
                + "; unknown outgoing variables: " + (", ".join(names[r.key] for r in outgoing if r.key in names) or "none") + ".",
                f"(unknown incoming) - (unknown outgoing) = -({fmt(j.external_inflow)}) - {fmt(known_in)} + {fmt(known_out)} = {fmt(rhs)}.",
            ],
        })
    aug = [row + [b] for row, b in zip(A, B)]
    return SystemBuild(variables, equations, A, B, aug)
