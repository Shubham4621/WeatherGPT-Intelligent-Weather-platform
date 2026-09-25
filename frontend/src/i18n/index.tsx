import { createContext, useContext } from 'react';

export type Language = 'en' | 'mr' | 'hi';
export const LANGUAGE_LABELS: Record<Language, string> = { en: 'English', mr: 'मराठी', hi: 'हिन्दी' };
export const LanguageContext = createContext<{ language: Language; setLanguage: (language: Language) => void }>({ language: 'en', setLanguage: () => undefined });
export const useLanguage = () => useContext(LanguageContext);

const dictionaries: Record<Language, Record<string, string>> = {
  en: {},
  mr: {
    Dashboard: 'डॅशबोर्ड', Chat: 'चॅट', Forecast: 'अंदाज', Alerts: 'इशारे', Advisory: 'सल्ला',
    Weather: 'हवामान', Search: 'शोधा', Settings: 'सेटिंग्ज', Loading: 'लोड होत आहे', Retry: 'पुन्हा प्रयत्न करा',
    Error: 'त्रुटी', 'No data': 'माहिती उपलब्ध नाही', Location: 'स्थान', Temperature: 'तापमान', Humidity: 'आर्द्रता',
    Wind: 'वारा', 'Rain probability': 'पावसाची शक्यता', Today: 'आज', Tomorrow: 'उद्या', Source: 'स्रोत',
    'Retrieved at': 'माहिती मिळाल्याची वेळ', 'Get forecast': 'अंदाज मिळवा', 'Get Advisory': 'सल्ला मिळवा',
    'Weather Alerts': 'हवामान इशारे', 'Weather Advisory': 'हवामान सल्ला', 'Forecast intelligence': 'हवामान अंदाज',
    'Search city for alerts': 'इशाऱ्यांसाठी शहर शोधा', 'Loading alerts…': 'इशारे लोड होत आहेत…', 'Loading forecast…': 'अंदाज लोड होत आहे…',
    'Official Source': 'अधिकृत स्रोत', 'Official warning intelligence': 'अधिकृत इशारा माहिती', 'Decision support': 'निर्णय सहाय्य',
    'Unable to retrieve official weather warnings. Please try again later.': 'अधिकृत हवामान इशारे मिळवता आले नाहीत. कृपया नंतर पुन्हा प्रयत्न करा.',
    'No official warning reported for this day': 'या दिवसासाठी अधिकृत इशारा नोंदवलेला नाही',
    'No official IMD weather warning is currently reported': 'सध्या कोणताही अधिकृत IMD हवामान इशारा नोंदवलेला नाही',
    'Search current weather by city name': 'शहराच्या नावाने सध्याचे हवामान शोधा', 'Find a location': 'स्थान शोधा',
    'Current weather assistant': 'सध्याच्या हवामानासाठी सहाय्यक', 'Ask WeatherGPT': 'WeatherGPT ला विचारा',
    'WeatherGPT assistant': 'WeatherGPT सहाय्यक', 'Grounded in current provider data': 'प्रत्यक्ष हवामान माहितीवर आधारित',
    'Ask about current weather in a city…': 'शहरातील हवामानाबद्दल विचारा…', 'Send message': 'संदेश पाठवा', 'Clear chat': 'चॅट साफ करा',
    'Factors': 'घटक', Recommendations: 'शिफारसी', Date: 'तारीख', Activity: 'कृती', 'IMD Level': 'IMD स्तर',
    'Temperature trend (°C)': 'तापमानातील बदल (°C)', 'Maximum temperatures': 'कमाल तापमान',
    'Generating advisory from available weather sources…': 'उपलब्ध हवामान स्रोतांवरून सल्ला तयार होत आहे…',
    'Fetching the latest available weather data': 'नवीनतम उपलब्ध हवामान माहिती घेत आहे',
    'Checking conditions for': 'हवामान स्थिती तपासत आहे:',
    'Current conditions': 'सध्याची स्थिती', 'Feels like': 'जाणवणारे तापमान', Observed: 'निरीक्षण वेळ',
    'Weather details': 'हवामान तपशील', 'Relative humidity': 'सापेक्ष आर्द्रता', 'Current wind': 'सध्याचा वारा',
    Gusts: 'वाऱ्याचे झोत', 'Wind speed': 'वाऱ्याचा वेग', 'Wind direction': 'वाऱ्याची दिशा', Pressure: 'दाब',
    Visibility: 'दृश्यमानता', 'Cloud cover': 'ढगांचे प्रमाण', 'Direction wind is coming from': 'वारा कोणत्या दिशेने येतो',
    'Sea-level pressure': 'समुद्रसपाटीवरील दाब', 'Horizontal visibility': 'आडवी दृश्यमानता', 'Sky coverage': 'आकाशातील ढगांचे प्रमाण',
    'Search weather by city': 'शहरानुसार हवामान शोधा',
    Searching: 'शोधत आहे',
    'Weather, made clearer.': 'हवामान अधिक स्पष्टपणे.',
    'Explore current conditions for your location, with real-time data from trusted weather sources.': 'विश्वसनीय हवामान स्रोतांमधील प्रत्यक्ष माहिती वापरून तुमच्या स्थानाची सध्याची स्थिती पाहा.',
    'District warnings published by the India Meteorological Department.': 'भारत हवामान विभागाने प्रकाशित केलेले जिल्हास्तरीय इशारे.',
    'Practical suggestions based on available forecast data and official IMD warnings. Risk levels below are WeatherGPT classifications, not official warning levels.': 'उपलब्ध अंदाज आणि अधिकृत IMD इशाऱ्यांवर आधारित सूचना. खालील जोखीम पातळी WeatherGPT ची आहे; ती अधिकृत इशारा पातळी नाही.',
    General: 'सामान्य', Travel: 'प्रवास', Commute: 'ये-जा', 'Outdoor activity': 'बाहेरील कृती', Exercise: 'व्यायाम', Event: 'कार्यक्रम', Agriculture: 'शेती',
    'Day after tomorrow': 'परवा', 'Official IMD Information': 'अधिकृत IMD माहिती', Meaning: 'अर्थ', District: 'जिल्हा', Issued: 'जारी केले',
    'Official IMD warning information could not be retrieved. This is not confirmation that no warning exists.': 'अधिकृत IMD इशाऱ्याची माहिती मिळाली नाही. याचा अर्थ इशारा नाही असा होत नाही.',
    'No official IMD warning was reported for this date; this does not mean there is zero weather risk.': 'या तारखेसाठी अधिकृत IMD इशारा नोंदवला नव्हता; याचा अर्थ हवामानाचा धोका शून्य आहे असा नाही.',
    'Your weather snapshot starts here': 'तुमची हवामान माहिती येथे दिसेल',
    'Enter a city above to see current conditions, temperature, wind, humidity, and more.': 'सध्याचे हवामान, तापमान, वारा, आर्द्रता आणि इतर माहिती पाहण्यासाठी वर शहर लिहा.',
  },
  hi: {
    Dashboard: 'डैशबोर्ड', Chat: 'चैट', Forecast: 'पूर्वानुमान', Alerts: 'चेतावनियाँ', Advisory: 'सलाह',
    Weather: 'मौसम', Search: 'खोजें', Settings: 'सेटिंग्स', Loading: 'लोड हो रहा है', Retry: 'फिर कोशिश करें',
    Error: 'त्रुटि', 'No data': 'कोई डेटा नहीं', Location: 'स्थान', Temperature: 'तापमान', Humidity: 'आर्द्रता',
    Wind: 'हवा', 'Rain probability': 'बारिश की संभावना', Today: 'आज', Tomorrow: 'कल', Source: 'स्रोत',
    'Retrieved at': 'प्राप्ति समय', 'Get forecast': 'पूर्वानुमान देखें', 'Get Advisory': 'सलाह प्राप्त करें',
    'Weather Alerts': 'मौसम चेतावनियाँ', 'Weather Advisory': 'मौसम सलाह', 'Forecast intelligence': 'मौसम पूर्वानुमान',
    'Search city for alerts': 'चेतावनियों के लिए शहर खोजें', 'Loading alerts…': 'चेतावनियाँ लोड हो रही हैं…', 'Loading forecast…': 'पूर्वानुमान लोड हो रहा है…',
    'Official Source': 'आधिकारिक स्रोत', 'Official warning intelligence': 'आधिकारिक चेतावनी जानकारी', 'Decision support': 'निर्णय सहायता',
    'Unable to retrieve official weather warnings. Please try again later.': 'आधिकारिक मौसम चेतावनी प्राप्त नहीं हो सकी। कृपया बाद में फिर कोशिश करें।',
    'No official warning reported for this day': 'इस दिन के लिए कोई आधिकारिक चेतावनी दर्ज नहीं है',
    'No official IMD weather warning is currently reported': 'वर्तमान में कोई आधिकारिक IMD मौसम चेतावनी दर्ज नहीं है',
    'Search current weather by city name': 'शहर के नाम से वर्तमान मौसम खोजें', 'Find a location': 'स्थान खोजें',
    'Current weather assistant': 'वर्तमान मौसम सहायक', 'Ask WeatherGPT': 'WeatherGPT से पूछें',
    'WeatherGPT assistant': 'WeatherGPT सहायक', 'Grounded in current provider data': 'वास्तविक मौसम डेटा पर आधारित',
    'Ask about current weather in a city…': 'किसी शहर के मौसम के बारे में पूछें…', 'Send message': 'संदेश भेजें', 'Clear chat': 'चैट साफ़ करें',
    'Factors': 'कारक', Recommendations: 'सुझाव', Date: 'तारीख', Activity: 'गतिविधि', 'IMD Level': 'IMD स्तर',
    'Temperature trend (°C)': 'तापमान का रुझान (°C)', 'Maximum temperatures': 'अधिकतम तापमान',
    'Generating advisory from available weather sources…': 'उपलब्ध मौसम स्रोतों से सलाह तैयार हो रही है…',
    'Fetching the latest available weather data': 'नवीनतम उपलब्ध मौसम डेटा प्राप्त किया जा रहा है',
    'Checking conditions for': 'मौसम की स्थिति जाँची जा रही है:',
    'Current conditions': 'वर्तमान स्थिति', 'Feels like': 'महसूस होने वाला तापमान', Observed: 'अवलोकन समय',
    'Weather details': 'मौसम विवरण', 'Relative humidity': 'सापेक्ष आर्द्रता', 'Current wind': 'वर्तमान हवा',
    Gusts: 'हवा के झोंके', 'Wind speed': 'हवा की गति', 'Wind direction': 'हवा की दिशा', Pressure: 'दबाव',
    Visibility: 'दृश्यता', 'Cloud cover': 'बादलों का आवरण', 'Direction wind is coming from': 'हवा किस दिशा से आ रही है',
    'Sea-level pressure': 'समुद्र तल का दबाव', 'Horizontal visibility': 'क्षैतिज दृश्यता', 'Sky coverage': 'आकाश का आवरण',
    'Search weather by city': 'शहर के अनुसार मौसम खोजें',
    Searching: 'खोज रहे हैं',
    'Weather, made clearer.': 'मौसम, अब और स्पष्ट।',
    'Explore current conditions for your location, with real-time data from trusted weather sources.': 'विश्वसनीय मौसम स्रोतों के वास्तविक समय के डेटा से अपने स्थान की वर्तमान स्थिति देखें।',
    'District warnings published by the India Meteorological Department.': 'भारत मौसम विज्ञान विभाग द्वारा प्रकाशित जिला चेतावनियाँ।',
    'Practical suggestions based on available forecast data and official IMD warnings. Risk levels below are WeatherGPT classifications, not official warning levels.': 'उपलब्ध पूर्वानुमान और आधिकारिक IMD चेतावनियों पर आधारित सुझाव। नीचे के जोखिम स्तर WeatherGPT वर्गीकरण हैं, आधिकारिक चेतावनी स्तर नहीं।',
    General: 'सामान्य', Travel: 'यात्रा', Commute: 'आवागमन', 'Outdoor activity': 'बाहरी गतिविधि', Exercise: 'व्यायाम', Event: 'कार्यक्रम', Agriculture: 'कृषि',
    'Day after tomorrow': 'परसों', 'Official IMD Information': 'आधिकारिक IMD जानकारी', Meaning: 'अर्थ', District: 'ज़िला', Issued: 'जारी किया गया',
    'Official IMD warning information could not be retrieved. This is not confirmation that no warning exists.': 'आधिकारिक IMD चेतावनी की जानकारी नहीं मिल सकी। इसका अर्थ यह नहीं कि कोई चेतावनी नहीं है।',
    'No official IMD warning was reported for this date; this does not mean there is zero weather risk.': 'इस तारीख के लिए कोई आधिकारिक IMD चेतावनी दर्ज नहीं थी; इसका अर्थ यह नहीं कि मौसम का जोखिम शून्य है।',
    'Your weather snapshot starts here': 'आपकी मौसम जानकारी यहाँ दिखाई देगी',
    'Enter a city above to see current conditions, temperature, wind, humidity, and more.': 'वर्तमान मौसम, तापमान, हवा, आर्द्रता और अन्य जानकारी के लिए ऊपर शहर दर्ज करें।',
  },
};

export function t(language: Language, text: string): string { return dictionaries[language][text] ?? text; }
export function conditionLabel(language: Language, condition: string): string {
  if (language === 'en') return condition;
  const value = condition.toLowerCase();
  const entries: Record<string, [string, string]> = {
    'clear sky': ['निरभ्र आकाश', 'साफ़ आसमान'], 'few clouds': ['काही ढग', 'कुछ बादल'],
    'scattered clouds': ['विखुरलेले ढग', 'छिटपुट बादल'], 'broken clouds': ['ढगाळ', 'बादल छाए हुए'],
    'overcast clouds': ['पूर्ण ढगाळ', 'घने बादल'], 'light rain': ['हलका पाऊस', 'हल्की बारिश'],
    'moderate rain': ['मध्यम पाऊस', 'मध्यम बारिश'], 'heavy rain': ['मुसळधार पाऊस', 'भारी बारिश'],
    thunderstorm: ['वादळी पाऊस', 'आंधी-तूफ़ान'], drizzle: ['रिमझिम पाऊस', 'बूंदाबांदी'],
    mist: ['धुके', 'धुंध'], fog: ['धुके', 'कोहरा'],
  };
  const key = Object.keys(entries).find((entry) => value.includes(entry));
  return key ? entries[key][language === 'mr' ? 0 : 1] : condition;
}
export function warningLabel(language: Language, code: number, original: string): string {
  if (language === 'en') return original;
  const labels: Record<number, [string, string]> = {
    2: ['मुसळधार पाऊस', 'भारी वर्षा'], 3: ['मुसळधार हिमवृष्टी', 'भारी हिमपात'],
    4: ['मेघगर्जना, वीज आणि वादळी वारे', 'गरज-चमक और तेज़ हवा'], 5: ['गारपीट', 'ओलावृष्टि'],
    6: ['धुळीचे वादळ', 'धूल भरी आँधी'], 7: ['धूळ उडवणारे वारे', 'धूल उड़ाने वाली हवाएँ'],
    8: ['जोरदार पृष्ठभागीय वारे', 'तेज़ सतही हवाएँ'], 9: ['उष्णतेची लाट', 'लू'],
    10: ['उष्ण दिवस', 'गर्म दिन'], 11: ['उष्ण रात्र', 'गर्म रात'], 12: ['थंडीची लाट', 'शीतलहर'],
    13: ['थंड दिवस', 'ठंडा दिन'], 14: ['भूपृष्ठावरील दंव', 'ज़मीनी पाला'], 15: ['धुके', 'कोहरा'],
    16: ['अतिवृष्टी', 'बहुत भारी वर्षा'], 17: ['अत्यंत मुसळधार पाऊस', 'अत्यंत भारी वर्षा'],
  };
  const translated = labels[code];
  return translated ? `${translated[language === 'mr' ? 0 : 1]} (${original})` : original;
}
export function localeFor(language: Language): string { return language === 'mr' ? 'mr-IN' : language === 'hi' ? 'hi-IN' : 'en-IN'; }
export function readLanguage(): Language {
  try { const value = window.localStorage.getItem('weathergpt-language'); return value === 'mr' || value === 'hi' ? value : 'en'; }
  catch { return 'en'; }
}
