"""
Application configuration via Pydantic BaseSettings.
All values can be overridden with environment variables.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Project root = two levels above this file (backend/app/config.py -> project root)
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

    # Database
    DATABASE_URL: str = "sqlite:///./retention.db"

    # LLM / Agent (not required — agent is fully rule-based, no paid API used)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    AGENT_MAX_TOKENS: int = 1024

    # Data paths — absolute so uvicorn launch directory does not matter
    DATA_DIR: str = os.path.join(_PROJECT_ROOT, "data")
    DATASET_FILENAME: str = "01_Customer_Retention.csv"

    # Reports — absolute path
    REPORTS_DIR: str = os.path.join(_PROJECT_ROOT, "reports")


settings = Settings()
