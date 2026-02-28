// Button.jsx - Bouton réutilisable avec plusieurs variantes
// Plutôt que de répéter <button className="btn primary"...> partout,
// on crée un composant Button qu'on configure via des props

// Props :
// - onClick   : la fonction à appeler au clic
// - disabled  : désactive le bouton (pendant le chargement par exemple)
// - variant   : le style du bouton ('primary', 'secondary', 'upload', 'record')
// - className : classes CSS supplémentaires optionnelles
// - children  : le contenu du bouton (texte, icônes...)
//               "children" est une prop spéciale React qui représente
//               tout ce qui est entre les balises ouvrante et fermante
//               Ex: <Button>Générer</Button> → children = "Générer"

export default function Button({
    onClick,
    disabled = false,
    variant = 'primary',
    className = '',
    children
}) {
    return (
        <button
            // On combine les classes CSS :
            // - "btn" = classe de base pour tous les boutons
            // - variant = 'primary', 'secondary', 'upload' ou 'record'
            // - className = classes supplémentaires passées par le parent
            // Les espaces entre les classes sont importants !
            className={`btn ${variant} ${className}`}
            onClick={onClick}
            disabled={disabled}
        >
            {children}
            {/* children = le texte ou les éléments entre les balises du composant */}
        </button>
    );
}