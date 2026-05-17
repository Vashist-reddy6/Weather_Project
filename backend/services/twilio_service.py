import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")


def send_sms_alert(to_phone: str, message: str) -> dict:
    """Send SMS alert via Twilio"""
    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        sms = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone
        )

        return {
            "success": True,
            "sid": sms.sid,
            "status": sms.status,
            "to": to_phone
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "to": to_phone
        }


def generate_alert_message(risk_level: str, location: str, weather_desc: str) -> str:
    """Generate alert message based on risk level"""
    emojis = {
        "LOW": "🟢",
        "MODERATE": "🟡",
        "HIGH": "🟠",
        "CRITICAL": "🔴"
    }
    emoji = emojis.get(risk_level, "⚠️")

    messages = {
        "LOW": f"{emoji} WeatherGuard: Low risk in {location}. {weather_desc}. Stay informed.",
        "MODERATE": f"{emoji} WeatherGuard MODERATE ALERT: Elevated risk in {location}. {weather_desc}. Be prepared.",
        "HIGH": f"{emoji} WeatherGuard HIGH ALERT: High risk in {location}! {weather_desc}. Take precautions immediately.",
        "CRITICAL": f"{emoji} WeatherGuard CRITICAL ALERT: CRITICAL RISK in {location}! {weather_desc}. EVACUATE or seek shelter NOW."
    }

    return messages.get(risk_level, f"⚠️ WeatherGuard Alert: {risk_level} risk in {location}. {weather_desc}.")
