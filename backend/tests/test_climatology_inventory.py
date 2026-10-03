from pathlib import Path

import pytest

from app.services.climatology_inventory import build_climatology_inventory, inspect_climatology_file


def _write_metadata_fixture(path: Path):
    scipy_io = pytest.importorskip("scipy.io")
    with scipy_io.netcdf_file(path, "w") as nc:
        nc.createDimension("lat", 2)
        nc.createDimension("lon", 3)
        lat = nc.createVariable("lat", "d", ("lat",))
        lon = nc.createVariable("lon", "d", ("lon",))
        data = nc.createVariable("rf", "d", ("lat", "lon"))
        lat[:] = [20.75, 21.0]
        lon[:] = [74.5, 74.75, 75.0]
        data.units = b"mm"
        data.missing_value = -999.0
        data.month = 0
        data.time_op_ncl = b"Climatology: 30 years"
        data[:] = [[1, 2, 3], [4, 5, 6]]


def test_netcdf_metadata_parser_reads_grid_metadata_without_assuming_period(tmp_path):
    path = tmp_path / "rf_p25_jan_clm.nc"
    _write_metadata_fixture(path)
    item = inspect_climatology_file(path, tmp_path)
    assert item["parameter"] == "rainfall"
    assert item["month"] == "jan" and item["month_attribute_matches_filename"]
    assert item["units"] == "mm"
    assert item["resolution_degrees"] == pytest.approx(.25)
    assert item["latitude"]["count"] == 2
    assert item["missing_value"] == -999
    assert item["climatology_period"].startswith("1991-2020")


def test_inventory_reports_month_coverage_and_duplicate_names(tmp_path):
    folder = tmp_path / "rainfall"
    folder.mkdir()
    _write_metadata_fixture(folder / "rf_p25_jan_clm.nc")
    inventory = build_climatology_inventory(tmp_path)
    assert inventory["file_count"] == 1
    group = inventory["month_completeness"]["rainfall (0.25 degree)"]
    assert group["available_months"] == ["jan"]
    assert len(group["missing_months"]) == 11


def test_repository_climatology_month_coverage_is_current():
    root = Path(__file__).resolve().parents[2] / "data" / "raw" / "imd_climatology"
    inventory = build_climatology_inventory(root)
    assert inventory["file_count"] == 60
    assert all(not group["missing_months"] for group in inventory["month_completeness"].values())
    assert "1991-2020" in inventory["period_note"]
