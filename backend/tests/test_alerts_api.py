from unittest.mock import AsyncMock

import pytest

from app.api.routes.weather import imd_alert_service
from app.core.config import settings
from app.schemas.weather import WeatherAlertsResponse, AlertDay
from datetime import datetime, timezone
from unittest.mock import Mock

from app.agents.weather_agent import WeatherAgent
from app.schemas.chat import ChatIntent, ChatIntentResult


@pytest.mark.anyio
async def test_alerts_api_success(client, monkeypatch):
    result = WeatherAlertsResponse(location="Dhule", district="Dhule", state="Maharashtra", issued_at=datetime.now(timezone.utc), forecast_days=[AlertDay(date=datetime.now(timezone.utc), warnings=[], is_active=False)], source_url="https://mausam.imd.gov.in/api/warnings_district_api.php?id=9001")
    monkeypatch.setattr(imd_alert_service, "get_alerts", AsyncMock(return_value=result))
    response = await client.get("/api/v1/weather/alerts?city=Dhule")
    assert response.status_code == 200 and response.json()["source"] == "India Meteorological Department (IMD)"


@pytest.mark.anyio
async def test_alerts_api_provider_unavailable_is_not_no_warning(client, monkeypatch):
    monkeypatch.setattr(settings, "IMD_DHULE_OBJ_ID", "")
    monkeypatch.setattr(imd_alert_service, "get_alerts", AsyncMock(side_effect=__import__("app.services.imd_alert_service", fromlist=["AlertProviderUnavailable"]).AlertProviderUnavailable()))
    response = await client.get("/api/v1/weather/alerts?city=Dhule")
    assert response.status_code == 503
    assert response.json()["error"] == "WEATHER_ALERT_PROVIDER_UNAVAILABLE"


@pytest.mark.anyio
async def test_alerts_api_preserves_machine_readable_authorization_reason(client, monkeypatch):
    from app.services.imd_alert_service import AlertProviderUnavailable
    monkeypatch.setattr(imd_alert_service, "get_alerts", AsyncMock(side_effect=AlertProviderUnavailable("provider_authorization_required")))
    response = await client.get("/api/v1/weather/alerts?city=Dhule")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["source"] == "IMD"
    assert response.json()["reason"] == "provider_authorization_required"


@pytest.mark.anyio
async def test_alerts_api_unsupported_city(client):
    response = await client.get("/api/v1/weather/alerts?city=Nashik")
    assert response.status_code == 422 and response.json()["error"] == "UNSUPPORTED_LOCATION"


@pytest.mark.anyio
async def test_alert_chat_routes_through_alert_tool():
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.ALERT, city="Dhule"))
    alert_result = WeatherAlertsResponse(location="Dhule", district="Dhule", state="Maharashtra", issued_at=datetime.now(timezone.utc), forecast_days=[AlertDay(date=datetime.now(timezone.utc), warnings=[], warning_codes=[1], severity="Green", severity_code=4, is_active=False)], source_url="https://mausam.imd.gov.in")
    tool = AsyncMock(return_value=alert_result)
    response = await WeatherAgent(llm_service=llm, alert_tool=tool).answer("Any IMD weather warnings in Dhule?")
    assert response.intent == ChatIntent.ALERT and response.tool_used == "get_weather_alerts"
    assert "No official IMD weather warning" in response.message
    tool.assert_awaited_once_with("Dhule")


@pytest.mark.anyio
async def test_alert_chat_provider_failure_does_not_claim_no_warning():
    from app.services.imd_alert_service import AlertProviderUnavailable
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.ALERT, city="Dhule"))
    tool = AsyncMock(side_effect=AlertProviderUnavailable())
    response = await WeatherAgent(llm_service=llm, alert_tool=tool).answer("Is there a warning in Dhule?")
    assert "couldn't retrieve" in response.message
    assert "No official" not in response.message
