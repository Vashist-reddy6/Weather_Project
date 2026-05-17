import sqlite3
import json
import random
from datetime import datetime

DB_PATH = "c:/Hack-Weatherproj/backend/disaster_alerts.db"

def inject_extreme_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # We will inject 1000 extreme/high weather events so the retrainer learns them
    for i in range(500):
        # CRITICAL
        weather = {
            "temperature": random.uniform(25.0, 38.0),
            "humidity": random.uniform(85, 100),
            "pressure": random.uniform(960, 990),
            "wind_speed": random.uniform(25, 45),
            "cloud_cover": random.uniform(90, 100),
            "rainfall_1h": random.uniform(50, 150)
        }
        cursor.execute(
            "INSERT INTO predictions (latitude, longitude, location_name, risk_score, risk_level, weather_data, predicted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (19.0, 72.0, "Synthetic Critical", 0.95, "CRITICAL", json.dumps(weather), datetime.now().isoformat())
        )
        
        # HIGH
        weather_high = {
            "temperature": random.uniform(20.0, 35.0),
            "humidity": random.uniform(75, 95),
            "pressure": random.uniform(980, 1000),
            "wind_speed": random.uniform(15, 25),
            "cloud_cover": random.uniform(80, 100),
            "rainfall_1h": random.uniform(20, 50)
        }
        cursor.execute(
            "INSERT INTO predictions (latitude, longitude, location_name, risk_score, risk_level, weather_data, predicted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (19.0, 72.0, "Synthetic High", 0.65, "HIGH", json.dumps(weather_high), datetime.now().isoformat())
        )
        
        # MODERATE
        weather_mod = {
            "temperature": random.uniform(15.0, 40.0),
            "humidity": random.uniform(60, 85),
            "pressure": random.uniform(1000, 1010),
            "wind_speed": random.uniform(10, 15),
            "cloud_cover": random.uniform(50, 80),
            "rainfall_1h": random.uniform(5, 20)
        }
        cursor.execute(
            "INSERT INTO predictions (latitude, longitude, location_name, risk_score, risk_level, weather_data, predicted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (19.0, 72.0, "Synthetic Mod", 0.35, "MODERATE", json.dumps(weather_mod), datetime.now().isoformat())
        )

    conn.commit()
    conn.close()
    print("Injected 1500 varied events into the database.")

if __name__ == "__main__":
    inject_extreme_data()
