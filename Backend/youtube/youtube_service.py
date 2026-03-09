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
    Télécharge UNIQUEMENT l'audio d'une vidéo YouTube en WAV.
    On ne télécharge plus la vidéo — elle sera jouée directement
    depuis YouTube en mode muet dans le frontend.

    POURQUOI ce changement ?
    Avant : téléchargement vidéo 4K (500MB+) = 40-50 secondes
    Après : téléchargement audio seulement (~10MB) = 5-8 secondes
    Gain : ~40 secondes sur le temps total de traitement

    Paramètres :
    ------------
    url : str
        URL complète de la vidéo YouTube
        Ex: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    job_id : str
        Identifiant unique du job, généré dans youtube_router.py
        Ex: "a3f8c2d1"

    Retourne : dict
    ---------------
    Succès :
    {
        "success": True,
        "job_dir": "youtube/temp/a3f8c2d1",
        "audio_path": "youtube/temp/a3f8c2d1/audio.wav",
        "youtube_url": "https://www.youtube.com/watch?v=...",
        "video_id": "dQw4w9WgXcQ",
        "title": "Titre de la vidéo",
        "duration": 213,
        "channel": "Nom chaîne",
        "error": None
    }
    """

    try:
        # -----------------------------------------------------------------
        # Création du dossier de travail isolé pour ce job
        # -----------------------------------------------------------------
        # Chaque job a son propre dossier pour éviter les conflits
        # si deux utilisateurs traitent des vidéos en même temps
        # Analogie : chaque client a son propre casier dans un vestiaire
        job_dir = os.path.join(YOUTUBE_TEMP_DIR, job_id)
        # os.path.join = construit le chemin compatible avec l'OS
        # Windows : "youtube\temp\a3f8c2d1"
        # Linux   : "youtube/temp/a3f8c2d1"

        os.makedirs(job_dir, exist_ok=True)
        # exist_ok=True = pas d'erreur si le dossier existe déjà
        # utile si on relance le même job (cas de debug)

        logger.info(f"Dossier job créé : {job_dir}")

        audio_path = os.path.join(job_dir, "audio.wav")
        # On définit le chemin final du fichier WAV à l'avance
        # pour pouvoir vérifier qu'il existe après le téléchargement

        # -----------------------------------------------------------------
        # Configuration de yt-dlp pour télécharger UNIQUEMENT l'audio
        # -----------------------------------------------------------------
        logger.info(f"Téléchargement audio depuis : {url}")

        audio_opts = {
            "format": "bestaudio/best",
            # "format" dit à yt-dlp QUOI télécharger
            # "bestaudio" = meilleur flux audio disponible sur YouTube
            # "/best" = fallback si pas de flux audio séparé disponible
            # DIFFÉRENCE AVEC AVANT :
            # Avant on avait deux appels :
            #   1. "bestvideo[ext=mp4]" → télécharge la vidéo 4K (lourd)
            #   2. "bestaudio/best"     → télécharge l'audio
            # Maintenant on fait UN SEUL appel audio → beaucoup plus rapide

            "outtmpl": os.path.join(job_dir, "audio.%(ext)s"),
            # "outtmpl" = output template = modèle du nom de fichier de sortie
            # %(ext)s sera remplacé par l'extension réelle du téléchargement
            # Ex: si yt-dlp télécharge du webm → "audio.webm"
            # Le postprocessor ci-dessous le convertira ensuite en "audio.wav"

            "postprocessors": [{
                # postprocessors = traitements appliqués APRÈS le téléchargement
                # C'est une liste car on peut chaîner plusieurs traitements
                # Dans notre cas on n'en a qu'un seul : la conversion en WAV

                "key": "FFmpegExtractAudio",
                # "FFmpegExtractAudio" = utilise ffmpeg pour extraire/convertir l'audio
                # yt-dlp appelle ffmpeg automatiquement en arrière-plan
                # C'est pour ça qu'on avait besoin d'installer ffmpeg !

                "preferredcodec": "wav",
                # On veut du WAV en sortie
                # WAV = format audio non compressé = parfait pour Whisper
                # POURQUOI WAV et pas MP3 ?
                # WAV = données brutes sans perte = meilleure qualité pour l'IA
                # MP3 = compressé avec perte = moins bon pour la transcription

                "preferredquality": "192",
                # Qualité audio en kbps (kilobits par seconde)
                # 192 = bonne qualité, suffisant pour la transcription vocale
                # On n'a pas besoin de 320kbps (qualité music) pour Whisper
            }],

            "quiet": True,
            # quiet = True → yt-dlp n'affiche rien dans le terminal
            # Sans ça, yt-dlp afficherait une barre de progression verbeuse
            # qui polluerait nos logs

            "no_warnings": True,
            # Supprime les avertissements de yt-dlp
        }

        # -----------------------------------------------------------------
        # Téléchargement + extraction des métadonnées en UN SEUL appel
        # -----------------------------------------------------------------
        video_info = {}
        # Dictionnaire vide qu'on va remplir avec les infos de la vidéo

        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            # "with ... as ydl" = gestionnaire de contexte
            # Ouvre yt-dlp, exécute le code dans le bloc, puis ferme proprement
            # Même principe que "with open(fichier) as f:"

            info = ydl.extract_info(url, download=True)
            # extract_info() fait deux choses simultanément :
            # 1. Télécharge l'audio (download=True)
            # 2. Retourne un dict avec TOUTES les métadonnées de la vidéo
            # Ce dict contient : titre, durée, chaîne, ID, miniature, etc.
            # AVANTAGE : on récupère les métadonnées GRATUITEMENT
            # pendant le téléchargement, sans appel réseau supplémentaire

            video_id = info.get("id", "")
            # "id" = l'identifiant unique YouTube de la vidéo
            # C'est la partie après "?v=" dans l'URL
            # Ex: "https://youtube.com/watch?v=dQw4w9WgXcQ" → id = "dQw4w9WgXcQ"
            # POURQUOI on en a besoin ?
            # Pour construire l'URL du player YouTube embarqué dans le frontend :
            # https://www.youtube.com/embed/dQw4w9WgXcQ?mute=1&autoplay=1
            # C'est cette URL qu'on mettra dans une balise <iframe> sur le site

            video_info = {
                "title": info.get("title", "Sans titre"),
                # .get("title", "Sans titre") = récupère "title" du dict
                # Si "title" n'existe pas → retourne "Sans titre" par défaut
                # C'est plus sûr que info["title"] qui planterait si absent

                "duration": info.get("duration", 0),
                # Durée en secondes
                # Ex: 213 pour une vidéo de 3min33s

                "channel": info.get("channel", "Inconnu"),
                # Nom de la chaîne YouTube

                "video_id": video_id,
                # L'ID extrait ci-dessus

                "youtube_url": url,
                # On garde l'URL ORIGINALE fournie par l'utilisateur
                # pour la retourner au frontend qui en aura besoin
                # pour le player embarqué
            }

        logger.info(f"Audio téléchargé : {video_info['title']} ({video_info['duration']}s)")

        # -----------------------------------------------------------------
        # Vérification que le fichier WAV a bien été créé
        # -----------------------------------------------------------------
        if not os.path.exists(audio_path):
            # yt-dlp peut parfois échouer silencieusement sans lever d'exception
            # Cette vérification explicite nous protège contre ce cas
            raise FileNotFoundError(
                f"Fichier audio introuvable après téléchargement : {audio_path}"
            )
            # raise = on "lance" l'erreur manuellement
            # Elle sera capturée par le except ci-dessous

        # Tout s'est bien passé → on retourne les infos
        return {
            "success": True,
            "job_dir": job_dir,
            "audio_path": audio_path,

            "youtube_url": video_info["youtube_url"],
            # L'URL YouTube originale
            # Utilisée par le frontend pour le player iframe

            "video_id": video_info["video_id"],
            # L'ID YouTube
            # Permet de construire : youtube.com/embed/{video_id}?mute=1

            "title": video_info["title"],
            "duration": video_info["duration"],
            "channel": video_info["channel"],
            "error": None
            # None = pas d'erreur
        }

    except Exception as e:
        # Exception = capture N'IMPORTE QUELLE erreur du bloc try
        # str(e) = convertit l'erreur en message texte lisible
        logger.error(f"Erreur téléchargement YouTube : {str(e)}")
        return {
            "success": False,
            "job_dir": None,
            "audio_path": None,
            "youtube_url": None,
            "video_id": None,
            "title": None,
            "duration": None,
            "channel": None,
            "error": str(e)
            # On retourne le message d'erreur pour que le router
            # puisse l'afficher dans la réponse HTTP
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