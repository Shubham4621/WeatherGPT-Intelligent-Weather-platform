"""Typed weather tools built on the existing provider service."""

from app.schemas.weather import CurrentWeatherResponse
from app.schemas.weather import ForecastResponse
from app.services.weather_service import WeatherService
from app.schemas.weather import WeatherAlertsResponse
from app.services.imd_alert_service import ImdAlertService
from app.services.advisory_service import WeatherAdvisoryService
from app.schemas.chat import AdvisoryActivity
from app.schemas.weather import WeatherAdvisoryResponse
from app.services.historical_weather_service import HistoricalWeatherService, LocalImdGridHistoricalProvider, HistoricalDataset, ImdClimatologyService, resolve_historical_coordinates
from app.services.location_service import LocationResolutionError, location_service
from app.services.nwp_service import NwpService
from app.schemas.nwp import NwpForecastResponse
from app.schemas.agriculture import AgricultureActivity, AgricultureAdviceResponse, AgricultureRequest
from app.services.agriculture_service import AgricultureIntelligenceService
from datetime import date
import re
from app.core.exceptions import WeatherAPIError, WeatherProviderError
from app.services.imd_alert_service import AlertProviderUnavailable, UnsupportedAlertLocation

_DEFAULT_WEATHER_SERVICE = WeatherService()
_DEFAULT_ALERT_SERVICE = ImdAlertService()
_DEFAULT_HISTORY_SERVICE = HistoricalWeatherService(LocalImdGridHistoricalProvider())
_CLIMATOLOGY_SERVICE = ImdClimatologyService()
_NWP_SERVICE = NwpService()
_AGRICULTURE_SERVICE = AgricultureIntelligenceService()


async def _resolve_city_coordinates(city: str) -> tuple[float, float]:
    try:
        resolved = await location_service.resolve(city)
        return resolved.latitude, resolved.longitude
    except LocationResolutionError as exc:
        status = 404 if exc.status == "location_not_found" else 422 if exc.status == "location_ambiguous" else 503
        raise WeatherAPIError(detail=f"{exc.status}: {exc}", status_code=status) from exc


async def get_nwp_forecast(location: str, days: int = 5, nwp_service: NwpService | None = None) -> NwpForecastResponse:
    """Resolve a chat location using Phase 13 and query GFS without forecast fallback."""
    normalized = location.strip()
    try:
        parts = normalized.split(",")
        if len(parts) == 2:
            try:
                resolved = location_service.from_coordinates(float(parts[0]), float(parts[1]), normalized)
            except ValueError:
                resolved = None
        else:
            resolved = None
        if resolved is None:
            try:
                resolved = await location_service.resolve(normalized)
            except LocationResolutionError as exc:
                configured = resolve_historical_coordinates(normalized)
                if not configured or exc.status != "location_provider_unavailable":
                    raise
                latitude, longitude = configured
                resolved = location_service.from_coordinates(latitude, longitude, normalized)
                resolved = resolved.model_copy(update={"city": normalized, "resolution_method": "configured_reference", "source": "Configured WeatherGPT reference location"})
    except LocationResolutionError as exc:
        return NwpForecastResponse(status="unavailable", reason=f"nwp_{exc.status}")
    result = await (nwp_service or _NWP_SERVICE).forecast(resolved.latitude, resolved.longitude, days)
    location_data = {**(result.location or {}), **resolved.model_dump(mode="json")}
    return result.model_copy(update={"location": location_data})


async def get_historical_weather(city: str, start_date: date, end_date: date, history_service: HistoricalWeatherService | None = None) -> HistoricalDataset:
    try:
        resolved = await location_service.resolve(city)
        point = (resolved.latitude, resolved.longitude)
    except LocationResolutionError as exc:
        return HistoricalDataset(status="unavailable", availability_status=exc.status, location=city, reason=str(exc))
    return await (history_service or _DEFAULT_HISTORY_SERVICE).get_history(city, start_date, end_date, *point)


async def get_climatology_normal(city: str, month: int, variable: str = "rainfall", latitude: float | None = None, longitude: float | None = None) -> dict:
    if latitude is None or longitude is None:
        try:
            resolved = await location_service.resolve(city)
            point = (resolved.latitude, resolved.longitude)
        except LocationResolutionError as exc:
            return {"status": "unavailable", "availability_status": exc.status, "reason": str(exc)}
        if latitude is None or longitude is None:
            latitude, longitude = point
    return _CLIMATOLOGY_SERVICE.monthly_normal(variable, month, latitude, longitude)


async def get_current_weather(
    city: str,
    weather_service: WeatherService | None = None,
) -> CurrentWeatherResponse:
    """Return normalized current weather by delegating to WeatherService."""
    if weather_service is not None:
        return await weather_service.get_current_weather_by_city(city)
    latitude, longitude = await _resolve_city_coordinates(city)
    return await _DEFAULT_WEATHER_SERVICE.get_current_weather_by_coords(latitude, longitude)


async def get_forecast(city: str, weather_service: WeatherService | None = None) -> ForecastResponse:
    if weather_service is not None:
        return await weather_service.get_forecast_by_city(city)
    latitude, longitude = await _resolve_city_coordinates(city)
    return await _DEFAULT_WEATHER_SERVICE.get_forecast_by_coords(latitude, longitude)


async def get_weather_alerts(city: str, alert_service: ImdAlertService | None = None) -> WeatherAlertsResponse:
    service = alert_service or _DEFAULT_ALERT_SERVICE
    return await service.get_alerts(city)


async def get_weather_advisory(
    location: str,
    day_offset: int = 1,
    activity: AdvisoryActivity = AdvisoryActivity.GENERAL_PRECAUTION,
    weather_service: WeatherService | None = None,
    alert_service: ImdAlertService | None = None,
    advisory_service: WeatherAdvisoryService | None = None,
) -> WeatherAdvisoryResponse:
    weather = weather_service or _DEFAULT_WEATHER_SERVICE
    imd = alert_service or _DEFAULT_ALERT_SERVICE
    forecast = None
    alerts = None
    resolved_coordinates = None
    if weather_service is None:
        resolved_coordinates = await _resolve_city_coordinates(location)
    try:
        forecast = (await weather.get_forecast_by_city(location) if weather_service is not None
                   else await weather.get_forecast_by_coords(*resolved_coordinates))
    except (WeatherAPIError, WeatherProviderError):
        pass
    try:
        alerts = await imd.get_alerts(location)
        warning_status = "available"
    except UnsupportedAlertLocation:
        warning_status = "unsupported_location"
    except AlertProviderUnavailable:
        warning_status = "unavailable"
    return (advisory_service or WeatherAdvisoryService()).build(
        location=forecast.location.name if forecast else location.strip(),
        activity=activity,
        forecast=forecast,
        alerts=alerts,
        warning_status=warning_status,
        day_offset=day_offset,
    )


async def get_agriculture_advice(
    location: str,
    activity: AgricultureActivity = AgricultureActivity.GENERAL,
    agriculture_service: AgricultureIntelligenceService | None = None,
) -> AgricultureAdviceResponse:
    station_match = re.fullmatch(r"\s*station\s+([A-Za-z0-9_-]+)\s*", location, re.IGNORECASE)
    coordinate_match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", location)
    if station_match:
        request = AgricultureRequest(station_id=station_match.group(1), activity=activity)
    elif coordinate_match:
        request = AgricultureRequest(latitude=float(coordinate_match.group(1)), longitude=float(coordinate_match.group(2)), activity=activity)
    else:
        request = AgricultureRequest(city=location, activity=activity)
    return await (agriculture_service or _AGRICULTURE_SERVICE).advise(request)
