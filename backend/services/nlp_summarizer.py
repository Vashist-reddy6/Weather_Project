"""
NLP Alert Summarizer — rule-based human-readable alert generator.
Produces actionable text in EN/HI/TE/TA without any external API dependency.
"""

from datetime import datetime
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Templates per language ────────────────────────────────────────────────────
_TEMPLATES = {
    "en": {
        "CRITICAL": (
            "🔴 CRITICAL ALERT: Extreme disaster risk detected in {location}. "
            "Current conditions — Temp: {temp}°C, Wind: {wind} m/s, Rainfall: {rain} mm/h, Humidity: {humidity}%. "
            "Pressure: {pressure} hPa. {hazard_note} "
            "IMMEDIATE ACTION REQUIRED: Evacuate to nearest shelter. Call 112."
        ),
        "HIGH": (
            "🟠 HIGH RISK WARNING for {location}. "
            "Conditions — Temp: {temp}°C, Wind: {wind} m/s, Rainfall: {rain} mm/h. "
            "{hazard_note} Stay indoors, monitor NDMA updates at ndma.gov.in. Emergency: 112."
        ),
        "MODERATE": (
            "🟡 MODERATE RISK ADVISORY — {location}. "
            "Weather: Temp {temp}°C, Wind {wind} m/s, Humidity {humidity}%. "
            "{hazard_note} Stay alert and prepare emergency supplies."
        ),
        "LOW": (
            "🟢 LOW RISK — {location}. Conditions are currently stable. "
            "Temp: {temp}°C, Wind: {wind} m/s. Continue monitoring."
        ),
    },
    "hi": {
        "CRITICAL": (
            "🔴 अत्यधिक खतरा: {location} में गंभीर आपदा जोखिम। "
            "तापमान: {temp}°C, हवा: {wind} m/s, वर्षा: {rain} mm/h। "
            "तुरंत निकटतम आश्रय में जाएं। 112 पर कॉल करें।"
        ),
        "HIGH": (
            "🟠 उच्च जोखिम चेतावनी — {location}। "
            "तापमान: {temp}°C, हवा: {wind} m/s। घर के अंदर रहें, NDMA अपडेट देखें।"
        ),
        "MODERATE": (
            "🟡 मध्यम जोखिम सलाह — {location}। "
            "तापमान {temp}°C, हवा {wind} m/s। सतर्क रहें।"
        ),
        "LOW": "🟢 कम जोखिम — {location}। मौसम स्थिर है। तापमान: {temp}°C।",
    },
    "te": {
        "CRITICAL": (
            "🔴 అత్యవసర హెచ్చరిక: {location}లో తీవ్రమైన విపత్తు ప్రమాదం. "
            "ఉష్ణోగ్రత: {temp}°C, గాలి: {wind} m/s, వర్షపాతం: {rain} mm/h. "
            "వెంటనే సమీప ఆశ్రయానికి వెళ్ళండి. 112కి కాల్ చేయండి."
        ),
        "HIGH": (
            "🟠 అధిక ప్రమాద హెచ్చరిక — {location}. "
            "ఉష్ణోగ్రత: {temp}°C, గాలి: {wind} m/s. ఇంటి లోపల ఉండండి."
        ),
        "MODERATE": (
            "🟡 మధ్యస్థ ప్రమాద సూచన — {location}. "
            "ఉష్ణోగ్రత {temp}°C. అప్రమత్తంగా ఉండండి."
        ),
        "LOW": "🟢 తక్కువ ప్రమాదం — {location}. వాతావరణం స్థిరంగా ఉంది.",
    },
    "ta": {
        "CRITICAL": (
            "🔴 அவசர எச்சரிக்கை: {location}ல் தீவிர பேரிடர் அபாயம். "
            "வெப்பநிலை: {temp}°C, காற்று: {wind} m/s, மழை: {rain} mm/h. "
            "உடனடியாக அருகிலுள்ள தங்குமிடத்திற்கு செல்லுங்கள். 112 அழைக்கவும்."
        ),
        "HIGH": (
            "🟠 அதிக அபாய எச்சரிக்கை — {location}. "
            "வெப்பநிலை: {temp}°C, காற்று: {wind} m/s. வீட்டிலேயே இருங்கள்."
        ),
        "MODERATE": (
            "🟡 மிதமான அபாய அறிவிப்பு — {location}. "
            "வெப்பநிலை {temp}°C. விழிப்புடன் இருங்கள்."
        ),
        "LOW": "🟢 குறைந்த அபாயம் — {location}. வானிலை நிலையானது.",
    },
}

_HAZARD_NOTES = {
    "thunderstorm": "Severe thunderstorm in progress — lightning risk is high.",
    "tornado":      "Tornado conditions detected — seek underground shelter immediately.",
    "squall":       "Violent squall detected — stay away from windows and trees.",
    "rain":         "Heavy rainfall increasing flood risk in low-lying areas.",
    "drizzle":      "Persistent drizzle reducing visibility on roads.",
    "snow":         "Snowfall causing dangerous travel conditions.",
    "extreme":      "Extreme weather event in progress.",
}


def generate_alert_summary(
    risk_level: str,
    location: str,
    weather: dict,
    lang: str = "en",
) -> str:
    """Generate a human-readable alert message.

    Args:
        risk_level: One of LOW / MODERATE / HIGH / CRITICAL
        location:   Location name string
        weather:    Dict from get_current_weather()
        lang:       Language code (en / hi / te / ta)

    Returns:
        Formatted alert string in the requested language.
    """
    lang = lang if lang in _TEMPLATES else "en"
    level = risk_level.upper() if risk_level.upper() in _TEMPLATES[lang] else "LOW"
    template = _TEMPLATES[lang][level]

    weather_main = weather.get("weather_main", "").lower()
    hazard_note = next(
        (note for keyword, note in _HAZARD_NOTES.items() if keyword in weather_main),
        "",
    )

    return template.format(
        location=location,
        temp=round(weather.get("temperature", 0), 1),
        wind=round(weather.get("wind_speed", 0), 1),
        rain=round(weather.get("rainfall_1h", 0), 1),
        humidity=weather.get("humidity", 0),
        pressure=weather.get("pressure", 1013),
        hazard_note=hazard_note,
    ).strip()


def generate_sms_reply(risk_level: str, location: str, weather: dict) -> str:
    """Compact SMS reply (under 160 chars) for SMS-only mode."""
    level = risk_level.upper()
    emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MODERATE": "🟡", "LOW": "🟢"}.get(level, "⚪")
    temp  = round(weather.get("temperature", 0), 1)
    wind  = round(weather.get("wind_speed", 0), 1)
    rain  = round(weather.get("rainfall_1h", 0), 1)
    shelter = "Gandhi Nagar Community Hall" if level in ("CRITICAL", "HIGH") else "N/A"
    return (
        f"{emoji} WeatherGuard: {level} risk in {location}. "
        f"T:{temp}C W:{wind}m/s R:{rain}mm. "
        f"Shelter:{shelter}. Emergency:112"
    )[:320]


async def generate_llm_risk_assessment(location: str, weather: dict, ml_risk_score: float, ml_risk_level: str) -> dict:
    """Uses OpenAI to generate an AI Risk Score and an AI Alert Summary based on real-time weather."""
    if not OPENAI_API_KEY:
        return {
            "llm_risk_score": None,
            "llm_risk_level": None,
            "llm_alert_summary": None,
            "error": "OPENAI_API_KEY not configured"
        }
    
    prompt = f"""
You are an expert meteorological AI assistant. 
Given the following real-time weather conditions for {location}, and an initial machine learning risk assessment, provide an updated risk assessment.

Weather Data:
- Temperature: {weather.get('temperature')} °C
- Humidity: {weather.get('humidity')} %
- Pressure: {weather.get('pressure')} hPa
- Wind Speed: {weather.get('wind_speed')} m/s
- Rainfall (1h): {weather.get('rainfall_1h')} mm
- Weather condition: {weather.get('weather_main')} ({weather.get('weather_description')})

Initial ML Assessment:
- Risk Score: {ml_risk_score} (0.0 to 1.0)
- Risk Level: {ml_risk_level}

Your task:
1. Re-evaluate the hazard level.
2. Generate an "llm_risk_score" between 0.0 and 1.0.
3. Determine an "llm_risk_level" (LOW, MODERATE, HIGH, CRITICAL).
4. Write a short, actionable "llm_alert_summary" (1-2 sentences) for the residents.

Output MUST be strictly valid JSON in the following format:
{{
    "llm_risk_score": 0.0,
    "llm_risk_level": "LOW",
    "llm_alert_summary": "..."
}}
"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=12.0, write=5.0, pool=5.0)) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            import json
            result = json.loads(content)
            return {
                "llm_risk_score": result.get("llm_risk_score"),
                "llm_risk_level": result.get("llm_risk_level"),
                "llm_alert_summary": result.get("llm_alert_summary")
            }
    except Exception as e:
        return {
            "llm_risk_score": None,
            "llm_risk_level": None,
            "llm_alert_summary": None,
            "error": str(e)
        }
