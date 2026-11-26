"""Persistence helpers: payload <-> ORM <-> engine inputs. Writes are single transactions."""
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction

from sqlalchemy.orm import Session

from .. import models as m
from ..engine.equations import JunctionIn, NetworkError, RoadIn
from ..engine.linalg import fmt
from ..engine.pipeline import analyze
from ..engine.validation import parse_number, validate_network
from ..schemas import NetworkSchema, num_str


def get_default_user(db: Session) -> m.User:
    u = db.query(m.User).filter_by(username="demo").first()
    if not u:
        u = m.User(username="demo")
        db.add(u)
        db.flush()
    return u


def validation_report(p: NetworkSchema) -> dict:
    return validate_network([j.model_dump() for j in p.junctions], [r.model_dump() for r in p.roads])


def require_valid(p: NetworkSchema) -> dict:
    report = validation_report(p)
    if not report["ok"]:
        raise NetworkError(" ".join(e["message"] for e in report["errors"]))
    return report


def payload_to_engine(p: NetworkSchema) -> tuple[list[JunctionIn], list[RoadIn]]:
    require_valid(p)
    js = [JunctionIn(j.key, j.name, parse_number(j.net_demand) or Fraction(0)) for j in p.junctions]
    rs = [RoadIn(r.key, r.source, r.target, r.label, parse_number(r.known_flow)) for r in p.roads]
    return js, rs


def _num(value) -> str:
    return num_str(Fraction(str(value)))


def orm_to_payload(n: m.Network) -> dict:
    return {
        "id": n.id, "name": n.name, "description": n.description, "is_demo": n.is_demo,
        "method": n.method, "map_meta": n.map_meta,
        "created_at": n.created_at.isoformat(), "updated_at": n.updated_at.isoformat(),
        "status": network_status(n),
        "junctions": [{"key": j.key, "name": j.name, "x": j.x, "y": j.y, "lat": j.lat, "lng": j.lng,
                       "node_type": j.node_type, "net_demand": _num(j.net_demand)} for j in n.junctions],
        "roads": [{"key": r.key, "label": r.label, "source": r.source.key, "target": r.target.key,
                   "known_flow": _num(r.observed.value) if r.observed else None, "length_m": r.length_m,
                   "geometry": r.geometry, "osm_way_id": r.osm_way_id, "highway": r.highway, "origin": r.origin}
                  for r in n.roads],
    }


def orm_to_schema(n: m.Network) -> NetworkSchema:
    return NetworkSchema.model_validate(orm_to_payload(n))


def network_status(n: m.Network) -> dict:
    """not_solved | outdated | solved | inconsistent, from the latest stored solution."""
    if not n.solutions:
        return {"state": "not_solved", "classification": None, "rank": None}
    last = n.solutions[-1]
    state = "outdated" if last.stale else ("inconsistent" if last.classification == "none" else "solved")
    return {"state": state, "classification": last.classification, "rank": last.rank}


def summary(n: m.Network) -> dict:
    return {"id": n.id, "name": n.name, "description": n.description, "is_demo": n.is_demo, "method": n.method,
            "junctions": len(n.junctions), "roads": len(n.roads), "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat(), "status": network_status(n)}


def math_signature(p: NetworkSchema) -> tuple:
    """Everything that affects the equations (not names or positions)."""
    return (tuple((j.key, parse_number(j.net_demand) or 0) for j in p.junctions),
            tuple((r.key, r.source, r.target, parse_number(r.known_flow)) for r in p.roads))


def save_network(db: Session, p: NetworkSchema, network: m.Network | None = None, is_demo: bool = False) -> m.Network:
    require_valid(p)
    try:
        if network is None:
            network = m.Network(user_id=get_default_user(db).id, name=p.name, description=p.description,
                                is_demo=is_demo, method=p.method, map_meta=p.map_meta)
            db.add(network)
        else:
            changed = math_signature(orm_to_schema(network)) != math_signature(p)
            network.name, network.description = p.name, p.description
            network.method, network.map_meta = p.method, p.map_meta
            network.updated_at = datetime.now(timezone.utc)
            if changed:
                for s in network.solutions:
                    s.stale = True  # the stored solution no longer describes this network
            network.roads.clear()  # observed_flows go with their roads
            db.flush()
            network.junctions.clear()
            db.flush()
        jmap = {}
        for j in p.junctions:
            orm = m.Junction(key=j.key, name=j.name, x=j.x, y=j.y, lat=j.lat, lng=j.lng, node_type=j.node_type,
                             net_demand=Decimal(num_str(parse_number(j.net_demand) or Fraction(0))))
            network.junctions.append(orm)
            jmap[j.key] = orm
        db.flush()
        for i, r in enumerate(p.roads):
            road = m.Road(key=r.key, label=r.label, source_id=jmap[r.source].id, target_id=jmap[r.target].id,
                          position=i, length_m=r.length_m, geometry=[list(pt) for pt in r.geometry] if r.geometry else None,
                          osm_way_id=r.osm_way_id, highway=r.highway, origin=r.origin)
            flow = parse_number(r.known_flow)
            if flow is not None:
                road.observed = m.ObservedFlow(value=Decimal(num_str(flow)))
            network.roads.append(road)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(network)
    return network


def parse_parameters(parameters: dict) -> dict[str, Fraction]:
    out = {}
    for name, value in parameters.items():
        try:
            f = parse_number(value)
        except ValueError as e:
            raise NetworkError(f"Parameter {name}: {e}")
        if f is not None:
            out[name] = f
    return out


def save_solution(db: Session, network: m.Network, parameters: dict) -> m.Solution:
    js, rs = payload_to_engine(orm_to_schema(network))
    params = parse_parameters(parameters)
    result = analyze(js, rs, params)
    a = result["analysis"]
    s = m.Solution(network_id=network.id, classification=a["classification"], rank=a["rank"],
                   n_equations=a["n_equations"], n_unknowns=a["n_unknowns"], free_variables=a["free_variables"],
                   parameters={k: fmt(v) for k, v in params.items()},
                   result={"general_solution": a["general_solution"], "sample_solution": result["sample_solution"],
                           "conclusion": result["conclusion"], "verified": result["verification"]["all_passed"]})
    db.add(s)
    db.commit()
    db.refresh(s)
    db.refresh(network)
    return s


def seed_demos(db: Session) -> None:
    from .demo_networks import DEMO_NETWORKS
    if db.query(m.Network).count():  # never add sample data to a database the user is already using
        return
    for d in DEMO_NETWORKS:
        n = save_network(db, NetworkSchema.model_validate(d), is_demo=True)
        save_solution(db, n, {})
