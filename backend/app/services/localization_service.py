"""Language selection and deterministic presentation for supported chat languages.

Weather measurements and provider schemas remain canonical. This module only
normalizes common Indic questions for routing and renders already-known facts.
"""

from __future__ import annotations

import re
from typing import Any

SUPPORTED_LANGUAGES = {"en": "English", "mr": "मराठी", "hi": "हिन्दी"}


def validate_language(language: str) -> str:
    value = language.strip().lower()
    if value not in SUPPORTED_LANGUAGES:
        raise ValueError("Language must be one of: en, mr, hi")
    return value


_CITIES = {
    "धुळे": "Dhule", "धुले": "Dhule", "धुळ्य": "Dhule", "नाशिक": "Nashik", "नासिक": "Nashik",
    "मुंबई": "Mumbai", "पुणे": "Pune", "dhule": "Dhule", "nashik": "Nashik",
    "mumbai": "Mumbai", "pune": "Pune",
}


def _indic_question(message: str, language: str) -> tuple[str, str | None]:
    """Return an English routing phrase and explicit city for common supported queries."""
    text = message.casefold()
    city = next((canonical for token, canonical in _CITIES.items() if token.casefold() in text), None)
    travel = any(x in text for x in ("प्रवास", "यात्रा", "travel", "जाना चाहिए"))
    advisory = travel or any(x in text for x in ("छत्री", "छाता", "काळजी", "तैयारी", "बाहेर", "बाहर", "सावधानी", "व्यायाम"))
    alert = any(x in text for x in ("इशारा", "चेतावणी", "चेतावनी", "अलर्ट", "warning", "alert"))
    tomorrow = any(x in text for x in ("उद्या", "कल"))
    today = any(x in text for x in ("आज", "आजचे", "आजचा"))
    rain = any(x in text for x in ("पाऊस", "बारिश", "वर्षा"))
    weather = any(x in text for x in ("हवामान", "मौसम"))

    if advisory:
        intent_phrase = "Should I travel" if travel else "What precautions should I take"
        when = " tomorrow" if tomorrow else " today" if today else ""
    elif alert:
        intent_phrase, when = "Is there an official weather warning", " tomorrow" if tomorrow else ""
    elif rain or tomorrow:
        intent_phrase, when = "Will it rain", " tomorrow" if tomorrow else ""
    elif weather:
        intent_phrase, when = "What is the weather", " today" if today else ""
    else:
        return message, city
    return f"{intent_phrase}{when} in {city}" if city else f"{intent_phrase}{when}", city


_TEXT = {
    "mr": {
        "ask_city": "कृपया कोणते शहर किंवा जिल्हा तपासायचा ते सांगा.",
        "unknown": "मी सध्याचे हवामान, अंदाज, अधिकृत इशारे आणि हवामानविषयक सल्ला देऊ शकतो.",
        "unavailable": "अधिकृत IMD इशाऱ्यांची माहिती सध्या मिळवता आली नाही. याचा अर्थ इशारा नाही असा होत नाही.",
        "no_alert": "या कालावधीसाठी कोणताही अधिकृत IMD हवामान इशारा नोंदवलेला नाही. याचा अर्थ हवामानाचा धोका शून्य आहे असा नाही.",
        "weather": "{place} मधील सध्याचे हवामान {temp}°C आणि {condition} आहे. जाणवणारे तापमान {feels}°C, आर्द्रता {humidity}% आणि वाऱ्याचा वेग {wind} m/s आहे.",
        "temp": "{place} मध्ये सध्या तापमान {temp}°C आहे; जाणवणारे तापमान {feels}°C आहे.",
        "humidity": "{place} मधील सध्याची आर्द्रता {value}% आहे.",
        "wind": "{place} मधील सध्याचा वाऱ्याचा वेग {value} m/s आहे.",
        "forecast": "{label} {place} येथे तापमान साधारण {min}°C ते {max}°C दरम्यान राहण्याची शक्यता आहे. अंदाजानुसार {condition}{rain}.",
        "rain": ", पावसाची शक्यता साधारण {value}% आहे",
        "title_forecast": "{place} साठी हवामानाचा अंदाज: {items}.",
        "alert_title": "अधिकृत IMD हवामान इशारा",
        "alert_row": "{date}: {warnings}; IMD स्तर: {severity}",
        "alert_source": "अधिकृत इशारा स्रोत",
        "explanation": "WeatherGPT स्पष्टीकरण: IMD ने वर नमूद केलेले इशारे दिले आहेत.",
        "advisory_title": "WeatherGPT हवामान सल्ला",
        "risk": "WeatherGPT जोखीम वर्गीकरण: {value} (हा अधिकृत IMD स्तर नाही).",
        "official": "अधिकृत IMD इशारा: {value}",
        "official_unavailable": "अधिकृत IMD इशाऱ्यांची स्थिती मिळवता आली नाही.",
        "official_none": "या तारखेसाठी कोणताही अधिकृत IMD इशारा नोंदवला नव्हता; याचा अर्थ हवामानाचा धोका शून्य आहे असा नाही.",
        "factors": "घटक:", "recommendations": "WeatherGPT शिफारसी:", "sources": "स्रोत:",
        "advisory_forecast": "{place} साठी {date} च्या अंदाजानुसार {condition}; तापमान {minimum}°C ते {maximum}°C दरम्यान राहण्याची शक्यता आहे.",
        "advisory_unavailable": "अंदाज उपलब्ध नसल्यामुळे {place} साठी हवामान सल्ला अंदाजित परिस्थितींवर आधारित नाही.",
        "advisory_imd_unavailable": "अधिकृत IMD इशाऱ्यांची माहिती मिळवता आली नाही.",
        "recommend_rain": "पावसापासून संरक्षणासाठी आवश्यक वस्तू सोबत ठेवा.",
        "recommend_travel": "प्रवासासाठी अतिरिक्त वेळ ठेवा.",
        "recommend_check_travel": "निघण्यापूर्वी स्थानिक रस्ते आणि वाहतूक स्थिती तपासा.",
        "recommend_updates": "हवामानाशी संबंधित योजना करण्यापूर्वी नवीनतम अधिकृत IMD माहिती तपासा.",
        "recommend_check_updates": "योजना करण्यापूर्वी अधिकृत IMD माहिती तपासा.",
        "recommend_flexible": "बाहेरील कृतींसाठी वेळेत बदल किंवा घरातील पर्याय विचारात घ्या.",
        "recommend_weather": "तुमच्या नियोजित कृतीच्या जवळ पुन्हा अंदाज तपासा.",
        "condition_rain": "पाऊस", "condition_cloud": "ढगाळ", "condition_clear": "निरभ्र आकाश",
    },
    "hi": {
        "ask_city": "कृपया बताएं कि किस शहर या जिले का मौसम देखना है।",
        "unknown": "मैं वर्तमान मौसम, पूर्वानुमान, आधिकारिक चेतावनियों और मौसम संबंधी सलाह में मदद कर सकता हूँ।",
        "unavailable": "आधिकारिक IMD चेतावनी की जानकारी अभी प्राप्त नहीं हो सकी। इसका अर्थ यह नहीं है कि कोई चेतावनी नहीं है।",
        "no_alert": "इस अवधि के लिए कोई आधिकारिक IMD मौसम चेतावनी दर्ज नहीं है। इसका अर्थ यह नहीं कि मौसम का जोखिम शून्य है।",
        "weather": "{place} में वर्तमान मौसम {temp}°C और {condition} है। महसूस होने वाला तापमान {feels}°C, आर्द्रता {humidity}% और हवा की गति {wind} m/s है।",
        "temp": "{place} में अभी तापमान {temp}°C है और महसूस होने वाला तापमान {feels}°C है।",
        "humidity": "{place} में वर्तमान आर्द्रता {value}% है।",
        "wind": "{place} में वर्तमान हवा की गति {value} m/s है।",
        "forecast": "{label} {place} में तापमान लगभग {min}°C से {max}°C के बीच रहने की संभावना है। पूर्वानुमान में {condition}{rain}।",
        "rain": ", बारिश की संभावना लगभग {value}% है",
        "title_forecast": "{place} का मौसम पूर्वानुमान: {items}।",
        "alert_title": "आधिकारिक IMD मौसम चेतावनी",
        "alert_row": "{date}: {warnings}; IMD स्तर: {severity}",
        "alert_source": "आधिकारिक चेतावनी स्रोत",
        "explanation": "WeatherGPT व्याख्या: IMD ने ऊपर दी गई चेतावनी जारी की है।",
        "advisory_title": "WeatherGPT मौसम सलाह",
        "risk": "WeatherGPT जोखिम वर्गीकरण: {value} (यह आधिकारिक IMD स्तर नहीं है)।",
        "official": "आधिकारिक IMD चेतावनी: {value}",
        "official_unavailable": "आधिकारिक IMD चेतावनी की स्थिति प्राप्त नहीं हो सकी।",
        "official_none": "इस तारीख के लिए कोई आधिकारिक IMD चेतावनी दर्ज नहीं थी; इसका अर्थ यह नहीं कि मौसम का जोखिम शून्य है।",
        "factors": "कारक:", "recommendations": "WeatherGPT सुझाव:", "sources": "स्रोत:",
        "advisory_forecast": "{place} के लिए {date} के पूर्वानुमान में {condition} है; तापमान {minimum}°C से {maximum}°C के बीच रहने की संभावना है।",
        "advisory_unavailable": "पूर्वानुमान उपलब्ध न होने के कारण {place} की सलाह अनुमानित मौसम स्थितियों पर आधारित नहीं है।",
        "advisory_imd_unavailable": "आधिकारिक IMD चेतावनी की जानकारी प्राप्त नहीं हो सकी।",
        "recommend_rain": "बारिश से बचाव के लिए आवश्यक सामान साथ रखें।",
        "recommend_travel": "यात्रा के लिए अतिरिक्त समय रखें।",
        "recommend_check_travel": "रवाना होने से पहले स्थानीय सड़क और परिवहन स्थिति जाँचें।",
        "recommend_updates": "मौसम-संवेदनशील योजना से पहले नवीनतम आधिकारिक IMD अपडेट देखें।",
        "recommend_check_updates": "योजना से पहले आधिकारिक IMD अपडेट देखें।",
        "recommend_flexible": "बाहरी गतिविधियों के लिए समय बदलने या घर के भीतर विकल्प पर विचार करें।",
        "recommend_weather": "अपनी गतिविधि के समय के करीब फिर से पूर्वानुमान देखें।",
        "condition_rain": "बारिश", "condition_cloud": "बादल छाए हुए", "condition_clear": "साफ़ आसमान",
    },
}


def _translate_condition(value: str, language: str) -> str:
    if language == "en":
        return value
    lowered = value.casefold()
    dictionary = {
        "rain": "condition_rain", "drizzle": "condition_rain", "cloud": "condition_cloud",
        "clear": "condition_clear",
    }
    key = next((target for word, target in dictionary.items() if word in lowered), None)
    return _TEXT[language].get(key, value) if key else value


def localize_chat_response(response: Any, language: str) -> Any:
    """Translate deterministic chat presentation while retaining typed values/source."""
    language = validate_language(language)
    if language == "en":
        return response
    t = _TEXT[language]
    intent = response.intent.value
    message = response.message
    if response.location is None and "which city or district" in message.casefold():
        return response.model_copy(update={"message": t["ask_city"]})
    if intent == "CURRENT_WEATHER" and response.weather:
        w = response.weather
        # Pick a safe template by the exact numeric facts in the canonical response.
        if "temperature" in message.casefold() or ("current weather" in message.casefold() and "feels" in message.casefold()):
            message = t["weather"].format(place=response.location or "", temp=f"{w.temperature:.1f}", feels=f"{w.feels_like:.1f}", humidity=w.humidity, wind=f"{w.wind_speed:.2f}", condition=_translate_condition(w.description, language))
        elif "humidity" in message.casefold():
            message = t["humidity"].format(place=response.location or "", value=w.humidity)
        elif "wind speed" in message.casefold():
            message = t["wind"].format(place=response.location or "", value=f"{w.wind_speed:.2f}")
        elif "currently" in message.casefold() and "feels" in message.casefold() and "°c in" in message.casefold():
            message = t["temp"].format(place=response.location or "", temp=f"{w.temperature:.1f}", feels=f"{w.feels_like:.1f}")
        else:
            message = t["weather"].format(place=response.location or "", temp=f"{w.temperature:.1f}", feels=f"{w.feels_like:.1f}", humidity=w.humidity, wind=f"{w.wind_speed:.2f}", condition=_translate_condition(w.description, language))
    elif intent == "FORECAST" and response.forecast:
        item = response.forecast[0]
        label = "आज" if language == "hi" else "आज" if "Today" in message else "कल" if language == "hi" else "उद्या"
        if "Tomorrow" in message:
            label = "कल" if language == "hi" else "उद्या"
        if len(response.forecast) > 1:
            rows = []
            for forecast_day in response.forecast:
                chance = forecast_day.get("rain_probability")
                rain = t["rain"].format(value=f"{chance:.0f}") if chance is not None else ""
                rows.append(f"{forecast_day.get('date')}: {forecast_day.get('temperature_min', 0):.1f}–{forecast_day.get('temperature_max', 0):.1f}°C, {_translate_condition(str(forecast_day.get('description', '')), language)}{rain}")
            message = t["title_forecast"].format(place=response.location or "", items="; ".join(rows))
        else:
            chance = item.get("rain_probability")
            rain = t["rain"].format(value=f"{chance:.0f}") if chance is not None else ""
            message = t["forecast"].format(label=label, place=response.location or "", min=f"{item.get('temperature_min', 0):.1f}", max=f"{item.get('temperature_max', 0):.1f}", condition=_translate_condition(str(item.get("description", "")), language), rain=rain)
    elif intent == "ALERT":
        if "couldn't retrieve" in message.casefold() or "unavailable" in message.casefold():
            message = t["unavailable"]
        elif response.alert_days is not None and not any(day.is_active for day in response.alert_days):
            message = f"{t['no_alert']}\n\nSource: {response.source or 'India Meteorological Department (IMD)'}"
        else:
            # Preserve the original warning rows, severity, dates, codes, and attribution.
            replacements = {
                "Official IMD Weather Warning": t["alert_title"],
                "Location:": "स्थान:" if language == "mr" else "स्थान:",
                "IMD Level:": "IMD स्तर:",
                "Official warning source:": t["alert_source"] + ":",
                "WeatherGPT explanation:": t["explanation"],
                "WeatherGPT advisory:": "WeatherGPT सल्ला:" if language == "mr" else "WeatherGPT सलाह:",
                "Heavy Rain": "मुसळधार पाऊस" if language == "mr" else "भारी बारिश",
                "Very Heavy Rain": "अतिवृष्टी" if language == "mr" else "बहुत भारी बारिश",
                "Extremely Heavy Rain": "अत्यंत मुसळधार पाऊस" if language == "mr" else "अत्यंत भारी बारिश",
                "Thunderstorm & Lightning, Squall etc": "मेघगर्जना, वीज आणि वादळी वारे" if language == "mr" else "गरज-चमक और तेज़ हवा",
                "Heat Wave": "उष्णतेची लाट" if language == "mr" else "लू",
                "Cold Wave": "थंडीची लाट" if language == "mr" else "शीतलहर",
            }
            for original, translated in sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True):
                message = message.replace(original, translated)
    elif intent == "ADVISORY" and response.advisory:
        a = response.advisory
        import re
        summary_match = re.search(r"indicates (.+?) with temperatures from ([\d.]+)°C to ([\d.]+)°C", a.summary, re.IGNORECASE)
        if summary_match:
            summary = t["advisory_forecast"].format(place=a.location, date=a.date.date().isoformat() if a.date else "", condition=_translate_condition(summary_match.group(1), language), minimum=summary_match.group(2), maximum=summary_match.group(3))
        else:
            summary = t["advisory_unavailable"].format(place=a.location)
        if a.official_warning_status == "unavailable":
            summary += " " + t["advisory_imd_unavailable"]
        localized_recommendations = []
        recommendation_map = {
            "Carry rain protection.": "recommend_rain", "Consider carrying rain protection.": "recommend_rain",
            "Allow extra travel time.": "recommend_travel", "Check local road and transport conditions before departure.": "recommend_check_travel",
            "Check the latest official IMD updates before making weather-sensitive plans.": "recommend_updates",
            "Check official IMD updates before making weather-sensitive plans.": "recommend_check_updates",
            "Consider flexible timing or an indoor alternative.": "recommend_flexible",
            "Check the forecast again closer to your planned activity.": "recommend_weather",
        }
        localized_recommendations = [t[recommendation_map[item]] if item in recommendation_map else item for item in a.recommendations]
        factor_details = {
            "IMD_STATUS_UNAVAILABLE": t["official_unavailable"],
            "IMD_LOOKUP_UNSUPPORTED": "या स्थानासाठी अधिकृत IMD इशारा शोध उपलब्ध नाही." if language == "mr" else "इस स्थान के लिए आधिकारिक IMD चेतावनी खोज उपलब्ध नहीं है।",
            "FORECAST_UNAVAILABLE": "अंदाजाची माहिती मिळाली नाही; कोणतीही परिस्थिती गृहीत धरलेली नाही." if language == "mr" else "पूर्वानुमान जानकारी उपलब्ध नहीं है; कोई स्थिति नहीं मानी गई है।",
            "PRECIPITATION_CHANCE": "पावसाची शक्यता {value} आहे." if language == "mr" else "बारिश की संभावना {value} है।",
            "RAIN_CONDITION": "अंदाजातील स्थिती: {value}" if language == "mr" else "पूर्वानुमान की स्थिति: {value}",
            "WIND": "अंदाजातील वाऱ्याचा वेग {value} m/s आहे." if language == "mr" else "पूर्वानुमान में हवा की गति {value} m/s है।",
            "TEMPERATURE": "अंदाजातील कमाल तापमान {value}°C आहे." if language == "mr" else "पूर्वानुमान में अधिकतम तापमान {value}°C है।",
        }
        localized_factors = []
        for factor in a.factors:
            detail = factor.detail
            if factor.code in factor_details:
                if factor.code == "PRECIPITATION_CHANCE":
                    match = re.search(r"([\d.]+%)", detail)
                    detail = factor_details[factor.code].format(value=match.group(1) if match else "")
                elif factor.code in {"WIND", "TEMPERATURE"}:
                    match = re.search(r"([\d.]+) ?(?:m/s|°C)", detail)
                    detail = factor_details[factor.code].format(value=match.group(1) if match else "")
                elif factor.code == "RAIN_CONDITION":
                    detail = factor_details[factor.code].format(value=_translate_condition(detail.partition(":")[-1].strip(), language))
                else:
                    detail = factor_details[factor.code]
            localized_factors.append(factor.model_copy(update={"detail": detail}))
        activity_labels = {
            "TRAVEL": "प्रवास" if language == "mr" else "यात्रा",
            "COMMUTE": "ये-जा" if language == "mr" else "आवागमन",
            "OUTDOOR_ACTIVITY": "बाहेरील कृती" if language == "mr" else "बाहरी गतिविधि",
            "EXERCISE": "व्यायाम" if language == "mr" else "व्यायाम",
            "EVENT": "कार्यक्रम" if language == "mr" else "कार्यक्रम",
            "AGRICULTURE": "शेती" if language == "mr" else "कृषि",
            "GENERAL_PRECAUTION": "सामान्य खबरदारी" if language == "mr" else "सामान्य सावधानी",
        }
        localized_advisory = a.model_copy(update={"summary": summary, "recommendations": localized_recommendations, "factors": localized_factors, "risk_label": "WeatherGPT जोखीम वर्गीकरण" if language == "mr" else "WeatherGPT जोखिम वर्गीकरण"})
        message = f"{t['advisory_title']}\n\n{a.location} · {a.date.isoformat() if a.date else ''} · {activity_labels.get(a.activity, a.activity)}\n\n{summary}\n\n" + t["risk"].format(value=a.risk_level.value if a.risk_level else "Not assessed")
        if a.official_warning:
            message += "\n\n" + t["official"].format(value=", ".join(a.official_warning.warnings)) + f" · IMD {a.official_warning.severity or ''}"
        elif a.official_warning_status == "unavailable":
            message += "\n\n" + t["official_unavailable"]
        elif a.official_warning_status == "none_reported":
            message += "\n\n" + t["official_none"]
        if a.factors:
            message += "\n\n" + t["factors"] + "\n" + "\n".join(f"• {x.detail} ({x.source})" for x in localized_factors)
        if localized_recommendations:
            message += "\n\n" + t["recommendations"] + "\n" + "\n".join(f"• {x}" for x in localized_recommendations)
        message += "\n\n" + t["sources"] + " " + ", ".join(a.sources)
        return response.model_copy(update={"message": message, "advisory": localized_advisory})
    elif intent == "UNKNOWN":
        message = t["unknown"]
    return response.model_copy(update={"message": message})


def language_prompt(language: str) -> str:
    language = validate_language(language)
    return {"en": "Respond in English.", "mr": "Respond in Marathi (मराठी). Preserve every supplied number, date, unit, warning level/code, and source exactly.", "hi": "Respond in Hindi (हिन्दी). Preserve every supplied number, date, unit, warning level/code, and source exactly."}[language]
