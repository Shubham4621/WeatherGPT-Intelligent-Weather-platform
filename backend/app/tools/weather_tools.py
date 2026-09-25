"""Typed weather tools built on the existing provider service."""

from app.schemas.weather import CurrentWeatherResponse
from app.schemas.weather import ForecastResponse
from app.services.weather_service import WeatherService
from app.schemas.weather import WeatherAlertsResponse
from app.services.imd_alert_service import ImdAlertService
from app.services.advisory_service import WeatherAdvisoryService
from app.schemas.chat import AdvisoryActivity
from app.schemas.weather import WeatherAdvisoryResponse
from app.core.exceptions import WeatherAPIError, WeatherProviderError
from app.services.imd_alert_service import AlertProviderUnavailable, UnsupportedAlertLocation

_DEFAULT_WEATHER_SERVICE = WeatherService()
_DEFAULT_ALERT_SERVICE = ImdAlertService()


async def get_current_weather(
    city: str,
    weather_service: WeatherService | None = None,
) -> CurrentWeatherResponse:
    """Return normalized current weather by delegating to WeatherService."""
    service = weather_service or _DEFAULT_WEATHER_SERVICE
    return await service.get_current_weather_by_city(city)


async def get_forecast(city: str, weather_service: WeatherService | None = None) -> ForecastResponse:
    service = weather_service or _DEFAULT_WEATHER_SERVICE
    return await service.get_forecast_by_city(city)


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
    try:
        forecast = await weather.get_forecast_by_city(location)
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
