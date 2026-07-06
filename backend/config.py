from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

# Load .env file if it exists (for local development)
# In production (Render), environment variables are set directly
load_dotenv()

class Settings(BaseSettings):
    MONGO_DETAILS: str
    CLOUDINARY_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    OPENROUTER_API_KEY: str
    GROQ_API_KEY: Optional[str] = None
    API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra env vars not defined in class
    )

settings = Settings()