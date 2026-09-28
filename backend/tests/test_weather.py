"""Tests for the /api/v1/weather/* endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import SAMPLE_OWM_RESPONSE


# ------------------------------------------------------------------ #
# Validation tests (no external calls)
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_current_weather_missing_location(client):
    """Should return 400 when no location params are provided."""
    response = await client.get("/api/v1/weather/current")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data


@pytest.mark.anyio
async def test_current_weather_partial_coords(client):
    """Should return 400 when only lat is provided without lon."""
    response = await client.get("/api/v1/weather/current?lat=20.9")
    assert response.status_code == 400


# ------------------------------------------------------------------ #
# Mocked provider — success path
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_current_weather_by_city_success(client):
    """Should return normalized weather when the provider responds."""
    with patch(
        "app.services.weather_service.WeatherService._fetch",
        new_callable=AsyncMock,
        return_value=SAMPLE_OWM_RESPONSE,
    ):
        response = await client.get("/api/v1/weather/current?city=Dhule")

    assert response.status_code == 200
    data = response.json()

    # Verify our normalized schema
    assert data["location"]["name"] == "Dhule"
    assert data["location"]["country"] == "IN"
    assert isinstance(data["weather"]["temperature"], (int, float))
    assert isinstance(data["weather"]["humidity"], int)
    assert data["source"] == "OpenWeatherMap"
    assert "observed_at" in data


@pytest.mark.anyio
async def test_current_weather_by_coords_success(client):
    """Should return weather when valid lat/lon are provided."""
    with patch(
        "app.services.weather_service.WeatherService._fetch",
        new_callable=AsyncMock,
        return_value=SAMPLE_OWM_RESPONSE,
    ):
        response = await client.get("/api/v1/weather/current?lat=20.9&lon=74.78")

    assert response.status_code == 200
    data = response.json()
    assert data["location"]["latitude"] == 20.9


# ------------------------------------------------------------------ #
# Response schema validation
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_response_schema_completeness(client):
    """All expected top-level keys must be present."""
    with patch(
        "app.services.weather_service.WeatherService._fetch",
        new_callable=AsyncMock,
        return_value=SAMPLE_OWM_RESPONSE,
    ):
        data = (await client.get("/api/v1/weather/current?city=Dhule")).json()

    assert set(data.keys()) == {"location", "weather", "sun", "source", "observed_at"}
    assert set(data["location"].keys()) == {"name", "country", "latitude", "longitude"}
    weather_keys = set(data["weather"].keys())
    for required_key in (
        "temperature", "feels_like", "humidity", "pressure",
        "wind_speed", "wind_direction", "description",
    ):
        assert required_key in weather_keys


    