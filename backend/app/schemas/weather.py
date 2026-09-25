"""Weather data schemas — our normalized response format."""

from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class LocationInfo(BaseModel):
    """Location metadata."""
    name: str = Field(..., description="City / location name")
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    latitude: float = Field(..., description="Latitude in decimal degrees")
    longitude: float = Field(..., description="Longitude in decimal degrees")


class WeatherCondition(BaseModel):
    """Current weather measurements."""
    temperature: float = Field(..., description="Temperature in °C")
    feels_like: float = Field(..., description="Feels-like temperature in °C")
    temp_min: float = Field(..., description="Minimum temperature in °C")
    temp_max: float = Field(..., description="Maximum temperature in °C")
    humidity: int = Field(..., description="Relative humidity in %")
    pressure: int = Field(..., description="Atmospheric pressure in hPa")
    wind_speed: float = Field(..., description="Wind speed in m/s")
    wind_direction: Optional[int] = Field(None, description="Wind direction in degrees")
    wind_gust: Optional[float] = Field(None, description="Wind gust in m/s")
    visibility: Optional[int] = Field(None, description="Visibility in metres")
    cloudiness: Optional[int] = Field(None, description="Cloudiness in %")
    description: str = Field(..., description="Human-readable weather description")
    icon: Optional[str] = Field(None, description="Weather icon code")


class SunInfo(BaseModel):
    """Sunrise / sunset times."""
    sunrise: datetime
    sunset: datetime


class CurrentWeatherResponse(BaseModel):
    """Normalized current-weather response returned by WeatherGPT."""
    location: LocationInfo
    weather: WeatherCondition
    sun: SunInfo
    source: str = Field(..., description="Data-source attribution")
    observed_at: datetime = Field(..., description="Observation timestamp (UTC)")


class ForecastDay(BaseModel):
    date: datetime
    temperature_min: float
    temperature_max: float
    feels_like: float | None = None
    humidity: int | None = None
    description: str
    cloudiness: int | None = None
    wind_speed: float | None = None
    rain_probability: float | None = None


class ForecastResponse(BaseModel):
    location: LocationInfo
    forecast: list[ForecastDay]
    source: str
    forecasted_at: datetime


class AlertWarning(BaseModel):
    warning_type: str
    warning_code: int


class AlertDay(BaseModel):
    date: datetime
    warnings: list[AlertWarning]
    warning_codes: list[int] = []
    severity: str | None = None
    severity_code: int | None = None
    is_active: bool


class WeatherAlertsResponse(BaseModel):
    location: str
    district: str
    state: str
    issued_at: datetime
    forecast_days: list[AlertDay]
    source: str = "India Meteorological Department (IMD)"
    source_url: str


class AdvisoryRisk(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class AdvisoryFactor(BaseModel):
    code: str
    detail: str
    source: str


class OfficialWarningSummary(BaseModel):
    warnings: list[str]
    severity: str | None = None
    date: datetime
    source: str = "India Meteorological Department (IMD)"
    source_url: str


class WeatherAdvisoryResponse(BaseModel):
    location: str
    date: datetime | None = None
    activity: str
    summary: str
    risk_level: AdvisoryRisk | None
    risk_label: str = "WeatherGPT advisory classification"
    factors: list[AdvisoryFactor]
    recommendations: list[str]
    official_warning: OfficialWarningSummary | None = None
    official_warning_status: str
    sources: list[str]
