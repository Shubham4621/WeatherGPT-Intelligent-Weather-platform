"""IMD historical grid metadata, extraction and validation helpers.

This module never downloads data. Readers only open paths explicitly supplied by
the caller, and binary grid decoding requires the grid layout to be provided.
"""
from __future__ import annotations

import csv
import math
import re
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field


RAIN_URL = "https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_NetCDF.html"
TMAX_URL = "https://www.imdpune.gov.in/cmpg/Griddata/Max_1_Bin.html"
TMIN_URL = "https://www.imdpune.gov.in/cmpg/Griddata/Min_1_Bin.html"


@dataclass(frozen=True)
class GridDatasetMetadata:
    source: str
    dataset: str
    variable: str
    resolution: float
    start_year: int
    end_year: int
    units: str
    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float
    missing_values: tuple[float, ...]
    reference_url: str
    format: str
    rows: int
    columns: int
    time_step_days: int = 1

    def as_dict(self) -> dict[str, Any]:
        value = dict(self.__dict__)
        value["missing_values"] = list(self.missing_values)
        return value


IMD_DATASETS: dict[str, GridDatasetMetadata] = {
    "rainfall": GridDatasetMetadata("India Meteorological Department (IMD Pune)", "Daily Gridded Rainfall", "rainfall_mm", .25, 1901, 2024, "mm", 6.5, 38.5, 66.5, 100.0, (-999.0,), RAIN_URL, "NetCDF or IMD binary grid", 129, 135),
    "tmax": GridDatasetMetadata("India Meteorological Department (IMD Pune)", "Daily Gridded Maximum Temperature", "temp_max_c", 1.0, 1951, 2024, "°C", 7.5, 37.5, 67.5, 97.5, (99.9, -999.0), TMAX_URL, "IMD direct-access binary grid", 31, 31),
    "tmin": GridDatasetMetadata("India Meteorological Department (IMD Pune)", "Daily Gridded Minimum Temperature", "temp_min_c", 1.0, 1951, 2024, "°C", 7.5, 37.5, 67.5, 97.5, (99.9, -999.0), TMIN_URL, "IMD direct-access binary grid", 31, 31),
}


class NormalizedHistoricalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    rainfall_mm: float | None = None
    temp_max_c: float | None = None
    temp_min_c: float | None = None
    source: str
    dataset: str
    grid_resolution: float = Field(gt=0)


class ValidationReport(BaseModel):
    records: int
    date_start: date | None = None
    date_end: date | None = None
    missing_rainfall: int = 0
    missing_tmax: int = 0
    missing_tmin: int = 0
    duplicate_dates: list[str] = Field(default_factory=list)
    invalid_values: list[str] = Field(default_factory=list)
    date_gaps: list[str] = Field(default_factory=list)
    coordinate: dict[str, float] | None = None
    source: str | None = None
    status: str = "PASS"


@dataclass(frozen=True)
class GridPoint:
    requested_latitude: float
    requested_longitude: float
    grid_latitude: float
    grid_longitude: float
    distance_km: float

    # Compatibility properties for existing extractors.
    @property
    def latitude(self) -> float:
        return self.grid_latitude

    @property
    def longitude(self) -> float:
        return self.grid_longitude


def validate_metadata(metadata: GridDatasetMetadata) -> list[str]:
    problems: list[str] = []
    if not metadata.source.strip() or not metadata.dataset.strip() or not metadata.variable.strip():
        problems.append("source, dataset and variable are required")
    if metadata.start_year < 1800 or metadata.end_year < metadata.start_year:
        problems.append("invalid expected time range")
    if metadata.resolution <= 0 or metadata.rows <= 0 or metadata.columns <= 0:
        problems.append("resolution and grid dimensions must be positive")
    if not metadata.reference_url.startswith("https://"):
        problems.append("reference_url must use HTTPS")
    if metadata.min_latitude > metadata.max_latitude or metadata.min_longitude > metadata.max_longitude:
        problems.append("invalid coordinate bounds")
    return problems


def select_nearest_grid_point(latitude: float, longitude: float,
                              dataset_coordinates: Iterable[tuple[float, float]]) -> GridPoint:
    """Select the closest supplied (latitude, longitude) coordinate by haversine distance."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("coordinates are outside valid latitude/longitude bounds")
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("coordinates must be finite numbers")
    candidates = list(dataset_coordinates)
    if not candidates:
        raise ValueError("dataset_coordinates must contain at least one coordinate")
    for candidate_latitude, candidate_longitude in candidates:
        if (not math.isfinite(candidate_latitude) or not math.isfinite(candidate_longitude)
                or not -90 <= candidate_latitude <= 90 or not -180 <= candidate_longitude <= 180):
            raise ValueError("dataset coordinates must be finite latitude/longitude pairs")
    earth_radius_km = 6371.0088

    def distance(candidate: tuple[float, float]) -> float:
        candidate_latitude, candidate_longitude = candidate
        lat1, lat2 = math.radians(latitude), math.radians(candidate_latitude)
        delta_lat = lat2 - lat1
        delta_lon = math.radians(candidate_longitude - longitude)
        haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
        return 2 * earth_radius_km * math.asin(math.sqrt(min(1.0, haversine)))

    selected_latitude, selected_longitude = min(candidates, key=distance)
    return GridPoint(latitude, longitude, selected_latitude, selected_longitude,
                     distance((selected_latitude, selected_longitude)))


def _ensure_imd_coverage(latitude: float, longitude: float, latitudes: Any, longitudes: Any,
                         resolution: float, dataset_type: str) -> None:
    half_cell = resolution / 2
    if (latitude < float(min(latitudes)) - half_cell or latitude > float(max(latitudes)) + half_cell
            or longitude < float(min(longitudes)) - half_cell or longitude > float(max(longitudes)) + half_cell):
        raise ValueError(f"coordinates fall outside the {dataset_type} grid coverage")


def nearest_grid_point(latitude: float, longitude: float, dataset_type: str) -> GridPoint:
    """Select from an IMD grid catalog; arbitrary coordinates are supported."""
    try:
        metadata = IMD_DATASETS[dataset_type.lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported IMD grid dataset: {dataset_type}") from exc
    half_cell = metadata.resolution / 2
    if (latitude < metadata.min_latitude - half_cell or latitude > metadata.max_latitude + half_cell
            or longitude < metadata.min_longitude - half_cell or longitude > metadata.max_longitude + half_cell):
        raise ValueError(f"coordinates fall outside the {dataset_type} grid coverage")
    coordinates = ((metadata.min_latitude + i * metadata.resolution,
                    metadata.min_longitude + j * metadata.resolution)
                   for i in range(metadata.rows) for j in range(metadata.columns))
    return select_nearest_grid_point(latitude, longitude, coordinates)


def normalize_missing(value: float | int | None, dataset_type: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    metadata = IMD_DATASETS[dataset_type.lower()]
    if not math.isfinite(number) or any(math.isclose(number, marker, abs_tol=1e-6) for marker in metadata.missing_values):
        return None
    return number


def expected_dates(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def validate_records(records: list[NormalizedHistoricalRecord], *, expected_start: date | None = None,
                     expected_end: date | None = None) -> ValidationReport:
    issues: list[str] = []
    if not records:
        issues.append("empty dataset")
    ordered = sorted(records, key=lambda row: row.date)
    dates = [row.date for row in ordered]
    series_key = lambda row: (row.dataset, round(row.latitude, 6), round(row.longitude, 6))
    duplicate_counts = Counter((row.date, *series_key(row)) for row in records)
    duplicates = sorted({item[0].isoformat() for item, count in duplicate_counts.items() if count > 1})
    if duplicates:
        issues.append("duplicate dates")
    if any(row.rainfall_mm is not None and row.rainfall_mm < 0 for row in records):
        issues.append("negative rainfall")
    if any(row.temp_max_c is not None and not -100 <= row.temp_max_c <= 70 for row in records):
        issues.append("impossible Tmax")
    if any(row.temp_min_c is not None and not -100 <= row.temp_min_c <= 70 for row in records):
        issues.append("impossible Tmin")
    if any(row.temp_max_c is not None and row.temp_min_c is not None and row.temp_min_c > row.temp_max_c for row in records):
        issues.append("Tmin exceeds Tmax")
    series: dict[tuple[str, float, float], list[date]] = defaultdict(list)
    for row in records:
        series[series_key(row)].append(row.date)
    gaps: list[str] = []
    for series_dates in series.values():
        start = expected_start or min(series_dates)
        end = expected_end or max(series_dates)
        if start <= end:
            present = set(series_dates)
            gaps.extend(d.isoformat() for d in expected_dates(start, end) if d not in present)
    gaps = sorted(set(gaps))
    if gaps:
        issues.append("date gaps")
    coordinates_by_dataset: dict[str, set[tuple[float, float]]] = defaultdict(set)
    for row in records:
        coordinates_by_dataset[row.dataset].add((round(row.latitude, 6), round(row.longitude, 6)))
    if any(len(coords) > 1 for coords in coordinates_by_dataset.values()):
        issues.append("inconsistent coordinates")
    coords = {coord for group in coordinates_by_dataset.values() for coord in group}
    sources = {r.source for r in records if r.source.strip()}
    if any(not r.source.strip() or not r.dataset.strip() for r in records):
        issues.append("missing provenance")
    return ValidationReport(records=len(records), date_start=min(dates) if dates else None,
        date_end=max(dates) if dates else None,
        missing_rainfall=sum(r.rainfall_mm is None for r in records),
        missing_tmax=sum(r.temp_max_c is None for r in records),
        missing_tmin=sum(r.temp_min_c is None for r in records),
        duplicate_dates=duplicates, invalid_values=sorted(set(issues) - {"duplicate dates", "date gaps", "inconsistent coordinates", "missing provenance"}),
        date_gaps=gaps, coordinate={"latitude": next(iter(coords))[0], "longitude": next(iter(coords))[1]} if len(coords) == 1 else None,
        source=next(iter(sources)) if len(sources) == 1 else None,
        status="FAIL" if any(term in issues for term in ("empty dataset", "negative rainfall", "impossible Tmax", "impossible Tmin", "Tmin exceeds Tmax", "duplicate dates", "inconsistent coordinates", "missing provenance")) else "WARNING" if issues else "PASS")


def read_normalized_csv(path: str | Path) -> list[NormalizedHistoricalRecord]:
    """Read the normalized interchange CSV; reject absent or malformed input."""
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "latitude", "longitude", "rainfall_mm", "temp_max_c", "temp_min_c", "source", "dataset", "grid_resolution"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"normalized CSV is missing required columns: {', '.join(missing)}")
        records = []
        for line_number, row in enumerate(reader, start=2):
            for key in ("rainfall_mm", "temp_max_c", "temp_min_c"):
                if row.get(key, "").strip() == "":
                    row[key] = None
            try:
                records.append(NormalizedHistoricalRecord.model_validate(row))
            except Exception as exc:
                raise ValueError(f"invalid normalized record on CSV line {line_number}: {exc}") from exc
        return records


def validate_csv(path: str | Path, *, expected_start: date | None = None,
                 expected_end: date | None = None) -> ValidationReport:
    return validate_records(read_normalized_csv(path), expected_start=expected_start, expected_end=expected_end)


def read_netcdf_point(path: str | Path, dataset_type: str, latitude: float, longitude: float) -> list[dict[str, Any]]:
    """Extract one coordinate-selected series, supporting xarray or SciPy NetCDF3."""
    try:
        metadata = IMD_DATASETS[dataset_type.lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported IMD grid dataset: {dataset_type}") from exc
    try:
        import xarray as xr  # optional dependency; application startup does not require it
    except ImportError as exc:
        try:
            from scipy.io import netcdf_file
        except ImportError as scipy_exc:
            raise RuntimeError("NetCDF extraction requires xarray/netCDF4 or scipy") from scipy_exc
        return _read_netcdf3_point(netcdf_file, path, metadata, dataset_type, latitude, longitude)
    with xr.open_dataset(path) as dataset:
        variables = {name.casefold(): name for name in dataset.data_vars}
        variable = next((variables[name] for name in (metadata.variable.casefold(), "rain", "rf", "rainfall") if name in variables), None)
        if variable is None:
            raise ValueError(f"no recognized {dataset_type} variable in NetCDF file")
        coords = {name.casefold(): name for name in dataset.coords}
        lat_name = next((coords[name] for name in ("lat", "latitude") if name in coords), None)
        lon_name = next((coords[name] for name in ("lon", "longitude") if name in coords), None)
        time_name = next((coords[name] for name in ("time", "date") if name in coords), None)
        if not lat_name or not lon_name or not time_name:
            raise ValueError("NetCDF must expose latitude, longitude and time coordinates")
        latitudes = dataset[lat_name].values.reshape(-1)
        longitudes = dataset[lon_name].values.reshape(-1)
        _ensure_imd_coverage(latitude, longitude, latitudes, longitudes, metadata.resolution, dataset_type)
        point = select_nearest_grid_point(latitude, longitude,
            ((float(lat), float(lon)) for lat in latitudes for lon in longitudes))
        series = dataset[variable].sel({lat_name: point.grid_latitude, lon_name: point.grid_longitude})
        values = series.values.reshape(-1)
        times = dataset[time_name].values.reshape(-1)
        return [_normalized_grid_sample(t, v, point, metadata, dataset_type) for t, v in zip(times, values)]


def _normalized_grid_sample(time_value: Any, value: Any, point: GridPoint,
                            metadata: GridDatasetMetadata, dataset_type: str) -> dict[str, Any]:
    if hasattr(time_value, "strftime"):
        day = time_value.strftime("%Y-%m-%d")
    else:
        day = str(time_value)[:10]
    return {"date": day, "latitude": point.grid_latitude, "longitude": point.grid_longitude,
            "requested_latitude": point.requested_latitude, "requested_longitude": point.requested_longitude,
            "distance_km": point.distance_km, "source": metadata.source, "dataset": metadata.dataset,
            "grid_resolution": metadata.resolution,
            metadata.variable: normalize_missing(float(value), dataset_type)}


def _read_netcdf3_point(netcdf_file: Any, path: str | Path, metadata: GridDatasetMetadata,
                        dataset_type: str, latitude: float, longitude: float) -> list[dict[str, Any]]:
    """Read a single time series from a classic NetCDF file without loading its grid."""
    handle = netcdf_file(path, "r", mmap=True)
    try:
        variables = {name.casefold(): name for name in handle.variables}
        variable_name = next((variables[name] for name in (metadata.variable.casefold(), "rain", "rf", "rainfall") if name in variables), None)
        lat_name = next((variables[name] for name in ("latitude", "lat") if name in variables), None)
        lon_name = next((variables[name] for name in ("longitude", "lon") if name in variables), None)
        time_name = next((variables[name] for name in ("time", "date") if name in variables), None)
        if not variable_name or not lat_name or not lon_name or not time_name:
            raise ValueError("NetCDF must expose a rainfall variable and latitude, longitude, and time coordinates")
        var = handle.variables[variable_name]
        dimensions = tuple(dimension.casefold() for dimension in var.dimensions)
        time_axis = next((i for i, name in enumerate(dimensions) if name in {"time", "date"}), None)
        lat_axis = next((i for i, name in enumerate(dimensions) if name in {"latitude", "lat"}), None)
        lon_axis = next((i for i, name in enumerate(dimensions) if name in {"longitude", "lon"}), None)
        if None in (time_axis, lat_axis, lon_axis) or len(dimensions) != 3:
            raise ValueError(f"unsupported NetCDF variable dimensions: {var.dimensions}")
        latitudes = handle.variables[lat_name][:].copy()
        longitudes = handle.variables[lon_name][:].copy()
        _ensure_imd_coverage(latitude, longitude, latitudes, longitudes, metadata.resolution, dataset_type)
        point = select_nearest_grid_point(latitude, longitude,
            ((float(lat), float(lon)) for lat in latitudes for lon in longitudes))
        lat_index = int(abs(latitudes - point.grid_latitude).argmin())
        lon_index = int(abs(longitudes - point.grid_longitude).argmin())
        selection: list[Any] = [slice(None)] * 3
        selection[lat_axis] = lat_index
        selection[lon_axis] = lon_index
        values = var[tuple(selection)].copy().reshape(-1)
        time_var = handle.variables[time_name]
        offsets = time_var[:].copy().reshape(-1)
        units = getattr(time_var, "units", b"")
        if isinstance(units, bytes):
            units = units.decode("ascii", errors="strict")
        match = re.fullmatch(r"\s*days\s+since\s+(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}:\d{2}))?\s*", str(units), re.IGNORECASE)
        if not match:
            raise ValueError(f"unsupported NetCDF time units: {units!r}")
        base = datetime.fromisoformat(match.group(1) + ("T" + match.group(2) if match.group(2) else "T00:00:00"))
        times = [base + timedelta(days=float(offset)) for offset in offsets]
        result = [_normalized_grid_sample(t, v, point, metadata, dataset_type) for t, v in zip(times, values)]
        del var, time_var
        return result
    finally:
        handle.close()


def read_binary_grid_point(path: str | Path, dataset_type: str, latitude: float, longitude: float,
                           *, year: int, byte_order: str, cell_order: str,
                           values_per_day: int | None = None) -> list[dict[str, Any]]:
    """Decode explicit float32 daily grids; caller must supply official file layout.

    This deliberately does not guess IMD headers, endian order, or packed formats.
    Both byte_order and cell_order must be explicitly confirmed by authoritative
    metadata. Do not call for IMD GRD files while either remains unknown.
    """
    if dataset_type not in {"tmax", "tmin"} or byte_order not in {"<", ">"}:
        raise ValueError("binary grid requires dataset_type tmax/tmin and byte_order '<' or '>'")
    if cell_order != "latitude_rows_longitude_fastest":
        raise ValueError("cell_order must be explicitly confirmed as 'latitude_rows_longitude_fastest'")
    metadata = IMD_DATASETS[dataset_type]
    point = nearest_grid_point(latitude, longitude, dataset_type)
    row = round((point.latitude - metadata.min_latitude) / metadata.resolution)
    col = round((point.longitude - metadata.min_longitude) / metadata.resolution)
    per_day = values_per_day or metadata.rows * metadata.columns
    if per_day < metadata.rows * metadata.columns:
        raise ValueError("declared binary grid has fewer cells than the IMD grid")
    raw = Path(path).read_bytes()
    record_bytes = per_day * 4
    if len(raw) % record_bytes:
        raise ValueError("binary file size does not match the declared float32 grid layout")
    day_count = len(raw) // record_bytes
    year_start = date(year, 1, 1)
    max_days = (date(year + 1, 1, 1) - year_start).days
    if day_count != max_days:
        raise ValueError(f"expected {max_days} daily grids for {year}, found {day_count}")
    cell = row * metadata.columns + col
    fmt = f"{byte_order}{per_day}f"
    output = []
    for offset in range(day_count):
        vals = struct.unpack_from(fmt, raw, offset * record_bytes)
        output.append({"date": (year_start + timedelta(days=offset)).isoformat(),
                       "latitude": point.grid_latitude, "longitude": point.grid_longitude,
                       "requested_latitude": point.requested_latitude, "requested_longitude": point.requested_longitude,
                       "distance_km": point.distance_km, "source": metadata.source, "dataset": metadata.dataset,
                       "grid_resolution": metadata.resolution,
                       metadata.variable: normalize_missing(vals[cell], dataset_type)})
    return output

