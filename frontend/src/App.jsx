import { useState, useEffect, useRef, useCallback } from 'react';
import Map from './Map';
import Dashboard from './Dashboard';
import HistoricalPanel from './HistoricalPanel';
import WeatherCharts from './WeatherCharts';
import ChatBot from './ChatBot';
import CommunityReport from './CommunityReport';
import ResourceTracker from './ResourceTracker';
import { getWeather, getForecast, getRiskPrediction, registerUser, getVoiceAlert, getGeocode } from './api';
import './index.css';

const RISK_COLORS = { LOW: '#22c55e', MODERATE: '#e8c426', HIGH: '#f97316', CRITICAL: '#ef4444' };
const VOICE_LANGS = [
  { code: 'en', label: 'EN' },
  { code: 'hi', label: 'HI' },
  { code: 'te', label: 'TE' },
  { code: 'ta', label: 'TA' },
];

/* ── Probability Breakdown Bar ── */
const RISK_LEVELS_ORDER = ['LOW', 'MODERATE', 'HIGH', 'CRITICAL'];
const PROBA_COLORS = { LOW: '#22c55e', MODERATE: '#e8c426', HIGH: '#f97316', CRITICAL: '#ef4444' };

function ProbabilityBar({ probas }) {
  if (!probas) return null;
  return (
    <div style={{ marginTop: '1.2rem' }}>
      <div style={{ fontSize: '0.9rem', color: 'var(--on-surface)', fontWeight: 600, marginBottom: '0.8rem' }}>Risk Probability Breakdown</div>
      {RISK_LEVELS_ORDER.map(lvl => {
        const pct = Math.round((probas[lvl] || 0) * 100);
        return (
          <div key={lvl} style={{ marginBottom: '0.4rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
              <span style={{ fontSize: '0.8rem', color: PROBA_COLORS[lvl], fontWeight: 600 }}>{lvl}</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--on-surface)', fontWeight: 500 }}>{pct}%</span>
            </div>
            <div style={{ height: 5, background: 'rgba(255,255,255,0.05)', borderRadius: 99 }}>
              <div style={{ height: '100%', width: `${pct}%`, background: PROBA_COLORS[lvl], borderRadius: 99, boxShadow: `0 0 8px ${PROBA_COLORS[lvl]}66`, transition: 'width 0.8s ease' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Risk Gauge ── */
function RiskCircle({ score, level }) {
  const c = RISK_COLORS[level] || '#94a3b8';
  const pct = Math.round(score * 100);
  const r = 42, circ = 2 * Math.PI * r;
  const dash = circ - (pct / 100) * circ;
  return (
    <div className="risk-gauge">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={c} strokeWidth="6"
          strokeDasharray={circ} strokeDashoffset={dash}
          strokeLinecap="round" transform="rotate(-90 50 50)"
          style={{ transition: 'stroke-dashoffset 0.8s ease', filter: `drop-shadow(0 0 6px ${c}88)` }}
        />
        <text x="50" y="45" textAnchor="middle" fill={c} fontSize="18" fontWeight="700" fontFamily="JetBrains Mono">{pct}</text>
        <text x="50" y="60" textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize="9" fontFamily="JetBrains Mono">/ 100</text>
      </svg>
    </div>
  );
}

/* ── Toast ── */
function Toast({ toast }) {
  if (!toast) return null;
  const styles = {
    error:   { background: 'rgba(239,68,68,0.12)',   border: '1px solid rgba(239,68,68,0.35)',   boxShadow: '0 0 20px rgba(239,68,68,0.2)' },
    success: { background: 'rgba(34,197,94,0.12)',   border: '1px solid rgba(34,197,94,0.35)',   boxShadow: '0 0 20px rgba(34,197,94,0.2)' },
    info:    { background: 'rgba(111,246,255,0.08)', border: '1px solid rgba(111,246,255,0.25)', boxShadow: '0 0 20px rgba(111,246,255,0.15)' },
  };
  return (
    <div className="toast" style={styles[toast.type] || styles.info}>
      {toast.msg}
    </div>
  );
}

/* ── Divider ── */
const Div = () => <div style={{ height: 1, background: 'rgba(111,246,255,0.06)', margin: '0.25rem 0' }} />;

export default function App() {
  const [view, setView]         = useState('map');
  const [tab, setTab]           = useState('analyze');
  const [loading, setLoading]   = useState(false);
  const [weather, setWeather]   = useState(null);
  const [forecast, setForecast] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [markers, setMarkers]   = useState([]);
  const [searchLat, setSearchLat] = useState('');
  const [searchLon, setSearchLon] = useState('');
  const [searchCity, setSearchCity] = useState('');
  const [toast, setToast]       = useState(null);
  const [voiceLang, setVoiceLang] = useState('en');
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [isPlayingVoice, setIsPlayingVoice] = useState(false);
  const audioRef = useRef(null);
  const [form, setForm]         = useState({ name: '', phone: '', email: '', lat: '', lon: '', locationName: '' });
  const [regStatus, setRegStatus] = useState('');
  const [geoLoading, setGeoLoading] = useState(false);
  const autoRefreshRef = useRef(null);
  const lastAnalyzedRef = useRef(null);

  const showToast = (msg, type = 'info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const analyze = async (lat, lon, name = 'Selected Location') => {
    setLoading(true); setView('map');
    try {
      const [wRes, fRes, pRes] = await Promise.all([
        getWeather(lat, lon), getForecast(lat, lon), getRiskPrediction(lat, lon, name),
      ]);
      setWeather(wRes.data.data);
      setForecast(fRes.data.data.slice(0, 8));
      setPrediction(pRes.data);
      const p = pRes.data;
      lastAnalyzedRef.current = { lat, lon, name };
      setMarkers(prev => {
        const filtered = prev.filter(m => !(Math.abs(m.lat - lat) < 0.01 && Math.abs(m.lon - lon) < 0.01));
        return [...filtered, { lat, lon, name, risk_level: p.prediction.risk_level, risk_score: p.prediction.risk_score, temperature: p.weather.temperature, humidity: p.weather.humidity, wind_speed: p.weather.wind_speed }];
      });
      setTab('analyze');
      // Auto-fill registration location when a scan completes
      setForm(prev => ({
        ...prev,
        lat: lat.toFixed(4),
        lon: lon.toFixed(4),
        locationName: p.weather?.city_name || name,
      }));
      showToast(`${p.prediction.risk_level} RISK — ${p.weather.city_name || name}`, 'success');
    } catch (err) {
      showToast(err.response?.data?.detail || 'API error — check backend & API key', 'error');
    } finally { setLoading(false); }
  };

  /* ── 10-minute silent auto-refresh ── */
  useEffect(() => {
    const interval = setInterval(() => {
      if (lastAnalyzedRef.current && !loading) {
        const { lat, lon, name } = lastAnalyzedRef.current;
        analyze(lat, lon, name);
      }
    }, 10 * 60 * 1000); // 10 minutes
    autoRefreshRef.current = interval;
    return () => clearInterval(interval);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── My Location ── */
  const handleMyLocation = () => {
    if (!navigator.geolocation) { showToast('Geolocation not supported', 'error'); return; }
    setGeoLoading(true);
    navigator.geolocation.getCurrentPosition(
      pos => {
        const { latitude: lat, longitude: lon } = pos.coords;
        setSearchLat(lat.toFixed(4));
        setSearchLon(lon.toFixed(4));
        analyze(lat, lon, 'My Location');
        setGeoLoading(false);
      },
      () => { showToast('Location access denied', 'error'); setGeoLoading(false); },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };


  const handleSearch = () => {
    const lat = parseFloat(searchLat), lon = parseFloat(searchLon);
    if (isNaN(lat) || isNaN(lon)) { showToast('Enter valid coordinates', 'error'); return; }
    analyze(lat, lon, `${lat.toFixed(3)}, ${lon.toFixed(3)}`);
  };

  const handleCitySearch = async () => {
    if (!searchCity.trim()) return;
    setLoading(true);
    try {
      const res = await getGeocode(searchCity);
      const data = res.data.data;
      setSearchLat(data.lat.toFixed(4));
      setSearchLon(data.lon.toFixed(4));
      analyze(data.lat, data.lon, data.name);
    } catch (err) {
      showToast(err.response?.data?.detail || 'City not found', 'error');
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    // Use prediction location if available, fall back to manual lat/lon
    const lat  = prediction ? prediction.location.lat  : parseFloat(form.lat);
    const lon  = prediction ? prediction.location.lon  : parseFloat(form.lon);
    const locName = prediction ? prediction.location.name : (form.locationName.trim() || 'Unknown');
    if (isNaN(lat) || isNaN(lon)) {
      setRegStatus('ERR — Enter valid coordinates or scan a location first');
      return;
    }
    try {
      const payload = {
        name:          form.name,
        phone:         form.phone,
        email:         form.email.trim() || null,
        latitude:      lat,
        longitude:     lon,
        location_name: locName,
      };
      await registerUser(payload);
      setRegStatus('OK — Registered for SMS alerts');
      setForm({ name: '', phone: '', email: '', lat: '', lon: '', locationName: '' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setRegStatus(`ERR — ${Array.isArray(detail) ? detail[0]?.msg : (detail || 'Registration failed')}`);
    }
  };

  const handleVoiceAlert = async () => {
    if (isPlayingVoice && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      setIsPlayingVoice(false);
      return;
    }

    if (!prediction) { showToast('Analyze a location first', 'error'); return; }
    setVoiceLoading(true);
    try {
      const res = await getVoiceAlert(prediction.prediction.risk_level, prediction.location.name, voiceLang);
      const url = URL.createObjectURL(new Blob([res.data], { type: 'audio/mpeg' }));
      const audio = new Audio(url);
      audioRef.current = audio;
      
      audio.onended = () => {
        setIsPlayingVoice(false);
        URL.revokeObjectURL(url);
      };
      
      audio.play();
      setIsPlayingVoice(true);
      showToast('PLAYING VOICE ALERT', 'info');
    } catch { showToast('Voice alert unavailable — install gTTS on backend', 'error'); }
    finally { setVoiceLoading(false); }
  };

  const riskColor = prediction ? RISK_COLORS[prediction.prediction.risk_level] : null;

  return (
    <div className="app">
      <Toast toast={toast} />

      {/* ── Header ── */}
      <header className="header">
        <div className="header-logo" onClick={() => setView('map')}>
          <div className="header-logo-mark">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.5 19C19.433 19 21 17.433 21 15.5C21 13.567 19.433 12 17.5 12C17.26 12 17.027 12.024 16.804 12.069C16.326 9.206 13.882 7 10.875 7C7.632 7 5 9.632 5 12.875C5 13.045 5.007 13.212 5.021 13.376C3.308 13.834 2 15.424 2 17.333C2 19.542 3.791 21.333 6 21.333H17.5Z"/><path d="M12 12V21"/><path d="M8 16L12 12L16 16"/></svg>
          </div>
          <div>
            <h1>WeatherGuard</h1>
            <p>AI Disaster Engine</p>
          </div>
        </div>

        <nav className="header-nav">
          {[['map','Map'],['dashboard','Dashboard'],['guide','Emergency']].map(([v, l]) => (
            <button key={v} className={`nav-btn ${view === v ? 'active' : ''}`} onClick={() => setView(v)}>{l}</button>
          ))}
        </nav>

        <div className="header-right">
          <div className="system-status">
            <div className="status-dot" />
            ONLINE
          </div>
        </div>
      </header>

      {/* ── DASHBOARD ── */}
      {view === 'dashboard' && (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <Dashboard />
        </div>
      )}

      {/* ── EMERGENCY GUIDE ── */}
      {view === 'guide' && <EmergencyGuide />}

      {/* ── MAP VIEW ── */}
      {view === 'map' && (
        <div className="main">
          {/* Sidebar */}
          <aside className="sidebar">
            <div className="tabs" style={{ flexWrap: 'wrap', gap: '4px' }}>
              {[['analyze','Scan'],['forecast','Forecast'],['historical','NASA'],['community','Reports'],['resources','Shelters'],['register','Alerts']].map(([t, l]) => (
                <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{l}</button>
              ))}
            </div>
            <div className="sidebar-content">

            {/* ── ANALYZE ── */}
            {tab === 'analyze' && (
              <>
                <div className="card">
                  <div className="card-title">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
                    Scanning Sector
                  </div>
                  <div className="search-row" style={{ marginBottom: '0.5rem' }}>
                    <input className="input" placeholder="Search by city name..." value={searchCity} onChange={e => setSearchCity(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleCitySearch()} style={{ width: '100%' }} />
                    <button className="btn btn-outline" onClick={handleCitySearch} disabled={loading} style={{ padding: '0 1rem' }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                    </button>
                  </div>
                  
                  <div className="search-row" style={{ marginTop: '1.75rem', marginBottom: '1rem', position: 'relative' }}>
                    <div style={{ position: 'absolute', top: '-11px', left: '50%', transform: 'translateX(-50%)', background: 'var(--surface-card)', padding: '0 0.75rem', fontSize: '0.8rem', color: 'var(--on-muted)', fontWeight: 600, zIndex: 1, whiteSpace: 'nowrap' }}>OR ENTER COORDS</div>
                    <div style={{ height: '1px', background: 'var(--outline)', width: '100%', position: 'absolute', top: '0', zIndex: 0 }} />
                    <div style={{ display: 'flex', gap: '0.5rem', width: '100%', marginTop: '0.75rem' }}>
                      <input className="input" placeholder="Latitude" value={searchLat} onChange={e => setSearchLat(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} style={{ flex: 1, minWidth: 0, boxSizing: 'border-box' }} />
                      <input className="input" placeholder="Longitude" value={searchLon} onChange={e => setSearchLon(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()} style={{ flex: 1, minWidth: 0, boxSizing: 'border-box' }} />
                    </div>
                  </div>
                  
                  <button className="btn btn-primary" style={{ width: '100%', marginBottom: '0.6rem' }} onClick={handleSearch} disabled={loading}>
                    {loading ? 'Scanning...' : 'Analyze Risk'}
                  </button>
                  <button
                    id="my-location-btn"
                    className="btn btn-outline"
                    style={{ width: '100%', marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                    onClick={handleMyLocation}
                    disabled={geoLoading || loading}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/></svg>
                    {geoLoading ? 'Locating...' : 'My Location'}
                  </button>
                  <div className="quick-locations">
                    {[['Mumbai',19.07,72.87],['Chennai',13.08,80.27],['Kolkata',22.57,88.36],['Delhi',28.61,77.20]].map(([name, lat, lon]) => (
                      <button key={name} className="quick-loc-btn" onClick={() => analyze(lat, lon, name)}>{name}</button>
                    ))}
                  </div>
                </div>

                {/* Risk Result */}
                {prediction ? (
                  <div className="card risk-panel">
                    {/* ── Row: Gauge + Info ── */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <RiskCircle score={prediction.prediction.risk_score} level={prediction.prediction.risk_level} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="card-title" style={{ marginBottom: '0.3rem', fontSize: '0.85rem' }}>AI Threat Matrix</div>
                        <span className={`risk-badge risk-${prediction.prediction.risk_level}`} style={{ marginBottom: '0.4rem', display: 'inline-block', fontSize: '0.85rem', padding: '0.35rem 0.85rem' }}>
                          {prediction.prediction.risk_level}
                        </span>
                        <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fff', marginBottom: '0.2rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {weather?.city_name}{weather?.country ? `, ${weather.country}` : ''}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--on-muted)' }}>
                          Model: {prediction.model_used?.replace('_', ' ')}
                        </div>
                      </div>
                    </div>

                    {/* Probability breakdown bars */}
                    <ProbabilityBar probas={prediction.probas} />

                    <Div />

                    {/* LLM Narrative — FRONT AND CENTER */}
                    {prediction.prediction?.llm_alert_summary && (
                      <div style={{ padding: '1rem', background: 'var(--surface-hover)', border: '1px solid var(--outline)', borderRadius: 12, marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--on-surface)" strokeWidth="2"><path d="M12 2a2 2 0 0 1 2 2v2.2a9.96 9.96 0 0 1 6.8 6.8h2.2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2h-2.2a9.96 9.96 0 0 1-6.8 6.8v2.2a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.2a9.96 9.96 0 0 1-6.8-6.8H2a2 2 0 0 1-2-2v-2a2 2 0 0 1 2-2h2.2A9.96 9.96 0 0 1 10 6.2V4a2 2 0 0 1 2-2h4z"/></svg>
                          <span style={{ fontSize: '0.8rem', color: 'var(--on-surface)', fontWeight: 600 }}>AI Intelligence</span>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--on-muted)', lineHeight: 1.6 }}>{prediction.prediction.llm_alert_summary}</div>
                        {prediction.prediction.llm_risk_level && (
                          <div style={{ marginTop: '0.8rem', fontSize: '0.75rem', color: 'var(--on-muted)' }}>
                            LLM Verdict: <span style={{ color: RISK_COLORS[prediction.prediction.llm_risk_level] || '#fff', fontWeight: 600 }}>{prediction.prediction.llm_risk_level}</span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* NLP Alert Summary */}
                    {prediction.alert_summary && (
                      <div style={{ padding: '1rem', background: 'var(--surface)', border: '1px solid var(--outline)', borderRadius: 12, marginBottom: '1rem' }}>
                        <div style={{ fontSize: '0.8rem', color: 'var(--on-surface)', fontWeight: 600, marginBottom: '0.5rem' }}>AI Alert Summary</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--on-muted)', lineHeight: 1.6 }}>{prediction.alert_summary}</div>
                      </div>
                    )}

                    {/* Anomalies — pulsing when detected */}
                    {prediction.anomalies?.length > 0 && (
                      <div style={{ marginTop: '1rem', marginBottom: '1rem' }}>
                        <div style={{ fontSize: '0.8rem', color: 'var(--risk-critical)', fontWeight: 600, marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span className="anomaly-pulse-dot" />
                          Anomalies Detected ({prediction.anomalies.length})
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {prediction.anomalies.map((a, i) => (
                            <div key={i} className="anomaly-item" style={{ background: 'var(--surface-hover)', border: '1px solid var(--outline)', padding: '0.75rem', borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.8rem', color: 'var(--on-surface)' }}>{a.parameter}</span>
                              <span style={{ fontSize: '0.8rem', color: 'var(--risk-critical)', fontWeight: 600 }}>{a.current_value} ({a.direction} avg)</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <Div />

                    {/* Voice Alert — compact row */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                      <div style={{ fontSize: '0.6rem', color: 'var(--on-muted)', fontFamily: 'JetBrains Mono', flexShrink: 0 }}>VOICE:</div>
                      {VOICE_LANGS.map(l => (
                        <button key={l.code} className={`btn btn-sm ${voiceLang === l.code ? 'btn-primary' : 'btn-outline'}`} onClick={() => setVoiceLang(l.code)} style={{ padding: '0.3rem 0.6rem', fontSize: '0.7rem' }}>
                          {l.label}
                        </button>
                      ))}
                      <button className={`btn btn-sm ${isPlayingVoice ? 'btn-primary' : 'btn-outline'}`} style={{ marginLeft: 'auto', fontSize: '0.72rem' }} onClick={handleVoiceAlert} disabled={voiceLoading}>
                        {voiceLoading ? '...' : (isPlayingVoice ? '⏹ Stop' : '▶ Play')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="card empty-state">
                    <div className="icon">
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                    </div>
                    <p>Select a location on the map or enter coordinates to begin AI risk analysis</p>
                  </div>
                )}

                {/* Weather Stats */}
                {weather && (
                  <div className="card">
                    <div className="card-title">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v3"/><path d="M12 18v3"/><path d="M4.22 4.22l2.12 2.12"/><path d="M17.66 17.66l2.12 2.12"/><path d="M3 12h3"/><path d="M18 12h3"/><path d="M4.22 19.78l2.12-2.12"/><path d="M17.66 6.34l2.12-2.12"/><circle cx="12" cy="12" r="5"/></svg>
                      Live Conditions
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', margin: '0.5rem 0 1rem' }}>
                      <img src={`https://openweathermap.org/img/wn/${weather.weather_icon}@2x.png`} alt={weather.weather_description} style={{ width: 48, height: 48, filter: 'drop-shadow(0 0 8px rgba(255,255,255,0.2))' }} />
                      <span style={{ color: '#fff', fontSize: '0.9rem', fontWeight: 600, textTransform: 'capitalize' }}>
                        {weather.weather_description}
                      </span>
                    </div>
                    <div className="stats-grid">
                      {[
                        ['Temp',     `${weather.temperature}`, '°C'],
                        ['Feels',    `${weather.feels_like}`,  '°C'],
                        ['Humidity', `${weather.humidity}`,    '%'],
                        ['Wind',     `${weather.wind_speed}`,  'm/s'],
                        ['Pressure', `${weather.pressure}`,    'hPa'],
                        ['Rain 1h',  `${weather.rainfall_1h}`, 'mm'],
                      ].map(([label, val, unit]) => (
                        <div className="stat-item" key={label}>
                          <span className="stat-label">{label}</span>
                          <span className="stat-value">{val}<span className="stat-unit">{unit}</span></span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* ── FORECAST ── */}
            {tab === 'forecast' && (
              <WeatherCharts forecast={forecast} />
            )}

            {/* ── COMMUNITY ── */}
            {tab === 'community' && (
              <CommunityReport lat={prediction?.location?.lat} lon={prediction?.location?.lon} />
            )}

            {/* ── RESOURCES ── */}
            {tab === 'resources' && (
              <ResourceTracker lat={prediction?.location?.lat} lon={prediction?.location?.lon} />
            )}

            {/* ── NASA HISTORICAL ── */}
            {tab === 'historical' && (
              <HistoricalPanel lat={prediction?.location?.lat} lon={prediction?.location?.lon} />
            )}

            {tab === 'register' && (
              <div className="card">
                <div className="card-title">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                  Register For Alerts
                </div>
                <form onSubmit={handleRegister}>
                  {[
                    ['name',  'Operator Name',        'text',  'Full Name',      true],
                    ['phone', 'Phone (with code)',     'tel',   '+91XXXXXXXXXX',  true],
                    ['email', 'Email (optional)',      'email', 'you@example.com',false],
                  ].map(([field, label, type, placeholder, required]) => (
                    <div className="form-group" key={field}>
                      <label className="form-label">{label}</label>
                      <input
                        className="input" type={type} placeholder={placeholder}
                        value={form[field]}
                        onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
                        required={required}
                      />
                    </div>
                  ))}

                  {/* Location — auto-filled from scan or manual entry */}
                  {prediction ? (
                    <div style={{ fontSize: '0.65rem', color: 'var(--cyan)', marginBottom: '1rem', fontFamily: 'JetBrains Mono', background: 'rgba(0,240,255,0.05)', borderRadius: 8, padding: '0.6rem', border: '1px solid rgba(0,240,255,0.1)' }}>
                      TARGET ZONE: {prediction.location.name}
                    </div>
                  ) : (
                    <>
                      <div style={{ fontSize: '0.65rem', color: 'var(--on-muted)', marginBottom: '0.5rem', fontFamily: 'JetBrains Mono' }}>
                        No scan active — enter coordinates manually:
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                          <label className="form-label">Latitude</label>
                          <input className="input" type="number" step="any" placeholder="e.g. 19.07"
                            value={form.lat} onChange={e => setForm(p => ({ ...p, lat: e.target.value }))} required />
                        </div>
                        <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
                          <label className="form-label">Longitude</label>
                          <input className="input" type="number" step="any" placeholder="e.g. 72.87"
                            value={form.lon} onChange={e => setForm(p => ({ ...p, lon: e.target.value }))} required />
                        </div>
                      </div>
                      <div className="form-group" style={{ marginBottom: '0.5rem' }}>
                        <label className="form-label">Location Name (optional)</label>
                        <input className="input" type="text" placeholder="e.g. Mumbai"
                          value={form.locationName} onChange={e => setForm(p => ({ ...p, locationName: e.target.value }))} />
                      </div>
                    </>
                  )}

                  <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>
                    Register Operator
                  </button>
                  {regStatus && (
                    <p style={{ marginTop: '0.8rem', fontSize: '0.7rem', textAlign: 'center', fontFamily: 'JetBrains Mono', color: regStatus.startsWith('OK') ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
                      {regStatus}
                    </p>
                  )}
                </form>
              </div>
            )}
            </div> {/* end sidebar-content */}
          </aside>

          {/* Map */}
          <Map markers={markers} onMapClick={analyze} loading={loading} />
        </div>
      )}

      {/* AI ChatBot (Floating) */}
      <ChatBot predictionContext={prediction} />
    </div>
  );
}

/* ── Emergency Guide ── */
function EmergencyGuide() {
  const guides = [
    {
      code: 'FLD', title: 'Flood Emergency', color: '#3b82f6',
      steps: [
        'Move immediately to higher ground — do not wait for instructions.',
        'Avoid walking or driving through flood waters (15cm can knock you over).',
        'Disconnect electrical appliances and avoid contact with floodwater.',
        'Follow evacuation orders from local authorities immediately.',
        'Store emergency kit: water (3L/person/day), food, torch, medicines.',
        'Emergency: 112 (India) | 911 (USA) | 999 (UK)',
      ],
      safeZones: ['School buildings (upper floors)', 'Community halls', 'High-ground structures', 'Government relief camps'],
    },
    {
      code: 'CYC', title: 'Cyclone / Hurricane', color: '#8b5cf6',
      steps: [
        'Stay indoors, away from windows and glass doors.',
        'Move to the innermost room on the lowest floor.',
        'Do not go outside during the eye of the storm — it will return.',
        'Secure loose outdoor items before it hits.',
        'Charge devices and fill bathtubs before power cuts.',
        'Monitor NDMA alerts: ndma.gov.in or local radio.',
      ],
      safeZones: ['Concrete cyclone shelters', 'Reinforced community buildings', 'Government schools', 'Hospitals'],
    },
    {
      code: 'HWT', title: 'Heatwave Emergency', color: '#f97316',
      steps: [
        'Stay indoors between 12 PM – 4 PM (peak heat hours).',
        'Drink water every 20 minutes — do not wait until thirsty.',
        'Wear loose, light-colored, cotton clothing.',
        'Never leave children or elderly in parked vehicles.',
        'Heat stroke signs: hot skin, confusion, no sweating — call 108.',
        'Use ORS if experiencing dehydration.',
      ],
      safeZones: ['Air-conditioned malls / libraries', 'Community cooling centers', 'Hospitals', 'Shaded water bodies'],
    },
    {
      code: 'THN', title: 'Thunderstorm Safety', color: '#e8c426',
      steps: [
        'Seek shelter in a substantial building or hard-topped vehicle.',
        'Avoid open fields, hilltops, and isolated trees.',
        'Stay away from tall objects and metal structures.',
        'Unplug sensitive electronics to protect from power surges.',
        'Wait 30 minutes after the last thunder before going outside.',
      ],
      safeZones: ['Concrete buildings', 'Vehicles (not convertibles)', 'Low-lying areas away from trees'],
    },
    {
      code: 'SOS', title: 'Emergency Contacts', color: '#ef4444',
      steps: [],
      contacts: [
        { label: 'India Emergency', number: '112' },
        { label: 'Ambulance (India)', number: '108' },
        { label: 'NDMA Helpline', number: '1078' },
        { label: 'Police', number: '100' },
        { label: 'Fire Brigade', number: '101' },
        { label: 'Disaster Helpline', number: '1070' },
      ],
    },
  ];

  const [open, setOpen] = useState(0);

  return (
    <div className="guide-wrap">
      <div className="guide-inner">
        <div style={{ marginBottom: '2rem', textAlign: 'center' }}>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--on-surface)' }}>
            Emergency Preparedness Guide
          </h2>
          <p style={{ color: 'var(--on-muted)', fontSize: '0.85rem' }}>
            Works <strong style={{ color: '#fff' }}>offline</strong> — safety information always available
          </p>
        </div>

        {guides.map((g, i) => (
          <div key={i} className="card" style={{ marginBottom: '1rem', padding: '0', overflow: 'hidden' }}>
            <button
              style={{ width: '100%', background: open === i ? 'rgba(255,255,255,0.02)' : 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.25rem', color: '#fff' }}
              onClick={() => setOpen(open === i ? -1 : i)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.75rem', color: `${g.color}`, background: `${g.color}15`, padding: '0.4rem 0.6rem', borderRadius: 6, border: `1px solid ${g.color}30` }}>
                  {g.code}
                </span>
                <span style={{ fontWeight: 600, fontSize: '1rem', color: g.color }}>{g.title.replace('_', ' ')}</span>
              </div>
              <span style={{ color: 'var(--on-muted)' }}>
                {open === i ? <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 15l-6-6-6 6"/></svg> : <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6"/></svg>}
              </span>
            </button>

            {open === i && (
              <div style={{ marginTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1rem' }}>
                {g.steps.length > 0 && (
                  <>
                    <div style={{ fontWeight: 600, fontSize: '0.58rem', color: 'rgba(185,202,203,0.3)', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '0.75rem', fontFamily: 'JetBrains Mono' }}>
                      ▸ ACTION_STEPS
                    </div>
                    <ol style={{ paddingLeft: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {g.steps.map((s, j) => (
                        <li key={j} style={{ color: 'var(--on-muted)', fontSize: '0.8rem', lineHeight: 1.65 }}>{s}</li>
                      ))}
                    </ol>
                  </>
                )}

                {g.safeZones && (
                  <div style={{ marginTop: '1rem' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.58rem', color: 'rgba(185,202,203,0.3)', textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: '0.5rem', fontFamily: 'JetBrains Mono' }}>
                      ▸ SAFE_ZONES
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {g.safeZones.map((z, j) => (
                        <span key={j} style={{ background: `${g.color}10`, border: `1px solid ${g.color}25`, borderRadius: 999, padding: '0.25rem 0.65rem', fontSize: '0.7rem', color: g.color, fontFamily: 'JetBrains Mono' }}>
                          {z}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {g.contacts && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginTop: '0.75rem' }}>
                    {g.contacts.map((c, j) => (
                      <a key={j} href={`tel:${c.number}`}
                        style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--outline)', borderRadius: 8, padding: '0.65rem', display: 'flex', flexDirection: 'column', gap: '0.1rem', textDecoration: 'none', transition: 'all 0.2s' }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = g.color; e.currentTarget.style.background = `${g.color}08`; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--outline)'; e.currentTarget.style.background = 'rgba(0,0,0,0.3)'; }}
                      >
                        <span style={{ color: 'rgba(185,202,203,0.35)', fontSize: '0.6rem', fontFamily: 'JetBrains Mono', letterSpacing: '0.08em' }}>{c.label}</span>
                        <span style={{ color: g.color, fontSize: '1.25rem', fontWeight: 700, fontFamily: 'JetBrains Mono' }}>{c.number}</span>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: 'rgba(111,246,255,0.04)', border: '1px solid rgba(111,246,255,0.1)', borderRadius: 10, textAlign: 'center', fontSize: '0.65rem', color: 'rgba(185,202,203,0.3)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em' }}>
          CACHED_BY_SERVICE_WORKER — Available offline. Last updated: {new Date().toLocaleDateString()}
        </div>
      </div>
    </div>
  );
}
