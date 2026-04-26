"""
Application configuration via Pydantic BaseSettings.
All values can be overridden with environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


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
    AGENT_MAX_TOKENS: int = 1024

    # Data paths
    DATA_DIR: str = "data"
    DATASET_FILENAME: str = "01_Customer_Retention.csv"

    # Reports
    REPORTS_DIR: str = "reports"


settings = Settings()
