import { useState, useEffect, useRef, useCallback } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { getPredictionHistory, getUsers, broadcastAlert } from './api';

const RISK_COLOR = { LOW: '#22c55e', MODERATE: '#e8c426', HIGH: '#f97316', CRITICAL: '#ef4444' };
const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`;
const POLL_INTERVAL_MS = 30_000; // 30-second live refresh

const TooltipStyle = {
  contentStyle: {
    background: 'rgba(19,19,20,0.95)',
    border: '1px solid var(--outline)',
    borderRadius: 8, color: '#e5e2e3', fontSize: '0.85rem'
  },
  cursor: { stroke: 'rgba(0,240,255,0.15)' },
};

export default function Dashboard() {
  const [history, setHistory]       = useState([]);
  const [users, setUsers]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [bcStatus, setBcStatus]     = useState('');
  const [activeTab, setActiveTab]   = useState('predictions');
  const [liveEvents, setLiveEvents] = useState([]);
  const wsRef = useRef(null);

  // ── Core fetch function (used for both initial load & polling) ──
  const fetchAll = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true); else setRefreshing(true);
    try {
      // Prediction history is public; users list requires auth
      const [hRes, uRes] = await Promise.allSettled([
        getPredictionHistory(50),
        getUsers(),
      ]);
      if (hRes.status === 'fulfilled') setHistory(hRes.value.data.data || []);
      if (uRes.status === 'fulfilled') {
        setUsers(uRes.value.data.data || []);
      }
      // else: unauthenticated — users stays at [] (not an error state)
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      if (isInitial) setLoading(false); else setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    // Initial load
    fetchAll(true);

    // Periodic polling — keeps stat cards live even without WebSocket events
    const pollTimer = setInterval(() => fetchAll(false), POLL_INTERVAL_MS);

    // WebSocket live feed
    const connectWS = () => {
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data);
            if (msg.type === 'prediction') {
              setLiveEvents(prev => [msg, ...prev].slice(0, 10));
              // Immediately refresh all data on new predictions
              fetchAll(false);
            }
          } catch {}
        };
        ws.onerror = () => {};
        ws.onclose = () => setTimeout(connectWS, 3000); // auto-reconnect
      } catch {}
    };
    connectWS();

    return () => {
      clearInterval(pollTimer);
      wsRef.current?.close();
    };
  }, [fetchAll]);

  const riskCounts = { LOW: 0, MODERATE: 0, HIGH: 0, CRITICAL: 0 };
  history.forEach(h => { if (riskCounts[h.risk_level] !== undefined) riskCounts[h.risk_level]++; });

  const chartData = history.slice(0, 20).reverse().map((h, i) => ({
    name: i + 1,
    score: Math.round(h.risk_score * 100),
    level: h.risk_level,
    location: h.location_name || 'Generic'
  }));

  const handleBroadcast = async () => {
    if (!window.confirm('Broadcast HIGH risk alert to all registered users?')) return;
    setBcStatus('TRANSMITTING...');
    try {
      const res = await broadcastAlert('HIGH', 'All Monitored Zones', 'Elevated weather conditions detected');
      setBcStatus(`OK — Transmitted to ${res.data.total_sent} operators`);
    } catch { setBcStatus('ERR — Broadcast failed'); }
  };

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '1rem', color: 'var(--on-muted)' }}>
      <div className="spinner" />
      <span style={{ fontSize: '0.9rem', fontWeight: 500, letterSpacing: '0.05em' }}>CONNECTING TO TELEMETRY NODE...</span>
    </div>
  );

  return (
    <div className="dashboard">
      {/* Dashboard header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: refreshing ? '#e8c426' : '#22c55e', boxShadow: `0 0 8px ${refreshing ? '#e8c426' : '#22c55e'}`, animation: 'pulse-dot 1.2s infinite' }} />
          <span style={{ fontSize: '0.78rem', color: 'var(--on-muted)', fontFamily: 'JetBrains Mono' }}>
            {refreshing ? 'REFRESHING...' : lastUpdated ? `UPDATED ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : 'LOADING...'}
          </span>
        </div>
        <button
          onClick={() => fetchAll(false)}
          disabled={refreshing || loading}
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(0,240,255,0.06)', border: '1px solid rgba(0,240,255,0.2)', borderRadius: 8, padding: '0.35rem 0.9rem', cursor: 'pointer', color: 'var(--cyan)', fontSize: '0.78rem', fontWeight: 600, transition: 'all 0.2s', opacity: (refreshing || loading) ? 0.5 : 1 }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }}>
            <path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          Refresh
        </button>
      </div>

      {/* Stat Cards */}
      <div className="stat-cards">
        {[
          { label: 'Total Scans',       value: history.length,        color: 'var(--cyan)',  icon: <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/> },
          { label: 'Registered Ops',    value: users.length,          color: 'var(--cyan)',  icon: <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm14 14v-2a4 4 0 0 0-3-3.87m-4-12a4 4 0 0 1 0 7.75"/> },
          { label: 'Critical Events',   value: riskCounts.CRITICAL,   color: '#ef4444',      icon: <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"/> },
          { label: 'High Events',       value: riskCounts.HIGH,       color: '#f97316',      icon: <path d="M22 12h-4l-3 9L9 3l-3 9H2"/> },
        ].map(({ label, value, color, icon }) => (
          <div className="stat-card" key={label}>
            <div className="stat-card-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{icon}</svg>
              {label}
            </div>
            <div className="stat-card-value">{value}</div>
          </div>
        ))}
      </div>

      {/* ── Live WebSocket Ticker ── */}
      {liveEvents.length > 0 && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: 'var(--surface)', border: '1px solid var(--outline)', borderRadius: 12, display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--cyan)', fontWeight: 600, flexShrink: 0, display: 'flex', alignItems: 'center' }}>
            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 10px #22c55e', marginRight: 8, animation: 'pulse-dot 1.2s infinite' }} />
            LIVE FEED
          </span>
          {liveEvents.slice(0, 4).map((ev, i) => (
            <span key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem', borderRadius: 20, background: `${RISK_COLOR[ev.risk_level]}18`, border: `1px solid ${RISK_COLOR[ev.risk_level]}40`, color: RISK_COLOR[ev.risk_level], fontWeight: 600 }}>
              {ev.location} → {ev.risk_level}
            </span>
          ))}
        </div>
      )}

      {/* Chart ─ color-coded bars per risk level */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1.5rem' }}>
        <div className="card-title" style={{ marginBottom: '1.5rem', fontSize: '1rem' }}>Risk Score History (last 20 scans)</div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--outline)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'var(--on-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: 'var(--on-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip {...TooltipStyle} formatter={(v, _n, p) => [`${v}% — ${p.payload.level}`, p.payload.location]} />
            <Area type="monotone" dataKey="score" stroke="var(--accent)" strokeWidth={3} fillOpacity={1} fill="url(#colorRisk)" animationDuration={1000} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Tab switcher */}
      <div className="tabs" style={{ marginBottom: '1.5rem', maxWidth: '400px', margin: '0 auto 1.5rem' }}>
        {[['predictions','Predictions'],['users','Operators'],['broadcast','Broadcast']].map(([t, l]) => (
          <button key={t} className={`tab ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>{l}</button>
        ))}
      </div>

      {/* Predictions table */}
      {activeTab === 'predictions' && (
        <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
          <div className="card-title" style={{ padding: '1.5rem 1.5rem 0' }}>Prediction History</div>
          <div style={{ overflowX: 'auto', padding: '0 0.5rem 1rem' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Location</th><th>Risk Level</th><th>Score</th><th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 25).map(h => (
                  <tr key={h.id}>
                    <td style={{ color: 'var(--on-surface)', fontWeight: 500 }}>{h.location_name || `${h.latitude?.toFixed(2)}, ${h.longitude?.toFixed(2)}`}</td>
                    <td>
                      <span className={`risk-badge risk-${h.risk_level}`} style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', fontWeight: 600 }}>
                        {h.risk_level}
                      </span>
                    </td>
                    <td style={{ color: RISK_COLOR[h.risk_level] || '#fff', fontWeight: 700, fontSize: '1rem' }}>
                      {Math.round(h.risk_score * 100)}%
                    </td>
                    <td style={{ color: 'var(--on-muted)', fontSize: '0.85rem' }}>
                      {new Date(h.predicted_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                    </td>
                  </tr>
                ))}
                {history.length === 0 && (
                  <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--on-muted)', padding: '2rem' }}>No data — Click the map to initiate a scan</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Users table */}
      {activeTab === 'users' && (
        <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
          <div className="card-title" style={{ padding: '1.5rem 1.5rem 0' }}>Registered Operators</div>
          <div style={{ overflowX: 'auto', padding: '0 0.5rem 1rem' }}>
            <table className="data-table">
              <thead>
                <tr><th>Name</th><th>Phone</th><th>Location</th><th>Registered</th></tr>
              </thead>
              <tbody>
                {users.map(u => {
                  const maskPhone = p => p ? p.slice(0, 3) + '****' + p.slice(-3) : '***';
                  const maskName = n => n ? n.split(' ').map(part => part[0] + '*'.repeat(part.length - 1)).join(' ') : '***';
                  return (
                    <tr key={u.id}>
                      <td style={{ fontWeight: 600 }}>{maskName(u.name)}</td>
                      <td style={{ color: 'var(--on-muted)', fontFamily: 'var(--font-data)' }}>{maskPhone(u.phone)}</td>
                      <td style={{ color: 'var(--on-muted)', fontSize: '0.72rem' }}>{u.location_name}</td>
                      <td style={{ color: 'rgba(185,202,203,0.35)', fontSize: '0.68rem' }}>{new Date(u.created_at).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
                {users.length === 0 && (
                  <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--on-muted)', padding: '2rem' }}>No operators registered</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Broadcast */}
      {activeTab === 'broadcast' && (
        <div className="card" style={{ maxWidth: '600px', margin: '0 auto' }}>
          <div className="card-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            Broadcast Emergency Alert
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--on-muted)', marginBottom: '1.5rem', lineHeight: 1.6 }}>
            Transmit an SMS alert to all <strong style={{ color: '#fff' }}>{users.length} registered operators</strong> simultaneously.
          </p>
          <div className="alert-box" style={{ marginBottom: '1.5rem', background: 'rgba(239,68,68,0.05)', borderColor: 'rgba(239,68,68,0.2)', color: 'var(--risk-critical)' }}>
            <span style={{ fontSize: '1.2rem' }}>⚠️</span>
            <span style={{ fontSize: '0.8rem' }}>This will trigger real SMS messages via Twilio to every registered operator.</span>
          </div>
          <button className="btn btn-danger" style={{ width: '100%', padding: '1rem' }} onClick={handleBroadcast}>
            Broadcast HIGH Risk Alert
          </button>
          {bcStatus && (
            <p style={{ marginTop: '0.75rem', textAlign: 'center', fontSize: '0.65rem', fontFamily: 'JetBrains Mono', letterSpacing: '0.1em', color: bcStatus.startsWith('OK') ? 'var(--risk-low)' : 'var(--risk-critical)' }}>
              {bcStatus}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
