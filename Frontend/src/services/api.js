// services/api.js
// Tous les appels API — backend FastAPI localhost:8000

export const API_URL = 'http://localhost:8000';

// ─── Helper authentifié ───────────────────────────────────────────────────────

export const authFetch = async (url, options = {}, token) => {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Erreur ${response.status}`);
  }

  return response.json();
};

// ─── AUTH ─────────────────────────────────────────────────────────────────────

export const apiRegister = ({ email, password }) =>
  authFetch(`${API_URL}/auth/register`, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
// → { message, email }

export const apiLogin = ({ email, password }) =>
  authFetch(`${API_URL}/auth/login`, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
// → { access_token, refresh_token, token_type }

export const apiRefreshToken = (refreshToken) =>
  authFetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
// → { access_token, refresh_token, token_type }

export const apiGetMe = (token) =>
  authFetch(`${API_URL}/auth/me`, {}, token);
// → { id, email, is_verified, avatar_url, created_at }

export const apiForgotPassword = ({ email }) =>
  authFetch(`${API_URL}/auth/forgot-password`, {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
// → { message }

export const apiResetPassword = ({ token, new_password }) =>
  authFetch(`${API_URL}/auth/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ token, new_password }),
  });
// → { message }

export const apiVerifyEmail = (token) =>
  authFetch(`${API_URL}/auth/verify-email?token=${token}`);
// → { access_token, refresh_token, token_type }

// Redirige vers le backend qui redirige vers Google OAuth
export const apiGoogleLogin = () => {
  window.location.href = `${API_URL}/auth/google`;
};

export const apiGetHistory = (token) =>
  authFetch(`${API_URL}/users/me/history`, {}, token);

// ─── TTS ──────────────────────────────────────────────────────────────────────

export const generateTTS = async ({ text, language, voice, speed }, token) => {
  const response = await fetch(`${API_URL}/tts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ text, language, voice, speed }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur lors de la génération TTS');
  }

  const blob = await response.blob();
  const filename = response.headers.get('x-audio-filename') || 'audio.wav';
  const audioUrl = URL.createObjectURL(blob);
  return { filename, audioUrl };
};

export const fetchVoices = async () => {
  const response = await fetch(`${API_URL}/voices`);
  if (!response.ok) throw new Error('Impossible de récupérer les voix');
  const data = await response.json();
  return data.voices || data;
};

// ─── STT ──────────────────────────────────────────────────────────────────────

export const uploadAudioSTT = async (file, language = 'auto', token) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('language', language);

  const response = await fetch(`${API_URL}/stt/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur pendant la transcription');
  }
  return response.json();
};

export const recordAudioSTT = async (blob, language = 'auto', token) => {
  // Utilise le mimeType réel du blob enregistré par MediaRecorder
  const mimeType = blob.type || 'audio/webm';
  const ext = mimeType.includes('ogg') ? '.ogg' : '.webm';
  const file = new File([blob], `recording${ext}`, { type: mimeType });

  const formData = new FormData();
  formData.append('file', file);
  formData.append('language', language);

  const response = await fetch(`${API_URL}/stt/record`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur pendant la transcription');
  }
  return response.json();
};

// ─── YOUTUBE ──────────────────────────────────────────────────────────────────

export const startYouTubePipeline = async ({ url, source_language, target_language }, token) => {
  const response = await fetch(`${API_URL}/youtube/process`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      url,
      source_language: source_language === 'auto' ? null : source_language,
      target_language,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur au lancement du pipeline');
  }
  return response.json();
};

export const fetchYouTubeStatus = async (jobId) => {
  const response = await fetch(`${API_URL}/youtube/status/${jobId}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Erreur lors du polling');
  }
  return response.json();
};

export const getYouTubeAudioUrl = (jobId) => `${API_URL}/youtube/audio/${jobId}`;