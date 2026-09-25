from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.weather_agent import WeatherAgent
from app.core.exceptions import WeatherProviderError
from app.schemas.chat import AdvisoryActivity, ChatIntent, ChatIntentResult
from app.schemas.weather import (AlertDay, AlertWarning, ForecastDay, ForecastResponse, LocationInfo, WeatherAlertsResponse)
from app.services.advisory_service import WeatherAdvisoryService
from app.services.imd_alert_service import AlertProviderUnavailable
from app.services.llm_service import LLMService
from app.tools.weather_tools import get_weather_advisory


def forecast(**updates):
    values = dict(date=datetime(2026, 9, 26, tzinfo=timezone.utc), temperature_min=24, temperature_max=31, feels_like=30, humidity=65, description="light rain", cloudiness=70, wind_speed=5.2, rain_probability=80)
    values.update(updates)
    return ForecastResponse(location=LocationInfo(name="Dhule", country="IN", latitude=20.9, longitude=74.78), forecast=[ForecastDay(**values), ForecastDay(**{**values, "date": datetime(2026, 9, 27, tzinfo=timezone.utc)})], source="OpenWeatherMap", forecasted_at=datetime.now(timezone.utc))


def alerts(active=True):
    day = AlertDay(date=datetime(2026, 9, 26, tzinfo=timezone.utc), warnings=[AlertWarning(warning_type="Heavy Rain", warning_code=2)] if active else [], warning_codes=[2] if active else [1], severity="Orange" if active else "Green", severity_code=2 if active else 4, is_active=active)
    return WeatherAlertsResponse(location="Dhule", district="Dhule", state="Maharashtra", issued_at=datetime.now(timezone.utc), forecast_days=[day], source_url="https://mausam.imd.gov.in/api/warnings_district_api.php?id=9001")


def test_advisory_uses_forecast_factors_and_activity_recommendations():
    result = WeatherAdvisoryService().build("Dhule", AdvisoryActivity.TRAVEL, forecast(), None, "unavailable", 0)
    assert result.risk_level.value == "HIGH"
    assert any(f.code == "PRECIPITATION_CHANCE" for f in result.factors)
    assert "Allow extra travel time." in result.recommendations
    assert result.official_warning is None and result.official_warning_status == "unavailable"
    assert "could not be retrieved" in result.summary


def test_advisory_detects_heat_and_strong_wind_as_conditions_not_official_hazards():
    data = forecast(temperature_max=41, wind_speed=13, rain_probability=None, description="clear sky")
    result = WeatherAdvisoryService().build("Dhule", AdvisoryActivity.OUTDOOR_ACTIVITY, data, None, "unavailable", 0)
    assert result.risk_level.value == "HIGH"
    assert {factor.code for factor in result.factors} >= {"TEMPERATURE", "WIND"}
    assert all("heat wave" not in factor.detail.casefold() for factor in result.factors)


def test_official_warning_is_kept_separate_from_weathergpt_risk():
    result = WeatherAdvisoryService().build("Dhule", AdvisoryActivity.GENERAL_PRECAUTION, forecast(), alerts(), "available", 0)
    assert result.official_warning is not None
    assert result.official_warning.severity == "Orange"
    assert result.risk_label == "WeatherGPT risk classification"
    assert "WeatherGPT" in result.sources


def test_no_warning_and_missing_forecast_are_not_fabricated():
    result = WeatherAdvisoryService().build("Dhule", AdvisoryActivity.GENERAL_PRECAUTION, None, alerts(False), "available", 1)
    assert result.official_warning is None
    assert result.official_warning_status == "none_reported"
    assert result.date is None and any(f.code == "FORECAST_UNAVAILABLE" for f in result.factors)


@pytest.mark.anyio
async def test_advisory_tool_degrades_when_forecast_or_imd_fails():
    weather = Mock(); weather.get_forecast_by_city = AsyncMock(side_effect=WeatherProviderError("unavailable", 502))
    imd = Mock(); imd.get_alerts = AsyncMock(side_effect=AlertProviderUnavailable())
    result = await get_weather_advisory("Dhule", weather_service=weather, alert_service=imd)
    assert result.date is None and result.official_warning_status == "unavailable"
    assert result.official_warning is None
    assert any("could not be retrieved" in factor.detail for factor in result.factors)


@pytest.mark.anyio
async def test_advisory_chat_uses_tool_and_returns_sources():
    llm = Mock(); llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.ADVISORY, city="Dhule", activity=AdvisoryActivity.TRAVEL))
    llm.explain_advisory = AsyncMock(return_value="Rain is likely, according to the provider forecast.")
    result = WeatherAdvisoryService().build("Dhule", AdvisoryActivity.TRAVEL, forecast(), alerts(), "available", 0)
    tool = AsyncMock(return_value=result)
    reply = await WeatherAgent(llm_service=llm, advisory_tool=tool).answer("Should I travel tomorrow in Dhule?")
    assert reply.intent == ChatIntent.ADVISORY and reply.tool_used == "get_weather_advisory"
    assert reply.advisory.official_warning.severity == "Orange"
    assert "Official IMD warning" in reply.message and "WeatherGPT recommendations" in reply.message
    tool.assert_awaited_once()


@pytest.mark.anyio
async def test_advisory_intent_router_preserves_other_intents():
    class Provider:
        async def classify(self, message):
            return ChatIntentResult(intent=ChatIntent.UNKNOWN)
    llm = LLMService(provider=Provider())
    assert (await llm.classify("Should I carry an umbrella tomorrow in Dhule?")).intent == ChatIntent.ADVISORY
    assert (await llm.classify("Should I travel tomorrow in Dhule?")).activity == AdvisoryActivity.TRAVEL
    assert (await llm.classify("Is there an official weather warning in Dhule?")).intent == ChatIntent.ALERT
    assert (await llm.classify("What is the weather tomorrow in Dhule?")).intent == ChatIntent.FORECAST
    assert (await llm.classify("Should I travel tomorrow if there is a warning in Dhule?")).intent == ChatIntent.ADVISORY
