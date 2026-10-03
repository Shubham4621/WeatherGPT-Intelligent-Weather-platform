"""Weather service — isolates all interaction with the upstream weather provider.

Currently backed by OpenWeatherMap.  The provider can be swapped by changing
only this module.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import httpx

from app.core.config import settings
from app.core.exceptions import WeatherAPIError, WeatherProviderError
from app.core.logging import get_logger
from app.schemas.weather import (
    CurrentWeatherResponse,
    LocationInfo,
    SunInfo,
    WeatherCondition,
    ForecastDay,
    ForecastResponse,
)

logger = get_logger(__name__)

_PROVIDER_NAME = "OpenWeatherMap"


class WeatherService:
    """Fetches weather data from OpenWeatherMap and normalizes the response."""

    def __init__(self) -> None:
        self.api_key = settings.WEATHER_API_KEY
        self.base_url = settings.WEATHER_API_BASE_URL
        self.timeout = settings.WEATHER_API_TIMEOUT

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def get_current_weather_by_city(self, city: str) -> CurrentWeatherResponse:
        """Fetch current weather by city name."""
        params = {"q": city, "units": "metric", "appid": self.api_key}
        data = await self._fetch("/weather", params)
        return self._normalize(data)

    async def get_current_weather_by_coords(
        self, lat: float, lon: float
    ) -> CurrentWeatherResponse:
        """Fetch current weather by latitude/longitude."""
        params = {
            "lat": lat,
            "lon": lon,
            "units": "metric",
            "appid": self.api_key,
        }
        data = await self._fetch("/weather", params)
        return self._normalize(data)

    async def get_forecast_by_city(self, city: str) -> ForecastResponse:
        """Fetch and aggregate OpenWeatherMap's 3-hour forecast into local days."""
        data = await self._fetch("/forecast", {"q": city, "units": "metric", "appid": self.api_key})
        return self._normalize_forecast(data)

    async def get_forecast_by_coords(self, lat: float, lon: float) -> ForecastResponse:
        """Fetch forecast by validated latitude/longitude coordinates."""
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise WeatherAPIError(detail="Coordinates are outside valid latitude/longitude bounds.", status_code=422)
        data = await self._fetch("/forecast", {"lat": lat, "lon": lon, "units": "metric", "appid": self.api_key})
        return self._normalize_forecast(data)

    def _normalize_forecast(self, data: Dict[str, Any]) -> ForecastResponse:
        try:
            city_data = data["city"]
            rows = data["list"]
            if not rows:
                raise ValueError("Empty forecast")
            grouped: dict[str, list[dict[str, Any]]] = {}
            offset = int(city_data.get("timezone", 0))
            for row in rows:
                stamp = datetime.fromtimestamp(row["dt"] + offset, tz=timezone.utc)
                date_key = stamp.date().isoformat()
                grouped.setdefault(date_key, []).append(row)
            days = []
            for day, entries in grouped.items():
                mains = [entry["main"] for entry in entries]
                weather = entries[len(entries) // 2]["weather"][0]
                required = [m["temp_min"] for m in mains] + [m["temp_max"] for m in mains]
                if any(value is None for value in required):
                    raise ValueError("Missing temperatures")
                pops = [entry.get("pop") for entry in entries if entry.get("pop") is not None]
                days.append(ForecastDay(
                    date=datetime.fromisoformat(day).replace(tzinfo=timezone.utc),
                    temperature_min=min(m["temp_min"] for m in mains),
                    temperature_max=max(m["temp_max"] for m in mains),
                    feels_like=sum(m["feels_like"] for m in mains if m.get("feels_like") is not None) / max(1, sum(m.get("feels_like") is not None for m in mains)),
                    humidity=round(sum(m["humidity"] for m in mains if m.get("humidity") is not None) / max(1, sum(m.get("humidity") is not None for m in mains))) if any(m.get("humidity") is not None for m in mains) else None,
                    description=weather["description"],
                    cloudiness=round(sum(e["clouds"]["all"] for e in entries if e.get("clouds") and e["clouds"].get("all") is not None) / max(1, sum(bool(e.get("clouds") and e["clouds"].get("all") is not None) for e in entries))) if any(e.get("clouds") and e["clouds"].get("all") is not None for e in entries) else None,
                    wind_speed=round(sum(e["wind"]["speed"] for e in entries if e.get("wind") and e["wind"].get("speed") is not None) / max(1, sum(bool(e.get("wind") and e["wind"].get("speed") is not None) for e in entries)), 2) if any(e.get("wind") and e["wind"].get("speed") is not None for e in entries) else None,
                    rain_probability=max(pops) * 100 if pops else None,
                ))
            return ForecastResponse(
                location=LocationInfo(name=city_data["name"], country=city_data["country"], latitude=city_data["coord"]["lat"], longitude=city_data["coord"]["lon"]),
                forecast=days, source=_PROVIDER_NAME,
                forecasted_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.error("Failed to normalize forecast data", extra={"error_type": type(exc).__name__})
            raise WeatherProviderError(detail="Failed to process weather provider response.", status_code=502)

    # ------------------------------------------------------------------
    # Private — HTTP client
    # ------------------------------------------------------------------

    async def _fetch(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an HTTP GET request to the weather provider."""
        if not self.api_key:
            raise WeatherProviderError(
                detail="Weather API key is not configured. Set WEATHER_API_KEY in your environment.",
                status_code=503,
            )

        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
        except httpx.TimeoutException:
            logger.error(
                "Weather provider timeout",
                extra={"provider": _PROVIDER_NAME, "path": path},
            )
            raise WeatherProviderError(
                detail="Weather provider request timed out. Please try again.",
                status_code=504,
            )
        except httpx.RequestError as exc:
            logger.error(
                "Weather provider connection error",
                extra={"provider": _PROVIDER_NAME, "error_type": type(exc).__name__},
            )
            raise WeatherProviderError(
                detail="Unable to connect to the weather provider.",
                status_code=502,
            )

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Inspect the provider response and raise appropriate errors."""
        if response.status_code == 200:
            try:
                return response.json()
            except Exception:
                raise WeatherProviderError(
                    detail="Invalid response from weather provider.",
                    status_code=502,
                )

        # --- Map provider HTTP codes to our errors ---
        try:
            body = response.json()
            provider_msg = body.get("message", "")
        except Exception:
            provider_msg = response.text

        if response.status_code == 401:
            logger.error("Invalid weather API key", extra={"provider": _PROVIDER_NAME})
            raise WeatherProviderError(
                detail="Weather provider authentication failed. Check WEATHER_API_KEY.",
                status_code=502,
            )
        if response.status_code == 404:
            raise WeatherAPIError(
                detail=f"Location not found: {provider_msg}",
                status_code=404,
            )
        if response.status_code == 429:
            logger.warning("Weather API rate limit hit", extra={"provider": _PROVIDER_NAME})
            raise WeatherProviderError(
                detail="Weather provider rate limit exceeded. Please try again later.",
                status_code=429,
            )

        logger.error(
            "Unexpected weather provider response",
            extra={
                "provider": _PROVIDER_NAME,
                "status_code": response.status_code,
                "body": provider_msg[:200],
            },
        )
        raise WeatherProviderError(
            detail="Unexpected error from weather provider.",
            status_code=502,
        )

    # ------------------------------------------------------------------
    # Private — Normalization
    # ------------------------------------------------------------------

    def _normalize(self, data: Dict[str, Any]) -> CurrentWeatherResponse:
        """Convert the raw OpenWeatherMap JSON into our normalized schema."""
        try:
            # Reject incomplete upstream payloads instead of manufacturing
            # zero-valued measurements that could be mistaken for observations.
            weather_rows = data["weather"]
            weather_block = weather_rows[0]
            main = data["main"]
            wind = data["wind"]
            sys_block = data["sys"]
            coord = data["coord"]
            required = (
                data["name"], sys_block["country"], coord["lat"], coord["lon"],
                main["temp"], main["feels_like"], main["temp_min"],
                main["temp_max"], main["humidity"], main["pressure"],
                wind["speed"], weather_block["description"],
                sys_block["sunrise"], sys_block["sunset"], data["dt"],
            )
            if not weather_rows or any(value is None for value in required):
                raise ValueError("Required weather fields are missing")
            clouds = data.get("clouds", {})

            return CurrentWeatherResponse(
                location=LocationInfo(
                    name=data.get("name", "Unknown"),
                    country=sys_block.get("country", "??"),
                    latitude=coord.get("lat", 0.0),
                    longitude=coord.get("lon", 0.0),
                ),
                weather=WeatherCondition(
                    temperature=main.get("temp", 0.0),
                    feels_like=main.get("feels_like", 0.0),
                    temp_min=main.get("temp_min", 0.0),
                    temp_max=main.get("temp_max", 0.0),
                    humidity=main.get("humidity", 0),
                    pressure=main.get("pressure", 0),
                    wind_speed=wind.get("speed", 0.0),
                    wind_direction=wind.get("deg"),
                    wind_gust=wind.get("gust"),
                    visibility=data.get("visibility"),
                    cloudiness=clouds.get("all"),
                    description=weather_block["description"],
                    icon=weather_block.get("icon"),
                ),
                sun=SunInfo(
                    sunrise=datetime.fromtimestamp(
                        sys_block["sunrise"], tz=timezone.utc
                    ),
                    sunset=datetime.fromtimestamp(
                        sys_block["sunset"], tz=timezone.utc
                    ),
                ),
                source=_PROVIDER_NAME,
                observed_at=datetime.fromtimestamp(
                    data["dt"], tz=timezone.utc
                ),
            )
        except Exception as exc:
            logger.error(
                "Failed to normalize weather data",
                extra={"error_type": type(exc).__name__},
                exc_info=True,
            )
            raise WeatherProviderError(
                detail="Failed to process weather provider response.",
                status_code=502,
            )
