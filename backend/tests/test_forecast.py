from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agents.weather_agent import WeatherAgent
from app.core.exceptions import WeatherProviderError
from app.schemas.chat import ChatIntent, ChatIntentResult
from app.schemas.weather import ForecastDay, ForecastResponse, LocationInfo
from app.services.llm_service import LLMService
from app.services.weather_service import WeatherService
from app.tools.weather_tools import get_forecast


def sample_forecast():
    return ForecastResponse(
        location=LocationInfo(name="Dhule", country="IN", latitude=20.9, longitude=74.78),
        forecast=[ForecastDay(date=datetime(2026, 9, 25, tzinfo=timezone.utc), temperature_min=24, temperature_max=31, feels_like=30, humidity=65, description="scattered clouds", cloudiness=40, wind_speed=5.2, rain_probability=20)],
        source="OpenWeatherMap", forecasted_at=datetime.now(timezone.utc),
    )


@pytest.mark.anyio
async def test_forecast_endpoint_returns_typed_normalized_data(client):
    with (
        patch("app.api.routes.weather.location_service.resolve", new_callable=AsyncMock, return_value=Mock(latitude=20.9, longitude=74.78)),
        patch("app.api.routes.weather.weather_service.get_forecast_by_coords", new_callable=AsyncMock, return_value=sample_forecast()),
    ):
        response = await client.get("/api/v1/weather/forecast?city=Dhule")
    assert response.status_code == 200
    body = response.json()
    assert body["location"]["name"] == "Dhule"
    assert body["forecast"][0]["temperature_max"] == 31
    assert ForecastResponse.model_validate(body)


@pytest.mark.anyio
async def test_forecast_service_normalizes_provider_slots():
    raw = {"city": {"name": "Dhule", "country": "IN", "coord": {"lat": 20.9, "lon": 74.78}, "timezone": 19800}, "list": [{"dt": 1790272800, "main": {"temp_min": 24, "temp_max": 30, "feels_like": 29, "humidity": 65}, "weather": [{"description": "scattered clouds"}], "clouds": {"all": 40}, "wind": {"speed": 5.2}, "pop": 0.2}]}
    service = WeatherService()
    with patch.object(service, "_fetch", new_callable=AsyncMock, return_value=raw) as fetch:
        result = await service.get_forecast_by_city("Dhule")
    assert result.forecast[0].rain_probability == 20
    assert result.forecast[0].temperature_min == 24
    fetch.assert_awaited_once()


@pytest.mark.anyio
async def test_forecast_tool_delegates_to_service():
    service = Mock()
    service.get_forecast_by_city = AsyncMock(return_value=sample_forecast())
    result = await get_forecast("Dhule", weather_service=service)
    assert result.source == "OpenWeatherMap"
    service.get_forecast_by_city.assert_awaited_once_with("Dhule")


@pytest.mark.anyio
async def test_forecast_chat_is_grounded_in_tool_data():
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.FORECAST, city="Dhule", forecast_day_offset=0))
    tool = AsyncMock(return_value=sample_forecast())
    result = await WeatherAgent(llm_service=llm, forecast_tool=tool).answer("Forecast Dhule")
    assert result.intent == ChatIntent.FORECAST
    assert "24.0" in result.message and "31.0" in result.message
    assert "scattered clouds" in result.message
    assert "20%" in result.message
    assert result.tool_used == "get_forecast"


@pytest.mark.anyio
async def test_forecast_language_routes_forecast_and_preserves_current_weather():
    class Provider:
        async def classify(self, message):
            return ChatIntentResult(intent=ChatIntent.CURRENT_WEATHER, city="Dhule")
    service = LLMService(provider=Provider())
    assert (await service.classify("Will it rain tomorrow in Nashik?")).intent == ChatIntent.FORECAST
    assert (await service.classify("What is weather in Dhule right now?")).intent == ChatIntent.CURRENT_WEATHER


@pytest.mark.anyio
async def test_warning_language_routes_alert_not_forecast():
    class Provider:
        async def classify(self, message):
            return ChatIntentResult(intent=ChatIntent.UNKNOWN, unsupported_topic="alerts")
    result = await LLMService(provider=Provider()).classify("Is there an official rain warning tomorrow in Dhule?")
    assert result.intent == ChatIntent.ALERT and result.city == "Dhule"


@pytest.mark.anyio
async def test_forecast_agent_uses_forecast_tool_for_tomorrow_question():
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.FORECAST, city="Dhule", forecast_day_offset=1))
    alert_tool = AsyncMock()
    forecast_tool = AsyncMock(return_value=sample_forecast())
    answer = await WeatherAgent(llm_service=llm, forecast_tool=forecast_tool, alert_tool=alert_tool).answer("Weather tomorrow in Dhule")
    forecast_tool.assert_awaited_once_with("Dhule")
    alert_tool.assert_not_awaited()


@pytest.mark.anyio
async def test_forecast_malformed_payload_is_controlled():
    service = WeatherService()
    with patch.object(service, "_fetch", new_callable=AsyncMock, return_value={"city": {}, "list": []}):
        with pytest.raises(WeatherProviderError):
            await service.get_forecast_by_city("Dhule")
