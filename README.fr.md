# 🎙️ Projet TTS — Text-to-Speech avec Kokoro v0.19

Application web de synthèse vocale qui transforme du texte en audio naturel.
L'utilisateur saisit un texte, choisit une langue et une voix, et génère un fichier audio qu'il peut écouter et télécharger.

---

## 🏗️ Architecture
```
Utilisateur → React (port 5173)
                  ↓ Axios POST /tts
             FastAPI (port 8000)
                  ↓ Kokoro v0.19
             Génération audio WAV
                  ↓
             Player + Téléchargement
```

Le projet est séparé en deux parties indépendantes qui communiquent via une API REST :

- **Backend** : API FastAPI en Python qui intègre le modèle Kokoro
- **Frontend** : Interface utilisateur React + Vite

---

## 🛠️ Stack technique

| Technologie | Rôle |
|-------------|------|
| Python | Langage backend |
| FastAPI | Framework API REST |
| Uvicorn | Serveur HTTP |
| Pydantic | Validation des données |
| Kokoro v0.19 | Modèle Text-to-Speech |
| soundfile | Écriture fichiers audio |
| React | Framework frontend |
| Vite | Outil de build |
| Axios | Requêtes HTTP |

---

## 📁 Structure du projet
```
PROJET TTS/
├── BACKEND/
│   ├── config.py          → Configuration centralisée
│   ├── tts_service.py     → Moteur Kokoro
│   ├── main.py            → Serveur FastAPI
│   ├── audio_files/       → Fichiers audio générés
│   ├── requirements.txt   → Dépendances Python
│   └── .env               → Variables secrètes (non commité)
└── FRONTEND/
    └── tts-project/
        └── src/
            └── App.jsx    → Interface utilisateur
```

---

## 🔌 Endpoints de l'API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Vérifie que l'API est en ligne |
| GET | `/voices` | Liste les voix disponibles |
| POST | `/tts` | Génère un fichier audio |
| GET | `/audio/{filename}` | Télécharge un fichier audio |

### Exemple de requête POST /tts
```json
{
    "text": "Bonjour, ceci est un test.",
    "language": "fr",
    "voice": "ff_siwis",
    "speed": 1.0
}
```

---

## 🚀 Installation et lancement

### Prérequis
- Python 3.10+
- Node.js 20+
- GPU NVIDIA (recommandé)

### Backend
```bash
# Créer et activer l'environnement virtuel
python -m venv .venv
.venv\Scripts\activate

# Installer les dépendances
cd BACKEND
pip install -r requirements.txt

# Créer le fichier .env
cp .env.example .env
# Ajouter votre HF_TOKEN dans le fichier .env

# Lancer le serveur
python main.py
```

Le serveur démarre sur `http://localhost:8000`
La documentation interactive est disponible sur `http://localhost:8000/docs`

### Frontend
```bash
cd FRONTEND/tts-project

# Installer les dépendances
npm install

# Lancer le serveur de développement
npm run dev
```

L'interface est disponible sur `http://localhost:5173`

---

## 🎯 Fonctionnalités

- ✅ Synthèse vocale français et anglais
- ✅ Choix parmi plusieurs voix
- ✅ Contrôle de la vitesse de lecture
- ✅ Pré-écoute directe dans le navigateur
- ✅ Téléchargement du fichier audio
- ✅ Gestion des erreurs
- ✅ Logs serveur

---

## 🔒 Sécurité (prévue en production)

- Authentification JWT
- HTTPS
- Rate limiting
- Restriction CORS à l'URL du frontend

---

## 🗺️ Roadmap

- [ ] Fonctionnalité Speech-to-Text
- [ ] Système de comptes utilisateurs
- [ ] Historique des générations
- [ ] Stockage S3 pour les fichiers audio
- [ ] Système de paiement Stripe
- [ ] Clonage vocal avec XTTS v2
- [ ] Déploiement sur AWS EC2

---

## 👤 Auteur

**Damien** — Projet d'apprentissage fullstack IA