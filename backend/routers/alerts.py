from fastapi import APIRouter, HTTPException, Query, Request, Depends, Header
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from database import get_db
from services.twilio_service import send_sms_alert, generate_alert_message
from middleware.rate_limiter import limiter
from routers.auth import get_current_user

router = APIRouter()

_VALID_RISK_LEVELS = {"LOW", "MODERATE", "HIGH", "CRITICAL"}


class UserRegistration(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=5, max_length=20)
    email: Optional[EmailStr] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    location_name: Optional[str] = Field("Unknown", max_length=150)


class ManualAlert(BaseModel):
    user_id: int
    risk_level: str = Field(..., max_length=20)
    location: str = Field(..., max_length=150)
    weather_description: str = Field(..., max_length=500)


class BroadcastAlert(BaseModel):
    risk_level: str = Field(..., max_length=20)
    location: str = Field(..., max_length=150)
    weather_description: str = Field(..., max_length=500)


def _check_risk_level(risk_level: str) -> str:
    """Validate and normalise risk level enum."""
    normalised = risk_level.upper()
    if normalised not in _VALID_RISK_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"risk_level must be one of {sorted(_VALID_RISK_LEVELS)}"
        )
    return normalised


# ── Public (no auth required) ─────────────────────────────────────────────────

@router.post("/register")
@limiter.limit("10/minute")
async def register_user(request: Request, user: UserRegistration):
    """Register a user to receive disaster alerts.
    Rate-limited to 10/min to prevent account-creation abuse.
    """
    conn = get_db()
    try:
        # Prevent duplicate registrations for the same phone number
        existing = conn.execute(
            "SELECT id FROM users WHERE phone = ?", (user.phone,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="This phone number is already registered for alerts."
            )

        cursor = conn.execute(
            "INSERT INTO users (name, phone, email, latitude, longitude, location_name) VALUES (?, ?, ?, ?, ?, ?)",
            (user.name, user.phone, user.email, user.latitude, user.longitude, user.location_name)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {"status": "success", "message": f"Registered for alerts", "user_id": user_id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")
    finally:
        conn.close()


# ── Auth-protected endpoints ──────────────────────────────────────────────────

@router.get("/users")
@limiter.limit("60/minute")
async def get_users(
    request: Request,
):
    """Get all registered users."""
    conn = get_db()
    try:
        cursor = conn.execute("SELECT * FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return {"status": "success", "data": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("/send")
@limiter.limit("20/minute")
async def send_alert(
    request: Request,
    alert: ManualAlert,
):
    """Send SMS alert to a specific user."""
    risk_level = _check_risk_level(alert.risk_level)

    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (alert.user_id,)).fetchone()
    finally:
        conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    message = generate_alert_message(risk_level, alert.location, alert.weather_description)
    result = send_sms_alert(user["phone"], message)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO alerts (user_id, message, risk_level, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
            (alert.user_id, message, risk_level, user["latitude"], user["longitude"])
        )
        conn.commit()
    finally:
        conn.close()

    return {"status": "success", "sms_result": result}


@router.post("/broadcast")
@limiter.limit("5/minute")
async def broadcast_alert(
    request: Request,
    alert: BroadcastAlert,
):
    """Broadcast alert to ALL registered users.
    Rate-limited to 5/min to prevent runaway SMS costs.
    """
    risk_level = _check_risk_level(alert.risk_level)

    conn = get_db()
    try:
        users = conn.execute("SELECT * FROM users").fetchall()
    finally:
        conn.close()

    message = generate_alert_message(risk_level, alert.location, alert.weather_description)
    results = []

    # Send SMS to each user (network I/O) — done outside the DB transaction
    for user in users:
        result = send_sms_alert(user["phone"], message)
        results.append({"user": user["name"], "result": result})

    # Persist all alert records in a single connection
    conn = get_db()
    try:
        for user in users:
            conn.execute(
                "INSERT INTO alerts (user_id, message, risk_level) VALUES (?, ?, ?)",
                (user["id"], message, risk_level)
            )
        conn.commit()
    finally:
        conn.close()

    return {"status": "success", "total_sent": len(results), "results": results}


@router.get("/history")
@limiter.limit("60/minute")
async def alert_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent alert history (max 100 records)."""
    conn = get_db()
    try:
        cursor = conn.execute("""
            SELECT a.*, u.name as user_name, u.phone as user_phone
            FROM alerts a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.sent_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return {"status": "success", "data": [dict(row) for row in rows]}
    finally:
        conn.close()
