"""Read-only structural validation for annual IMD 1-degree temperature GRDs.

This module intentionally does not decode values. IMD's public examples specify
4-byte C/Fortran floats and the grid, but do not specify byte order or explicitly
tie the sample's I/J indices to the geographic axes.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

GRID_ROWS = 31
GRID_COLUMNS = 31
BYTES_PER_VALUE = 4
LATITUDE_FIRST = 7.5
LATITUDE_STEP = 1.0
LONGITUDE_FIRST = 67.5
LONGITUDE_STEP = 1.0
UNDEFINED_VALUE = 99.9

_FILENAMES = {
    "tmax": re.compile(r"^Maxtemp_MaxT_(\d{4})\.GRD$", re.IGNORECASE),
    "tmin": re.compile(r"^Mintemp_MinT_(\d{4})\.GRD$", re.IGNORECASE),
}


def expected_daily_records(year: int) -> int:
    """Number of calendar days for an annual file (including leap day)."""
    if not 1 <= year < 9999:
        raise ValueError("year must be between 1 and 9998")
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days


def expected_record_bytes(*, rows: int = GRID_ROWS, columns: int = GRID_COLUMNS,
                          bytes_per_value: int = BYTES_PER_VALUE) -> int:
    if min(rows, columns, bytes_per_value) <= 0:
        raise ValueError("grid dimensions and bytes_per_value must be positive")
    return rows * columns * bytes_per_value


def inspect_imd_temperature_grd(path: str | Path) -> dict[str, Any]:
    """Report file-size/layout checks and unresolved decode assumptions, read-only."""
    path = Path(path)
    product = next((kind for kind, pattern in _FILENAMES.items() if pattern.fullmatch(path.name)), None)
    if product is None:
        raise ValueError(f"unrecognized IMD Tmax/Tmin annual GRD filename: {path.name}")
    match = _FILENAMES[product].fullmatch(path.name)
    assert match is not None
    year = int(match.group(1))
    records = expected_daily_records(year)
    record_bytes = expected_record_bytes()
    expected_size = records * record_bytes
    size = path.stat().st_size
    return {
        "path": str(path), "product": product, "year_from_filename": year,
        "actual_size_bytes": size, "expected_size_bytes": expected_size,
        "size_matches_documented_layout": size == expected_size,
        "expected_daily_records": records, "record_bytes": record_bytes,
        "grid_dimensions": [GRID_ROWS, GRID_COLUMNS], "bytes_per_value": BYTES_PER_VALUE,
        "float32_width_supported_by_documented_record": True,
        "byte_order": "UNVERIFIED", "ieee_754_representation": "UNVERIFIED",
        "date_mapping": "Daily sequential records; official sample descriptor starts 1 Jan at 1-day increments; exact per-file payload was not decoded.",
        "record_1_date_by_archive_convention": f"{year:04d}-01-01",
        "logical_longitude_axis": {"first_center": LONGITUDE_FIRST, "last_center": LONGITUDE_FIRST + (GRID_COLUMNS - 1) * LONGITUDE_STEP,
                                   "step_degrees": LONGITUDE_STEP, "direction": "ascending"},
        "logical_latitude_axis": {"first_center": LATITUDE_FIRST, "last_center": LATITUDE_FIRST + (GRID_ROWS - 1) * LATITUDE_STEP,
                                  "step_degrees": LATITUDE_STEP, "direction": "ascending"},
        "raw_ij_to_geographic_axis_mapping": "UNVERIFIED",
        "units": "degrees Celsius (official IMD annual 1-degree daily Tmax/Tmin archive documentation)",
        "scale_offset": "No scale/offset is documented; examples read/write float values directly.",
        "undefined_value": UNDEFINED_VALUE,
        "values_decoded": False,
    }
