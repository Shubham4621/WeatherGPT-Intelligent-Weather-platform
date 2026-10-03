from datetime import date, datetime, timezone
import asyncio

import pytest

from app.services.historical_weather_service import (
    HistoricalDataset, HistoricalWeatherRecord, HistoricalWeatherService,
    UnconfiguredHistoricalProvider, aggregate, compare, monthly_aggregation, yearly_aggregation, trend, linear_trend, ImdClimatologyService, LocalImdGridHistoricalProvider,
    rainfall_anomaly, annual_rainfall_climatology_comparison,
)
from app.services.llm_service import LLMService
from app.schemas.chat import ChatIntent
from app.agents.weather_agent import WeatherAgent
from app.schemas.chat import ChatIntentResult
from unittest.mock import AsyncMock, Mock


def records():
    return [HistoricalWeatherRecord(location="Dhule", date=date(2025, 7, day), temperature_min=20+day,
        temperature_max=30+day, temperature_mean=25+day, rainfall=float(day-1), humidity=50+day,
        wind_speed=2.0, source="fixture-provider", retrieved_at=datetime(2025, 8, 1, tzinfo=timezone.utc)) for day in (1, 2, 3, 4)]


class FixtureProvider:
    async def fetch(self, city, start, end):
        return HistoricalDataset(status="available", location=city, source="fixture-provider", records=records())


def test_unconfigured_provider_returns_controlled_unavailable():
    response = asyncio.run(UnconfiguredHistoricalProvider().fetch("Dhule", date(2025, 7, 1), date(2025, 7, 31)))
    assert response.status == "unavailable"
    assert not response.records


def test_service_filters_period_and_marks_partial_coverage():
    result = asyncio.run(HistoricalWeatherService(FixtureProvider()).get_history("Dhule", date(2025, 7, 1), date(2025, 7, 31)))
    assert result.status == "partial"
    assert len(result.records) == 4
    assert result.period_start == date(2025, 7, 1)


def test_service_marks_provider_data_outside_requested_range_as_no_weather_data():
    result = asyncio.run(HistoricalWeatherService(FixtureProvider()).get_history("Dhule", date(2025, 8, 1), date(2025, 8, 2)))
    assert result.status == "no_data"
    assert result.availability_status == "NO_WEATHER_DATA"
    assert result.records == []


def test_reversed_dates_rejected():
    with pytest.raises(ValueError):
        asyncio.run(HistoricalWeatherService().get_history("Dhule", date(2025, 8, 1), date(2025, 7, 1)))


def test_aggregation_temperature_rainfall_rainy_days_and_optional_fields():
    rows = records()
    rows[0].humidity = None
    rows[0].wind_speed = None
    summary = aggregate(rows)
    assert summary["average_temperature"] == 27.5
    assert summary["temperature_min"] == 21
    assert summary["temperature_max"] == 34
    assert summary["total_rainfall"] == 6
    assert summary["rainy_days"] == 3
    assert summary["average_humidity"] == 53
    assert summary["average_wind_speed"] == 2


def test_monthly_aggregation():
    result = monthly_aggregation(records())
    assert result[0]["month"] == "July"
    assert result[0]["total_rainfall"] == 6


def test_yearly_aggregation_identifies_months_from_available_values():
    result = yearly_aggregation(records())[0]
    assert result["year"] == 2025
    assert result["wettest_month"] == "July"
    assert result["hottest_month"] == "July"


def test_history_intent_uses_deterministic_english_and_indic_normalization():
    llm = LLMService(provider=object())
    english = asyncio.run(llm.classify("How much rainfall did Dhule receive last year?"))
    marathi = asyncio.run(llm.classify("मागच्या जुलैमध्ये धुळ्यात किती पाऊस झाला?", language="mr"))
    hindi = asyncio.run(llm.classify("पिछले जुलाई में धुले में कितनी बारिश हुई?", language="hi"))
    assert english.intent == marathi.intent == hindi.intent == ChatIntent.HISTORICAL_WEATHER
    assert english.city == "Dhule"


@pytest.mark.parametrize("question", ["What was the rainfall in Dhule in July 2024?", "What is normal rainfall in July in Dhule?"])
def test_historical_chat_routing_extracts_location(question):
    result = asyncio.run(LLMService(provider=object()).classify(question))
    assert result.intent == ChatIntent.HISTORICAL_WEATHER and result.city == "Dhule"


@pytest.mark.anyio
async def test_historical_chat_uses_tool_facts_and_says_unavailable_without_records():
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.HISTORICAL_WEATHER, city="Dhule"))
    unavailable = HistoricalDataset(status="no_data", availability_status="NO_WEATHER_DATA", location="Dhule", reason="No validated rows for requested period")
    tool = AsyncMock(return_value=unavailable)
    response = await WeatherAgent(llm_service=llm, historical_tool=tool).answer("What rainfall in Dhule in 2025?")
    assert "unavailable" in response.message and "cannot provide a value" in response.message
    assert response.historical_data["status"] == "no_data"
    tool.assert_awaited_once_with("Dhule", date(2025, 1, 1), date(2025, 12, 31))


@pytest.mark.anyio
async def test_historical_chat_routes_requested_observation_period():
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.HISTORICAL_WEATHER, city="Dhule"))
    tool = AsyncMock(return_value=HistoricalDataset(status="available", location="Dhule", source="IMD", records=records()))
    response = await WeatherAgent(llm_service=llm, historical_tool=tool).answer("What rainfall in July 2025?")
    assert response.tool_used == "get_historical_weather"
    tool.assert_awaited_once_with("Dhule", date(2025, 7, 1), date(2025, 7, 31))


@pytest.mark.anyio
async def test_live_local_historical_chat_uses_records_and_normal_files():
    agent = WeatherAgent(llm_service=LLMService(provider=object()))
    observed = await agent.answer("What was the rainfall in Dhule in July 2024?")
    normal = await agent.answer("What is normal rainfall in July in Dhule?")
    assert observed.intent == ChatIntent.HISTORICAL_WEATHER and "mm across 31 available daily records" in observed.message
    assert observed.historical_data["status"] == "available"
    assert normal.historical_data["kind"] == "CLIMATOLOGY" and "1991-2020" in normal.message
    assert "not an observation" in normal.message


@pytest.mark.anyio
async def test_chat_trend_and_annual_normal_comparison_use_structured_history_analysis():
    llm = Mock()
    llm.classify = AsyncMock(return_value=ChatIntentResult(intent=ChatIntent.HISTORICAL_WEATHER, city="Dhule"))
    agent = WeatherAgent(llm_service=llm)

    trend_answer = await agent.answer("What was the rainfall trend in Dhule?")
    assert trend_answer.historical_data["trend"]["status"] == "available"
    assert trend_answer.historical_data["trend"]["observations"] >= 8
    assert str(trend_answer.historical_data["trend"]["slope_per_year"]) in trend_answer.message
    assert "not a forecast or significance claim" in trend_answer.message

    comparison_answer = await agent.answer("How does rainfall in Dhule in 2020 compare with normal?")
    comparison = comparison_answer.historical_data["annual_climatology"]
    assert comparison["status"] == "available" and comparison["kind"] == "ANOMALY"
    assert comparison["observed_mm"] is not None and comparison["normal_mm"] is not None
    assert str(comparison["anomaly_mm"]) in comparison_answer.message
    assert "not an IMD warning" in comparison_answer.message


@pytest.mark.anyio
async def test_generic_city_history_uses_resolved_coordinates_without_dhule_fallback(monkeypatch):
    from app.services.location_service import ResolvedLocation, location_service
    from app.tools.weather_tools import get_historical_weather
    async def resolve(query):
        assert query == "Nashik"
        return ResolvedLocation(query=query, city="Nashik", state="Maharashtra", country="IN", latitude=19.9975,
            longitude=73.7898, source="fixture geocoder", resolution_method="provider_geocoding")
    monkeypatch.setattr(location_service, "resolve", resolve)
    result = await get_historical_weather("Nashik", date(2024, 7, 1), date(2024, 7, 2))
    assert result.status == "no_data" and result.availability_status == "NO_WEATHER_DATA"
    assert not result.records


@pytest.mark.anyio
async def test_city_climatology_uses_geocoded_coordinates_and_returns_selected_grid(monkeypatch):
    from app.services.location_service import ResolvedLocation, location_service
    from app.tools.weather_tools import get_climatology_normal
    async def resolve(query):
        assert query == "Pune"
        return ResolvedLocation(query=query, city=query, state="Maharashtra", country="IN", latitude=18.52,
            longitude=73.85, source="fixture geocoder", resolution_method="provider_geocoding")
    monkeypatch.setattr(location_service, "resolve", resolve)
    result = await get_climatology_normal("Pune", 7)
    assert result["status"] == "available" and result["baseline"] == "1991-2020"
    assert result["requested_latitude"] == 18.52 and result["resolution_degrees"] == 0.25


@pytest.mark.parametrize("value,baseline,difference,pct", [(12, 10, 2, 20), (8, 10, -2, -20), (10, 10, 0, 0), (2, 0, 2, None)])
def test_comparison(value, baseline, difference, pct):
    result = compare(value, baseline)
    assert result["difference"] == difference
    assert result["percentage_difference"] == pct


def test_trend_directions_and_insufficient_data():
    assert trend([1, 2, 3, 6]) == "increasing"
    assert trend([6, 5, 3, 1]) == "decreasing"
    assert trend([2, 2, 2, 2]) == "stable"
    assert trend([2, 3, 4]) == "insufficient data"


def test_empty_aggregation_is_not_zero_rainfall():
    result = aggregate([])
    assert result["status"] == "no_data"
    assert result["reason"]


@pytest.mark.anyio
async def test_history_api_returns_controlled_unavailable(client):
    response = await client.get("/api/v1/weather/history", params={"city": "Dhule", "start_date": "2025-07-01", "end_date": "2025-07-31"})
    assert response.status_code == 200
    assert response.json()["status"] == "no_data"
    assert response.json()["availability_status"] == "NO_WEATHER_DATA"
    assert response.json()["records"] == []


@pytest.mark.anyio
async def test_installed_rainfall_history_api_backwards_compatible_and_has_analysis(client):
    response = await client.get("/api/v1/weather/history", params={"city": "Dhule", "start_date": "2024-07-01", "end_date": "2024-07-31"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available" and len(body["records"]) == 31
    assert body["summary"]["rainfall_observations"] == 31
    assert body["monthly"][0]["total_rainfall"] is not None
    assert body["metadata"]["grid_resolution"] == 0.25
    assert body["analysis"]["climatology"][0]["rainfall"]["baseline"] == "1991-2020"
    assert body["analysis"]["climatology"][0]["tmax"]["status"] == "available"


@pytest.mark.anyio
async def test_partial_month_never_gets_full_month_anomaly(client):
    response = await client.get("/api/v1/weather/history", params={"city": "Dhule", "start_date": "2024-07-01", "end_date": "2024-07-02"})
    body = response.json()
    comparison = body["analysis"]["comparisons"][0]
    assert body["status"] == "available"
    assert comparison["status"] == "insufficient_data"
    assert comparison["anomaly_rainfall_mm"] is None and comparison["expected_days"] == 31


@pytest.mark.anyio
async def test_climatology_endpoint_and_history_coordinate_selection(client):
    normal = await client.get("/api/v1/weather/climatology", params={"month": 7, "lat": 20.9, "lon": 74.8, "variable": "rainfall"})
    assert normal.status_code == 200
    assert normal.json()["normals"][0]["normal"] > 0
    history = await client.get("/api/v1/weather/history", params={"lat": 20.9, "lon": 74.8, "start_date": "2024-07-01", "end_date": "2024-07-02"})
    assert history.status_code == 200 and history.json()["records"]


@pytest.mark.anyio
async def test_history_date_range_comparison_is_structured(client):
    response = await client.get("/api/v1/weather/history", params={"city": "Dhule", "start_date": "2024-07-01", "end_date": "2024-07-31", "compare_start_date": "2023-07-01", "compare_end_date": "2023-07-31"})
    assert response.status_code == 200
    comparison = next(row for row in response.json()["analysis"]["comparisons"] if row["kind"] == "date_range")
    assert comparison["status"] == "available"
    assert comparison["first_period"]["observed_rainfall_mm"] is not None
    assert comparison["difference_mm"] is not None


def test_climatology_reads_real_july_normals_and_missing_tmax_file_is_unavailable(tmp_path, monkeypatch):
    service = ImdClimatologyService()
    rain = service.monthly_normal("rainfall", 7, 20.9, 74.8)
    tmax = service.monthly_normal("tmax", 7, 20.9, 74.8)
    monkeypatch.setattr(service, "ROOT", tmp_path)
    missing_tmax = service.monthly_normal("tmax", 1, 20.9, 74.8)
    assert rain["kind"] == "CLIMATOLOGY" and rain["baseline"] == "1991-2020" and rain["units"] == "mm"
    assert rain["normal"] > 0 and rain["resolution_degrees"] == 0.25
    assert tmax["normal"] is not None and tmax["resolution_degrees"] == 0.5
    assert missing_tmax["status"] == "unavailable" and missing_tmax["reason"] == "climatology_file_missing"


def test_climatology_does_not_snap_out_of_coverage_location_to_grid_edge():
    result = ImdClimatologyService().monthly_normal("rainfall", 7, 51.5, -0.1)
    assert result["status"] == "no_data"
    assert result["reason"] == "climatology_location_unavailable"
    assert result["normal"] is None


def test_linear_trend_reports_slope_coverage_and_insufficient_data():
    result = linear_trend([(year, value) for year, value in zip(range(2013, 2021), range(0, 16, 2))])
    assert result["status"] == "available" and result["slope_per_year"] == 2
    assert result["observations"] == 8 and result["method"].startswith("ordinary least squares")
    assert linear_trend([(2020, 1), (2021, 2)]) ["status"] == "insufficient_data"


def test_rainfall_anomaly_is_structured_and_requires_both_values():
    assert rainfall_anomaly(100, 80) == {"status": "available", "anomaly_rainfall_mm": 20, "anomaly_percent": 25}
    assert rainfall_anomaly(None, 80)["status"] == "insufficient_data"


def test_annual_rainfall_normal_comparison_requires_complete_observed_months():
    observations = [{"month_number": month, "complete_month": True, "total_rainfall": 10} for month in range(1, 13)]
    normals = [{"month": month, "status": "available", "normal": 5} for month in range(1, 13)]
    result = annual_rainfall_climatology_comparison(observations, normals)
    assert result["status"] == "available" and result["observed_mm"] == 120
    assert result["normal_mm"] == 60 and result["anomaly_mm"] == 60 and result["units"] == "mm"
    observations[0]["complete_month"] = False
    assert annual_rainfall_climatology_comparison(observations, normals)["status"] == "insufficient_data"


@pytest.mark.anyio
async def test_default_local_provider_returns_validated_rainfall_only_and_coordinate_selection():
    provider = LocalImdGridHistoricalProvider()
    result = await provider.fetch("Dhule", date(2024, 7, 1), date(2024, 7, 3))
    assert result.status == "available" and len(result.records) == 3
    assert all(record.temperature_mean is None and record.temperature_max is None for record in result.records)
    close = await provider.fetch("coordinate", date(2024, 7, 1), date(2024, 7, 2), 20.9, 74.8)
    far = await provider.fetch("coordinate", date(2024, 7, 1), date(2024, 7, 2), 28.6, 77.2)
    assert close.status == "available" and far.status == "no_data"


@pytest.mark.anyio
async def test_history_api_rejects_reversed_range(client):
    response = await client.get("/api/v1/weather/history", params={"city": "Dhule", "start_date": "2025-08-01", "end_date": "2025-07-31"})
    assert response.status_code == 422
