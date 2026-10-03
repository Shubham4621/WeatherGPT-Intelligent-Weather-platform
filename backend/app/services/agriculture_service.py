"""Weather-grounded, deterministic farm decision support."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.schemas.agriculture import (
    AgricultureActivity, AgricultureAdviceResponse, AgricultureEvidence, AgricultureRecommendation,
    AgricultureRequest, StationObservation,
)
from app.services.historical_weather_service import HistoricalWeatherService, ImdClimatologyService
from app.services.imd_alert_service import AlertProviderUnavailable, ImdAlertService, UnsupportedAlertLocation
from app.services.imd_station_service import latest_station_observations, nearest_station, station_metadata, station_quality_report
from app.services.location_service import LocationResolutionError, location_service
from app.services.nwp_service import NwpService
from app.services.weather_service import WeatherService


class AgricultureDecisionEngine:
    """Transparent heuristic rules; thresholds are WeatherGPT screening values, not official limits."""

    WIND_ELEVATED_KMH = 20.0
    WIND_HIGH_KMH = 35.0
    HEAT_ELEVATED_C = 35.0
    HEAT_HIGH_C = 40.0
    RAIN_SIGNAL_PROBABILITY_PCT = 60.0
    NWP_RAIN_CONCERN_MM = 25.0
    NWP_RAIN_HIGH_MM = 50.0

    def evaluate(
        self,
        request: AgricultureRequest,
        *,
        current: dict[str, Any] | None,
        forecast: dict[str, Any] | None,
        nwp: dict[str, Any] | None,
        recent_station: StationObservation | None = None,
    ) -> AgricultureRecommendation:
        activity = request.activity
        evidence: list[AgricultureEvidence] = []
        limitations: list[str] = []
        sources: list[str] = []
        current_temp = None
        humidity = None
        current_wind_kmh = None
        observed_at = None
        if current:
            weather = current.get("weather", {})
            current_temp = weather.get("temperature")
            humidity = weather.get("humidity")
            current_wind_kmh = float(weather["wind_speed"]) * 3.6 if weather.get("wind_speed") is not None else None
            observed_at = current.get("observed_at")
            source = str(current.get("source", "OpenWeatherMap"))
            sources.append(source)
            if current_temp is not None:
                evidence.append(AgricultureEvidence(label="Current observed temperature", value=current_temp, unit="°C", source=source, valid_time=observed_at))
            if humidity is not None:
                evidence.append(AgricultureEvidence(label="Current observed relative humidity", value=humidity, unit="%", source=source, valid_time=observed_at))
            if current_wind_kmh is not None:
                evidence.append(AgricultureEvidence(label="Current observed wind speed", value=round(current_wind_kmh, 1), unit="km/h", source=source, valid_time=observed_at, detail="Converted from provider m/s to km/h."))
        periods = (forecast or {}).get("periods", [])
        forecast_source = (forecast or {}).get("source")
        if periods and forecast_source:
            sources.append(str(forecast_source))
        rain_probabilities = [float(item["rain_probability"]) for item in periods if item.get("rain_probability") is not None]
        forecast_winds = [float(item["wind_speed"]) * 3.6 for item in periods if item.get("wind_speed") is not None]
        forecast_max_temps = [float(item["temperature_max"]) for item in periods if item.get("temperature_max") is not None]
        rain_condition = any(any(token in str(item.get("description", "")).casefold() for token in ("rain", "shower", "drizzle")) for item in periods)
        max_rain_probability = max(rain_probabilities) if rain_probabilities else None
        max_forecast_wind = max(forecast_winds) if forecast_winds else None
        max_forecast_temp = max(forecast_max_temps) if forecast_max_temps else None
        if max_rain_probability is not None:
            evidence.append(AgricultureEvidence(label="Maximum operational forecast precipitation probability", value=round(max_rain_probability, 1), unit="%", source=str(forecast_source), valid_time=periods[-1].get("date")))
        if rain_condition and forecast_source:
            evidence.append(AgricultureEvidence(label="Operational forecast precipitation condition", value="rain indicated", source=str(forecast_source), valid_time=periods[-1].get("date")))
        if max_forecast_wind is not None:
            evidence.append(AgricultureEvidence(label="Maximum operational forecast wind speed", value=round(max_forecast_wind, 1), unit="km/h", source=str(forecast_source), valid_time=periods[-1].get("date"), detail="Converted from provider m/s to km/h."))
        if max_forecast_temp is not None:
            evidence.append(AgricultureEvidence(label="Maximum operational forecast temperature", value=round(max_forecast_temp, 1), unit="°C", source=str(forecast_source), valid_time=periods[-1].get("date")))

        points = (nwp or {}).get("points", [])
        nwp_rains = [float(point["precipitation_since_initialization_mm"]) for point in points if point.get("precipitation_since_initialization_mm") is not None]
        nwp_winds = [float(point["wind_speed_ms"]) * 3.6 for point in points if point.get("wind_speed_ms") is not None]
        nwp_source = (nwp or {}).get("source")
        if points and nwp_source:
            sources.append(str(nwp_source))
        max_nwp_rain = max(nwp_rains) if nwp_rains else None
        has_rain_forecast = max_rain_probability is not None or rain_condition
        has_weather_forecast = has_rain_forecast or max_forecast_temp is not None or max_forecast_wind is not None
        if max_nwp_rain is not None:
            last_valid = points[-1].get("forecast_time")
            run = (nwp or {}).get("initialization_time")
            evidence.append(AgricultureEvidence(label="GFS precipitation accumulated since model initialization", value=round(max_nwp_rain, 2), unit="mm", source=str(nwp_source), valid_time=last_valid, detail=f"Accumulation period starts at model run {run}; this is not a daily rainfall amount."))
        if nwp_winds:
            evidence.append(AgricultureEvidence(label="GFS maximum point wind speed", value=round(max(nwp_winds), 1), unit="km/h", source=str(nwp_source), valid_time=points[-1].get("forecast_time"), detail="Converted from model m/s; point guidance only."))

        if recent_station is not None and recent_station.rainfall_mm is not None:
            age = datetime.now(timezone.utc) - recent_station.observed_at
            if age <= timedelta(hours=72) and not recent_station.quality_flags:
                evidence.append(AgricultureEvidence(label="Recent IMD station rainfall", value=recent_station.rainfall_mm, unit="mm", source=f"{recent_station.source} · {recent_station.dataset}", valid_time=recent_station.observed_at))
                sources.append(recent_station.source)
            else:
                limitations.append("The latest local DSP station observation is stale or has quality flags and was excluded from current decision rules.")

        temp = max([value for value in (current_temp, max_forecast_temp) if value is not None], default=None)
        wind = max([value for value in (current_wind_kmh, max_forecast_wind, max(nwp_winds, default=None)) if value is not None], default=None)
        wet_signal = (max_rain_probability is not None and max_rain_probability >= self.RAIN_SIGNAL_PROBABILITY_PCT) or rain_condition or (max_nwp_rain is not None and max_nwp_rain >= self.NWP_RAIN_CONCERN_MM)
        sources = list(dict.fromkeys(sources))
        limitations.extend([
            "WeatherGPT weather-based decision support only; not an official agricultural department instruction.",
            "No soil-moisture observation or crop-specific agronomic rule was available; inspect field conditions and follow local agricultural guidance.",
        ])
        if request.crop:
            limitations.append(f"Crop '{request.crop}' was recorded as context only; no crop-specific rule was applied.")

        if activity == AgricultureActivity.SPRAYING:
            if not has_weather_forecast and current_wind_kmh is None:
                condition, text, confidence = "insufficient_data", "Insufficient forecast wind and rainfall data to assess weather conditions for spraying.", "low"
            elif wet_signal or (wind is not None and wind >= self.WIND_HIGH_KMH) or (temp is not None and temp >= self.HEAT_ELEVATED_C):
                condition, text, confidence = "unfavorable_weather_signal", "Rain potential, strong wind, or high temperature appears in the available data; consider postponing and follow product-label and local safety guidance.", "moderate"
            elif wind is not None and wind >= self.WIND_ELEVATED_KMH:
                condition, text, confidence = "wind_caution", "Forecast wind may increase drift risk; check local conditions and product guidance before spraying.", "moderate"
            elif has_weather_forecast or current_wind_kmh is not None:
                condition, text, confidence = "no_strong_weather_signal", "No strong rain or wind signal was found in the available forecast; verify field conditions and product guidance before spraying.", "low"
            else:
                condition, text, confidence = "insufficient_data", "Insufficient data to assess spraying weather conditions.", "low"
        elif activity == AgricultureActivity.IRRIGATION:
            if wet_signal:
                condition, text, confidence = "rain_may_reduce_need", "Forecast or GFS output indicates rain potential that may reduce immediate irrigation need; check soil moisture and the crop's water needs before deciding.", "moderate"
            elif temp is not None or recent_station is not None:
                condition, text, confidence = "monitor_soil_moisture", "No sufficient soil-moisture or recent-rainfall measurement is available. Monitor field soil moisture; irrigation may be needed depending on crop and field conditions.", "low"
            else:
                condition, text, confidence = "insufficient_data", "Insufficient recent rainfall and forecast data for irrigation guidance.", "low"
        elif activity == AgricultureActivity.SOWING:
            if not periods or (not has_rain_forecast and max_forecast_temp is None):
                condition, text, confidence = "insufficient_data", "Forecast rainfall and temperature context is unavailable for sowing guidance.", "low"
            elif wet_signal:
                condition, text, confidence = "wet_weather_signal", "Recent-period forecast data indicates wet-weather potential. Conditions may be suitable for sowing only if crop-specific soil moisture and field conditions are also suitable.", "moderate"
            else:
                condition, text, confidence = "no_rain_signal", "The available forecast has no strong rain signal. Check seedbed moisture and crop-specific local guidance before sowing.", "low"
        elif activity == AgricultureActivity.HARVESTING:
            if not periods or (not has_rain_forecast and max_forecast_temp is None):
                condition, text, confidence = "insufficient_data", "Forecast rainfall context is unavailable for harvesting guidance.", "low"
            elif wet_signal:
                condition, text, confidence = "rainfall_concern", "Upcoming rainfall potential may affect harvesting and field access; consider crop maturity and actual field conditions.", "moderate"
            else:
                condition, text, confidence = "no_strong_rain_signal", "No strong rainfall signal was identified in the available forecast; assess crop maturity and field conditions.", "low"
        elif activity == AgricultureActivity.FIELD_OPERATIONS:
            if not periods or not has_weather_forecast:
                condition, text, confidence = "insufficient_data", "Forecast weather context is unavailable for field-operation guidance.", "low"
            elif wet_signal or (wind is not None and wind >= self.WIND_ELEVATED_KMH):
                condition, text, confidence = "weather_caution", "Rain potential or elevated wind may affect field operations; check local field access and conditions.", "moderate"
            else:
                condition, text, confidence = "no_strong_weather_signal", "No strong rain or wind signal was identified for field operations; verify local field conditions.", "low"
        elif activity == AgricultureActivity.HEAT_STRESS:
            if temp is None:
                condition, text, confidence = "insufficient_data", "Temperature data is unavailable; crop/weather heat concern was not assessed.", "low"
            elif temp >= self.HEAT_HIGH_C:
                condition, text, confidence = "high_weather_heat_concern", "High air temperature indicates elevated crop/weather heat concern. Consider timing work for cooler periods and monitor crops; this is not a crop diagnosis.", "moderate"
            elif temp >= self.HEAT_ELEVATED_C:
                condition, text, confidence = "moderate_weather_heat_concern", "Warm air temperature indicates a moderate crop/weather heat concern. Monitor crops and local field conditions.", "moderate"
            else:
                condition, text, confidence = "no_threshold_exceeded", "The available temperature data did not cross the WeatherGPT heat-screening thresholds; crop-specific heat response is not assessed.", "low"
        elif activity == AgricultureActivity.HEAVY_RAIN:
            if max_nwp_rain is None and max_rain_probability is None and not rain_condition:
                condition, text, confidence = "insufficient_data", "Rainfall amount/probability information is unavailable; heavy-rain concern was not assessed.", "low"
            elif max_nwp_rain is not None and max_nwp_rain >= self.NWP_RAIN_HIGH_MM:
                condition, text, confidence = "high_weather_rainfall_concern", "GFS shows a high accumulated-rainfall concern over its returned run-to-valid period; monitor drainage and field access. This is model output, not an official warning.", "moderate"
            elif wet_signal:
                condition, text, confidence = "rainfall_concern", "The available forecast/model output indicates rainfall potential; monitor drainage and field access. Actual waterlogging has not been observed.", "low"
            else:
                condition, text, confidence = "no_strong_rain_signal", "No strong rainfall signal was found in the returned data; this does not establish that field waterlogging risk is zero.", "low"
        elif activity == AgricultureActivity.WIND_RISK:
            if wind is None:
                condition, text, confidence = "insufficient_data", "Validated wind-speed data is unavailable; wind concern was not assessed.", "low"
            elif wind >= self.WIND_HIGH_KMH:
                condition, text, confidence = "high_weather_wind_concern", "Wind speed exceeds the WeatherGPT high-concern screening value; protect light materials and check exposed field conditions.", "moderate"
            elif wind >= self.WIND_ELEVATED_KMH:
                condition, text, confidence = "elevated_weather_wind_concern", "Wind speed exceeds the WeatherGPT elevated-concern screening value; use care with exposed field work.", "moderate"
            else:
                condition, text, confidence = "low_weather_wind_concern", "Returned wind speed is below WeatherGPT screening values; no wind direction is inferred.", "low"
        else:
            if not periods and current is None and not points:
                condition, text, confidence = "insufficient_data", "Current, forecast, and NWP weather data are unavailable; no agriculture recommendation can be grounded.", "low"
            elif wet_signal:
                condition, text, confidence = "rainfall_caution", "Available forecast/model output indicates rainfall potential; consider how this may affect planned farm activity and check field conditions.", "low"
            else:
                condition, text, confidence = "weather_context_available", "Weather context is available. Match planned farm work to actual field, crop, and soil conditions.", "low"
        if not evidence:
            confidence = "low"
            if condition not in {"insufficient_data"}:
                condition = "insufficient_data"
                text = "No validated measurements are available to support this agriculture recommendation."
        valid_period = "Forecast periods returned by the operational provider and valid times returned by the GFS model; observation timestamps are shown with each evidence item."
        if nwp and nwp.get("initialization_time"):
            valid_period += f" GFS run: {nwp['initialization_time']}."
        return AgricultureRecommendation(activity=activity, condition=condition, recommendation=text,
            evidence=evidence, sources=sources, valid_period=valid_period, confidence=confidence,
            limitations=list(dict.fromkeys(limitations)))


class AgricultureIntelligenceService:
    def __init__(self, weather: WeatherService | None = None, nwp: NwpService | None = None,
                 history: HistoricalWeatherService | None = None, climatology: ImdClimatologyService | None = None,
                 alerts: ImdAlertService | None = None):
        self.weather = weather or WeatherService()
        self.nwp = nwp or NwpService()
        self.history = history or HistoricalWeatherService()
        self.climatology = climatology or ImdClimatologyService()
        self.alerts = alerts or ImdAlertService()
        self.engine = AgricultureDecisionEngine()

    async def advise(self, request: AgricultureRequest) -> AgricultureAdviceResponse:
        if request.station_id:
            meta = station_metadata(request.station_id)
            if meta is None:
                recommendation = AgricultureRecommendation(activity=request.activity, condition="insufficient_data",
                    recommendation=f"IMD station {request.station_id} is not configured; station-based guidance is unavailable.",
                    confidence="low", limitations=["No station metadata or coordinates were assumed."])
                return AgricultureAdviceResponse(status="unavailable", location={"station_id": request.station_id, "status": "station_not_configured"}, recommendation=recommendation, data_quality={"location": "station_not_configured"})
            resolved = location_service.from_coordinates(meta.latitude, meta.longitude, meta.station_name).model_copy(update={
                "city": meta.station_name, "district": meta.district, "state": meta.state, "country": meta.country,
                "source": meta.source, "resolution_method": "configured_reference"})
        elif request.city:
            try:
                resolved = await location_service.resolve(request.city)
            except LocationResolutionError as exc:
                from app.schemas.agriculture import AgricultureEvidence
                recommendation = AgricultureRecommendation(activity=request.activity, condition="insufficient_data",
                    recommendation=f"Location could not be resolved ({exc.status}); weather-based agricultural guidance is unavailable.",
                    confidence="low", limitations=["No location or weather values were assumed."])
                return AgricultureAdviceResponse(status="unavailable", location={"query": request.city, "status": exc.status}, recommendation=recommendation,
                    data_quality={"location": exc.status})
        else:
            resolved = location_service.from_coordinates(request.latitude, request.longitude)
        lat, lon = resolved.latitude, resolved.longitude
        current_task = self.weather.get_current_weather_by_coords(lat, lon)
        forecast_task = self.weather.get_forecast_by_coords(lat, lon)
        nwp_task = self.nwp.forecast(lat, lon, days=2)
        history_task = self.history.get_history(resolved.city or resolved.query, date.today() - timedelta(days=7), date.today(), lat, lon)
        results = await asyncio.gather(current_task, forecast_task, nwp_task, history_task, return_exceptions=True)
        current_result, forecast_result, nwp_result, history_result = results
        current = None if isinstance(current_result, Exception) else current_result.model_dump(mode="json")
        forecast = None if isinstance(forecast_result, Exception) else {
            "source": forecast_result.source,
            "periods": [item.model_dump(mode="json") for item in forecast_result.forecast[:3]],
            "forecasted_at": forecast_result.forecasted_at.isoformat(),
        }
        nwp = None if isinstance(nwp_result, Exception) or nwp_result.status not in {"available", "partial"} else nwp_result.model_dump(mode="json")
        matched = nearest_station(lat, lon)
        station_info: dict[str, Any] | None = None
        recent_station = None
        if matched:
            meta, distance_km = matched
            latest = latest_station_observations(meta.station_id)
            recent_station = latest.get("daily")
            quality_report = station_quality_report(meta.station_id)
            quality = {key: value for key, value in ((key, obs.quality_flags) for key, obs in latest.items() if obs) if value}
            observation_time = recent_station.observed_at if recent_station else None
            age_hours = (datetime.now(timezone.utc) - observation_time).total_seconds() / 3600 if observation_time else None
            station_info = {
                "metadata": meta.model_dump(mode="json"), "distance_km": round(distance_km, 3),
                "retrieval_mode": "validated local IMD DSP dataset; not a live DSP session",
            "data_status": "available" if observation_time and age_hours is not None and 0 <= age_hours <= 72 else "stale" if observation_time else "unavailable",
                "latest_daily_observation": recent_station.model_dump(mode="json") if recent_station else None,
                "latest_synoptic_observation": latest["synoptic"].model_dump(mode="json") if latest.get("synoptic") else None,
                "quality_flags": quality,
                "quality_summary": ({kind: {key: value.get(key) for key in ("row_count", "normalized_row_count", "coverage_start", "coverage_end", "duplicate_records", "missing_dates_or_slots_between_coverage", "invalid_date_or_station_rows", "missing_values_by_parameter", "invalid_values_by_parameter")} for kind, value in quality_report.datasets.items()} if quality_report else {}),
            }
        try:
            alerts = await self.alerts.get_alerts(resolved.district or resolved.city or resolved.query)
            warning_context = {"status": "available", "source": alerts.source, "district": alerts.district,
                "active_days": [day.model_dump(mode="json") for day in alerts.forecast_days if day.is_active]}
        except UnsupportedAlertLocation:
            warning_context = {"status": "location_mapping_unresolved", "source": "India Meteorological Department (IMD)"}
        except AlertProviderUnavailable:
            warning_context = {"status": "unavailable", "source": "India Meteorological Department (IMD)"}
        history_context = None if isinstance(history_result, Exception) else history_result.model_dump(mode="json")
        if history_context and history_context.get("records"):
            history_context = {"status": history_context.get("status"), "source": history_context.get("source"), "record_count": len(history_context["records"]), "period": {"start": str(date.today() - timedelta(days=7)), "end": str(date.today())}}
        normal = self.climatology.monthly_normal("rainfall", date.today().month, lat, lon)
        climate_context = {"status": normal.get("status"), "baseline": normal.get("baseline"), "normal_monthly_rainfall_mm": normal.get("normal"), "source": normal.get("source"), "resolution": normal.get("resolution")}
        recommendation = self.engine.evaluate(request, current=current, forecast=forecast, nwp=nwp, recent_station=recent_station)
        statuses = ["available" if item is not None else "unavailable" for item in (current, forecast, nwp)]
        status = "available" if all(value == "available" for value in statuses) else "partial" if any(value == "available" for value in statuses) else "insufficient_data"
        if recommendation.condition == "insufficient_data":
            status = "insufficient_data"
        quality_summary = {
            "current_weather": "available" if current else "unavailable",
            "operational_forecast": "available" if forecast else "unavailable",
            "nwp": "available" if nwp else (nwp_result.reason if not isinstance(nwp_result, Exception) else "unavailable"),
            "station": station_info["data_status"] if station_info else "no_station_within_50_km",
            "historical": (history_context or {}).get("status", "unavailable"),
            "climatology": climate_context.get("status", "unavailable"),
            "official_warning": warning_context["status"],
        }
        return AgricultureAdviceResponse(status=status, location=resolved.model_dump(mode="json"), station=station_info,
            current_weather=current, forecast_context=forecast, nwp_context=nwp, historical_context=history_context,
            climatology_context=climate_context, official_warning=warning_context, recommendation=recommendation,
            data_quality=quality_summary, limitations=recommendation.limitations)

