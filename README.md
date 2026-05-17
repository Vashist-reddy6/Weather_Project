<div align="center">

# 🌪️ WeatherGuard AI

### Enterprise-Grade AI Disaster Prediction & Alert System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![XGBoost](https://img.shields.io/badge/XGBoost-ML-orange?style=flat-square)](https://xgboost.ai)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

**Real-time weather risk prediction · SMS + Voice alerts in 4 languages · 3D map · Live WebSocket dashboard**

[Features](#-features) · [Quick Start](#-quick-start) · [API Docs](#-api-reference) · [Architecture](#-architecture) · [Deploy](#-deployment)

</div>

---

## ✨ Features

| Category | Feature |
|---|---|
| 🌦️ **Weather** | Real-time conditions via OpenWeatherMap + hyperlocal data via Tomorrow.io |
| 🛰️ **Historical** | 30-day NASA POWER climate baseline for anomaly detection |
| 🤖 **AI / ML** | XGBoost multi-class risk classifier (LOW / MODERATE / HIGH / CRITICAL) |
| 🗺️ **3D Map** | MapLibre GL with terrain elevation, animated radar-blip risk markers |
| 📡 **Live Feed** | WebSocket dashboard — stat cards auto-refresh every 30 s + on new prediction |
| 📲 **SMS Alerts** | Auto-SMS via Twilio on HIGH/CRITICAL detection; manual broadcast to all operators |
| 🔊 **Voice Alerts** | gTTS voice briefings in English, Hindi, Telugu, Tamil |
| 🧠 **AI Chatbot** | Rule-based safety Q&A engine + optional OpenAI GPT fallback |
| 📊 **Dashboard** | Risk history chart, prediction table, operator table, broadcast console |
| 📝 **Community** | Crowdsourced hazard reports (flooded roads, downed lines, landslides…) |
| 🏕️ **Shelters** | Static resource tracker for 20+ Indian disaster-relief centres |
| 📴 **Offline** | Emergency guide cached by PWA service worker — works without internet |
| 🔐 **Security** | Rate limiting (slowapi), auth-protected admin endpoints, WAL SQLite, XSS escaping |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- Free API keys (see [API Keys](#-api-keys))

### 1 · Clone the repo

```bash
git clone https://github.com/<your-username>/WeatherGuard-AI.git
cd WeatherGuard-AI
```

### 2 · Backend setup

```bash
cd backend
pip install -r requirements.txt

# Copy the env template and fill in your keys
cp .env.example .env
```

Edit `backend/.env`:
```env
OPENWEATHER_API_KEY=your_key_here
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
TOMORROW_IO_API_KEY=your_key_here   # optional — improves rain/wind accuracy
OPENAI_API_KEY=sk-...               # optional — enables GPT chatbot + LLM risk narrative
```

Start the backend:
```bash
python -m uvicorn main:app --reload
# API → http://localhost:8000
# Swagger docs → http://localhost:8000/docs
```

### 3 · Train the ML model *(one-time, recommended)*

```bash
cd ml
python train_unified.py
# Saves ml/disaster_model.pkl — used automatically by the backend
```

> If `disaster_model.pkl` is absent the backend falls back to the built-in rule-based predictor.

### 4 · Frontend setup

```bash
cd frontend
npm install
npm run dev
# App → http://localhost:5173
```

---

## 🔑 API Keys

| Service | Purpose | Free Tier | Link |
|---|---|---|---|
| **OpenWeatherMap** | Real-time weather + geocoding | 1,000 calls/day | [openweathermap.org/api](https://openweathermap.org/api) |
| **Twilio** | SMS disaster alerts | $15 trial credit | [twilio.com](https://www.twilio.com/try-twilio) |
| **Tomorrow.io** | Hyperlocal rain/wind data | 500 calls/day | [tomorrow.io](https://app.tomorrow.io/signup) |
| **OpenAI** *(optional)* | GPT chatbot + LLM risk narrative | Pay-per-use | [platform.openai.com](https://platform.openai.com) |
| **NASA POWER** | 30-day historical climate | ∞ — no key needed | Auto-configured |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                 │
│  Map (MapLibre 3D) · Dashboard · ChatBot · PWA          │
└──────────────────────┬──────────────────────────────────┘
                       │  REST API + WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend                         │
│                                                         │
│  /api/weather   → OpenWeatherMap + Tomorrow.io          │
│  /api/predict   → XGBoost ML → risk score + level       │
│                   ↳ anomaly detection (NASA baseline)   │
│                   ↳ LLM narrative (OpenAI, optional)    │
│                   ↳ auto-SMS on HIGH/CRITICAL           │
│                   ↳ WebSocket broadcast                 │
│  /api/alerts    → Twilio SMS (auth-protected)           │
│  /api/voice     → gTTS MP3 in 4 languages               │
│  /api/chatbot   → rule-based engine + OpenAI fallback   │
│  /api/community → crowdsourced hazard reports           │
│  /api/resources → shelter / medical camp database       │
│  /ws/live       → WebSocket live risk feed              │
│                                                         │
│  SQLite (WAL mode) · slowapi rate limiting · auth JWT   │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    OpenWeatherMap  NASA POWER   Tomorrow.io
```

### Directory Structure

```
WeatherGuard-AI/
├── backend/
│   ├── main.py                  # FastAPI app + router registration
│   ├── database.py              # SQLite helpers (WAL, foreign keys)
│   ├── requirements.txt
│   ├── .env.example             # Key template — copy to .env
│   ├── routers/
│   │   ├── predict.py           # ML risk prediction endpoint
│   │   ├── alerts.py            # SMS alert management (auth-protected)
│   │   ├── auth.py              # PBKDF2 auth + opaque session tokens
│   │   ├── weather.py           # Current + forecast weather
│   │   ├── voice.py             # gTTS voice alert generation
│   │   ├── chatbot.py           # AI Q&A engine
│   │   ├── community.py         # Crowdsourced hazard reports
│   │   ├── resources.py         # Shelter / relief centre data
│   │   ├── ws.py                # WebSocket live feed (max 100 clients)
│   │   └── sms_webhook.py       # Twilio inbound SMS bot (RISK <city>)
│   ├── services/
│   │   ├── openweather.py       # OpenWeatherMap client
│   │   ├── tomorrow_io.py       # Tomorrow.io hyperlocal client
│   │   ├── nasa_power.py        # NASA POWER historical API client
│   │   ├── nlp_summarizer.py    # Alert text generation + LLM assessment
│   │   ├── anomaly_detection.py # 2σ anomaly detection vs. NASA baseline
│   │   └── twilio_service.py    # Twilio SMS helper
│   └── middleware/
│       └── rate_limiter.py      # slowapi limiters (60/min general, 5/15min auth)
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main app shell + sidebar
│   │   ├── Map.jsx              # 3D MapLibre GL map
│   │   ├── Dashboard.jsx        # Live-polling admin dashboard
│   │   ├── ChatBot.jsx          # Floating AI chatbot
│   │   ├── WeatherCharts.jsx    # Recharts forecast visualisation
│   │   ├── HistoricalPanel.jsx  # NASA POWER historical chart
│   │   ├── CommunityReport.jsx  # Hazard report submission + map
│   │   ├── ResourceTracker.jsx  # Shelter finder
│   │   ├── api.js               # Axios client + auth header injection
│   │   └── index.css            # Design system tokens + animations
│   └── public/
│       └── sw.js                # PWA service worker (offline guide)
└── ml/
    ├── train_unified.py         # XGBoost training pipeline
    ├── train.py                 # Alternative training script
    └── download_data.py         # Dataset downloader
```

---

## 📡 API Reference

Full interactive docs available at **`http://localhost:8000/docs`** when the backend is running.

### Public Endpoints (no auth)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/weather/current?lat=&lon=` | Real-time weather for a coordinate |
| `GET` | `/api/weather/forecast?lat=&lon=` | 5-day / 40-point forecast |
| `GET` | `/api/weather/geocode?q=CityName` | City → coordinates |
| `GET` | `/api/predict/risk?lat=&lon=&location_name=` | ML risk prediction + anomalies + LLM narrative |
| `GET` | `/api/predict/history?limit=50` | Recent prediction log |
| `POST` | `/api/alerts/register` | Register a phone number for SMS alerts |
| `GET` | `/api/community/reports` | Get crowdsourced hazard reports |
| `POST` | `/api/community/report` | Submit a hazard report |
| `GET` | `/api/resources/list` | Nearby shelters / medical camps |
| `GET` | `/api/voice/alert?risk_level=&location=&lang=` | MP3 voice alert |
| `POST` | `/api/chatbot/message` | AI safety Q&A |
| `WS` | `/ws/live` | Real-time risk event feed |

### Protected Endpoints (require `Authorization: Bearer <token>`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/alerts/users` | List all registered operators |
| `POST` | `/api/alerts/send` | Send SMS to a specific user |
| `POST` | `/api/alerts/broadcast` | Broadcast SMS to all operators |
| `GET` | `/api/alerts/history` | Alert send history |
| `DELETE` | `/api/community/report/{id}` | Delete a hazard report (admin) |

### Auth Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create operator account |
| `POST` | `/api/auth/login` | Get session token |
| `POST` | `/api/auth/logout` | Invalidate token |

---

## 📲 SMS Bot

Text commands to your Twilio number (configure the inbound webhook to `/api/sms/inbound`):

| Command | Response |
|---|---|
| `RISK <city>` | Current risk level + nearest shelter |
| `HELP` | Usage instructions |
| `STATUS` | System status |

**Example:** `RISK HYDERABAD` → `🟠 HIGH risk in Hyderabad. T:34C W:12m/s R:8mm. Shelter:Gandhi Nagar Community Hall. Emergency:112`

Works on **any phone without internet** — SMS-only mode.

---

## 🔐 Security

| Protection | Implementation |
|---|---|
| Rate limiting | slowapi — 60 req/min general, 5 req/15 min for auth |
| Admin endpoints | Bearer token auth via `Depends(get_current_user)` |
| Password hashing | PBKDF2-HMAC-SHA256, 260,000 iterations, random salt |
| SQL injection | 100% parameterised queries — no string concatenation |
| XSS | HTML escaping on all user-controlled values in map popups |
| Input validation | Pydantic models with `Literal` enums, `Field` bounds |
| Secrets | `.env` excluded from git; no secrets in source code |
| DB integrity | WAL journal mode + `foreign_keys=ON` on every connection |
| WebSocket DoS | Hard cap of 100 concurrent clients |
| TTS injection | Location strings stripped of control characters before synthesis |
| Mock/override endpoints | Gated behind ALLOW_MOCK env var — disabled in production |

---

## 🌐 Deployment

### Frontend → Vercel

```bash
cd frontend
npm run build
# Upload the dist/ folder to Vercel, or connect your GitHub repo directly
```

Set the `VITE_API_URL` env var in Vercel to point to your deployed backend.

### Backend → Render (free tier)

1. Create a new **Web Service** on [render.com](https://render.com)
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add your API keys under **Environment Variables**

### Backend → Railway

```bash
railway login
railway init
railway up
# Set env vars in Railway dashboard
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: describe your change"`
4. Push and open a Pull Request

Please make sure:
- No API keys or `.env` files are included
- New endpoints follow the existing Pydantic + rate-limiter pattern
- Frontend changes maintain the existing dark-mode design system

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for disaster preparedness · Powered by XGBoost, FastAPI, React & MapLibre GL

**Emergency (India): 112 | NDMA Helpline: 1078 | Ambulance: 108**

</div>
