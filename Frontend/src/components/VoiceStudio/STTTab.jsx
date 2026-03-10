// components/VoiceStudio/STTTab.jsx
import { useRef, useState } from 'react';
import { useSTT } from '../../hooks/useSTT';

const MIC_BARS = Array.from({ length: 24 }, () => ({
  h: Math.random() * 60 + 20,
  dur: `${0.4 + Math.random() * 0.8}s`,
  delay: `${Math.random() * 0.6}s`,
}));

const LANG_FLAGS = { en: '🇬🇧', fr: '🇫🇷', de: '🇩🇪', es: '🇪🇸', it: '🇮🇹', ja: '🇯🇵' };

function formatTime(s) {
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, '0')}`;
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function STTTab() {
  const {
    mode, setMode,
    transcript, loading, error,
    isRecording, recordTime,
    language, setLanguage,
    selectedFile, handleFileSelect, handleUpload,
    startRecording, stopRecording, copyTranscript,
  } = useSTT();

  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  return (
    <div className="stt-layout">
      {/* Mode toggle */}
      <div className="mode-toggle">
        <button
          className={`mode-btn${mode === 'upload' ? ' active' : ''}`}
          onClick={() => setMode('upload')}
        >
          📁 Fichier audio
        </button>
        <button
          className={`mode-btn${mode === 'mic' ? ' active' : ''}`}
          onClick={() => setMode('mic')}
        >
          🎙️ Microphone
        </button>
      </div>

      {/* Upload mode */}
      {mode === 'upload' && (
        <>
          {!selectedFile ? (
            <div
              className={`dropzone${dragOver ? ' drag-over' : ''}`}
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileRef.current?.click()}
              role="button"
              tabIndex={0}
              aria-label="Zone de dépôt de fichier audio"
            >
              <div className="dropzone-icon">🎵</div>
              <div className="dropzone-text">Glissez un fichier audio ici</div>
              <div className="dropzone-hint">WAV · MP3 · OGG · WebM · M4A — 25 MB max</div>
              <input
                ref={fileRef}
                type="file"
                accept=".wav,.mp3,.ogg,.webm,.m4a,audio/*"
                style={{ display: 'none' }}
                onChange={e => handleFileSelect(e.target.files[0])}
              />
            </div>
          ) : (
            <div className="file-selected">
              <span className="file-icon">🎵</span>
              <div>
                <div style={{ color: 'var(--text-primary)' }}>{selectedFile.name}</div>
                <div style={{ fontSize: '11px', marginTop: '2px' }}>{formatSize(selectedFile.size)}</div>
              </div>
              <button
                onClick={() => handleFileSelect(null)}
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px' }}
                aria-label="Supprimer le fichier"
              >×</button>
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '16px' }}>
            <span className="select-label">Langue :</span>
            <select className="custom-select" value={language} onChange={e => setLanguage(e.target.value)}>
              <option value="auto">Détection automatique</option>
              <option value="fr">Français</option>
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="de">Deutsch</option>
            </select>
          </div>

          <button
            className="btn-transcribe"
            disabled={!selectedFile || loading}
            onClick={handleUpload}
          >
            {loading
              ? <><div className="spinner" /> Transcription en cours...</>
              : '🔤 Transcrire'}
          </button>
        </>
      )}

      {/* Mic mode */}
      {mode === 'mic' && (
        <div className="mic-area">
          <button
            className={`btn-record${isRecording ? ' recording' : ''}`}
            onClick={isRecording ? stopRecording : startRecording}
          >
            {isRecording ? '⏹ Arrêter et transcrire' : '🎙️ Démarrer l\'enregistrement'}
          </button>

          {isRecording && (
            <>
              <div className="record-timer">{formatTime(recordTime)}</div>
              <div className="mic-wave" aria-hidden="true">
                {MIC_BARS.map((b, i) => (
                  <div
                    key={i}
                    className="mic-bar"
                    style={{ height: `${b.h}%`, '--dur': b.dur, '--delay': b.delay }}
                  />
                ))}
              </div>
            </>
          )}

          {loading && !isRecording && (
            <div style={{ marginTop: '20px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)' }}>
              Transcription en cours...
            </div>
          )}
        </div>
      )}

      {/* Error */}
      {error && <div className="error-msg" style={{ marginTop: '12px' }}>{error}</div>}

      {/* Result */}
      {transcript && (
        <div className="transcript-block">
          <div className="transcript-header">
            <span className="transcript-label">Transcription</span>
            <button className="btn-copy" onClick={copyTranscript}>
              📋 Copier
            </button>
          </div>

          <textarea
            className="transcript-text"
            readOnly
            value={transcript.text}
            aria-label="Résultat de la transcription"
          />

          <div className="transcript-meta">
            <span className="meta-item">
              Langue : <strong>
                {LANG_FLAGS[transcript.language] || '🌐'} {(transcript.language ?? '?').toUpperCase()}
                {transcript.language_probability != null && ` (${Math.round(transcript.language_probability * 100)}%)`}
              </strong>
            </span>
            <span className="meta-item">
              Durée : <strong>{transcript.duration != null ? `${parseFloat(transcript.duration).toFixed(1)}s` : '—'}</strong>
            </span>
            <span className="meta-item">
              Segments : <strong>{Array.isArray(transcript.segments) ? transcript.segments.length : transcript.segments ?? 0}</strong>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
