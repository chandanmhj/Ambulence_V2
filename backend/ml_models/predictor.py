"""
Loads the two trained models and exposes simple predict functions.
Falls back to the physics/queueing formulas directly if the .pkl files
haven't been trained yet (e.g. running outside Docker for a quick test).
"""

from pathlib import Path
import joblib

MODELS_DIR = Path(__file__).parent / "models"

_eat_model = None
_clear_model = None

# The EAT model was trained on distances of 50-3000m (see
# ml_models/generate_synthetic_data.py). Gradient-boosted trees don't
# extrapolate sensibly past their training range - predictions for a junction
# many kilometers away would just plateau near whatever the nearest training
# leaf predicts, not scale up correctly. Past this distance we use the plain
# physics fallback instead, which is actually more reliable at that scale.
EAT_MODEL_MAX_DISTANCE_M = 3000


def _load():
    global _eat_model, _clear_model
    if _eat_model is None:
        eat_path = MODELS_DIR / "eat_model.pkl"
        _eat_model = joblib.load(eat_path) if eat_path.exists() else None
    if _clear_model is None:
        clear_path = MODELS_DIR / "clear_time_model.pkl"
        _clear_model = joblib.load(clear_path) if clear_path.exists() else None


def _physics_eat(distance_m: float, base_speed_kmh: float, road_type: int) -> float:
    speed_factor = 1.15 if road_type == 1 else 0.85
    speed_ms = (base_speed_kmh * speed_factor) * 1000 / 3600
    return distance_m / max(speed_ms, 0.1)


def predict_eat(distance_m: float, base_speed_kmh: float, road_type: int) -> float:
    _load()
    if _eat_model is not None and distance_m <= EAT_MODEL_MAX_DISTANCE_M:
        pred = _eat_model.predict([[distance_m, base_speed_kmh, road_type]])
        return max(float(pred[0]), 0.5)
    # Out of the model's trained range (or model not trained yet) - use physics directly.
    return _physics_eat(distance_m, base_speed_kmh, road_type)


def predict_clear_time(vehicle_count: int, lane_count: int, time_of_day_factor: float = 1.0) -> float:
    _load()
    if _clear_model is not None:
        pred = _clear_model.predict([[vehicle_count, lane_count, time_of_day_factor]])
        return max(float(pred[0]), 0.5)
    # fallback: queueing formula
    effective_lanes = max(1, min(lane_count, 3))
    return 3.0 + (vehicle_count / effective_lanes) * 2.2 * time_of_day_factor