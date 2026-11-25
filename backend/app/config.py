from __future__ import annotations

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
LOCAL_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env files."""

    model_config = SettingsConfigDict(
        env_file=[str(ROOT_ENV), str(LOCAL_ENV)],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/text-embedding-004"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "exampulse_rag"

    supabase_url: str = ""
    supabase_key: str = ""

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key and self.groq_api_key.strip())

    @property
    def has_qdrant_cloud(self) -> bool:
        return bool(self.qdrant_url and self.qdrant_url.strip())

    @property
    def has_supabase(self) -> bool:
        return bool(
            self.supabase_url
            and self.supabase_url.strip()
            and self.supabase_key
            and self.supabase_key.strip()
        )


settings = Settings()
