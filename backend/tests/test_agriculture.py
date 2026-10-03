import json
from datetime import datetime, timezone

import pytest

from app.schemas.agriculture import AgricultureActivity, AgricultureRequest, StationObservation
from app.services.agriculture_service import AgricultureDecisionEngine
from app.services import imd_station_service as station_service


def configure_station_fixture(tmp_path, monkeypatch):
    root = tmp_path
    (root / "data" / "stations").mkdir(parents=True)
    (root / "data" / "raw" / "imd_dsp").mkdir(parents=True)
    catalog = {
        "stations": [{
            "station_id": "70001", "station_name": "Fixture Station", "district": "Test", "state": "Test",
            "country": "IN", "latitude": 20.0, "longitude": 74.0, "elevation_m": 100,
            "source": "IMD Data Service Portal", "datasets": {
                "daily": {"name": "SURFACE_TABLE_2_DAY_SUMMARY", "path": "data/raw/imd_dsp/daily.csv"},
                "synoptic": {"name": "SURFACE_TABLE_3_SYNOPTIC_HOUR", "path": "data/raw/imd_dsp/synoptic.csv"},
            },
        }]
    }
    (root / "data" / "stations" / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    monkeypatch.setattr(station_service, "PROJECT_ROOT", root)
    monkeypatch.setattr(station_service, "CATALOG_PATH", root / "data" / "stations" / "catalog.json")
    station_service._load_observations.cache_clear()
    station_service._quality_report.cache_clear()
    return root


def test_station_metadata_daily_validation_duplicates_missing_and_provenance(tmp_path, monkeypatch):
    root = configure_station_fixture(tmp_path, monkeypatch)
    (root / "data" / "raw" / "imd_dsp" / "daily.csv").write_text(
        "INDEX,YEAR,MN,DT,MAX,MIN,RF\n"
        "70001,2024,01,01,25,10,0\n"
        "70001,2024,01,01,24,11,\n"
        "70001,2024,01,03,70,9,2\n", encoding="utf-8")
    (root / "data" / "raw" / "imd_dsp" / "synoptic.csv").write_text(
        "INDEX,YEAR,MN,HR,DT,SLP,MSLP,DBT,WBT,DPT,RH,VP,DD,FFF,AW,RF\n", encoding="utf-8")
    records = station_service.station_observations("70001", "daily")
    assert records[0].source == "IMD Data Service Portal"
    assert records[0].dataset == "SURFACE_TABLE_2_DAY_SUMMARY"
    assert records[0].observed_at == datetime(2024, 1, 1, 3, tzinfo=timezone.utc)
    assert records[0].rainfall_mm == 0
    assert records[1].rainfall_mm is None
    assert "duplicate_observation_time" in records[0].quality_flags
    assert "duplicate_observation_time" in records[1].quality_flags
    assert records[2].temp_max_c is None and records[2].invalid_values["MAX"] == "70"
    report = station_service.station_quality_report("70001")
    assert report.datasets["daily"]["row_count"] == 3
    assert report.datasets["daily"]["duplicate_records"] == 1
    assert report.datasets["daily"]["missing_dates_or_slots_between_coverage"] == 1
    assert report.datasets["daily"]["missing_values_by_parameter"]["RF"] == 1
    assert report.datasets["daily"]["invalid_values_by_parameter"]["MAX"] == 1


def test_synoptic_timestamp_mapping_values_and_invalid_direction_are_explicit(tmp_path, monkeypatch):
    root = configure_station_fixture(tmp_path, monkeypatch)
    (root / "data" / "raw" / "imd_dsp" / "daily.csv").write_text("INDEX,YEAR,MN,DT,MAX,MIN,RF\n", encoding="utf-8")
    (root / "data" / "raw" / "imd_dsp" / "synoptic.csv").write_text(
        "INDEX,YEAR,MN,HR,DT,SLP,MSLP,DBT,WBT,DPT,RH,VP,DD,FFF,AW,RF\n"
        "70001,2024,01,1200,02,937.4,997.5,29.2,24.8,23.0,69,28.1,110,16,8,0.4\n"
        "70001,2024,01,12,03,937.4,997.5,29.2,,23.0,69,,390,16,,\n", encoding="utf-8")
    records = station_service.station_observations("70001", "synoptic")
    assert records[0].observed_at == datetime(2024, 1, 2, 12, tzinfo=timezone.utc)
    assert records[0].wind_direction == "ESE"
    assert records[0].wind_speed_kmh == 16
    assert records[0].rainfall_mm == 0.4
    assert records[1].observed_at == datetime(2024, 1, 3, 3, tzinfo=timezone.utc)
    assert records[1].wet_bulb_c is None
    assert records[1].invalid_values["DD"] == "390"
    assert "invalid_DD" in records[1].quality_flags


def test_nearest_station_generic_distance_and_outside_coverage(tmp_path, monkeypatch):
    configure_station_fixture(tmp_path, monkeypatch)
    meta, distance = station_service.nearest_station(20.01, 74.01)
    assert meta.station_id == "70001"
    assert 1 < distance < 2
    assert station_service.nearest_station(0, 0) is None


def inputs(rain_pct=0, wind_ms=1, temp_max=25, nwp_rain=0):
    return {
        "current": {"source": "OpenWeatherMap", "observed_at": "2026-09-30T00:00:00Z", "weather": {"temperature": 25, "humidity": 60, "wind_speed": 1}},
        "forecast": {"source": "OpenWeatherMap", "periods": [{"date": "2026-09-30T00:00:00Z", "temperature_max": temp_max, "temperature_min": 20, "rain_probability": rain_pct, "wind_speed": wind_ms, "description": "light rain" if rain_pct >= 60 else "clear"}]},
        "nwp": {"source": "NOAA/NCEP NOMADS", "initialization_time": "2026-09-30T00:00:00Z", "points": [{"forecast_time": "2026-09-30T06:00:00Z", "temperature_c": temp_max, "precipitation_since_initialization_mm": nwp_rain, "wind_speed_ms": wind_ms}]},
    }


@pytest.mark.parametrize("activity,kwargs,expected", [
    ("irrigation", {"rain_pct": 80}, "rain_may_reduce_need"),
    ("sowing", {"rain_pct": 80}, "wet_weather_signal"),
    ("spraying", {"rain_pct": 80}, "unfavorable_weather_signal"),
    ("harvesting", {"rain_pct": 80}, "rainfall_concern"),
    ("field_operations", {"wind_ms": 8}, "weather_caution"),
    ("heat_stress", {"temp_max": 41}, "high_weather_heat_concern"),
    ("heavy_rain", {"nwp_rain": 55}, "high_weather_rainfall_concern"),
    ("wind_risk", {"wind_ms": 11}, "high_weather_wind_concern"),
])
def test_deterministic_agriculture_activity_rules(activity, kwargs, expected):
    context = inputs(**kwargs)
    result = AgricultureDecisionEngine().evaluate(AgricultureRequest(city="Fixture", activity=activity), **context)
    assert result.condition == expected
    assert result.evidence
    assert "not an official agricultural department" in " ".join(result.limitations)


def test_insufficient_weather_data_does_not_create_recommendation_values():
    result = AgricultureDecisionEngine().evaluate(AgricultureRequest(city="Fixture", activity="spraying"), current=None, forecast=None, nwp=None)
    assert result.condition == "insufficient_data"
    assert not result.evidence


def test_stale_station_observation_is_not_used_as_current_evidence():
    old = StationObservation(station_id="70001", station_name="Fixture", latitude=20, longitude=74,
        observed_at=datetime(2025, 1, 1, tzinfo=timezone.utc), source="IMD Data Service Portal",
        dataset="SURFACE_TABLE_2_DAY_SUMMARY", rainfall_mm=20)
    result = AgricultureDecisionEngine().evaluate(AgricultureRequest(city="Fixture", activity="irrigation"),
        current=None, forecast=None, nwp=None, recent_station=old)
    assert result.condition == "insufficient_data"
    assert not any("station rainfall" in item.label for item in result.evidence)
    assert any("stale" in item for item in result.limitations)
