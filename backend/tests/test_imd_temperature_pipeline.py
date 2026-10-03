from datetime import date
from dataclasses import replace

import pytest

from app.services.imd_grd_inspection import expected_daily_records, expected_record_bytes
from app.services.imd_temperature_pipeline import (
    RawIJMapping, TemperatureDecodeBlocked, TemperatureGrdFormatSpec,
    audit_temperature_directory, make_normalized_temperature_record,
    missing_years, read_temperature_grd, select_temperature_grid_point,
    temperature_date_for_record, temperature_format_blockers,
    temperature_value_to_nullable, validate_temperature_format_spec,
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

    def forbid_payload_open(*args, **kwargs):
        raise AssertionError("GRD bytes must not be read before format verification")

    monkeypatch.setattr(type(path), "read_bytes", forbid_payload_open)
    monkeypatch.setattr(type(path), "open", forbid_payload_open)
    with pytest.raises(TemperatureDecodeBlocked) as blocked:
        read_temperature_grd(path, 20.9, 74.8)
    assert blocked.value.reason_code == "BLOCKED_FORMAT_FIELDS_UNVERIFIED"
    assert blocked.value.details["unverified_fields"][:3] == [
        "numeric_representation", "byte_order", "raw_ij_mapping",
    ]


def _synthetic_complete_format_spec(**overrides):
    """Test-only configuration; these values are not claims about IMD files."""
    values = {
        "numeric_representation": "synthetic-test-binary32",
        "byte_order": "big",
        "raw_ij_mapping": RawIJMapping(
            i_axis="longitude", i_direction="ascending",
            j_axis="latitude", j_direction="ascending",
            i_index_origin=0, j_index_origin=0, fastest_index="i",
        ),
        "record_framing": "synthetic-test-direct-records",
    }
    values.update(overrides)
    return TemperatureGrdFormatSpec(**values)


@pytest.mark.parametrize(
    ("field", "missing_value"),
    [
        ("numeric_representation", None),
        ("byte_order", None),
        ("raw_ij_mapping", None),
    ],
)
def test_each_unresolved_decoder_critical_field_blocks(tmp_path, field, missing_value):
    path = _create_grd(tmp_path / "Maxtemp_MaxT_2024.GRD", 2024)
    spec = _synthetic_complete_format_spec(**{field: missing_value})
    with pytest.raises(TemperatureDecodeBlocked) as blocked:
        read_temperature_grd(path, 20.9, 74.8, format_spec=spec)
    assert blocked.value.reason_code == "BLOCKED_FORMAT_FIELDS_UNVERIFIED"
    assert field in blocked.value.details["unverified_fields"]


def test_invalid_format_configuration_is_blocked_before_payload_access(tmp_path, monkeypatch):
    path = _create_grd(tmp_path / "Maxtemp_MaxT_2024.GRD", 2024)

    def forbid_payload_open(*args, **kwargs):
        raise AssertionError("invalid format config must block before payload access")

    monkeypatch.setattr(type(path), "read_bytes", forbid_payload_open)
    monkeypatch.setattr(type(path), "open", forbid_payload_open)
    invalid = _synthetic_complete_format_spec(byte_order="native")
    with pytest.raises(TemperatureDecodeBlocked) as blocked:
        read_temperature_grd(path, 20.9, 74.8, format_spec=invalid)
    assert blocked.value.reason_code == "BLOCKED_FORMAT_CONFIGURATION_INVALID"


def test_explicit_synthetic_format_configuration_is_accepted_without_authorizing_decode():
    synthetic_payload = bytes(31 * 31 * 4)
    assert len(synthetic_payload) == 3844
    spec = _synthetic_complete_format_spec()
    assert validate_temperature_format_spec(spec) is None
    assert temperature_format_blockers(spec) == [
        "numeric_representation.authoritative_evidence",
        "byte_order.authoritative_evidence",
        "raw_ij_mapping.authoritative_evidence",
        "record_framing.authoritative_evidence",
    ]
    # Configuration validation is metadata-only; even this synthetic buffer is
    # not decoded, and no real IMD GRD bytes are involved.


def test_record_number_date_mapping_handles_leap_year_boundaries():
    assert temperature_date_for_record(2023, 1) == date(2023, 1, 1)
    assert temperature_date_for_record(2023, 365) == date(2023, 12, 31)
    assert temperature_date_for_record(2024, 60) == date(2024, 2, 29)
    assert temperature_date_for_record(2024, 366) == date(2024, 12, 31)
    with pytest.raises(ValueError, match="record_number"):
        temperature_date_for_record(2024, 367)


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


def test_nashik_temperature_grid_selection_uses_shared_nearest_grid_utility():
    point = select_temperature_grid_point(20.0112475, 73.7902364)
    assert (point.grid_latitude, point.grid_longitude) == (20.5, 73.5)
    assert point.distance_km > 0


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
