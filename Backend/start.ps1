# start.ps1
Set-Location "C:\Users\Daminos\OneDrive\Documents\Code\projets\IA\Projet TTS\Backend"
& "C:\Users\Daminos\OneDrive\Documents\Code\projets\IA\Projet TTS\.venv\Scripts\Activate.ps1"
uvicorn main:app --reload --host 0.0.0.0 --port 8000