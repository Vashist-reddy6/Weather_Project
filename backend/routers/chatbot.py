"""
AI Chatbot router — risk-aware Q&A using a rule-based engine + optional OpenAI fallback.
Works 100% offline with the rule-based engine; the OpenAI path activates when
OPENAI_API_KEY is present in .env.
"""
import os
import re
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from middleware.rate_limiter import limiter

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

router = APIRouter()


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    context: dict = Field(default_factory=dict)   # optional: pass prediction/weather data for grounded answers


# ── Rule-based knowledge base ─────────────────────────────────────────────────
_KB = [
    # Travel safety
    (r"safe.*(travel|go|visit|drive).*(flood|rain|storm|cyclone)",
     "⚠️ Avoid travel during active flood or storm alerts. Check local road conditions at https://ndma.gov.in before departing."),
    (r"(travel|go|visit|drive).*(safe|ok|okay|should i)",
     "Check the risk level for your destination first. LOW/MODERATE = generally safe with caution. HIGH/CRITICAL = avoid travel."),
    # Flood guidance
    (r"flood",
     "🌊 Flood Safety: Move to higher ground immediately. Avoid walking in water above ankle height (15cm can knock you over). Disconnect electrical appliances. Call 112."),
    # Cyclone guidance
    (r"cyclone|hurricane|typhoon",
     "🌀 Cyclone Safety: Stay indoors away from windows. Move to the innermost room on the lowest floor. Do not go out during the eye — winds return. Monitor NDMA alerts."),
    # Heat wave
    (r"heat|heatwave|hot weather",
     "☀️ Heatwave: Stay indoors 12 PM–4 PM. Drink water every 20 minutes. Wear loose light-colored clothing. Heat stroke signs: hot skin + confusion → call 108."),
    # Thunderstorm
    (r"thunder|lightning|storm",
     "⛈️ Thunderstorm: Seek solid shelter immediately. Avoid trees, hilltops, and metal structures. Wait 30 min after last thunder before going outside."),
    # Emergency numbers
    (r"emergency|helpline|number|call|contact",
     "📞 Emergency Numbers (India): Emergency 112 | Ambulance 108 | NDMA Helpline 1078 | Police 100 | Fire 101 | Disaster 1070"),
    # Shelter
    (r"shelter|safe zone|evacuation|evacuate",
     "🏚️ Nearest shelters: Government schools (upper floors), Community halls, Concrete cyclone shelters, Hospitals. Ask local authorities for the nearest active relief camp."),
    # Risk score
    (r"risk score|what.*risk|how dangerous|danger",
     "The risk score (0–100) is computed by our XGBoost ML model from real-time weather data. Score ≥70 = CRITICAL, ≥45 = HIGH, ≥20 = MODERATE, <20 = LOW."),
    # Rainfall
    (r"rain|rainfall|precipitation",
     "🌧️ Heavy rainfall >50mm/h is a flood trigger. >20mm/h — avoid low-lying areas. >10mm/h — reduce travel speed. Monitor hourly forecasts."),
    # Wind
    (r"wind|windspeed|wind speed",
     "💨 Wind speed thresholds: >10 m/s = caution outdoors | >15 m/s = secure loose items | >25 m/s = stay indoors | >35 m/s = extreme danger, evacuate."),
    # SMS mode
    (r"sms|text|offline|no internet|feature phone",
     "📱 SMS Mode: Text 'RISK <city>' to our Twilio number to get the current risk level and nearest shelter by SMS — works on any phone without internet."),
    # Voice alerts
    (r"voice|audio|speak|telugu|hindi|tamil",
     "🔊 Voice alerts are available in English, Hindi (HI), Telugu (TE), and Tamil (TA). Use the 'Play Alert' button in the app after analyzing a location."),
    # Data sources
    (r"data|source|nasa|openweather|how does it work",
     "📡 Data sources: OpenWeatherMap (real-time weather), NASA POWER (30-day historical climate), XGBoost ML model (trained on 5000+ flood events)."),
    # Greeting
    (r"hello|hi|hey|namaste|vanakkam",
     "👋 Hello! I'm WeatherGuard AI Assistant. Ask me about disaster safety, risk levels, evacuation, or weather conditions for any location."),
]


def rule_based_chat(message: str, context: dict) -> str:
    """Match message against knowledge base rules. Returns best match or fallback."""
    msg_lower = message.lower()

    # If context has prediction data, give grounded answers
    prediction = context.get("prediction", {})
    location = context.get("location", {}).get("name", "your area")
    risk_level = prediction.get("risk_level", "")
    weather = context.get("weather", {})

    # Grounded travel/safety answer when we have a live prediction
    if risk_level and re.search(r"safe|travel|go|ok|should i", msg_lower):
        advice = {
            "CRITICAL": f"🔴 NO — {location} has CRITICAL risk right now. Do NOT travel. Evacuate if in the area.",
            "HIGH":     f"🟠 NOT RECOMMENDED — {location} has HIGH risk. Avoid travel; stay indoors.",
            "MODERATE": f"🟡 EXERCISE CAUTION — {location} has MODERATE risk. Travel only if necessary.",
            "LOW":      f"🟢 GENERALLY SAFE — {location} has LOW risk. Normal precautions apply.",
        }.get(risk_level, "")
        if advice:
            return advice

    for pattern, response in _KB:
        if re.search(pattern, msg_lower):
            return response

    return (
        "I'm not sure about that specific query. Try asking about: flood safety, cyclone preparedness, "
        "risk scores, evacuation routes, emergency contacts, or SMS alerts. "
        "For immediate emergencies call 112."
    )


async def openai_chat(message: str, context: dict) -> str:
    """Call OpenAI API for a richer, grounded response."""
    try:
        import httpx
        system_prompt = (
            "You are WeatherGuard AI, a disaster preparedness and risk assessment assistant for India. "
            "You answer questions about weather safety, evacuation, flood risk, cyclone preparedness, "
            "and emergency contacts. Be concise (max 3 sentences), factual, and safety-focused. "
            "Always recommend calling 112 for immediate emergencies."
        )
        if context.get("prediction"):
            p = context["prediction"]
            loc = context.get("location", {}).get("name", "")
            rl = p.get("prediction", {}).get("risk_level", "")
            w = context.get("weather", {})
            system_prompt += (
                f"\n\nCurrent context: Location={loc}, RiskLevel={rl}, "
                f"Temp={w.get('temperature')}°C, Wind={w.get('wind_speed')}m/s, "
                f"Rainfall={w.get('rainfall_1h')}mm/h."
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.4,
                },
            )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return rule_based_chat(message, context)


@router.post("/message")
@limiter.limit("30/minute")
async def chat(request: Request, body: ChatMessage):
    """Process a chat message and return an AI response."""
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if OPENAI_API_KEY:
        reply = await openai_chat(body.message, body.context)
        engine = "openai"
    else:
        reply = rule_based_chat(body.message, body.context)
        engine = "rule_based"

    return {"status": "success", "reply": reply, "engine": engine}
