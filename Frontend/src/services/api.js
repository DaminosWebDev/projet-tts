// api.js - Toutes les fonctions Axios centralisées
// Si l'URL de l'API change, on ne modifie que ce fichier
// Principe de responsabilité unique : ce fichier ne fait QUE parler à l'API

// axios est une librairie HTTP qui simplifie les requêtes vers le backend
// Elle gère automatiquement : la conversion JSON, les headers, les erreurs HTTP
// Alternative native : fetch(), mais axios est plus lisible et plus pratique
import axios from 'axios';

// L'URL de base du backend FastAPI
// On la définit ici UNE SEULE FOIS pour tout le projet
// En production on changera juste cette ligne pour pointer vers le vrai serveur
// export = on rend cette variable accessible depuis les autres fichiers
export const API_URL = 'http://localhost:8000';

// ===========================================================================
// TTS (Text-to-Speech)
// ===========================================================================

// Génère un fichier audio à partir d'un texte
// Paramètres : objet avec text, language, voice, speed
// Retourne : la réponse axios complète (avec headers + data blob)
// On retourne la réponse COMPLÈTE car on a besoin des headers
// pour récupérer le nom du fichier (x-audio-filename)
export const generateTTS = async ({ text, language, voice, speed }) => {
    const response = await axios.post(
        `${API_URL}/tts`,       // URL de l'endpoint
        { text, language, voice, speed }, // Body de la requête en JSON
        { responseType: 'blob' } // Très important : on attend un fichier binaire
                                 // Sans ça axios essaierait de parser l'audio en JSON → plantage
    );
    return response;
    // On retourne response et pas response.data car on a besoin
    // de response.headers pour récupérer le nom du fichier audio
};

// Récupère la liste des voix disponibles par langue
// Retourne : { fr: ["ff_siwis"], en: ["af_heart", ...] }
export const fetchVoices = async () => {
    const response = await axios.get(`${API_URL}/voices`);
    return response.data;
    // Ici on retourne response.data directement car on n'a pas besoin des headers
};

// ===========================================================================
// STT (Speech-to-Text)
// ===========================================================================

// Transcrit un fichier audio uploadé par l'utilisateur
// Paramètres :
// - file     : l'objet File sélectionné par l'utilisateur (input type="file")
// - language : "fr", "en", ou "auto" pour détection automatique
// Retourne : { success, text, language, language_probability, segments, duration }
export const uploadAudioSTT = async (file, language = 'auto') => {

    // FormData est l'objet JavaScript pour envoyer des fichiers via HTTP
    // C'est l'équivalent d'un formulaire HTML avec enctype="multipart/form-data"
    // On ne peut pas envoyer un fichier en JSON simple, il faut du multipart
    const formData = new FormData();
    formData.append('file', file);         // Le fichier audio → champ "file" attendu par FastAPI
    formData.append('language', language); // La langue → champ "language" attendu par FastAPI

    const response = await axios.post(
        `${API_URL}/stt/upload`,
        formData,
        {
            headers: {
                'Content-Type': 'multipart/form-data'
                // On spécifie le type multipart pour que le serveur sache
                // qu'il va recevoir un fichier et pas du JSON
            }
        }
    );
    return response.data;
    // Ici on retourne response.data car la réponse est du JSON
    // (pas un blob comme pour le TTS)
};

// Transcrit un audio enregistré depuis le microphone du navigateur
// Paramètres :
// - blob     : l'objet Blob créé par MediaRecorder (enregistrement micro)
// - language : "fr", "en", ou "auto"
// Retourne : { success, text, language, language_probability, segments, duration }
export const recordAudioSTT = async (blob, language = 'auto') => {

    // On convertit le Blob en File pour pouvoir lui donner un nom
    // MediaRecorder produit un Blob sans nom, FastAPI a besoin d'un File avec un nom
    // new File([blob], nom, options) = crée un File à partir d'un Blob
    const file = new File([blob], 'voice.webm', { type: 'audio/webm' });
    // 'voice.webm' = nom du fichier (arbitraire mais avec la bonne extension)
    // 'audio/webm' = format produit par MediaRecorder dans la plupart des navigateurs

    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);

    const response = await axios.post(`${API_URL}/stt/record`, formData);
    // Pas besoin de spécifier Content-Type ici, axios le détecte automatiquement
    // quand on passe un FormData
    return response.data;
};

// Récupère la liste des langues supportées par Faster-Whisper
// Retourne : [{ code: "fr", label: "Français" }, ...]
export const fetchSTTLanguages = async () => {
    const response = await axios.get(`${API_URL}/stt/languages`);
    return response.data;
};