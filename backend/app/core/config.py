"""Application configuration via Pydantic Settings."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "WeatherGPT"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    # Avoid colliding with unrelated shell/tooling DEBUG variables (for example
    # DEBUG=release). Only WEATHERGPT_DEBUG configures this application flag.
    DEBUG: bool = Field(default=False, validation_alias="WEATHERGPT_DEBUG")

    # --- API ---
    API_V1_PREFIX: str = "/api/v1"

    # --- CORS ---
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Weather Provider (OpenWeatherMap) ---
    WEATHER_API_KEY: str = ""
    WEATHER_API_BASE_URL: str = "https://api.openweathermap.org/data/2.5"

    # --- Database (future) ---
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/weathergpt"

    # --- Redis (future) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Phase 3 LLM intent provider ---
    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "qwen3:4b"
    LLM_BASE_URL: str = "http://127.0.0.1:11434"
    LLM_TIMEOUT: int = 45

    # --- Timeouts ---
    WEATHER_API_TIMEOUT: int = 10

    # --- IMD official district warning feed ---
    IMD_DISTRICT_WARNING_URL: str = "https://mausam.imd.gov.in/api/warnings_district_api.php"
    IMD_ALERT_TIMEOUT: int = 10
    IMD_ALERT_CACHE_TTL_SECONDS: int = 900
    # Populate only with the object ID verified from an official IMD district source.
    IMD_DHULE_OBJ_ID: str = ""


settings = Settings()
