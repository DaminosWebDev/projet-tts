// App.jsx - Point d'entrée principal de l'application
// Grâce à la réorganisation en composants, App.jsx est maintenant
// très léger : il assemble juste les sections TTS et STT
// et gère la communication entre les deux (onUseInTTS)

import { useState } from 'react';
// On importe les deux composants principaux
import TTSForm from './components/TTS/TTSForm';
import STTForm from './components/STT/STTForm';
import './App.css';

export default function App() {

    // Cet état permet de pré-remplir le textarea TTS
    // avec le texte transcrit par le STT
    // On le gère ici car il fait le lien entre les deux sections
    const [ttsInitialText, setTtsInitialText] = useState('');

    // Fonction passée à STTForm via onUseInTTS
    // Quand l'utilisateur clique "Utiliser dans le TTS →"
    // le texte transcrit est envoyé dans le textarea TTS
    const handleUseInTTS = (text) => {
        setTtsInitialText(text);
        // On scroll vers le haut pour que l'utilisateur voie le TTS
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <div className="app-container">
            <header>
                <h1>Kokoro — TTS & STT</h1>
                <p>Synthèse vocale et reconnaissance vocale</p>
            </header>

            {/* Section TTS */}
            {/* On passe le texte initial si l'utilisateur vient du STT */}
            <TTSForm initialText={ttsInitialText} />

            {/* Section STT */}
            {/* On passe la fonction pour envoyer le texte vers le TTS */}
            <STTForm onUseInTTS={handleUseInTTS} />

        </div>
    );
}