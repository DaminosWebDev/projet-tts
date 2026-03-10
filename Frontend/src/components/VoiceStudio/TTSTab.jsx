// components/VoiceStudio/TTSTab.jsx
import { useRef, useState, useEffect } from 'react';
import { useTTS } from '../../hooks/useTTS';

const MAX = 2000;
const WAVE = Array.from({ length: 30 }, () => Math.random() * 80 + 20);

export default function TTSTab() {
  const {
    text, setText, language, changeLanguage,
    voice, setVoice, speed, setSpeed,
    loading, result, error,
    generate, download, copyText,
    VOICES,
  } = useTTS();

  // Lecteur audio natif HTML5
  const audioRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  // Reset player quand un nouveau résultat arrive
  useEffect(() => {
    setPlaying(false);
    setAudioProgress(0);
    setCurrentTime(0);
    setDuration(0);
  }, [result]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setPlaying(p => !p);
  };

  const onTimeUpdate = () => {
    if (!audioRef.current) return;
    const cur = audioRef.current.currentTime;
    const dur = audioRef.current.duration || 0;
    setCurrentTime(cur);
    setDuration(dur);
    setAudioProgress(dur ? (cur / dur) * 100 : 0);
  };

  const onEnded = () => setPlaying(false);

  const formatTime = (s) => {
    if (!s || isNaN(s)) return '0:00';
    const m = Math.floor(s / 60);
    return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  };

  const seekTo = (e) => {
    if (!audioRef.current || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    audioRef.current.currentTime = ratio * duration;
  };

  const charCount = text.length;

  return (
    <div className="tts-layout">
      {/* Left — inputs */}
      <div>
        <div className="tts-textarea-wrap">
          <textarea
            className="tts-textarea"
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Entrez votre texte ici..."
            maxLength={MAX}
            aria-label="Texte à synthétiser"
          />
          <span className={`char-counter${charCount > 1800 ? ' warn' : ''}`}>
            {charCount} / {MAX}
          </span>
        </div>

        <div className="tts-controls">
          <div className="control-group">
            <span className="control-label">Langue</span>
            <select
              className="custom-select"
              value={language}
              onChange={e => changeLanguage(e.target.value)}
            >
              <option value="fr">Français</option>
              <option value="en">English</option>
            </select>
          </div>

          <div className="control-group">
            <span className="control-label">Voix</span>
            <select
              className="custom-select"
              value={voice}
              onChange={e => setVoice(e.target.value)}
            >
              {VOICES[language].map(v => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>

          <div className="control-group">
            <span className="control-label">Vitesse</span>
            <div className="slider-row">
              <input
                type="range"
                min={0.5} max={2.0} step={0.1}
                value={speed}
                onChange={e => setSpeed(parseFloat(e.target.value))}
                aria-label="Vitesse de lecture"
              />
              <span className="slider-value">{speed.toFixed(1)}×</span>
            </div>
          </div>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <button
          className="btn-generate"
          onClick={generate}
          disabled={loading || !text.trim()}
        >
          {loading
            ? <><div className="spinner" /> Génération en cours...</>
            : '⚡ Générer l\'audio'}
        </button>
      </div>

      {/* Right — player */}
      <div className="player-card">
        {!result ? (
          <div className="player-empty">
            <div className="player-empty-icon">🎵</div>
            <div className="player-empty-text">
              {loading
                ? 'Synthèse en cours...'
                : 'L\'audio apparaîtra ici\naprès la génération'}
            </div>
          </div>
        ) : (
          <div className="player-ready">
            {/* Lecteur HTML5 caché — géré manuellement */}
            <audio
              ref={audioRef}
              src={result.audioUrl}
              onTimeUpdate={onTimeUpdate}
              onEnded={onEnded}
              onLoadedMetadata={onTimeUpdate}
            />

            <div className="player-filename">{result.filename}</div>

            {/* Waveform décorative */}
            <div className="player-waveform" aria-hidden="true">
              {WAVE.map((h, i) => (
                <div key={i} className="p-wave-bar" style={{ height: `${h}%`, opacity: playing ? 0.9 : 0.4 }} />
              ))}
            </div>

            {/* Contrôles player */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {/* Barre de progression clickable */}
              <div
                className="progress-track"
                style={{ cursor: 'pointer', height: '4px' }}
                onClick={seekTo}
                role="slider"
                aria-label="Progression audio"
                aria-valuenow={Math.round(audioProgress)}
              >
                <div className="progress-fill" style={{ width: `${audioProgress}%`, background: 'var(--accent-blue)' }} />
              </div>

              {/* Timer + bouton play */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>
                <button
                  onClick={togglePlay}
                  style={{
                    background: 'var(--accent-blue)',
                    border: 'none',
                    borderRadius: '50%',
                    width: '36px',
                    height: '36px',
                    cursor: 'pointer',
                    fontSize: '14px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: playing ? '0 0 16px var(--accent-blue-glow)' : 'none',
                    transition: 'box-shadow 0.2s',
                  }}
                  aria-label={playing ? 'Pause' : 'Play'}
                >
                  {playing ? '⏸' : '▶'}
                </button>
              </div>
            </div>

            <div className="player-actions">
              <button className="btn-action" onClick={download}>
                ⬇ Télécharger .wav
              </button>
              <button className="btn-action" onClick={copyText}>
                📋 Copier le texte
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
