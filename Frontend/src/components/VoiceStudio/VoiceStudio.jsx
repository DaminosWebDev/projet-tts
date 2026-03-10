// components/VoiceStudio/VoiceStudio.jsx
import { useState } from 'react';
import TTSTab from './TTSTab';
import STTTab from './STTTab';
import './VoiceStudio.css';

export default function VoiceStudio() {
  const [activeTab, setActiveTab] = useState('tts');

  return (
    <section id="studio" className="studio-section">
      <div className="section-header">
        <div className="section-label">Voice Studio</div>
        <h2 className="section-title">Voice Studio</h2>
        <p className="section-sub">Synthèse et transcription vocale</p>
      </div>

      <div className="studio-tabs">
        <button
          className={`tab-btn${activeTab === 'tts' ? ' active' : ''}`}
          onClick={() => setActiveTab('tts')}
        >
          Text-to-Speech
        </button>
        <button
          className={`tab-btn${activeTab === 'stt' ? ' active' : ''}`}
          onClick={() => setActiveTab('stt')}
        >
          Speech-to-Text
        </button>
      </div>

      {activeTab === 'tts' ? <TTSTab /> : <STTTab />}
    </section>
  );
}
