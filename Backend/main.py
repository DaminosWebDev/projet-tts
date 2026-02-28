# main.py - Chef d'orchestre de l'API
# C'est ce fichier qu'on lance pour démarrer le serveur
# Il définit tous les endpoints (URLs) de l'API et coordonne les autres fichiers

import os
import logging
import uvicorn
import uuid  # Pour générer des identifiants uniques pour les fichiers uploadés
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from config import (
    HOST,
    PORT,
    MAX_TEXT_LENGTH,
    TTS_OUTPUT_DIR,
    STT_UPLOAD_DIR,
    STT_MAX_FILE_SIZE_MB,
    LOG_LEVEL
)
from tts.tts_service import generate_audio, get_available_voices
from stt.stt_service import transcribe_audio, get_supported_languages
from fastapi import File, UploadFile
import shutil
# shutil = module Python pour manipuler les fichiers (copier, déplacer, supprimer)

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
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
logger.info(f"Dossier audio prêt : {TTS_OUTPUT_DIR}")
# Création du dossier uploads STT au démarrage
os.makedirs(STT_UPLOAD_DIR, exist_ok=True)
logger.info(f"Dossier STT uploads prêt : {STT_UPLOAD_DIR}")


# --- Modèle de données pour les requêtes ---
# Pydantic est intégré à FastAPI et permet de définir la structure exacte
# des données qu'on attend dans les requêtes
# Si le client envoie des données qui ne correspondent pas, FastAPI retourne
# automatiquement une erreur 422 avec un message clair
class TTSRequest(BaseModel):
    text: str = Field(
        ...,
        description="Le texte à convertir en audio",
        json_schema_extra={"example": "Bonjour, comment allez-vous ?"}
    )
    language: str = Field(
        default="fr",
        description="La langue du texte : 'fr' pour français, 'en' pour anglais",
        json_schema_extra={"example": "fr"}
    )
    voice: str = Field(
        default="",
        description="La voix à utiliser (optionnel)",
        json_schema_extra={"example": "ff_siwis"}
    )
    speed: float = Field(
        default=1.0,
        description="Vitesse de lecture : 0.5 (lent) à 2.0 (rapide)",
        json_schema_extra={"example": 1.0}
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

# ===========================================================================
# ENDPOINTS TTS (Text-to-Speech)
# ===========================================================================

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
    filepath = os.path.join(TTS_OUTPUT_DIR, filename)

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


# ===========================================================================
# ENDPOINTS STT (Speech-to-Text)
# ===========================================================================

# --- Endpoint des langues supportées ---
@app.get("/stt/languages")
def list_stt_languages():
    """
    Retourne la liste des langues supportées par Faster-Whisper.
    """
    languages = get_supported_languages()
    return {
        "success": True,
        "languages": languages
    }


# --- Endpoint upload fichier audio ---
# POST /stt/upload → reçoit un fichier audio, le transcrit et retourne le texte
@app.post("/stt/upload")
async def speech_to_text_upload(
    file: UploadFile = File(...),
    # UploadFile = le fichier audio envoyé par l'utilisateur
    # File(...) = ce champ est obligatoire
    language: str = "auto"
    # language = la langue de l'audio, "auto" pour détection automatique
):
    """
    Reçoit un fichier audio, le transcrit avec Faster-Whisper
    et retourne le texte transcrit avec les timestamps.
    """
    logger.info(f"Upload STT reçu | fichier={file.filename} | langue={language}")

    # --- Validation du fichier ---
    # Vérifie que le fichier est bien un audio
    allowed_types = ["audio/wav", "audio/wave", "audio/mp3", "audio/mpeg", "audio/ogg", "audio/webm", "audio/m4a"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Format non supporté : {file.content_type}. Utilisez WAV, MP3, OGG, WEBM ou M4A"
        )

    # Vérifie la taille du fichier
    # On lit le contenu pour vérifier la taille
    contents = await file.read()
    # await = on attend que la lecture soit terminée
    # read() est asynchrone car le fichier peut être volumineux
    
    file_size_mb = len(contents) / (1024 * 1024)
    # len(contents) = taille en bytes
    # On divise par 1024*1024 pour avoir des MB

    if file_size_mb > STT_MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux : {file_size_mb:.1f}MB. Maximum : {STT_MAX_FILE_SIZE_MB}MB"
        )

    # --- Sauvegarde temporaire du fichier ---
    # On sauvegarde le fichier uploadé pour que Faster-Whisper puisse le lire
    # Faster-Whisper a besoin d'un chemin de fichier, pas de données en mémoire
    unique_id = str(uuid.uuid4())[:8]
    # On garde l'extension originale du fichier
    extension = os.path.splitext(file.filename)[1] or ".wav"
    # os.path.splitext sépare le nom de l'extension : "audio.mp3" → ("audio", ".mp3")
    
    upload_filename = f"upload_{unique_id}{extension}"
    upload_filepath = os.path.join(STT_UPLOAD_DIR, upload_filename)

    # Écriture du fichier sur le disque
    with open(upload_filepath, "wb") as f:
        f.write(contents)
    # "wb" = write binary (écriture en mode binaire)
    # Les fichiers audio sont des données binaires, pas du texte

    # --- Transcription ---
    language_param = None if language == "auto" else language
    # Si l'utilisateur choisit "auto" on passe None à Faster-Whisper
    # qui détectera automatiquement la langue

    result = transcribe_audio(upload_filepath, language=language_param)

    # --- Nettoyage du fichier temporaire ---
    # On supprime le fichier uploadé après la transcription
    # pour ne pas surcharger le disque
    try:
        os.remove(upload_filepath)
        logger.info(f"Fichier temporaire supprimé : {upload_filename}")
    except Exception as e:
        logger.warning(f"Impossible de supprimer le fichier temporaire : {str(e)}")

    # --- Retour de la réponse ---
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la transcription : {result['error']}"
        )

    logger.info(f"Transcription réussie | langue={result['language']}")

    return {
        "success": True,
        "text": result["text"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "segments": result["segments"],
        "duration": result["duration"]
    }


# --- Endpoint enregistrement micro ---
# POST /stt/record → reçoit un audio enregistré depuis le navigateur
@app.post("/stt/record")
async def speech_to_text_record(
    file: UploadFile = File(...),
    language: str = "auto"
):
    """
    Reçoit un audio enregistré depuis le microphone du navigateur
    et retourne la transcription.
    
    Le navigateur envoie l'audio en format WebM ou WAV selon le navigateur.
    On traite ça exactement comme un upload classique.
    """
    logger.info(f"Enregistrement micro STT reçu | langue={language}")

    # On réutilise la même logique que l'upload
    # La seule différence c'est le nom de l'endpoint
    # Le frontend saura distinguer les deux usages
    
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)

    if file_size_mb > STT_MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Enregistrement trop volumineux : {file_size_mb:.1f}MB. Maximum : {STT_MAX_FILE_SIZE_MB}MB"
        )

    # Sauvegarde temporaire
    unique_id = str(uuid.uuid4())[:8]
    upload_filepath = os.path.join(STT_UPLOAD_DIR, f"record_{unique_id}.webm")

    with open(upload_filepath, "wb") as f:
        f.write(contents)

    # Transcription
    language_param = None if language == "auto" else language
    result = transcribe_audio(upload_filepath, language=language_param)

    # Nettoyage
    try:
        os.remove(upload_filepath)
    except Exception as e:
        logger.warning(f"Impossible de supprimer l'enregistrement temporaire : {str(e)}")

    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la transcription : {result['error']}"
        )

    return {
        "success": True,
        "text": result["text"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "segments": result["segments"],
        "duration": result["duration"]
    }


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