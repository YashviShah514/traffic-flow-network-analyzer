"""REST API. All routes are under /api."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models as m
from ..database import get_db
from ..engine.equations import NetworkError
from ..engine.pipeline import analyze
from ..schemas import AnalyzeRequest, MapNetworkRequest, NetworkSchema, SolveRequest
from ..engine.sample import sample_values
from ..services import osm, osm_graph
from ..services import repository as repo
from ..services.report import build_pdf

router = APIRouter(prefix="/api")


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
    """Every number is computed from the database at request time."""
    networks = db.query(m.Network).order_by(m.Network.created_at.desc(), m.Network.id.desc()).all()
    items = [repo.summary(n) for n in networks]
    return {
        "total_networks": len(items),
        "total_junctions": db.query(m.Junction).count(),
        "solved_networks": sum(1 for i in items if i["status"]["state"] == "solved"),
        "networks": items,
    }


@router.get("/networks")
def list_networks(db: Session = Depends(get_db)):
    return [repo.summary(n) for n in db.query(m.Network).order_by(m.Network.updated_at.desc()).all()]


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
    """The one analysis endpoint used by both creation methods: validation first, then the solver."""
    validation = repo.validation_report(req.network)
    if not validation["ok"]:
        return {"validation": validation, "result": None}
    try:
        js, rs = repo.payload_to_engine(req.network)
        result = analyze(js, rs, repo.parse_parameters(req.parameters), req.start_junction)
    except NetworkError as e:
        raise HTTPException(422, str(e))
    return {"validation": validation, "result": result}


@router.post("/networks/{nid}/solutions", status_code=201)
def store_solution(nid: int, req: SolveRequest, db: Session = Depends(get_db)):
    n = _get(db, nid)
    try:
        s = repo.save_solution(db, n, req.parameters)
    except NetworkError as e:
        raise HTTPException(422, str(e))
    return {"id": s.id, "classification": s.classification, "rank": s.rank, "created_at": s.created_at.isoformat(),
            "status": repo.network_status(n)}


@router.get("/networks/{nid}/solutions")
def list_solutions(nid: int, db: Session = Depends(get_db)):
    return [{"id": s.id, "created_at": s.created_at.isoformat(), "classification": s.classification, "rank": s.rank,
             "n_unknowns": s.n_unknowns, "free_variables": s.free_variables, "parameters": s.parameters,
             "stale": s.stale, "conclusion": s.result.get("conclusion"), "verified": s.result.get("verified")}
            for s in reversed(_get(db, nid).solutions)]


@router.post("/sample-values")
def sample(network: NetworkSchema):
    """Clearly labelled demonstration traffic that satisfies conservation. NOT real counts."""
    try:
        repo.require_valid(network)
        return sample_values(network)
    except NetworkError as e:
        raise HTTPException(422, str(e))


@router.post("/report")
def report(req: AnalyzeRequest):
    """PDF of the network exactly as shown on screen, with the chosen parameter values."""
    try:
        js, rs = repo.payload_to_engine(req.network)
        result = analyze(js, rs, repo.parse_parameters(req.parameters))
    except NetworkError as e:
        raise HTTPException(422, str(e))
    pdf = build_pdf(req.network, result, repo.validation_report(req.network))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="flowmatrix-report.pdf"'})


# ---------------------------------------------------------------- map-based creation

def _map_call(fn, *args):
    try:
        return fn(*args)
    except osm_graph.MapError as e:
        raise HTTPException(422, str(e))
    except osm.ServiceError as e:
        raise HTTPException(502, str(e))


@router.get("/geocode")
def geocode(q: str = Query(max_length=200), lat: float | None = None, lng: float | None = None):
    near = (lat, lng) if lat is not None and lng is not None else None
    return _map_call(osm.search_places, q, near)


@router.get("/geocode/reverse")
def reverse(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180)):
    return _map_call(osm.reverse_place, lat, lng)


@router.post("/map/network")
def map_network(req: MapNetworkRequest):
    """Real road network between two places. Returns an UNSAVED draft in the common graph model."""
    return _map_call(osm.generate_network, req.start.model_dump(), req.end.model_dump(), req.detail,
                     req.radius_m, req.prune_stubs, req.trip_flow)
