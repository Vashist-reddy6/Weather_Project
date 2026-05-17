"""
Authentication Router — WeatherGuard AI
========================================
Provides login and registration endpoints with strict rate limiting:
  • 5 attempts per 15 minutes per IP address

No external auth library is required; passwords are hashed with bcrypt via
the standard `hashlib` module (PBKDF2-HMAC-SHA256).  Tokens are signed
HS256 JWTs via PyJWT (added to requirements if needed) — or, if you prefer
to keep dependencies minimal, a simple opaque token stored in the DB is
used as a fallback.

Current implementation uses the DB-based opaque token pattern so there are
zero extra dependencies beyond what is already in requirements.txt.
"""

import secrets
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends, Header
from pydantic import BaseModel, EmailStr, field_validator, Field
from slowapi.errors import RateLimitExceeded

from database import get_db
from middleware.rate_limiter import auth_limiter

router = APIRouter()

# ---------------------------------------------------------------------------
# Password helpers  (PBKDF2-HMAC-SHA256 — no extra deps needed)
# ---------------------------------------------------------------------------
_ITERATIONS = 260_000
_HASH_NAME   = "sha256"


def _hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash string: <salt_hex>$<hash_hex>"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison of a plaintext password against a stored hash."""
    try:
        salt, hash_hex = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode(), salt.encode(), _ITERATIONS)
    return hmac.compare_digest(dk.hex(), hash_hex)


def _create_token() -> str:
    """Generate a cryptographically secure opaque session token."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Ensure the auth tables exist in SQLite
# ---------------------------------------------------------------------------

def create_auth_tables():
    """Create auth_users and auth_tokens tables if they don't exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auth_users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT    NOT NULL UNIQUE,
            name       TEXT    NOT NULL,
            password   TEXT    NOT NULL,
            role       TEXT    NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auth_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES auth_users(id)
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name:     str = Field(..., min_length=2, max_length=100)
    email:    EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(..., max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int           # seconds
    user_id:      int
    name:         str
    role:         str


# ---------------------------------------------------------------------------
# Token lifetime
# ---------------------------------------------------------------------------
TOKEN_TTL_HOURS = 24


# ---------------------------------------------------------------------------
# Routes — rate-limited to 5 requests / 15 minutes per IP
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    summary="Register a new user account",
)
@auth_limiter.limit("5/15minutes")
async def register(request: Request, body: RegisterRequest):
    """
    Create a new user account and return a session token.

    **Rate limited**: 5 attempts per 15 minutes per IP address.
    """
    conn = get_db()
    try:
        # Check duplicate email
        existing = conn.execute(
            "SELECT id FROM auth_users WHERE email = ?", (body.email.lower(),)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        hashed = _hash_password(body.password)
        cursor = conn.execute(
            "INSERT INTO auth_users (email, name, password) VALUES (?, ?, ?)",
            (body.email.lower(), body.name, hashed),
        )
        conn.commit()
        user_id = cursor.lastrowid
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()

    return _issue_token(user_id, body.name, "user")


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a session token",
)
@auth_limiter.limit("5/15minutes")
async def login(request: Request, body: LoginRequest):
    """
    Authenticate with email + password and receive a session token.

    **Rate limited**: 5 attempts per 15 minutes per IP address.
    Exceeding this returns **HTTP 429 Too Many Requests**.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, password, role FROM auth_users WHERE email = ?",
            (body.email.lower(),),
        ).fetchone()
    finally:
        conn.close()

    # Deliberate vague error — don't reveal whether email exists
    if not row or not _verify_password(body.password, row["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return _issue_token(row["id"], row["name"], row["role"])


@router.post("/logout", summary="Invalidate the current session token")
async def logout(authorization: Optional[str] = Header(None, alias="Authorization")):
    """Delete a session token, effectively logging the user out.

    Reads the token from the ``Authorization: Bearer <token>`` header
    so the token is never exposed in server access logs or browser history.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    conn = get_db()
    try:
        conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "success", "message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def get_current_user(authorization: Optional[str] = Header(None, alias="Authorization")):
    """Dependency to retrieve the currently authenticated user from the token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    
    conn = get_db()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.email, u.role 
            FROM auth_users u 
            JOIN auth_tokens t ON u.id = t.user_id 
            WHERE t.token = ? AND t.expires_at > ?
            """,
            (token, datetime.now(timezone.utc).isoformat())
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return dict(row)
    finally:
        conn.close()

def require_admin(user: dict = Depends(get_current_user)):
    """Dependency to enforce admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

# ---------------------------------------------------------------------------
# Helper — persist token and return response
# ---------------------------------------------------------------------------

def _issue_token(user_id: int, name: str, role: str) -> TokenResponse:
    token      = _create_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)

    conn = get_db()
    try:
        # Purge expired tokens for this user first (housekeeping)
        conn.execute(
            "DELETE FROM auth_tokens WHERE user_id = ? AND expires_at < ?",
            (user_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "INSERT INTO auth_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return TokenResponse(
        access_token=token,
        expires_in=TOKEN_TTL_HOURS * 3600,
        user_id=user_id,
        name=name,
        role=role,
    )
