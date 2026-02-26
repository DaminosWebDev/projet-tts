# main.py - Chef d'orchestre de l'API
# C'est ce fichier qu'on lance pour démarrer le serveur
# Il définit tous les endpoints (URLs) de l'API et coordonne les autres fichiers

import os
import logging
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config import (
    HOST,
    PORT,
    MAX_TEXT_LENGTH,
    AUDIO_DIR,
    LOG_LEVEL
)
from tts_service import generate_audio, get_available_voices

# --- Configuration des logs ---
# basicConfig configure le format des messages de log
# %(asctime)s   = heure du message
# %(name)s      = nom du fichier qui a émis le log (ex: "tts_service")
# %(levelname)s = niveau du log (INFO, ERROR, etc.)
# %(message)s   = le message lui-même
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),  # On convertit le string "INFO" en constante logging.INFO
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# --- Création de l'application FastAPI ---
# C'est l'objet principal de notre API
# title et description apparaissent dans la documentation automatique de FastAPI
app = FastAPI(
    title="Kokoro TTS API",
    description="API de synthèse vocale basée sur Kokoro v0.19 - Supporte le français et l'anglais",
    version="1.0.0"
)

# --- Configuration CORS ---
# CORS = Cross-Origin Resource Sharing
# C'est une sécurité des navigateurs qui bloque les requêtes venant d'un autre domaine
# Par exemple : ton frontend sur http://localhost:3000 qui appelle ton API sur http://localhost:8000
# Sans cette config, le navigateur bloquerait la requête !
# En développement on autorise tout ("*"), en production on mettra uniquement l'URL du frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Autorise toutes les origines (à restreindre en production)
    allow_credentials=True,     # Autorise les cookies dans les requêtes
    allow_methods=["*"],        # Autorise toutes les méthodes HTTP (GET, POST, etc.)
    allow_headers=["*"],        # Autorise tous les headers HTTP
)

# --- Création du dossier audio au démarrage ---
# On s'assure que le dossier audio_files existe avant de démarrer
# exist_ok=True = pas d'erreur si le dossier existe déjà
os.makedirs(AUDIO_DIR, exist_ok=True)
logger.info(f"Dossier audio prêt : {AUDIO_DIR}")


# --- Modèle de données pour les requêtes ---
# Pydantic est intégré à FastAPI et permet de définir la structure exacte
# des données qu'on attend dans les requêtes
# Si le client envoie des données qui ne correspondent pas, FastAPI retourne
# automatiquement une erreur 422 avec un message clair
class TTSRequest(BaseModel):
    text: str = Field(
        ...,  # "..." signifie que ce champ est obligatoire
        description="Le texte à convertir en audio",
        example="Bonjour, comment allez-vous ?"
    )
    language: str = Field(
        default="fr",  # Français par défaut
        description="La langue du texte : 'fr' pour français, 'en' pour anglais",
        example="fr"
    )
    voice: str = Field(
        default="",  # Vide = voix par défaut définie dans config.py
        description="La voix à utiliser (optionnel)",
        example="ff_siwis"
    )
    speed: float = Field(
        default=1.0,
        description="Vitesse de lecture : 0.5 (lent) à 2.0 (rapide)",
        example=1.0
    )


# --- Modèle de données pour les réponses ---
# On définit aussi la structure des réponses pour être cohérent
# Tous nos endpoints retourneront toujours ce même format
class TTSResponse(BaseModel):
    success: bool           # True si tout s'est bien passé
    message: str            # Message lisible par un humain
    filename: str | None    # Nom du fichier audio généré (None si erreur)
    download_url: str | None  # URL pour télécharger le fichier (None si erreur)
    duration: float | None  # Temps de génération en secondes (None si erreur)


# ===========================================================================
# ENDPOINTS DE L'API
# Un endpoint = une URL + une méthode HTTP (GET, POST, etc.)
# ===========================================================================

# --- Endpoint de santé ---
# Convention : toujours avoir un endpoint /health pour vérifier que l'API tourne
# C'est le premier truc qu'on teste quand on déploie
@app.get("/health")
def health_check():
    """
    Vérifie que l'API est bien en ligne.
    Retourne simplement {"status": "ok"} si tout va bien.
    """
    logger.info("Health check appelé")
    return {"status": "ok", "message": "L'API Kokoro TTS est opérationnelle"}


# --- Endpoint des voix disponibles ---
# GET /voices → retourne la liste des voix disponibles par langue
# Utile pour que le frontend affiche les choix à l'utilisateur
@app.get("/voices")
def list_voices():
    """
    Retourne la liste de toutes les voix disponibles, organisées par langue.
    """
    voices = get_available_voices()
    return {
        "success": True,
        "voices": voices
    }


# --- Endpoint principal : génération audio ---
# POST /tts → reçoit un texte, génère l'audio, retourne le fichier + l'URL
# On utilise POST (et pas GET) car on envoie des données dans le corps de la requête
@app.post("/tts")
def text_to_speech(request: TTSRequest):
    """
    Convertit un texte en fichier audio.
    
    - Reçoit : texte, langue, voix, vitesse
    - Retourne : le fichier audio en streaming + une URL de téléchargement dans les headers
    """
    logger.info(f"Requête TTS reçue | langue={request.language} | voix={request.voice} | texte={request.text[:50]}...")

    # --- Validation du texte ---
    # On vérifie les règles AVANT d'appeler Kokoro pour éviter de gaspiller des ressources

    # Règle 1 : le texte ne doit pas être vide
    if not request.text.strip():
        # strip() supprime les espaces au début et à la fin
        # Si après suppression le texte est vide, on refuse
        logger.warning("Requête refusée : texte vide")
        raise HTTPException(
            status_code=400,  # 400 = Bad Request (la faute vient du client)
            detail="Le texte ne peut pas être vide"
        )

    # Règle 2 : le texte ne doit pas dépasser la limite définie dans config.py
    if len(request.text) > MAX_TEXT_LENGTH:
        logger.warning(f"Requête refusée : texte trop long ({len(request.text)} > {MAX_TEXT_LENGTH})")
        raise HTTPException(
            status_code=400,
            detail=f"Le texte dépasse la limite de {MAX_TEXT_LENGTH} caractères ({len(request.text)} reçus)"
        )

    # Règle 3 : la langue doit être "fr" ou "en"
    if request.language not in ["fr", "en"]:
        logger.warning(f"Requête refusée : langue non supportée ({request.language})")
        raise HTTPException(
            status_code=400,
            detail=f"Langue non supportée : '{request.language}'. Utilisez 'fr' ou 'en'"
        )

    # --- Génération de l'audio ---
    # On appelle tts_service.py qui fait le vrai travail
    result = generate_audio(
        text=request.text,
        language=request.language,
        voice=request.voice,
        speed=request.speed
    )

    # --- Vérification du résultat ---
    if not result["success"]:
        # Si tts_service a retourné success=False, on retourne une erreur 500
        # 500 = Internal Server Error (la faute vient du serveur, pas du client)
        logger.error(f"Échec de la génération : {result['error']}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération audio : {result['error']}"
        )

    # --- Retour de la réponse ---
    # FileResponse retourne directement le fichier audio dans la réponse HTTP
    # Le navigateur / Postman pourra lire l'audio directement
    # On ajoute aussi des headers personnalisés avec les infos utiles
    logger.info(f"Audio retourné avec succès : {result['filename']}")

    return FileResponse(
        path=result["filepath"],       # Chemin vers le fichier à retourner
        media_type="audio/wav",        # On dit au client que c'est un fichier WAV
        filename=result["filename"],   # Nom suggéré pour le téléchargement
        headers={
            # Les headers sont des métadonnées ajoutées à la réponse HTTP
            # Le client peut les lire pour avoir des infos supplémentaires
            "X-Generation-Duration": str(result["duration"]),  # Temps de génération
            "X-Audio-Filename": result["filename"],             # Nom du fichier
            # X- = convention pour les headers personnalisés (non standards)
            "Access-Control-Expose-Headers": "X-Generation-Duration, X-Audio-Filename, Content-Disposition"
            # Nécessaire pour que le frontend JavaScript puisse lire ces headers
        }
    )


# --- Endpoint de téléchargement ---
# GET /audio/{filename} → permet de télécharger un fichier audio déjà généré
# {filename} est un paramètre dynamique dans l'URL
# Ex: GET /audio/audio_a834c6d0.wav
@app.get("/audio/{filename}")
def download_audio(filename: str):
    """
    Télécharge un fichier audio précédemment généré via son nom de fichier.
    """
    # On reconstruit le chemin complet vers le fichier
    filepath = os.path.join(AUDIO_DIR, filename)

    # Sécurité : on vérifie que le fichier existe avant de le retourner
    if not os.path.exists(filepath):
        logger.warning(f"Fichier demandé introuvable : {filename}")
        raise HTTPException(
            status_code=404,  # 404 = Not Found
            detail=f"Fichier audio '{filename}' introuvable"
        )

    logger.info(f"Téléchargement du fichier : {filename}")
    return FileResponse(
        path=filepath,
        media_type="audio/wav",
        filename=filename
    )


# --- Point d'entrée du programme ---
# Ce bloc s'exécute uniquement quand on lance "python main.py" directement
# Si main.py est importé par un autre fichier, ce bloc est ignoré
if __name__ == "__main__":
    logger.info(f"Démarrage du serveur sur http://{HOST}:{PORT}")
    uvicorn.run(
        "main:app",   # "main" = nom du fichier, "app" = nom de l'objet FastAPI
        host=HOST,
        port=PORT,
        reload=True   # reload=True = redémarre automatiquement si tu modifies le code
                      # Très pratique en développement, à désactiver en production
    )