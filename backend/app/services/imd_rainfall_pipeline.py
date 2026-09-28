"""Read-only IMD 0.25-degree daily rainfall validation and point extraction."""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.historical_data import GridPoint, select_nearest_grid_point

_FILE_RE = re.compile(r"^RF25_ind(\d{4})_rfp25\.nc$", re.IGNORECASE)
_MONTHLY_CLIMO_RE = re.compile(r"_clm\.nc$", re.IGNORECASE)
_EXPECTED_LAT = (6.5, 38.5, 0.25, 129)
_EXPECTED_LON = (66.5, 100.0, 0.25, 135)


@dataclass
class RainfallFileReport:
    filename: str
    year: int
    provenance_status: str
    expected_records: int
    actual_records: int
    missing_rainfall_count: int
    duplicate_date_count: int
    missing_date_count: int
    invalid_coordinate_count: int
    unexpected_dimensions: list[str]
    coordinate_bounds: dict[str, float | int | None]
    date_start: str | None
    date_end: str | None
    requested_latitude: float
    requested_longitude: float
    selected_latitude: float | None
    selected_longitude: float | None
    selection_distance_km: float | None
    minimum_rainfall_mm: float | None
    maximum_rainfall_mm: float | None
    variable: str | None
    data_dimensions: list[str]
    units: str | None
    missing_markers: list[float]
    grid_resolution_degrees: float | None
    status: str
    issues: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace").strip("\x00 ")
    return str(value)


def _expected_days(year: int) -> int:
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days


def _dates_from_cf(offsets: Any, units_value: Any) -> list[date]:
    units = _text(units_value)
    match = re.fullmatch(r"\s*days\s+since\s+(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}:\d{2}))?\s*", units, re.I)
    if not match:
        raise ValueError(f"unsupported CF time units: {units!r}")
    base = datetime.fromisoformat(match.group(1) + ("T" + match.group(2) if match.group(2) else "T00:00:00"))
    return [(base + timedelta(days=float(value))).date() for value in offsets]


def validate_and_extract_rainfall_file(path: str | Path, latitude: float, longitude: float
                                       ) -> tuple[RainfallFileReport, list[dict[str, Any]]]:
    """Validate an annual 0.25-degree IMD NetCDF and extract its nearest point.

    Data is read only. Missing markers/non-finite rainfall are represented as
    None in extracted records; no interpolation, replacement, or raw write occurs.
    """
    path = Path(path)
    match = _FILE_RE.fullmatch(path.name)
    if not match or _MONTHLY_CLIMO_RE.search(path.name):
        raise ValueError(f"not a recognized annual IMD RF25 file: {path.name}")
    year = int(match.group(1))
    try:
        from scipy.io import netcdf_file
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("IMD rainfall extraction requires scipy and numpy") from exc

    issues: list[str] = []
    rows: list[dict[str, Any]] = []
    actual_records = 0
    missing_count = duplicates = missing_dates = invalid_coordinates = 0
    minimum: float | None = None
    maximum: float | None = None
    variable_name: str | None = None
    units: str | None = None
    markers: list[float] = []
    resolution: float | None = None
    bounds: dict[str, float | int | None] = {}
    dates: list[date] = []
    unexpected: list[str] = []
    data_dimensions: list[str] = []
    point: GridPoint | None = None

    with netcdf_file(path, "r", mmap=False) as nc:
        variables = {name.casefold(): name for name in nc.variables}
        lat_name = next((variables[n] for n in ("latitude", "lat") if n in variables), None)
        lon_name = next((variables[n] for n in ("longitude", "lon") if n in variables), None)
        time_name = next((variables[n] for n in ("time", "date") if n in variables), None)
        variable_name = next((variables[n] for n in ("rainfall", "rf", "rain") if n in variables), None)
        if not all((lat_name, lon_name, time_name, variable_name)):
            raise ValueError("NetCDF requires rainfall, time, latitude, and longitude variables")

        latitudes = nc.variables[lat_name][:].copy().reshape(-1)
        longitudes = nc.variables[lon_name][:].copy().reshape(-1)
        time_var = nc.variables[time_name]
        raw_dates = _dates_from_cf(time_var[:].copy().reshape(-1), getattr(time_var, "units", b""))
        dates = raw_dates
        data_var = nc.variables[variable_name]
        data_dims = tuple(d.casefold() for d in data_var.dimensions)
        data_dimensions = list(data_var.dimensions)
        axis_name_sets = ({"time", "date"}, {"latitude", "lat"}, {"longitude", "lon"})
        if len(data_dims) != 3 or any(sum(dim in alias for dim in data_dims) != 1 for alias in axis_name_sets):
            unexpected = list(data_var.dimensions)
            issues.append(f"unexpected rainfall dimensions: {data_var.dimensions}")
        else:
            allowed = set(data_dims)
            unexpected = sorted(d for d in nc.dimensions if d.casefold() not in allowed and nc.dimensions[d] is not None)
            if unexpected:
                issues.append(f"unexpected dimensions declared: {unexpected}")

        bounds = {
            "latitude_min": float(np.min(latitudes)) if latitudes.size else None,
            "latitude_max": float(np.max(latitudes)) if latitudes.size else None,
            "latitude_count": int(latitudes.size),
            "longitude_min": float(np.min(longitudes)) if longitudes.size else None,
            "longitude_max": float(np.max(longitudes)) if longitudes.size else None,
            "longitude_count": int(longitudes.size),
        }
        def coordinate_valid(values: Any, expected: tuple[float, float, float, int]) -> bool:
            start, end, step, count = expected
            return (values.size == count and np.all(np.isfinite(values))
                    and np.allclose(values, np.linspace(start, end, count), atol=1e-6, rtol=0))

        if not coordinate_valid(latitudes, _EXPECTED_LAT):
            issues.append("latitude coordinates do not match official 0.25-degree definition")
        if not coordinate_valid(longitudes, _EXPECTED_LON):
            issues.append("longitude coordinates do not match official 0.25-degree definition")
        invalid_latitude_values = int((~np.isfinite(latitudes) | (latitudes < -90) | (latitudes > 90)).sum())
        invalid_longitude_values = int((~np.isfinite(longitudes) | (longitudes < -180) | (longitudes > 180)).sum())
        invalid_coordinates = invalid_latitude_values + invalid_longitude_values
        if not coordinate_valid(latitudes, _EXPECTED_LAT) and not invalid_latitude_values:
            invalid_coordinates += 1
        if not coordinate_valid(longitudes, _EXPECTED_LON) and not invalid_longitude_values:
            invalid_coordinates += 1
        valid_latitudes = latitudes[np.isfinite(latitudes) & (latitudes >= -90) & (latitudes <= 90)]
        valid_longitudes = longitudes[np.isfinite(longitudes) & (longitudes >= -180) & (longitudes <= 180)]
        if not valid_latitudes.size or not valid_longitudes.size:
            raise ValueError("NetCDF contains no valid latitude/longitude coordinates for point selection")
        coordinate_pairs = [(float(y), float(x)) for y in valid_latitudes for x in valid_longitudes]
        point: GridPoint = select_nearest_grid_point(latitude, longitude, coordinate_pairs)
        if latitudes.size > 1:
            resolution = float(abs(latitudes[1] - latitudes[0]))

        attrs = getattr(data_var, "_attributes", {})
        units = _text(attrs.get("units", "")) or None
        if units and units.casefold() != "mm":
            issues.append(f"unexpected rainfall units: {units}")
        if not units:
            issues.append("rainfall units are missing")
        for key in ("_FillValue", "missing_value"):
            if key in attrs:
                marker = float(np.asarray(attrs[key]).reshape(-1)[0])
                if marker not in markers:
                    markers.append(marker)
        if not markers:
            issues.append("rainfall missing-value marker is absent")

        time_axis_for_count = next((i for i, d in enumerate(data_dims) if d in {"time", "date"}), None)
        actual_records = int(data_var.shape[time_axis_for_count]) if time_axis_for_count is not None else 0
        expected_records = _expected_days(year)
        if actual_records != expected_records or len(raw_dates) != expected_records:
            issues.append(f"expected {expected_records} daily records, found variable={actual_records}, time={len(raw_dates)}")
        if dates:
            counts = Counter(dates)
            duplicates = sum(count - 1 for count in counts.values() if count > 1)
            expected_dates = [date(year, 1, 1) + timedelta(days=i) for i in range(expected_records)]
            missing_dates = len(set(expected_dates) - set(dates))
            if dates[0] != expected_dates[0] or dates[-1] != expected_dates[-1] or missing_dates or duplicates:
                issues.append("date coordinates are not a unique complete calendar year")
        else:
            issues.append("time coordinate is empty")

        if len(data_dims) == 3 and not unexpected:
            selection: list[Any] = [slice(None)] * 3
            time_axis = next(i for i, d in enumerate(data_dims) if d in {"time", "date"})
            lat_axis = next(i for i, d in enumerate(data_dims) if d in {"latitude", "lat"})
            lon_axis = next(i for i, d in enumerate(data_dims) if d in {"longitude", "lon"})
            lat_index = int(np.abs(latitudes - point.grid_latitude).argmin())
            lon_index = int(np.abs(longitudes - point.grid_longitude).argmin())
            selection[lat_axis] = lat_index
            selection[lon_axis] = lon_index
            extracted = data_var[tuple(selection)].copy().reshape(-1)
            all_values = data_var[:].copy()
            valid = np.isfinite(all_values)
            for marker in markers:
                valid &= ~np.isclose(all_values, marker, atol=1e-6, rtol=0)
            missing_count = int(valid.size - valid.sum())
            if valid.any():
                minimum = float(np.min(all_values[valid]))
                maximum = float(np.max(all_values[valid]))
                if minimum < 0:
                    issues.append("negative rainfall values found")
            for day, value in zip(dates, extracted):
                number = float(value)
                rainfall = None if (not math.isfinite(number) or any(math.isclose(number, marker, abs_tol=1e-6) for marker in markers)) else number
                rows.append({"date": day.isoformat(), "latitude": point.grid_latitude,
                    "longitude": point.grid_longitude, "rainfall_mm": rainfall,
                    "source": "India Meteorological Department (IMD Pune)",
                    "dataset": "Daily Gridded Rainfall 0.25 degree",
                    "grid_resolution": 0.25})

    if actual_records <= 0:
        issues.append("empty rainfall data")
    provenance_status = "OFFICIAL_RANGE_1901_2024" if year <= 2024 else "UNVERIFIED_BEYOND_OFFICIAL_ARCHIVE_END_2024"
    status = "FAIL" if issues else "PASS"
    report = RainfallFileReport(path.name, year, provenance_status, _expected_days(year), actual_records,
        missing_count, duplicates, missing_dates, invalid_coordinates, unexpected, bounds,
        dates[0].isoformat() if dates else None, dates[-1].isoformat() if dates else None,
        latitude, longitude, point.grid_latitude if point else None, point.grid_longitude if point else None,
        round(point.distance_km, 3) if point else None,
        minimum, maximum, variable_name, data_dimensions, units, markers, resolution, status, issues)
    return report, rows


def extract_rainfall_directory(raw_dir: str | Path, processed_dir: str | Path,
                               validation_dir: str | Path, latitude: float, longitude: float
                               ) -> dict[str, Any]:
    """Extract all recognized annual files; put post-2024 files in a separate output."""
    raw_dir, processed_dir, validation_dir = Path(raw_dir), Path(processed_dir), Path(validation_dir)
    candidates = sorted(p for p in raw_dir.glob("*.nc") if _FILE_RE.fullmatch(p.name))
    if not candidates:
        raise FileNotFoundError(f"no annual IMD RF25 NetCDF files found in {raw_dir}")
    processed_dir.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)
    per_file_validation_dir = validation_dir / "imd_rainfall"
    per_file_validation_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    rows_by_status: dict[str, list[dict[str, Any]]] = {"verified_period": [], "provenance_unverified": []}
    all_dates: list[date] = []
    for path in candidates:
        report, rows = validate_and_extract_rainfall_file(path, latitude, longitude)
        reports.append(report.as_dict())
        (per_file_validation_dir / f"{path.stem}.validation.json").write_text(
            json.dumps(report.as_dict(), indent=2) + "\n", encoding="utf-8")
        target = "verified_period" if report.year <= 2024 else "provenance_unverified"
        rows_by_status[target].extend(rows)
        all_dates.extend(date.fromisoformat(row["date"]) for row in rows)
    duplicates_across_files = sorted(d.isoformat() for d, n in Counter(all_dates).items() if n > 1)
    for key, filename in (("verified_period", "imd_rainfall_daily_0.25deg.csv"),
                          ("provenance_unverified", "imd_rainfall_daily_0.25deg_2025_provenance_unverified.csv")):
        rows = rows_by_status[key]
        if rows:
            with (processed_dir / filename).open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "latitude", "longitude", "rainfall_mm", "source", "dataset", "grid_resolution"])
                writer.writeheader()
                writer.writerows(rows)
    validation_file = validation_dir / "imd_rainfall_0.25deg_validation.json"
    point_record = next(iter(rows_by_status["verified_period"] or rows_by_status["provenance_unverified"]), None)
    validation_file.write_text(json.dumps({
        "source": "India Meteorological Department (IMD Pune)",
        "reference": "https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html",
        "requested_coordinate": {"latitude": latitude, "longitude": longitude},
        "selection_method": "nearest supplied NetCDF lat/lon centers by haversine distance",
        "files": reports, "duplicate_dates_across_files": duplicates_across_files,
        "processed_records_official_range": len(rows_by_status["verified_period"]),
        "processed_records_provenance_unverified": len(rows_by_status["provenance_unverified"]),
        "selected_grid_point": ({"latitude": point_record["latitude"], "longitude": point_record["longitude"],
            "distance_km": reports[0]["selection_distance_km"]} if point_record else None),
    }, indent=2) + "\n", encoding="utf-8")
    return {"reports": reports, "duplicate_dates_across_files": duplicates_across_files,
            "processed_records_official_range": len(rows_by_status["verified_period"]),
            "processed_records_provenance_unverified": len(rows_by_status["provenance_unverified"]),
            "validation_report": str(validation_file)}
