from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.nwp import NwpForecastResponse, NwpPoint
from app.services.location_service import ResolvedLocation


@pytest.mark.anyio
async def test_nwp_api_supports_coordinates_and_returns_provenance(client):
    run = datetime(2026, 9, 29, tzinfo=timezone.utc)
    valid = run.replace(hour=run.hour + 1)
    result = NwpForecastResponse(status="available", initialization_time=run,
        forecast_start=valid, forecast_end=valid,
        points=[NwpPoint(forecast_time=valid, lead_hours=1, temperature_c=18.0)])
    with patch("app.api.routes.weather.nwp_service.forecast", new_callable=AsyncMock, return_value=result) as mocked:
        response = await client.get("/api/v1/weather/nwp?lat=90&lon=-180&days=1")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "NOAA/NCEP NOMADS"
    assert body["model"] == "GFS 0.25 degree"
    assert body["location"]["resolution_method"] == "coordinates"
    assert body["retrieved_at"]
    mocked.assert_awaited_once_with(90.0, -180.0, 1)


@pytest.mark.anyio
async def test_nwp_api_rejects_invalid_coordinates(client):
    response = await client.get("/api/v1/weather/nwp?lat=90.1&lon=0")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_nwp_api_reports_city_resolution_unavailable(client):
    with patch("app.api.routes.weather.resolve_historical_coordinates", return_value=None), patch(
        "app.api.routes.weather.location_service.resolve", new_callable=AsyncMock,
        side_effect=__import__("app.services.location_service", fromlist=["LocationResolutionError"]).LocationResolutionError("location_not_found", "not found")):
        response = await client.get("/api/v1/weather/nwp?city=NoSuchPlace")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["reason"] == "nwp_location_not_found"


@pytest.mark.anyio
async def test_nwp_city_uses_phase13_location_resolution_before_provider(client):
    resolved = ResolvedLocation(query="Pune", city="Pune", state="Maharashtra", country="IN",
        latitude=18.52, longitude=73.85, source="OpenWeatherMap Geocoding API", resolution_method="provider_geocoding")
    with patch("app.api.routes.weather.location_service.resolve", new_callable=AsyncMock, return_value=resolved), patch(
        "app.api.routes.weather.resolve_historical_coordinates", return_value=None), patch(
        "app.api.routes.weather.nwp_service.forecast", new_callable=AsyncMock,
        return_value=NwpForecastResponse(status="unavailable", reason="grib_decoder_unavailable")) as mocked:
        response = await client.get("/api/v1/weather/nwp?city=Pune&days=1")
    assert response.status_code == 200
    assert response.json()["location"]["latitude"] == 18.52
    assert response.json()["location"]["source"] == "OpenWeatherMap Geocoding API"
    assert response.json()["reason"] == "grib_decoder_unavailable"
    mocked.assert_awaited_once_with(18.52, 73.85, 1)
