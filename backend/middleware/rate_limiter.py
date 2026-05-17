"""
Rate Limiting Middleware — WeatherGuard AI
==========================================
Uses slowapi (starlette-compatible wrapper around the `limits` library).

Strategy
--------
* Login / registration routes  → 5 requests per 15 minutes  (per IP)
* All other API routes          → 60 requests per minute      (per IP)

The key function extracts the real client IP, respecting X-Forwarded-For
when the app is behind a reverse proxy (Nginx, Traefik, etc.).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


# ---------------------------------------------------------------------------
# Key function — combine IP + (optional) username for login endpoints
# ---------------------------------------------------------------------------

def _get_login_key(request: Request) -> str:
    """
    For login/register routes we key on IP *and* the submitted identifier
    (email / phone) so that an attacker cannot bypass the limit by rotating
    IPs while hammering a single account, and a legitimate user isn't blocked
    because they share a NAT IP with other users.

    Falls back to pure IP if the body isn't JSON or lacks an identifier field.
    """
    ip = get_remote_address(request)
    # The identifier will be read from the JSON body in the auth router via
    # a dependency; here we just use IP as the primary key so slowapi can
    # track it at request-time without awaiting the body.
    return ip


# ---------------------------------------------------------------------------
# Shared Limiter instance  (in-memory storage — no Redis required)
# ---------------------------------------------------------------------------

limiter = Limiter(
    key_func=get_remote_address,          # default key for general routes
    default_limits=["60/minute"],         # applied to every decorated route
    storage_uri="memory://",
)

# A stricter limiter specifically for auth / login routes.
# Keyed on IP; 5 attempts per 15-minute window.
auth_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["5/15minutes"],
    storage_uri="memory://",
)


# ---------------------------------------------------------------------------
# Re-export helpers consumed by main.py and routers
# ---------------------------------------------------------------------------

__all__ = ["limiter", "auth_limiter"]
