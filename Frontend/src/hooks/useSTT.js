// useSTT.js - Hook personnalisé pour toute la logique STT
// Même principe que useTTS.js : on sépare la logique du visuel
// Les composants STT n'auront qu'à appeler ce hook sans se soucier
// de comment fonctionne l'API ou le microphone

// useState : variables d'état qui déclenchent un re-rendu quand elles changent
// useRef : variables persistantes qui NE déclenchent PAS de re-rendu
// On utilise useRef pour MediaRecorder et les chunks audio car on n'a pas
// besoin de re-afficher l'interface quand ces valeurs changent
import { useState, useRef } from 'react';

// Nos fonctions API centralisées
// uploadAudioSTT = pour les fichiers uploadés depuis le PC
// recordAudioSTT = pour les enregistrements depuis le micro
import { uploadAudioSTT, recordAudioSTT } from '../services/api';

export function useSTT() {

    // ── États ──────────────────────────────────────────────────────────────

    // Le mode actif : 'upload' (fichier) ou 'record' (micro)
    // Détermine quel panneau afficher dans l'interface
    const [mode, setMode] = useState('upload');

    // Le texte transcrit retourné par Faster-Whisper
    // Vide au départ, rempli après une transcription réussie
    const [transcript, setTranscript] = useState('');

    // true quand la transcription est en cours
    // Permet de désactiver les boutons et d'afficher un message de chargement
    const [loading, setLoading] = useState(false);

    // Le message d'erreur à afficher si quelque chose plante
    // null = pas d'erreur
    const [error, setError] = useState(null);

    // true quand le microphone est en train d'enregistrer
    // Permet de changer l'apparence du bouton (rouge + animation pulse)
    const [isRecording, setIsRecording] = useState(false);

    // La langue choisie pour la transcription
    // "auto" = Faster-Whisper détecte automatiquement la langue
    const [language, setLanguage] = useState('auto');

    // ── Références (useRef) ────────────────────────────────────────────────

    // L'instance de MediaRecorder qui gère l'enregistrement micro
    // On utilise useRef et pas useState car :
    // 1. On n'a pas besoin de re-afficher l'interface quand elle change
    // 2. On doit pouvoir y accéder depuis plusieurs fonctions (start/stop)
    // 3. Sa valeur persiste entre les re-rendus contrairement à une variable normale
    const mediaRecorderRef = useRef(null);

    // Tableau qui accumule les morceaux (chunks) audio pendant l'enregistrement
    // MediaRecorder envoie l'audio par morceaux via l'événement ondataavailable
    // On les stocke ici puis on les assemble en un seul Blob à la fin
    const audioChunksRef = useRef([]);

    // ── Fonctions ──────────────────────────────────────────────────────────

    // Réinitialise les états avant une nouvelle transcription
    // Appelée au début de handleUpload et dans onstop du recorder
    const resetSTT = () => {
        setLoading(true);
        setError(null);
        setTranscript('');
    };

    // Gère l'upload d'un fichier audio sélectionné par l'utilisateur
    // Paramètre : l'événement onChange de l'input type="file"
    // e.target.files[0] = le premier fichier sélectionné
    const handleUpload = async (e) => {
        const file = e.target.files?.[0];
        // L'opérateur ?. évite une erreur si files est undefined
        // (ex: l'utilisateur annule la sélection)

        if (!file) return; // Si pas de fichier sélectionné, on arrête

        resetSTT();

        try {
            // On appelle notre fonction API avec le fichier et la langue
            const result = await uploadAudioSTT(file, language);
            setTranscript(result.text || '(pas de texte détecté)');
            // result.text = le texte transcrit par Faster-Whisper
            // Si vide on affiche un message par défaut
        } catch (err) {
            // err.response?.data?.detail = le message d'erreur de FastAPI
            // Si pas disponible on affiche un message générique
            setError(err.response?.data?.detail || 'Erreur pendant l\'upload');
        } finally {
            setLoading(false);
        }
    };

    // Démarre l'enregistrement depuis le microphone
    // Utilise l'API Web native MediaRecorder disponible dans tous les navigateurs modernes
    const startRecording = async () => {
        try {
            // navigator.mediaDevices.getUserMedia demande l'accès au micro
            // Le navigateur affiche une popup de permission à l'utilisateur
            // { audio: true } = on veut seulement l'audio, pas la vidéo
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            // stream = le flux audio en direct depuis le micro

            // On crée une instance MediaRecorder avec le flux audio
            // MediaRecorder est une API native du navigateur, pas besoin de librairie
            const recorder = new MediaRecorder(stream);
            mediaRecorderRef.current = recorder;
            // On stocke le recorder dans la ref pour pouvoir l'arrêter plus tard
            // depuis la fonction stopRecording

            // On vide le tableau des chunks pour un nouvel enregistrement
            audioChunksRef.current = [];

            // ondataavailable se déclenche régulièrement pendant l'enregistrement
            // avec un morceau (chunk) de données audio
            // event.data = le chunk audio sous forme de Blob
            recorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    // On vérifie que le chunk n'est pas vide avant de l'ajouter
                    audioChunksRef.current.push(event.data);
                }
            };

            // onstop se déclenche quand on appelle recorder.stop()
            // C'est ici qu'on envoie l'audio au backend pour transcription
            recorder.onstop = async () => {
                // On assemble tous les chunks en un seul Blob audio
                // new Blob([...chunks], { type }) = crée un blob à partir d'un tableau de blobs
                const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                // audio/webm = format produit par MediaRecorder sur Chrome/Firefox

                resetSTT();

                try {
                    // On envoie le blob au backend via notre fonction API
                    const result = await recordAudioSTT(blob, language);
                    setTranscript(result.text || '(aucune parole détectée)');
                } catch (err) {
                    setError(err.response?.data?.detail || 'Erreur transcription');
                } finally {
                    setLoading(false);
                }
            };

            // On démarre l'enregistrement !
            recorder.start();
            setIsRecording(true);

        } catch (err) {
            // Erreur possible : l'utilisateur refuse l'accès au micro
            // ou le micro n'est pas disponible
            setError('Impossible d\'accéder au microphone : ' + err.message);
        }
    };

    // Arrête l'enregistrement
    // Appelle recorder.stop() qui déclenche automatiquement onstop
    const stopRecording = () => {
        if (mediaRecorderRef.current?.state === 'recording') {
            // On vérifie que le recorder est bien en train d'enregistrer
            // avant d'appeler stop() pour éviter les erreurs
            mediaRecorderRef.current.stop();
            // stop() déclenche automatiquement l'événement onstop
            // défini dans startRecording
            setIsRecording(false);
        }
    };

    // ── Retour du hook ─────────────────────────────────────────────────────

    // On expose tous les états et fonctions dont les composants auront besoin
    return {
        // États
        mode, setMode,
        transcript,
        loading,
        error,
        isRecording,
        language, setLanguage,
        // Fonctions
        handleUpload,
        startRecording,
        stopRecording,
    };
}