"""Unit tests for WeatherService (provider error handling)."""

from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from app.core.exceptions import WeatherAPIError, WeatherProviderError
from app.services.weather_service import WeatherService


@pytest.fixture
def service():
    svc = WeatherService()
    svc.api_key = "test-key"
    return svc


# ------------------------------------------------------------------ #
# Missing API key
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_missing_api_key_raises():
    svc = WeatherService()
    svc.api_key = ""
    with pytest.raises(WeatherProviderError, match="API key is not configured"):
        await svc.get_current_weather_by_city("Mumbai")


# ------------------------------------------------------------------ #
# Timeout
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_timeout_raises(service):
    with patch(
        "app.services.weather_service.httpx.AsyncClient.get",
        side_effect=httpx.TimeoutException("timed out"),
    ):
        with pytest.raises(WeatherProviderError, match="timed out"):
            await service.get_current_weather_by_city("Delhi")


# ------------------------------------------------------------------ #
# Connection error
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_connection_error_raises(service):
    with patch(
        "app.services.weather_service.httpx.AsyncClient.get",
        side_effect=httpx.ConnectError("Connection refused"),
    ):
        with pytest.raises(WeatherProviderError, match="Unable to connect"):
            await service.get_current_weather_by_city("Delhi")


# ------------------------------------------------------------------ #
# Provider returns 404 (invalid city)
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_invalid_city_404(service):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"message": "city not found"}

    with patch(
        "app.services.weather_service.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        with pytest.raises(WeatherAPIError, match="Location not found"):
            await service.get_current_weather_by_city("xyznonexistent")


# ------------------------------------------------------------------ #
# Provider returns 401 (bad key)
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_invalid_api_key_401(service):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"message": "Invalid API key"}

    with patch(
        "app.services.weather_service.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        with pytest.raises(WeatherProviderError, match="authentication failed"):
            await service.get_current_weather_by_city("Mumbai")


# ------------------------------------------------------------------ #
# Provider returns 429 (rate limit)
# ------------------------------------------------------------------ #


@pytest.mark.anyio
async def test_rate_limit_429(service):
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.json.return_value = {"message": "rate limit exceeded"}

    with patch(
        "app.services.weather_service.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        with pytest.raises(WeatherProviderError, match="rate limit"):
            await service.get_current_weather_by_city("Mumbai")


def test_malformed_provider_payload_is_rejected(service):
    """Incomplete data must not be returned as fabricated zero measurements."""
    with pytest.raises(WeatherProviderError, match="Failed to process"):
        service._normalize({"name": "Somewhere", "main": {}})
