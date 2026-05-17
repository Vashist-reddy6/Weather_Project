"""
Anomaly Detection — flags when weather parameters deviate more than 2σ
from a rolling baseline built from NASA POWER historical data.
"""

import statistics
from services.nasa_power import get_historical_climate


async def detect_anomalies(current_weather: dict, lat: float, lon: float) -> list[dict]:
    """
    Compare current weather readings against a 30-day NASA POWER baseline.
    Returns a list of anomaly dicts for parameters that exceed 2σ.
    Each dict has: parameter, current_value, mean, std_dev, z_score, severity.
    """
    try:
        historical = await get_historical_climate(lat, lon, days=30)
    except Exception:
        return []  # gracefully skip if NASA POWER is unavailable

    anomalies = []

    checks = [
        {
            "param":    "rainfall_1h",
            "label":    "Rainfall (1h)",
            "current":  current_weather.get("rainfall_1h", 0),
            "hist_avg": historical.get("avg_precipitation_mm", 0),
            "hist_max": historical.get("max_precipitation_mm", 0),
        },
        {
            "param":    "wind_speed",
            "label":    "Wind Speed",
            "current":  current_weather.get("wind_speed", 0),
            "hist_avg": historical.get("avg_wind_speed", 0),
            "hist_max": historical.get("max_wind_speed", 0),
        },
        {
            "param":    "humidity",
            "label":    "Humidity",
            "current":  current_weather.get("humidity", 50),
            "hist_avg": historical.get("avg_humidity", 60),
            "hist_max": 100,
        },
    ]

    for c in checks:
        avg = c["hist_avg"]
        # Approximate std dev from avg & max (σ ≈ (max − avg) / 2)
        std = max((c["hist_max"] - avg) / 2, 0.1)
        z = (c["current"] - avg) / std

        if abs(z) >= 2.0:
            if abs(z) >= 3.5:
                severity = "EXTREME"
            elif abs(z) >= 2.5:
                severity = "HIGH"
            else:
                severity = "MODERATE"

            anomalies.append({
                "parameter":     c["label"],
                "current_value": round(c["current"], 2),
                "baseline_mean": round(avg, 2),
                "std_dev":       round(std, 2),
                "z_score":       round(z, 2),
                "severity":      severity,
                "direction":     "above" if z > 0 else "below",
            })

    return anomalies
