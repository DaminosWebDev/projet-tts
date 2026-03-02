# =============================================================================
# youtube_service.py - Gestion du téléchargement YouTube et transcription
# =============================================================================
# Ce fichier a deux responsabilités :
# 1. Télécharger une vidéo YouTube avec yt-dlp
#    - La vidéo SANS son → pour l'assemblage final
#    - L'audio SEUL en WAV → pour la transcription Whisper
# 2. Transcrire l'audio avec Faster-Whisper (avec timestamps)
#
# POURQUOI SÉPARER VIDÉO ET AUDIO ?
# On a besoin de deux fichiers distincts :
# - La vidéo sans son = le support visuel qu'on va garder
# - L'audio = ce qu'on va analyser, traduire, et remplacer
# C'est comme démixer une chanson pour séparer la voix des instruments
# =============================================================================


# =============================================================================
# IMPORTS — Chaque import est une boîte à outils qu'on emprunte
# =============================================================================

import os
# os = module intégré à Python pour interagir avec le système d'exploitation
# On l'utilise pour :
# - os.path.join() : construire des chemins de fichiers (compatible Windows/Linux)
# - os.makedirs()  : créer des dossiers
# - os.path.exists() : vérifier qu'un fichier existe
# Exemple : os.path.join("youtube", "temp", "abc123") → "youtube\temp\abc123" sur Windows

import logging
# logging = module intégré à Python pour afficher des messages dans le terminal
# C'est mieux que print() car :
# - On peut filtrer par niveau (DEBUG, INFO, WARNING, ERROR)
# - On voit d'où vient le message (nom du fichier)
# - En production on peut envoyer les logs dans un fichier
# Exemple : logger.info("Téléchargement démarré") → affiche avec timestamp + nom fichier

import uuid
# uuid = module intégré à Python pour générer des identifiants uniques
# UUID = Universally Unique Identifier
# Exemple : str(uuid.uuid4()) → "a3f8c2d1-4b5e-6f7a-8b9c-0d1e2f3a4b5c"
# On l'utilise pour créer des job_id uniques → évite les conflits entre utilisateurs

import yt_dlp
# yt_dlp = bibliothèque externe qu'on a installée avec pip
# C'est l'outil qui télécharge les vidéos YouTube
# Il s'utilise comme un objet contextuel (with yt_dlp.YoutubeDL(options) as ydl:)
# On lui passe des options (format, dossier de sortie, etc.) et il fait le travail
# POURQUOI yt_dlp et pas pytube ?
# yt_dlp est activement maintenu, supporte 1000+ sites, et est beaucoup plus fiable

from faster_whisper import WhisperModel
# WhisperModel = la classe principale de Faster-Whisper
# On l'importe directement depuis le module faster_whisper
# C'est le même modèle qu'on utilise dans stt_service.py
# POURQUOI un deuxième modèle Whisper ?
# Pour YouTube on utilise "medium" au lieu de "small"
# Medium = plus précis = meilleurs timestamps = meilleure synchronisation vidéo
# Le coût : plus de VRAM GPU, mais on a un bon GPU donc ce n'est pas un problème

import soundfile as sf
# soundfile = bibliothèque pour lire et écrire des fichiers audio
# On l'utilise pour sauvegarder chaque segment audio généré par Kokoro
# en fichier WAV numéroté : segment_001.wav, segment_002.wav, etc.
# POURQUOI soundfile et pas une autre lib ?
# C'est déjà utilisé dans tts_service.py, on reste cohérent
# et c'est la bibliothèque la plus simple pour écrire du WAV depuis numpy

import numpy as np
# numpy = bibliothèque de calcul numérique
# Kokoro retourne l'audio sous forme de tableau numpy
# On en a besoin pour concatener les chunks audio de Kokoro
# POURQUOI numpy ?
# Les données audio sont des tableaux de nombres (échantillons)
# numpy est le standard Python pour manipuler ce type de données
# Analogie : c'est comme Excel mais pour les mathématiques

from tts.tts_service import get_pipeline_and_voice
# On importe la fonction qui sélectionne le bon pipeline Kokoro
# selon la langue — déjà écrite dans tts_service.py
# POURQUOI réutiliser cette fonction ?
# Elle gère déjà la logique de sélection de voix FR/EN
# On ne réécrit pas ce qui existe déjà — principe DRY
# DRY = Don't Repeat Yourself = ne pas se répéter

from config import (
    YOUTUBE_TEMP_DIR,
    # YOUTUBE_TEMP_DIR = "youtube/temp"
    # C'est le dossier racine où on stocke les fichiers temporaires
    # Chaque job aura son sous-dossier : youtube/temp/{job_id}/

    YOUTUBE_WHISPER_MODEL,
    # YOUTUBE_WHISPER_MODEL = "medium"
    # La taille du modèle Whisper pour YouTube
    # Plus précis que "small" pour avoir des timestamps fiables

    STT_DEVICE,
    # STT_DEVICE = "cuda"
    # On réutilise la même config GPU que le STT existant
    # cuda = utilise le GPU NVIDIA → beaucoup plus rapide

    STT_COMPUTE_TYPE
    # STT_COMPUTE_TYPE = "float16"
    # Précision des calculs sur GPU
    # float16 = demi-précision → plus rapide, assez précis pour notre usage
)
# POURQUOI importer depuis config.py ?
# Centraliser la configuration évite de répéter les mêmes valeurs partout
# Si on veut changer le modèle, on le change UNE SEULE FOIS dans config.py


# =============================================================================
# CONFIGURATION DU LOGGER
# =============================================================================

logger = logging.getLogger(__name__)
# logging.getLogger(__name__) crée un logger spécifique à ce fichier
# __name__ = nom du module actuel, ici "youtube.youtube_service"
# Résultat dans le terminal : "youtube.youtube_service | INFO | Téléchargement..."
# Ça permet de savoir exactement QUEL fichier a produit quel message de log


# =============================================================================
# CHARGEMENT DU MODÈLE WHISPER
# =============================================================================

# On charge le modèle UNE SEULE FOIS au démarrage du serveur
# POURQUOI ? Charger un modèle IA prend 5-15 secondes et consomme de la mémoire
# Si on le chargeait à chaque requête, chaque transcription prendrait 15s de plus
# En le chargeant une fois, il reste en mémoire GPU et est disponible instantanément
# C'est le même principe que dans stt_service.py

logger.info(f"Chargement du modèle Whisper YouTube ({YOUTUBE_WHISPER_MODEL})...")

youtube_whisper_model = WhisperModel(
    YOUTUBE_WHISPER_MODEL,      # "medium" → plus précis que "small"
    device=STT_DEVICE,          # "cuda" → utilise le GPU
    compute_type=STT_COMPUTE_TYPE  # "float16" → calculs rapides sur GPU
)

logger.info("Modèle Whisper YouTube chargé !")


# =============================================================================
# FONCTION 1 : download_youtube()
# Télécharge la vidéo et extrait l'audio
# =============================================================================

def download_youtube(url: str, job_id: str) -> dict:
    """
    Télécharge une vidéo YouTube en deux fichiers séparés :
    - La vidéo SANS son (.mp4) → pour l'assemblage final avec ffmpeg
    - L'audio SEUL (.wav)      → pour la transcription avec Faster-Whisper

    POURQUOI DEUX TÉLÉCHARGEMENTS SÉPARÉS ?
    YouTube stocke la vidéo et l'audio dans des flux (streams) séparés.
    On veut :
    - Le flux vidéo seul → on supprimera l'audio original dedans
    - Le flux audio seul → on le transcrit, traduit, et remplace

    Paramètres :
    ------------
    url : str
        L'URL complète de la vidéo YouTube
        Ex: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    job_id : str
        Identifiant unique du job (généré dans main.py avec uuid)
        Ex: "a3f8c2d1"
        Permet d'organiser les fichiers par job dans youtube/temp/

    Valeur de retour : dict
    -----------------------
    Succès :
    {
        "success": True,
        "job_dir": "youtube/temp/a3f8c2d1",
        "video_path": "youtube/temp/a3f8c2d1/video.mp4",
        "audio_path": "youtube/temp/a3f8c2d1/audio.wav",
        "title": "Titre de la vidéo",
        "duration": 1234,        ← durée en secondes
        "channel": "Nom chaîne",
        "error": None
    }
    Échec :
    {
        "success": False,
        "error": "Message d'erreur explicite"
        ... (autres champs à None)
    }
    """

    try:
        # -----------------------------------------------------------------
        # ÉTAPE 1 : Créer le dossier de travail pour ce job
        # -----------------------------------------------------------------
        # Chaque job a son propre dossier isolé
        # Analogie : chaque client a son propre casier dans un vestiaire
        # youtube/temp/
        # ├── a3f8c2d1/    ← job 1
        # │   ├── video.mp4
        # │   └── audio.wav
        # └── b4e9f3d2/    ← job 2
        #     ├── video.mp4
        #     └── audio.wav

        job_dir = os.path.join(YOUTUBE_TEMP_DIR, job_id)
        # os.path.join construit le chemin compatible avec l'OS
        # Sur Windows : "youtube\temp\a3f8c2d1"
        # Sur Linux   : "youtube/temp/a3f8c2d1"

        os.makedirs(job_dir, exist_ok=True)
        # exist_ok=True = pas d'erreur si le dossier existe déjà

        logger.info(f"Dossier job créé : {job_dir}")

        # Chemins exacts des fichiers qu'on va créer
        video_path = os.path.join(job_dir, "video.mp4")
        audio_path = os.path.join(job_dir, "audio.wav")

        # -----------------------------------------------------------------
        # ÉTAPE 2 : Télécharger la vidéo SANS son
        # -----------------------------------------------------------------
        # On configure yt-dlp pour ne télécharger QUE le flux vidéo
        # sans audio — ce sera notre "coquille" visuelle

        logger.info(f"Téléchargement vidéo (sans son) depuis : {url}")

        video_opts = {
            "format": "bestvideo[ext=mp4]/bestvideo",
            # "format" dit à yt-dlp QUOI télécharger
            # "bestvideo[ext=mp4]" = meilleure qualité vidéo en format MP4
            # "/bestvideo" = si pas de MP4 dispo → prend la meilleure vidéo disponible
            # Le "/" est un opérateur de fallback (repli)
            # IMPORTANT : "bestvideo" sans audio = flux vidéo seul

            "outtmpl": os.path.join(job_dir, "video.%(ext)s"),
            # "outtmpl" = output template = modèle du nom de fichier de sortie
            # %(ext)s sera remplacé automatiquement par l'extension réelle
            # Ex: si yt-dlp télécharge du mp4 → "video.mp4"
            #     si yt-dlp télécharge du webm → "video.webm"

            "quiet": True,
            # quiet = True → yt-dlp n'affiche rien dans le terminal
            # Sans ça, yt-dlp afficherait une barre de progression verbeuse

            "no_warnings": True,
            # Supprime les avertissements de yt-dlp dans le terminal
        }

        video_info = {}
        # On utilise yt-dlp comme gestionnaire de contexte (with ... as)
        # C'est comme ouvrir un fichier avec open() — ça gère proprement
        # l'ouverture et la fermeture des ressources automatiquement
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # extract_info() fait deux choses à la fois :
            # 1. Télécharge la vidéo (download=True)
            # 2. Retourne un dict avec toutes les infos de la vidéo
            # info contient : titre, durée, chaîne, miniature, etc.

            video_info = {
                "title": info.get("title", "Sans titre"),
                # .get("title", "Sans titre") = récupère "title" du dict
                # Si "title" n'existe pas → retourne "Sans titre" par défaut
                "duration": info.get("duration", 0),
                # durée en secondes (ex: 1234 pour une vidéo de 20min34s)
                "channel": info.get("channel", "Inconnu"),
            }

        logger.info(f"Vidéo téléchargée : {video_info['title']} ({video_info['duration']}s)")

        # -----------------------------------------------------------------
        # ÉTAPE 3 : Extraire l'audio SEUL en WAV
        # -----------------------------------------------------------------
        # On retélécharge le flux audio et on le convertit en WAV
        # WAV = format audio non compressé → parfait pour Whisper
        # POURQUOI WAV et pas MP3 ?
        # WAV = données brutes, pas de perte de qualité = meilleure transcription
        # MP3 = compressé avec perte = moins bon pour l'IA

        logger.info("Extraction audio en WAV...")

        audio_opts = {
            "format": "bestaudio/best",
            # "bestaudio" = meilleur flux audio disponible
            # "/best" = fallback si pas d'audio séparé disponible

            "outtmpl": os.path.join(job_dir, "audio.%(ext)s"),
            # Le fichier sera d'abord téléchargé dans son format original
            # puis converti en WAV par le postprocessor ci-dessous

            "postprocessors": [{
                # postprocessors = traitements appliqués APRÈS le téléchargement
                # C'est une liste car on peut chaîner plusieurs traitements
                "key": "FFmpegExtractAudio",
                # "FFmpegExtractAudio" = utilise ffmpeg pour extraire l'audio
                # C'est pour ça qu'on avait besoin d'installer ffmpeg !
                # yt-dlp appelle ffmpeg automatiquement en arrière-plan

                "preferredcodec": "wav",
                # On veut du WAV en sortie
                # yt-dlp + ffmpeg vont convertir automatiquement

                "preferredquality": "192",
                # Qualité audio en kbps (kilobits par seconde)
                # 192 = bonne qualité, suffisant pour la transcription vocale
            }],

            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.extract_info(url, download=True)
            # On n'a pas besoin des infos cette fois (déjà récupérées)
            # On télécharge juste l'audio et le convertit en WAV

        logger.info(f"Audio extrait : {audio_path}")

        # -----------------------------------------------------------------
        # ÉTAPE 4 : Vérifier que les fichiers existent bien
        # -----------------------------------------------------------------
        # Après les téléchargements, on vérifie que les fichiers sont là
        # Des fois yt-dlp peut échouer silencieusement sans lever d'exception

        if not os.path.exists(video_path):
            raise FileNotFoundError(
                f"Fichier vidéo introuvable après téléchargement : {video_path}"
            )
            # FileNotFoundError = type d'erreur Python standard pour "fichier manquant"
            # raise = on "lance" l'erreur → elle sera capturée par le except ci-dessous

        if not os.path.exists(audio_path):
            raise FileNotFoundError(
                f"Fichier audio introuvable après téléchargement : {audio_path}"
            )

        # Tout s'est bien passé → on retourne les infos
        return {
            "success": True,
            "job_dir": job_dir,
            "video_path": video_path,
            "audio_path": audio_path,
            "title": video_info["title"],
            "duration": video_info["duration"],
            "channel": video_info["channel"],
            "error": None
        }

    except Exception as e:
        # Exception = capture N'IMPORTE QUELLE erreur qui se produit dans le try
        # "e" = l'objet erreur, str(e) = son message en texte lisible
        # On ne laisse pas le serveur planter → on retourne un dict d'échec propre
        logger.error(f"Erreur téléchargement YouTube : {str(e)}")
        return {
            "success": False,
            "job_dir": None,
            "video_path": None,
            "audio_path": None,
            "title": None,
            "duration": None,
            "channel": None,
            "error": str(e)
        }


# =============================================================================
# FONCTION 2 : transcribe_youtube_audio()
# Transcrit l'audio avec Faster-Whisper et retourne les segments horodatés
# =============================================================================

def transcribe_youtube_audio(audio_path: str, source_language: str = None) -> dict:
    """
    Transcrit l'audio d'une vidéo YouTube avec Faster-Whisper.
    Retourne les segments de texte avec leurs timestamps précis.

    POURQUOI DES SEGMENTS ET PAS UN SEUL TEXTE ?
    On a besoin de savoir QUAND chaque phrase est prononcée dans la vidéo
    pour pouvoir placer le bon audio TTS au bon moment.
    Exemple de segment :
    {
        "start": 12.340,    ← commence à 12 secondes 340ms
        "end": 15.680,      ← finit à 15 secondes 680ms
        "text": "Bonjour tout le monde",
        "duration": 3.340   ← dure 3.34 secondes
    }

    Paramètres :
    ------------
    audio_path : str
        Chemin vers le fichier WAV à transcrire
        Ex: "youtube/temp/a3f8c2d1/audio.wav"

    source_language : str ou None
        Langue de la vidéo : "fr", "en", "es", etc.
        None = Faster-Whisper détecte automatiquement la langue
        Recommandé : toujours spécifier si on la connaît → plus précis

    Valeur de retour : dict
    -----------------------
    Succès :
    {
        "success": True,
        "segments": [
            {"start": 0.0, "end": 3.2, "text": "Hello everyone", "duration": 3.2},
            {"start": 3.5, "end": 7.1, "text": "Welcome to my channel", "duration": 3.6},
            ...
        ],
        "language": "en",
        "language_probability": 0.99,
        "error": None
    }
    """

    try:
        logger.info(f"Transcription YouTube : {audio_path} | langue={source_language or 'auto'}")

        # On appelle le modèle Whisper chargé en mémoire
        # transcribe() retourne deux choses :
        # - segments : générateur de morceaux de texte avec timestamps
        # - info     : infos sur l'audio (langue détectée, durée...)
        segments, info = youtube_whisper_model.transcribe(
            audio_path,
            language=source_language,
            # None = détection automatique de la langue

            beam_size=5,
            # beam_size = nombre de "chemins" explorés simultanément
            # Plus élevé = plus précis mais plus lent
            # 5 = bon compromis vitesse/précision (valeur par défaut recommandée)
            # Analogie : comme chercher le meilleur chemin sur une carte
            # beam_size=1 = on prend le premier chemin trouvé
            # beam_size=5 = on explore 5 chemins et on garde le meilleur

            word_timestamps=False
            # False = timestamps au niveau des SEGMENTS (phrases entières)
            # True  = timestamps mot par mot
            # POURQUOI False ici ?
            # Pour la synchro vidéo, les segments sont plus stables et naturels
            # Les timestamps mot par mot peuvent être instables sur de longs audios
        )

        # -----------------------------------------------------------------
        # Assemblage des segments
        # -----------------------------------------------------------------
        # segments est un GÉNÉRATEUR — en Python, un générateur ne calcule
        # les données que quand on les demande (lazy evaluation)
        # Analogie : comme un robinet → l'eau coule seulement quand tu ouvres
        # On doit itérer (boucle for) pour obtenir tous les segments

        segments_list = []
        for segment in segments:
            # segment.start    = timestamp de début en secondes (float)
            # segment.end      = timestamp de fin en secondes (float)
            # segment.text     = le texte transcrit du segment (string)

            segments_list.append({
                "start": round(segment.start, 3),
                # round(x, 3) = arrondit à 3 décimales
                # Ex: 12.3456789 → 12.346
                # 3 décimales = précision à la milliseconde, suffisant pour la synchro

                "end": round(segment.end, 3),

                "text": segment.text.strip(),
                # .strip() supprime les espaces et retours à la ligne superflus
                # Whisper ajoute parfois des espaces en début/fin de segment

                "duration": round(segment.end - segment.start, 3)
                # On calcule la durée maintenant pour s'en servir plus tard
                # dans le time-stretching sans recalculer à chaque fois
            })

        if not segments_list:
            raise ValueError(
                "Aucun segment transcrit — audio vide ou inaudible"
            )

        logger.info(
            f"Transcription terminée : {len(segments_list)} segments | "
            f"langue={info.language} | confiance={info.language_probability:.0%}"
        )
        # :.0% = formate un float en pourcentage sans décimales
        # Ex: 0.987 → "99%"

        return {
            "success": True,
            "segments": segments_list,
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "error": None
        }

    except Exception as e:
        logger.error(f"Erreur transcription YouTube : {str(e)}")
        return {
            "success": False,
            "segments": [],
            "language": None,
            "language_probability": None,
            "error": str(e)
        }
    
    # =============================================================================
    # FONCTION 3 : generate_tts_segments()
    # Génère un fichier audio WAV par segment traduit avec Kokoro
    # =============================================================================

def generate_tts_segments(
    translated_segments: list,
    job_dir: str,
    target_language: str = "fr",
    voice: str = "",
    speed: float = 1.0
) -> dict:
    """
    Génère un fichier audio WAV pour chaque segment traduit avec Kokoro
    """
    try:
        # -----------------------------------------------------------------
        # Création du dossier pour les segments audio
        # -----------------------------------------------------------------
        segments_dir = os.path.join(job_dir, "segments")
        # Résultat : "youtube/temp/a3f8c2d1/segments"
        os.makedirs(segments_dir, exist_ok=True)
        logger.info(f"Génération TTS de {len(translated_segments)} segments...")

        # -----------------------------------------------------------------
        # Sélection du pipeline Kokoro selon la langue cible
        # -----------------------------------------------------------------
        pipeline, selected_voice = get_pipeline_and_voice(target_language, voice)
        # get_pipeline_and_voice retourne :
        # - pipeline_fr si target_language == "fr"
        # - pipeline_en sinon
        # - la voix sélectionnée (par défaut si voice == "")
        logger.info(f"Pipeline TTS sélectionné | langue={target_language} | voix={selected_voice}")

        # -----------------------------------------------------------------
        # Génération audio segment par segment
        # -----------------------------------------------------------------
        audio_segments = []
        # Liste qui contiendra les infos de chaque segment généré
        for i, segment in enumerate(translated_segments):
            # enumerate() donne l'index i ET le segment
            # i = 0, 1, 2, ... → pour nommer les fichiers segment_000.wav, etc.

            text_to_speak = segment["translated_text"]
            # C'est le texte traduit qu'on va transformer en audio

            # ────────────────────────────────────────────────
            # SOLUTION 1 : Ignorer les segments sans texte utile
            # ────────────────────────────────────────────────
            if not text_to_speak.strip() or text_to_speak.lower() in [
                "[music]", "[musique]", "[intro]", "[instrumental]",
                "[silence]", "[no speech]", "[background music]"
            ]:
                logger.info(
                    f"Segment {i:03d} ignoré (pas de texte / musique / silence) "
                    f"→ durée originale {segment.get('duration', 0):.1f}s | "
                    f"texte='{text_to_speak[:60]}...'"
                )
                continue

            try:
                # --- Génération audio avec Kokoro ---
                # pipeline() retourne un générateur de chunks audio
                # Même fonctionnement que dans tts_service.py
                generator = pipeline(
                    text_to_speak,
                    voice=selected_voice,
                    speed=speed
                )

                # Assemblage des chunks audio en un seul tableau numpy
                audio_chunks = []
                for (gs, ps, audio) in generator:
                    # gs = graphemes (texte du chunk)
                    # ps = phonemes (représentation phonétique)
                    # audio = tableau numpy avec les données audio
                    audio_chunks.append(audio)

                if not audio_chunks:
                    logger.warning(f"Kokoro n'a rien généré pour le segment {i}")
                    continue

                # np.concatenate colle tous les morceaux bout à bout
                # Résultat : un seul tableau numpy = l'audio complet du segment
                full_audio = np.concatenate(audio_chunks)

                # --- Calcul de la durée réelle de l'audio généré ---
                # len(full_audio) = nombre d'échantillons audio
                # 24000 = fréquence d'échantillonnage de Kokoro (24000 Hz)
                # durée = nombre d'échantillons / fréquence
                # Ex: 72000 échantillons / 24000 Hz = 3.0 secondes
                audio_duration = len(full_audio) / 24000
                # POURQUOI calculer ça ?
                # Pour le time-stretching à l'étape F :
                # on compare audio_duration (durée TTS) vs segment["duration"] (durée originale)
                # Si différence > 20% → on étire/compresse

                # --- Sauvegarde du fichier WAV ---
                # Nom formaté avec zéros devant pour tri alphabétique correct
                # segment_000.wav, segment_001.wav, ..., segment_099.wav
                # POURQUOI les zéros devant ?
                # Sans eux : segment_1, segment_10, segment_2 (ordre alphabétique cassé)
                # Avec eux : segment_000, segment_001, segment_002 (ordre correct)
                segment_filename = f"segment_{i:03d}.wav"
                # :03d = formate l'entier sur 3 chiffres avec zéros devant
                # Ex: 0 → "000", 5 → "005", 42 → "042"

                segment_path = os.path.join(segments_dir, segment_filename)
                sf.write(segment_path, full_audio, 24000)
                # sf.write(chemin, données_audio, fréquence_échantillonnage)
                # 24000 Hz = fréquence standard de Kokoro

                logger.info(
                    f"Segment {i:03d} généré | "
                    f"durée_originale={segment['duration']:.2f}s | "
                    f"durée_tts={audio_duration:.2f}s | "
                    f"texte={text_to_speak[:40]}..."
                )

                # Ajout des infos du segment à notre liste
                audio_segments.append({
                    "index": i,
                    "start": segment["start"],
                    # Timestamp de début dans la vidéo originale
                    "end": segment["end"],
                    # Timestamp de fin dans la vidéo originale
                    "duration": segment["duration"],
                    # Durée ORIGINALE du segment dans la vidéo
                    "original_text": segment["original_text"],
                    "translated_text": segment["translated_text"],
                    "audio_path": segment_path,
                    # Chemin vers le fichier WAV généré
                    "audio_duration": round(audio_duration, 3),
                    # Durée RÉELLE de l'audio TTS généré
                    # Peut être différente de "duration" !
                })

            except Exception as e:
                # Si Kokoro plante sur UN segment, on log et on continue
                # On ne veut pas que toute la vidéo échoue à cause d'un segment
                logger.error(f"Erreur génération segment {i} : {str(e)}")
                continue

        if not audio_segments:
            raise ValueError("Aucun segment audio généré — tous les segments ont échoué")

        logger.info(f"TTS terminé : {len(audio_segments)}/{len(translated_segments)} segments générés")

        return {
            "success": True,
            "segments_dir": segments_dir,
            "audio_segments": audio_segments,
            "error": None
        }

    except Exception as e:
        logger.error(f"Erreur génération TTS segments : {str(e)}")
        return {
            "success": False,
            "segments_dir": None,
            "audio_segments": [],
            "error": str(e)
        }