from datetime import date

import pytest

from app.services.imd_grd_inspection import expected_daily_records, expected_record_bytes
from app.services.imd_temperature_pipeline import (
    TemperatureDecodeBlocked, audit_temperature_directory, make_normalized_temperature_record,
    missing_years, read_temperature_grd, select_temperature_grid_point,
    temperature_value_to_nullable,
)


def _create_grd(path, year):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    with path.open("r+b") as handle:
        handle.truncate(expected_daily_records(year) * expected_record_bytes())
    return path


def test_file_size_and_leap_year_layout_validation(tmp_path):
    report = audit_temperature_directory(tmp_path)
    assert report["files_inspected"] == 0
    assert report["structure_status"] == "FAIL"
    assert expected_record_bytes() == 3844
    assert expected_daily_records(2012) == 366
    _create_grd(tmp_path / "Maxtemp_MaxT_2012.GRD", 2012)
    report = audit_temperature_directory(tmp_path)
    item = report["files"][0]
    assert report["structure_status"] == "PASS"
    assert item["expected_daily_records"] == 366
    assert item["expected_date_start_by_archive_convention"] == "2012-01-01"
    assert item["expected_date_end_by_archive_convention"] == "2012-12-31"
    assert item["date_continuity_status"].startswith("EXPECTED_FROM_FILENAME")
    assert item["value_quality_status"] == "BLOCKED_NOT_DECODED"


def test_missing_year_gap_and_tmax_2013_is_not_fabricated(tmp_path):
    assert missing_years([2010, 2011, 2012, 2014, 2015]) == [2013]
    for year in (2010, 2012, 2014):
        _create_grd(tmp_path / f"Maxtemp_MaxT_{year}.GRD", year)
    for year in (2010, 2011, 2012, 2013, 2014):
        _create_grd(tmp_path / f"Mintemp_MinT_{year}.GRD", year)
    report = audit_temperature_directory(tmp_path)
    assert report["products"]["tmax"]["detected_years"] == [2010, 2012, 2014]
    assert report["products"]["tmax"]["missing_years_within_detected_range"] == [2011, 2013]
    assert 2013 not in report["products"]["tmax"]["detected_years"]
    assert report["products"]["tmin"]["missing_years_within_detected_range"] == []
    assert report["tmax_tmin_overlap"]["years_by_filename"] == [2010, 2012, 2014]
    assert report["tmax_tmin_overlap"]["expected_calendar_days_by_annual_convention"] == 1096
    assert report["tmax_tmin_overlap"]["measurement_level_tmin_le_tmax_check"] == "NOT_RUN_GRD_VALUES_NOT_DECODED"


def test_decode_fails_before_reading_when_format_is_unverified(tmp_path, monkeypatch):
    path = _create_grd(tmp_path / "Mintemp_MinT_2024.GRD", 2024)

    def forbid_read_bytes(*args, **kwargs):
        raise AssertionError("GRD bytes must not be read before format verification")

    monkeypatch.setattr(type(path), "read_bytes", forbid_read_bytes)
    with pytest.raises(TemperatureDecodeBlocked, match="byte_order.*explicit_float_representation"):
        read_temperature_grd(path, 20.9, 74.8)


def test_structural_size_mismatch_fails_before_decode(tmp_path):
    path = tmp_path / "Maxtemp_MaxT_2013.GRD"
    path.write_bytes(b"small invalid layout")
    with pytest.raises(ValueError, match="structural validation failed"):
        read_temperature_grd(path, 20.9, 74.8)


def test_missing_value_conversion_and_nullable_temperature_schema():
    assert temperature_value_to_nullable(99.9) is None
    assert temperature_value_to_nullable(float("nan")) is None
    assert temperature_value_to_nullable(0) == 0
    tmax = make_normalized_temperature_record(observation_date=date(2024, 1, 1),
        latitude=20.9, longitude=74.8, dataset_type="tmax", value=25.5)
    tmin = make_normalized_temperature_record(observation_date=date(2024, 1, 1),
        latitude=20.9, longitude=74.8, dataset_type="tmin", value=99.9)
    assert (tmax.latitude, tmax.longitude, tmax.grid_resolution) == (20.5, 74.5, 1.0)
    assert tmax.temp_max_c == 25.5 and tmax.temp_min_c is None
    assert tmin.temp_min_c is None and tmin.temp_max_c is None
    assert tmax.source and "Maximum Temperature" in tmax.dataset


def test_generic_temperature_coordinate_selection_and_invalid_coordinates():
    point = select_temperature_grid_point(20.9, 74.8)
    assert (point.requested_latitude, point.requested_longitude) == (20.9, 74.8)
    assert (point.grid_latitude, point.grid_longitude) == (20.5, 74.5)
    assert point.distance_km > 0
    other = select_temperature_grid_point(28.6, 77.2)
    assert (other.grid_latitude, other.grid_longitude) == (28.5, 77.5)
    with pytest.raises(ValueError, match="coverage"):
        select_temperature_grid_point(95, 10)


def test_file_provenance_and_unverified_binary_fields_are_explicit(tmp_path):
    _create_grd(tmp_path / "Maxtemp_MaxT_2024.GRD", 2024)
    _create_grd(tmp_path / "Mintemp_MinT_2025.GRD", 2025)
    report = audit_temperature_directory(tmp_path)
    tmax, tmin = report["files"]
    assert tmax["provenance_status"] == "FILENAME_WITHIN_PUBLISHED_PRODUCT_PERIOD_SOURCE_CHAIN_UNVERIFIED"
    assert tmin["provenance_status"] == "OUTSIDE_PUBLISHED_PRODUCT_PERIOD_SOURCE_CHAIN_UNVERIFIED"
    assert report["format_metadata"]["byte_order"] == "UNVERIFIED"
    assert report["format_metadata"]["explicit_float_representation"] == "UNVERIFIED"
    assert report["format_metadata"]["raw_ij_to_geographic_mapping"] == "UNVERIFIED"
    assert report["format_metadata"]["header_or_prefix_structure"] == "UNVERIFIED"
    assert "byte_order" in report["format_metadata"]["unverified_required_for_decode"]
    assert report["format_metadata"]["header_bytes"] == "UNKNOWN"
    assert report["decode_status"] == "BLOCKED_FORMAT_FIELDS_UNVERIFIED"
    assert "Monthly and Seasonal Mean Temperature" in report["format_metadata"]["local_pdf_finding"]["title"]
