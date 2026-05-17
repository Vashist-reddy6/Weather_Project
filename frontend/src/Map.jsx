/**
 * Map.jsx — 3D MapLibre GL map with terrain, sky, and animated risk markers.
 * Uses:
 *  - Free CARTO Dark Matter vector style (no API key)
 *  - Free MapLibre demo terrain tiles for 3D elevation
 *  - maplibre-gl (already in package.json)
 */
import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const RISK_COLORS = {
  LOW:      '#10b981',
  MODERATE: '#eab308',
  HIGH:     '#f97316',
  CRITICAL: '#ef4444',
};

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json';

/** Escape HTML special chars to prevent XSS via user-controlled location names. */
function _esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildPopupHTML(m, color) {
  return `
    <div style="
      position:relative; font-family:'Inter', sans-serif; min-width:210px;
      background:var(--surface-card, #131316); color:var(--on-surface, #fff); border-radius:12px;
      padding:14px; border:1px solid var(--outline, rgba(255,255,255,0.1));
      box-shadow:var(--shadow-lg, 0 10px 40px rgba(0,0,0,0.5)); overflow:hidden;
    ">
      <div style="position:absolute;top:0;left:0;width:100%;height:4px;background:${color};"></div>
      <div style="font-weight:600;font-size:0.9rem;margin-bottom:4px;color:var(--on-surface, #fff);">${_esc(m.name) || 'Selected Location'}</div>
      <div style="font-size:0.7rem;color:var(--on-muted, #94a3b8);margin-bottom:8px;">Threat Level</div>
      <div style="font-size:1.15rem;font-weight:700;color:${color};margin-bottom:12px;">${_esc(m.risk_level)}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.75rem;background:var(--surface, rgba(255,255,255,0.03));padding:10px;border-radius:8px;border:1px solid var(--outline, rgba(255,255,255,0.05));">
        <span style="color:var(--on-muted, #94a3b8);">Score</span>
        <span style="color:${color};font-weight:600;">${(m.risk_score * 100).toFixed(1)}%</span>
        ${m.temperature !== undefined ? `<span style="color:var(--on-muted, #94a3b8);">Temp</span><span style="color:var(--on-surface, #fff);">${_esc(m.temperature)}°C</span>` : ''}
        ${m.humidity    !== undefined ? `<span style="color:var(--on-muted, #94a3b8);">Humid</span><span style="color:var(--on-surface, #fff);">${_esc(m.humidity)}%</span>` : ''}
        ${m.wind_speed  !== undefined ? `<span style="color:var(--on-muted, #94a3b8);">Wind</span><span style="color:var(--on-surface, #fff);">${_esc(m.wind_speed)} m/s</span>` : ''}
      </div>
    </div>`;
}

function createMarkerEl(color) {
  const el = document.createElement('div');
  el.className = 'wg-marker';
  // The marker anchor is set to 'center' in maplibregl.Marker options.
  // The wg-core dot sits exactly at the center (0,0) of the element,
  // and the rings expand outward from that same center point.
  // This ensures the visual pin never drifts from the coordinate on zoom/pitch.
  el.innerHTML = `
    <div class="wg-core" style="background:${color};box-shadow:0 0 18px ${color}90;"></div>
    <div class="wg-ring  wg-r1" style="border-color:${color};"></div>
    <div class="wg-ring  wg-r2" style="border-color:${color};"></div>`;
  return el;
}

export default function Map({ markers, onMapClick, loading }) {
  const containerRef = useRef(null);
  const mapRef       = useRef(null);
  const markersRef   = useRef([]);
  const onClickRef   = useRef(onMapClick);

  // Keep click callback fresh without re-initialising the map
  useEffect(() => { onClickRef.current = onMapClick; }, [onMapClick]);

  // ── Initialise map once ────────────────────────────────────────────────────
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    const map = new maplibregl.Map({
      container:  containerRef.current,
      style:      MAP_STYLE,
      center:     [78, 20],
      zoom:       4.5,
      pitch:      52,
      bearing:    -12,
      antialias:  true,
    });

    mapRef.current = map;

    map.on('load', () => {
      // 3D Terrain ─────────────────────────────────────────────────────────
      map.addSource('terrain-dem', {
        type:     'raster-dem',
        url:      'https://demotiles.maplibre.org/terrain-tiles/tiles.json',
        tileSize: 256,
      });
      map.setTerrain({ source: 'terrain-dem', exaggeration: 2.5 });

      // Daytime atmospheric sky ──────────────────────────────────────────────
      map.setSky({
        'sky-color':           '#87ceeb',
        'sky-horizon-blend':   0.5,
        'horizon-color':       '#d4eaf7',
        'horizon-fog-blend':   0.4,
        'fog-color':           '#e8f4f8',
        'fog-ground-blend':    0.3,
      });
    });

    // Click → analyse location
    map.on('click', (e) => {
      onClickRef.current(e.lngLat.lat, e.lngLat.lng);
    });

    // Controls
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Sync markers whenever the prop changes ─────────────────────────────────
  useEffect(() => {
    if (!mapRef.current) return;

    // Remove old GL markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    markers.forEach((m) => {
      const color = RISK_COLORS[m.risk_level] || '#00f0ff';
      const el    = createMarkerEl(color);

      const popup = new maplibregl.Popup({
        offset:      30,
        closeButton: false,
        maxWidth:    '260px',
      }).setHTML(buildPopupHTML(m, color));

      const glMarker = new maplibregl.Marker({ element: el, anchor: 'center' })
        .setLngLat([m.lon, m.lat])
        .addTo(mapRef.current);

      el.addEventListener('mouseenter', () => popup.setLngLat([m.lon, m.lat]).addTo(mapRef.current));
      el.addEventListener('mouseleave', () => popup.remove());

      markersRef.current.push(glMarker);
    });

    // Fly to the most recent marker with a cinematic pitch
    if (markers.length > 0 && mapRef.current.loaded()) {
      const last = markers[markers.length - 1];
      mapRef.current.flyTo({
        center:   [last.lon, last.lat],
        zoom:     7.5,
        pitch:    60,
        bearing:  -25,
        duration: 2200,
        essential: true,
      });
    }
  }, [markers]);

  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      borderRadius: '12px', overflow: 'hidden',
      border: '1px solid var(--outline)',
      boxShadow: 'var(--shadow-sm)',
    }}>

      {/* Loading overlay */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 9999,
          background: 'rgba(9, 9, 11, 0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        }}>
          <div className="spinner" style={{ width: 40, height: 40, border: '3px solid var(--surface-hover)', borderTopColor: 'var(--accent)' }} />
          <span style={{
            color: 'var(--on-muted)', marginTop: 16,
            fontFamily: 'var(--font-data)', letterSpacing: 2,
            fontWeight: 500, fontSize: '0.8rem'
          }}>SCANNING SECTOR…</span>
        </div>
      )}

      {/* Status badge */}
      <div style={{
        position: 'absolute', top: 20, left: '50%', transform: 'translateX(-50%)',
        zIndex: 1000, background: 'var(--surface-card)', color: 'var(--on-surface)',
        padding: '8px 16px', borderRadius: 20, fontSize: '0.75rem',
        boxShadow: 'var(--shadow-sm)',
        border: '1px solid var(--outline)',
        fontFamily: 'var(--font-body)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8,
        pointerEvents: 'none', backdropFilter: 'blur(12px)',
      }}>
        <span style={{
          width: 6, height: 6, background: 'var(--risk-low)', borderRadius: '50%',
          display: 'inline-block', flexShrink: 0,
        }} />
        AI SATELLITE FEED ACTIVE
      </div>

      {/* Map container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 30, right: 30, zIndex: 1000,
        background: 'var(--surface-card)', padding: '16px 20px',
        borderRadius: 12, backdropFilter: 'blur(12px)',
        border: '1px solid var(--outline)',
        boxShadow: 'var(--shadow-lg)',
      }}>
        <h4 style={{
          color: 'var(--on-muted)', margin: '0 0 12px', fontSize: '0.75rem',
          fontFamily: 'var(--font-data)', letterSpacing: 1, fontWeight: 500
        }}>AI THREAT MATRIX</h4>
        {Object.entries(RISK_COLORS).map(([level, color]) => (
          <div key={level} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <div style={{
              width: 10, height: 10, borderRadius: '2px',
              background: color, marginRight: 10,
            }} />
            <span style={{
              color: 'var(--on-surface)', fontSize: '0.75rem',
              fontFamily: 'var(--font-body)', fontWeight: 500,
            }}>{level}</span>
          </div>
        ))}
      </div>

      {/* Inline styles */}
      <style>{`
        /* ── Animated radar blip markers ──
         * The .wg-marker wrapper is 0×0 so its top-left (which MapLibre
         * uses as the placement point when anchor='center' is given as offset)
         * sits exactly at the lat/lng pixel.
         * Every child is absolutely positioned and centred via
         * translate(-50%, -50%) so the visual dot is always on the pin.
         */
        .wg-marker {
          width: 30px; height: 30px;
          cursor: pointer;
          pointer-events: auto;
        }
        .wg-core {
          width: 14px; height: 14px; border-radius: 50%;
          border: 2.5px solid rgba(255,255,255,0.9);
          position: absolute;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          z-index: 3;
          transition: transform 0.2s;
        }
        .wg-marker:hover .wg-core {
          transform: translate(-50%, -50%) scale(1.4);
        }
        .wg-ring {
          position: absolute;
          width: 40px; height: 40px;
          border: 2px solid;
          border-radius: 50%;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%) scale(0.4);
          opacity: 0;
          z-index: 1;
          pointer-events: none;
        }
        .wg-r1 { animation: wg-ping 2.2s cubic-bezier(0,0,0.2,1) infinite; }
        .wg-r2 { animation: wg-ping 2.2s cubic-bezier(0,0,0.2,1) 0.8s infinite; }
        @keyframes wg-ping {
          0%   { transform: translate(-50%,-50%) scale(0.3);  opacity: 0.9; }
          100% { transform: translate(-50%,-50%) scale(3.5);  opacity: 0; }
        }

        /* ── MapLibre GL popup overrides ── */
        .maplibregl-popup-content {
          background: transparent !important;
          padding: 0 !important;
          box-shadow: none !important;
        }
        .maplibregl-popup-tip { display: none !important; }

        /* ── Navigation controls (styled for light map) ── */
        .maplibregl-ctrl-group {
          background: rgba(255,255,255,0.92) !important;
          border: 1px solid rgba(0,0,0,0.12) !important;
          box-shadow: 0 2px 12px rgba(0,0,0,0.15) !important;
          border-radius: 10px !important;
        }
        .maplibregl-ctrl-group button {
          background: transparent !important;
        }
        .maplibregl-ctrl-icon { filter: none; }
      `}</style>
    </div>
  );
}
