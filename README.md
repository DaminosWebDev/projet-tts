# 🎙️ TTS Project — Text-to-Speech with Kokoro-82M (kokoro 0.9.4)

🇫🇷 [Version française](README.fr.md)

Web application that transforms text into natural audio.
The user types a text, chooses a language and a voice, and generates an audio file that can be listened to and downloaded.

---

## 🏗️ Architecture
```
User → React (port 5173)
           ↓ Axios POST /tts
      FastAPI (port 8000)
           ↓ Kokoro-82M (kokoro 0.9.4)
      WAV Audio Generation
           ↓
      Player + Download
```

The project is split into two independent parts communicating via a REST API :

- **Backend** : FastAPI Python API integrating the Kokoro model
- **Frontend** : React + Vite user interface

---

## 🛠️ Tech Stack

| Technology | Role |
|------------|------|
| Python | Backend language |
| FastAPI | REST API framework |
| Uvicorn | HTTP server |
| Pydantic | Data validation |
| Kokoro v0.19 | Text-to-Speech model |
| soundfile | Audio file writing |
| React | Frontend framework |
| Vite | Build tool |
| Axios | HTTP requests |

---

## 📁 Project Structure
```
TTS PROJECT/
├── BACKEND/
│   ├── config.py          → Centralized configuration
│   ├── tts_service.py     → Kokoro engine
│   ├── main.py            → FastAPI server
│   ├── audio_files/       → Generated audio files
│   ├── requirements.txt   → Python dependencies
│   └── .env               → Secret variables (not committed)
└── FRONTEND/
    └── tts-project/
        └── src/
            └── App.jsx    → User interface
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Check API status |
| GET | `/voices` | List available voices |
| POST | `/tts` | Generate audio file |
| GET | `/audio/{filename}` | Download audio file |

### POST /tts request example
```json
{
    "text": "Hello, this is a test.",
    "language": "en",
    "voice": "af_heart",
    "speed": 1.0
}
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 20+
- NVIDIA GPU (recommended)

### Backend
```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
cd BACKEND
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Add your HF_TOKEN in the .env file

# Start the server
python main.py
```

Server runs on `http://localhost:8000`
Interactive documentation available at `http://localhost:8000/docs`

### Frontend
```bash
cd FRONTEND/tts-project

# Install dependencies
npm install

# Start development server
npm run dev
```

Interface available at `http://localhost:5173`

---

## 🎯 Features

- ✅ Text-to-speech in French and English
- ✅ Multiple voice selection
- ✅ Reading speed control
- ✅ Direct in-browser audio preview
- ✅ Audio file download
- ✅ Error handling
- ✅ Server logs

---

## 🔒 Security (planned for production)

- JWT authentication
- HTTPS
- Rate limiting
- CORS restriction to frontend URL

---

## 🗺️ Roadmap

- [ ] Speech-to-Text feature
- [ ] User account system
- [ ] Generation history
- [ ] S3 storage for audio files
- [ ] Stripe payment system
- [ ] Voice cloning with XTTS v2
- [ ] Deployment on AWS EC2

---

## 👤 Author

**Damien** — Fullstack AI learning project