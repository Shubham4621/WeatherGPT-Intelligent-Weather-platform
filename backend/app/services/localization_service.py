"""Language selection and deterministic presentation for supported chat languages.

Weather measurements and provider schemas remain canonical. This module only
normalizes common Indic questions for routing and renders already-known facts.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.location_service import find_maharashtra_district_in_text

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
    city = find_maharashtra_district_in_text(message) or next((canonical for token, canonical in _CITIES.items() if token.casefold() in text), None)
    if any(term in text for term in ("à¤®à¤¾à¤—à¤šà¥à¤¯à¤¾", "à¤®à¤¾à¤—à¥€à¤²", "à¤ªà¤¿à¤›à¤²à¥‡", "à¤ªà¥à¤°à¤¾à¤¨à¤¾", "à¤‡à¤¤à¤¿à¤¹à¤¾à¤¸")):
        return ("historical rainfall in " + city if city else "historical weather", city)
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
        "history_unavailable": "{place} साठी विनंती केलेल्या कालावधीतील प्रमाणित ऐतिहासिक पावसाची निरीक्षणे उपलब्ध नाहीत. उपलब्ध नसलेली मूल्ये मी अंदाजाने देत नाही.",
        "history_rainfall": "{place} येथे {period} दरम्यान {amount} mm पावसाची निरीक्षणे {count} उपलब्ध दैनिक नोंदींवर आधारित आहेत.",
        "history_trend": "{place} साठी वर्णनात्मक ऐतिहासिक पाऊस कल {slope} mm/वर्ष आहे; {start} ते {end} या कालावधीतील {count} वार्षिक निरीक्षणांवर आधारित. हा वर्णनात्मक कल आहे, अंदाज किंवा सांख्यिकीय महत्त्वाचा दावा नाही.",
        "history_trend_insufficient": "{place} साठी ऐतिहासिक पावसाचा कल मोजण्यासाठी पुरेशी वार्षिक निरीक्षणे उपलब्ध नाहीत ({count}; आवश्यक किमान {minimum}).",
        "history_comparison": "{place} मध्ये {first_year} मध्ये {first} mm आणि {second_year} मध्ये {second} mm पाऊस नोंदला गेला; फरक {difference} mm आहे.",
        "history_normal": "{place} येथे {period} मध्ये {observed} mm पाऊस नोंदला गेला; {baseline} कालावधीच्या IMD मासिक सामान्यांशी तुलना केल्यास विसंगती {anomaly} mm आहे. ही विश्लेषणात्मक तुलना आहे, अधिकृत इशारा नाही.",
        "history_wettest": "उपलब्ध ऐतिहासिक निरीक्षणांमध्ये सर्वाधिक पावसाचा महिना {period} होता: {amount} mm.",
        "history_driest": "उपलब्ध ऐतिहासिक निरीक्षणांमध्ये सर्वात कमी पावसाचा महिना {period} होता: {amount} mm.",
        "climatology": "{place} साठी {period} चा IMD {variable} हवामान सामान्य {normal} {units} आहे (आधार कालावधी {baseline}; मूळ ग्रिड रिझोल्यूशन {resolution}°). हे हवामान सामान्य आहे, निरीक्षण, अंदाज किंवा इशारा नाही.",
        "climatology_unavailable": "{place} साठी विनंती केलेले IMD हवामान सामान्य उपलब्ध नाही. उपलब्ध नसलेले मूल्य मी अंदाजाने देत नाही.",
        "nwp_unavailable": "{place} साठी NWP मॉडेल माहिती उपलब्ध नाही. त्याऐवजी कार्यकारी अंदाज किंवा WeatherGPT भविष्यवाणी वापरलेली नाही.",
        "nwp_available": "{place} साठी {model} मॉडेल मार्गदर्शन उपलब्ध आहे. प्रारंभ वेळ: {run}; वैध कालावधी: {start} ते {end}; स्रोत: {source}; मूळ ग्रिड रिझोल्यूशन: {resolution}°. हे मॉडेल मार्गदर्शन आहे, निरीक्षण, अधिकृत इशारा किंवा WeatherGPT भविष्यवाणी नाही.",
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
        "history_unavailable": "{place} के लिए अनुरोधित अवधि में सत्यापित ऐतिहासिक वर्षा अवलोकन उपलब्ध नहीं हैं। अनुपलब्ध मान अनुमान से नहीं दिए जाएँगे।",
        "history_rainfall": "{place} में {period} के दौरान {count} उपलब्ध दैनिक रिकॉर्ड के आधार पर {amount} mm वर्षा दर्ज हुई।",
        "history_trend": "{place} के लिए वर्णनात्मक ऐतिहासिक वर्षा प्रवृत्ति {slope} mm/वर्ष है; यह {start} से {end} तक के {count} वार्षिक अवलोकनों पर आधारित है। यह वर्णनात्मक ढलान है, पूर्वानुमान या सांख्यिकीय महत्व का दावा नहीं।",
        "history_trend_insufficient": "{place} के लिए ऐतिहासिक वर्षा प्रवृत्ति निकालने हेतु पर्याप्त वार्षिक अवलोकन उपलब्ध नहीं हैं ({count}; न्यूनतम आवश्यक {minimum})।",
        "history_comparison": "{place} में {first_year} में {first} mm और {second_year} में {second} mm वर्षा दर्ज हुई; अंतर {difference} mm है।",
        "history_normal": "{place} में {period} के दौरान {observed} mm वर्षा दर्ज हुई; {baseline} अवधि के IMD मासिक सामान्य से तुलना करने पर विसंगति {anomaly} mm है। यह विश्लेषणात्मक तुलना है, आधिकारिक चेतावनी नहीं।",
        "history_wettest": "उपलब्ध ऐतिहासिक अवलोकनों में सबसे अधिक वर्षा वाला महीना {period} था: {amount} mm।",
        "history_driest": "उपलब्ध ऐतिहासिक अवलोकनों में सबसे कम वर्षा वाला महीना {period} था: {amount} mm।",
        "climatology": "{place} के लिए {period} का IMD {variable} जलवायु सामान्य {normal} {units} है (आधार अवधि {baseline}; मूल ग्रिड रिज़ॉल्यूशन {resolution}°)। यह जलवायु सामान्य है, अवलोकन, पूर्वानुमान या चेतावनी नहीं।",
        "climatology_unavailable": "{place} के लिए अनुरोधित IMD जलवायु सामान्य उपलब्ध नहीं है। अनुपलब्ध मान अनुमान से नहीं दिया जाएगा।",
        "nwp_unavailable": "{place} के लिए NWP मॉडल डेटा उपलब्ध नहीं है। इसके स्थान पर परिचालन पूर्वानुमान या WeatherGPT भविष्यवाणी का उपयोग नहीं किया गया।",
        "nwp_available": "{place} के लिए {model} मॉडल मार्गदर्शन उपलब्ध है। आरंभ समय: {run}; वैध अवधि: {start} से {end}; स्रोत: {source}; मूल ग्रिड रिज़ॉल्यूशन: {resolution}°। यह मॉडल मार्गदर्शन है, अवलोकन, आधिकारिक चेतावनी या WeatherGPT भविष्यवाणी नहीं।",
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


_MONTH_NAMES = {
    "mr": ("", "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून", "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर"),
    "hi": ("", "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"),
}


def _localized_month(month: Any, language: str) -> str:
    try:
        return _MONTH_NAMES[language][int(month)]
    except (KeyError, IndexError, TypeError, ValueError):
        return str(month)


def _value(value: Any) -> str:
    return "unavailable" if value is None else str(value)


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
    if intent == "HISTORICAL_WEATHER":
        from calendar import month_name

        facts = response.historical_data or {}
        place = response.location or ""
        source = facts.get("source") or response.source
        if facts.get("kind") == "CLIMATOLOGY":
            if facts.get("status") != "available" or facts.get("normal") is None:
                message = t["climatology_unavailable"].format(place=place)
            else:
                month = facts.get("month")
                period = _localized_month(month, language)
                variable = {"rainfall": "पर्जन्य" if language == "mr" else "वर्षा", "tmax": "कमाल तापमान" if language == "mr" else "अधिकतम तापमान", "tmin": "किमान तापमान" if language == "mr" else "न्यूनतम तापमान"}.get(facts.get("variable"), str(facts.get("variable", "")))
                message = t["climatology"].format(place=place, period=period, variable=variable,
                    normal=_value(facts.get("normal")), units=facts.get("units", ""), baseline=facts.get("baseline", ""),
                    resolution=_value(facts.get("resolution_degrees")))
        elif facts.get("status") not in {"available", "partial"}:
            message = t["history_unavailable"].format(place=place)
        elif facts.get("analysis_kind") == "trend":
            trend = facts.get("trend") or {}
            if trend.get("status") == "available":
                message = t["history_trend"].format(place=place, slope=_value(trend.get("slope_per_year")),
                    start=_value(trend.get("period_start")), end=_value(trend.get("period_end")), count=_value(trend.get("observations")))
            else:
                message = t["history_trend_insufficient"].format(place=place, count=_value(trend.get("observations")), minimum=_value(trend.get("minimum_observations")))
        elif facts.get("analysis_kind") == "year_comparison" and facts.get("year_comparison"):
            comparison = facts["year_comparison"]
            message = t["history_comparison"].format(place=place, first_year=_value(comparison.get("first_year")),
                first=_value(comparison.get("first_rainfall_mm")), second_year=_value(comparison.get("second_year")),
                second=_value(comparison.get("second_rainfall_mm")), difference=_value(comparison.get("difference_mm")))
        elif facts.get("analysis_kind") == "normal_comparison" and facts.get("annual_climatology", {}).get("status") == "available":
            comparison = facts["annual_climatology"]
            message = t["history_normal"].format(place=place, period=_value(comparison.get("year")),
                observed=_value(comparison.get("observed_mm")), baseline=_value(comparison.get("baseline")),
                anomaly=_value(comparison.get("anomaly_mm")))
        elif facts.get("analysis_kind") in {"wettest", "driest"} and facts.get("selected_month"):
            selected = facts["selected_month"]
            period = f"{_localized_month(selected.get('month_number'), language)} {selected.get('year')}"
            message = t["history_wettest" if facts["analysis_kind"] == "wettest" else "history_driest"].format(
                period=period, amount=_value(selected.get("total_rainfall")))
        else:
            summary = facts.get("summary") or {}
            period_data = facts.get("requested_period") or {}
            start_text, end_text = period_data.get("start"), period_data.get("end")
            years = facts.get("requested_years") or []
            if len(years) == 1:
                period = str(years[0])
            elif facts.get("requested_month"):
                period = f"{_localized_month(facts['requested_month'], language)} {start_text[:4] if start_text else ''}".strip()
            elif start_text and end_text:
                period = f"{start_text}–{end_text}"
            else:
                period = f"{summary.get('period_start', '')}–{summary.get('period_end', '')}"
            message = t["history_rainfall"].format(place=place, period=period,
                amount=_value(summary.get("total_rainfall")), count=_value(summary.get("rainfall_observations")))
        if source:
            message += f"\n{t['sources']} {source}"
        return response.model_copy(update={"message": message})
    if intent == "AGRICULTURE" and response.agriculture_data:
        data = response.agriculture_data
        recommendation = data.get("recommendation") or {}
        activity = str(recommendation.get("activity", "general"))
        condition = str(recommendation.get("condition", "insufficient_data"))
        activities = {
            "irrigation": ("सिंचन नियोजन", "सिंचाई योजना"), "sowing": ("पेरणी मार्गदर्शन", "बुवाई मार्गदर्शन"),
            "spraying": ("फवारणीसाठी हवामान", "छिड़काव का मौसम"), "harvesting": ("कापणी", "कटाई"),
            "field_operations": ("शेतातील कामे", "खेत के काम"), "heat_stress": ("पीक/हवामान उष्णतेची चिंता", "फसल/मौसम गर्मी की चिंता"),
            "heavy_rain": ("पावसाबाबत चिंता", "वर्षा की चिंता"), "wind_risk": ("वाऱ्याबाबत चिंता", "हवा की चिंता"),
            "general": ("सामान्य शेती हवामान", "सामान्य कृषि मौसम"),
        }
        recommendations = {
            "rain_may_reduce_need": ("अंदाज किंवा GFS मध्ये पावसाची शक्यता दिसते; त्यामुळे तातडीच्या सिंचनाची गरज कमी होऊ शकते. निर्णयापूर्वी मातीतील ओलावा आणि पिकाची गरज तपासा.", "पूर्वानुमान या GFS में बारिश की संभावना है; इससे तुरंत सिंचाई की जरूरत कम हो सकती है। निर्णय से पहले मिट्टी की नमी और फसल की जरूरत जाँचें।"),
            "monitor_soil_moisture": ("मातीतील ओलाव्याचे किंवा अलीकडील पावसाचे पुरेसे मोजमाप उपलब्ध नाही. शेतातील ओलावा तपासा; पिकाच्या आणि शेताच्या स्थितीनुसार सिंचन ठरवा.", "मिट्टी की नमी या हाल की वर्षा का पर्याप्त माप उपलब्ध नहीं है। खेत की नमी जाँचें और फसल व खेत की स्थिति के अनुसार सिंचाई तय करें।"),
            "unfavorable_weather_signal": ("उपलब्ध माहितीमध्ये पाऊस, जोरदार वारा किंवा जास्त तापमानाचा संकेत आहे; फवारणी पुढे ढकलण्याचा विचार करा आणि उत्पादनाच्या लेबल व स्थानिक सुरक्षितता मार्गदर्शनाचे पालन करा.", "उपलब्ध जानकारी में बारिश, तेज हवा या अधिक तापमान का संकेत है; छिड़काव टालने पर विचार करें और उत्पाद लेबल व स्थानीय सुरक्षा मार्गदर्शन का पालन करें।"),
            "wind_caution": ("अंदाजातील वाऱ्यामुळे फवारणीचा फवारा वाहून जाण्याचा धोका वाढू शकतो; स्थानिक परिस्थिती आणि उत्पादन मार्गदर्शन तपासा.", "पूर्वानुमान की हवा से छिड़काव बहने का जोखिम बढ़ सकता है; स्थानीय स्थिति और उत्पाद निर्देश जाँचें।"),
            "wet_weather_signal": ("अलीकडील कालावधीच्या अंदाजात ओल्या हवामानाची शक्यता आहे. पीक-विशिष्ट मातीची ओल आणि शेताची स्थिती योग्य असल्यासच पेरणीचा विचार करा.", "हाल की अवधि के पूर्वानुमान में गीले मौसम की संभावना है। फसल के अनुसार मिट्टी की नमी और खेत की स्थिति सही हो तभी बुवाई पर विचार करें।"),
            "no_rain_signal": ("उपलब्ध अंदाजात पावसाचा ठळक संकेत नाही. पेरणीपूर्वी बीजपेरणीसाठीची मातीची ओल आणि स्थानिक मार्गदर्शन तपासा.", "उपलब्ध पूर्वानुमान में बारिश का मजबूत संकेत नहीं है। बुवाई से पहले बीज-क्षेत्र की नमी और स्थानीय मार्गदर्शन जाँचें।"),
            "rainfall_concern": ("आगामी पावसाची शक्यता कापणी किंवा शेतातील वाहतुकीवर परिणाम करू शकते; पिकाची परिपक्वता आणि प्रत्यक्ष शेतस्थिती तपासा.", "आने वाली बारिश की संभावना कटाई या खेत तक पहुँच को प्रभावित कर सकती है; फसल की परिपक्वता और वास्तविक खेत स्थिति जाँचें।"),
            "weather_caution": ("पाऊस किंवा वाढलेला वारा शेतातील कामावर परिणाम करू शकतो; स्थानिक शेतस्थिती आणि प्रवेशयोग्यता तपासा.", "बारिश या तेज हवा खेत के काम को प्रभावित कर सकती है; स्थानीय खेत स्थिति और पहुँच जाँचें।"),
            "high_weather_heat_concern": ("उच्च हवेचे तापमान पीक/हवामान उष्णतेची चिंता दर्शवते. थंड वेळेत कामाचे नियोजन करा आणि पिकांचे निरीक्षण करा; हा पीक-रोग निदान नाही.", "अधिक वायु तापमान फसल/मौसम गर्मी की चिंता दर्शाता है। ठंडे समय में काम रखें और फसल पर नजर रखें; यह फसल रोग का निदान नहीं है।"),
            "moderate_weather_heat_concern": ("उबदार तापमानामुळे मध्यम पीक/हवामान उष्णतेची चिंता आहे. पिके आणि शेतस्थितीचे निरीक्षण करा.", "गर्म तापमान से मध्यम फसल/मौसम गर्मी की चिंता है। फसल और खेत की स्थिति पर नजर रखें।"),
            "high_weather_rainfall_concern": ("GFS ने त्याच्या उपलब्ध रन-ते-वैध-वेळ कालावधीत जास्त संचयी पावसाची चिंता दर्शवली आहे; निचरा आणि शेतातील प्रवेशावर लक्ष ठेवा. हा अधिकृत इशारा नाही.", "GFS ने उपलब्ध रन-से-वैध-समय अवधि में अधिक संचयी वर्षा की चिंता दिखाई है; जलनिकासी और खेत तक पहुँच पर नजर रखें। यह आधिकारिक चेतावनी नहीं है।"),
            "elevated_weather_wind_concern": ("वाऱ्याचा वेग WeatherGPT च्या वाढीव-चिंता स्क्रीनिंग मर्यादेपेक्षा जास्त आहे; उघड्या शेतातील कामात काळजी घ्या.", "हवा की गति WeatherGPT की बढ़ी हुई चिंता सीमा से अधिक है; खुले खेत में काम करते समय सावधानी रखें।"),
            "high_weather_wind_concern": ("वाऱ्याचा वेग WeatherGPT च्या उच्च-चिंता स्क्रीनिंग मर्यादेपेक्षा जास्त आहे; हलक्या वस्तू सुरक्षित करा आणि उघड्या शेतस्थिती तपासा.", "हवा की गति WeatherGPT की उच्च चिंता सीमा से अधिक है; हल्की वस्तुएँ सुरक्षित रखें और खुले खेत की स्थिति जाँचें।"),
            "insufficient_data": ("या शिफारसीसाठी पुरेशी पडताळलेली हवामान मोजमापे उपलब्ध नाहीत; मी अंदाजाने मूल्ये देत नाही.", "इस सलाह के लिए पर्याप्त सत्यापित मौसम माप उपलब्ध नहीं हैं; कोई मान अनुमान से नहीं दिया गया है।"),
        }
        place = response.location or ""
        action = activities.get(activity, activities["general"])[0 if language == "mr" else 1]
        advice_text = recommendations.get(condition, ("उपलब्ध हवामान माहिती तपासा आणि प्रत्यक्ष शेतस्थितीनुसार काम ठरवा.", "उपलब्ध मौसम जानकारी देखें और वास्तविक खेत स्थिति के अनुसार काम तय करें।"))[0 if language == "mr" else 1]
        title = "WeatherGPT शेती हवामान सल्ला" if language == "mr" else "WeatherGPT कृषि मौसम सलाह"
        disclaimer = "हा अधिकृत कृषी विभागाचा सल्ला नाही." if language == "mr" else "यह आधिकारिक कृषि विभाग की सलाह नहीं है।"
        evidence = recommendation.get("evidence") or []
        evidence_lines = [f"• {item.get('label')}: {item.get('value')}{(' ' + str(item.get('unit')) if item.get('unit') else '')} ({item.get('source')})" for item in evidence]
        sources = recommendation.get("sources") or []
        message = f"{title}\n\n{place} · {action}\n\n{advice_text}\n\n{disclaimer}"
        if evidence_lines:
            message += "\n\n" + t["factors"] + "\n" + "\n".join(evidence_lines)
        message += "\n\n" + t["sources"] + " " + (", ".join(sources) if sources else "उपलब्ध नाही" if language == "mr" else "उपलब्ध नहीं")
        return response.model_copy(update={"message": message})
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
    elif intent == "NWP":
        facts = response.nwp_data or {}
        place = response.location or ""
        if facts.get("status") not in {"available", "partial"}:
            message = t["nwp_unavailable"].format(place=place)
        else:
            message = t["nwp_available"].format(place=place, model=facts.get("model", "GFS"),
                run=_value(facts.get("initialization_time")), start=_value(facts.get("forecast_start")),
                end=_value(facts.get("forecast_end")), source=facts.get("source", "NOAA/NCEP NOMADS"),
                resolution=_value(facts.get("resolution_degrees")))
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
