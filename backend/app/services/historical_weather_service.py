"""Provider-independent historical weather contracts and deterministic analysis."""
from calendar import month_name
from datetime import date, datetime, timezone
from statistics import mean
from typing import Protocol
from pathlib import Path

from pydantic import BaseModel, Field


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
    """Reads a normalized local file only; it never downloads or synthesizes records."""
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(__file__).resolve().parents[3] / "data" / "processed" / "dhule_historical.csv"

    async def fetch(self, city: str, start_date: date, end_date: date) -> HistoricalDataset:
        if city.strip().casefold() not in {"dhule", "dhule, maharashtra", "dhule, india"}:
            return HistoricalDataset(status="no_data", availability_status="NO_WEATHER_DATA", location=city,
                reason="The installed IMD grid extract is configured for Dhule only.")
        if not self.path.is_file():
            return HistoricalDataset(status="data_not_available", availability_status="DATA_NOT_AVAILABLE", location=city,
                source="India Meteorological Department (IMD Pune)", reason="IMD dataset metadata is configured, but no normalized historical data file is installed.",
                metadata={"expected_file": "data/processed/dhule_historical.csv", "reference": "IMD Pune gridded archives",
                    "period": "1901–2024 rainfall; 1951–2024 Tmax/Tmin", "resolution": "0.25° rainfall; 1° Tmax/Tmin",
                    "variables": "rainfall_mm, temp_max_c, temp_min_c"})
        try:
            from app.services.historical_data import read_normalized_csv, validate_records
            rows = read_normalized_csv(self.path)
        except (OSError, ValueError, TypeError) as exc:
            return HistoricalDataset(status="unavailable", availability_status="DATA_INVALID", location=city,
                reason=f"Installed historical data could not be validated: {type(exc).__name__}")
        if not rows:
            return HistoricalDataset(status="unavailable", availability_status="DATA_INVALID", location=city,
                reason="Installed historical data file contains no records.")
        selected = [row for row in rows if start_date <= row.date <= end_date]
        if not selected:
            return HistoricalDataset(status="no_data", availability_status="NO_WEATHER_DATA", location=city,
                source="India Meteorological Department (IMD Pune)", reason="No installed historical records cover the requested period.")
        report = validate_records(rows)
        if report.status == "FAIL":
            return HistoricalDataset(status="unavailable", availability_status="DATA_INVALID", location=city,
                source=selected[0].source, reason="Installed historical data failed validation; no records were returned.",
                metadata={"validation_status": report.status, "invalid_values": report.invalid_values})
        records = [HistoricalWeatherRecord(location=city, date=row.date, temperature_min=row.temp_min_c,
            temperature_max=row.temp_max_c, temperature_mean=None,
            rainfall=row.rainfall_mm, source=row.source, retrieved_at=datetime.now(timezone.utc)) for row in selected]
        return HistoricalDataset(status="available", availability_status="DATA_AVAILABLE", location=city,
            source=selected[0].source, period_start=min(r.date for r in records), period_end=max(r.date for r in records),
            records=records, metadata={"dataset": selected[0].dataset, "grid_resolution": selected[0].grid_resolution,
                "latitude": selected[0].latitude, "longitude": selected[0].longitude,
                "validation_status": report.status, "missing_rainfall": report.missing_rainfall,
                "missing_tmax": report.missing_tmax, "missing_tmin": report.missing_tmin})


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
    }


def monthly_aggregation(records: list[HistoricalWeatherRecord]) -> list[dict]:
    grouped: dict[tuple[int, int], list[HistoricalWeatherRecord]] = {}
    for record in records:
        grouped.setdefault((record.date.year, record.date.month), []).append(record)
    results = []
    for (year, month), rows in sorted(grouped.items()):
        summary = aggregate(rows)
        results.append({"year": year, "month": month_name[month], "month_number": month,
                        "average_temperature": summary["average_temperature"], "total_rainfall": summary["total_rainfall"], "rainy_days": summary["rainy_days"]})
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
            "average_temperature": aggregate(rows)["average_temperature"],
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


def trend(values: list[float]) -> str:
    """Compare first-half and second-half means; stable when change is <= 1% of scale."""
    if len(values) < 4:
        return "insufficient data"
    split = len(values) // 2
    first, second = mean(values[:split]), mean(values[split:])
    if abs(second-first) <= max(abs(first), 1) * 0.01:
        return "stable"
    return "increasing" if second > first else "decreasing"


class HistoricalWeatherService:
    def __init__(self, provider: HistoricalWeatherProvider | None = None):
        self.provider = provider or UnconfiguredHistoricalProvider()

    async def get_history(self, city: str, start_date: date, end_date: date) -> HistoricalDataset:
        validate_range(start_date, end_date)
        data = await self.provider.fetch(city.strip(), start_date, end_date)
        if data.status == "available":
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
        return data
