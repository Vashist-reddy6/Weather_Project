import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts';
import { getHistorical } from './api';

const BAR_COLORS = ['#6ff6ff', '#00dce6', '#8b5cf6', '#f97316'];

const TooltipStyle = {
  contentStyle: {
    background: 'rgba(19,19,20,0.95)',
    border: '1px solid rgba(111,246,255,0.15)',
    borderRadius: 8, color: '#e5e2e3', fontSize: 11,
    fontFamily: 'JetBrains Mono',
  },
  cursor: { fill: 'rgba(111,246,255,0.04)' },
};

export default function HistoricalPanel({ lat, lon }) {
  const [data, setData]       = useState(null);
  const [days, setDays]       = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const fetchData = async () => {
    if (!lat || !lon) return;
    setLoading(true); setError('');
    try {
      const res = await getHistorical(lat, lon, days);
      setData(res.data.data);
    } catch { setError('ERR — Failed to load NASA POWER data'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [lat, lon, days]);

  if (!lat || !lon) {
    return (
      <div className="card">
        <div className="empty-state">
          <div className="icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1"><path d="M12 2a10 10 0 1 0 10 10 10 10 0 0 0-10-10z"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          </div>
          <p>Scan a location first to view NASA POWER climate data</p>
        </div>
      </div>
    );
  }

  const chartData = data ? [
    { name: 'Avg Precip', value: data.avg_precipitation_mm, unit: 'mm' },
    { name: 'Max Precip', value: data.max_precipitation_mm, unit: 'mm' },
    { name: 'Avg Wind',   value: data.avg_wind_speed,        unit: 'm/s' },
    { name: 'Max Wind',   value: data.max_wind_speed,        unit: 'm/s' },
  ] : [];

  return (
    <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
      <div className="card-title" style={{ padding: '1.25rem 1.25rem 0' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        NASA POWER Climate
      </div>

      {/* Period selector */}
      <div style={{ display: 'flex', gap: '0.4rem', padding: '0 1.25rem', marginBottom: '1.25rem' }}>
        {[7, 14, 30, 60].map(d => (
          <button key={d} onClick={() => setDays(d)} className={`btn btn-sm ${days === d ? 'btn-primary' : 'btn-outline'}`}>
            {d} Days
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.75rem', padding: '2rem', color: 'rgba(185,202,203,0.3)' }}>
          <div className="spinner" style={{ width: 24, height: 24 }} />
          <span style={{ fontFamily: 'JetBrains Mono', fontSize: '0.62rem', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Querying satellite data...</span>
        </div>
      )}

      {error && (
        <p style={{ color: 'var(--risk-critical)', fontSize: '0.7rem', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em' }}>{error}</p>
      )}

      {data && !loading && (
        <div style={{ padding: '0 1.25rem 1.25rem' }}>
          {/* Summary stats */}
          <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
            {[
              ['Avg Rain',    data.avg_precipitation_mm, 'mm/day'],
              ['Max Rain',    data.max_precipitation_mm, 'mm/day'],
              ['Avg Wind',    data.avg_wind_speed,        'm/s'],
              ['Max Wind',    data.max_wind_speed,        'm/s'],
              ['Avg Humid',   data.avg_humidity,          '%'],
              ['Data Pts',    data.data_points,           'days'],
            ].map(([label, val, unit]) => (
              <div className="stat-item" key={label}>
                <span className="stat-label">{label}</span>
                <span className="stat-value">{val}<span className="stat-unit">{unit}</span></span>
              </div>
            ))}
          </div>

          <div className="card-title" style={{ marginBottom: '1.25rem', fontSize: '0.9rem' }}>Climate Summary</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 5, right: 0, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(111,246,255,0.04)" />
              <XAxis dataKey="name" tick={{ fill: 'var(--on-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--on-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...TooltipStyle} formatter={(v, n, p) => [`${v} ${p.payload.unit}`, p.payload.name]} />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={BAR_COLORS[i]} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <p style={{ fontSize: '0.8rem', color: 'var(--on-muted)', marginTop: '1.25rem', textAlign: 'center', fontWeight: 500 }}>
            SOURCE: NASA POWER — {days}D period
          </p>
        </div>
      )}
    </div>
  );
}
