"""
Exact-arithmetic row reduction (written from scratch; SymPy is used only to
cross-check results in ``verification.py``).

All numbers are ``fractions.Fraction`` so there is no floating point error.

Terminology
-----------
* Gaussian elimination  -> forward elimination to Row Echelon Form (REF).
* Gauss-Jordan          -> continue from REF: scale pivots to 1 and clear the
                           entries above each pivot, giving the Reduced Row
                           Echelon Form (RREF).
Pivot candidates are taken only from the coefficient columns, never from the
augmented (constant) column.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

Matrix = list[list[Fraction]]


def fmt(x: Fraction) -> str:
    """Fraction -> '3', '-7/2'."""
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def matrix_to_str(m: Matrix) -> list[list[str]]:
    return [[fmt(v) for v in row] for row in m]


def copy_matrix(m: Matrix) -> Matrix:
    return [row[:] for row in m]


@dataclass
class Step:
    """One recorded row operation (or pivot selection) with the matrix after it."""
    index: int
    phase: str  # 'forward' (Gaussian) | 'backward' (Gauss-Jordan)
    kind: str  # 'pivot' | 'swap' | 'scale' | 'add'
    description: str
    notation: str  # e.g. "R2 <- R2 - 3 R1"
    matrix: list[list[str]]
    pivot: Optional[tuple[int, int]] = None  # (row, col) 0-based


@dataclass
class Reduction:
    ref: Matrix
    rref: Matrix
    steps: list[Step]
    pivot_cols: list[int]  # pivot column of row i is pivot_cols[i]
    rank: int
    # Row-echelon matrix right after Gaussian (forward) phase, before scaling.
    n_vars: int = 0
    notes: list[str] = field(default_factory=list)


def _coef(c: Fraction) -> str:
    return fmt(c)


def gaussian_elimination(aug: Matrix, n_vars: int) -> tuple[Matrix, list[Step], list[int]]:
    """Forward elimination. Returns (REF, steps, pivot_cols).

    The first non-zero entry in the working column (at or below the current
    row) is chosen as pivot; with exact arithmetic no numerical pivoting is
    required.
    """
    m = copy_matrix(aug)
    rows = len(m)
    steps: list[Step] = []
    pivot_cols: list[int] = []
    r = 0
    for c in range(n_vars):
        if r >= rows:
            break
        p = next((i for i in range(r, rows) if m[i][c] != 0), None)
        if p is None:
            continue  # no pivot in this column -> free variable
        if p != r:
            m[r], m[p] = m[p], m[r]
            steps.append(Step(len(steps) + 1, "forward", "swap",
                              f"Row swap: column {c + 1} has a zero at row {r + 1}, so bring row {p + 1} up.",
                              f"R{r + 1} <-> R{p + 1}", matrix_to_str(m), (r, c)))
        steps.append(Step(len(steps) + 1, "forward", "pivot",
                          f"Pivot selected at row {r + 1}, column {c + 1} (value {fmt(m[r][c])}).",
                          f"pivot = a[{r + 1},{c + 1}] = {fmt(m[r][c])}", matrix_to_str(m), (r, c)))
        for i in range(r + 1, rows):
            if m[i][c] != 0:
                factor = m[i][c] / m[r][c]
                m[i] = [a - factor * b for a, b in zip(m[i], m[r])]
                sign = "-" if factor > 0 else "+"
                mag = abs(factor)
                coef = "" if mag == 1 else _coef(mag) + " "
                steps.append(Step(len(steps) + 1, "forward", "add",
                                  f"Eliminate entry ({i + 1},{c + 1}) below the pivot.",
                                  f"R{i + 1} <- R{i + 1} {sign} {coef}R{r + 1}", matrix_to_str(m), (r, c)))
        pivot_cols.append(c)
        r += 1
    return m, steps, pivot_cols


def gauss_jordan(ref: Matrix, pivot_cols: list[int], steps: list[Step]) -> Matrix:
    """Continue from REF to RREF (appends to ``steps``)."""
    m = copy_matrix(ref)
    for r in range(len(pivot_cols) - 1, -1, -1):
        c = pivot_cols[r]
        if m[r][c] != 1:
            pv = m[r][c]
            m[r] = [v / pv for v in m[r]]
            steps.append(Step(len(steps) + 1, "backward", "scale",
                              f"Scale row {r + 1} so the pivot becomes 1.",
                              f"R{r + 1} <- (1/{fmt(pv)}) R{r + 1}",
                              matrix_to_str(m), (r, c)))
        for i in range(r):
            if m[i][c] != 0:
                factor = m[i][c]
                m[i] = [a - factor * b for a, b in zip(m[i], m[r])]
                sign = "-" if factor > 0 else "+"
                mag = abs(factor)
                coef = "" if mag == 1 else _coef(mag) + " "
                steps.append(Step(len(steps) + 1, "backward", "add",
                                  f"Clear entry ({i + 1},{c + 1}) above the pivot.",
                                  f"R{i + 1} <- R{i + 1} {sign} {coef}R{r + 1}", matrix_to_str(m), (r, c)))
    return m


def row_reduce(aug: Matrix, n_vars: int) -> Reduction:
    """Full pipeline: Gaussian elimination (REF) then Gauss-Jordan (RREF)."""
    ref, steps, pivots = gaussian_elimination(aug, n_vars)
    rref = gauss_jordan(ref, pivots, steps)
    return Reduction(ref=ref, rref=rref, steps=steps, pivot_cols=pivots,
                     rank=len(pivots), n_vars=n_vars)


def back_substitution(ref: Matrix, pivot_cols: list[int], n_vars: int) -> list[Fraction]:
    """Particular solution (free variables = 0) from the REF by classic back
    substitution. Used as an independent cross-check of the RREF-based answer."""
    x = [Fraction(0)] * n_vars
    for r in range(len(pivot_cols) - 1, -1, -1):
        c = pivot_cols[r]
        s = ref[r][n_vars] - sum(ref[r][j] * x[j] for j in range(c + 1, n_vars))
        x[c] = s / ref[r][c]
    return x


def mat_vec(a: Matrix, x: list[Fraction]) -> list[Fraction]:
    return [sum((v * xi for v, xi in zip(row, x)), Fraction(0)) for row in a]
