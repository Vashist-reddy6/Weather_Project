import { useState, useEffect, useRef } from 'react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';

const TTStyle = {
  contentStyle: {
    background: 'rgba(10, 11, 14, 0.95)',
    border: '1px solid rgba(0,240,255,0.2)',
    borderRadius: 8, color: '#e5e2e3', fontSize: 11,
    fontFamily: 'JetBrains Mono',
  },
  cursor: { stroke: 'rgba(0,240,255,0.15)' },
};

/**
 * WeatherCharts — Recharts visualizations for 5-day hourly forecast data.
 * Props:
 *   forecast: array of forecast objects from OpenWeatherMap
 */
export default function WeatherCharts({ forecast }) {
  const [activeChart, setActiveChart] = useState('temperature');

  if (!forecast || forecast.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        </div>
        <p>Scan a location first to view weather charts</p>
      </div>
    );
  }

  // Prepare chart data
  const chartData = forecast.map((f) => ({
    time: new Date(f.datetime).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', hour12: true }),
    temp:     parseFloat(f.temperature?.toFixed(1) ?? 0),
    feels:    parseFloat(f.feels_like?.toFixed(1)  ?? 0),
    humidity: f.humidity ?? 0,
    wind:     parseFloat(f.wind_speed?.toFixed(1)  ?? 0),
    rain:     parseFloat((f.rainfall_3h ?? 0).toFixed(1)),
    clouds:   f.cloud_cover ?? 0,
  }));

  const charts = {
    temperature: {
      label: 'Temperature',
      color: '#f97316',
      color2: '#6ff6ff',
      render: () => (
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="tempGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#f97316" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#f97316" stopOpacity={0.01} />
            </linearGradient>
            <linearGradient id="feelsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#6ff6ff" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#6ff6ff" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="time" tick={tick} axisLine={false} tickLine={false} interval={2} />
          <YAxis tick={tick} axisLine={false} tickLine={false} unit="°" domain={['auto','auto']} />
          <Tooltip {...TTStyle} formatter={(v, n) => [`${v}°C`, n === 'temp' ? 'Temperature' : 'Feels Like']} />
          <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: 'rgba(185,202,203,0.7)' }} />
          <Area type="monotone" dataKey="temp"  name="Temp"       stroke="#f97316" fill="url(#tempGrad)"  strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#f97316' }} />
          <Area type="monotone" dataKey="feels" name="Feels Like" stroke="#6ff6ff" fill="url(#feelsGrad)" strokeWidth={1.5} strokeDasharray="4 2" dot={false} activeDot={{ r: 3, fill: '#6ff6ff' }} />
        </AreaChart>
      ),
    },
    humidity: {
      label: 'Humidity & Cloud Cover',
      color: '#3b82f6',
      render: () => (
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="time" tick={tick} axisLine={false} tickLine={false} interval={2} />
          <YAxis tick={tick} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
          <Tooltip {...TTStyle} formatter={(v, n) => [`${v}%`, n === 'humidity' ? 'Humidity' : 'Cloud Cover']} />
          <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: 'rgba(185,202,203,0.7)' }} />
          <Line type="monotone" dataKey="humidity" name="Humidity"    stroke="#3b82f6" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#3b82f6' }} />
          <Line type="monotone" dataKey="clouds"   name="Cloud Cover" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="3 2" dot={false} activeDot={{ r: 3 }} />
        </LineChart>
      ),
    },
    wind: {
      label: 'Wind Speed',
      color: '#22c55e',
      render: () => (
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="windGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="time" tick={tick} axisLine={false} tickLine={false} interval={2} />
          <YAxis tick={tick} axisLine={false} tickLine={false} unit=" m/s" domain={[0,'auto']} />
          <Tooltip {...TTStyle} formatter={(v) => [`${v} m/s`, 'Wind Speed']} />
          <Area type="monotone" dataKey="wind" name="Wind" stroke="#22c55e" fill="url(#windGrad)" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#22c55e' }} />
        </AreaChart>
      ),
    },
    rain: {
      label: 'Rainfall Forecast',
      color: '#6366f1',
      render: () => (
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="time" tick={tick} axisLine={false} tickLine={false} interval={2} />
          <YAxis tick={tick} axisLine={false} tickLine={false} unit="mm" domain={[0,'auto']} />
          <Tooltip {...TTStyle} formatter={(v) => [`${v} mm`, 'Rainfall (3h)']} />
          <Bar dataKey="rain" name="Rain" fill="rgba(99,102,241,0.7)" radius={[4, 4, 0, 0]} />
        </BarChart>
      ),
    },
  };

  const CHART_TABS = [
    { key: 'temperature', label: '🌡 Temp' },
    { key: 'humidity',    label: '💧 Humid' },
    { key: 'wind',        label: '💨 Wind' },
    { key: 'rain',        label: '🌧 Rain' },
  ];

  return (
    <div className="card" style={{ padding: '1rem' }}>
      <div className="card-title" style={{ marginBottom: '1.25rem', fontSize: '0.95rem' }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '0.5rem' }}>
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        Weather Forecast Charts
      </div>

      {/* Chart type selector */}
      <div style={{ display: 'flex', gap: '0.35rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        {CHART_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveChart(key)}
            style={{
              fontSize: '0.95rem', padding: '0.5rem 1rem', borderRadius: 20,
              border: `1px solid ${activeChart === key ? charts[key].color : 'var(--outline)'}`,
              background: activeChart === key ? `${charts[key].color}20` : 'var(--surface-hover)',
              color: activeChart === key ? charts[key].color : 'var(--on-muted)',
              cursor: 'pointer', transition: 'all 0.2s',
              fontWeight: activeChart === key ? 600 : 500,
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Chart area */}
      <ResponsiveContainer width="100%" height={210}>
        {charts[activeChart].render()}
      </ResponsiveContainer>

      {/* Summary stats below chart */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginTop: '1rem' }}>
        {(() => {
          switch (activeChart) {
            case 'temperature':
              return [
                { label: 'Max Temp', value: `${Math.max(...chartData.map(d => d.temp))}°C`, color: '#f97316' },
                { label: 'Min Temp', value: `${Math.min(...chartData.map(d => d.temp))}°C`, color: '#6ff6ff' },
                { label: 'Avg Feels', value: `${Math.round(chartData.reduce((a,c)=>a+c.feels,0)/chartData.length)}°C`, color: '#f59e0b' },
              ];
            case 'humidity':
              return [
                { label: 'Max Humid', value: `${Math.max(...chartData.map(d => d.humidity))}%`, color: '#3b82f6' },
                { label: 'Avg Humid', value: `${Math.round(chartData.reduce((a,c)=>a+c.humidity,0)/chartData.length)}%`, color: '#60a5fa' },
                { label: 'Max Clouds', value: `${Math.max(...chartData.map(d => d.clouds))}%`, color: '#94a3b8' },
              ];
            case 'wind':
              return [
                { label: 'Max Wind', value: `${Math.max(...chartData.map(d => d.wind)).toFixed(1)} m/s`, color: '#22c55e' },
                { label: 'Avg Wind', value: `${(chartData.reduce((a,c)=>a+c.wind,0)/chartData.length).toFixed(1)} m/s`, color: '#4ade80' },
                { label: 'Status', value: Math.max(...chartData.map(d=>d.wind)) > 15 ? 'Gale' : 'Normal', color: '#10b981' },
              ];
            case 'rain':
              return [
                { label: 'Total Rain', value: `${chartData.reduce((a,c)=>a+c.rain,0).toFixed(1)} mm`, color: '#6366f1' },
                { label: 'Max Rain', value: `${Math.max(...chartData.map(d => d.rain)).toFixed(1)} mm`, color: '#818cf8' },
                { label: 'Rain Risk', value: chartData.some(d=>d.rain > 0) ? 'Yes' : 'No', color: '#a5b4fc' },
              ];
            default: return [];
          }
        })().map(({ label, value, color }) => (
          <div key={label} style={{
            background: 'var(--surface)', border: '1px solid var(--outline)',
            borderRadius: 10, padding: '0.6rem', textAlign: 'center',
          }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--on-muted)', fontWeight: 600, marginBottom: '0.25rem' }}>{label}</div>
            <div style={{ fontSize: '1.15rem', fontWeight: 600, color }}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

const tick = { fill: 'rgba(185,202,203,0.7)', fontSize: 12, fontFamily: 'JetBrains Mono' };
