"""Persistence helpers: payload <-> ORM <-> engine inputs."""
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction

from sqlalchemy.orm import Session

from .. import models as m
from ..engine.equations import JunctionIn, NetworkError, RoadIn, validate
from ..engine.pipeline import analyze
from ..schemas import NetworkSchema, num_str, to_fraction


def dec_to_fraction(d) -> Fraction:
    return Fraction(str(d))


def get_default_user(db: Session) -> m.User:
    u = db.query(m.User).filter_by(username="demo").first()
    if not u:
        u = m.User(username="demo")
        db.add(u)
        db.flush()
    return u


def payload_to_engine(p: NetworkSchema) -> tuple[list[JunctionIn], list[RoadIn]]:
    js = [JunctionIn(j.key, j.name, to_fraction(j.external_inflow) or Fraction(0)) for j in p.junctions]
    rs = [RoadIn(r.key, r.source, r.target, r.label, to_fraction(r.known_flow)) for r in p.roads]
    validate(js, rs)
    return js, rs


def orm_to_payload(n: m.Network) -> dict:
    return {
        "id": n.id, "name": n.name, "description": n.description, "is_demo": n.is_demo,
        "created_at": n.created_at.isoformat(), "updated_at": n.updated_at.isoformat(),
        "junctions": [{"key": j.key, "name": j.name, "x": j.x, "y": j.y,
                       "external_inflow": num_str(dec_to_fraction(j.external_inflow))} for j in n.junctions],
        "roads": [{"key": r.key, "label": r.label, "source": r.source.key, "target": r.target.key,
                   "known_flow": num_str(dec_to_fraction(r.observed.value)) if r.observed else None}
                  for r in n.roads],
    }


def orm_to_schema(n: m.Network) -> NetworkSchema:
    return NetworkSchema(**{k: v for k, v in orm_to_payload(n).items()
                            if k in ("name", "description", "junctions", "roads")})


def save_network(db: Session, p: NetworkSchema, network: m.Network | None = None, is_demo: bool = False) -> m.Network:
    payload_to_engine(p)  # validates; raises NetworkError
    if network is None:
        network = m.Network(user_id=get_default_user(db).id, name=p.name, description=p.description, is_demo=is_demo)
        db.add(network)
    else:
        network.name, network.description = p.name, p.description
        network.updated_at = datetime.now(timezone.utc)
        network.roads.clear()
        network.junctions.clear()
        db.flush()
        # Old solutions describe an old topology; keep history but they stay linked by network id.
    jmap = {}
    for j in p.junctions:
        orm = m.Junction(key=j.key, name=j.name, x=j.x, y=j.y, external_inflow=Decimal(str(j.external_inflow)))
        network.junctions.append(orm)
        jmap[j.key] = orm
    db.flush()
    for i, r in enumerate(p.roads):
        road = m.Road(key=r.key, label=r.label, source_id=jmap[r.source].id, target_id=jmap[r.target].id, position=i)
        if r.known_flow is not None:
            road.observed = m.ObservedFlow(value=Decimal(str(r.known_flow)))
        network.roads.append(road)
    db.commit()
    db.refresh(network)
    return network


def save_solution(db: Session, network: m.Network, parameters: dict, start: str | None = None) -> m.Solution:
    schema = orm_to_schema(network)
    js, rs = payload_to_engine(schema)
    result = analyze(js, rs, {k: to_fraction(v) for k, v in parameters.items()}, start)
    a = result["analysis"]
    s = m.Solution(network_id=network.id, classification=a["classification"], rank=a["rank"],
                   n_equations=a["n_equations"], n_unknowns=a["n_unknowns"], free_variables=a["free_variables"],
                   parameters=parameters, result={"analysis": a, "sample_solution": result["sample_solution"],
                                                  "conclusion": result["conclusion"],
                                                  "verified": result["verification"]["all_passed"]})
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def seed_demos(db: Session) -> None:
    from .demo_networks import DEMO_NETWORKS
    if db.query(m.Network).filter_by(is_demo=True).count():
        return
    for d in DEMO_NETWORKS:
        n = save_network(db, NetworkSchema(**d), is_demo=True)
        save_solution(db, n, {})
