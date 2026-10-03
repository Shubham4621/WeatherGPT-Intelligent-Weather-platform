"""Small intent-to-tool orchestration for current weather chat."""

from collections.abc import Awaitable, Callable

from app.schemas.chat import AdvisoryActivity, ChatIntent, ChatIntentResult, ChatResponse, WeatherMetric
from app.schemas.agriculture import AgricultureActivity
from app.schemas.weather import CurrentWeatherResponse, ForecastResponse
from app.services.llm_service import LLMService
from app.tools.weather_tools import get_current_weather, get_forecast, get_weather_alerts, get_weather_advisory, get_historical_weather, get_climatology_normal, get_nwp_forecast, get_agriculture_advice
from app.schemas.weather import WeatherAdvisoryResponse
from app.services.imd_alert_service import AlertProviderUnavailable, UnsupportedAlertLocation
from app.services.localization_service import localize_chat_response
from app.services.historical_weather_service import aggregate, monthly_aggregation, yearly_aggregation, linear_trend, annual_rainfall_climatology_comparison
from datetime import date
from calendar import month_name
import re
import inspect

WeatherTool = Callable[[str], Awaitable[CurrentWeatherResponse]]
ForecastTool = Callable[[str], Awaitable[ForecastResponse]]
AlertTool = Callable[..., Awaitable]
AdvisoryTool = Callable[..., Awaitable[WeatherAdvisoryResponse]]
HistoricalTool = Callable[..., Awaitable]


class WeatherAgent:
    """Routes supported intents to real weather data and grounds every fact."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        weather_tool: WeatherTool = get_current_weather,
        forecast_tool: ForecastTool = get_forecast,
        alert_tool: AlertTool = get_weather_alerts,
        advisory_tool: AdvisoryTool = get_weather_advisory,
        historical_tool: HistoricalTool = get_historical_weather,
        climatology_tool: Callable[..., dict] = get_climatology_normal,
        nwp_tool: Callable[..., Awaitable] = get_nwp_forecast,
        agriculture_tool: Callable[..., Awaitable] = get_agriculture_advice,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.weather_tool = weather_tool
        self.forecast_tool = forecast_tool
        self.alert_tool = alert_tool
        self.advisory_tool = advisory_tool
        self.historical_tool = historical_tool
        self.climatology_tool = climatology_tool
        self.nwp_tool = nwp_tool
        self.agriculture_tool = agriculture_tool

    async def answer(self, message: str, language: str = "en") -> ChatResponse:
        language = language.strip().lower()
        intent = await self.llm_service.classify(message, language=language)
        if intent.intent == ChatIntent.UNKNOWN:
            return localize_chat_response(self._unsupported(intent), language)
        if not intent.city:
            if intent.intent == ChatIntent.AGRICULTURE:
                return localize_chat_response(ChatResponse(message="Which city or coordinates should I use for weather-based farm guidance?", intent=ChatIntent.AGRICULTURE), language)
            return localize_chat_response(ChatResponse(
                message="Which city or district should I check?",
                intent=intent.intent,
            ), language)

        if intent.intent == ChatIntent.NWP:
            result = await self.nwp_tool(intent.city)
            facts = result.model_dump(mode="json")
            if result.status not in {"available", "partial"} or not result.points:
                message_text = f"NWP model data is unavailable for {intent.city} ({result.reason or result.status}). I did not substitute the operational forecast or WeatherGPT prediction."
                facts["summary"] = message_text
            else:
                temps = [point.temperature_c for point in result.points if point.temperature_c is not None]
                valid_start = result.forecast_start.isoformat() if result.forecast_start else "unavailable"
                valid_end = result.forecast_end.isoformat() if result.forecast_end else "unavailable"
                run_label = result.initialization_time.isoformat() if result.initialization_time else "unavailable"
                message_text = (f"{result.model} NWP model output for {intent.city}: 2 m temperature values range from "
                    f"{min(temps):.1f} to {max(temps):.1f} °C across retrieved valid times {valid_start} through {valid_end}. "
                    f"Model initialization: {run_label}. Provider: {result.source}; native grid: {result.resolution_degrees}°. "
                    "This is numerical model guidance, not an observation, official warning, or WeatherGPT prediction.")
                facts["summary"] = message_text
                if result.status == "partial":
                    message_text += f" Some forecast leads were unavailable ({', '.join(map(str, result.missing_leads))} hours)."
                    facts["summary"] = message_text
                if hasattr(self.llm_service, "explain_nwp"):
                    message_text = await self.llm_service.explain_nwp(facts, language=language)
                    message_text = f"NWP model output — {result.model}: {message_text}"
            return localize_chat_response(ChatResponse(message=message_text, intent=ChatIntent.NWP, location=intent.city,
                source=result.source, tool_used="get_nwp_forecast", forecast=[row.model_dump(mode="json") for row in result.forecast],
                nwp_data=facts), language)

        if intent.intent == ChatIntent.AGRICULTURE:
            result = await self.agriculture_tool(intent.city, intent.agriculture_activity)
            facts = result.model_dump(mode="json")
            deterministic = result.recommendation.recommendation
            facts["summary"] = deterministic
            if result.status == "unavailable" or result.recommendation.condition == "insufficient_data":
                explanation = deterministic
            elif hasattr(self.llm_service, "explain_agriculture"):
                explanation = await self.llm_service.explain_agriculture({
                    "summary": deterministic,
                    "activity": result.recommendation.activity.value,
                    "condition": result.recommendation.condition,
                    "evidence": [item.model_dump(mode="json") for item in result.recommendation.evidence],
                    "limitations": result.recommendation.limitations,
                }, language=language)
            else:
                explanation = deterministic
            message_text = (
                f"WeatherGPT Agriculture Advisory for {intent.city}\n\n{explanation}\n\n"
                f"Activity: {result.recommendation.activity.value.replace('_', ' ').title()} · "
                f"Condition: {result.recommendation.condition.replace('_', ' ')}.\n"
                "This is weather-based decision support, not an official agricultural department advisory.\n"
                f"Sources: {', '.join(result.recommendation.sources) or 'No weather source available'}."
            )
            return localize_chat_response(ChatResponse(message=message_text, intent=ChatIntent.AGRICULTURE,
                location=intent.city, source="WeatherGPT Agriculture Advisory", tool_used="get_agriculture_advice",
                agriculture_data=facts), language)

        if intent.intent == ChatIntent.ADVISORY:
            result = await self.advisory_tool(intent.city, intent.advisory_day_offset, intent.activity)
            facts = {"location": result.location, "date": result.date.isoformat() if result.date else None, "activity": result.activity, "risk_label": result.risk_label, "risk_level": result.risk_level.value if result.risk_level else None, "factors": [factor.model_dump() for factor in result.factors], "official_warning_status": result.official_warning_status, "official_warning": result.official_warning.model_dump(mode="json") if result.official_warning else None, "summary": result.summary}
            # Let the response-language instruction reach every supported language.
            # The deterministic localizer below still controls final wording and values.
            explanation = await self.llm_service.explain_advisory(facts, language=language)
            result = result.model_copy(update={"summary": explanation})
            factor_text = "\n".join(f"• {factor.detail} ({factor.source})" for factor in result.factors) or "No elevated forecast factor was identified from available data."
            recommendations = "\n".join(f"• {item}" for item in result.recommendations)
            if result.official_warning:
                official = f"Official IMD warning: {', '.join(result.official_warning.warnings)} — IMD Level {result.official_warning.severity or 'not specified'}."
            elif result.official_warning_status == "unavailable":
                official = "Official IMD warning information could not be retrieved. This is not confirmation that no warning exists."
            elif result.official_warning_status == "none_reported":
                official = "No official IMD warning was reported for this date; this does not mean there is zero weather risk."
            else:
                official = "Official IMD warning lookup is not configured for this location."
            date_label = result.date.strftime("%A, %B %d") if result.date else "requested date"
            risk_text = f"{result.risk_level.value} (not an official IMD level)" if result.risk_level else "Not assessed because forecast data is unavailable (not an official IMD level)"
            message = f"WeatherGPT Advisory\n\n{result.location} · {date_label} · {result.activity.replace('_', ' ').title()}\n\n{result.summary}\n\nWeatherGPT risk classification: {risk_text}.\n\nFactors:\n{factor_text}\n\n{official}\n\nWeatherGPT recommendations:\n{recommendations}\n\nSources: {', '.join(result.sources)}"
            return localize_chat_response(ChatResponse(message=message, intent=ChatIntent.ADVISORY, location=result.location, source="WeatherGPT", tool_used="get_weather_advisory", advisory=result), language)

        if intent.intent == ChatIntent.ALERT:
            try:
                alert_result = await self.alert_tool(intent.city)
            except UnsupportedAlertLocation:
                return localize_chat_response(ChatResponse(message="Official IMD warning lookup is not configured for that location.", intent=ChatIntent.ALERT, location=intent.city, tool_used="get_weather_alerts"), language)
            except AlertProviderUnavailable:
                return localize_chat_response(ChatResponse(message="I couldn't retrieve the latest official IMD warning information right now. Please check the India Meteorological Department for the latest warning.", intent=ChatIntent.ALERT, location=intent.city, tool_used="get_weather_alerts"), language)
            active = [day for day in alert_result.forecast_days if day.is_active]
            if not active:
                message = f"No official IMD weather warning is currently reported for {alert_result.district} for the requested period. This does not mean there is zero weather risk.\n\nSource: {alert_result.source}"
            else:
                rows = []
                for day in active:
                    warnings = ", ".join(f"{warning.warning_type} (code {warning.warning_code})" for warning in day.warnings)
                    rows.append(f"{day.date.strftime('%A, %B %d')}: {warnings}; IMD Level: {day.severity or 'not specified'}")
                message = f"Official IMD Weather Warning\n\nLocation: {alert_result.district}, {alert_result.state}\n" + "\n".join(rows) + f"\n\nOfficial warning source: {alert_result.source}\n{alert_result.source_url}\n\nWeatherGPT explanation: IMD reports the warning(s) listed above.\n\nWeatherGPT advisory: Consider checking local conditions and official updates before making weather-sensitive plans."
            return localize_chat_response(ChatResponse(message=message, intent=ChatIntent.ALERT, location=alert_result.district, source=alert_result.source, tool_used="get_weather_alerts", alert_days=alert_result.forecast_days), language)

        if intent.intent == ChatIntent.FORECAST:
            result = await self.forecast_tool(intent.city)
            offset = intent.forecast_day_offset
            if not result.forecast:
                return localize_chat_response(ChatResponse(message="The forecast data is unavailable for this location.", intent=ChatIntent.FORECAST), language)
            if offset >= len(result.forecast):
                return localize_chat_response(ChatResponse(message="That date is outside the available provider forecast range.", intent=ChatIntent.FORECAST, location=result.location.name, source=result.source, tool_used="get_forecast"), language)
            selected = result.forecast[offset:offset + intent.forecast_days]
            day = selected[0]
            label = "Today" if offset == 0 else "Tomorrow" if offset == 1 else day.date.strftime("%A, %B %d")
            if len(selected) > 1:
                summaries = [f"{item.date.strftime('%a %b %d')}: {item.temperature_min:.1f}?{item.temperature_max:.1f}?C, {item.description}" for item in selected]
                message = f"Forecast for {result.location.name}: " + "; ".join(summaries) + "."
            else:
                chance = f", with a rain probability of approximately {day.rain_probability:.0f}%" if day.rain_probability is not None else ""
                message = f"{label} in {result.location.name}, temperatures are expected to range from approximately {day.temperature_min:.1f}?C to {day.temperature_max:.1f}?C. The forecast indicates {day.description}{chance}."
            return localize_chat_response(ChatResponse(message=message, intent=ChatIntent.FORECAST, location=result.location.name, source=result.source, tool_used="get_forecast", forecast=[item.model_dump(mode="json") for item in selected]), language)

        if intent.intent == ChatIntent.HISTORICAL_WEATHER:
            lowered = message.casefold()
            month_map = {name.casefold(): number for number, name in enumerate(month_name) if name}
            month_number = next((number for name, number in month_map.items() if re.search(rf"\b{name}\b", lowered)), None)
            years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", lowered)]
            is_normal = "normal" in lowered or "climatolog" in lowered
            if is_normal and month_number:
                variable = "tmax" if "maximum temperature" in lowered or "tmax" in lowered else "tmin" if "minimum temperature" in lowered or "tmin" in lowered else "rainfall"
                normal = self.climatology_tool(intent.city, month_number, variable)
                if inspect.isawaitable(normal):
                    normal = await normal
                facts = {"kind": "CLIMATOLOGY", **normal}
                if normal.get("status") == "available":
                    message_text = f"IMD {variable} climatology normal for {month_name[month_number]} at the selected grid cell is {normal['normal']} {normal['units']} (baseline {normal['baseline']}; {normal['resolution_degrees']}° grid). This is a climatological normal, not an observation, forecast, or warning."
                else:
                    message_text = f"The IMD {variable} climatology normal for {month_name[month_number]} is unavailable for this location: {normal.get('reason', 'required data is missing')}."
                return localize_chat_response(ChatResponse(message=message_text, intent=ChatIntent.HISTORICAL_WEATHER, location=intent.city, source=normal.get("source"), tool_used="get_climatology_normal", historical_data=facts), language)

            if len(years) >= 1:
                start_year, end_year = min(years), max(years)
            elif "last year" in lowered:
                start_year, end_year = date.today().year - 1, date.today().year - 1
            else:
                start_year, end_year = 2013, 2024
            start = date(start_year, month_number or 1, 1)
            if month_number:
                from calendar import monthrange
                end = date(end_year, month_number, monthrange(end_year, month_number)[1])
            else:
                end = date(end_year, 12, 31)
            result = await self.historical_tool(intent.city, start, end)
            facts: dict = {"status": result.status, "availability_status": result.availability_status, "reason": result.reason, "source": result.source, "metadata": result.metadata,
                "requested_period": {"start": start.isoformat(), "end": end.isoformat()}, "requested_years": years,
                "requested_month": month_number}
            if result.status not in {"available", "partial"} or not result.records:
                message_text = f"Historical observations are unavailable for {intent.city} for {start} through {end}: {result.reason or result.availability_status or result.status}. I cannot provide a value without supporting records."
                return localize_chat_response(ChatResponse(message=message_text, intent=ChatIntent.HISTORICAL_WEATHER, location=intent.city, source=result.source, tool_used="get_historical_weather", historical_data=facts), language)
            summary = aggregate(result.records)
            monthly = monthly_aggregation(result.records)
            annual = yearly_aggregation(result.records)
            analysis_kind = "trend" if "trend" in lowered else "wettest" if "wettest" in lowered or "most rainfall" in lowered else "driest" if "driest" in lowered else "year_comparison" if len(years) >= 2 else "normal_comparison" if "normal" in lowered and len(years) == 1 else "observations"
            facts.update({"summary": summary, "monthly": monthly, "annual": annual, "analysis_kind": analysis_kind})
            if "trend" in lowered:
                points = [(row["year"], row["total_rainfall"]) for row in annual if row["total_rainfall"] is not None and row.get("complete_year", True)]
                trend_result = linear_trend(points)
                facts["trend"] = trend_result
                message_text = (f"The descriptive IMD rainfall trend for {intent.city} is {trend_result['slope_per_year']} mm/year across {trend_result['observations']} annual observations ({trend_result['period_start']}–{trend_result['period_end']}). This is a descriptive linear slope, not a forecast or significance claim." if trend_result["status"] == "available" else f"There is insufficient validated annual rainfall coverage to calculate a trend ({trend_result['observations']} observations; {trend_result['minimum_observations']} required).")
            elif "wettest" in lowered or "most rainfall" in lowered or "driest" in lowered:
                selected = max(monthly, key=lambda row: row["total_rainfall"] or -1) if "driest" not in lowered else min(monthly, key=lambda row: row["total_rainfall"] or float("inf"))
                facts["selected_month"] = selected
                message_text = f"The {('driest' if 'driest' in lowered else 'wettest')} available month in the returned historical records is {selected['month']} {selected['year']} with {selected['total_rainfall']} mm observed rainfall."
            elif len(years) >= 2:
                by_year = {row["year"]: row for row in annual}
                a, b = by_year.get(min(years)), by_year.get(max(years))
                if a and b and a["total_rainfall"] is not None and b["total_rainfall"] is not None:
                    delta = round(b["total_rainfall"] - a["total_rainfall"], 2)
                    facts["year_comparison"] = {"first_year": a["year"], "first_rainfall_mm": a["total_rainfall"],
                        "second_year": b["year"], "second_rainfall_mm": b["total_rainfall"], "difference_mm": delta}
                    message_text = f"Observed rainfall was {a['total_rainfall']} mm in {a['year']} and {b['total_rainfall']} mm in {b['year']}, a difference of {delta} mm."
                else:
                    message_text = "There is insufficient validated rainfall coverage to compare both requested years."
            else:
                rainfall = summary.get("total_rainfall")
                message_text = f"Observed rainfall in {intent.city} during {start.strftime('%B %Y') if month_number else str(start_year)} was {rainfall} mm across {summary['rainfall_observations']} available daily records." if rainfall is not None else "Rainfall observations are unavailable for the requested period."
                if "normal" in lowered and len(years) == 1:
                    anomalies = [row for row in facts["monthly"] if row["total_rainfall"] is not None]
                    comparisons = []
                    for row in anomalies:
                        normal_result = self.climatology_tool(intent.city, row["month_number"], "rainfall")
                        comparisons.append(await normal_result if inspect.isawaitable(normal_result) else normal_result)
                    annual_comparison = annual_rainfall_climatology_comparison(facts["monthly"], comparisons)
                    facts["annual_climatology"] = annual_comparison
                    if annual_comparison["status"] == "available":
                        message_text = f"{start_year} recorded {annual_comparison['observed_mm']} mm of observed rainfall versus {annual_comparison['normal_mm']} mm of summed monthly IMD {annual_comparison['baseline']} normals: an anomaly of {annual_comparison['anomaly_mm']} mm. This is a historical comparison, not an IMD warning."
                    else:
                        message_text = "There is insufficient complete rainfall and climatology coverage to compare this year with the IMD normal."
            return localize_chat_response(ChatResponse(message=message_text, intent=ChatIntent.HISTORICAL_WEATHER, location=result.location, source=result.source, tool_used="get_historical_weather", historical_data=facts), language)

        observation = await self.weather_tool(intent.city)
        return localize_chat_response(self._grounded_response(intent, observation), language)

    @staticmethod
    def _unsupported(intent: ChatIntentResult) -> ChatResponse:
        if intent.unsupported_topic.value == "forecast":
            message = "Forecasts outside the provider's available five-day range are not available yet. I can answer for the next five days."
        elif intent.unsupported_topic.value == "alerts":
            message = "Weather alerts are not available yet. I can answer questions about current weather conditions."
        elif intent.unsupported_topic.value == "historical":
            message = "Historical weather analysis is not available yet. I can answer current weather questions."
        elif intent.unsupported_topic.value == "climate":
            message = "Climate analysis is not available yet. I can answer current weather questions."
        elif intent.unsupported_topic.value == "maps":
            message = "Weather maps are not available yet. I can answer current weather questions."
        else:
            message = "I can help with current weather for a city. Try asking, ‘What is the weather in Dhule right now?’"
        return ChatResponse(message=message, intent=ChatIntent.UNKNOWN)

    @staticmethod
    def _grounded_response(
        intent: ChatIntentResult,
        observation: CurrentWeatherResponse,
    ) -> ChatResponse:
        place = observation.location.name
        weather = observation.weather
        metric = intent.metric
        if metric == WeatherMetric.TEMPERATURE:
            message = f"It is currently {weather.temperature:.1f}°C in {place}, and it feels like {weather.feels_like:.1f}°C."
        elif metric == WeatherMetric.HUMIDITY:
            message = f"The current humidity in {place} is {weather.humidity}%."
        elif metric == WeatherMetric.WIND_SPEED:
            message = f"The current wind speed in {place} is {weather.wind_speed:.2f} m/s."
        elif metric == WeatherMetric.WIND_DIRECTION:
            message = (
                f"The wind in {place} is coming from {weather.wind_direction}°."
                if weather.wind_direction is not None
                else f"Wind direction is not available for {place} right now."
            )
        elif metric == WeatherMetric.PRESSURE:
            message = f"The current atmospheric pressure in {place} is {weather.pressure} hPa."
        elif metric == WeatherMetric.VISIBILITY:
            message = (
                f"Current visibility in {place} is {weather.visibility / 1000:.1f} km."
                if weather.visibility is not None
                else f"Visibility data is not available for {place} right now."
            )
        elif metric == WeatherMetric.CLOUDINESS:
            message = (
                f"Cloud cover in {place} is currently {weather.cloudiness}%."
                if weather.cloudiness is not None
                else f"Cloud-cover data is not available for {place} right now. The reported condition is {weather.description}."
            )
        elif metric == WeatherMetric.CONDITION:
            message = f"The current condition in {place} is {weather.description}."
            if weather.cloudiness is not None:
                message += f" Cloud cover is {weather.cloudiness}%."
        else:
            message = (
                f"The current weather in {place} is {weather.temperature:.1f}°C with {weather.description}. "
                f"It feels like {weather.feels_like:.1f}°C, with {weather.humidity}% humidity "
                f"and wind speed of {weather.wind_speed:.2f} m/s."
            )

        return ChatResponse(
            message=message,
            intent=ChatIntent.CURRENT_WEATHER,
            location=place,
            source=observation.source,
            tool_used="get_current_weather",
            observed_at=observation.observed_at,
            weather=weather,
        )
