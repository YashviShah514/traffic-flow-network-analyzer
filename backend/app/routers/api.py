"""REST API. All routes are under /api."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models as m
from ..database import get_db
from ..engine.equations import NetworkError
from ..engine.pipeline import analyze
from ..schemas import AnalyzeRequest, AnalyzeSavedRequest, NetworkSchema, to_fraction
from ..services import repository as repo
from ..services.report import build_pdf

router = APIRouter(prefix="/api")


def _run(schema: NetworkSchema, parameters: dict, start: str | None) -> dict:
    try:
        js, rs = repo.payload_to_engine(schema)
        params = {k: to_fraction(v) for k, v in parameters.items() if to_fraction(v) is not None}
        return analyze(js, rs, params, start)
    except (NetworkError, ValueError) as e:
        raise HTTPException(422, str(e))


def _get(db: Session, nid: int) -> m.Network:
    n = db.get(m.Network, nid)
    if not n:
        raise HTTPException(404, "Network not found")
    return n


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    networks = db.query(m.Network).order_by(m.Network.id).all()
    latest: dict[int, m.Solution] = {}
    for s in db.query(m.Solution).order_by(m.Solution.id).all():
        latest[s.network_id] = s
    activity = [{"type": "network", "title": n.name, "at": n.updated_at.isoformat(), "id": n.id} for n in networks]
    activity += [{"type": "solution", "title": f"Solved: {next((n.name for n in networks if n.id == s.network_id), '?')}",
                  "detail": s.classification, "at": s.created_at.isoformat(), "id": s.network_id}
                 for s in db.query(m.Solution).all()]
    activity.sort(key=lambda a: a["at"], reverse=True)
    return {
        "total_networks": len(networks),
        "total_junctions": db.query(m.Junction).count(),
        "total_roads": db.query(m.Road).count(),
        "solved_networks": len(latest),
        "networks_with_free_variables": sum(1 for s in latest.values() if s.n_unknowns - s.rank > 0 and s.classification == "infinite"),
        "per_network": [{"name": n.name, "junctions": len(n.junctions), "roads": len(n.roads)} for n in networks],
        "classification_counts": {c: sum(1 for s in latest.values() if s.classification == c) for c in ("unique", "infinite", "none")},
        "recent_activity": activity[:8],
    }


@router.get("/networks")
def list_networks(db: Session = Depends(get_db)):
    out = []
    for n in db.query(m.Network).order_by(m.Network.updated_at.desc()).all():
        last = n.solutions[-1] if n.solutions else None
        out.append({"id": n.id, "name": n.name, "description": n.description, "is_demo": n.is_demo,
                    "junctions": len(n.junctions), "roads": len(n.roads),
                    "updated_at": n.updated_at.isoformat(),
                    "classification": last.classification if last else None,
                    "rank": last.rank if last else None})
    return out


@router.post("/networks", status_code=201)
def create_network(p: NetworkSchema, db: Session = Depends(get_db)):
    try:
        return repo.orm_to_payload(repo.save_network(db, p))
    except NetworkError as e:
        raise HTTPException(422, str(e))


@router.get("/networks/{nid}")
def read_network(nid: int, db: Session = Depends(get_db)):
    return repo.orm_to_payload(_get(db, nid))


@router.put("/networks/{nid}")
def update_network(nid: int, p: NetworkSchema, db: Session = Depends(get_db)):
    n = _get(db, nid)
    if n.is_demo:
        raise HTTPException(403, "Demonstration networks are read-only. Save a copy instead.")
    try:
        return repo.orm_to_payload(repo.save_network(db, p, n))
    except NetworkError as e:
        raise HTTPException(422, str(e))


@router.delete("/networks/{nid}", status_code=204)
def delete_network(nid: int, db: Session = Depends(get_db)):
    db.delete(_get(db, nid))
    db.commit()


@router.post("/analyze")
def analyze_draft(req: AnalyzeRequest):
    """Analyse an (unsaved) network exactly as drawn in the editor."""
    return _run(req.network, req.parameters, req.start_junction)


@router.post("/networks/{nid}/analysis")
def analyze_saved(nid: int, req: AnalyzeSavedRequest, db: Session = Depends(get_db)):
    return _run(repo.orm_to_schema(_get(db, nid)), req.parameters, req.start_junction)


@router.post("/networks/{nid}/solutions", status_code=201)
def store_solution(nid: int, req: AnalyzeSavedRequest, db: Session = Depends(get_db)):
    s = repo.save_solution(db, _get(db, nid), req.parameters, req.start_junction)
    return {"id": s.id, "classification": s.classification, "rank": s.rank, "created_at": s.created_at.isoformat()}


@router.get("/networks/{nid}/solutions")
def list_solutions(nid: int, db: Session = Depends(get_db)):
    n = _get(db, nid)
    return [{"id": s.id, "created_at": s.created_at.isoformat(), "classification": s.classification, "rank": s.rank,
             "n_unknowns": s.n_unknowns, "n_equations": s.n_equations, "free_variables": s.free_variables,
             "parameters": s.parameters, "conclusion": s.result.get("conclusion"), "verified": s.result.get("verified")}
            for s in reversed(n.solutions)]


@router.get("/solutions")
def all_solutions(db: Session = Depends(get_db)):
    rows = db.query(m.Solution).order_by(m.Solution.id.desc()).limit(100).all()
    return [{"id": s.id, "network_id": s.network_id, "network": s.network.name, "created_at": s.created_at.isoformat(),
             "classification": s.classification, "rank": s.rank, "free_variables": s.free_variables} for s in rows]


@router.post("/report")
def report_for_draft(req: AnalyzeRequest):
    result = _run(req.network, req.parameters, req.start_junction)
    pdf = build_pdf(req.network, result)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="traffic-report.pdf"'})
