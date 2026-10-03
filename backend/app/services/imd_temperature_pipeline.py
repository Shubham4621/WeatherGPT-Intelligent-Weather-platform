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
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

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
FORMAT_CRITICAL_FIELDS = (
    "numeric_representation", "byte_order", "raw_ij_mapping", "record_framing",
)
UNRESOLVED_FORMAT_FIELDS = FORMAT_CRITICAL_FIELDS
_FILE_PATTERN = re.compile(r"^(Maxtemp_MaxT|Mintemp_MinT)_(\d{4})\.GRD$", re.IGNORECASE)


class TemperatureDecodeBlocked(RuntimeError):
    """Raised before reading values when GRD decoding is not safe to enable."""

    def __init__(self, message: str, *, reason_code: str = "BLOCKED_FORMAT_FIELDS_UNVERIFIED",
                 details: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason_code = reason_code
        self.details = details or {}


@dataclass(frozen=True)
class RawIJMapping:
    """Explicit raw I/J axis mapping; None is retained until IMD confirms it."""

    i_axis: Literal["latitude", "longitude"]
    i_direction: Literal["ascending", "descending"]
    j_axis: Literal["latitude", "longitude"]
    j_direction: Literal["ascending", "descending"]
    i_index_origin: Literal[0, 1] | None = None
    j_index_origin: Literal[0, 1] | None = None
    fastest_index: Literal["i", "j"] | None = None


@dataclass(frozen=True)
class TemperatureFormatEvidence:
    """Authoritative evidence attached to one configured decoder property."""

    field: str
    authority: Literal["IMD"]
    source: str
    statement: str


@dataclass(frozen=True)
class TemperatureGrdFormatSpec:
    """Known IMD layout plus explicitly unset encoding properties.

    The defaults below record only established metadata. In particular, they do
    not infer a numeric representation, byte order, or mapping from raw I/J to
    geographic coordinates.
    """

    numeric_representation: str | None = None
    byte_order: Literal["little", "big"] | None = None
    raw_ij_mapping: RawIJMapping | None = None
    record_framing: str | None = None
    field_evidence: tuple[TemperatureFormatEvidence, ...] = ()
    grid_rows: int = GRID_ROWS
    grid_columns: int = GRID_COLUMNS
    bytes_per_value: int = 4
    units: Literal["°C"] = "°C"
    missing_marker: float = UNDEFINED_VALUE
    record_date_mapping: Literal["jan1_then_sequential_days"] = "jan1_then_sequential_days"


# This is the production specification. Its unresolved fields must remain None
# until authoritative IMD clarification and field-specific evidence are added.
IMD_TEMPERATURE_FORMAT = TemperatureGrdFormatSpec()


def validate_temperature_format_spec(spec: TemperatureGrdFormatSpec) -> None:
    """Validate an explicitly supplied format configuration, without decoding.

    A successful result means the values are internally consistent. It does
    not establish that the values describe IMD files or authorize file reads.
    """
    problems: list[str] = []
    if not isinstance(spec, TemperatureGrdFormatSpec):
        raise ValueError("spec must be a TemperatureGrdFormatSpec")
    if (spec.numeric_representation is not None
            and (not isinstance(spec.numeric_representation, str) or not spec.numeric_representation.strip())):
        problems.append("numeric_representation must be a non-empty explicit string when supplied")
    if spec.byte_order is not None and spec.byte_order not in ("little", "big"):
        problems.append("byte_order must be 'little' or 'big'")
    mapping = spec.raw_ij_mapping
    if mapping is not None and not isinstance(mapping, RawIJMapping):
        problems.append("raw_ij_mapping must be a RawIJMapping")
    elif mapping is not None and (mapping.i_axis == mapping.j_axis
          or mapping.i_axis not in ("latitude", "longitude")
          or mapping.j_axis not in ("latitude", "longitude")
          or mapping.i_direction not in ("ascending", "descending")
          or mapping.j_direction not in ("ascending", "descending")
          or mapping.i_index_origin not in (0, 1)
          or mapping.j_index_origin not in (0, 1)
          or mapping.fastest_index not in ("i", "j")):
        problems.append(
            "raw_ij_mapping must define distinct axes, directions, index origins, and storage-fastest index"
        )
    if spec.record_framing is not None and (
            not isinstance(spec.record_framing, str) or not spec.record_framing.strip()):
        problems.append("record_framing must be a non-empty explicit string when supplied")
    if spec.grid_rows != GRID_ROWS or spec.grid_columns != GRID_COLUMNS:
        problems.append("grid dimensions must match the documented 31 by 31 layout")
    if spec.bytes_per_value != 4:
        problems.append("bytes_per_value must match the documented four-byte value width")
    if spec.units != "°C":
        problems.append("units must match the documented Celsius unit")
    if (not isinstance(spec.missing_marker, (int, float))
            or not math.isfinite(spec.missing_marker)
            or not math.isclose(spec.missing_marker, UNDEFINED_VALUE)):
        problems.append("missing_marker must match the documented 99.9 sentinel")
    if spec.record_date_mapping != "jan1_then_sequential_days":
        problems.append("record_date_mapping must match the documented annual daily sequence")
    seen: set[str] = set()
    if not isinstance(spec.field_evidence, tuple):
        problems.append("field_evidence must be a tuple")
    for evidence in spec.field_evidence if isinstance(spec.field_evidence, tuple) else ():
        if (not isinstance(evidence, TemperatureFormatEvidence)
                or evidence.field not in FORMAT_CRITICAL_FIELDS or evidence.field in seen
                or evidence.authority != "IMD" or not evidence.source.strip()
                or not evidence.statement.strip()):
            problems.append("field_evidence entries must uniquely identify a critical field and cite evidence")
            break
        seen.add(evidence.field)
    configured_by_field = {
        "numeric_representation": spec.numeric_representation is not None,
        "byte_order": spec.byte_order is not None,
        "raw_ij_mapping": spec.raw_ij_mapping is not None,
        "record_framing": spec.record_framing is not None,
    }
    if any(not configured_by_field[field] for field in seen):
        problems.append("field_evidence cannot be supplied for an unset format field")
    if problems:
        raise ValueError("; ".join(problems))


def temperature_format_blockers(spec: TemperatureGrdFormatSpec = IMD_TEMPERATURE_FORMAT) -> list[str]:
    """Return unset or unsupported-by-evidence critical fields, without IO."""
    validate_temperature_format_spec(spec)
    blockers: list[str] = []
    if spec.numeric_representation is None or not spec.numeric_representation.strip():
        blockers.append("numeric_representation")
    if spec.byte_order is None:
        blockers.append("byte_order")
    if spec.raw_ij_mapping is None:
        blockers.append("raw_ij_mapping")
    if spec.record_framing is None or not spec.record_framing.strip():
        blockers.append("record_framing")
    evidenced = {item.field for item in spec.field_evidence}
    for field in FORMAT_CRITICAL_FIELDS:
        configured = {
            "numeric_representation": bool(spec.numeric_representation and spec.numeric_representation.strip()),
            "byte_order": spec.byte_order is not None,
            "raw_ij_mapping": spec.raw_ij_mapping is not None,
            "record_framing": bool(spec.record_framing and spec.record_framing.strip()),
        }[field]
        if configured and field not in evidenced:
            blockers.append(f"{field}.authoritative_evidence")
    return blockers


def temperature_date_for_record(year: int, record_number: int) -> date:
    """Map one-based daily record number to the documented annual date sequence."""
    record_count = expected_daily_records(year)
    if not 1 <= record_number <= record_count:
        raise ValueError(f"record_number must be between 1 and {record_count} for {year}")
    return date(year, 1, 1) + timedelta(days=record_number - 1)


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


def read_temperature_grd(path: str | Path, latitude: float, longitude: float,
                         format_spec: TemperatureGrdFormatSpec = IMD_TEMPERATURE_FORMAT) -> list[NormalizedHistoricalRecord]:
    """Validate configuration/structure and fail before any payload read.

    This preparation phase intentionally has no binary unpacker. A complete
    configuration is necessary but not sufficient: field-specific IMD evidence
    is required, and successful authorization still stops until a decoder is
    implemented and separately validated.
    """
    path = Path(path)
    try:
        validate_temperature_format_spec(format_spec)
    except (TypeError, ValueError, AttributeError) as exc:
        raise TemperatureDecodeBlocked(
            f"Temperature decoding blocked for {path.name}; format configuration is invalid: {exc}",
            reason_code="BLOCKED_FORMAT_CONFIGURATION_INVALID",
            details={"configuration_error": str(exc)},
        ) from exc
    structural = inspect_imd_temperature_grd(path)
    if not structural["size_matches_documented_layout"]:
        raise ValueError(
            f"GRD structural validation failed for {path.name}: expected "
            f"{structural['expected_size_bytes']} bytes, found {structural['actual_size_bytes']}"
        )
    select_temperature_grid_point(latitude, longitude)  # validate generic coordinates/coverage
    blockers = temperature_format_blockers(format_spec)
    if blockers:
        raise TemperatureDecodeBlocked(
            f"Temperature decoding blocked for {path.name}; no GRD values were read. "
            f"Unverified required format fields: {', '.join(blockers)}.",
            reason_code="BLOCKED_FORMAT_FIELDS_UNVERIFIED",
            details={"unverified_fields": blockers},
        )
    raise TemperatureDecodeBlocked(
        f"Temperature decoding blocked for {path.name}; configuration is complete, "
        "but the payload decoder is intentionally not implemented in this preparation phase.",
        reason_code="BLOCKED_DECODER_NOT_IMPLEMENTED",
        details={"payload_read": False},
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
            "bytes_per_value": 4,
            "units": "degrees Celsius", "missing_value_marker": UNDEFINED_VALUE,
            "scale_offset": "No scale/offset documented; sample readers use direct values.",
            "byte_order": "UNVERIFIED",
            "numeric_representation": "UNVERIFIED",
            "explicit_float_representation": "UNVERIFIED",
            "raw_ij_to_geographic_mapping": "UNVERIFIED",
            "record_framing": "UNVERIFIED",
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
