import csv
import json
from datetime import date
from pathlib import Path

import pytest

from app.services.historical_data import (
    IMD_DATASETS, NormalizedHistoricalRecord, nearest_grid_point, select_nearest_grid_point,
    normalize_missing, validate_metadata, validate_records, validate_csv,
    read_binary_grid_point,
)
from app.services.historical_weather_service import (
    HistoricalWeatherService, LocalImdGridHistoricalProvider, UnconfiguredHistoricalProvider,
)


def test_catalog_metadata_is_valid():
    assert all(not validate_metadata(item) for item in IMD_DATASETS.values())
    catalog = json.loads((Path(__file__).parents[2] / "data" / "imd_catalog.json").read_text(encoding="utf-8"))
    assert {row["dataset"] for row in catalog["datasets"]} == {item.dataset for item in IMD_DATASETS.values()}


@pytest.mark.parametrize(("kind", "expected"), [
    ("rainfall", (21.0, 74.75)), ("tmax", (20.5, 74.5)), ("tmin", (20.5, 74.5)),
])
def test_dhule_nearest_grid_points(kind, expected):
    point = nearest_grid_point(20.9, 74.8, kind)
    assert (point.latitude, point.longitude) == expected
    assert (point.requested_latitude, point.requested_longitude) == (20.9, 74.8)
    assert point.distance_km > 0


def test_grid_selection_validates_inputs():
    with pytest.raises(ValueError):
        nearest_grid_point(100, 74.8, "rainfall")
    with pytest.raises(ValueError):
        nearest_grid_point(20.9, 74.8, "unknown")
    with pytest.raises(ValueError):
        nearest_grid_point(50, 74.8, "rainfall")


@pytest.mark.parametrize(("requested", "coordinates", "selected"), [
    ((0.4, 0.6), [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0)], (0.0, 1.0)),
    ((-33.86, 151.20), [(-34.0, 151.0), (-33.0, 152.0)], (-34.0, 151.0)),
    ((40.71, -74.0), [(40.5, -74.5), (41.0, -73.5)], (40.5, -74.5)),
])
def test_generic_selection_supports_hypothetical_coordinates(requested, coordinates, selected):
    point = select_nearest_grid_point(*requested, coordinates)
    assert (point.requested_latitude, point.requested_longitude) == requested
    assert (point.grid_latitude, point.grid_longitude) == selected
    assert point.distance_km > 0


def test_generic_selection_handles_grid_boundaries_and_exact_distance():
    point = select_nearest_grid_point(90, 180, [(90, 180), (89, 179)])
    assert (point.grid_latitude, point.grid_longitude) == (90, 180)
    assert point.distance_km == pytest.approx(0)
    one_degree = select_nearest_grid_point(0, 0, [(0, 1)])
    assert one_degree.distance_km == pytest.approx(111.195, abs=.01)
    assert IMD_DATASETS["rainfall"].resolution == .25
    assert IMD_DATASETS["tmax"].resolution == 1.0
    assert IMD_DATASETS["tmin"].resolution == 1.0


def test_generic_selection_rejects_empty_or_invalid_grid_coordinates():
    with pytest.raises(ValueError):
        select_nearest_grid_point(0, 0, [])
    with pytest.raises(ValueError):
        select_nearest_grid_point(0, 0, [(91, 0)])


@pytest.mark.parametrize("dataset_type", ["tmax", "tmin"])
def test_temperature_grd_decoder_does_not_accept_unspecified_byte_order(dataset_type, tmp_path):
    with pytest.raises(ValueError, match="byte_order"):
        read_binary_grid_point(tmp_path / "not-read.grd", dataset_type, 20.9, 74.8,
                               year=2024, byte_order="native", cell_order="unknown")


@pytest.mark.parametrize("dataset_type", ["tmax", "tmin"])
def test_temperature_grd_decoder_requires_explicit_cell_order(dataset_type, tmp_path):
    with pytest.raises(ValueError, match="cell_order"):
        read_binary_grid_point(tmp_path / "not-read.grd", dataset_type, 20.9, 74.8,
                               year=2024, byte_order="<", cell_order="unknown")


@pytest.mark.parametrize("dataset_type", ["tmax", "tmin"])
def test_temperature_grd_decoder_blocks_before_read_even_with_caller_supplied_layout(
    dataset_type, tmp_path, monkeypatch,
):
    def forbid_payload_read(*args, **kwargs):
        raise AssertionError("unverified GRD payload must not be opened")

    monkeypatch.setattr(Path, "read_bytes", forbid_payload_read)
    with pytest.raises(RuntimeError) as blocked:
        read_binary_grid_point(
            tmp_path / "not-read.grd", dataset_type, 20.9, 74.8,
            year=2024, byte_order="<", cell_order="latitude_rows_longitude_fastest",
        )
    assert blocked.value.reason_code == "BLOCKED_FORMAT_FIELDS_UNVERIFIED"
    assert blocked.value.details["unverified_fields"]


def test_missing_value_markers_are_null_not_zero():
    assert normalize_missing(-999, "rainfall") is None
    assert normalize_missing(99.9, "tmax") is None
    assert normalize_missing(99.9, "tmin") is None
    # -999 is documented for the rainfall product here, not for the temp GRD.
    assert normalize_missing(-999, "tmax") == -999
    assert normalize_missing(-999, "tmin") == -999
    assert normalize_missing(0, "rainfall") == 0


def make_record(day: int, **values):
    return NormalizedHistoricalRecord(date=date(2024, 1, day), latitude=21, longitude=74.75,
        rainfall_mm=values.get("rainfall_mm", 0), temp_max_c=values.get("temp_max_c", 22),
        temp_min_c=values.get("temp_min_c", 12), source="IMD Pune", dataset="Daily grid", grid_resolution=.25)


def test_schema_accepts_nullable_variables_and_rejects_bad_coordinates():
    row = make_record(1, rainfall_mm=None, temp_max_c=None)
    assert row.rainfall_mm is None and row.temp_max_c is None
    with pytest.raises(ValueError):
        NormalizedHistoricalRecord(date="2024-01-01", latitude=91, longitude=74, source="x", dataset="x", grid_resolution=.25)


def test_validator_reports_gaps_duplicates_and_invalid_values():
    bad = make_record(2)
    bad.rainfall_mm = -1
    bad.temp_max_c = 100
    rows = [make_record(1), bad, make_record(2)]
    report = validate_records(rows, expected_start=date(2024, 1, 1), expected_end=date(2024, 1, 3))
    assert report.status == "FAIL"
    assert report.duplicate_dates == ["2024-01-02"]
    assert "2024-01-03" in report.date_gaps
    assert "negative rainfall" in report.invalid_values
    assert "impossible Tmax" in report.invalid_values


def test_csv_schema_nullable_fields_and_report(tmp_path):
    path = tmp_path / "records.csv"
    columns = ["date", "latitude", "longitude", "rainfall_mm", "temp_max_c", "temp_min_c", "source", "dataset", "grid_resolution"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow({"date": "2024-01-01", "latitude": 21, "longitude": 74.75, "rainfall_mm": "", "temp_max_c": 22, "temp_min_c": 12, "source": "IMD Pune", "dataset": "test", "grid_resolution": .25})
    report = validate_csv(path)
    assert report.records == 1 and report.missing_rainfall == 1 and report.status == "PASS"


@pytest.mark.anyio
async def test_local_provider_distinguishes_missing_file_from_unconfigured(tmp_path):
    local = await LocalImdGridHistoricalProvider(tmp_path / "missing.csv").fetch("Dhule", date(2024, 1, 1), date(2024, 1, 2))
    unconfigured = await UnconfiguredHistoricalProvider().fetch("Dhule", date(2024, 1, 1), date(2024, 1, 2))
    assert local.availability_status == "DATA_NOT_AVAILABLE"
    assert local.metadata["resolution"] == "0.25° rainfall; 1° Tmax/Tmin"
    assert unconfigured.availability_status == "NO_HISTORICAL_DATA_CONFIGURED"


@pytest.mark.anyio
async def test_local_provider_returns_real_csv_rows_and_no_data_is_distinct(tmp_path):
    path = tmp_path / "records.csv"
    path.write_text("date,latitude,longitude,rainfall_mm,temp_max_c,temp_min_c,source,dataset,grid_resolution\n2024-01-01,21,74.75,0,22,12,IMD Pune,test,0.25\n", encoding="utf-8")
    provider = LocalImdGridHistoricalProvider(path)
    available = await provider.fetch("Dhule", date(2024, 1, 1), date(2024, 1, 1))
    empty = await provider.fetch("Dhule", date(2024, 2, 1), date(2024, 2, 2))
    assert available.availability_status == "DATA_AVAILABLE"
    assert available.records[0].rainfall == 0
    assert empty.availability_status == "NO_WEATHER_DATA"


@pytest.mark.anyio
async def test_local_provider_rejects_empty_installed_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("date,latitude,longitude,rainfall_mm,temp_max_c,temp_min_c,source,dataset,grid_resolution\n", encoding="utf-8")
    result = await LocalImdGridHistoricalProvider(path).fetch("Dhule", date(2024, 1, 1), date(2024, 1, 2))
    assert result.availability_status == "DATA_INVALID"


@pytest.mark.parametrize("rows", [
    "2024-01-01,21,74.75,1,IMD,test,0.25\n2024-01-01,21,74.75,2,IMD,test,0.25\n",
    "2024-01-01,21,74.75,1,IMD,test,0.25\n2024-01-03,21,74.75,2,IMD,test,0.25\n",
    "2024-01-01,21,74.75,,IMD,test,0.25\n",
])
@pytest.mark.anyio
async def test_local_provider_does_not_repair_duplicate_gap_or_missing_observations(tmp_path, rows):
    path = tmp_path / "rain.csv"
    path.write_text("date,latitude,longitude,rainfall_mm,source,dataset,grid_resolution\n" + rows, encoding="utf-8")
    result = await LocalImdGridHistoricalProvider(path).fetch("Dhule", date(2024, 1, 1), date(2024, 1, 3))
    if ",,IMD," in rows:
        assert result.status == "partial" and result.metadata["missing_rainfall"] == 1
        assert result.records[0].rainfall is None
    else:
        assert result.status == "unavailable" and result.availability_status == "DATA_INVALID"


@pytest.mark.anyio
async def test_service_local_default_data_missing_never_yields_records(tmp_path):
    result = await HistoricalWeatherService(LocalImdGridHistoricalProvider(tmp_path / "absent.csv")).get_history("Dhule", date(2024, 1, 1), date(2024, 1, 2))
    assert result.status == "data_not_available"
    assert result.records == []
