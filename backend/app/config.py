"""
Application configuration via Pydantic BaseSettings.
All values can be overridden with environment variables.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Project root = two levels above this file (backend/app/config.py → project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    APP_NAME: str = "Customer Retention AI Agent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database (placeholder — swap for your real DB URL)
    DATABASE_URL: str = "sqlite:///./retention.db"

    # LLM / Agent
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    AGENT_MAX_TOK