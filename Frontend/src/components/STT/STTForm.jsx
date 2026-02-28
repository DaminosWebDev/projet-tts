// STTForm.jsx - Composant chef d'orchestre de la section STT
// Assemble tous les sous-composants STT
// Utilise le hook useSTT pour la logique

import { useSTT } from '../../hooks/useSTT';
import STTUpload from './STTUpload';
import STTRecorder from './STTRecorder';
import STTResult from './STTResult';
import ErrorMessage from '../UI/ErrorMessage';
import Loader from '../UI/Loader';

// Props :
// - onUseInTTS : fonction pour envoyer le texte transcrit vers le TTS
//               passée depuis App.jsx qui a accès aux deux hooks
export default function STTForm({ onUseInTTS }) {

    const {
        mode, setMode,
        transcript,
        loading,
        error,
        isRecording,
        language, setLanguage,
        handleUpload,
        startRecording,
        stopRecording,
    } = useSTT();

    return (
        <section className="stt-section">
            <h2>Speech-to-Text</h2>

            {/* Sélecteur de langue pour la transcription */}
            <div className="control" style={{ marginBottom: '1.2rem' }}>
                <label>Langue de l'audio</label>
                <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                >
                    <option value="auto">Détection automatique</option>
                    <option value="fr">Français</option>
                    <option value="en">Anglais</option>
                </select>
            </div>

            {/* Onglets pour switcher entre upload et enregistrement */}
            <div className="mode-tabs">
                <button
                    className={mode === 'upload' ? 'active' : ''}
                    onClick={() => setMode('upload')}
                >
                    Charger un fichier
                </button>
                <button
                    className={mode === 'record' ? 'active' : ''}
                    onClick={() => setMode('record')}
                >
                    Enregistrer avec micro
                </button>
            </div>

            {/* Affichage conditionnel selon le mode actif */}
            {mode === 'upload' && (
                <STTUpload
                    onUpload={handleUpload}
                    disabled={loading}
                />
            )}

            {mode === 'record' && (
                <STTRecorder
                    isRecording={isRecording}
                    onStart={startRecording}
                    onStop={stopRecording}
                    disabled={loading && !isRecording}
                    // On désactive uniquement pendant la transcription
                    // pas pendant l'enregistrement
                />
            )}

            {/* Indicateur de chargement */}
            {loading && <Loader text="Transcription en cours..." />}

            {/* Message d'erreur */}
            <ErrorMessage message={error} />

            {/* Résultat de la transcription */}
            <STTResult
                transcript={transcript}
                onUseInTTS={onUseInTTS}
            />

        </section>
    );
}