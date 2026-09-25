from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.chat import AdvisoryActivity
from app.schemas.weather import WeatherAdvisoryResponse, AdvisoryRisk


@pytest.mark.anyio
async def test_advisory_api_returns_typed_response(client):
    result = WeatherAdvisoryResponse(location="Dhule", date=datetime.now(timezone.utc), activity=AdvisoryActivity.TRAVEL.value, summary="Forecast summary", risk_level=AdvisoryRisk.MODERATE, factors=[], recommendations=["Allow extra travel time."], official_warning=None, official_warning_status="unavailable", sources=["OpenWeatherMap", "India Meteorological Department (IMD) — unavailable", "WeatherGPT"])
    with patch("app.api.routes.weather.get_weather_advisory", new_callable=AsyncMock, return_value=result):
        response = await client.get("/api/v1/weather/advisory?city=Dhule&activity=TRAVEL&day_offset=1")
    assert response.status_code == 200
    data = response.json()
    assert data["risk_label"] == "WeatherGPT advisory classification"
    assert data["official_warning_status"] == "unavailable"


@pytest.mark.anyio
async def test_advisory_api_rejects_invalid_activity(client):
    response = await client.get("/api/v1/weather/advisory?city=Dhule&activity=IMPOSSIBLE")
    assert response.status_code == 422
