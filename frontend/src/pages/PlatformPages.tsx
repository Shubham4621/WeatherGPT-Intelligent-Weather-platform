import { lazy, Suspense, useState } from 'react';
import { Anchor, CloudOff, Plane, ShieldAlert } from 'lucide-react';
import { getNwpForecast, getRainfallPrediction, WeatherApiError, type NwpForecastResponse, type RainfallPrediction } from '../services/weatherApi';
import { t, useLanguage } from '../i18n';
import WeatherMap from './WeatherMap';
const ClimateAnalysis = lazy(() => import('./ClimateAnalysis'));

function SectionIntro({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  const { language } = useLanguage();
  return <header className="mb-7"><p className="text-xs font-semibold uppercase tracking-[.16em] text-brand">{t(language, eyebrow)}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">{t(language, title)}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{t(language, description)}</p></header>;
}

function AvailabilityCard({ title, status, children }: { title: string; status: string; children: string }) {
  const { language } = useLanguage();
  return <article className="rounded-2xl border border-line bg-white p-5 shadow-card"><div className="flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-muted"><CloudOff size={19}/></span><div><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold text-ink">{t(language, title)}</h2><span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-900">{t(language, status)}</span></div><p className="mt-2 text-sm leading-6 text-muted">{t(language, children)}</p></div></div></article>;
}

export function WeatherMapPage() {
  return <WeatherMap/>;
}

export function ClimatePage() {
  const { language } = useLanguage();
  return <Suspense fallback={<main id="main" role="status" className="mx-auto max-w-7xl px-5 py-8 text-sm text-muted">{t(language, 'Loading')}</main>}><ClimateAnalysis /></Suspense>;
}

export function AviationPage() {
  return <main id="main" className="mx-auto max-w-6xl px-5 py-8 sm:px-8"><SectionIntro eyebrow="Operational context" title="Aviation Weather" description="Aviation conditions require dedicated observations, terminal forecasts, and aviation warnings."/><div className="grid gap-4 sm:grid-cols-2"><AvailabilityCard title="Visibility and wind" status="Data unavailable">The current weather service does not expose aviation-grade visibility and wind products for this dashboard.</AvailabilityCard><AvailabilityCard title="Aviation warnings" status="Integration pending">No METAR, TAF, or aviation warning feed is connected. This view does not replace official aeronautical information.</AvailabilityCard></div><div className="mt-5 flex items-center gap-3 rounded-2xl border border-line bg-white p-5"><Plane className="text-muted"/><p className="text-sm text-muted">Weather observations available elsewhere in WeatherGPT are not presented as certified aviation products.</p></div></main>;
}

export function MarinePage() {
  return <main id="main" className="mx-auto max-w-6xl px-5 py-8 sm:px-8"><SectionIntro eyebrow="Marine conditions" title="Marine Weather" description="Marine guidance needs coastal and ocean observations, marine forecasts, and relevant warnings."/><div className="grid gap-4 sm:grid-cols-2"><AvailabilityCard title="Wind and sea state" status="Data unavailable">No marine forecast or wave-height source is connected.</AvailabilityCard><AvailabilityCard title="Marine warnings" status="Integration pending">No official marine warning feed is available in the current backend.</AvailabilityCard></div><div className="mt-5 flex items-center gap-3 rounded-2xl border border-line bg-white p-5"><Anchor className="text-muted"/><p className="text-sm text-muted">No sea-state or storm values are displayed without a marine data source.</p></div></main>;
}

export function NwpPage() {
  const [location, setLocation] = useState('Nashik');
  const [result, setResult] = useState<NwpForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function load(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError(null); setResult(null);
    try { setResult(await getNwpForecast(location)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'NWP provider is unavailable.'); }
    finally { setLoading(false); }
  }
  return <main id="main" className="mx-auto max-w-6xl px-5 py-8 sm:px-8"><SectionIntro eyebrow="Numerical weather prediction" title="NWP Model Data" description="Retrieved GFS numerical model output. This remains separate from the operational forecast, IMD warnings, observations, and WeatherGPT prediction."/><form onSubmit={load} className="mb-5 flex flex-wrap gap-3 rounded-2xl border border-line bg-white p-4 shadow-card"><label className="min-w-60 flex-1 text-xs font-medium text-muted">City or latitude, longitude<input value={location} onChange={e => setLocation(e.target.value)} placeholder="Nashik or 19.99, 73.78" className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink"/></label><button disabled={loading} className="mt-auto min-h-11 rounded-xl bg-brand px-5 text-sm font-semibold text-white disabled:opacity-60">{loading ? 'Loading NWP…' : 'Get GFS model output'}</button></form>
    {error && <div role="alert" className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">NWP provider error: {error}</div>}
    {result && (result.status === 'unavailable' || result.status === 'error') && <div role="status" className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">NWP data {result.status}: {result.reason ?? 'No model data returned.'}</div>}
    {result && ['available', 'partial'].includes(result.status) && <section className="space-y-4"><div className="rounded-2xl border border-line bg-white p-5 shadow-card"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-brand">NWP model output · {result.model}</p><h2 className="mt-1 text-lg font-semibold text-ink">{String(result.location?.city ?? result.location?.query ?? location)}</h2><p className="mt-2 text-sm text-muted">Provider: {result.source} · Native grid: {result.resolution_degrees}° · Status: {result.status}</p></div><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-brand">{result.points.length} valid times</span></div><div className="mt-4 grid gap-3 sm:grid-cols-2"><Metric label="Model run (UTC)" value={result.initialization_time ? new Date(result.initialization_time).toLocaleString() : 'Unavailable'}/><Metric label="Valid period (UTC)" value={result.forecast_start && result.forecast_end ? `${new Date(result.forecast_start).toLocaleString()} — ${new Date(result.forecast_end).toLocaleString()}` : 'Unavailable'}/></div>{result.selected_grid_point && <p className="mt-3 text-xs text-muted">Selected model grid: {result.selected_grid_point.latitude.toFixed(3)}, {result.selected_grid_point.longitude.toFixed(3)} · {result.selected_grid_point.distance_km.toFixed(2)} km from request</p>}<p className="mt-3 text-xs text-muted">Source/provenance: {result.provenance} · Retrieved {result.retrieved_at ? new Date(result.retrieved_at).toLocaleString() : 'time unavailable'}</p>{result.status === 'partial' && <p className="mt-2 text-sm text-amber-800">Some forecast leads unavailable: {result.missing_leads.join(', ')} hours.</p>}</div><div className="overflow-x-auto rounded-2xl border border-line bg-white shadow-card"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-muted"><tr><th className="p-3">Forecast valid time</th><th className="p-3">Temperature</th>{result.points.some(p => p.precipitation_since_initialization_mm != null) && <th className="p-3">Accum. precip. since run</th>}{result.points.some(p => p.wind_speed_ms != null) && <th className="p-3">10 m wind speed</th>}</tr></thead><tbody>{result.points.map(point => <tr key={point.forecast_time} className="border-t border-line"><td className="p-3">{new Date(point.forecast_time).toLocaleString()}</td><td className="p-3">{point.temperature_c == null ? '—' : `${point.temperature_c.toFixed(1)} °C`}</td>{result.points.some(p => p.precipitation_since_initialization_mm != null) && <td className="p-3">{point.precipitation_since_initialization_mm == null ? '—' : `${point.precipitation_since_initialization_mm.toFixed(1)} mm`}</td>}{result.points.some(p => p.wind_speed_ms != null) && <td className="p-3">{point.wind_speed_ms == null ? '—' : `${point.wind_speed_ms.toFixed(1)} m/s`}</td>}</tr>)}</tbody></table></div><p className="text-xs text-muted">Variables shown: {Object.keys(result.units).join(', ')}. GFS values are model output, not observations, an official IMD warning, an operational provider forecast, or a WeatherGPT ML prediction.</p></section>}
  </main>;
}

export function SettingsPage({ darkMode, onToggleTheme }: { darkMode: boolean; onToggleTheme: () => void }) {
  return <main id="main" className="mx-auto max-w-4xl px-5 py-8 sm:px-8"><SectionIntro eyebrow="Preferences" title="Settings" description="Manage the display preferences available in this browser."/><section className="rounded-2xl border border-line bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="font-semibold">Appearance</h2><p className="mt-1 text-sm text-muted">Theme preference: {darkMode ? 'Dark' : 'Light'}</p></div><button type="button" onClick={onToggleTheme} className="min-h-11 rounded-xl border border-line px-4 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand">Switch to {darkMode ? 'light' : 'dark'} theme</button></div><p className="mt-4 text-xs text-muted">Language can be changed from the top bar. Voice availability depends on browser speech support.</p></section></main>;
}

export function PredictionPage() {
  const [latitude, setLatitude] = useState('20.90');
  const [longitude, setLongitude] = useState('74.80');
  const [result, setResult] = useState<RainfallPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function predict(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError(null); setResult(null);
    try { setResult(await getRainfallPrediction(Number(latitude), Number(longitude), 1)); }
    catch (cause) { setError(cause instanceof WeatherApiError ? cause.message : 'WeatherGPT model prediction is currently unavailable.'); }
    finally { setLoading(false); }
  }
  return <main id="main" className="mx-auto max-w-6xl px-5 py-8 sm:px-8"><SectionIntro eyebrow="Experimental model output" title="Rainfall Prediction" description="One-day rainfall estimate from the existing WeatherGPT model endpoint. This is a model prediction, not an official IMD forecast or warning."/><div className="mb-5 flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950"><ShieldAlert size={19} className="mt-0.5 shrink-0"/><p><strong>WeatherGPT Model Prediction.</strong> This is not an official IMD warning or forecast. Use official sources for safety decisions.</p></div><form onSubmit={predict} className="grid gap-4 rounded-2xl border border-line bg-white p-5 shadow-card sm:grid-cols-3"><label className="text-sm font-medium">Latitude<input required type="number" min="-90" max="90" step="any" value={latitude} onChange={(event) => setLatitude(event.target.value)} className="mt-2 block min-h-11 w-full rounded-xl border border-line bg-white px-3"/></label><label className="text-sm font-medium">Longitude<input required type="number" min="-180" max="180" step="any" value={longitude} onChange={(event) => setLongitude(event.target.value)} className="mt-2 block min-h-11 w-full rounded-xl border border-line bg-white px-3"/></label><div className="flex items-end"><button type="submit" disabled={loading} className="min-h-11 w-full rounded-xl bg-brand px-4 font-semibold text-white disabled:opacity-60">{loading ? 'Requesting prediction…' : 'Get 1-day prediction'}</button></div></form>{loading && <p role="status" className="mt-5 text-sm text-muted">Requesting the WeatherGPT model prediction.</p>}{error && <div role="alert" className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><strong>Prediction unavailable.</strong> {error}</div>}{result && <section className="mt-6 rounded-2xl border border-line bg-white p-5 shadow-card" aria-label="WeatherGPT model prediction result"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">{result.label}</h2><span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-brand">1-day horizon</span></div><p className="mt-2 text-sm text-muted">Requested {result.location.latitude.toFixed(2)}, {result.location.longitude.toFixed(2)} · selected grid {result.selected_grid_point.latitude.toFixed(2)}, {result.selected_grid_point.longitude.toFixed(2)} ({result.selected_grid_point.distance_km.toFixed(1)} km)</p><div className="mt-5 grid gap-3 sm:grid-cols-3"><Metric label="Rain probability" value={`${(result.rain_probability * 100).toFixed(1)}%`}/><Metric label="Predicted rainfall" value={`${result.predicted_rainfall_mm.toFixed(1)} mm`}/><Metric label="Rain expected" value={result.rain_expected ? 'Yes' : 'No'}/></div><p className="mt-4 text-xs text-muted">Prediction date: {result.prediction_date} · Model: {result.model} · Training period: {result.training_period.start} to {result.training_period.end}</p></section>}</main>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-lg font-semibold text-ink">{value}</p></div>; }
