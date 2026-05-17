import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

def assign_risk(row):
    score = 0
    # Rainfall is the strongest signal for floods
    if row['rainfall_1h'] >= 30:   score += 4
    elif row['rainfall_1h'] >= 15: score += 3
    elif row['rainfall_1h'] >= 7:  score += 2
    elif row['rainfall_1h'] >= 2:  score += 1
    
    # Humidity amplifies flood risk
    if row['humidity'] >= 95:      score += 2
    elif row['humidity'] >= 85:    score += 1
    
    # Wind speed matters for cyclones (now in m/s to match OpenWeatherMap metric)
    # 90 km/h = 25 m/s, 62 km/h = 17.2 m/s, 40 km/h = 11.1 m/s, 20 km/h = 5.5 m/s
    if row['wind_speed'] >= 25.0:  score += 4
    elif row['wind_speed'] >= 17.2:score += 3
    elif row['wind_speed'] >= 11.1:score += 2
    elif row['wind_speed'] >= 5.5: score += 1
    
    # Pressure drop is a cyclone precursor
    if row['pressure'] <= 970:     score += 3
    elif row['pressure'] <= 990:   score += 2
    elif row['pressure'] <= 1000:  score += 1
    
    # Heatwave: high temp + low humidity
    if row['temperature'] >= 45:   score += 4
    elif row['temperature'] >= 40 and row['humidity'] < 30: score += 3
    elif row['temperature'] >= 38: score += 1

    if score >= 8:   return 3  # CRITICAL
    elif score >= 5: return 2  # HIGH
    elif score >= 2: return 1  # MODERATE
    else:            return 0  # LOW

def train_unified():
    weather_csv_path = os.path.join(os.path.dirname(__file__), "real_weather_data.csv")
    output_path = os.path.join(os.path.dirname(__file__), "disaster_model.pkl")
    
    print("Loading Real Weather Data...")
    if not os.path.exists(weather_csv_path):
        print(f"Error: {weather_csv_path} not found.")
        return
        
    df = pd.read_csv(weather_csv_path)
    
    print("Relabeling data based on physical disaster thresholds (m/s for wind)...")
    df['risk_label'] = df.apply(assign_risk, axis=1)
    
    print("Injecting physically grounded synthetic CRITICAL cases (Step 3)...")
    # Cyclone synthetic data - wind_speed in m/s (25 to 50 m/s = 90 to 180 km/h)
    cyclone_samples = pd.DataFrame({
        'temperature': np.random.uniform(28, 35, 200),
        'humidity': np.random.uniform(90, 100, 200),
        'pressure': np.random.uniform(940, 975, 200),
        'wind_speed': np.random.uniform(25.0, 50.0, 200),
        'cloud_cover': np.random.uniform(85, 100, 200),
        'rainfall_1h': np.random.uniform(25, 60, 200),
        'risk_label': 3
    })

    # Heatwave synthetic data - wind_speed in m/s (1.4 to 7 m/s = 5 to 25 km/h)
    heatwave_samples = pd.DataFrame({
        'temperature': np.random.uniform(44, 50, 200),
        'humidity': np.random.uniform(10, 30, 200),
        'pressure': np.random.uniform(995, 1010, 200),
        'wind_speed': np.random.uniform(1.4, 7.0, 200),
        'cloud_cover': np.random.uniform(0, 20, 200),
        'rainfall_1h': np.zeros(200),
        'risk_label': 3
    })
    
    if 'cloud_cover' not in df.columns:
        df['cloud_cover'] = np.random.uniform(20, 80, len(df))
        
    df = pd.concat([df, cyclone_samples, heatwave_samples], ignore_index=True)
    
    print("\nDataset Distribution After Relabeling & Injection:")
    print(df["risk_label"].value_counts())
    
    features = ["temperature", "humidity", "pressure", "wind_speed", "cloud_cover", "rainfall_1h"]
    X = df[features]
    y = df["risk_label"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("\nCalculating sample weights to balance the classes...")
    sample_weights = compute_sample_weight(class_weight='balanced', y=y_train)
    
    print("\nTraining XGBoost Classifier...")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42
    )
    model.fit(X_train, y_train, sample_weight=sample_weights)
    
    joblib.dump(model, output_path)
    print(f"\nModel saved to: {output_path}")

if __name__ == "__main__":
    train_unified()
