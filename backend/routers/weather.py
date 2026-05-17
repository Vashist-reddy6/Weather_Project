from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from services.openweather import get_current_weather, get_forecast, geocode_city
from services.nasa_power import get_historical_climate
from services.tomorrow_io import get_hyperlocal_weather
from middleware.rate_limiter import limiter

router = APIRouter()


@router.get("/current")
@limiter.limit("60/minute")
async def current_weather(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude")
):
    """Get current weather for a location"""
    try:
        weather = await get_current_weather(lat, lon)
        return {"status": "success", "data": weather}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast")
@limiter.limit("60/minute")
async def weather_forecast(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude")
):
    """Get 5-day weather forecast"""
    try:
        forecast = await get_forecast(lat, lon)
        return {"status": "success", "data": forecast}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical")
@limiter.limit("60/minute")
async def historical_climate(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    days: int = Query(30, ge=1, le=365, description="Number of historical days to fetch")
):
    """Get historical climate data from NASA POWER API"""
    try:
        data = await get_historical_climate(lat, lon, days)
        return {"status": "success", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/geocode")
@limiter.limit("60/minute")
async def geocode(
    request: Request,
    q: str = Query(..., max_length=150, description="City name to search")
):
    """Geocode a city name into coordinates"""
    try:
        data = await geocode_city(q)
        return {"status": "success", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hyperlocal")
@limiter.limit("30/minute")
async def hyperlocal_weather(
    request: Request,
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude")
):
    """Get realtime hyperlocal weather data from Tomorrow.io"""
    try:
        data = await get_hyperlocal_weather(lat, lon)
        return {"status": "success", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

