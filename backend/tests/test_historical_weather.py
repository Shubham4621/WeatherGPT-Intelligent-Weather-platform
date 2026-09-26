from datetime import date, datetime, timezone
import asyncio

import pytest

from app.services.historical_weather_service import (
    HistoricalDataset, HistoricalWeatherRecord, HistoricalWeatherService,
    UnconfiguredHistoricalProvider, aggregate, compare, monthly_aggregation, yearly_aggregation, trend,
)
from app.services.llm_service import LLMService
from app.schemas.chat import ChatIntent


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
    assert response.json()["status"] == "unavailable"
    assert response.json()["records"] == []


@pytest.mark.anyio
async def test_history_api_rejects_reversed_range(client):
    response = await client.get("/api/v1/weather/history", params={"city": "Dhule", "start_date": "2025-08-01", "end_date": "2025-07-31"})
    assert response.status_code == 422
