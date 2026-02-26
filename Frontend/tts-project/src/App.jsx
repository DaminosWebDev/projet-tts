// App.jsx - Composant principal de l'application TTS
// C'est le composant racine, il contient toute l'interface utilisateur

import { useState } from "react"
// useState est un "hook" React qui permet de gérer des données qui changent
// Quand une variable d'état change, React re-affiche automatiquement le composant
// C'est le mécanisme central de React

import axios from "axios"
// On importe Axios pour faire nos appels HTTP vers l'API FastAPI

import "./App.css"
// On importe le fichier CSS qu'on va remplir juste après

// URL de base de notre API FastAPI
// On la met en constante pour ne pas la répéter partout dans le code
const API_URL = "http://localhost:8000"

// Liste des voix disponibles par langue
// On la met ici pour l'instant, plus tard elle viendra directement de l'API via /voices
const VOICES = {
  fr: [
    { id: "ff_siwis", label: "Siwis (Femme)" },
  ],
  en: [
    { id: "af_heart", label: "Heart 🇺🇸 (Femme)" },
    { id: "af_bella", label: "Bella 🇺🇸 (Femme)" },
    { id: "af_sarah", label: "Sarah 🇺🇸 (Femme)" },
    { id: "af_sky", label: "Sky 🇺🇸 (Femme)" },
    { id: "am_adam", label: "Adam 🇺🇸 (Homme)" },
    { id: "am_michael", label: "Michael 🇺🇸 (Homme)" },
    { id: "bf_emma", label: "Emma 🇬🇧 (Femme)" },
    { id: "bf_isabella", label: "Isabella 🇬🇧 (Femme)" },
    { id: "bm_george", label: "George 🇬🇧 (Homme)" },
    { id: "bm_lewis", label: "Lewis 🇬🇧 (Homme)" },
  ],
}

export default function App() {
  // --- Les états de notre composant ---
  // Chaque useState crée une variable et une fonction pour la modifier
  // La syntaxe est : const [valeur, modifierValeur] = useState(valeurInitiale)

  const [text, setText] = useState("")
  // text = le texte saisi par l'utilisateur, vide au départ

  const [language, setLanguage] = useState("fr")
  // language = la langue sélectionnée, français par défaut

  const [voice, setVoice] = useState("ff_siwis")
  // voice = la voix sélectionnée, ff_siwis par défaut

  const [speed, setSpeed] = useState(1.0)
  // speed = la vitesse de lecture, normale par défaut

  const [isLoading, setIsLoading] = useState(false)
  // isLoading = true quand l'API est en train de générer l'audio
  // Permet d'afficher un indicateur de chargement et désactiver le bouton

  const [audioUrl, setAudioUrl] = useState(null)
  // audioUrl = l'URL de l'audio généré pour le player
  // null = pas encore d'audio généré

  const [audioFilename, setAudioFilename] = useState(null)
  // audioFilename = le nom du fichier audio pour le téléchargement

  const [error, setError] = useState(null)
  // error = le message d'erreur à afficher, null = pas d'erreur

  const [duration, setDuration] = useState(null)
  // duration = le temps de génération retourné par l'API dans les headers

  // --- Fonction appelée quand on change de langue ---
  const handleLanguageChange = (newLanguage) => {
    setLanguage(newLanguage)
    // Quand on change de langue, on remet automatiquement la première voix
    // de la nouvelle langue pour éviter d'avoir une voix française sélectionnée
    // alors qu'on est passé en anglais
    setVoice(VOICES[newLanguage][0].id)
  }

  // --- Fonction principale : appel à l'API pour générer l'audio ---
  const handleGenerate = async () => {
    // async = cette fonction est asynchrone
    // Elle va "attendre" la réponse de l'API sans bloquer toute l'interface

    // Validation basique côté frontend avant même d'appeler l'API
    if (!text.trim()) {
      setError("Veuillez saisir un texte avant de générer l'audio")
      return
      // return = on arrête la fonction ici, on n'appelle pas l'API
    }

    // On réinitialise les états avant chaque nouvelle génération
    setIsLoading(true)   // Active le chargement
    setError(null)       // Efface l'erreur précédente
    setAudioUrl(null)    // Efface l'audio précédent
    setAudioFilename(null)
    setDuration(null)

    try {
      // Appel à notre API FastAPI avec Axios
      const response = await axios.post(
        `${API_URL}/tts`,  // L'URL de l'endpoint
        // Le corps de la requête (ce qu'on envoie)
        {
          text: text,
          language: language,
          voice: voice,
          speed: speed,
        },
        // La configuration de la requête
        {
          responseType: "blob",
          // "blob" = on dit à Axios que la réponse est un fichier binaire (audio)
          // et pas du JSON. Sans ça Axios essaierait de parser l'audio en JSON
          // et ça planterait
        }
      )

      // On récupère les headers de la réponse
      // Ce sont les infos qu'on a ajoutées dans main.py avec "X-Generation-Duration"
      const generationDuration = response.headers["x-generation-duration"]
      const filename = response.headers["x-audio-filename"]

      setDuration(generationDuration)
      setAudioFilename(filename)

      // On crée une URL temporaire dans le navigateur à partir du blob audio
      // C'est cette URL qu'on donnera au player HTML pour qu'il puisse lire l'audio
      // URL.createObjectURL crée une URL du style "blob:http://localhost:5173/a3f8..."
      const blob = new Blob([response.data], { type: "audio/wav" })
      const url = URL.createObjectURL(blob)
      setAudioUrl(url)

    } catch (err) {
      // Gestion des erreurs de l'API
      if (err.response) {
        // err.response existe = l'API a répondu mais avec une erreur (400, 500...)
        // On essaie de lire le message d'erreur retourné par FastAPI
        const errorBlob = err.response.data
        const errorText = await errorBlob.text()
        const errorJson = JSON.parse(errorText)
        setError(errorJson.detail || "Une erreur est survenue")
      } else {
        // Pas de réponse = problème réseau ou API éteinte
        setError("Impossible de contacter l'API. Vérifiez que le serveur FastAPI tourne.")
      }
    } finally {
      // finally s'exécute TOUJOURS, qu'il y ait eu une erreur ou non
      // On désactive le chargement dans tous les cas
      setIsLoading(false)
    }
  }

  // --- Fonction de téléchargement ---
  const handleDownload = () => {
    if (!audioUrl || !audioFilename) return

    // On crée un lien HTML invisible, on simule un clic dessus, puis on le supprime
    // C'est la technique standard pour déclencher un téléchargement en JavaScript
    const link = document.createElement("a")
    link.href = audioUrl
    link.download = audioFilename  // Nom suggéré pour le fichier téléchargé
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // --- Le rendu JSX ---
  // JSX = syntaxe qui mélange JavaScript et HTML
  // React transforme ça en vrai HTML dans le navigateur
  return (
    <div className="container">

      <h1 className="title">🎙️ Kokoro TTS</h1>
      <p className="subtitle">Transformez votre texte en audio naturel</p>

      {/* Zone de saisie du texte */}
      <div className="section">
        <label className="label">Texte à synthétiser</label>
        <textarea
          className="textarea"
          placeholder="Saisissez votre texte ici..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          // onChange se déclenche à chaque frappe du clavier
          // e.target.value = le contenu actuel du textarea
          rows={6}
          maxLength={2000}
        />
        {/* Compteur de caractères */}
        <p className="char-count">{text.length} / 2000 caractères</p>
      </div>

      {/* Sélecteurs langue et voix */}
      <div className="controls">

        <div className="control-group">
          <label className="label">Langue</label>
          <select
            className="select"
            value={language}
            onChange={(e) => handleLanguageChange(e.target.value)}
          >
            <option value="fr">🇫🇷 Français</option>
            <option value="en">🇬🇧 Anglais</option>
          </select>
        </div>

        <div className="control-group">
          <label className="label">Voix</label>
          <select
            className="select"
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
          >
            {/* On affiche uniquement les voix de la langue sélectionnée */}
            {VOICES[language].map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
              // key={v.id} est obligatoire quand on génère une liste en React
              // ça permet à React de distinguer chaque élément de la liste
            ))}
          </select>
        </div>

        <div className="control-group">
          <label className="label">Vitesse : {speed}x</label>
          <input
            type="range"
            className="slider"
            min="0.5"
            max="2.0"
            step="0.1"
            value={speed}
            onChange={(e) => setSpeed(parseFloat(e.target.value))}
            // parseFloat convertit la valeur string du slider en nombre décimal
          />
          <div className="speed-labels">
            <span>0.5x</span>
            <span>2.0x</span>
          </div>
        </div>

      </div>

      {/* Bouton de génération */}
      <button
        className={`btn-generate ${isLoading ? "loading" : ""}`}
        onClick={handleGenerate}
        disabled={isLoading}
        // disabled=true = bouton grisé et non cliquable pendant le chargement
        // Evite que l'utilisateur envoie plusieurs requêtes en même temps
      >
        {isLoading ? "⏳ Génération en cours..." : "🎵 Générer l'audio"}
      </button>

      {/* Message d'erreur */}
      {error && (
        // Le && en JSX = "affiche ça seulement si la condition est vraie"
        // Si error est null, rien n'est affiché
        <div className="error">
          ⚠️ {error}
        </div>
      )}

      {/* Player audio et téléchargement */}
      {audioUrl && (
        <div className="audio-section">

          {duration && (
            <p className="duration">⚡ Généré en {duration} secondes</p>
          )}

          {/* Player audio natif du navigateur */}
          <audio
            className="audio-player"
            controls
            // controls = affiche les boutons play/pause/volume du navigateur
            src={audioUrl}
            // src = l'URL blob qu'on a créée après la réponse de l'API
          />

          {/* Bouton télécharger */}
          <button className="btn-download" onClick={handleDownload}>
            ⬇️ Télécharger l'audio
          </button>

        </div>
      )}

    </div>
  )
}
