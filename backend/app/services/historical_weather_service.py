"""Provider-independent historical weather contracts and deterministic analysis."""
from calendar import month_name, monthrange, isleap
from datetime import date, datetime, timezone
import csv
import math
import json
from statistics import mean
from typing import Protocol
from pathlib import Path

from pydantic import BaseModel, Field
from app.core.config import settings


def resolve_historical_coordinates(location: str) -> tuple[float, float] | None:
    try:
        mappings = json.loads(settings.HISTORICAL_LOCATION_COORDINATES or "{}")
    except (TypeError, ValueError):
        return None
    key = location.strip().casefold()
    for value in mappings.values() if isinstance(mappings, dict) else []:
        if not isinstance(value, dict):
            continue
        names = [str(value.get("name", "")), *value.get("aliases", [])]
        if any(isinstance(name, str) and name.strip().casefold() == key for name in names):
            try:
                return float(value["latitude"]), float(value["longitude"])
            except (KeyError, TypeError, ValueError):
                return None
    if isinstance(mappings, dict):
        value = mappings.get(key)
        if isinstance(value, dict):
            try:
                return float(value["latitude"]), float(value["longitude"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


class HistoricalWeatherRecord(BaseModel):
    location: str
    date: date
    temperature_min: float | None = None
    temperature_max: float | None = None
    temperature_mean: float | None = None
    humidity: float | None = None
    rainfall: float | None = None
    wind_speed: float | None = None
    weather_condition: str | None = None
    source: str
    retrieved_at: datetime


class HistoricalDataset(BaseModel):
    status: str
    availability_status: str | None = None
    location: str
    source: str | None = None
    retrieved_at: datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    records: list[HistoricalWeatherRecord] = Field(default_factory=list)
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)


class HistoricalWeatherProvider(Protocol):
    async def fetch(self, city: str, start_date: date, end_date: date) -> HistoricalDataset: ...


class UnconfiguredHistoricalProvider:
    async def fetch(self, city: str, start_date: date, end_date: date) -> HistoricalDataset:
        return HistoricalDataset(status="unavailable", availability_status="NO_HISTORICAL_DATA_CONFIGURED", location=city, reason="Historical weather provider is not configured")


class LocalImdGridHistoricalProvider:
    """Reads the validated daily IMD rainfall extract; never decodes unverified temperature GRDs."""
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(__file__).resolve().parents[3] / "data" / "processed" / "imd_rainfall_daily_0.25deg.csv"

    async def fetch(self, city: str, start_date: date, end_date: date, latitude: float | None = None, longitude: float | None = None) -> HistoricalDataset:
        if (latitude is None) != (longitude is None):
            return HistoricalDataset(status="unavailable", availability_status="INVALID_LOCATION", location=city, reason="Provide both latitude and longitude.")
        if latitude is None:
            point = resolve_historical_coordinates(city)
            if point:
                latitude, longitude = point
        if latitude is None:
            return HistoricalDataset(status="no_data", availability_status="NO_WEATHER_DATA", location=city,
                reason="The installed validated extract contains one IMD rainfall grid cell. Select it by coordinates or use its Dhule reference location.")
        if not self.path.is_file():
            return HistoricalDataset(status="data_not_available", availability_status="DATA_NOT_AVAILABLE", location=city,
                source="India Meteorological Department (IMD Pune)", reason="IMD dataset metadata is configured, but no normalized historical data file is installed.",
                metadata={"expected_file": "data/processed/imd_rainfall_daily_0.25deg.csv", "reference": "IMD Pune gridded archives",
                    "period": "1901–2024 rainfall; 1951–2024 Tmax/Tmin", "resolution": "0.25° rainfall; 1° Tmax/Tmin",
                    "variables": "rainfall_mm, temp_max_c, temp_min_c"})
        try:
            with self.path.open("r", newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                required = {"date", "latitude", "longitude", "rainfall_mm", "source", "dataset", "grid_resolution"}
                if not reader.fieldnames or not required.issubset(reader.fieldnames):
                    raise ValueError("required columns missing")
                rows = []
                for row in reader:
                    rows.append({"date": date.fromisoformat(row["date"]), "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]), "rainfall": float(row["rainfall_mm"]) if row["rainfall_mm"].strip() else None,
                        "source": row["source"].strip(), "dataset": row["dataset"].strip(), "resolution": float(row["grid_resolution"])})
        except (OSError, ValueError, TypeError) as exc:
            return HistoricalDataset(status="unavailable", availability_status="DATA_INVALID", location=city,
                reason=f"Installed historical data could not be validated: {type(exc).__name__}")
        if not rows:
            return HistoricalDataset(status="unavailable", availability_status="DATA_INVALID", location=city,
                reason="Installed historical data file contains no records.")
        coordinates = {(r["latitude"], r["longitude"], r["resolution"]) for r in rows}
        dates = [r["date"] for r in rows]
        expected = (max(dates) - min(dates)).days + 1
        if len(coordinates) != 1 or len(set(dates)) != len(dates) or len(rows) != expected or any(r["rainfall"] is not None and (not math.isfinite(r["rainfall"]) or r["rainfall"] < 0) for r in rows):
            return HistoricalDataset(status="unavailable", availability_status="DATA_INVALID", location=city,
                reason="Installed rainfall extract has duplicate dates, gaps, inconsistent coordinates, or invalid values.")
        grid_lat, grid_lon, grid_resolution = next(iter(coordinates))
        if latitude is not None:
            from app.services.historical_data import select_nearest_grid_point
            selected_point = select_nearest_grid_point(latitude, longitude, [(grid_lat, grid_lon)])
            if selected_point.distance_km > 20:
                return HistoricalDataset(status="no_data", availability_status="NO_WEATHER_DATA", location=city,
                    reason="No validated rainfall grid cell is available within 20 km of the requested coordinate.")
        selected = [row for row in rows if start_date <= row["date"] <= end_date]
        if not selected:
            return HistoricalDataset(status="no_data", availability_status="NO_WEATHER_DATA", location=city,
                source="India Meteorological Department (IMD Pune)", reason="No installed historical records cover the requested period.")
        now = datetime.now(timezone.utc)
        records = [HistoricalWeatherRecord(location=city, date=row["date"], temperature_min=None,
            temperature_max=None, temperature_mean=None, rainfall=row["rainfall"], source=row["source"], retrieved_at=now) for row in selected]
        partial = any(record.rainfall is None for record in records)
        return HistoricalDataset(status="partial" if partial else "available", availability_status="DATA_AVAILABLE", location=city,
            source=selected[0]["source"], period_start=min(r.date for r in records), period_end=max(r.date for r in records), records=records,
            metadata={"dataset": selected[0]["dataset"], "grid_resolution": grid_resolution,
                "latitude": grid_lat, "longitude": grid_lon, "requested_latitude": latitude,
                "requested_longitude": longitude,
                "distance_km": round(selected_point.distance_km, 3) if latitude is not None else None,
                "validation_status": "PASS", "missing_rainfall": sum(r.rainfall is None for r in records),
                "missing_tmax": None, "missing_tmin": None, "provenance": "validated 2013-2024 IMD 0.25 degree extract"})


def validate_range(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")


def aggregate(records: list[HistoricalWeatherRecord]) -> dict:
    """Aggregate supported fields only; temperature average uses reported daily means."""
    if not records:
        return {"status": "no_data", "reason": "No historical data available for the requested period."}
    def avg(field: str):
        values = [getattr(r, field) for r in records if getattr(r, field) is not None]
        return round(mean(values), 2) if values else None
    rainfall_values = [r.rainfall for r in records if r.rainfall is not None]
    rainfall_min_record = min((r for r in records if r.rainfall is not None), key=lambda r: r.rainfall, default=None)
    rainfall_max_record = max((r for r in records if r.rainfall is not None), key=lambda r: r.rainfall, default=None)
    temps = [r.temperature_mean for r in records if r.temperature_mean is not None]
    return {
        "status": "available",
        "record_count": len(records), "temperature_min": min((r.temperature_min for r in records if r.temperature_min is not None), default=None),
        "temperature_max": max((r.temperature_max for r in records if r.temperature_max is not None), default=None),
        "average_temperature": avg("temperature_mean"), "total_rainfall": round(sum(rainfall_values), 2) if rainfall_values else None,
        "average_daily_rainfall": round(mean(rainfall_values), 2) if rainfall_values else None,
        "rainy_days": sum(1 for value in rainfall_values if value > 0) if rainfall_values else None,
        "average_humidity": avg("humidity"), "average_wind_speed": avg("wind_speed"),
        "period_start": min(r.date for r in records).isoformat(), "period_end": max(r.date for r in records).isoformat(),
        "temperature_observations": len(temps), "rainfall_observations": len(rainfall_values),
        "average_tmax": avg("temperature_max"), "average_tmin": avg("temperature_min"),
        "minimum_daily_rainfall": rainfall_min_record.rainfall if rainfall_min_record else None,
        "minimum_daily_rainfall_date": rainfall_min_record.date.isoformat() if rainfall_min_record else None,
        "maximum_daily_rainfall": rainfall_max_record.rainfall if rainfall_max_record else None,
        "maximum_daily_rainfall_date": rainfall_max_record.date.isoformat() if rainfall_max_record else None,
    }


def monthly_aggregation(records: list[HistoricalWeatherRecord]) -> list[dict]:
    grouped: dict[tuple[int, int], list[HistoricalWeatherRecord]] = {}
    for record in records:
        grouped.setdefault((record.date.year, record.date.month), []).append(record)
    results = []
    for (year, month), rows in sorted(grouped.items()):
        summary = aggregate(rows)
        results.append({"year": year, "month": month_name[month], "month_number": month,
                        "record_count": len(rows), "rainfall_observation_count": summary["rainfall_observations"],
                        "expected_day_count": monthrange(year, month)[1],
                        "complete_month": len(rows) == monthrange(year, month)[1] and summary["rainfall_observations"] == len(rows),
                        "average_temperature": summary["average_temperature"], "average_tmax": summary["average_tmax"],
                        "average_tmin": summary["average_tmin"], "temperature_max_observed": summary["temperature_max"],
                        "temperature_min_observed": summary["temperature_min"], "total_rainfall": summary["total_rainfall"], "rainy_days": summary["rainy_days"]})
    return results


def yearly_aggregation(records: list[HistoricalWeatherRecord]) -> list[dict]:
    by_year: dict[int, list[HistoricalWeatherRecord]] = {}
    for record in records:
        by_year.setdefault(record.date.year, []).append(record)
    results = []
    for year, rows in sorted(by_year.items()):
        months = monthly_aggregation(rows)
        wet = [m for m in months if m["total_rainfall"] is not None]
        hot = [m for m in months if m["average_temperature"] is not None]
        results.append({
            "year": year,
            "record_count": len(rows), "rainfall_observation_count": aggregate(rows)["rainfall_observations"],
            "expected_day_count": 366 if isleap(year) else 365,
            "complete_year": len(rows) == (366 if isleap(year) else 365) and aggregate(rows)["rainfall_observations"] == len(rows),
            "average_temperature": aggregate(rows)["average_temperature"],
            "average_tmax": aggregate(rows)["average_tmax"],
            "average_tmin": aggregate(rows)["average_tmin"],
            "temperature_max_observed": aggregate(rows)["temperature_max"],
            "temperature_min_observed": aggregate(rows)["temperature_min"],
            "total_rainfall": aggregate(rows)["total_rainfall"],
            "wettest_month": max(wet, key=lambda m: m["total_rainfall"])["month"] if wet else None,
            "driest_month": min(wet, key=lambda m: m["total_rainfall"])["month"] if wet else None,
            "hottest_month": max(hot, key=lambda m: m["average_temperature"])["month"] if hot else None,
            "coldest_month": min(hot, key=lambda m: m["average_temperature"])["month"] if hot else None,
            "monthly": months,
        })
    return results


def compare(value: float, baseline: float) -> dict:
    difference = round(value - baseline, 2)
    return {"difference": difference, "percentage_difference": round(difference / baseline * 100, 2) if baseline != 0 else None}


def rainfall_anomaly(observed_rainfall_mm: float | None, normal_rainfall_mm: float | None) -> dict:
    """Calculate a descriptive observed-vs-normal rainfall comparison."""
    if observed_rainfall_mm is None or normal_rainfall_mm is None:
        return {"status": "insufficient_data", "anomaly_rainfall_mm": None, "anomaly_percent": None}
    anomaly = round(observed_rainfall_mm - normal_rainfall_mm, 2)
    return {"status": "available", "anomaly_rainfall_mm": anomaly,
        "anomaly_percent": round(anomaly / normal_rainfall_mm * 100, 2) if abs(normal_rainfall_mm) > 1e-9 else None}


def annual_rainfall_climatology_comparison(monthly_observations: list[dict], monthly_normals: list[dict], baseline: str = "1991-2020") -> dict:
    """Compare a complete observed year with the sum of its 12 monthly normals."""
    observed = {int(row["month_number"]): row for row in monthly_observations}
    normals = {int(row["month"]): row for row in monthly_normals}
    if set(observed) != set(range(1, 13)) or set(normals) != set(range(1, 13)):
        return {"status": "insufficient_data", "kind": "ANOMALY", "reason": "twelve_months_required", "baseline": baseline}
    if any(not row.get("complete_month") or row.get("total_rainfall") is None for row in observed.values()):
        return {"status": "insufficient_data", "kind": "ANOMALY", "reason": "complete_observed_year_required", "baseline": baseline}
    if any(row.get("status") != "available" or row.get("normal") is None for row in normals.values()):
        return {"status": "insufficient_data", "kind": "ANOMALY", "reason": "monthly_climatology_unavailable", "baseline": baseline}
    observed_total = round(sum(float(row["total_rainfall"]) for row in observed.values()), 2)
    normal_total = round(sum(float(row["normal"]) for row in normals.values()), 2)
    comparison = rainfall_anomaly(observed_total, normal_total)
    return {"status": comparison["status"], "kind": "ANOMALY", "observed_mm": observed_total,
        "normal_mm": normal_total, "anomaly_mm": comparison["anomaly_rainfall_mm"], "anomaly_percent": comparison["anomaly_percent"],
        "baseline": baseline, "units": "mm", "source": "WeatherGPT analysis of IMD observations and IMD climatology"}


def trend(values: list[float]) -> str:
    """Compare first-half and second-half means; stable when change is <= 1% of scale."""
    if len(values) < 4:
        return "insufficient data"
    split = len(values) // 2
    first, second = mean(values[:split]), mean(values[split:])
    if abs(second-first) <= max(abs(first), 1) * 0.01:
        return "stable"
    return "increasing" if second > first else "decreasing"


def linear_trend(points: list[tuple[int, float]], *, minimum_observations: int = 8) -> dict:
    """Descriptive least-squares slope; reports no significance claim."""
    clean = [(float(x), float(y)) for x, y in points if math.isfinite(float(y))]
    years = [int(x) for x, _ in clean]
    if len(clean) < minimum_observations:
        return {"status": "insufficient_data", "observations": len(clean), "minimum_observations": minimum_observations}
    if len(set(years)) != len(years):
        return {"status": "unavailable", "reason": "duplicate_years"}
    xbar = mean(x for x, _ in clean)
    ybar = mean(y for _, y in clean)
    denominator = sum((x - xbar) ** 2 for x, _ in clean)
    slope = sum((x - xbar) * (y - ybar) for x, y in clean) / denominator if denominator else 0.0
    return {"status": "available", "slope_per_year": round(slope, 4), "period_start": min(years), "period_end": max(years),
        "observations": len(clean), "coverage_years": len(set(years)), "missing_years": sorted(set(range(min(years), max(years)+1)) - set(years)),
        "method": "ordinary least squares descriptive slope; no significance test"}


class ImdClimatologyService:
    """Read monthly normals from supplied IMD climatology NetCDF files."""
    BASELINE = "1991-2020"
    ROOT = Path(__file__).resolve().parents[3] / "data" / "raw" / "imd_climatology"
    _cache: dict[tuple[str, int, float, float], dict] = {}
    PRODUCTS = {"rainfall": ("rainfall", "rf_p25", "rf", "mm", .25),
        "tmax": ("temperature", "tmax_p5", "tmax", "°C", .5),
        "tmin": ("temperature", "tmin_p5", "tmin", "°C", .5)}

    def monthly_normal(self, variable: str, month: int, latitude: float, longitude: float) -> dict:
        from calendar import month_abbr
        if variable not in self.PRODUCTS or not 1 <= month <= 12:
            return {"status": "unavailable", "reason": "unsupported_variable_or_month"}
        key = (variable, month, round(latitude, 5), round(longitude, 5))
        if key in self._cache:
            return dict(self._cache[key])
        folder, prefix, data_name, units, resolution = self.PRODUCTS[variable]
        path = self.ROOT / folder / f"{prefix}_{month_abbr[month].lower()}_clm.nc"
        if not path.is_file():
            return {"status": "unavailable", "reason": "climatology_file_missing", "expected_file": str(path.relative_to(self.ROOT.parent.parent.parent))}
        try:
            from scipy.io import netcdf_file
            from app.services.historical_data import select_nearest_grid_point
            with netcdf_file(path, "r", mmap=False) as nc:
                latitudes = nc.variables["lat"][:].copy().reshape(-1)
                longitudes = nc.variables["lon"][:].copy().reshape(-1)
                half_cell = self.PRODUCTS[variable][4] / 2
                if (latitude < float(min(latitudes)) - half_cell or latitude > float(max(latitudes)) + half_cell
                        or longitude < float(min(longitudes)) - half_cell or longitude > float(max(longitudes)) + half_cell):
                    return {"status": "no_data", "kind": "CLIMATOLOGY", "variable": variable,
                        "month": month, "normal": None, "units": units, "baseline": self.BASELINE,
                        "source": "India Meteorological Department (IMD)", "reason": "climatology_location_unavailable",
                        "requested_latitude": latitude, "requested_longitude": longitude,
                        "resolution_degrees": resolution, "file": path.name}
                point = select_nearest_grid_point(latitude, longitude, ((float(y), float(x)) for y in latitudes for x in longitudes))
                yi = min(range(len(latitudes)), key=lambda i: abs(float(latitudes[i]) - point.grid_latitude))
                xi = min(range(len(longitudes)), key=lambda i: abs(float(longitudes[i]) - point.grid_longitude))
                var = nc.variables[data_name]
                value = float(var[yi, xi])
                attrs = var._attributes
                marker = attrs.get("missing_value", attrs.get("_FillValue", 99.9))
                if not math.isfinite(value) or math.isclose(value, float(marker), abs_tol=1e-5):
                    value = None
        except (OSError, ValueError, KeyError, ImportError, IndexError) as exc:
            return {"status": "unavailable", "reason": f"climatology_read_error:{type(exc).__name__}"}
        result = {"status": "available" if value is not None else "no_data", "kind": "CLIMATOLOGY", "variable": variable,
            "month": month, "normal": round(value, 2) if value is not None else None, "units": units,
            "baseline": self.BASELINE, "source": "India Meteorological Department (IMD)", "reference": "https://dsp.imdpune.gov.in/home_gridded_climatology.php",
            "grid_latitude": point.grid_latitude, "grid_longitude": point.grid_longitude,
            "requested_latitude": latitude, "requested_longitude": longitude, "distance_km": round(point.distance_km, 3),
            "resolution_degrees": resolution, "file": path.name}
        self._cache[key] = result
        return dict(result)


class HistoricalWeatherService:
    def __init__(self, provider: HistoricalWeatherProvider | None = None):
        self.provider = provider or UnconfiguredHistoricalProvider()

    async def get_history(self, city: str, start_date: date, end_date: date, latitude: float | None = None, longitude: float | None = None) -> HistoricalDataset:
        validate_range(start_date, end_date)
        try:
            data = await self.provider.fetch(city.strip(), start_date, end_date, latitude, longitude)
        except TypeError:
            data = await self.provider.fetch(city.strip(), start_date, end_date)
        if data.status in {"available", "partial"}:
            data.records = [r for r in data.records if start_date <= r.date <= end_date]
            data.records.sort(key=lambda r: r.date)
            if not data.records:
                data.status = "no_data"
                data.availability_status = "NO_WEATHER_DATA"
                data.reason = "No historical data available for the requested period."
            else:
                data.retrieved_at = data.retrieved_at or datetime.now(timezone.utc)
                data.period_start = data.records[0].date
                data.period_end = data.records[-1].date
                expected_days = (end_date - start_date).days + 1
                if len(data.records) < expected_days:
                    data.status = "partial"
                    data.availability_status = "DATA_AVAILABLE"
                if data.metadata.get("missing_rainfall", 0):
                    data.status = "partial"
        return data
