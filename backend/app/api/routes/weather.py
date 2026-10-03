"""Weather API endpoints."""

from datetime import date
from calendar import monthrange
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
from app.services.historical_weather_service import HistoricalWeatherService, ImdClimatologyService, LocalImdGridHistoricalProvider, aggregate, linear_trend, monthly_aggregation, yearly_aggregation, resolve_historical_coordinates, rainfall_anomaly
from app.services.location_service import LocationResolutionError, location_service
from app.services.nwp_service import NwpService
from app.schemas.nwp import NwpForecastResponse
from app.schemas.rainfall_prediction import RainfallPredictionResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/weather", tags=["Weather"])
location_router = APIRouter(prefix="/location", tags=["Location"])

weather_service = WeatherService()
imd_alert_service = ImdAlertService()
historical_weather_service = HistoricalWeatherService(LocalImdGridHistoricalProvider())
imd_climatology_service = ImdClimatologyService()
nwp_service = NwpService()


@router.get("/history")
async def get_historical_weather(
    city: str | None = Query(default=None, min_length=1, max_length=100),
    start_date: date = Query(...),
    end_date: date = Query(...),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    compare_year: int | None = Query(default=None, ge=1901, le=2100),
    compare_start_date: date | None = Query(default=None),
    compare_end_date: date | None = Query(default=None),
):
    """Historical observations are sourced separately from current and forecast data."""
    if (city is None and lat is None) or (city is not None and not city.strip()) or ((lat is None) != (lon is None)):
        raise WeatherAPIError(detail="Provide a city or both lat and lon coordinates.", status_code=422)
    location = city.strip() if city else f"{lat},{lon}"
    if lat is None:
        try:
            resolved = await location_service.resolve(location)
            lat, lon = resolved.latitude, resolved.longitude
        except LocationResolutionError as exc:
            return {"status": "unavailable", "availability_status": exc.status, "location": location, "reason": str(exc), "records": []}
    if (compare_start_date is None) != (compare_end_date is None):
        raise WeatherAPIError(detail="Provide both compare_start_date and compare_end_date.", status_code=422)
    if compare_start_date and compare_end_date and compare_start_date > compare_end_date:
        raise WeatherAPIError(detail="Comparison start date must be on or before comparison end date.", status_code=422)
    try:
        result = await historical_weather_service.get_history(location, start_date, end_date, lat, lon)
    except ValueError as exc:
        raise WeatherAPIError(detail=f"Invalid date range: {exc}", status_code=422) from exc
    payload = result.model_dump(mode="json")
    if result.status in {"available", "partial"}:
        summary = aggregate(result.records)
        months = monthly_aggregation(result.records)
        years = yearly_aggregation(result.records)
        payload["summary"] = summary
        payload["monthly"] = months
        payload["yearly"] = years
        payload["analysis"] = {"observations": {"rainfall": "OBSERVATION", "temperature": "unavailable; validated Tmax/Tmin daily records are not installed"},
            "trends": {"rainfall_mm_per_year": linear_trend([(row["year"], row["total_rainfall"]) for row in years if row["complete_year"] and row["total_rainfall"] is not None])},
            "climatology": [], "comparisons": [], "extremes": {"wettest_observed_days": [{"date": row.date.isoformat(), "rainfall_mm": row.rainfall} for row in sorted((r for r in result.records if r.rainfall is not None), key=lambda r: r.rainfall, reverse=True)[:5]],
                "wettest_month": max((r for r in months if r["total_rainfall"] is not None), key=lambda r: r["total_rainfall"], default=None),
                "driest_month": min((r for r in months if r["total_rainfall"] is not None), key=lambda r: r["total_rainfall"], default=None)}}
        latitude = result.metadata.get("latitude")
        longitude = result.metadata.get("longitude")
        if latitude is not None and longitude is not None:
            seen_months = sorted({row["month_number"] for row in months})
            for month in seen_months:
                rainfall_normal = imd_climatology_service.monthly_normal("rainfall", month, latitude, longitude)
                tmax_normal = imd_climatology_service.monthly_normal("tmax", month, latitude, longitude)
                tmin_normal = imd_climatology_service.monthly_normal("tmin", month, latitude, longitude)
                observed = [row for row in months if row["month_number"] == month]
                for row in observed:
                    complete_month = row["record_count"] == monthrange(row["year"], month)[1] and row["rainfall_observation_count"] == row["record_count"]
                    anomaly_values = rainfall_anomaly(row["total_rainfall"] if complete_month else None, rainfall_normal.get("normal"))
                    comparison = {"kind": "ANOMALY", "year": row["year"], "month": month,
                        "observation": {"kind": "OBSERVATION", "rainfall_mm": row["total_rainfall"]},
                        "climatology": {"kind": "CLIMATOLOGY", "rainfall_mm": rainfall_normal.get("normal"), "baseline": "1991-2020"},
                        "observed_rainfall_mm": row["total_rainfall"], "normal_rainfall_mm": rainfall_normal.get("normal"),
                        "anomaly_rainfall_mm": anomaly_values["anomaly_rainfall_mm"], "anomaly_percent": anomaly_values["anomaly_percent"],
                        "status": anomaly_values["status"], "observation_days": row["rainfall_observation_count"], "expected_days": monthrange(row["year"], month)[1], "units": "mm"}
                    payload["analysis"]["comparisons"].append(comparison)
                payload["analysis"]["climatology"].append({"month": month, "rainfall": rainfall_normal, "tmax": tmax_normal, "tmin": tmin_normal})
        if compare_year is not None:
            first = next((row for row in years if row["year"] == compare_year), None)
            second = next((row for row in years if row["year"] == compare_year + 1), None)
            payload["analysis"]["comparisons"].append({"kind": "year_over_year", "first_year": compare_year, "second_year": compare_year + 1,
                "rainfall_difference_mm": round(second["total_rainfall"] - first["total_rainfall"], 2) if first and second and first["complete_year"] and second["complete_year"] and first["total_rainfall"] is not None and second["total_rainfall"] is not None else None,
                "status": "available" if first and second and first["complete_year"] and second["complete_year"] else "insufficient_data"})
        if compare_start_date and compare_end_date:
            other = await historical_weather_service.get_history(location, compare_start_date, compare_end_date, lat, lon)
            current_rainfall = summary.get("total_rainfall")
            other_rainfall = aggregate(other.records).get("total_rainfall") if other.status in {"available", "partial"} else None
            payload["analysis"]["comparisons"].append({"kind": "date_range", "first_period": {"start": start_date.isoformat(), "end": end_date.isoformat(), "observed_rainfall_mm": current_rainfall},
                "second_period": {"start": compare_start_date.isoformat(), "end": compare_end_date.isoformat(), "observed_rainfall_mm": other_rainfall},
                "difference_mm": round(current_rainfall - other_rainfall, 2) if current_rainfall is not None and other_rainfall is not None else None,
                "status": "available" if current_rainfall is not None and other_rainfall is not None else "insufficient_data"})
    return payload


@router.get("/climatology")
async def get_climatology(
    month: int = Query(..., ge=1, le=12),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    city: str | None = Query(default=None, min_length=1, max_length=100),
    variable: str | None = Query(default=None, pattern="^(rainfall|tmax|tmin)$"),
):
    if (lat is None) != (lon is None) or (lat is None and not city) or (lat is not None and city):
        raise WeatherAPIError(detail="Provide a city or both lat and lon coordinates.", status_code=422)
    if city:
        try:
            resolved = await location_service.resolve(city)
            lat, lon = resolved.latitude, resolved.longitude
        except LocationResolutionError as exc:
            return {"status": "unavailable", "kind": "CLIMATOLOGY", "availability_status": exc.status, "reason": str(exc), "normals": []}
    variables = [variable] if variable else ["rainfall", "tmax", "tmin"]
    normals = [imd_climatology_service.monthly_normal(item, month, lat, lon) for item in variables]
    statuses = {normal.get("status") for normal in normals}
    status = "available" if statuses == {"available"} else "unavailable" if statuses <= {"unavailable", "no_data"} else "partial"
    return {"status": status, "kind": "CLIMATOLOGY", "baseline": "1991-2020", "normals": normals}


@location_router.get("/resolve")
async def resolve_location(q: str = Query(..., min_length=1, max_length=150)):
    try:
        return (await location_service.resolve(q)).model_dump(mode="json")
    except LocationResolutionError as exc:
        return JSONResponse(status_code=422 if exc.status in {"location_not_found", "location_ambiguous"} else 503,
            content={"status": exc.status, "query": q, "message": str(exc)})


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
    if city is not None and (lat is not None or lon is not None):
        raise WeatherAPIError(detail="Provide either a city or coordinates, not both.", status_code=400)
    if city is not None and not city.strip():
        raise WeatherAPIError(detail="City must contain a location name.", status_code=400)

    logger.info(
        "Current weather request",
        extra={"city": city.strip() if city else f"{lat},{lon}"},
    )

    if city:
        if weather_service.api_key:
            try:
                resolved = await location_service.resolve(city.strip())
            except LocationResolutionError as exc:
                return JSONResponse(status_code=422 if exc.status in {"location_not_found", "location_ambiguous"} else 503,
                    content={"status": exc.status, "query": city.strip(), "message": str(exc)})
            return await weather_service.get_current_weather_by_coords(resolved.latitude, resolved.longitude)
        return await weather_service.get_current_weather_by_city(city.strip())
    else:
        return await weather_service.get_current_weather_by_coords(lat, lon)


@router.get("/forecast", response_model=ForecastResponse)
async def get_forecast(city: str | None = Query(default=None, min_length=1, max_length=100),
                       lat: float | None = Query(default=None, ge=-90, le=90),
                       lon: float | None = Query(default=None, ge=-180, le=180)):
    if (city is None and (lat is None or lon is None)) or ((lat is None) != (lon is None)) or (city and lat is not None):
        raise WeatherAPIError(detail="Provide a city or both lat and lon coordinates.", status_code=422)
    if city:
        logger.info("Forecast request", extra={"city": city.strip()})
        if weather_service.api_key:
            try:
                resolved = await location_service.resolve(city.strip())
            except LocationResolutionError as exc:
                return JSONResponse(status_code=422 if exc.status in {"location_not_found", "location_ambiguous"} else 503,
                    content={"status": exc.status, "query": city.strip(), "message": str(exc)})
            return await weather_service.get_forecast_by_coords(resolved.latitude, resolved.longitude)
        return await weather_service.get_forecast_by_city(city.strip())
    return await weather_service.get_forecast_by_coords(lat, lon)


@router.get("/nwp", response_model=NwpForecastResponse)
async def get_nwp_forecast(
    city: str | None = Query(default=None, min_length=1, max_length=100),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    days: int = Query(default=5, ge=1, le=5),
):
    """Return separate NOAA GFS model guidance; never falls back to another forecast source."""
    if (city is None and (lat is None or lon is None)) or ((lat is None) != (lon is None)) or (city and lat is not None):
        raise WeatherAPIError(detail="Provide a city or both latitude and longitude coordinates.", status_code=422)
    if city:
        try:
            resolved = await location_service.resolve(city)
            lat, lon = resolved.latitude, resolved.longitude
            resolved_location = resolved.model_dump(mode="json") if hasattr(resolved, "model_dump") else {"query": city, "latitude": lat, "longitude": lon}
        except LocationResolutionError as exc:
            configured = resolve_historical_coordinates(city)
            if configured and exc.status == "location_provider_unavailable":
                lat, lon = configured
                resolved_location = {"query": city, "latitude": lat, "longitude": lon, "source": "configured location reference", "resolution_method": "configured_reference"}
            else:
                reason = {"location_not_found": "nwp_location_not_found", "location_ambiguous": "nwp_location_ambiguous"}.get(exc.status, "nwp_location_provider_unavailable")
                return NwpForecastResponse(status="unavailable", location={"query": city}, reason=reason)
    else:
        resolved_location = {"latitude": lat, "longitude": lon, "resolution_method": "coordinates"}
    try:
        result = await nwp_service.forecast(lat, lon, days)
        result.location = resolved_location
        from datetime import datetime, timezone
        result.retrieved_at = result.retrieved_at or datetime.now(timezone.utc)
        return result
    except ValueError as exc:
        raise WeatherAPIError(detail=f"Invalid NWP request: {exc}", status_code=422) from exc


@router.get("/alerts", response_model=WeatherAlertsResponse)
async def get_weather_alerts(city: str = Query(..., min_length=1, max_length=100)):
    try:
        return await imd_alert_service.get_alerts(city)
    except UnsupportedAlertLocation:
        return JSONResponse(status_code=422, content={"error": "UNSUPPORTED_LOCATION", "message": "Official IMD warning lookup is not configured for this location."})
    except AlertProviderUnavailable as exc:
        reason = str(exc) or "provider_unavailable"
        return JSONResponse(status_code=503, content={"error": "WEATHER_ALERT_PROVIDER_UNAVAILABLE", "status": "unavailable", "source": "IMD", "reason": reason, "message": "Official weather warning information is temporarily unavailable."})


@router.get("/advisory", response_model=WeatherAdvisoryResponse)
async def get_advisory(
    city: str = Query(..., min_length=1, max_length=100),
    day_offset: int = Query(default=1, ge=0, le=4),
    activity: AdvisoryActivity = Query(default=AdvisoryActivity.GENERAL_PRECAUTION),
):
    return await get_weather_advisory(city, day_offset, activity)


@router.get("/rainfall-prediction", response_model=RainfallPredictionResponse)
async def get_rainfall_prediction(
    lat: float = Query(..., ge=-90, le=90, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude in decimal degrees"),
    horizon: int = Query(default=1, ge=1, le=1, description="Prediction horizon in days; currently 1"),
):
    """Return a one-day WeatherGPT model estimate from the local validated IMD archive."""
    from app.services.rainfall_prediction import predict_next_day

    try:
        return predict_next_day(lat, lon, horizon)
    except FileNotFoundError as exc:
        raise WeatherAPIError(detail="Historical rainfall prediction model or validated data is unavailable.", status_code=503) from exc
    except ValueError as exc:
        raise WeatherAPIError(detail=f"Rainfall prediction unavailable: {exc}", status_code=422) from exc
