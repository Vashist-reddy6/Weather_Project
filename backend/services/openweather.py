import httpx
import os
import logging
from dotenv import load_dotenv
from fastapi import HTTPException
from services.cache import weather_cache, forecast_cache

load_dotenv()

logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5"
TIMEOUT  = httpx.Timeout(connect=8.0, read=12.0, write=5.0, pool=5.0)


def _handle_response(response: httpx.Response, endpoint: str) -> dict:
    """Raise a descriptive HTTPException on API errors instead of a raw 500."""
    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=401,
            detail="OpenWeather API key is invalid or inactive. "
                   "Check OPENWEATHER_API_KEY in backend/.env "
                   "and make sure the key is activated (takes up to 2 hours after signup)."
        )
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"OpenWeather {endpoint}: location not found.")
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"OpenWeather {endpoint} returned {response.status_code}: {response.text[:200]}"
        )


def _normalize_coords(lat: float, lon: float) -> tuple[float, float]:
    """Normalize lat/lon into valid WGS-84 ranges.

    Longitude must be in [-180, 180]. Values outside this range (e.g. 277.37
    instead of -82.63) are wrapped using modular arithmetic.
    Latitude is simply clamped to [-90, 90].
    """
    lon = ((lon + 180) % 360) - 180   # wrap to [-180, 180]
    lat = max(-90.0, min(90.0, lat))  # clamp to [-90, 90]
    return lat, lon


async def get_current_weather(lat: float, lon: float) -> dict:
    """Fetch current weather data from OpenWeatherMap API (5-min TTL cache)."""
    lat, lon = _normalize_coords(lat, lon)
    cache_key = f"weather:{lat:.4f}:{lon:.4f}"

    cached = weather_cache.get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT  weather %s,%s", lat, lon)
        return cached

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}/weather",
                params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric"}
            )
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach OpenWeatherMap API (network timeout/unreachable). "
                   f"Check your internet connection or firewall. ({type(exc).__name__})"
        )
    _handle_response(response, "/weather")
    data = response.json()

    result = {
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "wind_speed": data["wind"]["speed"],
        "wind_deg": data["wind"].get("deg", 0),
        "cloud_cover": data["clouds"]["all"],
        "rainfall_1h": data.get("rain", {}).get("1h", 0),
        "visibility": data.get("visibility", 10000),
        "weather_main": data["weather"][0]["main"],
        "weather_description": data["weather"][0]["description"],
        "weather_icon": data["weather"][0]["icon"],
        "city_name": data.get("name", "Unknown"),
        "country": data["sys"].get("country", ""),
    }
    weather_cache.set(cache_key, result)
    logger.debug("Cache MISS weather %s,%s — fetched from API", lat, lon)
    return result


async def get_forecast(lat: float, lon: float) -> list:
    """Fetch 5-day weather forecast (15-min TTL cache)."""
    lat, lon = _normalize_coords(lat, lon)
    cache_key = f"forecast:{lat:.4f}:{lon:.4f}"

    cached = forecast_cache.get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT  forecast %s,%s", lat, lon)
        return cached

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}/forecast",
                params={"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "cnt": 40}
            )
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach OpenWeatherMap API (network timeout/unreachable). ({type(exc).__name__})"
        )
    _handle_response(response, "/forecast")
    data = response.json()

    forecasts = []
    for item in data["list"]:
        forecasts.append({
            "datetime": item["dt_txt"],
            "temperature": item["main"]["temp"],
            "humidity": item["main"]["humidity"],
            "pressure": item["main"]["pressure"],
            "wind_speed": item["wind"]["speed"],
            "cloud_cover": item["clouds"]["all"],
            "rainfall": item.get("rain", {}).get("3h", 0),
            "weather_main": item["weather"][0]["main"],
            "weather_description": item["weather"][0]["description"],
            "weather_icon": item["weather"][0]["icon"],
        })

    forecast_cache.set(cache_key, forecasts)
    logger.debug("Cache MISS forecast %s,%s — fetched from API", lat, lon)
    return forecasts

async def geocode_city(city_name: str) -> dict:
    """Fetch coordinates for a city name (1-hour TTL cache)."""
    cache_key = f"geocode:{city_name.strip().lower()}"
    cached = weather_cache.get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT  geocode '%s'", city_name)
        return cached

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={"q": city_name, "limit": 1, "appid": OPENWEATHER_API_KEY}
            )
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
        raise HTTPException(status_code=503, detail="Cannot reach OpenWeatherMap Geocoding API.")

    _handle_response(response, "/geo/1.0/direct")
    data = response.json()

    if not data:
        raise HTTPException(status_code=404, detail="City not found.")

    result = {
        "name": data[0].get("name"),
        "country": data[0].get("country"),
        "lat": data[0].get("lat"),
        "lon": data[0].get("lon")
    }
    # Geocoding results are very stable — cache for 1 hour
    weather_cache.set(cache_key, result, ttl=3600)
    logger.debug("Cache MISS geocode '%s' — fetched from API", city_name)
    return result
