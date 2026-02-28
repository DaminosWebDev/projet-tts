// STTRecorder.jsx - Composant d'enregistrement depuis le microphone
// S'occupe uniquement du bouton d'enregistrement
// La logique MediaRecorder est dans le hook useSTT

// Props :
// - isRecording    : true quand le micro enregistre
// - onStart        : fonction startRecording() du hook useSTT
// - onStop         : fonction stopRecording() du hook useSTT
// - disabled       : true pendant la transcription
export default function STTRecorder({ isRecording, onStart, onStop, disabled }) {
    return (
        <button
            // On applique la classe 'recording' quand le micro est actif
            // Cette classe déclenche l'animation pulse rouge en CSS
            className={`btn record-btn ${isRecording ? 'recording' : ''}`}
            onClick={isRecording ? onStop : onStart}
            // Si en train d'enregistrer → clic = arrêter
            // Si pas en train d'enregistrer → clic = démarrer
            // C'est un bouton toggle (bascule)
            disabled={disabled}
            // Désactivé pendant la transcription pour éviter
            // de lancer un nouvel enregistrement pendant le traitement
        >
            {isRecording ? '■ Arrêter l\'enregistrement' : '● Commencer l\'enregistrement'}
            {/* ■ = caractère Unicode carré (stop) */}
            {/* ● = caractère Unicode rond (record) */}
        </button>
    );
}