"""
Generates synthetic-but-physically-grounded training data for the two junction models:

Model 1 - EAT (Estimated Arrival Time to a junction):
    Ground truth derived from distance/speed physics, with realistic noise layered on
    to simulate potholes, minor braking, lane changes etc. The model learns to predict
    arrival time robustly under that noise, not the physics itself.

Model 2 - Junction clear time:
    Ground truth derived from a queueing-style discharge formula (vehicles/sec a junction
    can release once green), with noise for junction width, time-of-day density, and
    driver behaviour variance.

Both are saved as CSVs for training scripts to consume.
"""

import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path(__file__).parent
np.random.seed(42)

N_SAMPLES = 20000

# ---------- Model 1: EAT (arrival time to junction) ----------

def generate_eat_data(n=N_SAMPLES):
    distance_m = np.random.uniform(50, 3000, n)          # distance to junction
    base_speed_kmh = np.random.uniform(20, 60, n)         # ambulance cruising speed

    # Road type affects achievable speed: 0 = residential, 1 = arterial
    road_type = np.random.randint(0, 2, n)
    speed_factor = np.where(road_type == 1, 1.15, 0.85)
    effective_speed_kmh = base_speed_kmh * speed_factor

    # Noise: potholes / traffic friction / signals along the way shave off effective speed
    friction_noise = np.random.normal(1.0, 0.08, n)
    effective_speed_kmh = np.clip(effective_speed_kmh * friction_noise, 5, 80)

    effective_speed_ms = effective_speed_kmh * 1000 / 3600
    true_time_s = distance_m / effective_speed_ms

    # Measurement/reporting noise (GPS jitter, speed sensor lag)
    reported_time_s = true_time_s + np.random.normal(0, 1.5, n)
    reported_time_s = np.clip(reported_time_s, 1, None)

    df = pd.DataFrame({
        "distance_m": distance_m,
        "base_speed_kmh": base_speed_kmh,
        "road_type": road_type,
        "eat_seconds": reported_time_s,
    })
    return df


# ---------- Model 2: Junction clear time ----------

def generate_clear_time_data(n=N_SAMPLES):
    vehicle_count = np.random.randint(0, 60, n)
    lane_count = np.random.randint(1, 5, n)
    time_of_day_factor = np.random.uniform(0.8, 1.4, n)   # peak hour = higher friction

    # Discharge rate: ~2.2s per vehicle per lane at saturation, plus fixed startup delay
    startup_delay_s = np.random.uniform(2, 4, n)
    per_vehicle_s = 2.2 * time_of_day_factor
    effective_lanes = np.clip(lane_count, 1, 3)  # diminishing returns beyond 3 lanes

    true_clear_time = startup_delay_s + (vehicle_count / effective_lanes) * per_vehicle_s

    # Driver behaviour noise
    reported_clear_time = true_clear_time + np.random.normal(0, 1.0, n)
    reported_clear_time = np.clip(reported_clear_time, 1, None)

    df = pd.DataFrame({
        "vehicle_count": vehicle_count,
        "lane_count": lane_count,
        "time_of_day_factor": time_of_day_factor,
        "clear_time_seconds": reported_clear_time,
    })
    return df


if __name__ == "__main__":
    eat_df = generate_eat_data()
    eat_df.to_csv(OUT_DIR / "eat_training_data.csv", index=False)
    print(f"Saved {len(eat_df)} rows to eat_training_data.csv")

    clear_df = generate_clear_time_data()
    clear_df.to_csv(OUT_DIR / "clear_time_training_data.csv", index=False)
    print(f"Saved {len(clear_df)} rows to clear_time_training_data.csv")
