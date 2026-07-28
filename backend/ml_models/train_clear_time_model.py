import pandas as pd
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib

BASE = Path(__file__).parent

def main():
    df = pd.read_csv(BASE / "clear_time_training_data.csv")

    X = df[["vehicle_count", "lane_count", "time_of_day_factor"]]
    y = df["clear_time_seconds"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = GradientBoostingRegressor(n_estimators=150, max_depth=4, learning_rate=0.08, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    print(f"Clear-time model MAE: {mae:.2f} seconds")

    joblib.dump(model, BASE / "models" / "clear_time_model.pkl")
    print("Saved models/clear_time_model.pkl")

if __name__ == "__main__":
    main()
