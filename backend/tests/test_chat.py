"""Tests for grounded chat routing and the chat API contract."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.weather_agent import WeatherAgent
from app.api.routes.chat import get_weather_agent
from app.core.exceptions import WeatherAPIError, WeatherProviderError
from app.main import app
from app.schemas.chat import ChatIntent, ChatIntentResult, ChatResponse, WeatherMetric
from app.schemas.weather import CurrentWeatherResponse
from app.services.llm_service import LLMServiceError
from app.services.weather_service import WeatherService
from app.tools.weather_tools import get_current_weather
from tests.conftest import SAMPLE_OWM_RESPONSE


@pytest.fixture
def observation() -> CurrentWeatherResponse:
    return WeatherService()._normalize(SAMPLE_OWM_RESPONSE)


@pytest.fixture
def current_intent() -> ChatIntentResult:
    return ChatIntentResult(intent=ChatIntent.CURRENT_WEATHER, city="Dhule", metric=WeatherMetric.HUMIDITY)


def use_agent(agent: WeatherAgent) -> None:
    app.dependency_overrides[get_weather_agent] = lambda: agent


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_chat_accepts_valid_message_and_returns_typed_response(client, observation, current_intent):
    llm = Mock()
    llm.classify = AsyncMock(return_value=current_intent)
    tool = AsyncMock(return_value=observation)
    use_agent(WeatherAgent(llm_service=llm, weather_tool=tool))

    response = await client.post("/api/v1/chat", json={"message": "What is the humidity in Dhule?"})

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "The current humidity in Dhule is 55%."
    assert data["location"] == "Dhule"
    assert data["source"] == "OpenWeatherMap"
    assert data["tool_used"] == "get_current_weather"
    assert data["weather"]["humidity"] == 55
    assert ChatResponse.model_validate(data)
    tool.assert_awaited_once_with("Dhule")


@pytest.mark.anyio
async def test_chat_rejects_empty_message(client):
    response = await client.post("/api/v1/chat", json={"message": "   "})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_chat_endpoint_is_registered_in_openapi(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    operation = response.json()["paths"]["/api/v1/chat"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("ChatRequest")


@pytest.mark.anyio
async def test_weather_tool_uses_existing_weather_service(observation):
    existing_service = Mock()
    existing_service.get_current_weather_by_city = AsyncMock(return_value=observation)

    result = await get_current_weather("Nashik", weather_service=existing_service)

    assert result is observation
    existing_service.get_current_weather_by_city.assert_awaited_once_with("Nashik")


@pytest.mark.anyio
async def test_weather_tool_can_be_invoked_from_agent(observation, current_intent):
    llm = Mock()
    llm.classify = AsyncMock(return_value=current_intent)
    tool = AsyncMock(return_value=observation)
    agent = WeatherAgent(llm_service=llm, weather_tool=tool)

    result = await agent.answer("What's the humidity in Dhule?")

    assert result.intent == ChatIntent.CURRENT_WEATHER
    assert result.weather is observation.weather
    tool.assert_awaited_once_with("Dhule")


@pytest.mark.anyio
async def test_invalid_city_is_a_controlled_error(client, current_intent):
    llm = Mock()
    llm.classify = AsyncMock(return_value=current_intent)
    tool = AsyncMock(side_effect=WeatherAPIError("Location not found", 404))
    use_agent(WeatherAgent(llm_service=llm, weather_tool=tool))

    response = await client.post("/api/v1/chat", json={"message": "Weather in NotARealCity?"})

    assert response.status_code == 404
    assert response.json()["error"] == "Location not found"


@pytest.mark.anyio
async def test_weather_provider_failure_is_controlled(client, current_intent):
    llm = Mock()
    llm.classify = AsyncMock(return_value=current_intent)
    tool = AsyncMock(side_effect=WeatherProviderError("Weather provider is unavailable", 502))
    use_agent(WeatherAgent(llm_service=llm, weather_tool=tool))

    response = await client.post("/api/v1/chat", json={"message": "Weather in Dhule?"})

    assert response.status_code == 502
    assert "provider is unavailable" in response.json()["error"]


@pytest.mark.anyio
async def test_llm_failure_is_controlled(client):
    llm = Mock()
    llm.classify = AsyncMock(side_effect=LLMServiceError("Weather assistant unavailable", 503))
    use_agent(WeatherAgent(llm_service=llm))

    response = await client.post("/api/v1/chat", json={"message": "Weather in Dhule?"})

    assert response.status_code == 503
    assert response.json()["error"] == "Weather assistant unavailable"


@pytest.mark.anyio
async def test_unsupported_request_never_calls_weather_tool(client):
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.UNKNOWN, unsupported_topic="forecast"))
    tool = AsyncMock()
    use_agent(WeatherAgent(llm_service=llm, weather_tool=tool))

    response = await client.post("/api/v1/chat", json={"message": "Give me a 7 day forecast for Dhule."})

    assert response.status_code == 200
    data = response.json()
    assert "not available yet" in data["message"]
    assert data["weather"] is None
    assert data["source"] is None
    assert data["tool_used"] is None
    tool.assert_not_awaited()


@pytest.mark.anyio
async def test_missing_city_requests_clarification_without_weather_call():
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.CURRENT_WEATHER, city=None))
    tool = AsyncMock()
    response = await WeatherAgent(llm_service=llm, weather_tool=tool).answer("What is the weather right now?")
    assert "Which city" in response.message
    assert response.weather is None
    tool.assert_not_awaited()
