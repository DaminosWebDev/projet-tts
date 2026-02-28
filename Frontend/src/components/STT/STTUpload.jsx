// STTUpload.jsx - Composant d'upload de fichier audio
// S'occupe uniquement de l'interface d'upload
// La logique est dans le hook useSTT

// useRef : pour accéder à l'input file caché
// On cache l'input file natif (moche) et on le déclenche
// via un bouton stylisé quand l'utilisateur clique
import { useRef } from 'react';

// Props :
// - onUpload  : la fonction handleUpload() du hook useSTT
// - disabled  : true pendant le chargement pour désactiver le bouton
export default function STTUpload({ onUpload, disabled }) {

    // Référence vers l'input file caché dans le DOM
    // On en a besoin pour simuler un clic dessus
    // quand l'utilisateur clique sur notre bouton stylisé
    const fileInputRef = useRef(null);

    return (
        <div>
            {/* Input file caché */}
            {/* On le cache car l'input file natif est difficile à styliser */}
            {/* On le déclenche programmatiquement via fileInputRef.current.click() */}
            <input
                type="file"
                accept="audio/*"
                // audio/* = accepte tous les formats audio (wav, mp3, ogg...)
                ref={fileInputRef}
                onChange={onUpload}
                // onChange se déclenche quand l'utilisateur sélectionne un fichier
                // On passe directement la fonction du hook useSTT
                style={{ display: 'none' }}
                // On cache l'input file natif
            />

            {/* Bouton stylisé qui déclenche l'input file caché */}
            <button
                className="btn upload-btn"
                onClick={() => fileInputRef.current?.click()}
                // On simule un clic sur l'input file caché
                // fileInputRef.current = l'élément DOM de l'input
                // .click() = déclenche l'ouverture du sélecteur de fichier
                disabled={disabled}
            >
                {disabled ? 'Traitement...' : 'Sélectionner un fichier audio'}
            </button>
        </div>
    );
}