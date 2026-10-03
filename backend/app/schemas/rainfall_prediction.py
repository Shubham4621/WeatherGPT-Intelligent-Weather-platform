"""Schemas for the clearly labeled experimental rainfall model endpoint."""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PredictionCoordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SelectedGridPoint(PredictionCoordinate):
    distance_km: float = Field(ge=0)


class RainfallPredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = "WeatherGPT model prediction"
    location: PredictionCoordinate
    selected_grid_point: SelectedGridPoint
    dataset: str = "IMD validated daily gridded rainfall"
    grid_resolution_degrees: float = Field(default=0.25, gt=0)
    source: str = "WeatherGPT model prediction using IMD historical rainfall observations"
    prediction_date: date
    rain_probability: float = Field(ge=0, le=1)
    rain_expected: bool
    predicted_rainfall_mm: float = Field(ge=0)
    model: str
    training_period: dict[str, date]
