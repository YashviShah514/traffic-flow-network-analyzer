"""Pydantic request schemas. Numbers are accepted as int/float/str and converted to exact Fractions."""
from fractions import Fraction

from pydantic import BaseModel, Field, field_validator


def to_fraction(v) -> Fraction | None:
    if v is None or v == "":
        return None
    try:
        f = Fraction(str(v).strip())
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"'{v}' is not a valid number")
    if f.denominator > 10**6:
        raise ValueError("Use at most 6 decimal places")
    return f


def num_str(f: Fraction) -> str:
    """Canonical decimal text for a stored number (<= 6 decimals)."""
    return str(f.numerator) if f.denominator == 1 else format(float(f), "f").rstrip("0").rstrip(".")


class JunctionSchema(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    x: float = 0
    y: float = 0
    external_inflow: str | float | int = "0"

    @field_validator("external_inflow")
    @classmethod
    def _num(cls, v):
        f = to_fraction(v)
        return "0" if f is None else num_str(f)


class RoadSchema(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(default="", max_length=120)
    source: str
    target: str
    known_flow: str | float | int | None = None

    @field_validator("known_flow")
    @classmethod
    def _num(cls, v):
        f = to_fraction(v)
        if f is None:
            return None
        if f < 0:
            raise ValueError("Measured flow must be >= 0")
        return num_str(f)


class NetworkSchema(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    junctions: list[JunctionSchema]
    roads: list[RoadSchema]


class AnalyzeRequest(BaseModel):
    network: NetworkSchema
    parameters: dict[str, str | float | int] = {}
    start_junction: str | None = None  # junction key for BFS


class AnalyzeSavedRequest(BaseModel):
    parameters: dict[str, str | float | int] = {}
    start_junction: str | None = None
