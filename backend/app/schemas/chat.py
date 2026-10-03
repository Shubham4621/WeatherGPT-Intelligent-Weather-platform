"""Typed request, intent, and response contracts for the chat API."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.weather import AlertDay, WeatherAdvisoryResponse, WeatherCondition
from app.schemas.agriculture import AgricultureActivity
from app.services.localization_service import validate_language


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000, description="A natural-language weather question")
    language: str = Field(default="en", description="Response language: en, mr, or hi")

    @field_validator("message")
    @classmethod
    def trim_and_require_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty")
        return value

    @field_validator("language")
    @classmethod
    def supported_language(cls, value: str) -> str:
        return validate_language(value)


class ChatIntent(StrEnum):
    CURRENT_WEATHER = "CURRENT_WEATHER"
    FORECAST = "FORECAST"
    ALERT = "ALERT"
    ADVISORY = "ADVISORY"
    HISTORICAL_WEATHER = "HISTORICAL_WEATHER"
    NWP = "NWP"
    AGRICULTURE = "AGRICULTURE"
    UNKNOWN = "UNKNOWN"


class WeatherMetric(StrEnum):
    GENERAL = "general"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    WIND_SPEED = "wind_speed"
    WIND_DIRECTION = "wind_direction"
    PRESSURE = "pressure"
    VISIBILITY = "visibility"
    CLOUDINESS = "cloudiness"
    CONDITION = "condition"


class UnsupportedTopic(StrEnum):
    FORECAST = "forecast"
    ALERTS = "alerts"
    HISTORICAL = "historical"
    CLIMATE = "climate"
    MAPS = "maps"
    OTHER = "other"


class AdvisoryActivity(StrEnum):
    TRAVEL = "TRAVEL"
    OUTDOOR_ACTIVITY = "OUTDOOR_ACTIVITY"
    COMMUTE = "COMMUTE"
    EXERCISE = "EXERCISE"
    EVENT = "EVENT"
    AGRICULTURE = "AGRICULTURE"
    GENERAL_PRECAUTION = "GENERAL_PRECAUTION"


class ChatIntentResult(BaseModel):
    """Constrained LLM output used only for routing and entity extraction."""

    model_config = ConfigDict(extra="forbid")

    intent: ChatIntent
    city: str | None = Field(default=None, max_length=100)
    metric: WeatherMetric = WeatherMetric.GENERAL
    unsupported_topic: UnsupportedTopic = UnsupportedTopic.OTHER
    forecast_day_offset: int = Field(default=0, ge=0, le=4)
    forecast_days: int = Field(default=1, ge=1, le=5)
    advisory_day_offset: int = Field(default=1, ge=0, le=4)
    activity: AdvisoryActivity = AdvisoryActivity.GENERAL_PRECAUTION
    agriculture_activity: AgricultureActivity = AgricultureActivity.GENERAL

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or not all(character.isalnum() or character in " .,'’-" for character in value):
            raise ValueError("Invalid city name")
        return value


class ChatResponse(BaseModel):
    message: str
    intent: ChatIntent
    location: str | None = None
    source: str | None = None
    tool_used: str | None = None
    observed_at: datetime | None = None
    weather: WeatherCondition | None = None
    forecast: list[dict] | None = None
    alert_days: list[AlertDay] | None = None
    advisory: WeatherAdvisoryResponse | None = None
    historical_data: dict | None = None
    nwp_data: dict | None = None
    agriculture_data: dict | None = None
