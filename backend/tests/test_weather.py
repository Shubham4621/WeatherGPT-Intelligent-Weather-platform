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


@pytest.mark.anyio
async def test_current_weather_rejects_mixed_city_and_coordinates(client):
    response = await client.get("/api/v1/weather/current?city=Pune&lat=18.52&lon=73.85")
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


@pytest.mark.anyio
async def test_current_weather_resolves_generic_city_to_coordinates(client, monkeypatch):
    from app.services.location_service import ResolvedLocation
    from app.api.routes import weather
    monkeypatch.setattr(weather.weather_service, "api_key", "test-key")
    async def resolve(query):
        return ResolvedLocation(query=query, city="Nashik", state="Maharashtra", country="IN", latitude=19.99,
            longitude=73.78, source="fixture geocoder", resolution_method="provider_geocoding")
    monkeypatch.setattr(weather.location_service, "resolve", resolve)
    with patch("app.services.weather_service.WeatherService._fetch", new_callable=AsyncMock, return_value=SAMPLE_OWM_RESPONSE) as fetch:
        response = await client.get("/api/v1/weather/current?city=Nashik")
    assert response.status_code == 200
    assert fetch.await_args.args[1]["lat"] == 19.99
    assert fetch.await_args.args[1]["lon"] == 73.78


@pytest.mark.anyio
async def test_forecast_accepts_coordinates_and_resolves_generic_cities(client, monkeypatch):
    from app.services.location_service import ResolvedLocation
    from app.api.routes.weather import location_service
    async def resolve(query):
        return ResolvedLocation(query=query, city="Pune", state="Maharashtra", country="IN", latitude=18.52,
            longitude=73.85, source="fixture geocoder", resolution_method="provider_geocoding")
    monkeypatch.setattr(location_service, "resolve", resolve)
    payload = {"city": {"name": "Pune", "country": "IN", "coord": {"lat": 18.52, "lon": 73.85}, "timezone": 19800},
        "list": [{"dt": 1790000000, "main": {"temp_min": 20, "temp_max": 28, "feels_like": 25, "humidity": 60},
                  "weather": [{"description": "clouds"}], "clouds": {"all": 50}, "wind": {"speed": 2}, "pop": 0.2}]}
    with patch("app.services.weather_service.WeatherService._fetch", new_callable=AsyncMock, return_value=payload) as fetch:
        response = await client.get("/api/v1/weather/forecast?lat=18.52&lon=73.85")
        city_response = await client.get("/api/v1/weather/forecast?city=Pune")
    assert response.status_code == 200
    assert response.json()["location"]["latitude"] == 18.52
    assert fetch.await_args_list[0].args[0] == "/forecast"
    assert fetch.await_args_list[0].args[1]["lat"] == 18.52
    assert city_response.status_code == 200
    assert fetch.await_args_list[1].args[1]["lat"] == 18.52


@pytest.mark.anyio
async def test_forecast_rejects_partial_and_out_of_range_coordinates(client):
    assert (await client.get("/api/v1/weather/forecast?lat=18.52")).status_code == 422
    assert (await client.get("/api/v1/weather/forecast?lat=91&lon=0")).status_code == 422


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



