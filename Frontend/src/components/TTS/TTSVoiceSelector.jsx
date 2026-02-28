// TTSVoiceSelector.jsx - Sélecteurs de langue, voix et vitesse
// Ce composant s'occupe UNIQUEMENT des contrôles de configuration TTS
// Il reçoit les valeurs et les fonctions de changement via des props
// depuis le composant parent qui utilise le hook useTTS

// Liste statique des voix disponibles par langue
// On la définit ici car elle est directement liée à ce composant
const VOICES = {
    fr: [
        { id: 'ff_siwis', label: 'Siwis 🇫🇷 (Femme)' }
    ],
    en: [
        { id: 'af_heart',    label: 'Heart 🇺🇸 (Femme)'    },
        { id: 'af_bella',    label: 'Bella 🇺🇸 (Femme)'    },
        { id: 'af_sarah',    label: 'Sarah 🇺🇸 (Femme)'    },
        { id: 'af_sky',      label: 'Sky 🇺🇸 (Femme)'      },
        { id: 'am_adam',     label: 'Adam 🇺🇸 (Homme)'     },
        { id: 'am_michael',  label: 'Michael 🇺🇸 (Homme)'  },
        { id: 'bf_emma',     label: 'Emma 🇬🇧 (Femme)'     },
        { id: 'bf_isabella', label: 'Isabella 🇬🇧 (Femme)' },
        { id: 'bm_george',   label: 'George 🇬🇧 (Homme)'   },
        { id: 'bm_lewis',    label: 'Lewis 🇬🇧 (Homme)'    },
    ],
};

// Props reçues depuis le composant parent :
// - language       : langue actuelle ("fr" ou "en")
// - changeLanguage : fonction du hook useTTS pour changer la langue
// - voice          : voix actuelle
// - setVoice       : fonction du hook useTTS pour changer la voix
// - speed          : vitesse actuelle (float entre 0.5 et 2.0)
// - setSpeed       : fonction du hook useTTS pour changer la vitesse
export default function TTSVoiceSelector({
    language,
    changeLanguage,
    voice,
    setVoice,
    speed,
    setSpeed
}) {
    return (
        <div className="controls-row">

            {/* Sélecteur de langue */}
            <div className="control">
                <label>Langue</label>
                <select
                    value={language}
                    onChange={(e) => changeLanguage(e.target.value)}
                    // e.target.value = la valeur de l'option sélectionnée
                    // On appelle changeLanguage (du hook useTTS) qui met à jour
                    // la langue ET réinitialise la voix automatiquement
                >
                    <option value="fr">Français</option>
                    <option value="en">Anglais</option>
                </select>
            </div>

            {/* Sélecteur de voix */}
            <div className="control">
                <label>Voix</label>
                <select
                    value={voice}
                    onChange={(e) => setVoice(e.target.value)}
                >
                    {/* On affiche uniquement les voix de la langue sélectionnée */}
                    {/* VOICES[language] = tableau des voix pour cette langue */}
                    {/* .map() transforme chaque voix en un élément <option> */}
                    {VOICES[language]?.map((v) => (
                        // key est obligatoire dans les listes React
                        // Il permet à React d'identifier chaque élément
                        // pour optimiser les re-rendus
                        <option key={v.id} value={v.id}>
                            {v.label}
                        </option>
                    ))}
                </select>
            </div>

            {/* Slider de vitesse */}
            <div className="control">
                {/* toFixed(1) formate le nombre avec 1 décimale : 1.0, 1.5, 2.0 */}
                <label>Vitesse {speed.toFixed(1)}×</label>
                <input
                    type="range"
                    min="0.5"
                    max="2.0"
                    step="0.1"
                    value={speed}
                    onChange={(e) => setSpeed(parseFloat(e.target.value))}
                    // parseFloat convertit la valeur string du slider en nombre décimal
                    // Sans ça on aurait "1.5" (string) au lieu de 1.5 (number)
                />
            </div>

        </div>
    );
}