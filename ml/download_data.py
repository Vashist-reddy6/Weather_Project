import httpx
import pandas as pd
import asyncio
from datetime import date, timedelta
import os

CITIES = [
    {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"name": "London", "lat": 51.5074, "lon": -0.1278},
    {"name": "Miami", "lat": 25.7617, "lon": -80.1918},
    {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456},
    {"name": "Manila", "lat": 14.5995, "lon": 120.9842},
    {"name": "Houston", "lat": 29.7604, "lon": -95.3698},
    
]

# Fetch last 3 years of data
END_DATE = date.today() - timedelta(days=10) # 10 days lag to ensure data is available
START_DATE = END_DATE - timedelta(days=365*3)

API_URL = "https://archive-api.open-meteo.com/v1/archive"

async def fetch_city_data(client, city):
    print(f"Fetching data for {city['name']} ({START_DATE} to {END_DATE})...")
    params = {
        "latitude": city["lat"],
        "longitude": city["lon"],
        "start_date": START_DATE.strftime("%Y-%m-%d"),
        "end_date": END_DATE.strftime("%Y-%m-%d"),
        "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,cloud_cover,rain",
        "timezone": "auto"
    }
    response = await client.get(API_URL, params=params, timeout=60.0)
    response.raise_for_status()
    data = response.json()
    
    hourly = data["hourly"]
    df = pd.DataFrame({
        "temperature": hourly["temperature_2m"],
        "humidity": hourly["relative_humidity_2m"],
        "pressure": hourly["surface_pressure"],
        "wind_speed": hourly["wind_speed_10m"], # Open-meteo provides km/h by default
        "cloud_cover": hourly["cloud_cover"],
        "rainfall_1h": hourly["rain"]
    })
    
    # Convert wind speed from km/h to m/s
    df["wind_speed"] = df["wind_speed"] * (1000 / 3600)
    
    # Drop rows with NaN
    df = df.dropna()
    return df

def compute_risk_label(row):
    """
    Compute a realistic risk label based on extreme weather logic.
    0 = LOW, 1 = MODERATE, 2 = HIGH, 3 = CRITICAL
    """
    score = 0.0
    rain = row["rainfall_1h"]
    wind = row["wind_speed"]
    pressure = row["pressure"]
    
    # Rainfall thresholds (mm/h)
    if rain > 50: score += 4.0
    elif rain > 20: score += 2.0
    elif rain > 10: score += 1.0
    elif rain > 5: score += 0.5
    
    # Wind thresholds (m/s)
    if wind > 30: score += 4.0
    elif wind > 20: score += 2.0
    elif wind > 15: score += 1.0
    elif wind > 10: score += 0.5
    
    # Pressure drop (hPa) - typical indicator of severe storms/cyclones
    if pressure < 980: score += 2.0
    elif pressure < 995: score += 1.0
    
    if score >= 4.0: return 3 # CRITICAL
    elif score >= 2.0: return 2 # HIGH
    elif score >= 1.0: return 1 # MODERATE
    else: return 0 # LOW

async def main():
    all_dfs = []
    async with httpx.AsyncClient() as client:
        for city in CITIES:
            try:
                df = await fetch_city_data(client, city)
                all_dfs.append(df)
            except Exception as e:
                print(f"Failed to fetch data for {city['name']}: {e}")
                
    if not all_dfs:
        print("No data fetched.")
        return
        
    combined_df = pd.concat(all_dfs, ignore_index=True)
    print(f"\nSuccessfully downloaded {len(combined_df)} hourly records.")
    
    print("\nComputing risk labels based on historical meteorological extremes...")
    combined_df["risk_label"] = combined_df.apply(compute_risk_label, axis=1)
    
    print("\nInitial distribution (highly imbalanced):")
    print(combined_df["risk_label"].value_counts())
    
    # Extreme weather is rare! We need to balance the dataset so the ML model 
    # doesn't just predict "LOW" every time. We will undersample the majority class
    # and keep all instances of the minority classes.
    balanced_dfs = []
    for label in [0, 1, 2, 3]:
        class_df = combined_df[combined_df["risk_label"] == label]
        if len(class_df) > 10000:
            # Undersample common weather
            class_df = class_df.sample(10000, random_state=42)
        balanced_dfs.append(class_df)
        
    final_df = pd.concat(balanced_dfs, ignore_index=True)
    
    print("\nBalanced distribution for training:")
    print(final_df["risk_label"].value_counts())
    
    out_path = os.path.join(os.path.dirname(__file__), "real_weather_data.csv")
    final_df.to_csv(out_path, index=False)
    print(f"\nSaved {len(final_df)} balanced historical data points to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
