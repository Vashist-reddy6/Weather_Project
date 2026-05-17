/**
 * ChatBot — floating AI Q&A panel powered by the rule-based engine (+ optional OpenAI).
 * Passes the current prediction context for grounded risk-aware answers.
 */
import { useState, useRef, useEffect } from 'react';
import API from './api';

const QUICK_PROMPTS = [
  'Is it safe to travel?',
  'What should I do during a flood?',
  'Nearest shelter?',
  'Emergency contacts',
  'What is the risk score?',
  'Cyclone safety tips',
];

export default function ChatBot({ predictionContext }) {
  const [open, setOpen]       = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: "👋 Hi! I'm WeatherGuard AI. Ask me about disaster safety, risk levels, evacuation routes, or weather conditions.",
      ts: Date.now(),
    },
  ]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const endRef                = useRef(null);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg) return;
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', text: msg, ts: Date.now() }]);
    setLoading(true);

    try {
      const res = await API.post('/chatbot/message', {
        message: msg,
        context: predictionContext || {},
      });
      setMessages((prev) => [
        ...prev,
        { role: 'bot', text: res.data.reply, engine: res.data.engine, ts: Date.now() },
      ].slice(-100)); // cap at 100 messages to prevent memory growth
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'bot', text: '⚠️ Unable to reach AI service. For emergencies call 112.', ts: Date.now() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* ── Floating toggle button ── */}
      <button
        id="chatbot-toggle"
        onClick={() => setOpen((v) => !v)}
        title="AI Safety Assistant"
        style={{
          position: 'fixed', bottom: '2rem', right: '2rem', zIndex: 2000,
          width: 56, height: 56, borderRadius: '50%',
          background: open
            ? 'var(--surface-hover)'
            : 'var(--accent)',
          border: '1px solid var(--outline)',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: 'var(--shadow-lg)',
          transition: 'all 0.3s',
        }}
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        )}
      </button>

      {/* ── Chat panel ── */}
      {open && (
        <div
          id="chatbot-panel"
          style={{
            position: 'fixed', bottom: '6rem', right: '2rem', zIndex: 1999,
            width: 360, height: 500,
            background: 'var(--surface)',
            border: '1px solid var(--outline)',
            borderRadius: 16,
            display: 'flex', flexDirection: 'column',
            boxShadow: 'var(--shadow-lg)',
            animation: 'fadeUp 0.3s ease forwards',
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div style={{
            padding: '1rem 1.25rem', borderBottom: '1px solid var(--outline)',
            display: 'flex', alignItems: 'center', gap: '0.75rem',
            background: 'var(--surface-card)',
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              background: 'var(--surface-hover)',
              border: '1px solid var(--outline)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--on-surface)" strokeWidth="2">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/>
              </svg>
            </div>
            <div>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--on-surface)' }}>WeatherGuard AI</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--on-muted)' }}>
                {predictionContext?.prediction?.risk_level
                  ? `Context: ${predictionContext.location?.name} — ${predictionContext.prediction.risk_level} RISK`
                  : 'Disaster Safety Assistant'}
              </div>
            </div>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {messages.map((m, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
              }}>
                <div style={{
                  maxWidth: '82%', padding: '0.65rem 0.9rem',
                  borderRadius: m.role === 'user' ? '16px 16px 4px 16px' : '4px 16px 16px 16px',
                  background: m.role === 'user'
                    ? 'var(--accent)'
                    : 'var(--surface-hover)',
                  border: `1px solid var(--outline)`,
                  fontSize: '0.85rem', lineHeight: 1.55, color: m.role === 'user' ? '#fff' : 'var(--on-surface)',
                }}>
                  {m.text}
                  {m.engine && (
                    <div style={{ fontSize: '0.65rem', color: 'var(--on-muted)', marginTop: '0.4rem' }}>
                      Engine: {m.engine}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div style={{ display: 'flex', gap: '0.35rem', padding: '0.5rem' }}>
                {[0.1, 0.2, 0.3].map((d) => (
                  <div key={d} style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: 'var(--on-muted)',
                    animation: `pulse-dot 1.2s ${d}s infinite`,
                  }} />
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Quick prompts */}
          <div style={{ padding: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', borderTop: '1px solid var(--outline)' }}>
            {QUICK_PROMPTS.slice(0, 3).map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                disabled={loading}
                style={{
                  fontSize: '0.7rem', padding: '0.35rem 0.75rem', borderRadius: 20,
                  background: 'var(--surface-hover)', border: '1px solid var(--outline)',
                  color: 'var(--on-muted)', cursor: 'pointer',
                  transition: 'all 0.2s', whiteSpace: 'nowrap',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--on-surface)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--outline)'; e.currentTarget.style.color = 'var(--on-muted)'; }}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Input */}
          <div style={{
            padding: '0.75rem', borderTop: '1px solid var(--outline)',
            display: 'flex', gap: '0.5rem', background: 'var(--surface-card)',
          }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !loading && send()}
              placeholder="Ask about safety, risk, evacuation..."
              disabled={loading}
              style={{
                flex: 1, background: 'var(--surface)', border: '1px solid var(--outline)',
                borderRadius: 10, color: 'var(--on-surface)', fontSize: '0.85rem',
                padding: '0.55rem 0.9rem', outline: 'none', transition: 'border-color 0.2s',
              }}
              onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--outline)'}
            />
            <button
              onClick={() => send()}
              disabled={loading || !input.trim()}
              style={{
                width: 38, height: 38, borderRadius: 10, border: 'none',
                background: 'var(--accent)', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.2s', flexShrink: 0,
                opacity: (!input.trim() || loading) ? 0.4 : 1,
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
