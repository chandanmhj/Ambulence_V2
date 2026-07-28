from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import random
import os
from pathlib import Path
from sqlalchemy.orm import Session

from routing import get_route, RoutingError
from hospital_selector import find_nearest_hospital, load_hospitals
from ml_models.predictor import predict_eat, predict_clear_time
from simulation import run_simulation
from emergency_classifier import classify_emergency_text
from db import get_db, init_db
from models import User
from auth_deps import get_current_user, get_current_user_ws
from auth_routes import router as auth_router

app = FastAPI(title="Bangalore Emergency Vehicle Routing System")


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(auth_router)

from dotenv import load_dotenv
load_dotenv()  # loads backend/.env locally if present; no-op in production where real env vars are set directly

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")

if os.environ.get("ENVIRONMENT", "development") == "production" and ALLOWED_ORIGINS == ["*"]:
    raise RuntimeError(
        "ALLOWED_ORIGINS is not set while ENVIRONMENT=production. Set it to your "
        "deployed frontend URL(s) (comma-separated if multiple) - refusing to start "
        "with CORS wide open to any origin."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # set ALLOWED_ORIGINS env var to your deployed frontend URL(s) in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Request/response models ----------

class Point(BaseModel):
    lat: float
    lon: float


class RouteRequest(BaseModel):
    source: Point
    destination: Point


class HospitalRequest(BaseModel):
    source: Point
    severity: str  # "primary" | "secondary" | "tertiary"
    emergency_text: str | None = None  # free-text description, e.g. "eye injury and blurry vision"


class JunctionEtaRequest(BaseModel):
    distance_m: float
    speed_kmh: float
    road_type: int = 1  # 0 = residential, 1 = arterial


class JunctionClearRequest(BaseModel):
    vehicle_count: int
    lane_count: int = 2
    time_of_day_factor: float = 1.0


# ---------- Basic routing (feature 1: shortest-time path between any 2 points) ----------

@app.post("/route")
async def route(req: RouteRequest, current_user: User = Depends(get_current_user)):
    try:
        result = await get_route((req.source.lat, req.source.lon), (req.destination.lat, req.destination.lon))
        return result
    except RoutingError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------- Hospital selection (feature 2: ambulance mode) ----------

@app.post("/nearest-hospital")
async def nearest_hospital(req: HospitalRequest, current_user: User = Depends(get_current_user)):
    matched_specialty = None
    specialty_confidence = None

    if req.emergency_text and req.emergency_text.strip():
        ranked = classify_emergency_text(req.emergency_text)
        matched_specialty, specialty_confidence = ranked[0]

    try:
        result = await find_nearest_hospital((req.source.lat, req.source.lon), req.severity, specialty=matched_specialty)
        result["matched_specialty"] = matched_specialty
        result["specialty_confidence"] = round(specialty_confidence, 3) if specialty_confidence is not None else None
        return result
    except (RoutingError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/classify-emergency")
def classify_emergency(text: str, current_user: User = Depends(get_current_user)):
    """Standalone endpoint if the frontend wants to preview the match before searching."""
    ranked = classify_emergency_text(text)
    return {"matches": [{"category": c, "confidence": round(s, 3)} for c, s in ranked]}


@app.get("/hospitals")
def list_hospitals(current_user: User = Depends(get_current_user)):
    return load_hospitals()


# ---------- Junction ML models, exposed individually for the "show calculations" panel ----------

@app.post("/junction-eta")
def junction_eta(req: JunctionEtaRequest, current_user: User = Depends(get_current_user)):
    eat = predict_eat(req.distance_m, req.speed_kmh, req.road_type)
    return {"eat_seconds": round(eat, 1)}


@app.post("/junction-clear-time")
def junction_clear_time(req: JunctionClearRequest, current_user: User = Depends(get_current_user)):
    clear_time = predict_clear_time(req.vehicle_count, req.lane_count, req.time_of_day_factor)
    return {"clear_time_seconds": round(clear_time, 1)}


# ---------- Simulation stream ----------

@app.websocket("/ws/simulate")
async def simulate_ws(websocket: WebSocket, token: str = Query(...)):
    """
    Client connects to ws://.../ws/simulate?token=<jwt> - browsers can't send
    custom Authorization headers during a WebSocket handshake, so the token
    travels as a query parameter instead.

    Client then sends: {"geometry": [[lat,lon],...], "junctions": [[lat,lon],...], "speed_kmh": 45}
    Server streams state dicts every tick until the ambulance arrives.
    """
    db = next(get_db())
    try:
        get_current_user_ws(token, db)
    except HTTPException:
        await websocket.close(code=4401)  # custom close code signaling auth failure
        return
    finally:
        db.close()

    await websocket.accept()
    try:
        init_msg = await websocket.receive_json()
        geometry = init_msg["geometry"]
        junctions = init_msg.get("junctions", [])
        speed_kmh = init_msg.get("speed_kmh", 45)

        async for state in run_simulation(geometry, junctions, speed_kmh):
            await websocket.send_json(state)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass


@app.get("/health")
def health():
    return {"status": "ok"}
