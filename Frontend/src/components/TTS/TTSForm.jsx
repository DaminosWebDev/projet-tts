// TTSForm.jsx - Formulaire principal de la section TTS
// C'est le composant "chef d'orchestre" de la section TTS
// Il utilise le hook useTTS pour la logique et assemble tous les sous-composants

// useRef : pour mettre le focus automatique sur le textarea au chargement
// useEffect : pour exécuter du code après le rendu (ici, le focus auto)
import { useRef, useEffect } from 'react';

// On importe le hook qui contient toute la logique TTS
import { useTTS } from '../../hooks/useTTS';

// On importe les sous-composants
// Chaque composant a une responsabilité unique
import TTSVoiceSelector from './TTSVoiceSelector';
import TTSPlayer from './TTSPlayer';
import ErrorMessage from '../UI/ErrorMessage';
import Loader from '../UI/Loader';

export default function TTSForm({ initialText = '' }) {

    // On récupère tous les états et fonctions du hook useTTS
    // via la déstructuration : on extrait exactement ce dont on a besoin
    const {
        text, setText,
        language, changeLanguage,
        voice, setVoice,
        speed, setSpeed,
        loading,
        audioUrl,
        audioFilename,
        error,
        generate,
        download,
    } = useTTS();

    // useRef pour le focus automatique sur le textarea
    // useRef crée une référence vers un élément DOM réel
    // textareaRef.current = l'élément <textarea> dans le DOM
    const textareaRef = useRef(null);

    // useEffect avec [] = s'exécute UNE SEULE FOIS au montage du composant
    // On met le curseur dans le textarea dès que la page s'affiche
    // pour une meilleure expérience utilisateur
    useEffect(() => {
        textareaRef.current?.focus();
        // ?. = optional chaining : évite une erreur si current est null
    }, []);

        // Ajoute cet effet après le useEffect du focus
    useEffect(() => {
        if (initialText) {
            setText(initialText);
            // On met à jour le texte du textarea avec le texte transcrit
        }
    }, [initialText]);
    // Se relance chaque fois que initialText change

    return (
        <section className="tts-section">
            <h2>Text-to-Speech</h2>

            {/* Zone de saisie du texte */}
            <textarea
                ref={textareaRef}
                placeholder="Écrivez votre texte ici..."
                value={text}
                // onChange se déclenche à chaque frappe
                // e.target.value = le texte actuel dans le textarea
                onChange={(e) => setText(e.target.value)}
                maxLength={2000}
                rows={5}
            />

            {/* Compteur de caractères */}
            {/* text.length = nombre de caractères actuels */}
            <div className="char-count">{text.length} / 2000</div>

            {/* Composant sélecteurs langue/voix/vitesse */}
            {/* On lui passe les états et fonctions dont il a besoin via les props */}
            <TTSVoiceSelector
                language={language}
                changeLanguage={changeLanguage}
                voice={voice}
                setVoice={setVoice}
                speed={speed}
                setSpeed={setSpeed}
            />

            {/* Bouton de génération */}
            <button
                className={`btn primary ${loading ? 'loading' : ''}`}
                // Si loading est true, on ajoute la classe 'loading'
                // qui change la couleur et le curseur via CSS
                onClick={generate}
                disabled={loading || !text.trim()}
                // Désactivé si : en cours de chargement OU texte vide
                // !text.trim() = true si le texte est vide ou ne contient que des espaces
            >
                {loading ? 'Génération en cours...' : 'Générer l\'audio'}
                {/* Affichage conditionnel selon l'état de chargement */}
            </button>

            {/* Composant d'erreur : n'affiche rien si error est null */}
            <ErrorMessage message={error} />

            {/* Indicateur de chargement : affiché uniquement pendant la génération */}
            {loading && <Loader text="Génération audio en cours..." />}

            {/* Player audio : affiché uniquement quand un audio est disponible */}
            {/* && en JSX = affiche le composant uniquement si la condition est vraie */}
            {audioUrl && (
                <TTSPlayer
                    audioUrl={audioUrl}
                    audioFilename={audioFilename}
                    onDownload={download}
                />
            )}

        </section>
    );
}