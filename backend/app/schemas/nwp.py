"""Typed responses for numerical weather model guidance."""
from datetime import datetime
from typing import Literal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.weather import ForecastDay


class NwpPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast_time: datetime
    lead_hours: int = Field(ge=1)
    temperature_c: float | None = Field(default=None, allow_inf_nan=False)
    precipitation_since_initialization_mm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    wind_speed_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class NwpForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "partial", "unavailable", "error"]
    location: dict[str, Any] | None = None
    source: str = "NOAA/NCEP NOMADS"
    model: str = "GFS 0.25 degree"
    initialization_time: datetime | None = None
    retrieved_at: datetime | None = None
    forecast_start: datetime | None = None
    forecast_end: datetime | None = None
    resolution_degrees: float = 0.25
    units: dict[str, str] = Field(default_factory=lambda: {"temperature": "°C", "precipitation": "mm", "wind_speed": "m/s"})
    provenance: str = "NOAA/NCEP Global Forecast System (GFS) operational GRIB2 guidance via NOMADS"
    source_url: str = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    selected_grid_point: dict[str, float] | None = None
    points: list[NwpPoint] = Field(default_factory=list)
    forecast: list[ForecastDay] = Field(default_factory=list)
    missing_leads: list[int] = Field(default_factory=list)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_forecast_consistency(self):
        times = [point.forecast_time for point in self.points]
        if len(times) != len(set(times)):
            raise ValueError("duplicate NWP forecast valid times")
        if times != sorted(times):
            raise ValueError("NWP forecast points must be time ordered")
        if self.initialization_time and any(value < self.initialization_time for value in times):
            raise ValueError("NWP forecast valid time precedes its model run")
        if self.initialization_time and any(
            (point.forecast_time - self.initialization_time).total_seconds() != point.lead_hours * 3600
            for point in self.points
        ):
            raise ValueError("NWP lead hour does not match model run and valid time")
        if self.status in {"unavailable", "error"} and self.points:
            raise ValueError("unavailable or error NWP responses cannot contain forecast values")
        return self
