// ErrorMessage.jsx - Composant réutilisable pour afficher les erreurs
// On le crée une seule fois et on l'utilise partout dans l'app
// Principe DRY (Don't Repeat Yourself) : pas de copier-coller du même HTML

// On reçoit "message" en prop (propriété)
// Une prop c'est comme un paramètre de fonction mais pour un composant React
// Le composant parent passe la valeur : <ErrorMessage message="Erreur !" />
export default function ErrorMessage({ message }) {

    // Si pas de message, on n'affiche rien du tout
    // null en JSX = rien n'est rendu dans le DOM
    if (!message) return null;

    return (
        <div className="error-msg">
            {message}
            {/* Les accolades {} permettent d'insérer du JavaScript dans le JSX */}
            {/* Ici on affiche la valeur de la variable message */}
        </div>
    );
}