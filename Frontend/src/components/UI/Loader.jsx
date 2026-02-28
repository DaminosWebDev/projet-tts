// Loader.jsx - Composant d'affichage du chargement
// Affiché pendant les appels API (génération TTS ou transcription STT)
// Paramètre "text" = le message à afficher, avec une valeur par défaut

// { text = 'Chargement...' } = destructuring avec valeur par défaut
// Si le parent ne passe pas de prop "text", on utilise 'Chargement...'
export default function Loader({ text = 'Chargement...' }) {
    return (
        <div className="loading">
            {text}
        </div>
    );
}