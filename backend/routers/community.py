"""
Community hazard reports router — crowdsourced ground-truth pins on the map.
"""
from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional, Literal
from database import get_db
from middleware.rate_limiter import limiter
from routers.auth import require_admin

router = APIRouter()


class HazardReport(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    hazard_type: Literal[
        "flooded_road", "downed_line", "landslide", "fire",
        "cyclone_damage", "building_collapse", "road_blocked", "other"
    ]
    description: str = Field(..., min_length=5, max_length=1000)
    reporter_name: Optional[str] = Field("Anonymous", max_length=100)
    severity: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"] = "MODERATE"


@router.post("/report")
@limiter.limit("20/minute")
async def submit_report(request: Request, report: HazardReport):
    """Submit a community hazard report."""
    conn = get_db()
    try:
        cursor = conn.execute(
            """INSERT INTO community_reports
               (latitude, longitude, hazard_type, description, reporter_name, severity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (report.latitude, report.longitude, report.hazard_type,
             report.description, report.reporter_name, report.severity)
        )
        conn.commit()
        return {"status": "success", "id": cursor.lastrowid, "message": "Report submitted. Thank you!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/reports")
@limiter.limit("60/minute")
async def get_reports(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(200.0, ge=0.0, le=10000.0),
):
    """Get recent community hazard reports, optionally filtered by radius."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM community_reports ORDER BY reported_at DESC LIMIT ?", (limit,)
        ).fetchall()
        reports = [dict(r) for r in rows]

        if lat is not None and lon is not None:
            # Simple bounding-box filter (good enough for hackathon)
            deg = radius_km / 111.0
            reports = [
                r for r in reports
                if abs(r["latitude"] - lat) <= deg and abs(r["longitude"] - lon) <= deg
            ]

        return {"status": "success", "data": reports}
    finally:
        conn.close()


@router.delete("/report/{report_id}")
@limiter.limit("10/minute")
async def delete_report(request: Request, report_id: int, admin: dict = Depends(require_admin)):
    """Delete a report (admin action)."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM community_reports WHERE id = ?", (report_id,))
        conn.commit()
        return {"status": "success", "message": f"Report {report_id} deleted"}
    finally:
        conn.close()
