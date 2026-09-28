"""Fail-closed validation foundation for IMD annual Tmax/Tmin GRD files.

This module inspects filenames and byte lengths only. It never decodes GRD
values while endian, floating-point representation, header layout, and raw
cell-to-coordinate mapping remain unverified.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.services.historical_data import NormalizedHistoricalRecord, nearest_grid_point
from app.services.imd_grd_inspection import (
    LATITUDE_FIRST, LATITUDE_STEP, LONGITUDE_FIRST, LONGITUDE_STEP,
    GRID_COLUMNS, GRID_ROWS, UNDEFINED_VALUE, expected_daily_records,
    inspect_imd_temperature_grd,
)

SOURCE = "India Meteorological Department (IMD Pune)"
DATASETS = {
    "tmax": "Daily Gridded Maximum Temperature (1 degree)",
    "tmin": "Daily Gridded Minimum Temperature (1 degree)",
}
REFERENCE_URLS = {
    "tmax": "https://imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html",
    "tmin": "https://imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html",
}
LOCAL_TEMPERATURE_PDF = "data/raw/imd_temperature/IMD-DSP_temp.pdf"
UNRESOLVED_FORMAT_FIELDS = (
    "byte_order", "explicit_float_representation (for example, IEEE-754)",
    "raw_IJ_to_latitude_longitude_mapping", "header_or_prefix_structure",
)
_FILE_PATTERN = re.compile(r"^(Maxtemp_MaxT|Mintemp_MinT)_(\d{4})\.GRD$", re.IGNORECASE)


class TemperatureDecodeBlocked(RuntimeError):
    """Raised before reading values when GRD decoding semantics are unverified."""


def missing_years(years: list[int] | tuple[int, ...]) -> list[int]:
    """Return gaps between the lowest and highest observed filename years."""
    unique = sorted(set(years))
    return [year for year in range(unique[0], unique[-1] + 1) if year not in unique] if unique else []


def expected_logical_temperature_coordinates():
    """Yield documented logical grid centers; this does not map raw file indices."""
    for row in range(GRID_ROWS):
        for column in range(GRID_COLUMNS):
            yield (LATITUDE_FIRST + row * LATITUDE_STEP,
                   LONGITUDE_FIRST + column * LONGITUDE_STEP)


def select_temperature_grid_point(latitude: float, longitude: float):
    """Use the existing generic haversine selector against the documented 1-degree grid."""
    return nearest_grid_point(latitude, longitude, "tmax")


def temperature_value_to_nullable(value: float | int | None) -> float | None:
    """Normalize an already decoded value using IMD's documented 99.9 sentinel."""
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or math.isclose(number, UNDEFINED_VALUE, abs_tol=1e-6):
        return None
    return number


def make_normalized_temperature_record(*, observation_date: date, latitude: float,
                                      longitude: float, dataset_type: str,
                                      value: float | int | None) -> NormalizedHistoricalRecord:
    """Create one nullable native-grid normalized record from a verified value.

    This schema helper is not an extractor: callers must already have a
    scientifically verified value-to-cell/date mapping.
    """
    kind = dataset_type.casefold()
    if kind not in DATASETS:
        raise ValueError("dataset_type must be 'tmax' or 'tmin'")
    point = select_temperature_grid_point(latitude, longitude)
    return NormalizedHistoricalRecord(
        date=observation_date,
        latitude=point.grid_latitude,
        longitude=point.grid_longitude,
        rainfall_mm=None,
        temp_max_c=temperature_value_to_nullable(value) if kind == "tmax" else None,
        temp_min_c=temperature_value_to_nullable(value) if kind == "tmin" else None,
        source=SOURCE,
        dataset=DATASETS[kind],
        grid_resolution=1.0,
    )


def read_temperature_grd(path: str | Path, latitude: float, longitude: float) -> list[NormalizedHistoricalRecord]:
    """Validate structure and fail before decoding until official format evidence is complete."""
    path = Path(path)
    structural = inspect_imd_temperature_grd(path)
    if not structural["size_matches_documented_layout"]:
        raise ValueError(
            f"GRD structural validation failed for {path.name}: expected "
            f"{structural['expected_size_bytes']} bytes, found {structural['actual_size_bytes']}"
        )
    select_temperature_grid_point(latitude, longitude)  # validate generic coordinates/coverage
    raise TemperatureDecodeBlocked(
        f"Temperature decoding blocked for {path.name}; no GRD values were read. "
        f"Unverified required format fields: {', '.join(UNRESOLVED_FORMAT_FIELDS)}. "
        "Annual date mapping is documented as a sequential daily archive convention, "
        "but the payload cannot be tied to dates/cells without the missing format details."
    )


def _provenance_status(year: int) -> str:
    if 1951 <= year <= 2024:
        return "FILENAME_WITHIN_PUBLISHED_PRODUCT_PERIOD_SOURCE_CHAIN_UNVERIFIED"
    return "OUTSIDE_PUBLISHED_PRODUCT_PERIOD_SOURCE_CHAIN_UNVERIFIED"


def audit_temperature_directory(raw_dir: str | Path) -> dict[str, Any]:
    """Inventory all recognized annual GRDs and report structural/date coverage only."""
    raw_dir = Path(raw_dir)
    files: list[dict[str, Any]] = []
    for path in sorted(raw_dir.iterdir()):
        if not path.is_file() or not _FILE_PATTERN.fullmatch(path.name):
            continue
        item = inspect_imd_temperature_grd(path)
        year = item["year_from_filename"]
        item.update({
            "filename": path.name,
            "expected_date_start_by_archive_convention": f"{year:04d}-01-01",
            "expected_date_end_by_archive_convention": f"{year:04d}-12-31",
            "date_continuity_status": "EXPECTED_FROM_FILENAME_AND_OFFICIAL_DAILY_SEQUENTIAL_CONVENTION_NOT_PAYLOAD_VERIFIED",
            "structural_status": "PASS" if item["size_matches_documented_layout"] else "FAIL",
            "value_quality_status": "BLOCKED_NOT_DECODED",
            "missing_value_count": None,
            "temperature_range_check": "NOT_RUN_GRD_VALUES_NOT_DECODED",
            "provenance_status": _provenance_status(year),
            "source": SOURCE,
            "dataset": DATASETS[item["product"]],
            "resolution_degrees": 1.0,
            "reference_url": REFERENCE_URLS[item["product"]],
        })
        files.append(item)

    by_kind: dict[str, list[dict[str, Any]]] = {
        kind: sorted((item for item in files if item["product"] == kind), key=lambda row: row["year_from_filename"])
        for kind in DATASETS
    }
    products: dict[str, Any] = {}
    for kind, rows in by_kind.items():
        years = [row["year_from_filename"] for row in rows]
        products[kind] = {
            "dataset": DATASETS[kind], "reference_url": REFERENCE_URLS[kind],
            "detected_years": years, "detected_year_range": [min(years), max(years)] if years else None,
            "missing_years_within_detected_range": missing_years(years),
            "annual_file_count": len(rows),
            "structural_pass_count": sum(row["structural_status"] == "PASS" for row in rows),
            "structural_failures": [row["filename"] for row in rows if row["structural_status"] == "FAIL"],
        }

    years_by_kind = {kind: set(products[kind]["detected_years"]) for kind in DATASETS}
    overlap_years = sorted(years_by_kind["tmax"] & years_by_kind["tmin"])
    overlap_calendar_days = sum(expected_daily_records(year) for year in overlap_years)
    structurally_aligned = bool(overlap_years) and all(
        next(row for row in by_kind["tmax"] if row["year_from_filename"] == year)["size_matches_documented_layout"]
        and next(row for row in by_kind["tmin"] if row["year_from_filename"] == year)["size_matches_documented_layout"]
        for year in overlap_years
    )
    structure_failures = [row["filename"] for row in files if row["structural_status"] == "FAIL"]
    return {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "inspection_mode": "read_only_file_names_and_file_sizes_only",
        "raw_files_modified": False,
        "decoder_status": "BLOCKED_FORMAT_FIELDS_UNVERIFIED",
        "files_inspected": len(files),
        "total_size_bytes": sum(row["actual_size_bytes"] for row in files),
        "format_metadata": {
            "official_product_period": "1951-2024",
            "grid_dimensions": [GRID_ROWS, GRID_COLUMNS], "grid_resolution_degrees": 1.0,
            "logical_latitude_centers": [LATITUDE_FIRST, LATITUDE_FIRST + (GRID_ROWS - 1) * LATITUDE_STEP],
            "logical_longitude_centers": [LONGITUDE_FIRST, LONGITUDE_FIRST + (GRID_COLUMNS - 1) * LONGITUDE_STEP],
            "logical_axis_directions": {"latitude": "ascending", "longitude": "ascending"},
            "daily_records": "Sequential direct-access records; archive sample convention starts 1 January and includes leap days.",
            "bytes_per_value": 4, "float32_width_supported": True,
            "units": "degrees Celsius", "missing_value_marker": UNDEFINED_VALUE,
            "scale_offset": "No scale/offset documented; sample readers use direct values.",
            "byte_order": "UNVERIFIED",
            "explicit_float_representation": "UNVERIFIED",
            "raw_ij_to_geographic_mapping": "UNVERIFIED",
            "header_or_prefix_structure": "UNVERIFIED",
            "unverified_required_for_decode": list(UNRESOLVED_FORMAT_FIELDS),
            "header_bytes": "UNKNOWN",
            "local_pdf_finding": {
                "file": LOCAL_TEMPERATURE_PDF,
                "title": "All India Series Monthly and Seasonal Mean Temperature",
                "relevance": "A rendered IMD-DSP statistical table; it does not document the daily GRD binary layout.",
            },
        },
        "products": products,
        "tmax_tmin_overlap": {
            "years_by_filename": overlap_years,
            "expected_calendar_days_by_annual_convention": overlap_calendar_days,
            "structural_date_alignment": "PASS" if structurally_aligned else "FAIL",
            "measurement_level_tmin_le_tmax_check": "NOT_RUN_GRD_VALUES_NOT_DECODED",
            "date_level_alignment_basis": "same annual filename year and expected 365/366-day size only; dates are not embedded",
        },
        "structure_status": "FAIL" if structure_failures or not files else "PASS",
        "decode_status": "BLOCKED_FORMAT_FIELDS_UNVERIFIED",
        "structure_failures": structure_failures,
        "files": files,
    }


def write_temperature_validation_report(raw_dir: str | Path | None = None,
                                         output_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    raw_dir = Path(raw_dir) if raw_dir else root / "data" / "raw" / "imd_temperature"
    output_path = Path(output_path) if output_path else root / "data" / "validation" / "imd_temperature_grd_validation.json"
    report = audit_temperature_directory(raw_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(write_temperature_validation_report(args.raw_dir, args.output), indent=2))
