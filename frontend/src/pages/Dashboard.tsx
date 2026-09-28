import { useState } from 'react';
import { AlertCircle, ArrowRight, Cloud, CloudRain, CloudSun, Compass, MapPin, Search, Sparkles, AlertTriangle, Bot, ChartNoAxesCombined, History, Leaf, Map, Mic, Sun, Umbrella, type LucideIcon } from 'lucide-react';
import CurrentWeatherCard from '../components/weather/CurrentWeatherCard';
import WeatherSearch from '../components/weather/WeatherSearch';
import { getCurrentWeather, getForecast, getWeatherAlerts, WeatherApiError } from '../services/weatherApi';
import type { ForecastDay, ForecastResponse, WeatherAlertsResponse, WeatherResponse } from '../types/weather';
import { conditionLabel, localeFor, t, useLanguage } from '../i18n';
import type { AppPage } from '../components/layout/AppHeader';

interface DashboardProps {
  onOpenChat: () => void;
  onOpenAlerts?: () => void;
  onNavigate?: (page: AppPage) => void;
}

export default function Dashboard({ onOpenChat, onOpenAlerts = () => undefined, onNavigate = () => undefined }: DashboardProps) {
  const { language } = useLanguage();
  const [city, setCity] = useState('Dhule');
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [officialAlerts, setOfficialAlerts] = useState<WeatherAlertsResponse | null>(null);
  const [forecastPreview, setForecastPreview] = useState<ForecastResponse | null>(null);
  const [forecastUnavailable, setForecastUnavailable] = useState(false);
  const [alertsUnavailable, setAlertsUnavailable] = useState(false);

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
      setOfficialAlerts(null); setForecastPreview(null); setForecastUnavailable(false); setAlertsUnavailable(false);
      void getWeatherAlerts(city).then((alerts) => { setOfficialAlerts(alerts); setAlertsUnavailable(false); }).catch(() => { setOfficialAlerts(null); setAlertsUnavailable(true); });
      void getForecast(city).then((forecast) => { setForecastPreview(forecast); setForecastUnavailable(false); }).catch(() => { setForecastPreview(null); setForecastUnavailable(true); });
    } catch (requestError) {
      const message = requestError instanceof WeatherApiError
        ? requestError.message
        : 'Something went wrong. Please try your search again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  const activeAlerts = officialAlerts?.forecast_days.filter((day) => day.is_active) ?? [];

  return (
    <div className="bg-canvas text-ink">
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

        {!loading && activeAlerts.map((day) => <button type="button" key={day.date} onClick={onOpenAlerts} className="mt-5 flex w-full items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-left text-amber-950 shadow-sm"><AlertTriangle className="mt-0.5 shrink-0"/><span><strong className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] uppercase tracking-wide">Official IMD warning</span><span>{day.warnings.map((warning) => warning.warning_type).join(', ')}</span></strong><span className="mt-1 block text-sm">{officialAlerts?.district} · {new Date(day.date).toLocaleDateString(localeFor(language), { dateStyle: 'medium', timeZone: 'UTC' })} · {day.severity ?? 'Severity not specified'}</span></span></button>)}

        {!loading && forecastPreview && forecastPreview.forecast.length > 0 && <section className="mt-9" aria-labelledby="dashboard-forecast-heading">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-brand">{t(language, 'Operational forecast')} · {forecastPreview.source}</p><h2 id="dashboard-forecast-heading" className="mt-1 text-xl font-semibold">{forecastPreview.forecast.length}-day outlook for {forecastPreview.location.name}</h2></div><button type="button" onClick={() => onNavigate('forecast')} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-line bg-white px-3 text-sm font-semibold text-brand hover:bg-blue-50">{t(language, 'Full forecast')} <ArrowRight size={15}/></button></div>
          <div className="weather-forecast-strip flex gap-3 overflow-x-auto pb-3" aria-label="Provider forecast cards">{forecastPreview.forecast.map((day) => <ForecastPreviewCard key={day.date} day={day}/>)}</div>
        </section>}
        {!loading && forecastUnavailable && weather && <p className="mt-6 rounded-xl border border-line bg-white p-4 text-sm text-muted">Forecast data is unavailable for this location right now. Current conditions are shown separately.</p>}

        {!loading && weather && <section className="mt-8" aria-labelledby="weather-insights-heading">
          <div className="mb-4"><p className="text-xs font-semibold uppercase tracking-[.14em] text-brand">{t(language, 'Grounded services')}</p><h2 id="weather-insights-heading" className="mt-1 text-xl font-semibold">{t(language, 'Weather insights')}</h2></div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <InsightCard icon={Compass} title="WeatherGPT advisory" detail="Use available forecast and official warning context." action="Open advisory" onClick={() => onNavigate('advisory')}/>
            <InsightCard icon={AlertTriangle} title="Official IMD warnings" detail={alertsUnavailable ? 'Official IMD warning data currently unavailable.' : officialAlerts ? activeAlerts.length ? `${activeAlerts.length} active warning day(s) returned for ${officialAlerts.district}.` : 'No active warning was reported by IMD for the returned period.' : 'Search a location to check the connected IMD warning source.'} action="View warnings" onClick={onOpenAlerts}/>
            <InsightCard icon={Leaf} title="Agriculture advisory" detail="Weather-based recommendations from the existing advisory service." action="Open agriculture" onClick={() => onNavigate('agriculture')}/>
            <InsightCard icon={ChartNoAxesCombined} title="Climate analysis" detail="Trend charts require validated historical climate series." action="View data status" onClick={() => onNavigate('climate')}/>
          </div>
        </section>}

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

        <section className="mt-9" aria-labelledby="quick-actions-heading">
          <div className="mb-4 flex items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.14em] text-brand">{t(language, 'Explore WeatherGPT')}</p><h2 id="quick-actions-heading" className="mt-1 text-xl font-semibold">{t(language, 'Quick actions')}</h2></div><p className="hidden text-xs text-muted sm:block">Open a connected service or a clearly labelled data status page.</p></div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {([
              ['Forecast', 'Open the available provider forecast.', 'forecast', Umbrella],
              ['Weather Alerts', 'Check official IMD warning availability.', 'alerts', AlertTriangle],
              ['Weather Map', 'View map data connection status.', 'map', Map],
              ['Climate Analysis', 'Review climate data validation status.', 'climate', ChartNoAxesCombined],
              ['AI Assistant', 'Ask through the existing weather chat.', 'chat', Bot],
              ['Agriculture Advisory', 'Request weather-based farm guidance.', 'agriculture', Leaf],
              ['Historical Data', 'Query the existing historical API.', 'historical', History],
              ['Voice Assistant', 'Use microphone input in the chat.', 'chat', Mic],
            ] as const).map(([title, description, destination, Icon]) => <button key={title} type="button" onClick={() => destination === 'chat' ? onOpenChat() : onNavigate(destination)} className="group flex min-h-28 items-start gap-3 rounded-2xl border border-line bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-card focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-brand"><Icon size={18}/></span><span className="min-w-0"><span className="block text-sm font-semibold text-ink">{t(language, title)}</span><span className="mt-1 block text-xs leading-5 text-muted">{t(language, description)}</span></span><ArrowRight size={15} className="ml-auto mt-1 shrink-0 text-slate-400 transition group-hover:text-brand"/></button>)}
          </div>
        </section>

        <footer className="mt-10 text-center text-xs text-slate-500">Weather information is provided by your connected weather data source.</footer>
      </main>
    </div>
  );
}

function ForecastPreviewCard({ day }: { day: ForecastDay }) {
  const { language } = useLanguage();
  const description = day.description.toLowerCase();
  const Icon = description.includes('rain') || description.includes('drizzle') || description.includes('thunder') ? CloudRain : description.includes('clear') ? Sun : description.includes('cloud') ? CloudSun : Cloud;
  return <article className="min-w-[190px] flex-1 rounded-2xl border border-line bg-white p-4 shadow-sm sm:min-w-[200px]">
    <p className="text-xs font-semibold text-muted">{new Date(day.date).toLocaleDateString(localeFor(language), { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' })}</p>
    <div className="my-3 flex items-center justify-between"><Icon className="text-brand" size={25} aria-hidden="true"/><span className="text-xs capitalize text-muted">{conditionLabel(language, day.description)}</span></div>
    <p className="text-xl font-semibold text-ink">{Math.round(day.temperature_max)}° <span className="text-sm font-normal text-muted">/ {Math.round(day.temperature_min)}°C</span></p>
    <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">{day.rain_probability !== null && <span>{t(language, 'Rain')} {Math.round(day.rain_probability)}%</span>}{day.wind_speed !== null && <span>{t(language, 'Wind')} {day.wind_speed.toFixed(1)} m/s</span>}</div>
  </article>;
}

function InsightCard({ icon: Icon, title, detail, action, onClick }: { icon: LucideIcon; title: string; detail: string; action: string; onClick: () => void }) {
  const { language } = useLanguage();
  return <article className="flex min-h-40 flex-col rounded-2xl border border-line bg-white p-4 shadow-sm"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50 text-brand"><Icon size={17}/></span><h3 className="mt-3 text-sm font-semibold text-ink">{t(language, title)}</h3><p className="mt-1 flex-1 text-xs leading-5 text-muted">{t(language, detail)}</p><button type="button" onClick={onClick} className="mt-3 self-start text-xs font-semibold text-brand hover:underline">{t(language, action)} →</button></article>;
}
