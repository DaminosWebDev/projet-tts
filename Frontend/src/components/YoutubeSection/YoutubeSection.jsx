// components/YoutubeSection/YoutubeSection.jsx
import { useYoutube } from '../../hooks/useYoutube';
import './YoutubeSection.css';

const MOCK_WAVE = Array.from({ length: 40 }, () => Math.random() * 80 + 20);

export default function YoutubeSection() {
  const {
    url, setUrl, sourceLang, setSourceLang, targetLang, setTargetLang,
    status, progress, currentStep, videoId, audioUrl, errorMsg,
    isValidUrl, pasteUrl, startPipeline, reset,
  } = useYoutube();

  const urlClass = url
    ? isValidUrl ? 'url-input valid' : 'url-input invalid'
    : 'url-input';

  const handleDownload = () => {
    if (!audioUrl) return;
    const link = document.createElement('a');
    link.href = audioUrl;
    link.download = 'audio_translated.wav';
    link.click();
  };

  return (
    <section id="youtube" className="youtube-section">
      <div className="section-header">
        <div className="section-label red">Pipeline</div>
        <h2 className="section-title">YouTube Translation Pipeline</h2>
        <p className="section-sub">
          Dubbing automatique — de l'anglais au français en quelques minutes
        </p>
      </div>

      {/* URL input — visible seulement en état idle */}
      {status === 'idle' && (
        <div className="yt-input-block">
          <div className="url-input-row">
            <input
              type="text"
              className={urlClass}
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              aria-label="URL YouTube"
            />
            <button className="btn-paste" onClick={pasteUrl} aria-label="Coller depuis le presse-papier">
              Coller
            </button>
          </div>

          <div className="yt-options">
            <span className="select-label">Source :</span>
            <select className="custom-select" value={sourceLang} onChange={e => setSourceLang(e.target.value)}>
              <option value="auto">Détection auto</option>
              <option value="en">EN — English</option>
              <option value="fr">FR — Français</option>
              <option value="es">ES — Español</option>
            </select>

            <span className="select-label">Cible :</span>
            <select className="custom-select" value={targetLang} onChange={e => setTargetLang(e.target.value)}>
              <option value="fr">FR — Français</option>
              <option value="en">EN — English</option>
            </select>
          </div>

          <div className="yt-launch-row">
            <button
              className="btn-launch"
              disabled={!isValidUrl}
              onClick={startPipeline}
            >
              Lancer la traduction →
            </button>
          </div>
        </div>
      )}

      {/* Progression */}
      {status === 'loading' && (
        <div className="progress-block">
          <div className="progress-step-label">
            <span className="progress-dots">{currentStep || 'Initialisation'}</span>
          </div>
          <div className="progress-bar-row">
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <span className="progress-pct">{progress}%</span>
          </div>
        </div>
      )}

      {/* Erreur */}
      {status === 'error' && (
        <div style={{ maxWidth: '700px', margin: '0 auto', textAlign: 'center' }}>
          <div className="error-msg" style={{ marginBottom: '16px' }}>
            ⚠ {errorMsg}
          </div>
          <button className="btn-reset-small" onClick={reset}>
            Réessayer
          </button>
        </div>
      )}

      {/* Résultat */}
      {status === 'done' && (
        <div className="yt-result">
          {/* Iframe YouTube muet */}
          <div className="yt-iframe-wrap">
            {videoId ? (
              <iframe
                src={`https://www.youtube.com/embed/${videoId}?autoplay=0&mute=1`}
                title="YouTube video"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope"
                allowFullScreen
              />
            ) : (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: '100%', color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)', fontSize: '12px'
              }}>
                Vidéo non disponible
              </div>
            )}
          </div>

          {/* Player piste traduite */}
          <div className="yt-player-card">
            <div>
              <div className="yt-player-title">Piste audio traduite</div>
              <div className="yt-player-filename">audio_translated.wav</div>
            </div>

            {/* Player natif HTML5 */}
            {audioUrl && (
              <audio
                controls
                src={audioUrl}
                style={{
                  width: '100%',
                  height: '36px',
                  filter: 'invert(1) hue-rotate(180deg)',
                  borderRadius: '4px',
                }}
                aria-label="Piste audio traduite"
              />
            )}

            {/* Waveform décorative */}
            <div className="yt-player-wave" aria-hidden="true">
              {MOCK_WAVE.map((h, i) => (
                <div key={i} className="yt-wave-bar" style={{ height: `${h}%` }} />
              ))}
            </div>

            <button className="btn-download" onClick={handleDownload}>
              ⬇ Télécharger la piste audio (.wav)
            </button>
            <button className="btn-reset-small" onClick={reset}>
              Nouvelle traduction
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
