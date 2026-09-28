from datetime import date, timedelta

import numpy as np
import pytest

from app.services.imd_rainfall_pipeline import validate_and_extract_rainfall_file


def _write_rainfall_fixture(path, *, year=2023, duplicate_day=False, extra_dimension=False,
                           invalid_latitude=False, negative_rainfall=False, wrong_units=False):
    netcdf = pytest.importorskip("scipy.io").netcdf_file
    days = (date(year + 1, 1, 1) - date(year, 1, 1)).days
    latitudes = np.linspace(6.5, 38.5, 129)
    longitudes = np.linspace(66.5, 100.0, 135)
    if invalid_latitude:
        latitudes[20] += 0.1
    offsets = np.arange(days, dtype="d")
    if duplicate_day:
        offsets[1] = offsets[0]
    values = np.zeros((days, 129, 135), dtype="f")
    values[:, :, :] = 1.0
    # One missing-value marker at Dhule's nearest cell; it must stay NULL.
    lat_index = int(np.where(np.isclose(latitudes, 21.0))[0][0])
    lon_index = int(np.where(np.isclose(longitudes, 74.75))[0][0])
    values[0, lat_index, lon_index] = -999.0
    values[1, lat_index, lon_index] = 25.0
    if negative_rainfall:
        values[2, lat_index, lon_index] = -1.0
    with netcdf(path, "w") as nc:
        nc.createDimension("TIME", days)
        nc.createDimension("LATITUDE", 129)
        nc.createDimension("LONGITUDE", 135)
        if extra_dimension:
            nc.createDimension("LEVEL", 1)
        lat = nc.createVariable("LATITUDE", "d", ("LATITUDE",))
        lon = nc.createVariable("LONGITUDE", "d", ("LONGITUDE",))
        time = nc.createVariable("TIME", "d", ("TIME",))
        rain = nc.createVariable("RAINFALL", "f", ("TIME", "LATITUDE", "LONGITUDE"))
        lat.units = b"degrees_north"
        lon.units = b"degrees_east"
        time.units = f"days since {year}-01-01 00:00:00".encode()
        rain.units = b"cm" if wrong_units else b"mm"
        rain.missing_value = -999.0
        rain._FillValue = -999.0
        lat[:] = latitudes
        lon[:] = longitudes
        time[:] = offsets
        rain[:] = values


def test_yearly_rainfall_pipeline_validates_and_extracts_normalized_point_rows(tmp_path):
    path = tmp_path / "RF25_ind2023_rfp25.nc"
    _write_rainfall_fixture(path)
    report, records = validate_and_extract_rainfall_file(path, 20.90, 74.80)
    assert report.status == "PASS"
    assert report.expected_records == report.actual_records == 365
    assert report.missing_rainfall_count == 1
    assert report.duplicate_date_count == report.missing_date_count == 0
    assert report.coordinate_bounds["latitude_min"] == pytest.approx(6.5)
    assert report.coordinate_bounds["latitude_max"] == pytest.approx(38.5)
    assert report.coordinate_bounds["longitude_min"] == pytest.approx(66.5)
    assert report.coordinate_bounds["longitude_max"] == pytest.approx(100.0)
    assert report.date_start == "2023-01-01" and report.date_end == "2023-12-31"
    assert report.minimum_rainfall_mm == 1.0 and report.maximum_rainfall_mm == 25.0
    assert report.units == "mm" and report.grid_resolution_degrees == pytest.approx(.25)
    assert (report.selected_latitude, report.selected_longitude) == (21.0, 74.75)
    assert report.selection_distance_km == pytest.approx(12.272, abs=.01)
    assert records[0] == {
        "date": "2023-01-01", "latitude": 21.0, "longitude": 74.75, "rainfall_mm": None,
        "source": "India Meteorological Department (IMD Pune)",
        "dataset": "Daily Gridded Rainfall 0.25 degree", "grid_resolution": .25,
    }
    assert records[1]["rainfall_mm"] == 25.0


def test_duplicate_dates_and_unexpected_dimensions_fail_validation(tmp_path):
    path = tmp_path / "RF25_ind2023_rfp25.nc"
    _write_rainfall_fixture(path, duplicate_day=True, extra_dimension=True)
    report, _ = validate_and_extract_rainfall_file(path, 20.90, 74.80)
    assert report.status == "FAIL"
    assert report.duplicate_date_count == 1
    assert report.missing_date_count == 1
    assert report.unexpected_dimensions == ["LEVEL"]


def test_invalid_coordinates_units_and_negative_values_are_reported(tmp_path):
    path = tmp_path / "RF25_ind2023_rfp25.nc"
    _write_rainfall_fixture(path, invalid_latitude=True, negative_rainfall=True, wrong_units=True)
    report, _ = validate_and_extract_rainfall_file(path, 20.90, 74.80)
    assert report.status == "FAIL"
    assert report.invalid_coordinate_count == 1
    assert report.units == "cm"
    assert report.minimum_rainfall_mm == -1.0
    assert "negative rainfall values found" in report.issues
    assert "unexpected rainfall units: cm" in report.issues


def test_2025_is_marked_provenance_unverified(tmp_path):
    path = tmp_path / "RF25_ind2025_rfp25.nc"
    _write_rainfall_fixture(path, year=2025)
    report, rows = validate_and_extract_rainfall_file(path, 20.90, 74.80)
    assert report.status == "PASS"
    assert report.provenance_status == "UNVERIFIED_BEYOND_OFFICIAL_ARCHIVE_END_2024"
    assert len(rows) == 365


def test_monthly_climatology_is_not_accepted_as_daily_observation(tmp_path):
    path = tmp_path / "rf_p25_jan_clm.nc"
    path.touch()
    with pytest.raises(ValueError, match="annual IMD RF25"):
        validate_and_extract_rainfall_file(path, 20.9, 74.8)
