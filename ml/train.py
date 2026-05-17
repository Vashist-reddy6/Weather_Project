"""
ML Training Script - Disaster Risk Classifier
=============================================
Generates synthetic training data and trains an XGBoost classifier.
In production, replace synthetic data with real datasets:
  - Kaggle Flood Dataset
  - NOAA Storm Events Database
  - ECMWF ERA5 Reanalysis Data
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from xgboost import XGBClassifier
import joblib
import os

np.random.seed(42)
N_SAMPLES = 6000
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "disaster_model.pkl")


def generate_samples(n: int) -> pd.DataFrame:
    records = []

    # LOW risk samples (~50%)
    for _ in range(int(n * 0.50)):
        records.append({
            "temperature": np.random.uniform(15, 38),
            "humidity":    np.random.uniform(20, 65),
            "pressure":    np.random.uniform(1005, 1025),
            "wind_speed":  np.random.uniform(0, 8),
            "cloud_cover": np.random.uniform(0, 40),
            "rainfall_1h": np.random.uniform(0, 3),
            "risk_label":  0  # LOW
        })

    # MODERATE risk samples (~25%)
    for _ in range(int(n * 0.25)):
        records.append({
            "temperature": np.random.uniform(10, 32),
            "humidity":    np.random.uniform(60, 80),
            "pressure":    np.random.uniform(995, 1010),
            "wind_speed":  np.random.uniform(5, 15),
            "cloud_cover": np.random.uniform(30, 70),
            "rainfall_1h": np.random.uniform(3, 15),
            "risk_label":  1  # MODERATE
        })

    # HIGH risk samples (~15%)
    for _ in range(int(n * 0.15)):
        records.append({
            "temperature": np.random.uniform(5, 28),
            "humidity":    np.random.uniform(75, 92),
            "pressure":    np.random.uniform(985, 1000),
            "wind_speed":  np.random.uniform(12, 25),
            "cloud_cover": np.random.uniform(60, 90),
            "rainfall_1h": np.random.uniform(15, 50),
            "risk_label":  2  # HIGH
        })

    # CRITICAL risk samples (~10%)
    for _ in range(int(n * 0.10)):
        records.append({
            "temperature": np.random.uniform(0, 25),
            "humidity":    np.random.uniform(88, 100),
            "pressure":    np.random.uniform(960, 990),
            "wind_speed":  np.random.uniform(22, 50),
            "cloud_cover": np.random.uniform(80, 100),
            "rainfall_1h": np.random.uniform(40, 120),
            "risk_label":  3  # CRITICAL
        })

    return pd.DataFrame(records)


def train():
    data_path = os.path.join(os.path.dirname(__file__), "real_weather_data.csv")
    
    if os.path.exists(data_path):
        print(f"Loading REAL historical training data from {data_path}...")
        df = pd.read_csv(data_path)
    else:
        print("real_weather_data.csv not found. Generating synthetic training data...")
        df = generate_samples(N_SAMPLES)
        
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)  # shuffle

    features = ["temperature", "humidity", "pressure", "wind_speed", "cloud_cover", "rainfall_1h"]
    X = df[features]
    y = df["risk_label"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    print("Training XGBoost classifier...")
    model = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"\nAccuracy: {acc:.4f}")
    print("\nClassification Report:")
    
    unique_classes = sorted(list(set(y_test) | set(y_pred)))
    all_names = {0: "LOW", 1: "MODERATE", 2: "HIGH", 3: "CRITICAL"}
    target_names = [all_names[c] for c in unique_classes]
    
    print(classification_report(y_test, y_pred, target_names=target_names))

    joblib.dump(model, OUTPUT_PATH)
    print(f"\nModel saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    train()
