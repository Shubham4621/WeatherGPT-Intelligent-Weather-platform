"""Read-only IMD DSP station provider with explicit validation and provenance."""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.agriculture import StationMetadata, StationObservation, StationQualityReport

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = PROJECT_ROOT / "data" / "stations" / "imd_dsp_stations.json"
# The supplied CSV format documents empty cells for missing values; other tokens
# stay visible as invalid input instead of being guessed as missing sentinels.
_MISSING = {""}
_HOUR_CODES = {"00": 0, "12": 3, "24": 6, "36": 9, "48": 12, "60": 15, "72": 18, "84": 21}
_DIRECTION_CODES = {
    0: "calm", 2: "NNE", 5: "NE", 7: "ENE", 9: "E", 11: "ESE", 14: "SE", 16: "SSE",
    18: "S", 20: "SSW", 23: "SW", 25: "WSW", 27: "W", 29: "WNW", 32: "NW", 34: "NNW",
    36: "N", 99: "variable",
}


def _catalog() -> list[StationMetadata]:
    if not CATALOG_PATH.exists():
        return []
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [StationMetadata.model_validate(item) for item in payload.get("stations", [])]


def station_metadata(station_id: str | None = None) -> list[StationMetadata] | StationMetadata | None:
    items = _catalog()
    if station_id is None:
        return items
    return next((item for item in items if item.station_id == station_id), None)


def _parse_float(raw: str | None, name: str, bounds: tuple[float, float], invalid: dict[str, str]) -> float | None:
    text = (raw or "").strip()
    if text.upper() in _MISSING:
        return None
    try:
        value = float(text)
    except ValueError:
        invalid[name] = text
        return None
    if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
        invalid[name] = text
        return None
    return value


def _hour_utc(raw: str) -> int:
    text = raw.strip()
    if text in _HOUR_CODES:
        return _HOUR_CODES[text]
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError("invalid_hour_code") from exc
    hour, minute = divmod(value, 100)
    if minute != 0 or hour not in {0, 3, 6, 9, 12, 15, 18, 21}:
        raise ValueError("invalid_utc_hhmm")
    return hour


def _base(meta: StationMetadata, observed_at: datetime, dataset: str) -> dict[str, Any]:
    return {
        "station_id": meta.station_id, "station_name": meta.station_name, "district": meta.district,
        "state": meta.state, "latitude": meta.latitude, "longitude": meta.longitude,
        "elevation_m": meta.elevation_m, "observed_at": observed_at, "source": meta.source, "dataset": dataset,
    }


def _read_rows(meta: StationMetadata, kind: str) -> tuple[list[dict[str, str]], str | None]:
    dataset = meta.datasets.get(kind, {})
    path = PROJECT_ROOT / dataset.get("path", "")
    if not path.is_file():
        return [], str(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream)), None


@lru_cache(maxsize=16)
def _load_observations(station_id: str, kind: str) -> tuple[StationObservation, ...]:
    meta = station_metadata(station_id)
    if not isinstance(meta, StationMetadata):
        return ()
    rows, _ = _read_rows(meta, kind)
    dataset = meta.datasets[kind]["name"]
    date_keys: list[date | datetime] = []
    prepared: list[StationObservation] = []
    for row in rows:
        flags: list[str] = []
        invalid: dict[str, str] = {}
        try:
            if row.get("INDEX", "").strip() != meta.station_id:
                raise ValueError("station_index_mismatch")
            year, month, day = int(row["YEAR"]), int(row["MN"]), int(row["DT"])
            local_date = date(year, month, day)
            if kind == "daily":
                # Table-II RF is the 24 h amount ending 08:30 IST, equivalent to 03:00 UTC.
                observed_at = datetime.combine(local_date, time(3), tzinfo=timezone.utc)
                tmax = _parse_float(row.get("MAX"), "MAX", (-50, 60), invalid)
                tmin = _parse_float(row.get("MIN"), "MIN", (-60, 55), invalid)
                rain = _parse_float(row.get("RF"), "RF", (0, 2000), invalid)
                if tmax is not None and tmin is not None and tmax < tmin:
                    invalid.update({"MAX": row.get("MAX", ""), "MIN": row.get("MIN", "")})
                    tmax = tmin = None
                observation = StationObservation(**_base(meta, observed_at, dataset), temp_max_c=tmax,
                    temp_min_c=tmin, rainfall_mm=rain, quality_flags=flags, invalid_values=invalid)
                date_keys.append(local_date)
            else:
                utc_hour = _hour_utc(row.get("HR", ""))
                observed_at = datetime.combine(local_date, time(utc_hour), tzinfo=timezone.utc)
                # DSP stores the synoptic slots as UTC HHMM (e.g. 1200); the supplied
                # hour-code table maps its 12 UTC slot to code 48 / 17:30 IST.
                slp = _parse_float(row.get("SLP"), "SLP", (800, 1100), invalid)
                mslp = _parse_float(row.get("MSLP"), "MSLP", (800, 1100), invalid)
                dbt = _parse_float(row.get("DBT"), "DBT", (-50, 60), invalid)
                wbt = _parse_float(row.get("WBT"), "WBT", (-50, 60), invalid)
                dpt = _parse_float(row.get("DPT"), "DPT", (-60, 60), invalid)
                rh = _parse_float(row.get("RH"), "RH", (0, 100), invalid)
                wind = _parse_float(row.get("FFF"), "FFF", (0, 300), invalid)
                rain = _parse_float(row.get("RF"), "RF", (0, 2000), invalid)
                vp = _parse_float(row.get("VP"), "VP", (0, 100), invalid)
                direction_raw = (row.get("DD") or "").strip()
                direction = None
                if direction_raw.upper() not in _MISSING:
                    try:
                        direction_code_tenths = int(direction_raw)
                        if direction_code_tenths % 10:
                            raise ValueError
                        direction = _DIRECTION_CODES.get(direction_code_tenths // 10)
                        if direction is None:
                            invalid["DD"] = direction_raw
                    except ValueError:
                        invalid["DD"] = direction_raw
                observation = StationObservation(**_base(meta, observed_at, dataset), temperature_c=dbt,
                    wet_bulb_c=wbt, dew_point_c=dpt, relative_humidity_pct=rh, pressure_hpa=slp,
                    sea_level_pressure_hpa=mslp, wind_speed_kmh=wind, wind_direction=direction,
                    rainfall_mm=rain, quality_flags=flags, invalid_values=invalid)
                date_keys.append(observed_at)
        except (ValueError, KeyError, TypeError):
            # Invalid calendar/hour/index rows are counted in the quality report.
            continue
        if invalid:
            observation.quality_flags.extend(f"invalid_{key}" for key in invalid)
        prepared.append(observation)
    counts = Counter(date_keys)
    for observation, key in zip(prepared, date_keys):
        if counts[key] > 1:
            observation.quality_flags.append("duplicate_observation_time")
    return tuple(prepared)


def station_observations(station_id: str, dataset: str = "daily") -> list[StationObservation]:
    if dataset not in {"daily", "synoptic"}:
        raise ValueError("dataset must be daily or synoptic")
    return [item.model_copy(deep=True) for item in _load_observations(station_id, dataset)]


def nearest_station(latitude: float, longitude: float, max_distance_km: float = 50) -> tuple[StationMetadata, float] | None:
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordinates are outside valid bounds.")
    closest: tuple[StationMetadata, float] | None = None
    for meta in station_metadata():
        lat1, lat2 = math.radians(latitude), math.radians(meta.latitude)
        dlat, dlon = lat2 - lat1, math.radians(meta.longitude - longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance = 6371.0088 * 2 * math.asin(math.sqrt(a))
        if closest is None or distance < closest[1]:
            closest = meta, distance
    return closest if closest and closest[1] <= max_distance_km else None


@lru_cache(maxsize=16)
def _quality_report(station_id: str) -> StationQualityReport | None:
    meta = station_metadata(station_id)
    if not isinstance(meta, StationMetadata):
        return None
    reports: dict[str, dict[str, Any]] = {}
    for kind in ("daily", "synoptic"):
        rows, missing_path = _read_rows(meta, kind)
        obs = _load_observations(station_id, kind)
        date_values = [o.observed_at.date() if kind == "daily" else o.observed_at for o in obs]
        frequencies = Counter(date_values)
        ordered = sorted(set(date_values))
        duplicate_count = sum(count - 1 for count in frequencies.values() if count > 1)
        missing_slots = 0
        if ordered:
            if kind == "daily":
                missing_slots = (ordered[-1] - ordered[0]).days + 1 - len(ordered)
            else:
                expected = int((ordered[-1] - ordered[0]).total_seconds() / (3 * 3600)) + 1
                missing_slots = max(0, expected - len(ordered))
        parameter_columns = ("MAX", "MIN", "RF") if kind == "daily" else ("SLP", "MSLP", "DBT", "WBT", "DPT", "RH", "VP", "DD", "FFF", "AW", "RF")
        missing_values = {key: sum(1 for row in rows if (row.get(key) or "").strip().upper() in _MISSING) for key in parameter_columns}
        invalid_values = Counter(key for observation in obs for key in observation.invalid_values)
        bad_rows = len(rows) - len(obs)
        reports[kind] = {
            "dataset": meta.datasets[kind]["name"], "source": meta.source, "file_available": missing_path is None,
            "missing_file": meta.datasets[kind]["path"] if missing_path else None, "row_count": len(rows), "normalized_row_count": len(obs),
            "invalid_date_or_station_rows": bad_rows, "duplicate_records": duplicate_count,
            "coverage_start": min(ordered).isoformat() if ordered else None,
            "coverage_end": max(ordered).isoformat() if ordered else None,
            "coverage_by_year": dict(sorted(Counter(str(v.year) for v in ordered).items())),
            "coverage_by_month": dict(sorted(Counter(f"{v.year:04d}-{v.month:02d}" for v in ordered).items())),
            "missing_dates_or_slots_between_coverage": missing_slots,
            "missing_values_by_parameter": missing_values,
            "invalid_values_by_parameter": dict(invalid_values),
            "parameter_coverage": {key: len(rows) - count for key, count in missing_values.items()},
            "units": {"temperature": "°C", "rainfall": "mm", "pressure": "hPa", "relative_humidity": "%", "wind_speed": "km/h"},
        }
    files_available = all(item["file_available"] for item in reports.values())
    return StationQualityReport(station=meta, datasets=reports, missing_value_representation="Empty CSV cells are preserved as null; non-empty unparsable or out-of-range measurements are retained in invalid_values and flagged, never imputed.", timestamp_interpretation="Table-II DT is the date of the 24-hour rainfall total ending 08:30 IST (represented at 03:00 UTC). Table-III HR values are UTC HHMM in these files; the supplied DSP codes map the same slots to IST (for example 12 UTC / code 48 = 17:30 IST). observed_at is UTC.", status="available" if files_available else "partial")


def station_quality_report(station_id: str) -> StationQualityReport | None:
    return _quality_report(station_id)


def latest_station_observations(station_id: str) -> dict[str, StationObservation | None]:
    result: dict[str, StationObservation | None] = {}
    for kind in ("daily", "synoptic"):
        rows = station_observations(station_id, kind)
        result[kind] = max(rows, key=lambda item: item.observed_at) if rows else None
    return result

