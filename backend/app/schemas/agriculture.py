"""Validated DSP observations and deterministic agricultural decision support."""
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgricultureActivity(StrEnum):
    IRRIGATION = "irrigation"
    SOWING = "sowing"
    SPRAYING = "spraying"
    HARVESTING = "harvesting"
    FIELD_OPERATIONS = "field_operations"
    HEAT_STRESS = "heat_stress"
    HEAVY_RAIN = "heavy_rain"
    WIND_RISK = "wind_risk"
    GENERAL = "general"


class StationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str
    station_name: str
    district: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_precision: str | None = None
    elevation_m: float | None = None
    source: str
    datasets: dict[str, dict[str, str]] = Field(default_factory=dict)


class StationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str
    station_name: str
    district: str | None = None
    state: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float | None = None
    observed_at: datetime
    source: str
    dataset: str
    temperature_c: float | None = None
    temp_max_c: float | None = None
    temp_min_c: float | None = None
    wet_bulb_c: float | None = None
    dew_point_c: float | None = None
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    pressure_hpa: float | None = None
    sea_level_pressure_hpa: float | None = None
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    wind_direction: str | None = None
    rainfall_mm: float | None = Field(default=None, ge=0)
    quality_flags: list[str] = Field(default_factory=list)
    invalid_values: dict[str, str] = Field(default_factory=dict)


class StationQualityReport(BaseModel):
    station: StationMetadata
    datasets: dict[str, dict[str, Any]]
    missing_value_representation: str
    timestamp_interpretation: str
    status: str


class AgricultureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str | None = Field(default=None, min_length=1, max_length=100)
    station_id: str | None = Field(default=None, min_length=1, max_length=20)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    activity: AgricultureActivity = AgricultureActivity.GENERAL
    crop: str | None = Field(default=None, max_length=80)
    growth_stage: str | None = Field(default=None, max_length=80)
    irrigation_available: bool | None = None
    soil_type: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_location(self):
        coordinate_pair = self.latitude is not None and self.longitude is not None
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude.")
        modes = int(bool(self.city)) + int(bool(self.station_id)) + int(coordinate_pair)
        if modes != 1:
            raise ValueError("Provide exactly one city, station ID, or coordinate location.")
        return self


class AgricultureEvidence(BaseModel):
    label: str
    value: float | str
    unit: str | None = None
    source: str
    valid_time: datetime | date | None = None
    detail: str | None = None


class AgricultureRecommendation(BaseModel):
    activity: AgricultureActivity
    condition: str
    recommendation: str
    evidence: list[AgricultureEvidence] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    valid_period: str | None = None
    confidence: str
    limitations: list[str] = Field(default_factory=list)


class AgricultureAdviceResponse(BaseModel):
    status: str
    location: dict[str, Any]
    station: dict[str, Any] | None = None
    current_weather: dict[str, Any] | None = None
    forecast_context: dict[str, Any] | None = None
    nwp_context: dict[str, Any] | None = None
    historical_context: dict[str, Any] | None = None
    climatology_context: dict[str, Any] | None = None
    official_warning: dict[str, Any] | None = None
    recommendation: AgricultureRecommendation
    data_quality: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)

