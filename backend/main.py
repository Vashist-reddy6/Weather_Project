import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from routers import weather, alerts, predict, voice, community, chatbot, resources
from routers import sms_webhook
from routers import ws as ws_router
from routers.auth import router as auth_router, create_auth_tables
from database import create_tables
from middleware.rate_limiter import limiter, auth_limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    create_auth_tables()
    yield


app = FastAPI(
    title="WeatherGuard AI — Disaster Prediction & Alert System",
    description="Real-time disaster risk prediction using weather data, ML models, and voice alerts",
    version="3.0.0",
    lifespan=lifespan,
)

# ── Rate limiting ────────────────────────────────────────────────────────────
# Attach the shared limiter to the app state so slowapi can find it.
app.state.limiter = limiter

# Also register auth_limiter so its RateLimitExceeded exceptions are caught.
# Without this, hitting the auth rate limit causes an unhandled 500 error.
app.state.auth_limiter = auth_limiter

# Register the built-in 429 handler — returns JSON with Retry-After header.
# Covers both limiter and auth_limiter since the exception type is the same.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# SlowAPIMiddleware injects the limiter into every request's state.
app.add_middleware(SlowAPIMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────
# allow_origins=["*"] is safe here because allow_credentials=False
# (cookies are not forwarded). In production you can restrict this to
# your frontend domain, e.g. allow_origins=["https://weatherguard.app"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/auth",    tags=["Authentication"])
app.include_router(weather.router, prefix="/api/weather", tags=["Weather"])
app.include_router(alerts.router,  prefix="/api/alerts",  tags=["Alerts"])
app.include_router(predict.router,    prefix="/api/predict",    tags=["Prediction"])
app.include_router(voice.router,      prefix="/api/voice",      tags=["Voice Alerts"])
app.include_router(community.router,    prefix="/api/community",   tags=["Community Reports"])
app.include_router(chatbot.router,      prefix="/api/chatbot",     tags=["AI Chatbot"])
app.include_router(resources.router,    prefix="/api/resources",   tags=["Resource Tracker"])
app.include_router(sms_webhook.router,  prefix="/api/sms",         tags=["SMS Webhook"])
app.include_router(ws_router.router,     prefix="/ws",              tags=["WebSocket"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "WeatherGuard AI — Disaster Prediction & Alert System",
        "docs":    "/docs",
        "status":  "running",
        "version": "3.0.0",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "WeatherGuard AI"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
