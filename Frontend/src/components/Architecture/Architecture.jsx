// components/Architecture/Architecture.jsx
import './Architecture.css';

const TECH_CARDS = [
  {
    icon: '🎤',
    name: 'Kokoro-82M',
    badge: 'IA Model',
    desc: 'Synthèse vocale FR/EN — 11 voix, 82M paramètres. Pipeline dédié par langue.',
  },
  {
    icon: '🎧',
    name: 'Faster-Whisper',
    badge: 'IA Model',
    desc: 'Transcription — modèle small pour STT, medium pour le pipeline YouTube.',
  },
  {
    icon: '🌐',
    name: 'LibreTranslate',
    badge: 'Infrastructure',
    desc: 'Traduction offline via Docker — jusqu\'à 80 segments en parallèle via asyncio.gather.',
  },
  {
    icon: '⚡',
    name: 'FastAPI',
    badge: 'API',
    desc: 'Framework async — 5 routers, JWT auth, Google OAuth 2.0, pipeline asynchrone.',
  },
  {
    icon: '🗄️',
    name: 'PostgreSQL',
    badge: 'Database',
    desc: 'SQLAlchemy async + Alembic — historique des jobs TTS, STT et YouTube par user.',
  },
  {
    icon: '🎬',
    name: 'ffmpeg + RubberBand',
    badge: 'Infrastructure',
    desc: 'Time-stretching pro + normalisation EBU R128 en 2 passes — ±0.1 LUFS de précision.',
  },
];

const STATS = [
  { value: '~2-5min', label: 'par vidéo' },
  { value: '99',      label: 'langues STT Whisper' },
  { value: '±0.1',    label: 'LUFS normalisation' },
];

export default function Architecture() {
  return (
    <section id="architecture" className="arch-section">
      <div className="section-header">
        <div className="section-label">Architecture</div>
        <h2 className="section-title">Under the Hood</h2>
        <p className="section-sub">Un backend FastAPI qui orchestre plusieurs modèles IA</p>
      </div>

      {/* Flow diagram */}
      <div className="flow-diagram">
        <div className="flow-box main">React + Vite</div>
        <div className="flow-arrow">→</div>

        <div className="flow-group">
          <div className="flow-box main">FastAPI</div>
          <div className="flow-arrow vert">↕</div>
          <div className="flow-box db">PostgreSQL</div>
        </div>

        <div className="flow-arrow">→</div>

        <div className="flow-models">
          <div className="flow-model">🎤 Kokoro-82M</div>
          <div className="flow-model">🎧 Faster-Whisper</div>
          <div className="flow-model">🌐 LibreTranslate</div>
          <div className="flow-model">🎬 ffmpeg + RubberBand</div>
        </div>
      </div>

      {/* Tech cards */}
      <div className="tech-grid">
        {TECH_CARDS.map((card) => (
          <div key={card.name} className="tech-card">
            <div className="tech-icon">{card.icon}</div>
            <div className="tech-header">
              <div className="tech-name">{card.name}</div>
              <span className="tech-badge">{card.badge}</span>
            </div>
            <p className="tech-desc">{card.desc}</p>
          </div>
        ))}
      </div>

      {/* Stats */}
      <div className="stats-row">
        {STATS.map((s) => (
          <div key={s.label} className="stat-card">
            <div className="stat-value">{s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="arch-footer">
        Damien — 2025 — FastAPI · Kokoro · Whisper · LibreTranslate
      </div>
    </section>
  );
}
