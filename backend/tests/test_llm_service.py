"""Tests for the Ollama provider adapter and invalid model responses."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.schemas.chat import ChatIntent
from app.services.llm_service import LLMService, LLMServiceError, OllamaIntentProvider


@pytest.mark.anyio
async def test_ollama_provider_parses_structured_intent():
    response = MagicMock(spec=httpx.Response)
    response.is_error = False
    response.json.return_value = {
        "message": {"content": '{"intent":"CURRENT_WEATHER","city":"Dhule","metric":"humidity","unsupported_topic":"other"}'}
    }
    with patch("app.services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response) as post:
        result = await OllamaIntentProvider().classify("What is the humidity in Dhule?")
    assert result.intent == ChatIntent.CURRENT_WEATHER
    assert result.city == "Dhule"
    assert result.metric == "humidity"
    payload = post.await_args.kwargs["json"]
    assert payload["stream"] is False
    assert "format" in payload


@pytest.mark.anyio
async def test_ollama_invalid_json_is_controlled():
    response = MagicMock(spec=httpx.Response)
    response.is_error = False
    response.json.return_value = {"message": {"content": "not valid json"}}
    with patch("app.services.llm_service.httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response):
        with pytest.raises(LLMServiceError) as exc:
            await OllamaIntentProvider().classify("weather in Dhule")
    assert exc.value.status_code == 502
    assert exc.value.error_type == "invalid_response"


@pytest.mark.anyio
async def test_ollama_timeout_is_controlled():
    with patch(
        "app.services.llm_service.httpx.AsyncClient.post",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("internal timeout detail"),
    ):
        with pytest.raises(LLMServiceError) as exc:
            await OllamaIntentProvider().classify("weather in Dhule")
    assert exc.value.status_code == 504
    assert "timed out" in exc.value.detail


@pytest.mark.anyio
async def test_llm_service_recovers_explicit_city_when_model_omits_it():
    class Provider:
        async def classify(self, message):
            from app.schemas.chat import ChatIntentResult
            return ChatIntentResult(intent="CURRENT_WEATHER", city=None, metric="humidity")

    result = await LLMService(provider=Provider()).classify("What is the humidity in Dhule right now?")
    assert result.city == "Dhule"
    assert result.metric.value == "humidity"


@pytest.mark.anyio
async def test_llm_service_does_not_guess_a_city():
    class Provider:
        async def classify(self, message):
            from app.schemas.chat import ChatIntentResult
            return ChatIntentResult(intent="CURRENT_WEATHER", city=None)

    result = await LLMService(provider=Provider()).classify("What is the weather right now?")
    assert result.city is None


@pytest.mark.anyio
async def test_llm_service_keeps_general_weather_questions_general():
    class Provider:
        async def classify(self, message):
            from app.schemas.chat import ChatIntentResult
            return ChatIntentResult(intent="CURRENT_WEATHER", city="Dhule", metric="temperature")

    result = await LLMService(provider=Provider()).classify("What is the weather in Dhule right now?")
    assert result.metric.value == "general"


@pytest.mark.anyio
async def test_llm_service_does_not_accept_a_city_not_named_by_user():
    class Provider:
        async def classify(self, message):
            from app.schemas.chat import ChatIntentResult
            return ChatIntentResult(intent="CURRENT_WEATHER", city="Mumbai")

    result = await LLMService(provider=Provider()).classify("What is the weather right now?")
    assert result.city is None


@pytest.mark.anyio
async def test_explicit_city_in_question_overrides_a_wrong_model_city():
    class Provider:
        async def classify(self, message):
            from app.schemas.chat import ChatIntentResult
            return ChatIntentResult(intent="CURRENT_WEATHER", city="Nashik")

    result = await LLMService(provider=Provider()).classify("What is the weather in Dhule right now?")
    assert result.city == "Dhule"
