"""
Chooses the destination hospital for an ambulance based on:
  1. Emergency severity (primary / secondary / tertiary requirement)
  2. Shortest TRAVEL TIME among hospitals that qualify for that severity

Rules (as specified):
  - "primary" emergency  -> search ALL hospital types, pick nearest by time
  - "secondary" emergency -> ignore primary, search secondary + tertiary, pick nearest by time
  - "tertiary" emergency  -> search ONLY tertiary, pick nearest by time
"""

import json
import asyncio
from pathlib import Path
from routing import get_route, RoutingError

DATA_PATH = Path(__file__).parent / "data" / "hospitals.json"

SEVERITY_ALLOWED_TYPES = {
    "primary": {"primary", "secondary", "tertiary"},
    "secondary": {"secondary", "tertiary"},
    "tertiary": {"tertiary"},
}

_hospitals_cache = None


def load_hospitals():
    global _hospitals_cache
    if _hospitals_cache is None:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            _hospitals_cache = json.load(f)
    return _hospitals_cache


def _haversine_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


async def find_nearest_hospital(source: tuple[float, float], severity: str, specialty: str | None = None, candidate_limit: int = 6):
    """
    Two-stage selection to avoid hitting OSRM once per hospital in the whole city:
      1. Filter hospitals by allowed type for this severity.
      2. If a specialty is given (and isn't "general"), narrow to hospitals tagged
         with that specialty - if none exist nearby, silently fall back to the
         full severity-filtered pool rather than failing the request.
      3. Take the `candidate_limit` closest by straight-line distance.
      4. Call OSRM for real travel time on just those candidates.
      5. Return the one with the lowest actual travel time.
    """
    severity = severity.lower()
    if severity not in SEVERITY_ALLOWED_TYPES:
        raise ValueError(f"Unknown severity '{severity}'. Must be one of {list(SEVERITY_ALLOWED_TYPES)}")

    allowed_types = SEVERITY_ALLOWED_TYPES[severity]
    hospitals = load_hospitals()

    candidates = [h for h in hospitals if h.get("type") in allowed_types]
    if not candidates:
        raise RoutingError(f"No hospitals of type {allowed_types} available in dataset")

    if specialty and specialty != "general":
        specialty_candidates = [h for h in candidates if specialty in h.get("specialties", [])]
        if specialty_candidates:
            candidates = specialty_candidates
        # else: no hospital of that specialty within the severity-allowed types -
        # fall back to the full pool below rather than erroring out.

    candidates.sort(key=lambda h: _haversine_km(source[0], source[1], h["lat"], h["lon"]))
    shortlist = candidates[:candidate_limit]

    async def evaluate(hospital):
        try:
            route = await get_route(source, (hospital["lat"], hospital["lon"]))
            return {**hospital, "eta_seconds": route["duration_seconds"], "route": route}
        except RoutingError:
            return None

    results = await asyncio.gather(*(evaluate(h) for h in shortlist))
    valid_results = [r for r in results if r is not None]

    if not valid_results:
        raise RoutingError("Could not route to any candidate hospital")

    best = min(valid_results, key=lambda r: r["eta_seconds"])
    return best
