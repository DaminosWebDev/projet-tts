# =============================================================================
# translate_service.py - Traduction des segments avec LibreTranslate
# =============================================================================
# Ce fichier s'occupe de traduire les segments de texte transcrits par Whisper
# vers la langue cible choisie par l'utilisateur.
#
# POURQUOI UN FICHIER SÉPARÉ ?
# La traduction est une responsabilité indépendante du téléchargement
# et de la transcription. Séparer les responsabilités = code plus propre,
# plus facile à tester et à modifier.
# Si on veut changer de service de traduction (DeepL, Google, etc.)
# on ne touche qu'à CE fichier, rien d'autre ne change.
#
# COMMENT ÇA MARCHE ?
# On envoie une requête HTTP à LibreTranslate (qui tourne dans Docker)
# LibreTranslate reçoit le texte + langue source + langue cible
# et retourne le texte traduit.
# C'est exactement comme appeler une API externe.
# =============================================================================


# =============================================================================
# IMPORTS
# =============================================================================

import logging
# logging = pour afficher les messages dans le terminal
# Même usage que dans les autres fichiers du projet

import httpx
# httpx = bibliothèque pour faire des requêtes HTTP depuis Python
# On l'utilise pour appeler l'API de LibreTranslate
# POURQUOI httpx et pas requests ?
# httpx supporte async/await nativement
# FastAPI est un framework asynchrone — utiliser requests bloquerait
# tout le serveur pendant qu'on attend la réponse de LibreTranslate
# Analogie : requests = appel téléphonique synchrone (tu attends en ligne)
#            httpx async = SMS (tu envoies et continues ta vie)

import asyncio
# asyncio = module intégré à Python pour la programmation asynchrone
# On l'utilise pour lancer plusieurs traductions EN PARALLÈLE
# au lieu de les faire une par une
# Analogie : au lieu de traduire 40 segments les uns après les autres
# (40 x 0.5s = 20 secondes), on les envoie tous en même temps
# et on attend que tous soient finis (~0.5s total)

from typing import List, Dict
# typing = module pour les annotations de types
# List[Dict] = une liste de dictionnaires
# Ça aide VS Code à comprendre la structure des données
# et à afficher des suggestions pertinentes

from config import (
    LIBRETRANSLATE_URL,
    # LIBRETRANSLATE_URL = "http://localhost:5000"
    # L'URL où tourne notre instance LibreTranslate dans Docker

    LIBRETRANSLATE_API_KEY
    # LIBRETRANSLATE_API_KEY = ""
    # Clé API optionnelle — vide pour notre instance locale
    # Nécessaire uniquement pour l'instance publique libretranslate.com
)


# =============================================================================
# CONFIGURATION DU LOGGER
# =============================================================================

logger = logging.getLogger(__name__)
# __name__ = "youtube.translate_service"
# Les logs apparaîtront comme :
# "youtube.translate_service | INFO | Traduction segment 1/40..."


# =============================================================================
# FONCTION 1 : translate_text()
# Traduit UN seul texte via l'API LibreTranslate
# =============================================================================

async def translate_text(
    text: str,
    source_lang: str,
    target_lang: str,
    client: httpx.AsyncClient
) -> str:
    """
    Traduit un texte depuis source_lang vers target_lang.

    POURQUOI async ?
    Cette fonction fait un appel réseau (HTTP vers LibreTranslate)
    qui peut prendre 100-500ms. Avec async, Python peut faire autre
    chose pendant qu'il attend la réponse — notamment lancer d'autres
    traductions en parallèle.

    Paramètres :
    ------------
    text : str
        Le texte à traduire
        Ex: "Never gonna give you up"

    source_lang : str
        Langue du texte original
        Ex: "en" pour anglais

    target_lang : str
        Langue de destination
        Ex: "fr" pour français

    client : httpx.AsyncClient
        Le client HTTP partagé pour toutes les requêtes
        POURQUOI le passer en paramètre plutôt qu'en créer un nouveau ?
        Créer un client HTTP a un coût (connexion TCP, handshake, etc.)
        En partageant UN seul client pour toutes les traductions,
        on réutilise les connexions existantes = beaucoup plus rapide
        Analogie : au lieu d'ouvrir et fermer une nouvelle fenêtre
        de navigateur pour chaque page, on réutilise le même onglet

    Retourne : str
        Le texte traduit, ou le texte original si la traduction échoue
    """

    try:
        # Construction du corps de la requête HTTP
        # C'est ce qu'on envoie à LibreTranslate
        payload = {
            "q": text,
            # "q" = query = le texte à traduire
            # C'est le paramètre attendu par l'API LibreTranslate

            "source": source_lang,
            # La langue source : "en", "fr", "es", etc.
            # LibreTranslate accepte aussi "auto" pour la détection
            # mais on préfère être explicite pour plus de précision

            "target": target_lang,
            # La langue cible : "fr", "en", etc.

            "api_key": LIBRETRANSLATE_API_KEY,
            # Clé API : "" pour notre instance locale
            # Sans clé, l'instance publique limite les requêtes
        }

        # Envoi de la requête POST à LibreTranslate
        # POST /translate = l'endpoint de traduction de LibreTranslate
        response = await client.post(
            f"{LIBRETRANSLATE_URL}/translate",
            # f-string = chaîne formatée avec la valeur de LIBRETRANSLATE_URL
            # Résultat : "http://localhost:5000/translate"

            json=payload,
            # json=payload convertit automatiquement le dict Python en JSON
            # et ajoute le header "Content-Type: application/json"

            timeout=30.0
            # timeout = délai maximum d'attente en secondes
            # Si LibreTranslate ne répond pas en 30s → erreur timeout
            # Sans timeout, on pourrait attendre indéfiniment
        )

        # Vérification du code de réponse HTTP
        response.raise_for_status()
        # raise_for_status() lève une exception si le code HTTP est une erreur
        # 200 OK → rien ne se passe
        # 400, 500, etc. → lève une exception HTTPStatusError
        # C'est plus propre que de vérifier response.status_code manuellement

        # Extraction du texte traduit depuis la réponse JSON
        result = response.json()
        # response.json() parse automatiquement le JSON reçu en dict Python
        # La réponse de LibreTranslate ressemble à :
        # {"translatedText": "Je ne vais jamais te lâcher"}

        translated = result.get("translatedText", text)
        # .get("translatedText", text) = récupère "translatedText"
        # Si la clé n'existe pas → retourne "text" (texte original) par défaut
        # C'est un filet de sécurité : si LibreTranslate retourne un format
        # inattendu, on garde le texte original plutôt que de planter

        return translated

    except httpx.TimeoutException:
        # TimeoutException = LibreTranslate n'a pas répondu à temps
        logger.warning(f"Timeout traduction, texte original conservé : {text[:50]}...")
        return text
        # On retourne le texte ORIGINAL si la traduction échoue
        # Mieux vaut une vidéo avec quelques phrases non traduites
        # qu'une vidéo complètement ratée

    except Exception as e:
        # Toute autre erreur (réseau, JSON malformé, etc.)
        logger.warning(f"Erreur traduction ({str(e)}), texte original conservé")
        return text


# =============================================================================
# FONCTION 2 : translate_segments()
# Traduit TOUS les segments en parallèle
# =============================================================================

async def translate_segments(
    segments: List[Dict],
    source_lang: str,
    target_lang: str
) -> dict:
    """
    Traduit tous les segments de transcription en parallèle.

    POURQUOI EN PARALLÈLE ?
    Une vidéo de 20 minutes peut avoir 80+ segments.
    En séquentiel (un par un) : 80 x 0.3s = 24 secondes
    En parallèle (tous en même temps) : ~0.3-1s total
    C'est la puissance de l'async/await avec asyncio.gather()

    Paramètres :
    ------------
    segments : List[Dict]
        Liste des segments retournés par transcribe_youtube_audio()
        Chaque segment : {"start": 0.0, "end": 3.2, "text": "...", "duration": 3.2}

    source_lang : str
        Langue originale de la vidéo ("en", "fr", etc.)

    target_lang : str
        Langue de destination ("fr", "en", etc.)

    Retourne : dict
    ---------------
    Succès :
    {
        "success": True,
        "segments": [
            {
                "start": 0.0,
                "end": 3.2,
                "duration": 3.2,
                "original_text": "Never gonna give you up",
                "translated_text": "Je ne vais jamais te lâcher"
            },
            ...
        ],
        "error": None
    }
    """

    try:
        logger.info(
            f"Traduction de {len(segments)} segments | "
            f"{source_lang} → {target_lang}"
        )

        # -----------------------------------------------------------------
        # Création du client HTTP partagé
        # -----------------------------------------------------------------
        # httpx.AsyncClient = client HTTP asynchrone
        # On le crée UNE SEULE FOIS et on le partage entre toutes les requêtes
        # Le "async with" garantit que le client est fermé proprement
        # même si une erreur survient — libère les connexions réseau
        async with httpx.AsyncClient() as client:

            # -----------------------------------------------------------------
            # Création des tâches de traduction en parallèle
            # -----------------------------------------------------------------
            # On crée une liste de "coroutines" (tâches async)
            # une par segment, sans les lancer encore
            tasks = [
                translate_text(
                    text=segment["text"],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    client=client
                )
                for segment in segments
                # list comprehension = façon concise de créer une liste
                # équivalent à :
                # tasks = []
                # for segment in segments:
                #     tasks.append(translate_text(...))
            ]

            # -----------------------------------------------------------------
            # Lancement de TOUTES les traductions en parallèle
            # -----------------------------------------------------------------
            # asyncio.gather() lance toutes les tâches simultanément
            # et attend que TOUTES soient terminées avant de continuer
            # Retourne une liste de résultats dans le même ordre que tasks
            # Analogie : comme envoyer 40 SMS en même temps et
            # attendre que tous les destinataires aient répondu
            translated_texts = await asyncio.gather(*tasks)
            # *tasks = décompresse la liste en arguments séparés
            # gather(task1, task2, task3, ...) au lieu de gather([task1, task2, ...])

        # -----------------------------------------------------------------
        # Assemblage des segments traduits
        # -----------------------------------------------------------------
        # On combine chaque segment original avec sa traduction
        translated_segments = []
        for i, segment in enumerate(segments):
            # enumerate() retourne à la fois l'INDEX (i) et la VALEUR (segment)
            # i = 0, 1, 2, 3... → permet d'accéder à translated_texts[i]

            translated_segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "duration": segment["duration"],
                "original_text": segment["text"],
                # On garde le texte original pour référence et débogage

                "translated_text": translated_texts[i]
                # Le texte traduit correspondant à ce segment
                # translated_texts[i] = résultat de la i-ème traduction
            })

        logger.info(f"Traduction terminée : {len(translated_segments)} segments traduits")

        return {
            "success": True,
            "segments": translated_segments,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "error": None
        }

    except Exception as e:
        logger.error(f"Erreur lors de la traduction des segments : {str(e)}")
        return {
            "success": False,
            "segments": [],
            "source_lang": source_lang,
            "target_lang": target_lang,
            "error": str(e)
        }