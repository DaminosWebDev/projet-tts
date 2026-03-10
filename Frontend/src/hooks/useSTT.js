// hooks/useSTT.js
import { useState, useRef } from 'react';
import { uploadAudioSTT, recordAudioSTT } from '../services/api';
import { useAuth } from '../context/AuthContext';

export function useSTT() {
  const { accessToken } = useAuth();

  const [mode, setMode]             = useState('upload');
  const [transcript, setTranscript] = useState(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [language, setLanguage]     = useState('auto');
  const [recordTime, setRecordTime] = useState(0);
  const [selectedFile, setSelectedFile] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef   = useRef([]);
  const timerRef         = useRef(null);

  const handleFileSelect = (file) => {
    if (!file) return;
    setSelectedFile(file);
    setTranscript(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setError(null);
    setTranscript(null);
    try {
      // accessToken passé — historique sauvegardé si connecté
      const result = await uploadAudioSTT(selectedFile, language, accessToken);
      setTranscript(result);
    } catch (e) {
      setError(e.message || 'Erreur pendant la transcription.');
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Essaie plusieurs formats selon ce que le navigateur supporte
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : '';

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];
      setRecordTime(0);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        clearInterval(timerRef.current);
        // Arrête tous les tracks pour libérer le micro
        stream.getTracks().forEach(t => t.stop());

        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        setLoading(true);
        setError(null);
        setTranscript(null);
        try {
          // Envoie vers /stt/record avec le token
          const result = await recordAudioSTT(blob, language, accessToken);
          setTranscript(result);
        } catch (e) {
          setError(e.message || 'Erreur pendant la transcription.');
        } finally {
          setLoading(false);
        }
      };

      recorder.start();
      setIsRecording(true);
      timerRef.current = setInterval(() => setRecordTime(t => t + 1), 1000);
    } catch (e) {
      setError('Impossible d\'accéder au microphone : ' + e.message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const copyTranscript = () => {
    if (transcript?.text) navigator.clipboard.writeText(transcript.text);
  };

  return {
    mode, setMode,
    transcript, loading, error,
    isRecording, recordTime,
    language, setLanguage,
    selectedFile,
    handleFileSelect, handleUpload,
    startRecording, stopRecording,
    copyTranscript,
  };
}