/**
 * CommunityReport — crowdsourced hazard reporting form + live reports list.
 */
import { useState, useEffect } from 'react';
import API from './api';

const HAZARD_TYPES = [
  { value: 'flooded_road',      label: '🌊 Flooded Road',     color: '#3b82f6' },
  { value: 'downed_line',       label: '⚡ Downed Power',     color: '#eab308' },
  { value: 'landslide',         label: '⛰️ Landslide',         color: '#92400e' },
  { value: 'fire',              label: '🔥 Fire',               color: '#ef4444' },
  { value: 'cyclone_damage',    label: '🌀 Cyclone Damage',    color: '#06b6d4' },
  { value: 'building_collapse', label: '🏢 Building Collapse', color: '#64748b' },
  { value: 'road_blocked',      label: '🚧 Road Blocked',      color: '#f97316' },
  { value: 'other',             label: '⚠️ Other Hazard',      color: '#94a3b8' },
];
const SEVERITY_OPTS = [
  { value: 'LOW', color: '#22c55e' }, { value: 'MODERATE', color: '#eab308' },
  { value: 'HIGH', color: '#f97316' }, { value: 'CRITICAL', color: '#ef4444' },
];
const timeAgo = (iso) => {
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s/60)}m ago`;
  return `${Math.round(s/3600)}h ago`;
};

export default function CommunityReport({ lat, lon }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSub]  = useState(false);
  const [status, setStatus]   = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    hazard_type: 'flooded_road', description: '', reporter_name: '',
    severity: 'MODERATE', latitude: lat ?? '', longitude: lon ?? '',
  });

  useEffect(() => {
    if (lat) setForm((p) => ({ ...p, latitude: lat, longitude: lon }));
  }, [lat, lon]);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const q = lat ? `?lat=${lat}&lon=${lon}&radius_km=300&limit=30` : '?limit=30';
      const res = await API.get(`/community/reports${q}`);
      setReports(res.data.data || []);
    } catch { /* silent */ } finally { setLoading(false); }
  };

  useEffect(() => { fetchReports(); }, [lat, lon]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.latitude || !form.longitude) { setStatus('ERR — Analyze a location first to fill coordinates'); return; }
    setSub(true); setStatus('');
    try {
      await API.post('/community/report', { ...form, latitude: parseFloat(form.latitude), longitude: parseFloat(form.longitude) });
      setStatus('OK — Report submitted. Thank you!');
      setShowForm(false);
      setForm((p) => ({ ...p, description: '', reporter_name: '' }));
      fetchReports();
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail) ? detail[0].msg : (detail || 'Failed to submit report');
      setStatus(`ERR — ${msg}`);
    }
    finally { setSub(false); }
  };

  const hm = (type) => HAZARD_TYPES.find((h) => h.value === type) ?? HAZARD_TYPES.at(-1);
  const sm = (sev)  => SEVERITY_OPTS.find((s) => s.value === sev) ?? SEVERITY_OPTS[1];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div className="card" style={{ padding: '1rem' }}>
        <div className="card-title" style={{ marginBottom: '0.5rem' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          Community Hazard Reports
        </div>
        <p style={{ fontSize: '0.72rem', color: 'rgba(185,202,203,0.5)', lineHeight: 1.5, marginBottom: '0.75rem' }}>
          Report local hazards (flooded roads, downed lines) as map pins visible to your community.
        </p>
        <button className={`btn ${showForm ? 'btn-outline' : 'btn-primary'}`} style={{ width: '100%' }}
          onClick={() => setShowForm((v) => !v)}>
          {showForm ? '✕ Cancel' : '+ Report a Hazard'}
        </button>
        {status && <p style={{ marginTop: '0.6rem', fontSize: '0.65rem', textAlign: 'center', fontFamily: 'JetBrains Mono', color: status.startsWith('OK') ? '#22c55e' : '#ef4444' }}>{status}</p>}
      </div>

      {showForm && (
        <div className="card" style={{ padding: '1rem', animation: 'fadeUp 0.3s ease forwards' }}>
          <div className="card-title" style={{ marginBottom: '0.75rem' }}>New Hazard Report</div>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            <div>
              <div className="form-label" style={{ marginBottom: '0.4rem' }}>Hazard Type</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.35rem' }}>
                {HAZARD_TYPES.map(({ value, label, color }) => (
                  <button key={value} type="button" onClick={() => setForm((p) => ({ ...p, hazard_type: value }))}
                    style={{ padding: '0.5rem', borderRadius: 8, border: `1px solid ${form.hazard_type === value ? color : 'var(--outline)'}`, background: form.hazard_type === value ? `${color}18` : 'var(--surface-hover)', color: form.hazard_type === value ? color : 'var(--on-muted)', cursor: 'pointer', fontSize: '0.8rem', transition: 'all 0.2s', textAlign: 'left' }}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="form-label" style={{ marginBottom: '0.4rem' }}>Severity</div>
              <div style={{ display: 'flex', gap: '0.35rem' }}>
                {SEVERITY_OPTS.map(({ value, color }) => (
                  <button key={value} type="button" onClick={() => setForm((p) => ({ ...p, severity: value }))}
                    style={{ flex: 1, padding: '0.45rem', borderRadius: 8, border: `1px solid ${form.severity === value ? color : 'var(--outline)'}`, background: form.severity === value ? `${color}18` : 'var(--surface-hover)', color: form.severity === value ? color : 'var(--on-muted)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, transition: 'all 0.2s' }}>
                    {value}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Description *</label>
              <textarea className="input" required rows={2} placeholder="e.g. Road flooded near bridge, ~30cm deep"
                value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                style={{ resize: 'vertical', minHeight: 56, fontSize: '0.9rem' }} />
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Your Name (optional)</label>
              <input className="input" type="text" placeholder="Anonymous" value={form.reporter_name}
                onChange={(e) => setForm((p) => ({ ...p, reporter_name: e.target.value }))} />
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {[['latitude','Latitude'],['longitude','Longitude']].map(([field, label]) => (
                <div key={field} className="form-group" style={{ flex: 1, marginBottom: 0, minWidth: 0 }}>
                  <label className="form-label">{label}</label>
                  <input className="input" type="number" step="any" placeholder="Auto-filled"
                    value={form[field]} onChange={(e) => setForm((p) => ({ ...p, [field]: e.target.value }))} required style={{ minWidth: 0, width: '100%', boxSizing: 'border-box' }} />
                </div>
              ))}
            </div>

            <button type="submit" className="btn btn-primary" disabled={submitting} style={{ width: '100%' }}>
              {submitting ? 'Submitting...' : 'Submit Report'}
            </button>
          </form>
        </div>
      )}

      <div className="card" style={{ padding: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <div className="card-title" style={{ marginBottom: 0 }}>
            Recent Reports {reports.length > 0 && <span style={{ color: 'rgba(185,202,203,0.4)', fontWeight: 400 }}>({reports.length})</span>}
          </div>
          <button onClick={fetchReports} disabled={loading}
            style={{ fontSize: '0.6rem', padding: '0.25rem 0.65rem', borderRadius: 20, background: 'rgba(0,0,0,0.4)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(185,202,203,0.5)', cursor: 'pointer', fontFamily: 'JetBrains Mono' }}>
            {loading ? '...' : '↻ Refresh'}
          </button>
        </div>

        {reports.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--on-muted)', fontSize: '0.85rem' }}>
            No reports in this area — Be the first to report a hazard.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: 280, overflowY: 'auto' }}>
            {reports.map((r) => {
              const h = hm(r.hazard_type), s = sm(r.severity);
              return (
                <div key={r.id} style={{ background: 'var(--surface-hover)', border: `1px solid ${h.color}30`, borderRadius: 10, padding: '0.8rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                    <span style={{ fontSize: '0.85rem', color: h.color, fontWeight: 600 }}>{h.label}</span>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.75rem', color: s.color, fontWeight: 600, background: `${s.color}15`, padding: '0.2rem 0.5rem', borderRadius: 20, border: `1px solid ${s.color}30` }}>{r.severity}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--on-muted)' }}>{timeAgo(r.reported_at)}</span>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.9rem', color: 'var(--on-surface)', lineHeight: 1.4, marginBottom: '0.35rem' }}>{r.description}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--on-muted)' }}>
                    by {r.reporter_name || 'Anonymous'} · {parseFloat(r.latitude).toFixed(3)}, {parseFloat(r.longitude).toFixed(3)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
