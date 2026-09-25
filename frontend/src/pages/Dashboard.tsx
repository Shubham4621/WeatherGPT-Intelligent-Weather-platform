import { useState } from 'react';
import { AlertCircle, ArrowRight, CloudSun, MapPin, Search, Sparkles, AlertTriangle } from 'lucide-react';
import CurrentWeatherCard from '../components/weather/CurrentWeatherCard';
import WeatherSearch from '../components/weather/WeatherSearch';
import { getCurrentWeather, getWeatherAlerts, WeatherApiError } from '../services/weatherApi';
import type { WeatherAlertsResponse, WeatherResponse } from '../types/weather';
import { t, useLanguage } from '../i18n';

interface DashboardProps {
  onOpenChat: () => void;
  onOpenAlerts?: () => void;
}

export default function Dashboard({ onOpenChat, onOpenAlerts = () => undefined }: DashboardProps) {
  const { language } = useLanguage();
  const [city, setCity] = useState('Dhule');
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [officialAlerts, setOfficialAlerts] = useState<WeatherAlertsResponse | null>(null);

  async function searchWeather() {
    if (!city.trim()) {
      setError('Enter a city to search.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await getCurrentWeather(city);
      setWeather(result);
      void getWeatherAlerts(city).then(setOfficialAlerts).catch(() => setOfficialAlerts(null));
    } catch (requestError) {
      const message = requestError instanceof WeatherApiError
        ? requestError.message
        : 'Something went wrong. Please try your search again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <main id="main" className="mx-auto max-w-7xl px-5 pb-14 pt-8 sm:px-8 sm:pt-12">
        <div className="mb-8 max-w-3xl">
          <p className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-brand">
            <Sparkles size={14} aria-hidden="true" /> Weather intelligence
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">Weather, made clearer.</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-muted">Explore current conditions for your location, with real-time data from trusted weather sources.</p>
        </div>

        <section aria-labelledby="search-heading" className="mb-8 rounded-3xl border border-line bg-white p-5 shadow-card sm:p-7">
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-brand"><MapPin size={19} aria-hidden="true" /></span>
            <div><h2 id="search-heading" className="font-semibold text-ink">{t(language, 'Find a location')}</h2><p className="text-sm text-muted">{t(language, 'Search current weather by city name')}</p></div>
          </div>
          <WeatherSearch city={city} loading={loading} onCityChange={setCity} onSearch={searchWeather} />
          {error && (
            <div className="mt-4 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">
              <AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
              <p>{error}</p>
            </div>
          )}
        </section>

        {loading && (
          <div className="flex min-h-72 flex-col items-center justify-center rounded-3xl border border-line bg-white text-center shadow-card" role="status" aria-live="polite">
            <span className="large-spinner" aria-hidden="true" />
            <p className="mt-5 font-semibold text-ink">{t(language, 'Checking conditions for')} {city.trim()}…</p>
            <p className="mt-1 text-sm text-muted">{t(language, 'Fetching the latest available weather data')}</p>
          </div>
        )}

        {!loading && weather && <CurrentWeatherCard data={weather} />}

        {!loading && officialAlerts?.forecast_days.filter((day) => day.is_active).map((day) => <button type="button" key={day.date} onClick={onOpenAlerts} className="mt-5 flex w-full items-center gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-left text-amber-950"><AlertTriangle className="shrink-0"/><span><strong className="block">IMD Weather Alert</strong><span>{day.warnings.map((warning) => warning.warning_type).join(', ')} · {officialAlerts.district} · {day.severity ?? 'IMD level unspecified'}</span></span></button>)}

        {!loading && !weather && !error && (
          <section className="flex min-h-72 flex-col items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-white/60 px-5 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-brand"><CloudSun size={30} strokeWidth={1.5} aria-hidden="true" /></span>
            <h2 className="mt-4 text-lg font-semibold text-ink">{t(language, 'Your weather snapshot starts here')}</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted">{t(language, 'Enter a city above to see current conditions, temperature, wind, humidity, and more.')}</p>
            <p className="mt-4 flex items-center gap-1.5 text-xs font-medium text-slate-500"><Search size={13} aria-hidden="true" /> Try Dhule, Mumbai, or Pune</p>
          </section>
        )}

        <button type="button" onClick={onOpenChat} className="mt-7 flex w-full items-center justify-between gap-4 rounded-2xl border border-blue-100 bg-blue-50/70 p-5 text-left transition hover:border-blue-200 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand sm:p-6">
          <span><span className="block font-semibold text-ink">Want to ask about the weather?</span><span className="mt-1 block text-sm text-muted">Chat with WeatherGPT about current conditions in any city.</span></span>
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-brand"><ArrowRight size={18} aria-hidden="true" /></span>
        </button>

        <footer className="mt-10 text-center text-xs text-slate-500">Weather information is provided by your connected weather data source.</footer>
      </main>
    </div>
  );
}
