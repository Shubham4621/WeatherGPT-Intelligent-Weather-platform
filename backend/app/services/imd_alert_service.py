"""IMD district-warning integration. No non-IMD warning inference is done here."""

import asyncio
import json
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
        try:
            configured = json.loads(settings.IMD_DISTRICT_MAPPINGS or "{}")
            if not isinstance(configured, dict):
                raise ValueError
        except (TypeError, ValueError):
            raise AlertProviderUnavailable("provider_configuration_invalid")
        # Values: {"aliases": ["city"], "district": "...", "state": "...", "obj_id": "..."}
        for value in configured.values():
            if not isinstance(value, dict):
                continue
            names = [value.get("district", ""), *value.get("aliases", [])]
            if any(isinstance(name, str) and name.strip().casefold() == normalized for name in names):
                obj_id = str(value.get("obj_id", "")).strip()
                if not obj_id:
                    raise AlertProviderUnavailable("location_mapping_unresolved")
                return str(value.get("district", "")).strip(), str(value.get("state", "")).strip(), obj_id
        # Compatibility for the previously configured verified Dhule ID.
        if normalized == "dhule" and settings.IMD_DHULE_OBJ_ID.strip():
            return "Dhule", "Maharashtra", settings.IMD_DHULE_OBJ_ID.strip()
        if normalized == "dhule":
            raise AlertProviderUnavailable("location_mapping_unresolved")
        raise UnsupportedAlertLocation(city)

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
            raise AlertProviderUnavailable("provider_timeout") from exc
        except httpx.RequestError as exc:
            logger.warning("IMD warning connection failed", extra={"provider": "IMD", "error_type": type(exc).__name__})
            raise AlertProviderUnavailable("provider_connection_error") from exc
        if response.status_code != 200:
            # Do not log body: gateways can include operational or access metadata.
            logger.warning("IMD warning provider returned HTTP error", extra={"provider": "IMD", "status_code": response.status_code})
            reason = "provider_authorization_required" if response.status_code in (401, 403) else "provider_http_error"
            raise AlertProviderUnavailable(reason)
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
            code_key = next((key for key in (f"Day{index}", f"Day_{index}") if key in row), None)
            color_key = next((key for key in (f"Day{index}_Color", f"Day_{index}_Color", f"Day{index}Color") if key in row), None)
            if code_key is None or color_key is None:
                raise ValueError("Required IMD forecast-day fields missing")
            raw_codes = row.get(code_key)
            codes = self._codes(raw_codes)
            color_raw = row.get(color_key)
            color_code = int(color_raw) if color_raw not in (None, "") else None
            warnings = [AlertWarning(warning_code=code, warning_type=WARNING_TYPES.get(code, f"Unknown IMD warning code {code}")) for code in codes if code != 1]
            days.append(AlertDay(date=(issued_at + timedelta(days=index - 1)).replace(hour=0, minute=0, second=0, microsecond=0), warnings=warnings, warning_codes=codes, severity=COLOR_NAMES.get(color_code) if color_code is not None else None, severity_code=color_code, is_active=bool(warnings)))
        return WeatherAlertsResponse(location=district, district=district_value, state=state, issued_at=issued_at, forecast_days=days, source=IMD_SOURCE, source_url=f"{self.url}?id={obj_id}", retrieved_at=datetime.now(timezone.utc), reference=obj_id)

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
