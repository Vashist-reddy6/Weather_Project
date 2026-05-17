from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
import io
from middleware.rate_limiter import limiter

router = APIRouter()

LANG_CODES = {
    "en": "en",
    "hi": "hi",
    "te": "te",
    "ta": "ta",
    "mr": "mr",
    "bn": "bn",
}

ALERT_TEMPLATES = {
    "en": {
        "LOW":      "WeatherGuard Alert. Low risk detected in {location}. Current weather conditions are safe. Stay informed and monitor updates.",
        "MODERATE": "WeatherGuard Moderate Alert. Elevated weather risk detected in {location}. Be prepared. Monitor weather updates frequently.",
        "HIGH":     "WeatherGuard High Alert! High disaster risk in {location}! Take immediate precautions. Avoid outdoor activities. Stay indoors.",
        "CRITICAL": "WeatherGuard Critical Emergency! Critical disaster risk in {location}! Evacuate to higher ground immediately. Seek emergency shelter now. Call 112 for help.",
    },
    "hi": {
        "LOW":      "{location} में कम खतरा है। मौसम सुरक्षित है।",
        "MODERATE": "{location} में मध्यम खतरा है। सतर्क रहें।",
        "HIGH":     "{location} में उच्च खतरा है! तुरंत सावधानी बरतें।",
        "CRITICAL": "{location} में अत्यंत गंभीर खतरा है! तुरंत सुरक्षित स्थान पर जाएं! मदद के लिए 112 पर कॉल करें।",
    },
    "te": {
        "LOW":      "{location} లో తక్కువ ప్రమాదం ఉంది. వాతావరణం సురక్షితంగా ఉంది.",
        "MODERATE": "{location} లో మధ్యస్థ ప్రమాదం ఉంది. అప్రమత్తంగా ఉండండి.",
        "HIGH":     "{location} లో అధిక ప్రమాదం ఉంది! వెంటనే జాగ్రత్తలు తీసుకోండి.",
        "CRITICAL": "{location} లో అత్యంత తీవ్రమైన ప్రమాదం ఉంది! వెంటనే సురక్షిత ప్రదేశానికి వెళ్ళండి!",
    },
    "ta": {
        "LOW":      "{location} இல் குறைந்த ஆபத்து உள்ளது. வானிலை பாதுகாப்பாக உள்ளது.",
        "MODERATE": "{location} இல் மிதமான ஆபத்து உள்ளது. கவனமாக இருங்கள்.",
        "HIGH":     "{location} இல் அதிக ஆபத்து உள்ளது! உடனடியாக நடவடிக்கை எடுங்கள்.",
        "CRITICAL": "{location} இல் மிக தீவிர ஆபத்து உள்ளது! உடனடியாக பாதுகாப்பான இடத்திற்கு செல்லுங்கள்!",
    },
}


@router.get("/alert")
@limiter.limit("60/minute")
async def voice_alert(
    request: Request,
    risk_level: str  = Query(..., max_length=20, description="Risk level: LOW/MODERATE/HIGH/CRITICAL"),
    location:   str  = Query(..., max_length=150, description="Location name"),
    lang:       str  = Query("en", max_length=5, description="Language code: en/hi/te/ta"),
):
    """Generate a voice alert MP3 using gTTS"""
    try:
        from gtts import gTTS
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="gTTS not installed. Run: pip install gTTS"
        )

    lang_code = LANG_CODES.get(lang, "en")
    templates = ALERT_TEMPLATES.get(lang, ALERT_TEMPLATES["en"])
    template  = templates.get(risk_level.upper(), templates["LOW"])

    # Strip control characters and null bytes before TTS injection
    import re
    safe_location = re.sub(r"[\x00-\x1f\x7f]", "", location).strip()[:100] or "Unknown Location"

    text = template.format(location=safe_location)

    try:
        tts = gTTS(text=text, lang=lang_code, slow=False)
        audio_fp = io.BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)

        return StreamingResponse(
            audio_fp,
            media_type="audio/mpeg",
            headers={"Content-Disposition": f"inline; filename=alert_{risk_level.lower()}.mp3"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice generation failed: {str(e)}")
