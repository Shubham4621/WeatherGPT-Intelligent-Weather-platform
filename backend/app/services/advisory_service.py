"""Deterministic, source-labelled decision support built only from supplied data."""

from datetime import datetime, timedelta, timezone

from app.schemas.chat import AdvisoryActivity
from app.schemas.weather import (
    AdvisoryFactor, AdvisoryRisk, AlertDay, ForecastResponse,
    OfficialWarningSummary, WeatherAdvisoryResponse, WeatherAlertsResponse,
)


class WeatherAdvisoryService:
    """Apply transparent condition thresholds; never manufacture an official hazard."""

    # Rules use OWM values only to describe weather conditions, not government hazards.
    RAIN_CHANCE_NOTICE = 30
    RAIN_CHANCE_HIGH = 60
    MODERATE_WIND_MPS = 8
    STRONG_WIND_MPS = 12
    HIGH_TEMPERATURE_C = 35
    VERY_HIGH_TEMPERATURE_C = 40

    def build(
        self,
        location: str,
        activity: AdvisoryActivity,
        forecast: ForecastResponse | None,
        alerts: WeatherAlertsResponse | None,
        warning_status: str,
        day_offset: int = 1,
    ) -> WeatherAdvisoryResponse:
        factors: list[AdvisoryFactor] = []
        recommendations: list[str] = []
        selected = None
        date = None
        if forecast and forecast.forecast and day_offset < len(forecast.forecast):
            selected = forecast.forecast[day_offset]
            date = selected.date
            description = selected.description.casefold()
            if selected.rain_probability is not None and selected.rain_probability >= self.RAIN_CHANCE_NOTICE:
                likelihood = "High" if selected.rain_probability >= self.RAIN_CHANCE_HIGH else "Elevated"
                factors.append(AdvisoryFactor(code="PRECIPITATION_CHANCE", detail=f"{likelihood} precipitation probability ({selected.rain_probability:.0f}%)", source=forecast.source))
                recommendations.append("Carry rain protection." if selected.rain_probability >= self.RAIN_CHANCE_HIGH else "Consider carrying rain protection.")
            if "rain" in description or "drizzle" in description or "shower" in description:
                if not any(f.code == "PRECIPITATION_CHANCE" for f in factors):
                    factors.append(AdvisoryFactor(code="RAIN_CONDITION", detail=f"Forecast condition: {selected.description}", source=forecast.source))
                if not recommendations:
                    recommendations.append("Consider flexible plans for outdoor activities.")
            if selected.wind_speed is not None and selected.wind_speed >= self.MODERATE_WIND_MPS:
                level = "Strong" if selected.wind_speed >= self.STRONG_WIND_MPS else "Elevated"
                factors.append(AdvisoryFactor(code="WIND", detail=f"{level} forecast wind ({selected.wind_speed:.1f} m/s)", source=forecast.source))
                recommendations.append("Use care around exposed outdoor areas if winds increase.")
            if selected.temperature_max >= self.HIGH_TEMPERATURE_C:
                level = "Very high" if selected.temperature_max >= self.VERY_HIGH_TEMPERATURE_C else "High"
                factors.append(AdvisoryFactor(code="TEMPERATURE", detail=f"{level} forecast maximum temperature ({selected.temperature_max:.1f}°C)", source=forecast.source))
                recommendations.append("Plan breaks in shade and drink water during outdoor activity.")
            if selected.humidity is not None and selected.humidity >= 80:
                factors.append(AdvisoryFactor(code="HUMIDITY", detail=f"High forecast humidity ({selected.humidity}%)", source=forecast.source))

        matching_alerts: list[AlertDay] = []
        if alerts:
            if date:
                matching_alerts = [day for day in alerts.forecast_days if day.date.date() == date.date() and day.is_active]
            else:
                matching_alerts = [day for day in alerts.forecast_days if day.is_active]
        warning_summaries = []
        for day in matching_alerts:
            labels = [warning.warning_type for warning in day.warnings]
            warning_summaries.extend(labels)
            factors.append(AdvisoryFactor(code="OFFICIAL_IMD_WARNING", detail=f"IMD reports: {', '.join(labels)}; IMD level {day.severity or 'not specified'}", source=alerts.source))
        official_warning = None
        if alerts and matching_alerts:
            first = matching_alerts[0]
            official_warning = OfficialWarningSummary(warnings=warning_summaries, severity=first.severity, date=first.date, source=alerts.source, source_url=alerts.source_url)
            recommendations.append("Check the latest official IMD updates before making weather-sensitive plans.")
        elif warning_status == "unavailable":
            factors.append(AdvisoryFactor(code="IMD_STATUS_UNAVAILABLE", detail="Official IMD warning information could not be retrieved.", source="India Meteorological Department (IMD)"))
            recommendations.append("Check official IMD updates before making weather-sensitive plans.")
        elif warning_status == "unsupported_location":
            factors.append(AdvisoryFactor(code="IMD_LOOKUP_UNSUPPORTED", detail="Official IMD warning lookup is not configured for this location.", source="India Meteorological Department (IMD)"))
        elif alerts and not matching_alerts:
            warning_status = "none_reported"

        if not forecast or (forecast and day_offset >= len(forecast.forecast)):
            factors.append(AdvisoryFactor(code="FORECAST_UNAVAILABLE", detail="Forecast information could not be retrieved; no forecast conditions are assumed.", source="OpenWeatherMap"))
        if activity in (AdvisoryActivity.TRAVEL, AdvisoryActivity.COMMUTE) and any(f.code in {"PRECIPITATION_CHANCE", "RAIN_CONDITION"} for f in factors):
            recommendations.extend(["Allow extra travel time.", "Check local road and transport conditions before departure."])
        elif activity in (AdvisoryActivity.OUTDOOR_ACTIVITY, AdvisoryActivity.EVENT, AdvisoryActivity.EXERCISE) and any(f.code in {"PRECIPITATION_CHANCE", "RAIN_CONDITION", "WIND"} for f in factors):
            recommendations.append("Consider flexible timing or an indoor alternative.")
        if not factors:
            recommendations.append("Check the forecast again closer to your planned activity.")

        codes = {factor.code for factor in factors}
        high = (official_warning and official_warning.severity in {"Red", "Orange"}) or (selected and selected.rain_probability is not None and selected.rain_probability >= 80 and "rain" in selected.description.casefold()) or (selected and selected.wind_speed is not None and selected.wind_speed >= self.STRONG_WIND_MPS) or (selected and selected.temperature_max >= self.VERY_HIGH_TEMPERATURE_C)
        moderate = bool(codes & {"PRECIPITATION_CHANCE", "RAIN_CONDITION", "WIND", "TEMPERATURE", "HUMIDITY", "OFFICIAL_IMD_WARNING"})
        risk = AdvisoryRisk.HIGH if high else AdvisoryRisk.MODERATE if moderate else AdvisoryRisk.LOW

        if selected:
            summary = f"For {location}, the forecast for {selected.date.strftime('%A, %B %d')} indicates {selected.description} with temperatures from {selected.temperature_min:.1f}°C to {selected.temperature_max:.1f}°C."
        else:
            summary = f"A weather advisory for {location} could not be based on forecast data because the forecast is unavailable."
        if warning_status == "unavailable":
            summary += " Official IMD warning information could not be retrieved."
        elif official_warning:
            summary += f" An official IMD warning is reported: {', '.join(official_warning.warnings)}."
        elif warning_status == "none_reported":
            summary += " No official IMD warning is reported for this date; this does not mean there is zero weather risk."
        elif warning_status == "unsupported_location":
            summary += " Official IMD warning lookup is not configured for this location."

        sources = []
        if forecast:
            sources.append(forecast.source)
        if alerts:
            sources.append(alerts.source)
        elif warning_status == "unavailable":
            sources.append("India Meteorological Department (IMD) — unavailable")
        elif warning_status == "unsupported_location":
            sources.append("India Meteorological Department (IMD) — location not configured")
        sources.append("WeatherGPT")
        # De-duplicate recommendations while retaining their order.
        recommendations = list(dict.fromkeys(recommendations))
        if selected is None:
            risk = None
        return WeatherAdvisoryResponse(location=location, date=date, activity=activity.value, summary=summary, risk_level=risk, risk_label="WeatherGPT risk classification", factors=factors, recommendations=recommendations, official_warning=official_warning, official_warning_status=warning_status, sources=sources)
