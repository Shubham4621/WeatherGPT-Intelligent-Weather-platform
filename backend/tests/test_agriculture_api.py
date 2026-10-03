from unittest.mock import AsyncMock

import pytest

from app.api.routes import agriculture as agriculture_routes
from app.main import app
from app.schemas.agriculture import AgricultureAdviceResponse, AgricultureRecommendation, StationMetadata, StationQualityReport


@pytest.mark.anyio
async def test_agriculture_advice_endpoint_is_structured_and_accepts_coordinates(client, monkeypatch):
    expected = AgricultureAdviceResponse(status="partial", location={"latitude": 20, "longitude": 74, "status": "resolved"},
        recommendation=AgricultureRecommendation(activity="irrigation", condition="insufficient_data",
            recommendation="Check actual soil moisture before deciding.", confidence="low", limitations=["No soil-moisture sensor input."]))
    service = agriculture_routes.agriculture_service
    monkeypatch.setattr(service, "advise", AsyncMock(return_value=expected))
    response = await client.post("/api/v1/agriculture/advice", json={"latitude": 20, "longitude": 74, "activity": "irrigation"})
    assert response.status_code == 200
    assert response.json()["recommendation"]["condition"] == "insufficient_data"
    assert response.json()["recommendation"]["limitations"] == ["No soil-moisture sensor input."]
    service.advise.assert_awaited_once()


@pytest.mark.anyio
async def test_agriculture_api_rejects_missing_or_invalid_location(client):
    missing = await client.post("/api/v1/agriculture/advice", json={"activity": "general"})
    invalid = await client.post("/api/v1/agriculture/advice", json={"latitude": 91, "longitude": 74, "activity": "general"})
    assert missing.status_code == 422
    assert invalid.status_code == 422


@pytest.mark.anyio
async def test_station_quality_report_endpoint_uses_validated_metadata(client, monkeypatch):
    report = StationQualityReport(station=StationMetadata(station_id="70001", station_name="Fixture", latitude=20,
        longitude=74, source="IMD Data Service Portal"), datasets={}, missing_value_representation="empty to null",
        timestamp_interpretation="UTC", status="partial")
    monkeypatch.setattr(agriculture_routes, "station_quality_report", lambda station_id: report if station_id == "70001" else None)
    response = await client.get("/api/v1/agriculture/stations/70001/quality")
    assert response.status_code == 200
    assert response.json()["station"]["source"] == "IMD Data Service Portal"
    assert (await client.get("/api/v1/agriculture/stations/00000/quality")).status_code == 404
