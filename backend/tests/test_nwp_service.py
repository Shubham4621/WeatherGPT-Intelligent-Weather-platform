from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.schemas.nwp import NwpForecastResponse, NwpPoint
from app.schemas.chat import ChatIntent, ChatIntentResult
from app.agents.weather_agent import WeatherAgent
from app.services.llm_service import LLMService
from app.services.nwp_service import GfsNomadsProvider, NwpMalformedResponse, NwpService


class Provider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def get_forecast(self, latitude, longitude, days):
        self.calls.append((latitude, longitude, days))
        return self.response

    def get_model_metadata(self):
        return {"model": "GFS 0.25 degree"}


def available():
    run = datetime(2026, 9, 29, tzinfo=timezone.utc)
    valid = run.replace(hour=run.hour + 1)
    return NwpForecastResponse(status="available", initialization_time=run,
        forecast_start=valid, forecast_end=valid,
        points=[NwpPoint(forecast_time=valid, lead_hours=1, temperature_c=20.0)])


class Response:
    status_code = 200
    content = b"GRIB test fixture"


class Client:
    requests = []
    def __init__(self, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return None
    async def get(self, *args, **kwargs):
        type(self).requests.append(kwargs.get("params", {}))
        return Response()


class Decoder:
    def decode(self, content, latitude, longitude):
        return {"temperature_c": 21.5, "precipitation_since_initialization_mm": 1.2,
            "wind_speed_ms": 3.4, "selected_latitude": 20.0, "selected_longitude": 74.0}


@pytest.mark.anyio
async def test_service_validates_coordinates_and_returns_provider_data():
    provider = Provider(available())
    service = NwpService(provider)
    result = await service.forecast(20.0, 74.0, 2)
    assert result.model == "GFS 0.25 degree"
    assert provider.calls == [(20.0, 74.0, 2)]
    with pytest.raises(ValueError):
        await service.forecast(90.01, 0)


@pytest.mark.anyio
async def test_service_does_not_cache_unavailable_provider_results():
    provider = Provider(NwpForecastResponse(status="unavailable", reason="nwp_run_unavailable"))
    service = NwpService(provider)
    await service.forecast(0, 0)
    await service.forecast(0, 0)
    assert len(provider.calls) == 2


@pytest.mark.anyio
async def test_missing_grib_decoder_is_explicit_unavailable(monkeypatch):
    def missing_decoder():
        from app.services.nwp_service import NwpUnavailable
        raise NwpUnavailable("grib_decoder_unavailable")
    monkeypatch.setattr("app.services.nwp_service.EcCodesGribPointDecoder", missing_decoder)
    result = await GfsNomadsProvider().get_forecast(20, 74, 1)
    assert result.status == "unavailable"
    assert result.reason == "grib_decoder_unavailable"
    assert result.points == []


@pytest.mark.anyio
async def test_gfs_provider_normalizes_realistic_provider_fields_and_run(monkeypatch):
    run = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    provider = GfsNomadsProvider(decoder=Decoder(), http_client=Client)
    provider._candidate_runs = lambda _now: [run]
    result = await provider.get_forecast(20.1, 74.1, 1)
    assert result.status == "available"
    assert result.source == "NOAA/NCEP NOMADS"
    assert result.model == "GFS 0.25 degree"
    assert result.initialization_time == run
    assert result.points[0].forecast_time == run.replace(hour=18)
    assert result.points[0].temperature_c == 21.5
    assert result.points[0].precipitation_since_initialization_mm == 1.2
    assert result.points[0].wind_speed_ms == 3.4
    assert result.selected_grid_point["distance_km"] > 0


@pytest.mark.anyio
async def test_prime_meridian_window_is_split_into_valid_longitude_segments():
    Client.requests.clear()
    provider = GfsNomadsProvider(decoder=Decoder(), http_client=Client)
    run = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    payload = await provider._client_fetch(Client(), 0.0, 0.0, run, 6)
    assert payload == b"GRIB test fixtureGRIB test fixture"
    assert [(row["leftlon"], row["rightlon"]) for row in Client.requests] == [("359.700", "360.000"), ("0.000", "0.300")]


def test_nwp_response_rejects_duplicate_or_unordered_valid_times():
    run = datetime(2026, 9, 29, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="duplicate"):
        NwpForecastResponse(status="available", initialization_time=run, points=[
            NwpPoint(forecast_time=run, lead_hours=1), NwpPoint(forecast_time=run, lead_hours=2)])
    with pytest.raises(ValueError, match="time ordered"):
        NwpForecastResponse(status="available", initialization_time=run, points=[
            NwpPoint(forecast_time=run.replace(hour=2), lead_hours=2), NwpPoint(forecast_time=run.replace(hour=1), lead_hours=1)])
    with pytest.raises(ValueError, match="lead hour"):
        NwpForecastResponse(status="available", initialization_time=run, points=[
            NwpPoint(forecast_time=run.replace(hour=2), lead_hours=1)])


def test_malformed_provider_content_is_not_normalized(monkeypatch):
    import sys
    from types import ModuleType
    monkeypatch.setitem(sys.modules, "eccodes", ModuleType("eccodes"))
    decoder = object.__new__(__import__("app.services.nwp_service", fromlist=["EcCodesGribPointDecoder"]).EcCodesGribPointDecoder)
    with pytest.raises(NwpMalformedResponse, match="not_grib"):
        decoder.decode(b"not a GRIB product", 0, 0)


@pytest.mark.anyio
async def test_nwp_intent_and_city_are_extracted_without_llm_weather_values():
    intent = await LLMService(provider=object()).classify("What does GFS show for Nashik tomorrow?")
    assert intent.intent == ChatIntent.NWP
    assert intent.city == "Nashik"


@pytest.mark.anyio
async def test_chat_nwp_routes_to_tool_and_preserves_unavailable_status():
    from unittest.mock import AsyncMock
    from app.schemas.chat import ChatResponse
    llm = type("Classifier", (), {"classify": AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.NWP, city="Pune"))})()
    tool = AsyncMock(return_value=NwpForecastResponse(status="unavailable", reason="grib_decoder_unavailable"))
    response = await WeatherAgent(llm_service=llm, nwp_tool=tool).answer("What does GFS show for Pune?")
    assert response.intent == ChatIntent.NWP
    assert "grib_decoder_unavailable" in response.message
    assert response.nwp_data["status"] == "unavailable"
    assert "substitute" in response.message
    tool.assert_awaited_once_with("Pune")
    ChatResponse.model_validate(response.model_dump())
