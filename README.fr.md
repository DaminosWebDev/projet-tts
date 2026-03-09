# VoxBridge — Plateforme IA de traitement vocal

Application web fullstack permettant la **synthèse vocale** (TTS), la **transcription audio** (STT) et la **traduction de vidéos YouTube** avec doublage automatique.

---

## Table des matières

- [Architecture globale](#architecture-globale)
- [Stack technique](#stack-technique)
- [Structure du projet](#structure-du-projet)
- [Fonctionnalités](#fonctionnalités)
- [Pipeline YouTube](#pipeline-youtube)
- [API — Endpoints](#api--endpoints)
- [Installation](#installation)
- [Variables d'environnement](#variables-denvironnement)
- [Sécurité](#sécurité)
- [Auteur](#auteur)

---

## Architecture globale

```
Utilisateur
    │
    ▼
React + Vite (port 5173)
    │  Axios — requêtes HTTP
    ▼
FastAPI (port 8000)
    ├── /auth      → JWT + Google OAuth 2.0
    ├── /tts       → Kokoro-82M (synthèse vocale)
    ├── /stt       → Faster-Whisper (transcription)
    ├── /youtube   → Pipeline de traduction asynchrone
    └── /users     → Historique utilisateur
         │
         ├── PostgreSQL (SQLAlchemy async + Alembic)
         ├── LibreTranslate (Docker — traduction offline)
         └── ffmpeg + Rubber Band (time-stretching audio)
```

Le backend expose une API REST. Chaque fonctionnalité est isolée dans son propre router et service — un changement de modèle IA n'affecte qu'un seul fichier.

---

## Stack technique

### Backend

| Technologie | Version | Rôle |
|---|---|---|
| Python | 3.10+ | Langage principal |
| FastAPI | — | Framework API REST async |
| Uvicorn | — | Serveur ASGI |
| SQLAlchemy | 2.x async | ORM base de données |
| Alembic | — | Migrations de schéma |
| PostgreSQL | — | Base de données principale |
| Pydantic | v2 | Validation et sérialisation |
| Kokoro-82M | 0.9.4 | Modèle Text-to-Speech |
| Faster-Whisper | — | Modèle Speech-to-Text |
| LibreTranslate | Docker | Traduction offline |
| ffmpeg + Rubber Band | — | Time-stretching et assemblage audio |
| yt-dlp | — | Téléchargement audio YouTube |
| httpx | — | Client HTTP async (LibreTranslate) |
| python-jose | — | Génération et vérification JWT |
| bcrypt | — | Hachage des mots de passe |
| soundfile | — | Lecture/écriture fichiers WAV |

### Frontend

| Technologie | Rôle |
|---|---|
| React | Framework UI |
| Vite | Build et dev server |
| Axios | Requêtes HTTP |

---

## Structure du projet

```
Backend/
├── main.py                    → Point d'entrée FastAPI — routers, CORS, lifespan
├── config.py                  → Configuration centralisée — tous les os.getenv()
├── database.py                → Engine async, session, Base SQLAlchemy
├── alembic.ini                → Configuration Alembic
│
├── migrations/
│   └── env.py                 → Connexion Alembic ↔ modèles SQLAlchemy
│
├── models/
│   ├── user.py                → Modèle User — auth, OAuth, tokens
│   ├── job_tts.py             → Historique jobs TTS
│   ├── job_stt.py             → Historique jobs STT
│   └── job_youtube.py         → Historique jobs YouTube
│
├── schemas/
│   └── history.py             → Schémas Pydantic pour l'API d'historique
│
├── auth/
│   ├── password.py            → Hachage bcrypt, vérification, force du mot de passe
│   ├── jwt.py                 → Création et vérification des tokens JWT
│   ├── dependencies.py        → get_current_user, get_optional_user, get_current_admin
│   └── oauth.py               → Google OAuth 2.0 — Authorization Code Flow
│
├── routers/
│   ├── auth_router.py         → /auth — register, login, refresh, OAuth, reset password
│   ├── tts_router.py          → /tts — synthèse vocale, liste des voix, téléchargement
│   ├── stt_router.py          → /stt — transcription fichier uploadé et microphone
│   ├── youtube_router.py      → /youtube — pipeline asynchrone, status, audio final
│   └── users_router.py        → /users — historique par type
│
├── tts/
│   └── tts_service.py         → Moteur Kokoro — pipelines FR/EN, génération WAV
│
├── stt/
│   └── stt_service.py         → Moteur Faster-Whisper — transcription, langues
│
├── youtube/
│   ├── youtube_service.py     → Téléchargement yt-dlp, transcription, TTS par segment
│   ├── sync_service.py        → Time-stretching ffmpeg, assemblage amix, loudnorm 2 passes
│   └── job_manager.py         → Gestionnaire d'état en mémoire — TTL automatique
│
├── translation/
│   └── translate_service.py   → Traduction async en parallèle — asyncio.gather
│
├── emails/
│   └── email_service.py       → Envoi d'emails (vérification, reset password)
│
├── audio_files/               → Fichiers WAV générés par le TTS
├── uploads/                   → Fichiers audio temporaires STT
└── youtube/
    ├── temp/                  → Dossiers de travail par job YouTube
    └── outputs/               → Pistes audio finales traduites
```

---

## Fonctionnalités

### Text-to-Speech (TTS)
- Synthèse vocale en **français** et **anglais**
- 11 voix disponibles — 1 FR, 10 EN
- Contrôle de la vitesse de lecture (0.5× à 2.0×)
- Pré-écoute directe dans le navigateur
- Téléchargement du fichier WAV
- Historique des 5 dernières synthèses (utilisateurs connectés)

### Speech-to-Text (STT)
- Transcription de **fichiers audio uploadés** (WAV, MP3, OGG, WebM, M4A)
- Transcription **depuis le microphone** directement dans le navigateur
- Détection automatique de la langue (99 langues supportées par Whisper)
- Retour des **timestamps par segment**
- Niveau de confiance de la détection de langue
- Historique des 5 dernières transcriptions (utilisateurs connectés)

### Pipeline YouTube
- Traduction de vidéos YouTube en **doublage audio synchronisé**
- Pipeline entièrement **asynchrone** — pas de blocage HTTP
- Progression en temps réel consultable par polling
- La vidéo YouTube reste jouée depuis YouTube (iframe muet), seule la piste audio est remplacée
- Piste finale **normalisée EBU R128** (loudnorm 2 passes — précision ±0.1 LUFS)

### Authentification
- Inscription avec vérification par email
- Connexion JWT (access token 30min + refresh token 30 jours)
- Rotation des refresh tokens à chaque renouvellement
- Connexion Google OAuth 2.0
- Réinitialisation du mot de passe par email
- Vérification de la force du mot de passe côté serveur

---

## Pipeline YouTube

Le pipeline transforme une vidéo YouTube anglaise en piste audio française en 6 étapes.

```
POST /youtube/process
    │
    ├── B — Téléchargement audio (yt-dlp → WAV)
    │
    ├── C — Transcription (Whisper medium → segments horodatés)
    │
    ├── D — Traduction (LibreTranslate — 80 segments en parallèle via asyncio.gather)
    │
    ├── E — Synthèse vocale (Kokoro — un WAV par segment)
    │
    ├── F — Time-stretching (ffmpeg + Rubber Band — ajuste chaque segment à sa durée originale)
    │
    └── G+H — Assemblage + Normalisation
              adelay positionne chaque segment à son timestamp
              amix fusionne tous les flux
              loudnorm 2 passes → piste finale normalisée

GET /youtube/status/{job_id}   → progression 0-100% + étape courante
GET /youtube/audio/{job_id}    → téléchargement de la piste WAV finale
```

**Durée typique :** 2-5 minutes pour une vidéo de 20 minutes.

---

## API — Endpoints

### Authentification — `/auth`

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | Non | Inscription |
| POST | `/auth/login` | Non | Connexion — retourne access + refresh token |
| POST | `/auth/refresh` | Non | Renouvellement du token (rotation) |
| GET | `/auth/me` | JWT | Profil de l'utilisateur connecté |
| POST | `/auth/forgot-password` | Non | Envoi du lien de réinitialisation |
| POST | `/auth/reset-password` | Non | Réinitialisation avec token email |
| GET | `/auth/google/login` | Non | URL d'autorisation Google OAuth |
| GET | `/auth/google/callback` | Non | Callback OAuth — retourne les tokens JWT |

### Text-to-Speech — `/tts`

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/voices` | Non | Liste des voix disponibles par langue |
| POST | `/tts` | Optionnelle | Génère un fichier WAV |
| GET | `/audio/{filename}` | Non | Télécharge un fichier audio généré |

```json
// POST /tts — Corps de la requête
{
    "text": "Bonjour, comment allez-vous ?",
    "language": "fr",
    "voice": "ff_siwis",
    "speed": 1.0
}
```

### Speech-to-Text — `/stt`

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/stt/languages` | Non | Langues supportées |
| POST | `/stt/upload` | Optionnelle | Transcrit un fichier audio uploadé |
| POST | `/stt/record` | Optionnelle | Transcrit un enregistrement micro |

### YouTube — `/youtube`

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/youtube/process` | Optionnelle | Lance le pipeline — retourne `job_id` (202) |
| GET | `/youtube/status/{job_id}` | Non | État et progression du job |
| GET | `/youtube/audio/{job_id}` | Non | Piste audio finale (WAV) |

```json
// POST /youtube/process
{ "url": "https://www.youtube.com/watch?v=...", "target_language": "fr" }

// GET /youtube/status/{job_id}
{
    "job_id": "a3f8c2d1-...",
    "status": "processing",
    "current_step": "C_transcribe",
    "progress": 25,
    "audio_url": null,
    "error": null
}
```

### Historique — `/users`

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/users/me/history` | JWT | Les 5 derniers jobs de chaque type |
| GET | `/users/me/history/tts` | JWT | Les 5 derniers jobs TTS |
| GET | `/users/me/history/stt` | JWT | Les 5 derniers jobs STT |
| GET | `/users/me/history/youtube` | JWT | Les 5 derniers jobs YouTube |

---

## Installation

### Prérequis

- Python 3.10+
- Node.js 20+
- PostgreSQL
- ffmpeg compilé avec `--enable-librubberband`
- Docker (pour LibreTranslate)
- GPU NVIDIA recommandé (CUDA)

### 1. Backend

```bash
# Cloner et se placer dans le backend
cd Backend

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (voir section suivante)

# Appliquer les migrations base de données
alembic upgrade head

# Lancer le serveur
python main.py
```

Serveur disponible sur `http://localhost:8000`
Documentation interactive : `http://localhost:8000/docs`

### 2. LibreTranslate (Docker)

```bash
docker run -d \
  -p 5000:5000 \
  --name libretranslate \
  libretranslate/libretranslate \
  --load-only fr,en
```

### 3. Frontend

```bash
cd Frontend

npm install
npm run dev
```

Interface disponible sur `http://localhost:5173`

---

## Variables d'environnement

```env
# Base de données
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/voxbridge

# JWT
JWT_SECRET_KEY=votre_cle_secrete_longue_et_aleatoire
JWT_ALGORITHM=HS256

# Google OAuth
GOOGLE_CLIENT_ID=votre_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=votre_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# HuggingFace (téléchargement Kokoro)
HF_TOKEN=votre_token_huggingface

# LibreTranslate
LIBRETRANSLATE_URL=http://localhost:5000
LIBRETRANSLATE_API_KEY=

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre@email.com
SMTP_PASSWORD=votre_mot_de_passe_application

# Modèles IA
STT_MODEL_SIZE=small
STT_DEVICE=cuda
STT_COMPUTE_TYPE=float16
YOUTUBE_WHISPER_MODEL=medium
```

---

## Sécurité

| Mesure | Implémentation |
|---|---|
| Mots de passe | Bcrypt rounds=12 — ~0.25s par hash |
| Tokens JWT | HS256, access 30min, refresh 30 jours avec rotation |
| Tokens email | UUID stockés en DB — révocables immédiatement |
| Enum. emails | Messages d'erreur identiques login/forgot-password |
| OAuth CSRF | State token à usage unique (secrets.token_hex) |
| Types MIME | Liste blanche explicite pour les uploads STT |
| Isolation DB | Chaque utilisateur ne voit que ses propres données |

---

## Auteur

**Damien** — Projet fullstack IA  
Apprentissage : FastAPI · SQLAlchemy async · JWT · OAuth 2.0 · Modèles IA (Whisper, Kokoro) · Pipeline audio (ffmpeg, Rubber Band, EBU R128)