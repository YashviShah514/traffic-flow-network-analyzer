from fractions import Fraction as F

from app.engine.equations import JunctionIn, RoadIn
from app.engine.pipeline import analyze


def net(junctions, roads, **kw):
    """junctions: [(key, ext)], roads: [(key, src, dst, known|None)]"""
    js = [JunctionIn(k, k, F(e)) for k, e in junctions]
    rs = [RoadIn(k, s, t, k, None if v is None else F(v)) for k, s, t, v in roads]
    return analyze(js, rs, **kw)
