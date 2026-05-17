"""
Resource Tracker router — shelters, medical camps, and relief distribution points.

Static JSON dataset covering major Indian disaster-prone cities.
For production, replace with a live NDMA / disaster management API.
"""
import math
from fastapi import APIRouter, Query, Request
from middleware.rate_limiter import limiter

router = APIRouter()

# ── Static resource dataset ───────────────────────────────────────────────────
RESOURCES = [
    # Hyderabad / Telangana
    {"id": 1,  "name": "Gandhi Nagar Community Hall",      "type": "shelter",      "city": "Hyderabad",   "state": "Telangana",     "lat": 17.3850, "lon": 78.4867, "capacity": 500, "contact": "040-23456789",   "status": "ACTIVE", "amenities": ["water","food","medical"]},
    {"id": 2,  "name": "Nalgonda Government School",       "type": "shelter",      "city": "Nalgonda",    "state": "Telangana",     "lat": 17.0575, "lon": 79.2636, "capacity": 300, "contact": "08682-222333",   "status": "ACTIVE", "amenities": ["water","food"]},
    {"id": 3,  "name": "Warangal District Relief Camp",    "type": "medical_camp", "city": "Warangal",    "state": "Telangana",     "lat": 17.9689, "lon": 79.5941, "capacity": 200, "contact": "0870-2461234",   "status": "ACTIVE", "amenities": ["medical","ambulance"]},
    {"id": 4,  "name": "Khammam Flood Relief Point",       "type": "relief_center","city": "Khammam",     "state": "Telangana",     "lat": 17.2473, "lon": 80.1514, "capacity": 350, "contact": "08742-222222",   "status": "ACTIVE", "amenities": ["water","food","clothing"]},
    # Andhra Pradesh
    {"id": 5,  "name": "Vijayawada Cyclone Shelter A",     "type": "shelter",      "city": "Vijayawada",  "state": "Andhra Pradesh","lat": 16.5062, "lon": 80.6480, "capacity": 800, "contact": "0866-2973600",   "status": "ACTIVE", "amenities": ["water","food","power_backup"]},
    {"id": 6,  "name": "Rajahmundry Emergency Camp",       "type": "medical_camp", "city": "Rajahmundry", "state": "Andhra Pradesh","lat": 16.9891, "lon": 81.7801, "capacity": 250, "contact": "0883-2423999",   "status": "ACTIVE", "amenities": ["medical","first_aid"]},
    {"id": 7,  "name": "Visakhapatnam Cyclone Shelter",    "type": "shelter",      "city": "Visakhapatnam","state":"Andhra Pradesh","lat": 17.6868, "lon": 83.2185, "capacity": 1200,"contact": "0891-2563333",   "status": "ACTIVE", "amenities": ["water","food","medical","power_backup"]},
    # Tamil Nadu
    {"id": 8,  "name": "Chennai Flood Relief Center",      "type": "relief_center","city": "Chennai",     "state": "Tamil Nadu",    "lat": 13.0827, "lon": 80.2707, "capacity": 1000,"contact": "044-28521100",   "status": "ACTIVE", "amenities": ["water","food","medical","clothing"]},
    {"id": 9,  "name": "Cuddalore District Shelter",       "type": "shelter",      "city": "Cuddalore",   "state": "Tamil Nadu",    "lat": 11.7480, "lon": 79.7714, "capacity": 600, "contact": "04142-220300",   "status": "ACTIVE", "amenities": ["water","food"]},
    # Maharashtra
    {"id": 10, "name": "Mumbai BKC Medical Camp",          "type": "medical_camp", "city": "Mumbai",      "state": "Maharashtra",   "lat": 19.0596, "lon": 72.8656, "capacity": 400, "contact": "022-26591111",   "status": "ACTIVE", "amenities": ["medical","ambulance","first_aid"]},
    {"id": 11, "name": "Pune Flood Emergency Shelter",     "type": "shelter",      "city": "Pune",        "state": "Maharashtra",   "lat": 18.5204, "lon": 73.8567, "capacity": 500, "contact": "020-26127500",   "status": "ACTIVE", "amenities": ["water","food","medical"]},
    # West Bengal
    {"id": 12, "name": "Kolkata Disaster Management HQ",   "type": "disaster_hq",  "city": "Kolkata",     "state": "West Bengal",   "lat": 22.5726, "lon": 88.3639, "capacity": 600, "contact": "033-22143526",   "status": "ACTIVE", "amenities": ["water","food","medical","command_center"]},
    {"id": 13, "name": "Midnapore Cyclone Relief Point",   "type": "relief_center","city": "Midnapore",   "state": "West Bengal",   "lat": 22.4225, "lon": 87.3195, "capacity": 400, "contact": "03222-255500",   "status": "ACTIVE", "amenities": ["water","food","clothing"]},
    # Odisha
    {"id": 14, "name": "Bhubaneswar Cyclone Shelter",      "type": "shelter",      "city": "Bhubaneswar", "state": "Odisha",        "lat": 20.2961, "lon": 85.8189, "capacity": 700, "contact": "0674-2392001",   "status": "ACTIVE", "amenities": ["water","food","medical","power_backup"]},
    {"id": 15, "name": "Puri Coastal Emergency Camp",      "type": "medical_camp", "city": "Puri",        "state": "Odisha",        "lat": 19.8134, "lon": 85.8314, "capacity": 300, "contact": "06752-222097",   "status": "ACTIVE", "amenities": ["medical","first_aid","ambulance"]},
    # Bihar
    {"id": 16, "name": "Patna Flood Relief Point",         "type": "relief_center","city": "Patna",       "state": "Bihar",         "lat": 25.5941, "lon": 85.1376, "capacity": 450, "contact": "0612-2201010",   "status": "ACTIVE", "amenities": ["water","food","medical","clothing"]},
    # Gujarat
    {"id": 17, "name": "Ahmedabad Emergency Shelter",      "type": "shelter",      "city": "Ahmedabad",   "state": "Gujarat",       "lat": 23.0225, "lon": 72.5714, "capacity": 550, "contact": "079-25502020",   "status": "ACTIVE", "amenities": ["water","food","medical"]},
    {"id": 18, "name": "Surat Flood Camp",                 "type": "relief_center","city": "Surat",       "state": "Gujarat",       "lat": 21.1702, "lon": 72.8311, "capacity": 400, "contact": "0261-2424242",   "status": "ACTIVE", "amenities": ["water","food","clothing"]},
    # Kerala
    {"id": 19, "name": "Kochi Flood Relief Hub",           "type": "disaster_hq",  "city": "Kochi",       "state": "Kerala",        "lat": 9.9312,  "lon": 76.2673, "capacity": 800, "contact": "0484-2364100",   "status": "ACTIVE", "amenities": ["water","food","medical","command_center","boats"]},
    {"id": 20, "name": "Thrissur Emergency Shelter",       "type": "shelter",      "city": "Thrissur",    "state": "Kerala",        "lat": 10.5276, "lon": 76.2144, "capacity": 500, "contact": "0487-2360000",   "status": "ACTIVE", "amenities": ["water","food","medical"]},
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.asin(math.sqrt(min(a, 1.0)))


@router.get("/list")
@limiter.limit("60/minute")
async def list_resources(
    request: Request,
    lat:           float = Query(None, ge=-90, le=90, description="Latitude for proximity sort"),
    lon:           float = Query(None, ge=-180, le=180, description="Longitude for proximity sort"),
    resource_type: str   = Query(None, max_length=50, description="Filter: shelter|medical_camp|relief_center|disaster_hq"),
    radius_km:     float = Query(500.0, ge=0.0, le=10000.0, description="Search radius in km (only if lat/lon provided)"),
):
    """Return nearby disaster resources, sorted by distance when lat/lon are given."""
    data = RESOURCES.copy()

    # Filter by type
    if resource_type:
        data = [r for r in data if r["type"] == resource_type]

    # Filter & sort by distance
    if lat is not None and lon is not None:
        enriched = []
        for r in data:
            dist = _haversine(lat, lon, r["lat"], r["lon"])
            if dist <= radius_km:
                enriched.append({**r, "distance_km": round(dist, 1)})
        enriched.sort(key=lambda r: r["distance_km"])
        data = enriched
    else:
        data = [{**r, "distance_km": None} for r in data]

    return {"status": "success", "count": len(data), "data": data}


@router.get("/types")
@limiter.limit("60/minute")
async def resource_types(request: Request):
    """Return available resource types."""
    types = list({r["type"] for r in RESOURCES})
    return {"status": "success", "data": sorted(types)}
