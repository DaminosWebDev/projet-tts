import os
import json
import logging
import re
import shutil
import subprocess

from config import YOUTUBE_OUTPUT_DIR, STRETCH_TOLERANCE

logger = logging.getLogger(__name__)

# Cibles EBU R128 — standard broadcast européen, utilisé par Spotify et YouTube
LOUDNORM_I   = -16.0  # Loudness intégrée en LUFS
LOUDNORM_TP  = -1.5   # True Peak max en dBTP
LOUDNORM_LRA = 11.0   # Loudness Range en LU


# ── ffprobe ───────────────────────────────────────────────────────────────────

def get_audio_duration(audio_path: str) -> float:
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data["streams"][0]["duration"])

    except Exception as e:
        logger.warning(f"Durée introuvable pour {audio_path} : {e}")
        return 0.0


# ── Time-stretching ───────────────────────────────────────────────────────────

def stretch_audio_segment(
    audio_path: str,
    target_duration: float,
    output_path: str
) -> dict:
    try:
        current_duration = get_audio_duration(audio_path)

        if current_duration <= 0:
            raise ValueError(f"Durée invalide : {current_duration}")

        ratio = target_duration / current_duration
        difference_pct = abs(1.0 - ratio)

        logger.info(
            f"Stretching | actuelle={current_duration:.2f}s | "
            f"cible={target_duration:.2f}s | ratio={ratio:.3f} | "
            f"diff={difference_pct:.0%}"
        )

        # Dans la tolérance — copie sans traitement
        if difference_pct <= STRETCH_TOLERANCE:
            shutil.copy2(audio_path, output_path)
            logger.info(f"Diff ≤{STRETCH_TOLERANCE:.0%} → copie sans stretching")
            return {
                "success": True, "output_path": output_path,
                "original_duration": current_duration,
                "target_duration": target_duration,
                "ratio": ratio, "stretched": False
            }

        # Limites qualité — au-delà l'oreille entend des artefacts
        if ratio < 0.5:
            logger.warning(f"Ratio {ratio:.3f} → limité à 0.5")
            ratio = 0.5
        elif ratio > 2.0:
            logger.warning(f"Ratio {ratio:.3f} → limité à 2.0")
            ratio = 2.0

        # tempo = inverse du ratio (rubberband travaille en vitesse, pas en durée)
        tempo = 1.0 / ratio

        cmd = [
            "ffmpeg", "-i", audio_path,
            "-filter:a", f"rubberband=tempo={tempo:.6f}",
            "-y", output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg : {result.stderr}")

        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Sortie introuvable : {output_path}")

        return {
            "success": True, "output_path": output_path,
            "original_duration": current_duration,
            "target_duration": target_duration,
            "ratio": round(ratio, 3), "stretched": True
        }

    except Exception as e:
        logger.error(f"Erreur stretching : {e}")
        return {
            "success": False, "output_path": None,
            "original_duration": 0, "target_duration": target_duration,
            "ratio": 0, "stretched": False, "error": str(e)
        }


# ── Loudnorm 2 passes ─────────────────────────────────────────────────────────

def _loudnorm_pass1(input_path: str) -> dict | None:
    # -f null - = aucun fichier produit — on veut uniquement les mesures dans stderr
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", (
            f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:"
            f"print_format=json"
        ),
        "-f", "null", "-"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        # ffmpeg écrit les mesures JSON dans stderr — comportement intentionnel, pas un bug
        json_match = re.search(r'\{[^{}]+\}', result.stderr, re.DOTALL)
        if not json_match:
            logger.error("loudnorm passe 1 : bloc JSON introuvable dans stderr")
            return None

        measures = json.loads(json_match.group())

        return {
            "measured_I":      float(measures["input_i"]),
            "measured_TP":     float(measures["input_tp"]),
            "measured_LRA":    float(measures["input_lra"]),
            "measured_thresh": float(measures["input_thresh"]),
        }

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"loudnorm passe 1 : parsing échoué : {e}")
        return None
    except subprocess.TimeoutExpired:
        logger.error("loudnorm passe 1 : timeout >120s")
        return None


def _loudnorm_pass2(input_path: str, output_path: str, measures: dict) -> dict:
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", (
            f"loudnorm="
            f"I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:"
            f"measured_I={measures['measured_I']}:"
            f"measured_TP={measures['measured_TP']}:"
            f"measured_LRA={measures['measured_LRA']}:"
            f"measured_thresh={measures['measured_thresh']}:"
            f"linear=true"  # Gain linéaire — pas de compression dynamique sur la voix
        ),
        "-ar", "24000",  # Fréquence Kokoro
        "-ac", "1",      # Mono
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"success": False, "error": f"passe 2 : {result.stderr[-200:]}"}
        return {"success": True, "output_path": output_path}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "passe 2 : timeout >120s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _apply_loudnorm_two_pass(input_path: str, output_path: str) -> dict:
    logger.info(f"loudnorm passe 1 : {os.path.basename(input_path)}")
    measures = _loudnorm_pass1(input_path)

    if measures is None:
        # Fallback une passe — mieux que rien si la mesure échoue
        logger.warning("passe 1 échouée → fallback une seule passe")
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}",
            "-ar", "24000", "-ac", "1", output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"success": False, "error": f"fallback : {result.stderr[-200:]}"}
        return {"success": True, "output_path": output_path, "passes": 1}

    logger.info(
        f"passe 1 OK → I={measures['measured_I']:.1f} LUFS | "
        f"TP={measures['measured_TP']:.1f} dBTP | "
        f"LRA={measures['measured_LRA']:.1f} LU"
    )

    logger.info(f"loudnorm passe 2 : cible {LOUDNORM_I} LUFS")
    result = _loudnorm_pass2(input_path, output_path, measures)

    if not result["success"]:
        return result

    return {"success": True, "output_path": output_path, "passes": 2}


# ── Assemblage final ──────────────────────────────────────────────────────────

def assemble_audio_track(
    audio_segments: list,
    job_id: str,
    job_dir: str,
    total_duration: float
) -> dict:
    try:
        # ── Étape F : Time-stretching ─────────────────────────────────────────
        stretched_dir = os.path.join(job_dir, "stretched")
        os.makedirs(stretched_dir, exist_ok=True)

        logger.info(f"Time-stretching de {len(audio_segments)} segments...")

        stretched_segments = []
        for segment in audio_segments:
            stretched_path = os.path.join(
                stretched_dir,
                f"stretched_{segment['index']:03d}.wav"
            )
            stretch_result = stretch_audio_segment(
                audio_path=segment["audio_path"],
                target_duration=segment["duration"],
                output_path=stretched_path
            )

            if stretch_result["success"]:
                stretched_segments.append({
                    **segment,
                    "audio_path": stretch_result["output_path"],
                    "stretched":  stretch_result["stretched"]
                })
            else:
                # Fallback — audio original non stretchés plutôt que pipeline échoué
                logger.warning(f"Stretching échoué segment {segment['index']} — audio original")
                stretched_segments.append({**segment, "stretched": False})

        # ── Étape G : Assemblage amix — mix brut sans loudnorm ────────────────
        mix_path = os.path.join(job_dir, f"mix_{job_id}.wav")

        cmd = ["ffmpeg", "-y"]
        for segment in stretched_segments:
            cmd += ["-i", segment["audio_path"]]

        filter_parts = []
        for i, segment in enumerate(stretched_segments):
            delay_ms = int(segment["start"] * 1000)  # secondes → millisecondes
            filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
            # adelay positionne chaque segment à son timestamp original

        audio_inputs = "".join([f"[a{i}]" for i in range(len(stretched_segments))])
        filter_parts.append(
            f"{audio_inputs}amix=inputs={len(stretched_segments)}:"
            f"duration=longest:dropout_transition=0[audio_out]"
            # loudnorm absent ici — appliqué en 2 passes séparées ci-dessous
        )

        cmd += [
            "-filter_complex", ";".join(filter_parts),
            "-map", "[audio_out]",
            "-ar", "24000",
            "-ac", "1",
            "-t", str(total_duration),
            mix_path
        ]

        logger.info(f"Assemblage mix brut : {mix_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg amix : {result.stderr[-500:]}")

        if not os.path.exists(mix_path):
            raise FileNotFoundError(f"Mix brut introuvable : {mix_path}")

        # ── Étape H : Loudnorm 2 passes ───────────────────────────────────────
        output_path = os.path.join(YOUTUBE_OUTPUT_DIR, f"audio_{job_id}.wav")
        os.makedirs(YOUTUBE_OUTPUT_DIR, exist_ok=True)

        logger.info(f"Loudnorm 2 passes : {mix_path} → {output_path}")
        loudnorm_result = _apply_loudnorm_two_pass(mix_path, output_path)

        if not loudnorm_result["success"]:
            raise RuntimeError(loudnorm_result["error"])

        logger.info(
            f"Piste finale : {output_path} "
            f"({loudnorm_result['passes']} passe(s) loudnorm)"
        )

        return {"success": True, "output_path": output_path, "error": None}

    except Exception as e:
        logger.error(f"Erreur assemblage : {e}")
        return {"success": False, "output_path": None, "error": str(e)}