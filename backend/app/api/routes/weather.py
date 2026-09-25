"""Weather API endpoints."""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.exceptions import WeatherAPIError
from app.core.logging import get_logger
from app.schemas.weather import CurrentWeatherResponse, ForecastResponse
from app.services.weather_service import WeatherService
from app.services.imd_alert_service import AlertProviderUnavailable, ImdAlertService, UnsupportedAlertLocation
from app.schemas.weather import WeatherAlertsResponse, WeatherAdvisoryResponse
from app.schemas.chat import AdvisoryActivity
from app.tools.weather_tools import get_weather_advisory

logger = get_logger(__name__)
router = APIRouter(prefix="/weather", tags=["Weather"])

weather_service = WeatherService()
imd_alert_service = ImdAlertService()


@router.get("/current", response_model=CurrentWeatherResponse)
async def get_current_weather(
    city: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
        description="City name (e.g. Dhule, Mumbai, Delhi)",
    ),
    lat: float | None = Query(
        default=None,
        ge=-90,
        le=90,
        description="Latitude in decimal degrees",
    ),
    lon: float | None = Query(
        default=None,
        ge=-180,
        le=180,
        description="Longitude in decimal degrees",
    ),
):
    """Get current weather for a location.

    Provide EITHER `city` OR both `lat` and `lon`.
    """
    # Validate that at least one location method is provided
    if city is None and (lat is None or lon is None):
        raise WeatherAPIError(
            detail="Provide either 'city' or both 'lat' and 'lon' query parameters.",
            status_code=400,
        )
    if city is not None and not city.strip():
        raise WeatherAPIError(detail="City must contain a location name.", status_code=400)

    logger.info(
        "Current weather request",
        extra={"city": city.strip() if city else f"{lat},{lon}"},
    )

    if city:
        return await weather_service.get_current_weather_by_city(city.strip())
    else:
        return await weather_service.get_current_weather_by_coords(lat, lon)


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(city: str = Query(..., min_length=1, max_length=100)):
    if not city.strip():
        raise WeatherAPIError(detail="City must contain a location name.", status_code=400)
    logger.info("Forecast request", extra={"city": city.strip()})
    return await weather_service.get_forecast_by_city(city.strip())


@router.get("/alerts", response_model=WeatherAlertsResponse)
async def get_weather_alerts(city: str = Query(..., min_length=1, max_length=100)):
    try:
        return await imd_alert_service.get_alerts(city)
    except UnsupportedAlertLocation:
        return JSONResponse(status_code=422, content={"error": "UNSUPPORTED_LOCATION", "message": "Official IMD warning lookup is not configured for this location."})
    except AlertProviderUnavailable:
        return JSONResponse(status_code=503, content={"error": "WEATHER_ALERT_PROVIDER_UNAVAILABLE", "message": "Official weather warning information is temporarily unavailable."})


@router.get("/advisory", response_model=WeatherAdvisoryResponse)
async def get_advisory(
    city: str = Query(..., min_length=1, max_length=100),
    day_offset: int = Query(default=1, ge=0, le=4),
    activity: AdvisoryActivity = Query(default=AdvisoryActivity.GENERAL_PRECAUTION),
):
    return await get_weather_advisory(city, day_offset, activity)
