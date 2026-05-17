"""
Twilio Inbound SMS Webhook — handles RISK <city> keyword bot.

Configure your Twilio phone number's "Messaging → Webhook (POST)" URL to:
    https://<your-backend>/api/sms/inbound

Supported keywords:
    RISK <city>     → returns current risk level + shelter info
    HELP            → returns usage instructions
    STATUS          → returns system status
"""
from fastapi import APIRouter, Request, Response
from services.openweather import geocode_city, get_current_weather
from services.nlp_summarizer import generate_sms_reply
from routers.predict import rule_based_prediction
from twilio.request_validator import RequestValidator
from fastapi import HTTPException
import logging
import os

log = logging.getLogger("sms_webhook")
router = APIRouter()


def _twiml(message: str) -> Response:
    """Wrap a plain-text reply in TwiML XML."""
    # Escape XML-special chars to be safe
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{safe}</Message>"
        "</Response>"
    )
    return Response(content=xml, media_type="text/xml")


@router.post("/inbound")
async def sms_inbound(request: Request):
    """
    Handle inbound SMS messages from Twilio.
    Returns a TwiML XML response that Twilio reads aloud / sends back as SMS.
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if auth_token:
        validator = RequestValidator(auth_token)
        signature = request.headers.get("X-Twilio-Signature", "")
        # Render the full URL, handling proxies if necessary.
        # In production, ensure the reverse proxy correctly sets X-Forwarded-Proto
        # or use request.url._url directly.
        url = str(request.url)
        form = await request.form()
        if not validator.validate(url, form, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    else:
        form = await request.form()

    body = (form.get("Body") or "").strip()
    body_upper = body.upper()

    log.info(f"Inbound SMS: '{body}'")

    # ── HELP ──────────────────────────────────────────────────────────────────
    if body_upper in ("HELP", "?", ""):
        return _twiml(
            "WeatherGuard SMS Bot\n"
            "Commands:\n"
            "RISK <city> — get current risk & shelter\n"
            "  Example: RISK HYDERABAD\n"
            "STATUS — system status\n"
            "Emergency: 112 | NDMA: 1078"
        )

    # ── STATUS ────────────────────────────────────────────────────────────────
    if body_upper == "STATUS":
        return _twiml(
            "WeatherGuard AI: ONLINE\n"
            "Text RISK <city> to get current disaster risk.\n"
            "Emergency: 112"
        )

    # ── RISK <city> ──────────────────────────────────────────────────────────
    if body_upper.startswith("RISK "):
        city_raw = body[5:].strip()
        if not city_raw:
            return _twiml("Usage: RISK <city name>  Example: RISK CHENNAI")

        city = city_raw.title()
        try:
            geo = await geocode_city(city)
            weather = await get_current_weather(geo["lat"], geo["lon"])
            pred = rule_based_prediction(weather)
            reply = generate_sms_reply(pred["risk_level"], city, weather)
            return _twiml(reply)
        except Exception as exc:
            log.warning(f"SMS RISK lookup failed for '{city}': {exc}")
            return _twiml(
                f"WeatherGuard: Could not fetch data for '{city}'.\n"
                "Check city spelling or try a nearby city.\n"
                "Emergency: 112"
            )

    # ── Unknown ───────────────────────────────────────────────────────────────
    return _twiml(
        "WeatherGuard: Unknown command.\n"
        "Text HELP for instructions.\n"
        "Example: RISK MUMBAI"
    )
