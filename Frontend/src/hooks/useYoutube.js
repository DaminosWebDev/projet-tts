// hooks/useYoutube.js
import { useState, useRef } from 'react';
import { startYouTubePipeline, fetchYouTubeStatus, getYouTubeAudioUrl } from '../services/api';
import { useAuth } from '../context/AuthContext';

const YOUTUBE_REGEX = /^(https?:\/\/)?(www\.)?(youtube\.com\/(watch\?v=|shorts\/)|youtu\.be\/)[\w-]{11}/;

const STEP_LABELS = {
  B_download:   'B — Téléchargement audio',
  C_transcribe: 'C — Transcription Whisper',
  D_translate:  'D — Traduction LibreTranslate',
  E_tts:        'E — Synthèse vocale Kokoro',
  F_stretch:    'F — Time-stretching ffmpeg',
  G_assemble:   'G+H — Assemblage + Loudnorm',
};

export function useYoutube() {
  const { accessToken } = useAuth();

  const [url, setUrl]               = useState('');
  const [sourceLang, setSourceLang] = useState('auto');
  const [targetLang, setTargetLang] = useState('fr');
  const [status, setStatus]         = useState('idle');
  const [progress, setProgress]     = useState(0);
  const [currentStep, setCurrentStep] = useState('');
  const [videoId, setVideoId]       = useState(null);
  const [audioUrl, setAudioUrl]     = useState(null);
  const [errorMsg, setErrorMsg]     = useState(null);

  const pollingRef = useRef(null);

  const isValidUrl = YOUTUBE_REGEX.test(url);

  const pasteUrl = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setUrl(text);
    } catch {}
  };

  const startPipeline = async () => {
    if (!isValidUrl) return;

    setStatus('loading');
    setProgress(0);
    setCurrentStep('Initialisation...');
    setErrorMsg(null);
    setVideoId(null);
    setAudioUrl(null);

    try {
      // accessToken passé — historique sauvegardé si connecté
      const { job_id } = await startYouTubePipeline({
        url,
        source_language: sourceLang,
        target_language: targetLang,
      }, accessToken);

      pollingRef.current = setInterval(async () => {
        try {
          const data = await fetchYouTubeStatus(job_id);

          setProgress(data.progress || 0);
          setCurrentStep(STEP_LABELS[data.current_step] || data.current_step || '');

          if (data.status === 'done') {
            clearInterval(pollingRef.current);
            setStatus('done');
            setVideoId(data.video_id || null);
            setAudioUrl(getYouTubeAudioUrl(job_id));
          } else if (data.status === 'error') {
            clearInterval(pollingRef.current);
            setStatus('error');
            setErrorMsg(data.error || 'Une erreur est survenue pendant le pipeline.');
          }
        } catch (err) {
          clearInterval(pollingRef.current);
          setStatus('error');
          setErrorMsg('Erreur réseau pendant le suivi du job.');
        }
      }, 2000);

    } catch (err) {
      setStatus('error');
      setErrorMsg(err.message || 'Erreur au lancement du pipeline.');
    }
  };

  const reset = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    setUrl('');
    setStatus('idle');
    setProgress(0);
    setCurrentStep('');
    setVideoId(null);
    setAudioUrl(null);
    setErrorMsg(null);
  };

  return {
    url, setUrl,
    sourceLang, setSourceLang,
    targetLang, setTargetLang,
    status, progress, currentStep,
    videoId, audioUrl, errorMsg,
    isValidUrl,
    pasteUrl, startPipeline, reset,
  };
}