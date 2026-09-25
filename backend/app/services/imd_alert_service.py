"""IMD district-warning integration. No non-IMD warning inference is done here."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.weather import AlertDay, AlertWarning, WeatherAlertsResponse

logger = get_logger(__name__)

WARNING_TYPES = {
    1: "No Warning", 2: "Heavy Rain", 3: "Heavy Snow",
    4: "Thunderstorm & Lightning, Squall etc", 5: "Hailstorm",
    6: "Dust Storm", 7: "Dust Raising Winds", 8: "Strong Surface Winds",
    9: "Heat Wave", 10: "Hot Day", 11: "Warm Night", 12: "Cold Wave",
    13: "Cold Day", 14: "Ground Frost", 15: "Fog", 16: "Very Heavy Rain",
    17: "Extremely Heavy Rain",
}
COLOR_NAMES = {1: "Red", 2: "Orange", 3: "Yellow", 4: "Green"}
IMD_SOURCE = "India Meteorological Department (IMD)"


class AlertProviderUnavailable(Exception):
    """Official IMD data could not be safely retrieved or mapped."""


class UnsupportedAlertLocation(Exception):
    pass


class ImdAlertService:
    """Fetches official IMD district warnings and caches successful responses."""

    def __init__(self) -> None:
        self.timeout = settings.IMD_ALERT_TIMEOUT
        self.ttl = max(0, settings.IMD_ALERT_CACHE_TTL_SECONDS)
        self.url = settings.IMD_DISTRICT_WARNING_URL
        self._cache: dict[str, tuple[float, WeatherAlertsResponse]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def resolve_district(city: str) -> tuple[str, str, str]:
        normalized = city.strip().casefold().split(",", 1)[0].strip()
        districts: dict[str, tuple[str, str, str]] = {
            "dhule": ("Dhule", "Maharashtra", settings.IMD_DHULE_OBJ_ID.strip()),
        }
        result = districts.get(normalized)
        if not result:
            raise UnsupportedAlertLocation(city)
        if not result[2]:
            raise AlertProviderUnavailable("IMD Dhule district object ID is not configured from a verified IMD source.")
        return result

    async def get_alerts(self, city: str) -> WeatherAlertsResponse:
        district, state, obj_id = self.resolve_district(city)
        key = obj_id
        async with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1].model_copy(deep=True)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.url, params={"id": obj_id}, headers={"Accept": "application/json"})
        except httpx.TimeoutException as exc:
            logger.warning("IMD warning request timed out", extra={"provider": "IMD"})
            raise AlertProviderUnavailable from exc
        except httpx.RequestError as exc:
            logger.warning("IMD warning connection failed", extra={"provider": "IMD", "error_type": type(exc).__name__})
            raise AlertProviderUnavailable from exc
        if response.status_code != 200:
            # Do not log body: gateways can include operational or access metadata.
            logger.warning("IMD warning provider returned HTTP error", extra={"provider": "IMD", "status_code": response.status_code})
            raise AlertProviderUnavailable
        try:
            payload = response.json()
            normalized = self._normalize(payload, district, state, obj_id)
        except Exception as exc:
            logger.warning("IMD warning response was invalid", extra={"provider": "IMD", "error_type": type(exc).__name__})
            raise AlertProviderUnavailable from exc
        if self.ttl:
            async with self._lock:
                self._cache[key] = (time.monotonic() + self.ttl, normalized)
        return normalized.model_copy(deep=True)

    def _normalize(self, payload: Any, district: str, state: str, obj_id: str) -> WeatherAlertsResponse:
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = payload.get("data", [payload])
        else:
            raise ValueError("Unexpected IMD payload")
        if not isinstance(rows, list) or not rows:
            raise ValueError("Missing IMD warning record")
        row = next((r for r in rows if isinstance(r, dict) and str(r.get("Obj_id", r.get("obj_id", ""))) == obj_id), None)
        if row is None:
            row = next((r for r in rows if isinstance(r, dict) and str(r.get("District", "")).strip().casefold() == district.casefold()), None)
        if row is None:
            raise ValueError("Missing IMD district record")
        district_value = str(row.get("District", "")).strip()
        issued_date = row.get("Date")
        issued_time = row.get("UTC", "00:00")
        if not district_value or not issued_date:
            raise ValueError("Required IMD fields missing")
        try:
            time_value = str(issued_time)
            issued_at = datetime.fromisoformat(f"{issued_date}T{time_value}")
            issued_at = issued_at.replace(tzinfo=timezone.utc) if issued_at.tzinfo is None else issued_at.astimezone(timezone.utc)
        except ValueError:
            issued_at = datetime.fromisoformat(str(issued_date)).replace(tzinfo=timezone.utc)
        days: list[AlertDay] = []
        for index in range(1, 6):
            if f"Day_{index}" not in row or f"Day{index}_Color" not in row:
                raise ValueError("Required IMD forecast-day fields missing")
            raw_codes = row.get(f"Day_{index}")
            codes = self._codes(raw_codes)
            color_raw = row.get(f"Day{index}_Color")
            color_code = int(color_raw) if color_raw not in (None, "") else None
            warnings = [AlertWarning(warning_code=code, warning_type=WARNING_TYPES.get(code, f"Unknown IMD warning code {code}")) for code in codes if code != 1]
            days.append(AlertDay(date=(issued_at + timedelta(days=index - 1)).replace(hour=0, minute=0, second=0, microsecond=0), warnings=warnings, warning_codes=codes, severity=COLOR_NAMES.get(color_code) if color_code is not None else None, severity_code=color_code, is_active=bool(warnings)))
        return WeatherAlertsResponse(location=district, district=district_value, state=state, issued_at=issued_at, forecast_days=days, source=IMD_SOURCE, source_url=f"{self.url}?id={obj_id}")

    @staticmethod
    def _codes(value: Any) -> list[int]:
        if value is None or str(value).strip() == "":
            return []
        parts = value if isinstance(value, list) else str(value).split(",")
        codes = []
        for part in parts:
            try:
                codes.append(int(str(part).strip()))
            except (TypeError, ValueError):
                continue
        return codes
