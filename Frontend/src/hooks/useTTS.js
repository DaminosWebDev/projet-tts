// useTTS.js - Hook personnalisé pour toute la logique TTS
// Un "hook" c'est une fonction React qui gère des états et de la logique
// On sépare la logique du visuel : TTSForm.jsx s'occupe de l'affichage,
// useTTS.js s'occupe de ce qui se passe quand on clique sur les boutons

// useState : permet de créer des variables d'état qui déclenchent un re-rendu
// quand elles changent. Ex: quand audioUrl change, React re-affiche le composant
// useEffect : permet d'exécuter du code en réaction à des changements
// Ex: nettoyer le blob URL quand audioUrl change pour éviter les fuites mémoire
import { useState, useEffect } from 'react';

// On importe les fonctions API depuis notre fichier centralisé
// Comme ça si l'URL change, on ne touche qu'à api.js
import { generateTTS } from '../services/api';

// La convention des hooks React c'est de commencer par "use"
// React reconnaît ainsi que c'est un hook et applique ses règles internes
export function useTTS() {

    // ── États ──────────────────────────────────────────────────────────────

    // Le texte saisi par l'utilisateur dans le textarea
    // useState('') = valeur initiale vide
    const [text, setText] = useState('');

    // La langue choisie : "fr" ou "en"
    // Impacte les voix disponibles dans le sélecteur
    const [language, setLanguage] = useState('fr');

    // La voix sélectionnée : doit correspondre à la langue
    // ff_siwis = seule voix française disponible dans Kokoro
    const [voice, setVoice] = useState('ff_siwis');

    // La vitesse de lecture : 1.0 = normale, 0.5 = lent, 2.0 = rapide
    const [speed, setSpeed] = useState(1.0);

    // true quand la requête API est en cours
    // Permet de désactiver le bouton et afficher "Génération en cours..."
    const [loading, setLoading] = useState(false);

    // L'URL blob temporaire du fichier audio généré
    // Un blob URL ressemble à "blob:http://localhost:5173/abc123..."
    // C'est une URL locale dans le navigateur, pas sur le serveur
    const [audioUrl, setAudioUrl] = useState(null);

    // Le nom du fichier audio (ex: "audio_a3f8c2d1.wav")
    // Récupéré depuis le header HTTP "x-audio-filename" de la réponse
    // Utilisé pour nommer le fichier lors du téléchargement
    const [audioFilename, setAudioFilename] = useState(null);

    // Le message d'erreur à afficher si quelque chose plante
    // null = pas d'erreur, string = message d'erreur
    const [error, setError] = useState(null);

    // ── Effets ─────────────────────────────────────────────────────────────

    // Nettoyage des blob URLs pour éviter les fuites mémoire
    // Quand on génère un nouvel audio, l'ancien blob reste en mémoire
    // si on ne le libère pas explicitement avec revokeObjectURL
    // Ce useEffect s'exécute à chaque fois que audioUrl change
    // et libère l'ancienne URL avant d'en créer une nouvelle
    useEffect(() => {
        // La fonction retournée par useEffect est appelée au "cleanup"
        // c'est à dire juste avant que l'effet se relance ou que le
        // composant se démonte (disparaisse de l'écran)
        return () => {
            if (audioUrl) URL.revokeObjectURL(audioUrl);
            // URL.revokeObjectURL libère la mémoire allouée pour ce blob
        };
    }, [audioUrl]); // Dépendance : se relance uniquement quand audioUrl change

    // ── Fonctions ──────────────────────────────────────────────────────────

    // Fonction principale : génère l'audio en appelant l'API FastAPI
    const generate = async () => {

        // Validation côté frontend avant d'appeler l'API
        // On vérifie que le texte n'est pas vide ou que des espaces
        // trim() supprime les espaces au début et à la fin
        if (!text.trim()) {
            setError('Veuillez entrer du texte à synthétiser.');
            return; // On arrête ici, pas besoin d'appeler l'API
        }

        // On démarre le chargement et on réinitialise les états
        setLoading(true);
        setError(null);

        // On supprime l'ancien audio s'il existe
        // pour libérer la mémoire avant d'en créer un nouveau
        if (audioUrl) {
            URL.revokeObjectURL(audioUrl);
            setAudioUrl(null);
            setAudioFilename(null);
        }

        try {
            // Appel à notre fonction centralisée dans api.js
            // On lui passe les 4 paramètres nécessaires
            const response = await generateTTS({ text, language, voice, speed });

            // On récupère le nom du fichier depuis le header HTTP personnalisé
            // qu'on a ajouté dans FastAPI avec "X-Audio-Filename"
            const filename = response.headers['x-audio-filename'] || 'audio.wav';

            // On crée un blob à partir des données binaires reçues
            // Le blob c'est la représentation binaire du fichier WAV en mémoire
            const blob = new Blob([response.data], { type: 'audio/wav' });

            // On crée une URL temporaire locale pour que le player HTML puisse lire le blob
            // Sans cette URL le player ne saurait pas où chercher l'audio
            const url = URL.createObjectURL(blob);

            // On met à jour les états pour déclencher le re-rendu du composant
            setAudioUrl(url);
            setAudioFilename(filename);

        } catch (err) {
            // Gestion des erreurs : on essaie de lire le message d'erreur
            // renvoyé par FastAPI dans le body de la réponse
            // C'est complexe car la réponse est un blob (responseType: 'blob')
            // donc on doit d'abord le convertir en texte avec .text()
            let msg = 'Erreur inconnue';
            if (err.response?.data) {
                // L'opérateur ?. (optional chaining) évite les erreurs si
                // err.response est undefined : err.response?.data = undefined
                // plutôt que TypeError: Cannot read property 'data' of undefined
                try {
                    const textErr = await err.response.data.text();
                    msg = JSON.parse(textErr).detail || msg;
                    // JSON.parse convertit le texte JSON en objet JavaScript
                    // .detail c'est le champ qu'on utilise dans FastAPI pour les erreurs
                } catch {}
                // Le catch vide évite que l'erreur de parsing plante tout
            }
            setError(msg);

        } finally {
            // finally s'exécute TOUJOURS, que ça ait réussi ou planté
            // C'est l'endroit idéal pour arrêter le loading
            setLoading(false);
        }
    };

    // Fonction de téléchargement du fichier audio
    // On crée un lien HTML invisible, on lui donne l'URL blob et le nom du fichier
    // puis on simule un clic pour déclencher le téléchargement natif du navigateur
    const download = () => {
        if (!audioUrl || !audioFilename) return;
        const link = document.createElement('a');
        // createElement crée un élément HTML en mémoire sans l'ajouter au DOM
        link.href = audioUrl;       // L'URL blob de l'audio
        link.download = audioFilename; // Le nom suggéré pour le fichier téléchargé
        link.click();               // Simule le clic pour déclencher le téléchargement
        // Pas besoin d'ajouter le lien au DOM pour que ça fonctionne
    };

    // Fonction appelée quand l'utilisateur change de langue
    // On met à jour la langue ET on réinitialise la voix
    // car les voix disponibles sont différentes selon la langue
    const changeLanguage = (newLang) => {
        setLanguage(newLang);
        // On choisit automatiquement la première voix de la nouvelle langue
        // pour éviter d'avoir une voix française sélectionnée avec la langue anglaise
        const firstVoice = newLang === 'fr' ? 'ff_siwis' : 'af_heart';
        setVoice(firstVoice);
    };

    // ── Retour du hook ─────────────────────────────────────────────────────

    // On retourne tous les états et fonctions dont les composants auront besoin
    // C'est comme l'interface publique du hook
    // Les composants qui utilisent useTTS() pourront accéder à tout ça
    // via la déstructuration : const { text, setText, generate } = useTTS()
    return {
        // États
        text, setText,
        language, changeLanguage,
        voice, setVoice,
        speed, setSpeed,
        loading,
        audioUrl,
        audioFilename,
        error,
        // Fonctions
        generate,
        download,
    };
}