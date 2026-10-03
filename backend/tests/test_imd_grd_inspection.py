from app.services.imd_grd_inspection import (
    expected_daily_records,
    expected_record_bytes,
    inspect_imd_temperature_grd,
)


def test_record_size_and_calendar_day_counts_match_imd_layout():
    assert expected_record_bytes() == 31 * 31 * 4 == 3844
    assert expected_daily_records(2023) == 365
    assert expected_daily_records(2024) == 366
    assert 365 * expected_record_bytes() == 1_403_060
    assert 366 * expected_record_bytes() == 1_406_904


def test_inspection_reports_valid_file_size_and_unresolved_encoding_without_decoding(tmp_path):
    path = tmp_path / "Maxtemp_MaxT_2024.GRD"
    # Length-only fixture: this test checks structure, not fabricated weather values.
    with path.open("wb") as handle:
        handle.truncate(366 * 3844)
    report = inspect_imd_temperature_grd(path)
    assert report["size_matches_documented_layout"] is True
    assert report["expected_daily_records"] == 366
    assert report["grid_dimensions"] == [31, 31]
    assert report["four_byte_value_width_documented"] is True
    assert report["values_decoded"] is False
    assert report["byte_order"] == "UNVERIFIED"
    assert report["raw_ij_to_geographic_axis_mapping"] == "UNVERIFIED"
    assert report["record_1_date_by_archive_convention"] == "2024-01-01"


def test_inspection_flags_size_mismatch_and_keeps_logical_axes_separate_from_raw_indices(tmp_path):
    path = tmp_path / "Mintemp_MinT_2023.GRD"
    path.write_bytes(b"")
    report = inspect_imd_temperature_grd(path)
    assert report["size_matches_documented_layout"] is False
    assert report["logical_latitude_axis"]["direction"] == "ascending"
    assert report["logical_longitude_axis"]["direction"] == "ascending"
    assert report["raw_ij_to_geographic_axis_mapping"] == "UNVERIFIED"
    assert "Celsius" in report["units"]

