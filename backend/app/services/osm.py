"""
Clients for the public OpenStreetMap-based services, used politely:
identifying User-Agent, minimum spacing between calls, caching.

* Photon  (geocoding / autocomplete). The public Nominatim server forbids autocomplete, so it is not used.
* OSRM    (reference driving route that defines the corridor).
* Overpass (the actual road data), with several mirrors.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

import httpx

from .osm_graph import MapError, build_graph, classes_for, haversine

USER_AGENT = os.getenv(
    "OSM_USER_AGENT",
    "FlowMatrix/1.0 (university traffic-analysis project; https://github.com/YashviShah514/traffic-flow-network-analyzer)")
PHOTON_URL = os.getenv("PHOTON_URL", "https://photon.komoot.io")
OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")
OVERPASS_URLS = [u.strip() for u in os.getenv(
    "OVERPASS_URLS",
    "https://overpass-api.de/api/interpreter,https://lz4.overpass-api.de/api/interpreter,"
    "https://z.overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter,"
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter").split(",") if u.strip()]
CACHE_DIR = Path(os.getenv("OSM_CACHE_DIR", Path(__file__).resolve().parents[2] / ".osm_cache"))
CACHE_TTL = 7 * 24 * 3600
MAX_DISTANCE_M = float(os.getenv("MAP_MAX_DISTANCE_M", "6000"))


class ServiceError(RuntimeError):
    """An upstream map service failed; the message is safe to show."""


class _Throttle:
    def __init__(self, interval: float):
        self.interval, self.last, self.lock = interval, 0.0, threading.Lock()

    def wait(self):
        with self.lock:
            delay = self.last + self.interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()


_throttle = {"photon": _Throttle(0.35), "osrm": _Throttle(1.0), "overpass": _Throttle(2.0)}
_memory: dict[str, tuple[float, object]] = {}


def _cache_get(key: str, disk: bool = False):
    hit = _memory.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    if disk:
        path = CACHE_DIR / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        try:
            if time.time() - path.stat().st_mtime < CACHE_TTL:
                value = json.loads(path.read_text(encoding="utf-8"))
                _memory[key] = (time.time(), value)
                return value
        except (OSError, ValueError):
            pass
    return None


def _cache_put(key: str, value, disk: bool = False):
    if len(_memory) > 500:
        _memory.clear()
    _memory[key] = (time.time(), value)
    if disk:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / (hashlib.sha256(key.encode()).hexdigest() + ".json")).write_text(json.dumps(value), encoding="utf-8")
        except OSError:
            pass


def _get_json(service: str, url: str, params: dict | None = None, timeout: float = 15):
    _throttle[service].wait()
    try:
        r = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except httpx.HTTPError as e:
        raise ServiceError(f"The {service} map service did not respond ({type(e).__name__}). Please retry.")
    if r.status_code == 429:
        raise ServiceError(f"The {service} map service is rate-limiting requests. Wait a minute and retry.")
    if r.status_code != 200:
        raise ServiceError(f"The {service} map service returned HTTP {r.status_code}. Please retry.")
    return r.json()


def _place(feature: dict) -> dict:
    p = feature.get("properties", {})
    lng, lat = feature["geometry"]["coordinates"][:2]
    primary = p.get("name") or " ".join(x for x in (p.get("housenumber"), p.get("street")) if x) or p.get("city") or "Location"
    rest = [p.get(k) for k in ("street", "locality", "district", "city", "state", "country")]
    secondary = ", ".join(dict.fromkeys(x for x in rest if x and x != primary))
    return {"label": primary, "detail": secondary, "lat": lat, "lng": lng}


def search_places(query: str, near: tuple[float, float] | None = None) -> list[dict]:
    query = " ".join(query.split())
    if len(query) < 3:
        return []
    params = {"q": query, "limit": 6, "lang": "en"}
    if near:
        params.update(lat=round(near[0], 3), lon=round(near[1], 3))
    key = "photon:" + json.dumps(params, sort_keys=True).lower()
    cached = _cache_get(key)
    if cached is not None:
        return cached
    data = _get_json("photon", f"{PHOTON_URL}/api/", params)
    places = [_place(f) for f in data.get("features", [])]
    _cache_put(key, places)
    return places


def reverse_place(lat: float, lng: float) -> dict:
    key = f"reverse:{lat:.5f},{lng:.5f}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    data = _get_json("photon", f"{PHOTON_URL}/reverse", {"lat": lat, "lon": lng, "lang": "en"})
    feats = data.get("features", [])
    place = _place(feats[0]) if feats else {"label": "Dropped pin", "detail": ""}
    place.update(lat=lat, lng=lng)
    _cache_put(key, place)
    return place


def fetch_route(pickup, destination) -> dict | None:
    """Driving route between the places; None if the router is unavailable or finds no route."""
    key = f"osrm:{pickup[0]:.5f},{pickup[1]:.5f};{destination[0]:.5f},{destination[1]:.5f}"
    cached = _cache_get(key, disk=True)
    if cached is not None:
        return cached
    url = f"{OSRM_URL}/route/v1/driving/{pickup[1]},{pickup[0]};{destination[1]},{destination[0]}"
    try:
        data = _get_json("osrm", url, {"overview": "full", "geometries": "geojson"})
    except ServiceError:
        return None
    if data.get("code") != "Ok" or not data.get("routes"):
        return None
    best = data["routes"][0]
    route = {"points": [[lat, lng] for lng, lat in best["geometry"]["coordinates"]], "distance_m": best["distance"]}
    _cache_put(key, route, disk=True)
    return route


def _thin(points: list, spacing: float = 120, limit: int = 60) -> list:
    """Fewer points for the Overpass query (the corridor stays the same within a few metres)."""
    out = [points[0]]
    for p in points[1:-1]:
        if haversine(tuple(out[-1]), tuple(p)) >= spacing:
            out.append(p)
    out.append(points[-1])
    if len(out) > limit:
        step = (len(out) - 1) / (limit - 1)
        out = [out[round(i * step)] for i in range(limit)]
    return out


def overpass_query(route_points: list, detail: str, radius_m: float) -> str:
    line = ",".join(f"{lat:.5f},{lng:.5f}" for lat, lng in _thin(route_points))
    pattern = "|".join(classes_for(detail))
    return (f'[out:json][timeout:40];way(around:{int(radius_m)},{line})["highway"~"^({pattern})$"];'
            "(._;>;);out body qt;")


def fetch_roads(route_points: list, detail: str, radius_m: float) -> list[dict]:
    query = overpass_query(route_points, detail, radius_m)
    key = "overpass:" + query
    cached = _cache_get(key, disk=True)
    if cached is not None:
        return cached
    problems = []
    for url in OVERPASS_URLS:
        _throttle["overpass"].wait()
        try:
            r = httpx.post(url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=60)
            if r.status_code == 200:
                data = r.json()
                if data.get("remark") and not data.get("elements"):
                    problems.append("server timeout")
                    continue
                _cache_put(key, data.get("elements", []), disk=True)
                return data.get("elements", [])
            problems.append(f"HTTP {r.status_code}")
        except (httpx.HTTPError, ValueError) as e:
            problems.append(type(e).__name__)
    raise ServiceError("OpenStreetMap road data could not be downloaded: every Overpass server failed "
                       f"({', '.join(problems)}). These public servers are sometimes overloaded - retry in a minute, "
                       "or create the network manually.")


def generate_network(pickup: dict, destination: dict, detail: str = "main", radius_m: float = 150,
                     prune_stubs: bool = True, trip_flow: float = 0) -> dict:
    """pickup/destination: {lat, lng, label}. Returns a network draft plus statistics."""
    a, b = (pickup["lat"], pickup["lng"]), (destination["lat"], destination["lng"])
    straight = haversine(a, b)
    if straight < 80:
        raise MapError("Pickup and destination are less than 80 m apart. Choose places further apart.")
    if straight > MAX_DISTANCE_M:
        raise MapError(f"The places are {straight / 1000:.1f} km apart; the limit is {MAX_DISTANCE_M / 1000:g} km so that "
                       "the equation system stays readable. Choose closer places.")
    route = fetch_route(a, b)
    if route is None:
        raise MapError("No driving route was found between these places (or the routing service is unavailable). "
                       "Retry, pick places on a road, or create the network manually.")
    points = route["points"]
    notes = []
    elements = fetch_roads(points, detail, radius_m)
    try:
        graph = build_graph(elements, points, a, b, detail, radius_m, prune_stubs, trip_flow)
        needs_all = detail == "main" and not graph["stats"]["destination_reachable"]
    except MapError:
        if detail != "main":
            raise
        needs_all, graph = True, None
    if needs_all:
        try:
            wider = build_graph(fetch_roads(points, "all", radius_m), points, a, b, "all", radius_m, prune_stubs, trip_flow)
            graph, detail = wider, "all"
            notes.append("Main roads alone did not connect the places, so local streets were included.")
        except (MapError, ServiceError):
            if graph is None:
                raise
    name = f"{pickup.get('label') or 'Pickup'} → {destination.get('label') or 'Destination'}"[:160]
    return {
        "network": {
            "name": name, "description": "Generated from OpenStreetMap road data.", "method": "map",
            "junctions": graph["junctions"], "roads": graph["roads"],
            "map_meta": {"pickup": pickup, "destination": destination, "route": points,
                         "route_distance_m": round(route["distance_m"], 1), "detail": detail, "radius_m": radius_m,
                         "trip_flow": trip_flow, "attribution": "© OpenStreetMap contributors"},
        },
        "stats": graph["stats"],
        "warnings": notes + graph["warnings"],
    }
