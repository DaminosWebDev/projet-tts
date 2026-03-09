from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class JobYoutubeResponse(BaseModel):
    id: str
    youtube_url: str
    video_id: Optional[str]
    video_title: Optional[str]
    source_language: Optional[str]
    target_language: str
    audio_url: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True  # Lecture depuis objet SQLAlchemy — pas un dict


class JobTTSResponse(BaseModel):
    id: str
    input_text: str
    voice: str
    language: str
    audio_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class JobSTTResponse(BaseModel):
    id: str
    filename: str
    detected_language: Optional[str]
    transcription_text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    youtube: list[JobYoutubeResponse]
    tts: list[JobTTSResponse]
    stt: list[JobSTTResponse]
    total: int  # Affiché comme badge dans le frontend — évite de compter côté client