"""Provider-independent numerical weather prediction integration.

GFS files are requested as small coordinate-centered GRIB2 subsets from NOAA
NOMADS. No OpenWeatherMap, historical, climatology, warning, or ML fallback is
used when NWP is unavailable.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.schemas.nwp import NwpForecastResponse, NwpPoint
from app.schemas.weather import ForecastDay
from app.services.historical_data import select_nearest_grid_point

GFS_FILTER_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
GFS_SOURCE = "NOAA/NCEP NOMADS"
GFS_MODEL = "GFS 0.25 degree"


class NwpUnavailable(Exception):
    """A model product or required decoder is unavailable."""


class NwpMalformedResponse(Exception):
    """A provider returned data that cannot be safely normalized."""


class GribPointDecoder(Protocol):
    def decode(self, content: bytes, latitude: float, longitude: float) -> dict[str, Any]: ...


class EcCodesGribPointDecoder:
    """Decode the requested GFS fields and select the nearest returned grid node."""

    def __init__(self) -> None:
        try:
            import eccodes  # noqa: F401
        except ImportError as exc:
            raise NwpUnavailable("grib_decoder_unavailable") from exc

    def decode(self, content: bytes, latitude: float, longitude: float) -> dict[str, Any]:
        import eccodes

        if not content.startswith(b"GRIB"):
            raise NwpMalformedResponse("provider_response_not_grib")
        result: dict[str, float | None] = {"temperature_c": None, "precipitation_since_initialization_mm": None,
                                           "wind_u_ms": None, "wind_v_ms": None}
        nearest_fields: dict[str, tuple[float, float, float, float]] = {}
        messages = 0
        offset = 0
        while offset < len(content):
            if content[offset:offset + 4] != b"GRIB" or len(content) - offset < 16:
                raise NwpMalformedResponse("malformed_grib2_message_boundary")
            edition = content[offset + 7]
            if edition != 2:
                raise NwpMalformedResponse("unsupported_grib_edition")
            message_length = int.from_bytes(content[offset + 8:offset + 16], "big")
            end = offset + message_length
            if message_length < 20 or end > len(content) or content[end - 4:end] != b"7777":
                raise NwpMalformedResponse("truncated_grib2_message")
            try:
                handle = eccodes.codes_new_from_message(content[offset:end])
            except Exception as exc:
                raise NwpMalformedResponse("ecCodes_rejected_grib2_message") from exc
            if handle is None:
                raise NwpMalformedResponse("ecCodes_rejected_grib2_message")
            offset = end
            messages += 1
            try:
                short_name = str(eccodes.codes_get(handle, "shortName")).lower()
                level_type = str(eccodes.codes_get(handle, "typeOfLevel"))
                level = int(eccodes.codes_get(handle, "level"))
                if not ((short_name in {"2t", "t"} and level_type == "heightAboveGround" and level == 2)
                        or (short_name in {"tp", "apcp"} and level_type == "surface")
                        or (short_name in {"10u", "u"} and level_type == "heightAboveGround" and level == 10)
                        or (short_name in {"10v", "v"} and level_type == "heightAboveGround" and level == 10)):
                    continue
                lats = eccodes.codes_get_array(handle, "latitudes")
                lons = eccodes.codes_get_array(handle, "longitudes")
                values = eccodes.codes_get_values(handle)
                coords = [(float(y), ((float(x) + 180) % 360) - 180) for y, x in zip(lats, lons)]
                point = select_nearest_grid_point(latitude, longitude, coords)
                index = min(range(len(coords)), key=lambda i: (coords[i][0] - point.grid_latitude) ** 2 + (coords[i][1] - point.grid_longitude) ** 2)
                value = float(values[index])
                if not math.isfinite(value):
                    raise NwpMalformedResponse("non_finite_nwp_value")
                units = str(eccodes.codes_get(handle, "units")).strip().lower()
                if short_name in {"2t", "t"}:
                    field_key = "temperature_c"
                    if units in {"k", "kelvin"}:
                        value -= 273.15
                    elif units in {"c", "°c", "degc"}:
                        pass
                    else:
                        raise NwpMalformedResponse("unsupported_temperature_units")
                elif short_name in {"tp", "apcp"}:
                    field_key = "precipitation_since_initialization_mm"
                    # GFS accumulated precipitation is commonly kg m-2, numerically mm water equivalent.
                    if units in {"kg m**-2", "kg m-2", "mm"}:
                        if value < 0:
                            raise NwpMalformedResponse("negative_accumulated_precipitation")
                    else:
                        raise NwpMalformedResponse("unsupported_precipitation_units")
                elif short_name in {"10u", "u"}:
                    field_key = "wind_u_ms"
                    if units not in {"m s**-1", "m s-1", "m/s"}:
                        raise NwpMalformedResponse("unsupported_wind_units")
                else:
                    field_key = "wind_v_ms"
                    if units not in {"m s**-1", "m s-1", "m/s"}:
                        raise NwpMalformedResponse("unsupported_wind_units")
                previous = nearest_fields.get(field_key)
                if previous is None or point.distance_km < previous[0]:
                    nearest_fields[field_key] = (point.distance_km, value, point.grid_latitude, point.grid_longitude)
            finally:
                eccodes.codes_release(handle)
        if not messages or "temperature_c" not in nearest_fields:
            raise NwpMalformedResponse("required_gfs_temperature_field_missing")
        for field_key, (_distance, value, _latitude, _longitude) in nearest_fields.items():
            result[field_key] = value
        if result["wind_u_ms"] is not None and result["wind_v_ms"] is not None:
            result["wind_speed_ms"] = math.hypot(result.pop("wind_u_ms"), result.pop("wind_v_ms"))
        else:
            result.pop("wind_u_ms", None)
            result.pop("wind_v_ms", None)
            result["wind_speed_ms"] = None
        result["selected_latitude"] = nearest_fields["temperature_c"][2]
        result["selected_longitude"] = nearest_fields["temperature_c"][3]
        return result


class NwpProvider(Protocol):
    async def get_forecast(self, latitude: float, longitude: float, days: int) -> NwpForecastResponse: ...
    async def get_available_runs(self, latitude: float, longitude: float) -> list[datetime]: ...
    def get_model_metadata(self) -> dict[str, Any]: ...
    async def get_point_forecast(self, latitude: float, longitude: float, days: int) -> NwpForecastResponse: ...


class GfsNomadsProvider:
    """Retrieve public GFS 0.25-degree guidance from the NOAA NOMADS filter."""

    def __init__(self, *, decoder: GribPointDecoder | None = None, timeout: float | None = None,
                 http_client: Any = httpx.AsyncClient):
        self._decoder = decoder
        self.timeout = timeout or settings.NWP_TIMEOUT_SECONDS
        self.http_client = http_client

    async def _client_fetch(self, client: Any, latitude: float, longitude: float,
                            run: datetime, lead: int) -> bytes:
        east_lon = longitude % 360
        left = east_lon - 0.3
        right = east_lon + 0.3
        longitude_segments = ([(left + 360, 360), (0, right)] if left < 0 else
                              [(left, 360), (0, right - 360)] if right >= 360 else [(left, right)])
        base_params = {
            "file": f"gfs.t{run:%H}z.pgrb2.0p25.f{lead:03d}",
            "var_TMP": "on", "lev_2_m_above_ground": "on",
            "var_APCP": "on", "lev_surface": "on",
            "var_UGRD": "on", "var_VGRD": "on", "lev_10_m_above_ground": "on",
            "subregion": "",
            "toplat": f"{min(90.0, latitude + 0.3):.3f}",
            "bottomlat": f"{max(-90.0, latitude - 0.3):.3f}",
            "dir": f"/gfs.{run:%Y%m%d}/{run:%H}/atmos",
        }
        payloads = []
        for left_lon, right_lon in longitude_segments:
            params = {**base_params, "leftlon": f"{left_lon:.3f}", "rightlon": f"{right_lon:.3f}"}
            response = await client.get(GFS_FILTER_URL, params=params)
            if response.status_code == 404:
                raise NwpUnavailable("gfs_lead_not_available")
            if response.status_code in (401, 403):
                raise NwpUnavailable("gfs_provider_access_denied")
            if response.status_code != 200:
                raise NwpUnavailable(f"gfs_provider_http_{response.status_code}")
            payloads.append(response.content)
        return b"".join(payloads)

    @staticmethod
    def _candidate_runs(now: datetime) -> list[datetime]:
        current = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        current = current.replace(hour=(current.hour // 6) * 6)
        return [current - timedelta(hours=6 * offset) for offset in range(0, 9)]

    async def get_forecast(self, latitude: float, longitude: float, days: int = 5) -> NwpForecastResponse:
        if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Coordinates are outside valid latitude/longitude bounds.")
        if not 1 <= days <= 5:
            raise ValueError("NWP forecast days must be between 1 and 5.")
        try:
            decoder = self._decoder or EcCodesGribPointDecoder()
        except NwpUnavailable as exc:
            return self._unavailable(latitude, longitude, str(exc))
        timeout = httpx.Timeout(self.timeout)
        async with self.http_client(timeout=timeout, follow_redirects=True) as client:
            run = None
            decoded: dict[int, dict[str, float | None]] = {}
            last_reason = "gfs_run_unavailable"
            for candidate in self._candidate_runs(datetime.now(timezone.utc)):
                try:
                    content = await self._client_fetch(client, latitude, longitude, candidate, 6)
                    decoded[6] = decoder.decode(content, latitude, longitude)
                    run = candidate
                    break
                except NwpUnavailable as exc:
                    last_reason = str(exc)
                except NwpMalformedResponse as exc:
                    last_reason = str(exc)
                except (httpx.TimeoutException, httpx.RequestError):
                    last_reason = "gfs_provider_unavailable"
            if run is None:
                response = self._unavailable(latitude, longitude, last_reason)
                if last_reason.startswith("provider_response") or last_reason.startswith("required_gfs"):
                    response.status = "error"
                return response

            leads = list(range(12, days * 24 + 1, 6))
            semaphore = asyncio.Semaphore(4)
            async def load(lead: int) -> tuple[int, dict[str, float | None] | None, str | None]:
                async with semaphore:
                    try:
                        content = await self._client_fetch(client, latitude, longitude, run, lead)
                        return lead, decoder.decode(content, latitude, longitude), None
                    except (NwpUnavailable, NwpMalformedResponse) as exc:
                        return lead, None, str(exc)
                    except (httpx.TimeoutException, httpx.RequestError):
                        return lead, None, "gfs_provider_unavailable"
            outcomes = await asyncio.gather(*(load(lead) for lead in leads))
            missing = []
            for lead, values, _reason in outcomes:
                if values is None:
                    missing.append(lead)
                else:
                    decoded[lead] = values

        points = [NwpPoint(forecast_time=run + timedelta(hours=lead), lead_hours=lead,
            temperature_c=values.get("temperature_c"),
            precipitation_since_initialization_mm=values.get("precipitation_since_initialization_mm"),
            wind_speed_ms=values.get("wind_speed_ms")) for lead, values in sorted(decoded.items())]
        daily: dict[str, list[NwpPoint]] = {}
        for point in points:
            daily.setdefault(point.forecast_time.date().isoformat(), []).append(point)
        forecast = []
        for day, values in sorted(daily.items()):
            temperatures = [p.temperature_c for p in values if p.temperature_c is not None]
            if not temperatures:
                continue
            forecast.append(ForecastDay(date=datetime.fromisoformat(day).replace(tzinfo=timezone.utc),
                temperature_min=min(temperatures), temperature_max=max(temperatures),
                description="GFS numerical model guidance", rain_probability=None))
        if not points:
            return self._unavailable(latitude, longitude, "gfs_forecast_fields_unavailable")
        selected_latitude = decoded[6].get("selected_latitude", latitude)
        selected_longitude = decoded[6].get("selected_longitude", longitude)
        selected_point = select_nearest_grid_point(latitude, longitude, [(selected_latitude, selected_longitude)])
        units = {"temperature": "°C"}
        if any(point.precipitation_since_initialization_mm is not None for point in points):
            units["precipitation_since_initialization"] = "mm"
        if any(point.wind_speed_ms is not None for point in points):
            units["wind_speed"] = "m/s"
        return NwpForecastResponse(status="partial" if missing else "available", location={"latitude": latitude, "longitude": longitude},
            initialization_time=run, forecast_start=points[0].forecast_time, forecast_end=points[-1].forecast_time,
            selected_grid_point={"latitude": selected_latitude, "longitude": selected_longitude,
                                 "distance_km": round(selected_point.distance_km, 3)}, units=units,
            points=points, forecast=forecast, missing_leads=missing,
            reason="Some GFS forecast lead files were unavailable." if missing else None)

    async def get_point_forecast(self, latitude: float, longitude: float, days: int = 5) -> NwpForecastResponse:
        return await self.get_forecast(latitude, longitude, days)

    def get_model_metadata(self) -> dict[str, Any]:
        return {"provider": GFS_SOURCE, "model": GFS_MODEL, "format": "GRIB2", "resolution_degrees": 0.25,
                "forecast_horizon_hours": 120, "requested_temporal_step_hours": 6,
                "variables": {"temperature": "2 m air temperature (K converted to °C)",
                    "precipitation_since_initialization": "surface accumulated precipitation (kg m-2 converted to mm water equivalent)",
                    "wind_speed": "10 m wind components (m/s) combined to speed"},
                "authentication": "No API key; public NOAA NOMADS access", "source_url": GFS_FILTER_URL}

    async def get_available_runs(self, latitude: float, longitude: float) -> list[datetime]:
        if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Coordinates are outside valid latitude/longitude bounds.")
        timeout = httpx.Timeout(self.timeout)
        runs = []
        async with self.http_client(timeout=timeout, follow_redirects=True) as client:
            for run in self._candidate_runs(datetime.now(timezone.utc)):
                try:
                    payload = await self._client_fetch(client, latitude, longitude, run, 6)
                    if payload.startswith(b"GRIB"):
                        runs.append(run)
                        break
                except (NwpUnavailable, httpx.TimeoutException, httpx.RequestError):
                    continue
        return runs

    @staticmethod
    def _unavailable(latitude: float, longitude: float, reason: str, status: str = "unavailable") -> NwpForecastResponse:
        return NwpForecastResponse(status=status, location={"latitude": latitude, "longitude": longitude}, reason=reason)


class NwpService:
    def __init__(self, provider: NwpProvider | None = None):
        self.provider = provider or GfsNomadsProvider()
        self.cache_ttl = max(0, settings.NWP_CACHE_TTL_SECONDS)
        self._cache: dict[tuple[float, float, int], tuple[datetime, NwpForecastResponse]] = {}
        self._cache_lock = asyncio.Lock()

    async def forecast(self, latitude: float, longitude: float, days: int = 5) -> NwpForecastResponse:
        if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Coordinates are outside valid latitude/longitude bounds.")
        if not 1 <= days <= 5:
            raise ValueError("NWP forecast days must be between 1 and 5.")
        key = (latitude, longitude, days)
        now = datetime.now(timezone.utc)
        async with self._cache_lock:
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                return cached[1].model_copy(deep=True)
        try:
            response = await self.provider.get_forecast(latitude, longitude, days)
        except httpx.TimeoutException:
            return NwpForecastResponse(status="unavailable", location={"latitude": latitude, "longitude": longitude}, reason="nwp_timeout")
        except httpx.RequestError:
            return NwpForecastResponse(status="unavailable", location={"latitude": latitude, "longitude": longitude}, reason="nwp_provider_unavailable")
        except NwpMalformedResponse as exc:
            return NwpForecastResponse(status="error", location={"latitude": latitude, "longitude": longitude}, reason=str(exc))
        except NwpUnavailable as exc:
            return NwpForecastResponse(status="unavailable", location={"latitude": latitude, "longitude": longitude}, reason=str(exc))
        except Exception:
            return NwpForecastResponse(status="error", location={"latitude": latitude, "longitude": longitude}, reason="nwp_invalid_response")
        response.retrieved_at = response.retrieved_at or datetime.now(timezone.utc)
        if response.status in {"available", "partial"} and self.cache_ttl:
            async with self._cache_lock:
                self._cache[key] = (now + timedelta(seconds=self.cache_ttl), response.model_copy(deep=True))
        return response

    def get_model_metadata(self) -> dict[str, Any]:
        metadata = getattr(self.provider, "get_model_metadata", None)
        return metadata() if metadata else {"provider": GFS_SOURCE, "model": GFS_MODEL}

    async def get_available_runs(self, latitude: float, longitude: float) -> list[datetime]:
        operation = getattr(self.provider, "get_available_runs", None)
        return await operation(latitude, longitude) if operation else []

    async def get_point_forecast(self, latitude: float, longitude: float, days: int = 5) -> NwpForecastResponse:
        return await self.forecast(latitude, longitude, days)
