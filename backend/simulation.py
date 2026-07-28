"""
Drives the "simulate" mode: moves a virtual ambulance along a precomputed OSRM route,
generates realistic-looking vehicle counts at each upcoming junction (standing in for
a real VAC - Vehicle Actuated Controller - sensor feed), and decides exactly when each
junction should flip to green so it clears just before the ambulance arrives.

This module is transport-agnostic - `run_simulation` is an async generator that yields
state dicts; main.py wires it to a WebSocket.
"""

import asyncio
import random
from math import radians, sin, cos, sqrt, atan2

from ml_models.predictor import predict_eat, predict_clear_time

TICK_SECONDS = 0.5          # simulation update interval
SAFETY_BUFFER_S = 10        # queue must finish clearing this many seconds BEFORE the ambulance arrives, not exactly at arrival


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _interpolate_path(geometry, speed_mps, tick_seconds):
    """
    Walks the polyline at a constant speed and yields (lat, lon, distance_covered_m)
    at each tick. Speed has small realistic variance layered on (potholes etc).
    """
    points = []
    dist_covered = 0.0
    idx = 0
    pos = geometry[0][:]

    while idx < len(geometry) - 1:
        seg_start = geometry[idx]
        seg_end = geometry[idx + 1]
        seg_len = _haversine_m(seg_start[0], seg_start[1], seg_end[0], seg_end[1])

        if seg_len == 0:
            idx += 1
            continue

        # jittered speed: simulate potholes / minor slowdowns
        jitter = random.uniform(0.85, 1.05)
        step_m = speed_mps * jitter * tick_seconds

        remaining_in_seg = seg_len - dist_covered
        if step_m < remaining_in_seg:
            dist_covered += step_m
            frac = dist_covered / seg_len
            lat = seg_start[0] + (seg_end[0] - seg_start[0]) * frac
            lon = seg_start[1] + (seg_end[1] - seg_start[1]) * frac
            points.append((lat, lon))
        else:
            idx += 1
            dist_covered = 0.0
            if idx < len(geometry):
                points.append(tuple(geometry[idx]))

    return points


def _cumulative_distances(geometry):
    """Cumulative distance (metres) from the start of the route to each point."""
    cum = [0.0]
    for i in range(1, len(geometry)):
        cum.append(cum[-1] + _haversine_m(geometry[i - 1][0], geometry[i - 1][1], geometry[i][0], geometry[i][1]))
    return cum


def _nearest_index(geometry, lat, lon):
    best_i, best_d = 0, float("inf")
    for i, p in enumerate(geometry):
        d = _haversine_m(p[0], p[1], lat, lon)
        if d < best_d:
            best_d, best_i = d, i
    return best_i


class JunctionState:
    def __init__(self, lat, lon, index, route_distance_m):
        self.lat = lat
        self.lon = lon
        self.index = index
        # Distance from the START of the route to this junction, measured ALONG
        # the road (not straight-line) - see run_simulation for why this matters.
        self.route_distance_m = route_distance_m
        self.vehicle_count = random.randint(0, 40)   # simulated VAC sensor reading
        self.lane_count = random.randint(1, 3)
        self.signal_color = "red"                     # default: standing traffic
        self.cleared = False
        self.clear_time_s = predict_clear_time(self.vehicle_count, self.lane_count)
        self.eat_seconds = None

    def as_dict(self):
        if self.signal_color == "green":
            signal_opens_in = 0.0
        elif self.eat_seconds is not None:
            signal_opens_in = max(self.eat_seconds - (self.clear_time_s + SAFETY_BUFFER_S), 0.0)
        else:
            signal_opens_in = None

        return {
            "lat": self.lat,
            "lon": self.lon,
            "index": self.index,
            "vehicle_count": self.vehicle_count,
            "lane_count": self.lane_count,
            "signal_color": self.signal_color,
            "clear_time_s": round(self.clear_time_s, 1),
            "eat_seconds": round(self.eat_seconds, 1) if self.eat_seconds is not None else None,
            "signal_opens_in_s": round(signal_opens_in, 1) if signal_opens_in is not None else None,
        }


async def run_simulation(geometry, junctions, ambulance_base_speed_kmh=45):
    """
    Async generator yielding state dicts for streaming over a WebSocket:
    {
        "ambulance": {"lat":..., "lon":...},
        "junctions": [ {...}, ... ],
        "distance_remaining_m": ...,
        "elapsed_s": ...
    }
    """
    speed_mps = ambulance_base_speed_kmh * 1000 / 3600
    path_points = _interpolate_path(geometry, speed_mps, TICK_SECONDS)

    # Precompute how far along the ROUTE each junction sits (not straight-line
    # distance from wherever the ambulance currently is). This matters a lot on
    # a real winding city route: a junction can be geometrically close in a
    # straight line (the road loops back near itself) while still being a
    # full route-minute away by road. Using straight-line distance here was
    # the bug behind "0.2s to next junction" when it was actually ~1 minute out.
    cum_dist = _cumulative_distances(geometry)
    junction_states = []
    for i, j in enumerate(junctions):
        idx = _nearest_index(geometry, j[0], j[1])
        junction_states.append(JunctionState(j[0], j[1], i, route_distance_m=cum_dist[idx]))

    total_m = cum_dist[-1]

    elapsed = 0.0
    covered_m = 0.0

    for i, (lat, lon) in enumerate(path_points):
        if i > 0:
            covered_m += _haversine_m(path_points[i - 1][0], path_points[i - 1][1], lat, lon)
        elapsed += TICK_SECONDS
        avg_speed_kmh = (covered_m / elapsed * 3.6) if elapsed > 0 else 0.0

        for js in junction_states:
            if js.cleared:
                continue
            # Distance-along-route remaining to this junction, not straight-line.
            dist_to_junction = max(js.route_distance_m - covered_m, 0)

            eat = predict_eat(dist_to_junction, ambulance_base_speed_kmh, road_type=1)
            js.eat_seconds = eat

            # Turn green with a safety buffer: the queue must finish clearing
            # SAFETY_BUFFER_S seconds before the ambulance actually arrives, not
            # exactly when it arrives - so trigger as soon as arrival time is within
            # (clear time + buffer), not just (clear time).
            if eat <= js.clear_time_s + SAFETY_BUFFER_S and js.signal_color != "green":
                js.signal_color = "green"
            if eat <= 1.0:
                js.cleared = True
                js.signal_color = "green"

        yield {
            "ambulance": {"lat": lat, "lon": lon},
            "junctions": [js.as_dict() for js in junction_states],
            "distance_remaining_m": round(max(total_m - covered_m, 0), 1),
            "elapsed_s": round(elapsed, 1),
            "avg_speed_kmh": round(avg_speed_kmh, 1),
        }

        await asyncio.sleep(TICK_SECONDS)

    yield {
        "ambulance": {"lat": geometry[-1][0], "lon": geometry[-1][1]},
        "junctions": [js.as_dict() for js in junction_states],
        "distance_remaining_m": 0,
        "elapsed_s": round(elapsed, 1),
        "avg_speed_kmh": round(avg_speed_kmh, 1),
        "arrived": True,
    }