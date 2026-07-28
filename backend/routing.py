"""
Thin client around a self-hosted OSRM instance.

OSRM gives us real-road shortest-TIME routing (not shortest distance) for free
once the Bangalore extract is preprocessed with `osrm-contract` / `osrm-partition`.
See README.md for the one-time setup.
"""

import os
import asyncio
import httpx

OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")

# OSRM can take a while to load a large extract into memory after container
# startup. 20 attempts x 3s = up to 60s of tolerance before we give up - enough
# to ride out a slow load on the southern-zone-sized extract without needing
# manual retries after `docker compose up`.
MAX_RETRIES = 20
RETRY_DELAY_SECONDS = 3.0


class RoutingError(Exception):
    pass


async def _request_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """
    Retries on connection errors only (OSRM not ready yet). Does NOT retry on
    4xx/5xx HTTP responses - those are real errors, not timing issues.
    """
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await client.get(url)
        except httpx.ConnectError as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise RoutingError(
        f"Could not reach OSRM at {OSRM_URL} after {MAX_RETRIES} attempts "
        f"({MAX_RETRIES * RETRY_DELAY_SECONDS:.0f}s). Check `docker compose logs osrm` "
        f"for the 'running and waiting for requests' line."
    ) from last_exc


async def get_route(source: tuple[float, float], destination: tuple[float, float]) -> dict:
    """
    source / destination are (lat, lon) tuples.
    Returns: {
        "duration_seconds": float,
        "distance_meters": float,
        "geometry": [[lat, lon], ...],   # polyline points for the map
        "junctions": [[lat, lon], ...],  # intermediate waypoints used as "junction" proxies
    }
    """
    src_lon, src_lat = source[1], source[0]
    dst_lon, dst_lat = destination[1], destination[0]

    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{src_lon},{src_lat};{dst_lon},{dst_lat}"
        f"?overview=full&geometries=geojson&steps=true"
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await _request_with_retry(client, url)

    if resp.status_code != 200:
        raise RoutingError(f"OSRM returned {resp.status_code}: {resp.text}")

    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(f"OSRM could not find a route: {data.get('message', 'unknown error')}")

    route = data["routes"][0]
    coords = route["geometry"]["coordinates"]  # [[lon, lat], ...]
    geometry = [[lat, lon] for lon, lat in coords]

    # Treat each maneuver/step endpoint as a "junction" the ambulance will pass.
    # This is a reasonable proxy for real traffic-signal junctions without needing
    # a separate junction dataset.
    junctions = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            loc = step.get("maneuver", {}).get("location")
            if loc:
                junctions.append([loc[1], loc[0]])  # -> lat, lon

    return {
        "duration_seconds": route["duration"],
        "distance_meters": route["distance"],
        "geometry": geometry,
        "junctions": junctions,
    }

