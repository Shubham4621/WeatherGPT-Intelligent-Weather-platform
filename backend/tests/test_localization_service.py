from datetime import UTC, datetime

import pytest
import anyio
from pydantic import ValidationError

from app.schemas.chat import ChatIntent, ChatIntentResult, ChatRequest, ChatResponse
from app.schemas.weather import AdvisoryFactor, AdvisoryRisk, WeatherAdvisoryResponse, WeatherCondition
from app.services.llm_service import LLMService
from app.services.localization_service import localize_chat_response


class Provider:
    async def classify(self, message: str) -> ChatIntentResult:
        text = message.casefold()
        if "warning" in text:
            intent = ChatIntent.ALERT
        elif "travel" in text or "precautions" in text:
            intent = ChatIntent.ADVISORY
        elif "rain" in text or "tomorrow" in text:
            intent = ChatIntent.FORECAST
        else:
            intent = ChatIntent.CURRENT_WEATHER
        return ChatIntentResult(intent=intent, city="Dhule")


@pytest.mark.parametrize(("language", "message", "intent"), [
    ("mr", "धुळ्याचे आजचे हवामान काय आहे?", ChatIntent.CURRENT_WEATHER),
    ("hi", "धुले में आज मौसम कैसा है?", ChatIntent.CURRENT_WEATHER),
    ("mr", "उद्या धुळ्यात पाऊस पडेल का?", ChatIntent.FORECAST),
    ("hi", "क्या कल धुले में बारिश होगी?", ChatIntent.FORECAST),
    ("mr", "धुळ्यात हवामानाचा इशारा आहे का?", ChatIntent.ALERT),
    ("hi", "क्या धुले में मौसम की कोई चेतावनी है?", ChatIntent.ALERT),
    ("mr", "मी उद्या धुळ्याला प्रवास करावा का?", ChatIntent.ADVISORY),
    ("hi", "क्या मुझे कल धुले की यात्रा करनी चाहिए?", ChatIntent.ADVISORY),
])
def test_indic_chat_is_normalized_before_existing_router(language, message, intent):
    service = LLMService(provider=Provider())
    result = anyio.run(lambda: service.classify(message, language=language))
    assert result.intent == intent
    assert result.city == "Dhule"


def test_language_validation_is_backward_compatible_and_controlled():
    assert ChatRequest(message="weather in Dhule").language == "en"
    assert ChatRequest(message="weather", language="mr").language == "mr"
    with pytest.raises(ValidationError):
        ChatRequest(message="weather", language="fr")


def test_localization_preserves_numeric_facts_and_provider_attribution():
    response = ChatResponse(
        message="The current weather in Dhule is 28.0°C with Clouds. It feels like 29.0°C, with 72% humidity and wind speed of 5.20 m/s.",
        intent=ChatIntent.CURRENT_WEATHER,
        location="Dhule", source="OpenWeatherMap", tool_used="get_current_weather",
        observed_at=datetime(2026, 9, 25, tzinfo=UTC),
        weather=WeatherCondition(temperature=28, feels_like=29, temp_min=26, temp_max=30, humidity=72, pressure=1008, wind_speed=5.2, description="Clouds"),
    )
    localized = localize_chat_response(response, "mr")
    assert "28.0°C" in localized.message and "29.0°C" in localized.message
    assert "72%" in localized.message and "5.20 m/s" in localized.message
    assert localized.weather == response.weather
    assert localized.observed_at == response.observed_at
    assert localized.source == "OpenWeatherMap"


def test_unavailable_imd_localization_never_means_no_warning():
    response = ChatResponse(message="IMD unavailable", intent=ChatIntent.ALERT, tool_used="get_weather_alerts")
    translated = localize_chat_response(response, "hi").message
    assert "प्राप्त" in translated
    assert "कोई आधिकारिक IMD मौसम चेतावनी दर्ज नहीं" not in translated


def test_advisory_localization_preserves_weather_values_and_imd_unavailable_status():
    advisory = WeatherAdvisoryResponse(
        location="Dhule", date=datetime(2026, 9, 26, tzinfo=UTC), activity="TRAVEL",
        summary="For Dhule, the forecast for Saturday indicates rain with temperatures from 25.0°C to 32.9°C.",
        risk_level=AdvisoryRisk.MODERATE, factors=[
            AdvisoryFactor(code="PRECIPITATION_CHANCE", detail="High precipitation probability (70%)", source="OpenWeatherMap"),
            AdvisoryFactor(code="IMD_STATUS_UNAVAILABLE", detail="Official IMD warning information could not be retrieved.", source="India Meteorological Department (IMD)"),
        ], recommendations=["Carry rain protection."], official_warning_status="unavailable", sources=["OpenWeatherMap", "India Meteorological Department (IMD) — unavailable", "WeatherGPT"],
    )
    response = ChatResponse(message="advisory", intent=ChatIntent.ADVISORY, advisory=advisory)
    translated = localize_chat_response(response, "hi")
    assert "25.0°C" in translated.message and "32.9°C" in translated.message
    assert "70%" in translated.message
    assert "आधिकारिक IMD चेतावनी" in translated.message
    assert "कोई आधिकारिक IMD चेतावनी दर्ज नहीं" not in translated.message
    assert translated.advisory is not None and translated.advisory.risk_level == AdvisoryRisk.MODERATE
    assert translated.advisory.factors[0].source == "OpenWeatherMap"
