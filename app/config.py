"""
Enviroment configuration for Booking Engine + templates path definition.
"""

from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

# Settings class
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ==== DATABASE ====
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int = 3306
    DB_NAME: str

    # ==== DEBUG ====
    DEBUG: bool = False

    # ==== SECURITY ====
    JWT_SECRET: str
    ALGORITHM: str = "HS256"
    TOKEN_EXPIRATION_MINS: int = 1440
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # ==== EXTERNAL APIs ====
    REDIS_SECRET_KEY: str
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ==== LOGGING ====
    LOG_FORMAT: Literal["TEXT", "JSON"] = "TEXT"
    LOG_LEVEL: str = "INFO"

settings = Settings()
