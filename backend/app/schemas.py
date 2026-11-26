"""Pydantic request schemas: the single graph model shared by both creation methods.

Flow values arrive as raw text/numbers and are checked by ``engine.validation`` so that every
problem can be reported together instead of failing on the first one.
"""
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Number = str | float | int | None


def num_str(f: Fraction) -> str:
    """Canonical decimal text for a stored number (<= 6 decimals)."""
    return str(f.numerator) if f.denominator == 1 else format(float(f), "f").rstrip("0").rstrip(".")


def _text(v):
    return None if v is None or (isinstance(v, str) and not v.strip()) else str(v).strip()


class JunctionSchema(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    x: float = 0
    y: float = 0
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    node_type: str = Field(default="junction", max_length=16)
    net_demand: Number = "0"

    @field_validator("net_demand")
    @classmethod
    def _n(cls, v):
        return _text(v) or "0"


class RoadSchema(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(default="", max_length=120)
    source: str = ""
    target: str = ""
    known_flow: Number = None
    length_m: float | None = Field(default=None, ge=0)
    geometry: list[tuple[float, float]] | None = Field(default=None, max_length=4000)
    osm_way_id: str | None = Field(default=None, max_length=32)
    highway: str = Field(default="", max_length=32)
    origin: Literal["osm", "user"] = "user"

    @field_validator("known_flow")
    @classmethod
    def _n(cls, v):
        return _text(v)


class NetworkSchema(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    method: Literal["manual", "map"] = "manual"
    map_meta: dict | None = None
    junctions: list[JunctionSchema] = Field(max_length=600)
    roads: list[RoadSchema] = Field(max_length=900)


class AnalyzeRequest(BaseModel):
    network: NetworkSchema
    parameters: dict[str, str | float | int] = {}
    start_junction: str | None = None  # junction key for BFS


class SolveRequest(BaseModel):
    parameters: dict[str, str | float | int] = {}


class Place(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    label: str = Field(default="", max_length=200)


class MapNetworkRequest(BaseModel):
    start: Place   # Location 1
    end: Place     # Location 2
    detail: Literal["main", "all"] = "main"
    radius_m: float = Field(default=150, ge=50, le=400)
    prune_stubs: bool = True
    trip_flow: float = Field(default=0, ge=0, le=100000)
