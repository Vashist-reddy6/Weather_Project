import axios from 'axios';

const API = axios.create({
  baseURL: '/api',
  timeout: 60000,   // 60 s — predict/risk can take 15-30 s on cold API calls
});

// ---------------------------------------------------------------------------
// Global response interceptor — handles common HTTP errors in one place
// ---------------------------------------------------------------------------
API.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    if (status === 401) {
      // Clear stale token and let the app redirect to login
      localStorage.removeItem('wg_token');
      window.dispatchEvent(new CustomEvent('wg:unauthorized'));
    } else if (status === 429) {
      console.warn('WeatherGuard: rate limit hit, back off and retry.');
    } else if (status >= 500) {
      console.error('WeatherGuard: server error', error.response?.data?.detail ?? error.message);
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Attach the session token to outgoing requests when available. */
export function setAuthToken(token) {
  if (token) {
    API.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete API.defaults.headers.common['Authorization'];
  }
}

// ---------------------------------------------------------------------------
// Weather
// ---------------------------------------------------------------------------
export const getWeather    = (lat, lon)            => API.get(`/weather/current?lat=${lat}&lon=${lon}`);
export const getForecast   = (lat, lon)            => API.get(`/weather/forecast?lat=${lat}&lon=${lon}`);
export const getHistorical = (lat, lon, days = 30) => API.get(`/weather/historical?lat=${lat}&lon=${lon}&days=${days}`);
export const getGeocode    = (city)                => API.get(`/weather/geocode?q=${encodeURIComponent(city)}`);

// ---------------------------------------------------------------------------
// Predict
// ---------------------------------------------------------------------------
export const getRiskPrediction    = (lat, lon, name = 'Unknown') =>
  API.get(`/predict/risk?lat=${lat}&lon=${lon}&location_name=${encodeURIComponent(name)}`);
export const getPredictionHistory = (limit = 20) => API.get(`/predict/history?limit=${limit}`);

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------
export const registerUser  = (data)                     => API.post('/alerts/register', data);
export const getUsers      = ()                         => API.get('/alerts/users');
export const sendAlert     = (data)                     => API.post('/alerts/send', data);

/**
 * Broadcast alert — sends JSON body so credentials are never in the URL /
 * server access logs (matches the updated backend BroadcastAlert schema).
 */
export const broadcastAlert = (riskLevel, location, desc) =>
  API.post('/alerts/broadcast', {
    risk_level:          riskLevel,
    location:            location,
    weather_description: desc,
  });

// ---------------------------------------------------------------------------
// Voice
// ---------------------------------------------------------------------------
export const getVoiceAlert = (riskLevel, location, lang = 'en') =>
  API.get(`/voice/alert?risk_level=${encodeURIComponent(riskLevel)}&location=${encodeURIComponent(location)}&lang=${lang}`, {
    responseType: 'blob',
  });

// ---------------------------------------------------------------------------
// Community Reports
// ---------------------------------------------------------------------------
export const submitCommunityReport = (data)                   => API.post('/community/report', data);
export const getCommunityReports   = (lat, lon, radiusKm=300) =>
  API.get(`/community/reports${lat ? `?lat=${lat}&lon=${lon}&radius_km=${radiusKm}&limit=50` : '?limit=50'}`);

// ---------------------------------------------------------------------------
// AI Chatbot
// ---------------------------------------------------------------------------
export const sendChatMessage = (message, context = {}) =>
  API.post('/chatbot/message', { message, context });

// ---------------------------------------------------------------------------
// Resource Tracker
// ---------------------------------------------------------------------------
export const getResources = (lat, lon, type = null, radiusKm = 600) => {
  const p = new URLSearchParams();
  if (lat)  { p.set('lat', lat); p.set('lon', lon); p.set('radius_km', radiusKm); }
  if (type)   p.set('resource_type', type);
  return API.get(`/resources/list?${p}`);
};

// ---------------------------------------------------------------------------
// Auth helpers — token is sent via Authorization header, never as a query param
// ---------------------------------------------------------------------------
export const authLogin    = (email, password) => API.post('/auth/login',    { email, password });
export const authRegister = (name, email, password) => API.post('/auth/register', { name, email, password });
export const logout = () => API.post('/auth/logout');  // token injected by setAuthToken

export default API;
