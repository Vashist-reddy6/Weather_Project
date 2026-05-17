from fastapi import APIRouter, HTTPException, Query, Request
import asyncio
import json
import joblib
import logging
import numpy as np
import os
import pandas as pd
from services.openweather import get_current_weather
from services.tomorrow_io import get_hyperlocal_weather
from services.nlp_summarizer import generate_alert_summary, generate_llm_risk_assessment
from services.anomaly_detection import detect_anomalies
from services.twilio_service import send_sms_alert, generate_alert_message
from database import get_db
from middleware.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "disaster_model.pkl")
LSTM_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "lstm_model.keras")
LSTM_SCALER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ml", "lstm_scaler.pkl")

_model = None
# ── LSTM (optional — only loaded when lstm_model.keras exists) ───────────────
_lstm_model  = None
_lstm_scaler = None
_LSTM_SEQ_LEN = 24


def load_model(force_reload=False):
    """Load and cache the XGBoost model (lazy singleton)."""
    global _model
    if (force_reload or _model is None) and os.path.exists(MODEL_PATH):
        _model = joblib.load(MODEL_PATH)
    return _model


def load_lstm_model():
    """Load LSTM model + scaler if they exist (graceful no-op otherwise)."""
    global _lstm_model, _lstm_scaler
    if _lstm_model is not None:
        return _lstm_model, _lstm_scaler
    if os.path.exists(LSTM_MODEL_PATH) and os.path.exists(LSTM_SCALER_PATH):
        try:
            import tensorflow as tf  # noqa: F401  (TF optional)
            from tensorflow import keras
            _lstm_model  = keras.models.load_model(LSTM_MODEL_PATH)
            _lstm_scaler = joblib.load(LSTM_SCALER_PATH)
            logger.info("LSTM model loaded from %s", LSTM_MODEL_PATH)
        except Exception as exc:
            logger.warning("LSTM model load failed (TensorFlow not installed?): %s", exc)
    return _lstm_model, _lstm_scaler


# Pre-warm LSTM at import time so first request is fast
try:
    load_lstm_model()
except Exception:
    pass


RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]


def rule_based_prediction(weather_data: dict) -> dict:
    """Fallback rule-based risk scoring when ML model is not available."""
    score = 0.0

    rainfall = weather_data.get("rainfall_1h", 0)
    if rainfall > 50:   score += 0.50
    elif rainfall > 20: score += 0.30
    elif rainfall > 10: score += 0.15
    elif rainfall > 5:  score += 0.05

    wind = weather_data.get("wind_speed", 0)
    if wind > 25:   score += 0.25
    elif wind > 15: score += 0.15
    elif wind > 10: score += 0.08

    humidity = weather_data.get("humidity", 50)
    if humidity > 90: score += 0.10
    elif humidity > 80: score += 0.05

    pressure = weather_data.get("pressure", 1013)
    if pressure < 980:    score += 0.15
    elif pressure < 995:  score += 0.08
    elif pressure < 1005: score += 0.03

    weather_main = weather_data.get("weather_main", "").lower()
    if weather_main == "thunderstorm":          score += 0.20
    elif weather_main in ["squall", "tornado"]: score += 0.40
    elif weather_main in ["rain", "drizzle"]:   score += 0.05

    score = min(score, 1.0)

    if score >= 0.70:   risk_level = "CRITICAL"
    elif score >= 0.45: risk_level = "HIGH"
    elif score >= 0.20: risk_level = "MODERATE"
    else:               risk_level = "LOW"

    return {"risk_score": round(score, 3), "risk_level": risk_level}


@router.get("/risk")
@limiter.limit("60/minute")
async def predict_risk(
    request: Request,
    lat:           float = Query(..., ge=-90, le=90, description="Latitude"),
    lon:           float = Query(..., ge=-180, le=180, description="Longitude"),
    location_name: str   = Query("Unknown", max_length=150, description="Location name"),
    mock_extreme:  bool  = Query(False, description="Simulate extreme weather for testing"),
    override_weather: str = Query(None, description="JSON string of weather features to override"),
):
    """Predict disaster risk for a given location using real-time weather data"""
    try:
        # Base data from OpenWeatherMap
        weather_data = await get_current_weather(lat, lon)
        
        # Fallback to city name if location_name is generic
        if location_name in ("Unknown", "Selected Location") and weather_data.get("city_name"):
            location_name = weather_data["city_name"]

        # Augment with Hyperlocal data from Tomorrow.io (better precipitation/wind accuracy)
        try:
            tomorrow_data = await get_hyperlocal_weather(lat, lon)
            if tomorrow_data.get("precipitation_intensity") is not None:
                weather_data["rainfall_1h"] = tomorrow_data["precipitation_intensity"]
            if tomorrow_data.get("wind_speed") is not None:
                weather_data["wind_speed"] = tomorrow_data["wind_speed"]
            weather_data["tomorrow_io_augmented"] = True
        except Exception:
            # Seamless fallback to just OpenWeatherMap if Tomorrow.io API key is missing or errors
            weather_data["tomorrow_io_augmented"] = False

        ALLOW_MOCK = os.getenv("ALLOW_MOCK", "false").lower() == "true"
        
        if (mock_extreme or override_weather) and not ALLOW_MOCK:
            raise HTTPException(status_code=403, detail="Mock mode disabled in production")

        if mock_extreme:
            weather_data.update({
                "temperature": 35.0, "humidity": 98, "pressure": 960.0, 
                "wind_speed": 45.0, "cloud_cover": 100, "rainfall_1h": 60.0,
                "weather_main": "Squall", "weather_description": "Simulated extreme storm"
            })
            
        if override_weather:
            try:
                overrides = json.loads(override_weather)
                weather_data.update(overrides)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="override_weather must be a valid JSON string")

        model = load_model()
        probas = None  # defined here so WS broadcast below is always safe
        lstm_result = None
        if model:
            features = pd.DataFrame([{
                "temperature": weather_data["temperature"],
                "humidity": weather_data["humidity"],
                "pressure": weather_data["pressure"],
                "wind_speed": weather_data["wind_speed"],
                "cloud_cover": weather_data["cloud_cover"],
                "rainfall_1h": weather_data["rainfall_1h"],
            }])
            # Multiclass: predict returns class index
            class_idx  = int(model.predict(features)[0])
            raw_probas = model.predict_proba(features)[0]

            # Ensure probas has 4 elements (in case the model was trained on fewer classes)
            probas = [float(p) for p in raw_probas]
            while len(probas) < 4:
                probas.append(0.0)

            predicted_class = class_idx
            confidence = probas[predicted_class]

            # Confidence gate: don't fire HIGH/CRITICAL alert on a coin-flip prediction
            if confidence < 0.60 and predicted_class >= 2:
                predicted_class = min(predicted_class, 1)  # cap at MODERATE
                logger.warning(f"Downgrading prediction to MODERATE due to low confidence ({confidence:.2f})")
                
            risk_level = RISK_LEVELS[predicted_class]

            # Keep hazard_score for risk_score metric
            hazard_score = float(probas[0]*0.0 + probas[1]*0.33 + probas[2]*0.66 + probas[3]*1.0)
            
            prediction = {"risk_score": round(hazard_score, 3), "risk_level": risk_level}
            model_used = "xgboost_ml"
            
            # Permanent logging for demo day transparency
            logger.info(f"PREDICT | lat={lat} lon={lon} | features={features.to_dict(orient='records')[0]} | pred={risk_level} | conf={confidence:.2f}")

            # ── LSTM dual-model inference (optional, best-effort) ─────────────
            try:
                lstm_model, lstm_scaler = load_lstm_model()
                if lstm_model is not None and lstm_scaler is not None:
                    FEATURES = ["temperature", "humidity", "pressure", "wind_speed", "cloud_cover", "rainfall_1h"]
                    raw_row = np.array([[weather_data[f] for f in FEATURES]], dtype=np.float32)
                    scaled_row = lstm_scaler.transform(raw_row)  # (1, 6)
                    # Repeat the snapshot to fill the 24-step window (single-snapshot inference)
                    seq = np.tile(scaled_row, (_LSTM_SEQ_LEN, 1))[np.newaxis, ...]  # (1, 24, 6)
                    raw_lstm_probas = lstm_model.predict(seq, verbose=0)[0]  # (3,) or (4,)
                    lstm_probas = [float(p) for p in raw_lstm_probas]
                    while len(lstm_probas) < 4:
                        lstm_probas.append(0.0)

                    lstm_class  = int(np.argmax(lstm_probas))
                    lstm_score  = float(
                        lstm_probas[0]*0.0 + lstm_probas[1]*0.33 +
                        lstm_probas[2]*0.66 + lstm_probas[3]*1.0
                    )
                    lstm_result = {
                        "lstm_risk_score": round(lstm_score, 3),
                        "lstm_risk_level": RISK_LEVELS[lstm_class],
                        "lstm_probas": {
                            "LOW":      round(lstm_probas[0], 4),
                            "MODERATE": round(lstm_probas[1], 4),
                            "HIGH":     round(lstm_probas[2], 4),
                            "CRITICAL": round(lstm_probas[3], 4),
                        }
                    }
                    model_used = "xgboost_ml+lstm"
            except Exception as lstm_err:
                logger.debug("LSTM inference skipped: %s", lstm_err)
        else:
            prediction = rule_based_prediction(weather_data)
            model_used = "rule_based"

        # Generate NLP alert summary & anomaly detection & LLM risk assessment (run concurrently)
        alert_summary, anomalies, llm_assessment = await asyncio.gather(
            asyncio.to_thread(
                generate_alert_summary,
                prediction["risk_level"],
                location_name,
                weather_data,
                "en",
            ),
            detect_anomalies(weather_data, lat, lon),
            generate_llm_risk_assessment(location_name, weather_data, prediction["risk_score"], prediction["risk_level"]),
        )
        
        # Merge the LLM assessment into the main prediction output
        if llm_assessment and not llm_assessment.get("error"):
            prediction["llm_risk_score"] = llm_assessment.get("llm_risk_score")
            prediction["llm_risk_level"] = llm_assessment.get("llm_risk_level")
            prediction["llm_alert_summary"] = llm_assessment.get("llm_alert_summary")
        elif llm_assessment and llm_assessment.get("error"):
            prediction["llm_error"] = llm_assessment.get("error")

        # Persist to DB
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO predictions (latitude, longitude, location_name, risk_score, risk_level, weather_data) VALUES (?, ?, ?, ?, ?, ?)",
                (lat, lon, location_name, prediction["risk_score"], prediction["risk_level"], json.dumps(weather_data))
            )
            conn.commit()
        finally:
            conn.close()

        # ── Auto-SMS on HIGH / CRITICAL risk ──────────────────────────────
        if prediction["risk_level"] in ("HIGH", "CRITICAL"):
            try:
                sms_conn = get_db()
                sms_cursor = sms_conn.execute("SELECT phone FROM users")
                phones = [row["phone"] for row in sms_cursor.fetchall()]
                sms_conn.close()
                sms_message = generate_alert_message(
                    prediction["risk_level"], location_name,
                    weather_data.get("weather_description", "severe conditions")
                )
                for phone in phones:
                    result = send_sms_alert(phone, sms_message)
                    if not result.get("success"):
                        logger.warning("SMS failed to %s: %s", phone, result.get("error"))
                logger.info("Auto-SMS sent to %d operators for %s risk", len(phones), prediction["risk_level"])
            except Exception as sms_err:
                logger.error("Auto-SMS broadcast error: %s", sms_err)

        # ── Push live event via WebSocket ──────────────────────────────────
        try:
            from routers.ws import manager as ws_manager
            await ws_manager.broadcast({
                "type":       "prediction",
                "location":   location_name,
                "lat":        lat,
                "lon":        lon,
                "risk_level": prediction["risk_level"],
                "risk_score": prediction["risk_score"],
                "temperature":weather_data.get("temperature"),
                "humidity":   weather_data.get("humidity"),
                "wind_speed": weather_data.get("wind_speed"),
                "probas":     probas if model else None,
            })
        except Exception as ws_err:
            logger.debug("WebSocket broadcast skipped: %s", ws_err)

        response_payload = {
            "status":        "success",
            "location":      {"lat": lat, "lon": lon, "name": location_name},
            "prediction":    prediction,
            "weather":       weather_data,
            "model_used":    model_used,
            "alert_summary": alert_summary,
            "anomalies":     anomalies,
        }
        # Include per-class probabilities if XGBoost model was used
        if model:
            response_payload["probas"] = {
                "LOW":      round(probas[0], 4),
                "MODERATE": round(probas[1], 4),
                "HIGH":     round(probas[2], 4),
                "CRITICAL": round(probas[3], 4),
            }
        # Include LSTM results when available
        if lstm_result:
            response_payload["lstm"] = lstm_result
        return response_payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
@limiter.limit("60/minute")
async def prediction_history(request: Request, limit: int = Query(20, ge=1, le=100)):
    """Get recent predictions from the database"""
    conn = get_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM predictions ORDER BY predicted_at DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        return {"status": "success", "data": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.get("/cache-stats")
async def cache_stats():
    """Return live sizes of all weather API caches (useful for debugging / demo)."""
    from services.cache import weather_cache, forecast_cache, tomorrow_cache
    return {
        "status": "success",
        "cache": {
            "weather_ttl_sec":  300,
            "forecast_ttl_sec": 900,
            "tomorrow_ttl_sec": 600,
            "weather_entries":  weather_cache.size(),
            "forecast_entries": forecast_cache.size(),
            "tomorrow_entries": tomorrow_cache.size(),
        }
    }


@router.get("/model-info")
async def model_info():
    """Return which ML models are currently loaded."""
    xgb_loaded = _model is not None or os.path.exists(MODEL_PATH)
    lstm_loaded = _lstm_model is not None
    lstm_file_exists = os.path.exists(LSTM_MODEL_PATH)
    return {
        "status": "success",
        "models": {
            "xgboost": {
                "loaded":      _model is not None,
                "file_exists": os.path.exists(MODEL_PATH),
            },
            "lstm": {
                "loaded":      lstm_loaded,
                "file_exists": lstm_file_exists,
                "note":        "Run ml/train_lstm.py to generate lstm_model.keras" if not lstm_file_exists else "Ready",
            },
        },
        "active_model": "xgboost_ml+lstm" if lstm_loaded else ("xgboost_ml" if _model is not None else "rule_based"),
    }
