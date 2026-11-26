"""Solution analysis: classification, general solution, null space, feasibility
and independent verification (exact arithmetic, SymPy cross-check, LP)."""
from __future__ import annotations

from fractions import Fraction

from .linalg import Reduction, back_substitution, fmt, mat_vec, Matrix

# Above this many unknowns the per-road min/max linear programs are skipped.
MAX_RANGE_VARIABLES = 160


def analyse(red: Reduction, n_vars: int, var_names: list[str]) -> dict:
    rref = red.rref
    pivots = red.pivot_cols
    pivot_set = set(pivots)
    inconsistent_rows = [i for i, row in enumerate(rref)
                         if row[n_vars] != 0 and not any(row[:n_vars])]
    consistent = not inconsistent_rows
    free = [c for c in range(n_vars) if c not in pivot_set]

    # The null space depends on A only (AX = 0), so it exists whether or not AX = B is consistent.
    basis: list[list[Fraction]] = []
    for f in free:
        v = [Fraction(0)] * n_vars
        v[f] = Fraction(1)
        for r, c in enumerate(pivots):
            v[c] = -rref[r][f]
        basis.append(v)
    result_null = [{"parameter": f"t{k + 1}", "free_variable": var_names[free[k]],
                    "vector": [fmt(v) for v in vec]} for k, vec in enumerate(basis)]

    if not consistent:
        classification = "none"
    elif free:
        classification = "infinite"
    else:
        classification = "unique"

    result: dict = {
        "classification": classification,
        "consistent": consistent,
        "rank": red.rank,
        "independent_equations": red.rank,
        "n_unknowns": n_vars,
        "n_equations": len(rref),
        "nullity": n_vars - red.rank,
        "pivot_columns": [c + 1 for c in pivots],
        "pivot_variables": [var_names[c] for c in pivots],
        "free_variables": [var_names[c] for c in free],
        "inconsistent_rows": [i + 1 for i in inconsistent_rows],
        "null_basis": result_null,
        "_basis": basis,
        "_free": free,
    }
    if not consistent:
        result["particular"] = None
        result["general_solution"] = []
        result["constraints"] = []
        return result

    particular = [Fraction(0)] * n_vars
    for r, c in enumerate(pivots):
        particular[c] = rref[r][n_vars]
    result["particular"] = [fmt(v) for v in particular]
    # x_i = p_i + sum_k t_k * v_k[i]
    free_pos = {f: k for k, f in enumerate(free)}
    gs, constraints = [], []
    for i in range(n_vars):
        terms = [{"parameter": f"t{k + 1}", "coefficient": fmt(basis[k][i])} for k in range(len(basis)) if basis[k][i] != 0]
        expr = _expression(particular[i], terms)
        if i in free_pos:
            text = f"{var_names[i]} = t{free_pos[i] + 1} (free)"
        else:
            text = f"{var_names[i]} = {expr}"
        gs.append({"variable": var_names[i], "constant": fmt(particular[i]), "terms": terms,
                   "is_free": i in free_pos, "expression": expr, "text": text})
        if terms:  # nonnegativity of this road restricts the parameters
            constraints.append({"variable": var_names[i], "text": f"{expr} ≥ 0"})
    result["general_solution"] = gs
    result["constraints"] = constraints
    result["_particular"] = particular
    return result


def _expression(constant: Fraction, terms: list[dict]) -> str:
    out = "" if constant == 0 and terms else fmt(constant)
    for t in terms:
        c = Fraction(t["coefficient"])
        body = ("" if abs(c) == 1 else fmt(abs(c)) + "·") + t["parameter"]
        if not out:
            out = ("-" if c < 0 else "") + body
        else:
            out += f" {'-' if c < 0 else '+'} {body}"
    return out


def instantiate(particular: list[Fraction], basis: list[list[Fraction]], params: list[Fraction]) -> list[Fraction]:
    x = particular[:]
    for t, v in zip(params, basis):
        if t:
            x = [xi + t * vi if vi else xi for xi, vi in zip(x, v)]
    return x


def feasibility(A: Matrix, B: list[Fraction], n_vars: int) -> dict:
    """Does ANY nonnegative solution of Ax=b exist, and what is the range of each
    unknown flow over all nonnegative solutions? (LP via SciPy, floating point.)"""
    if n_vars == 0:
        ok = all(b == 0 for b in B)
        return {"exists": ok, "ranges": {}, "point": [], "method": "trivial", "ranges_skipped": False}
    try:
        import numpy as np
        from scipy.optimize import linprog
    except Exception:  # pragma: no cover
        return {"exists": None, "ranges": {}, "point": None, "method": "unavailable", "ranges_skipped": True}
    Af = np.array([[float(v) for v in row] for row in A])
    bf = np.array([float(b) for b in B])
    bounds = [(0, None)] * n_vars
    res = linprog(np.zeros(n_vars), A_eq=Af, b_eq=bf, bounds=bounds, method="highs")
    if res.status != 0:
        return {"exists": False, "ranges": {}, "point": None, "method": "linprog-highs", "ranges_skipped": False}
    ranges = {}
    skipped = n_vars > MAX_RANGE_VARIABLES
    if not skipped:
        for i in range(n_vars):
            c = np.zeros(n_vars)
            c[i] = 1
            lo = linprog(c, A_eq=Af, b_eq=bf, bounds=bounds, method="highs")
            hi = linprog(-c, A_eq=Af, b_eq=bf, bounds=bounds, method="highs")
            ranges[i] = {"min": round(float(lo.fun), 6) + 0.0 if lo.status == 0 else None,
                         "max": round(float(-hi.fun), 6) + 0.0 if hi.status == 0 else None}  # None = unbounded
    return {"exists": True, "ranges": ranges, "point": [float(v) for v in res.x], "method": "linprog-highs",
            "ranges_skipped": skipped}


def nearest_feasible_parameters(particular, basis, free, point) -> list[Fraction] | None:
    """Turn the LP point into exact rational parameters (the free coordinates)
    and keep them only if the resulting solution is exactly nonnegative."""
    if point is None:
        return None
    for limit in (1, 10, 1000):
        params = [Fraction(point[f]).limit_denominator(limit) for f in free]
        x = instantiate(particular, basis, params)
        if all(v >= 0 for v in x):
            return params
    return None


def verify(A: Matrix, B: list[Fraction], red: Reduction, info: dict, n_vars: int, x: list[Fraction] | None) -> dict:
    """Independent checks. Every check is reported with a boolean."""
    checks: dict = {}
    checks["null_vectors_satisfy_Av_0"] = all(not any(mat_vec(A, v)) for v in info["_basis"]) if n_vars else True
    checks["rank_plus_nullity_equals_unknowns"] = info["rank"] + info["nullity"] == n_vars
    if info["consistent"] and x is not None:
        checks["AX_equals_B"] = mat_vec(A, x) == B if n_vars else all(b == 0 for b in B)
        bs = back_substitution(red.ref, red.pivot_cols, n_vars)
        checks["back_substitution_agrees"] = mat_vec(A, bs) == B if n_vars else True
    checks["sympy"] = _sympy_check(A, B, red, info, n_vars)
    checks["all_passed"] = all(v for k, v in checks.items() if k != "sympy" and isinstance(v, bool)) and \
        checks["sympy"].get("agrees", True)
    return checks


def _sympy_check(A, B, red, info, n_vars) -> dict:
    """Cross-check with SymPy's DomainMatrix (exact rationals, fast enough for large networks)."""
    if n_vars == 0 or not A:
        return {"skipped": True, "agrees": True}
    from sympy import QQ
    from sympy.polys.matrices import DomainMatrix

    def dm(rows, ncols):
        return DomainMatrix([[QQ(v.numerator, v.denominator) for v in r] for r in rows], (len(rows), ncols), QQ)

    aug_rref, aug_pivots = dm([row + [b] for row, b in zip(A, B)], n_vars + 1).to_sparse().rref()
    sp_pivots = [p for p in aug_pivots if p < n_vars]
    mine = dm(red.rref, n_vars + 1)
    out = {
        "rank_matches": len(sp_pivots) == red.rank,
        "pivots_match": sorted(sp_pivots) == sorted(red.pivot_cols),
        "rref_matches": aug_rref.to_dense() == mine,
        "consistent_matches": (n_vars not in aug_pivots) == info["consistent"],
    }
    nullity = n_vars - len(sp_pivots)
    out["nullity_matches"] = nullity == info["nullity"]
    if info["nullity"] and len(A) and n_vars <= 250:
        ns = dm(A, n_vars).to_sparse().nullspace().to_dense()
        my_basis = dm(info["_basis"], n_vars)
        stacked = ns.vstack(my_basis)
        out["nullspace_matches"] = my_basis.rank() == ns.rank() == stacked.rank()
    out["agrees"] = all(v for v in out.values() if isinstance(v, bool))
    return out
