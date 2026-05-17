/**
 * ResourceTracker — searchable list of shelters, medical camps, and relief points.
 * Fetches from GET /api/resources/list sorted by distance when coordinates are available.
 */
import { useState, useEffect } from 'react';
import API from './api';

const TYPE_META = {
  shelter:       { label: 'Shelter',       icon: '🏚️', color: '#3b82f6' },
  medical_camp:  { label: 'Medical Camp',  icon: '🏥', color: '#22c55e' },
  relief_center: { label: 'Relief Center', icon: '📦', color: '#f97316' },
  disaster_hq:   { label: 'Disaster HQ',  icon: '🎯', color: '#8b5cf6' },
};

const AMENITY_ICONS = {
  water: '💧', food: '🍲', medical: '💊', ambulance: '🚑',
  clothing: '👕', power_backup: '🔋', command_center: '📡',
  first_aid: '🩹', boats: '⛵',
};

const TYPE_FILTERS = [
  { value: null,             label: 'All' },
  { value: 'shelter',        label: '🏚️ Shelters' },
  { value: 'medical_camp',   label: '🏥 Medical' },
  { value: 'relief_center',  label: '📦 Relief' },
  { value: 'disaster_hq',    label: '🎯 HQ' },
];

export default function ResourceTracker({ lat, lon }) {
  const [resources, setResources] = useState([]);
  const [loading, setLoading]     = useState(false);
  const [filter, setFilter]       = useState(null);
  const [search, setSearch]       = useState('');
  const [expanded, setExpanded]   = useState(null);

  const fetchResources = async (type = filter) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (lat) { params.set('lat', lat); params.set('lon', lon); params.set('radius_km', 600); }
      if (type) params.set('resource_type', type);
      const res = await API.get(`/resources/list?${params}`);
      setResources(res.data.data || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchResources(); }, [lat, lon, filter]);

  const filtered = resources.filter((r) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return r.name.toLowerCase().includes(q) || r.city.toLowerCase().includes(q) || r.state.toLowerCase().includes(q);
  });

  const meta = (type) => TYPE_META[type] ?? { label: type, icon: '📍', color: '#94a3b8' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div className="card" style={{ padding: '1rem' }}>
        <div className="card-title" style={{ marginBottom: '0.75rem', fontSize: '0.9rem' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
          </svg>
          Resource Tracker
          {lat && <span style={{ fontSize: '0.75rem', color: 'var(--on-muted)', fontWeight: 500, marginLeft: 'auto' }}>sorted by distance</span>}
        </div>

        {/* Search */}
        <input
          className="input" placeholder="Search by name, city, state..."
          value={search} onChange={(e) => setSearch(e.target.value)}
          style={{ width: '100%', marginBottom: '0.65rem', fontSize: '0.8rem' }}
        />

        {/* Type filter pills */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          {TYPE_FILTERS.map(({ value, label }) => {
            const m = value ? meta(value) : null;
            const active = filter === value;
            return (
              <button key={String(value)} onClick={() => setFilter(value)}
                style={{
                  fontSize: '0.85rem', padding: '0.35rem 0.85rem', borderRadius: 20, cursor: 'pointer',
                  border: `1px solid ${active ? (m?.color ?? 'var(--cyan)') : 'var(--outline)'}`,
                  background: active ? `${m?.color ?? 'rgba(0,240,255,1)'}18` : 'var(--surface-hover)',
                  color: active ? (m?.color ?? 'var(--cyan)') : 'var(--on-muted)',
                  fontWeight: 500, transition: 'all 0.2s',
                }}>
                {label}
              </button>
            );
          })}
        </div>

        {/* Count */}
        <div style={{ fontSize: '0.8rem', color: 'var(--on-muted)', marginBottom: '1rem' }}>
          {loading ? 'Loading...' : `${filtered.length} resource${filtered.length !== 1 ? 's' : ''} found`}
        </div>

        {/* Resources list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {filtered.length === 0 && !loading && (
            <div style={{ padding: '2rem', textAlign: 'center', background: 'var(--surface-hover)', borderRadius: 8 }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📍</div>
              <p style={{ fontSize: '0.85rem', color: 'var(--on-muted)' }}>No resources match your filter</p>
            </div>
          )}

          {filtered.map((r) => {
            const m = meta(r.type);
            const isOpen = expanded === r.id;
            return (
              <div key={r.id} style={{ padding: '0', overflow: 'hidden', border: `1px solid ${isOpen ? m.color + '30' : 'var(--outline)'}`, borderRadius: 8, background: 'var(--surface)' }}>
              <button
                onClick={() => setExpanded(isOpen ? null : r.id)}
                style={{
                  width: '100%', background: isOpen ? `${m.color}06` : 'transparent',
                  border: 'none', cursor: 'pointer', padding: '0.85rem 1rem',
                  display: 'flex', alignItems: 'center', gap: '0.75rem', textAlign: 'left',
                }}
              >
                {/* Icon badge */}
                <div style={{
                  width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                  background: `${m.color}18`, border: `1px solid ${m.color}30`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '1.1rem',
                }}>
                  {m.icon}
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#fff', marginBottom: '0.15rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {r.name}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--on-muted)' }}>
                    {r.city}, {r.state}
                    {r.distance_km != null && <span style={{ color: m.color, marginLeft: '0.5rem' }}>· {r.distance_km} km</span>}
                  </div>
                </div>

                {/* Status + capacity */}
                <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.3rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#22c55e', background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 20, padding: '0.15rem 0.6rem' }}>
                    {r.status}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--on-muted)' }}>
                    cap: {r.capacity}
                  </span>
                </div>

                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--on-muted)" strokeWidth="2" style={{ flexShrink: 0, transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', marginLeft: '0.5rem' }}>
                  <path d="M6 9l6 6 6-6"/>
                </svg>
              </button>

              {isOpen && (
                <div style={{ padding: '0 1rem 1rem', borderTop: '1px solid var(--outline)', paddingTop: '0.75rem', animation: 'fadeUp 0.2s ease' }}>
                  {/* Amenities */}
                  {r.amenities?.length > 0 && (
                    <div style={{ marginBottom: '0.8rem' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--on-muted)', fontWeight: 600, letterSpacing: '0.05em', marginBottom: '0.4rem' }}>AMENITIES</div>
                      <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                        {r.amenities.map((a) => (
                          <span key={a} style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem', borderRadius: 20, background: 'var(--surface)', border: '1px solid var(--outline)', color: 'var(--on-surface)' }}>
                            {AMENITY_ICONS[a] ?? '✓'} {a.replace('_', ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Contact + map link */}
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <a href={`tel:${r.contact}`}
                      style={{ flex: 1, padding: '0.65rem', borderRadius: 8, background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', color: '#22c55e', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none', textAlign: 'center' }}>
                      📞 {r.contact}
                    </a>
                    <a href={`https://www.google.com/maps/dir/?api=1&destination=${r.lat},${r.lon}`} target="_blank" rel="noreferrer"
                      style={{ padding: '0.65rem 1rem', borderRadius: 8, background: `${m.color}10`, border: `1px solid ${m.color}25`, color: m.color, fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      🗺️ Directions
                    </a>
                  </div>
                </div>
              )}
              </div>
            );
          })}
        </div>
      </div>

      {/* SMS mode tip */}
      <div style={{ padding: '0.75rem 1rem', background: 'rgba(0,240,255,0.03)', border: '1px solid rgba(0,240,255,0.08)', borderRadius: 12, fontSize: '0.65rem', color: 'rgba(185,202,203,0.35)', fontFamily: 'JetBrains Mono', letterSpacing: '0.04em' }}>
        📱 No internet? Text <span style={{ color: 'var(--cyan)' }}>RISK {'<city>'}</span> to the WeatherGuard Twilio number for SMS shelter info.
      </div>
    </div>
  );
}
