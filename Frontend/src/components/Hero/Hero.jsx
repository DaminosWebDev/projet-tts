// components/Hero/Hero.jsx
import './Hero.css';

const WAVE_BARS = Array.from({ length: 80 }, (_, i) => ({
  height: Math.random() * 80 + 20,
  dur:    `${0.6 + Math.random() * 1.4}s`,
  delay:  `${Math.random() * 1.5}s`,
}));

export default function Hero() {
  const scrollToYoutube = () => {
    document.getElementById('youtube')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section id="hero" className="hero">
      <div className="hero-content">
        <div className="hero-eyebrow">AI Voice Processing Platform</div>

        <h1 className="hero-title">
          <span>VoxBridge</span>
        </h1>

        <div className="hero-tagline">
          <span className="tagline-word">Transcribe</span>
          <span className="tagline-sep">·</span>
          <span className="tagline-word">Translate</span>
          <span className="tagline-sep">·</span>
          <span className="tagline-word">Synthesize</span>
        </div>

        <p className="hero-desc">
          Une plateforme IA qui transforme votre voix en texte,
          traduit des vidéos YouTube et génère de l'audio naturel depuis du texte.
        </p>

        <div className="hero-badges">
          <span className="badge">🎙️ Kokoro-82M TTS</span>
          <span className="badge">🎧 Faster-Whisper STT</span>
          <span className="badge">🌐 LibreTranslate</span>
        </div>

        <div className="hero-cta">
          <button className="btn-primary" onClick={scrollToYoutube}>
            Essayer maintenant →
          </button>
        </div>
      </div>

      {/* Waveform decoration */}
      <div className="waveform" aria-hidden="true">
        {WAVE_BARS.map((bar, i) => (
          <div
            key={i}
            className="wave-bar"
            style={{
              height: `${bar.height}%`,
              '--dur': bar.dur,
              '--delay': bar.delay,
            }}
          />
        ))}
      </div>
    </section>
  );
}
