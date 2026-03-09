import logging
import asyncio
import httpx

from config import LIBRETRANSLATE_URL, LIBRETRANSLATE_API_KEY

logger = logging.getLogger(__name__)


async def translate_text(
    text: str,
    source_lang: str,
    target_lang: str,
    client: httpx.AsyncClient
) -> str:
    try:
        response = await client.post(
            f"{LIBRETRANSLATE_URL}/translate",
            json={
                "q":       text,
                "source":  source_lang,
                "target":  target_lang,
                "api_key": LIBRETRANSLATE_API_KEY,
            },
            timeout=30.0
        )
        response.raise_for_status()

        # Fallback sur le texte original si la clé "translatedText" est absente
        return response.json().get("translatedText", text)

    except httpx.TimeoutException:
        logger.warning(f"Timeout traduction — texte original conservé : {text[:50]}")
        return text  # Degradation gracieuse — mieux que de faire échouer le pipeline

    except Exception as e:
        logger.warning(f"Erreur traduction ({e}) — texte original conservé")
        return text


async def translate_segments(
    segments: list[dict],
    source_lang: str,
    target_lang: str
) -> dict:
    try:
        logger.info(f"Traduction {len(segments)} segments | {source_lang} → {target_lang}")

        # Client HTTP unique partagé entre toutes les requêtes — réutilise les connexions TCP
        async with httpx.AsyncClient() as client:
            tasks = [
                translate_text(
                    text=segment["text"],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    client=client
                )
                for segment in segments
            ]

            # Lance toutes les traductions simultanément — temps total ≈ temps d'une seule
            translated_texts = await asyncio.gather(*tasks)

        translated_segments = [
            {
                "start":           segment["start"],
                "end":             segment["end"],
                "duration":        segment["duration"],
                "original_text":   segment["text"],
                "translated_text": translated_texts[i],
            }
            for i, segment in enumerate(segments)
        ]

        logger.info(f"Traduction terminée : {len(translated_segments)} segments")

        return {
            "success":     True,
            "segments":    translated_segments,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "error":       None
        }

    except Exception as e:
        logger.error(f"Erreur traduction segments : {e}")
        return {
            "success":     False,
            "segments":    [],
            "source_lang": source_lang,
            "target_lang": target_lang,
            "error":       str(e)
        }