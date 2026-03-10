// components/History/HistoryPanel.jsx
// Panneau latéral coulissant — historique TTS / STT / YouTube de l'utilisateur

import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiGetHistory } from '../../services/api';
import './History.css';

// ── Helpers ───────────────────────────────────────────────────────────────────

const formatDate = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

const StatusBadge = ({ status }) => {
  const cls = status === 'done' ? 'done' : status === 'error' ? 'error' : 'pending';
  const labels = { done: '✓ Terminé', error: '✕ Erreur', pending: '⟳ En cours' };
  return <span className={`card-status ${cls}`}>{labels[status] || status}</span>;
};

// ── Cartes par type ───────────────────────────────────────────────────────────

function YouTubeCard({ job }) {
  return (
    <div className="history-card">
      <div className="card-top">
        <div className="card-title">
          {job.video_title || job.youtube_url}
        </div>
        <StatusBadge status={job.status} />
      </div>
      <div className="card-meta">
        {job.source_language && (
          <span className="card-tag">{job.source_language.toUpperCase()} → {job.target_language.toUpperCase()}</span>
        )}
        {job.video_id && (
          <a
            href={`https://youtube.com/watch?v=${job.video_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="card-tag"
            style={{ color: 'var(--accent-blue)', textDecoration: 'none' }}
          >
            ▶ Voir la vidéo
          </a>
        )}
        {job.audio_url && job.status === 'done' && (
          <a
            href={job.audio_url}
            download
            className="card-tag"
            style={{ color: 'var(--accent-green)', textDecoration: 'none' }}
          >
            ⬇ Audio
          </a>
        )}
      </div>
      <div className="card-date">{formatDate(job.created_at)}</div>
    </div>
  );
}

function TTSCard({ job }) {
  const preview = job.input_text?.length > 80
    ? job.input_text.slice(0, 80) + '…'
    : job.input_text;

  return (
    <div className="history-card">
      <div className="card-top">
        <div className="card-title">"{preview}"</div>
        {job.audio_url && (
          <a
            href={job.audio_url}
            download
            className="card-tag"
            style={{ color: 'var(--accent-green)', textDecoration: 'none', flexShrink: 0 }}
          >
            ⬇ WAV
          </a>
        )}
      </div>
      <div className="card-meta">
        <span className="card-tag">{job.language?.toUpperCase()}</span>
        <span className="card-tag">{job.voice}</span>
      </div>
      <div className="card-date">{formatDate(job.created_at)}</div>
    </div>
  );
}

function STTCard({ job }) {
  const preview = job.transcription_text?.length > 80
    ? job.transcription_text.slice(0, 80) + '…'
    : job.transcription_text;

  return (
    <div className="history-card">
      <div className="card-top">
        <div className="card-title">
          {preview || <span style={{ color: 'var(--text-muted)' }}>{job.filename}</span>}
        </div>
      </div>
      <div className="card-meta">
        <span className="card-tag">📁 {job.filename}</span>
        {job.detected_language && (
          <span className="card-tag">{job.detected_language.toUpperCase()}</span>
        )}
      </div>
      <div className="card-date">{formatDate(job.created_at)}</div>
    </div>
  );
}

// ── Composant principal ───────────────────────────────────────────────────────

export default function HistoryPanel({ onClose }) {
  const { accessToken } = useAuth();
  const [tab, setTab]       = useState('tts');
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const result = await apiGetHistory(accessToken);
        setData(result);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [accessToken]);

  // Ferme au clic sur l'overlay (pas sur le panel)
  const onOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  const tabs = [
    { key: 'tts',     label: 'TTS',     icon: '🔊', count: data?.tts?.length ?? 0 },
    { key: 'stt',     label: 'STT',     icon: '🎙',  count: data?.stt?.length ?? 0 },
    { key: 'youtube', label: 'YouTube', icon: '▶',  count: data?.youtube?.length ?? 0 },
  ];

  const items = data?.[tab] ?? [];

  return (
    <div className="history-overlay" onClick={onOverlayClick}>
      <div className="history-panel">

        {/* Header */}
        <div className="history-header">
          <div className="history-title">
            <span className="history-title-text">Historique</span>
            {data && (
              <span className="history-badge">{data.total} job{data.total !== 1 ? 's' : ''}</span>
            )}
          </div>
          <button className="history-close" onClick={onClose} aria-label="Fermer">×</button>
        </div>

        {/* Tabs */}
        <div className="history-tabs">
          {tabs.map(t => (
            <button
              key={t.key}
              className={`history-tab${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.icon} {t.label}
              <span className="tab-count">{t.count}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="history-content">
          {loading && (
            <div className="history-loading">
              <div className="spinner" />
              Chargement...
            </div>
          )}

          {error && (
            <div className="history-empty">
              <div className="history-empty-icon">⚠</div>
              <div className="history-empty-text">{error}</div>
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="history-empty">
              <div className="history-empty-icon">
                {tab === 'tts' ? '🔊' : tab === 'stt' ? '🎙' : '▶'}
              </div>
              <div className="history-empty-text">
                Aucun job {tab.toUpperCase()} pour l'instant.<br />
                Vos générations apparaîtront ici.
              </div>
            </div>
          )}

          {!loading && !error && items.map((job) => (
            <div key={job.id}>
              {tab === 'tts'     && <TTSCard     job={job} />}
              {tab === 'stt'     && <STTCard     job={job} />}
              {tab === 'youtube' && <YouTubeCard job={job} />}
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}
