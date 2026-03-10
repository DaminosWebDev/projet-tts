// hooks/useTTS.js
import { useState, useEffect } from 'react';
import { generateTTS } from '../services/api';
import { useAuth } from '../context/AuthContext';

export function useTTS() {
  const { accessToken } = useAuth();

  const [text, setText]         = useState('');
  const [language, setLanguage] = useState('fr');
  const [voice, setVoice]       = useState('ff_siwis');
  const [speed, setSpeed]       = useState(1.0);
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState(null);

  const VOICES = {
    fr: ['ff_siwis'],
    en: ['af_heart','af_bella','af_sarah','af_sky','am_adam','am_michael','bf_emma','bf_isabella','bm_george','bm_lewis'],
  };

  useEffect(() => {
    return () => {
      if (result?.audioUrl) URL.revokeObjectURL(result.audioUrl);
    };
  }, [result]);

  const changeLanguage = (lang) => {
    setLanguage(lang);
    setVoice(VOICES[lang][0]);
  };

  const generate = async () => {
    if (!text.trim()) {
      setError('Veuillez entrer du texte à synthétiser.');
      return;
    }

    if (result?.audioUrl) URL.revokeObjectURL(result.audioUrl);

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // accessToken passé au backend — sauvegarde l'historique si connecté
      const data = await generateTTS({ text, language, voice, speed }, accessToken);
      setResult(data);
    } catch (e) {
      setError(e.message || 'Erreur lors de la génération audio.');
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!result?.audioUrl) return;
    const link = document.createElement('a');
    link.href = result.audioUrl;
    link.download = result.filename;
    link.click();
  };

  const copyText = () => {
    if (text) navigator.clipboard.writeText(text);
  };

  return {
    text, setText,
    language, changeLanguage,
    voice, setVoice,
    speed, setSpeed,
    loading, result, error,
    generate, download, copyText,
    VOICES,
  };
}