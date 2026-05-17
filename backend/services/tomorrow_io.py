import httpx
import logging
import os
from dotenv import load_dotenv
from fastapi import HTTPException
from services.cache import tomorrow_cache

load_dotenv()

logger = logging.getLogger(__name__)

TOMORROW_IO_API_KEY = os.getenv("TOMORROW_IO_API_KEY", "")
BASE_URL = "https://api.tomorrow.io/v4"
TIMEOUT = httpx.Timeout(connect=8.0, read=12.0, write=5.0, pool=5.0)

def _handle_response(response: httpx.Response, endpoint: str) -> dict:
    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=401,
            detail="Tomorrow.io API key is invalid or inactive. Check TOMORROW_IO_API_KEY in backend/.env"
        )
    if response.status_code == 429:
        raise HTTPException(
            status_code=429, 
            detail="Tomorrow.io rate limit exceeded."
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Tomorrow.io {endpoint} returned {response.status_code}: {response.text[:200]}"
        )

async def get_hyperlocal_weather(lat: float, lon: float) -> dict:
    """Fetch hyperlocal realtime weather data from Tomorrow.io API (10-min TTL cache)."""
    if not TOMORROW_IO_API_KEY:
        raise HTTPException(status_code=500, detail="TOMORROW_IO_API_KEY is missing in environment variables.")

    cache_key = f"tomorrow:{lat:.4f}:{lon:.4f}"
    cached = tomorrow_cache.get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT  tomorrow.io %s,%s", lat, lon)
        return cached

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}/weather/realtime",
                params={
                    "location": f"{lat},{lon}",
                    "apikey": TOMORROW_IO_API_KEY,
                    "units": "metric"
                }
            )
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Tomorrow.io API (network timeout/unreachable). ({type(exc).__name__})"
        )

    _handle_response(response, "/weather/realtime")
    data = response.json()

    # Extract values
    values = data.get("data", {}).get("values", {})
    result = {
        "temperature": values.get("temperature"),
        "humidity": values.get("humidity"),
        "wind_speed": values.get("windSpeed"),
        "wind_gust": values.get("windGust"),
        "precipitation_intensity": values.get("precipitationIntensity"),
        "cloud_cover": values.get("cloudCover"),
        "uv_index": values.get("uvIndex"),
        "visibility": values.get("visibility"),
        "weather_code": values.get("weatherCode")
    }
    tomorrow_cache.set(cache_key, result)
    logger.debug("Cache MISS tomorrow.io %s,%s — fetched from API", lat, lon)
    return result
