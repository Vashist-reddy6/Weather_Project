import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException

NASA_BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
TIMEOUT = httpx.Timeout(connect=10.0, read=40.0, write=5.0, pool=5.0)


async def get_historical_climate(lat: float, lon: float, days: int = 30) -> dict:
    """Fetch historical climate data from NASA POWER API.

    NASA POWER uses -999.0 as a fill/missing value; those entries are
    filtered out before computing statistics to avoid nonsensical negatives.
    """
    # Normalise coordinates
    lon = ((lon + 180) % 360) - 180  # wrap to [-180, 180]
    lat = max(-90.0, min(90.0, lat))

    NASA_FILL_VALUE = -999.0  # sentinel used by NASA POWER for missing data

    end_date = datetime.now() - timedelta(days=5)  # NASA data has ~5 day lag
    start_date = end_date - timedelta(days=days)

    params = {
        "parameters": "PRECTOTCORR,WS2M,RH2M,T2M,PS",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON"
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(NASA_BASE_URL, params=params)
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach NASA POWER API (network timeout/unreachable). ({type(exc).__name__})"
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"NASA POWER API returned {response.status_code}: {response.text[:200]}"
        )
    data = response.json()

    properties = data.get("properties", {}).get("parameter", {})

    # Filter out fill/missing values (-999.0) before computing statistics
    precip_data   = [v for v in properties.get("PRECTOTCORR", {}).values() if v != NASA_FILL_VALUE]
    wind_data     = [v for v in properties.get("WS2M",        {}).values() if v != NASA_FILL_VALUE]
    humidity_data = [v for v in properties.get("RH2M",        {}).values() if v != NASA_FILL_VALUE]

    return {
        "avg_precipitation_mm": round(sum(precip_data)   / len(precip_data),   2) if precip_data   else 0,
        "max_precipitation_mm": round(max(precip_data),                         2) if precip_data   else 0,
        "avg_wind_speed":       round(sum(wind_data)     / len(wind_data),      2) if wind_data     else 0,
        "max_wind_speed":       round(max(wind_data),                            2) if wind_data     else 0,
        "avg_humidity":         round(sum(humidity_data) / len(humidity_data),  2) if humidity_data else 0,
        "data_points": len(precip_data),
        "period_days": days
    }
