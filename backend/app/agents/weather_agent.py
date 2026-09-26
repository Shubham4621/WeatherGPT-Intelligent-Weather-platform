"""Small intent-to-tool orchestration for current weather chat."""

from collections.abc import Awaitable, Callable

from app.schemas.chat import AdvisoryActivity, ChatIntent, ChatIntentResult, ChatResponse, WeatherMetric
from app.schemas.weather import CurrentWeatherResponse, ForecastResponse
from app.services.llm_service import LLMService
from app.tools.weather_tools import get_current_weather, get_forecast, get_weather_alerts, get_weather_advisory
from app.schemas.weather import WeatherAdvisoryResponse
from app.services.imd_alert_service import AlertProviderUnavailable, UnsupportedAlertLocation
from app.services.localization_service import localize_chat_response

WeatherTool = Callable[[str], Awaitable[CurrentWeatherResponse]]
ForecastTool = Callable[[str], Awaitable[ForecastResponse]]
AlertTool = Callable[..., Awaitable]
AdvisoryTool = Callable[..., Awaitable[WeatherAdvisoryResponse]]


class WeatherAgent:
    """Routes supported intents to real weather data and grounds every fact."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        weather_tool: WeatherTool = get_current_weather,
        forecast_tool: ForecastTool = get_forecast,
        alert_tool: AlertTool = get_weather_alerts,
        advisory_tool: AdvisoryTool = get_weather_advisory,
    ) -> None:
        self.llm_service = llm_service or LLMService()
        self.weather_tool = weather_tool
        self.forecast_tool = forecast_tool
        self.alert_tool = alert_tool
        self.advisory_tool = advisory_tool

    async def answer(self, message: str, language: str = "en") -> ChatResponse:
        language = language.strip().lower()
        intent = await self.llm_service.classify(message) if language == "en" else await self.llm_service.classify(message, language=language)
        if intent.intent == ChatIntent.UNKNOWN:
            return localize_chat_response(self._unsupported(intent), language)
        if not intent.city:
            return localize_chat_response(ChatResponse(
                message="Which city or district should I check?",
                intent=intent.intent,
            ), language)

        if intent.intent == ChatIntent.ADVISORY:
            result = await self.advisory_tool(intent.city, intent.advisory_day_offset, intent.activity)
            facts = {"location": result.location, "date": result.date.isoformat() if result.date else None, "activity": result.activity, "risk_label": result.risk_label, "risk_level": result.risk_level.value if result.risk_level else None, "factors": [factor.model_dump() for factor in result.factors], "official_warning_status": result.official_warning_status, "official_warning": result.official_warning.model_dump(mode="json") if result.official_warning else None, "summary": result.summary}
            if language == "en":
                explanation = await self.llm_service.explain_advisory(facts)
            else:
                try:
                    explanation = await self.llm_service.explain_advisory(facts, language=language)
                except TypeError:
                    explanation = await self.llm_service.explain_advisory(facts)
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
            return localize_chat_response(ChatResponse(
                message="Historical data unavailable. A reliable historical weather provider is not configured, so I cannot provide historical measurements.",
                intent=ChatIntent.HISTORICAL_WEATHER, location=intent.city,
                tool_used="get_historical_weather",
            ), language)

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
