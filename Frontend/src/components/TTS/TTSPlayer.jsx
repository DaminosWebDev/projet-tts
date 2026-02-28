// TTSPlayer.jsx - Player audio et bouton de téléchargement
// Affiché uniquement quand un audio a été généré (audioUrl !== null)
// Ce composant est purement visuel, toute la logique est dans useTTS

// Props :
// - audioUrl      : l'URL blob de l'audio généré
// - audioFilename : le nom du fichier pour le téléchargement
// - onDownload    : la fonction download() du hook useTTS
export default function TTSPlayer({ audioUrl, audioFilename, onDownload }) {

    // Si pas d'URL audio, on n'affiche rien
    // Le composant parent conditionne déjà l'affichage mais
    // c'est une bonne pratique de double-vérifier
    if (!audioUrl) return null;

    return (
        <div className="audio-player-container">

            {/* Player audio natif HTML5 */}
            {/* controls = affiche les contrôles play/pause/volume */}
            {/* src = l'URL blob créée avec URL.createObjectURL() */}
            <audio controls src={audioUrl} />

            {/* Bouton de téléchargement */}
            <button
                className="btn secondary"
                onClick={onDownload}
            >
                Télécharger audio
            </button>

        </div>
    );
}