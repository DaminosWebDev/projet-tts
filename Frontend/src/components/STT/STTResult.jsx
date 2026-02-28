// STTResult.jsx - Affichage du texte transcrit
// Composant simple qui affiche le résultat de la transcription
// et propose de l'utiliser directement dans le TTS

// Props :
// - transcript : le texte transcrit par Faster-Whisper
// - onUseInTTS : fonction optionnelle pour envoyer le texte vers le TTS
//               (fonctionnalité bonus qu'on ajoutera plus tard)
export default function STTResult({ transcript, onUseInTTS }) {

    // Si pas de transcription, on n'affiche rien
    if (!transcript) return null;

    return (
        <div className="transcript-result">
            <h3>Résultat :</h3>

            {/* Zone d'affichage du texte transcrit */}
            <div className="transcript-box">
                {transcript}
            </div>

            {/* Bouton optionnel pour envoyer le texte vers le TTS */}
            {/* onUseInTTS && = n'affiche le bouton que si la fonction est passée en prop */}
            {onUseInTTS && (
                <button
                    className="btn secondary"
                    onClick={() => onUseInTTS(transcript)}
                    // On passe le texte transcrit à la fonction
                    // qui le mettra dans le textarea du TTS
                    style={{ marginTop: '1rem' }}
                >
                    Utiliser dans le TTS →
                </button>
            )}
        </div>
    );
}