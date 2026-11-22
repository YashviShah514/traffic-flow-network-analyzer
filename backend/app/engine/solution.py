"""Solution analysis: classification, general solution, null space, feasibility
and independent verification (exact arithmetic, SymPy cross-check, LP)."""
from __future__ import annotations

from fractions import Fraction

from .linalg import Reduction, back_substitution, fmt, mat_vec, Matrix


def analyse(red: Reduction, n_vars: int, var_names: list[str]) -> dict:
    rref = red.rref
    pivots = red.pivot_cols
    inconsistent_rows = [i for i, row in enumerate(rref)
                         if all(v == 0 for v in row[:n_vars]) and row[n_vars] != 0]
    consistent = not inconsistent_rows
    free = [c for c in range(n_vars) if c not in pivots]
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
        "n_unknowns": n_vars,
        "n_equations": len(rref),
        "nullity": n_vars - red.rank,
        "pivot_columns": [var_names[c] for c in pivots],
        "free_variables": [var_names[c] for c in free],
        "inconsistent_rows": [i + 1 for i in inconsistent_rows],
        "null_basis": result_null,
        "_basis": basis,
        "_free": free,
    }
    if not consistent:
        result["particular"] = None
        result["general_solution"] = []
        return result

    particular = [Fraction(0)] * n_vars
    for r, c in enumerate(pivots):
        particular[c] = rref[r][n_vars]
    result["particular"] = [fmt(v) for v in particular]
    # x_i = p_i + sum_k t_k * v_k[i]
    gs = []
    for i in range(n_vars):
        terms = [{"parameter": f"t{k + 1}", "coefficient": fmt(basis[k][i])} for k in range(len(basis)) if basis[k][i] != 0]
        if i in free:
            text = f"{var_names[i]} = t{free.index(i) + 1} (free)"
        else:
            text = f"{var_names[i]} = {fmt(particular[i])}"
            for t in terms:
                c = Fraction(t["coefficient"])
                text += f" {'-' if c < 0 else '+'} " + ("" if abs(c) == 1 else fmt(abs(c)) + "*") + t["parameter"]
        gs.append({"variable": var_names[i], "constant": fmt(particular[i]), "terms": terms,
                   "is_free": i in free, "text": text})
    result["general_solution"] = gs
    result["_particular"] = particular
    return result


def instantiate(particular: list[Fraction], basis: list[list[Fraction]], params: list[Fraction]) -> list[Fraction]:
    x = particular[:]
    for t, v in zip(params, basis):
        x = [xi + t * vi for xi, vi in zip(x, v)]
    return x


def feasibility(A: Matrix, B: list[Fraction], n_vars: int) -> dict:
    """Does ANY nonnegative solution of Ax=b exist, and what is the range of each
    unknown flow over all nonnegative solutions? (LP via SciPy, floating point.)"""
    if n_vars == 0:
        ok = all(b == 0 for b in B)
        return {"exists": ok, "ranges": {}, "point": [], "method": "trivial"}
    try:
        import numpy as np
        from scipy.optimize import linprog
    except Exception:  # pragma: no cover
        return {"exists": None, "ranges": {}, "point": None, "method": "unavailable"}
    Af = np.array([[float(v) for v in row] for row in A])
    bf = np.array([float(b) for b in B])
    bounds = [(0, None)] * n_vars
    res = linprog(np.zeros(n_vars), A_eq=Af, b_eq=bf, bounds=bounds, method="highs")
    if res.status != 0:
        return {"exists": False, "ranges": {}, "point": None, "method": "linprog-highs"}
    ranges = {}
    for i in range(n_vars):
        c = np.zeros(n_vars)
        c[i] = 1
        lo = linprog(c, A_eq=Af, b_eq=bf, bounds=bounds, method="highs")
        hi = linprog(-c, A_eq=Af, b_eq=bf, bounds=bounds, method="highs")
        ranges[i] = {"min": round(float(lo.fun), 6) + 0.0 if lo.status == 0 else None,
                     "max": round(float(-hi.fun), 6) + 0.0 if hi.status == 0 else None}  # None = unbounded
    return {"exists": True, "ranges": ranges, "point": [float(v) for v in res.x], "method": "linprog-highs"}


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
    checks["null_vectors_satisfy_Av_0"] = all(all(c == 0 for c in mat_vec(A, v)) for v in info["_basis"]) if n_vars else True
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
    if n_vars == 0 or not A:
        return {"skipped": True, "agrees": True}
    import sympy as sp
    M = sp.Matrix([[sp.Rational(v.numerator, v.denominator) for v in row] for row in A])
    aug = M.row_join(sp.Matrix([sp.Rational(b.numerator, b.denominator) for b in B]))
    sp_rref, sp_piv = aug.rref()
    sp_pivots = [p for p in sp_piv if p < n_vars]
    mine = sp.Matrix([[sp.Rational(v.numerator, v.denominator) for v in row] for row in red.rref])
    out = {
        "rank_matches": M.rank() == red.rank,
        "pivots_match": sorted(sp_pivots) == sorted(red.pivot_cols),
        "rref_matches": mine == sp_rref,
        "consistent_matches": (n_vars not in sp_piv) == info["consistent"],
    }
    ns = M.nullspace()
    out["nullity_matches"] = len(ns) == info["nullity"]
    if True:
        # same subspace: stack my basis with SymPy's -> rank must not grow
        if ns:
            mine_b = sp.Matrix([[sp.Rational(c.numerator, c.denominator) for c in v] for v in info["_basis"]])
            sp_b = sp.Matrix.hstack(*ns).T
            out["nullspace_matches"] = mine_b.rank() == sp_b.rank() == sp.Matrix.vstack(mine_b, sp_b).rank()
    out["agrees"] = all(v for v in out.values() if isinstance(v, bool))
    return out
