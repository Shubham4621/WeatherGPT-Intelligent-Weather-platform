import { useState } from 'react';
import { AlertTriangle, RefreshCw, ShieldCheck } from 'lucide-react';
import { getWeatherAlerts } from '../services/weatherApi';
import type { WeatherAlertsResponse } from '../types/weather';
import { localeFor, t, useLanguage, warningLabel } from '../i18n';

const meaning: Record<string, string> = { Green: 'No Warning', Yellow: 'Watch', Orange: 'Alert', Red: 'Warning' };

export function AlertCard({ day, district }: { day: WeatherAlertsResponse['forecast_days'][number]; district: string }) {
  const { language } = useLanguage();
  return <article className={`rounded-2xl border bg-white p-5 shadow-card ${day.is_active ? 'border-amber-200' : 'border-line'}`}>
    <p className="text-sm font-semibold text-muted">{new Date(day.date).toLocaleDateString(localeFor(language), { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' })}</p>
    {day.is_active ? <div className="mt-3 flex gap-3"><AlertTriangle className="mt-1 shrink-0 text-amber-600"/><div><h2 className="font-semibold text-ink">{day.warnings.map((warning) => warningLabel(language, warning.warning_code, warning.warning_type)).join(', ')}</h2><p className="mt-1 text-sm text-muted">{district}</p><p className="mt-3 text-sm font-medium">{t(language, 'IMD Level')}: {day.severity ?? 'Not specified'}</p>{day.severity && <p className="mt-1 text-xs text-muted">{t(language, 'Meaning')}: {t(language, meaning[day.severity] ?? 'IMD color level')}</p>}<p className="mt-2 text-xs text-muted">Official warning from IMD · Codes {day.warnings.map((warning) => warning.warning_code).join(', ')}</p></div></div> : <div className="mt-3 flex items-center gap-2 text-sm text-muted"><ShieldCheck size={18}/><span>{t(language, 'No official warning reported for this day')}</span></div>}
  </article>;
}

export default function Alerts({ initialCity = 'Dhule' }: { initialCity?: string }) {
  const { language } = useLanguage();
  const [city, setCity] = useState(initialCity); const [data, setData] = useState<WeatherAlertsResponse | null>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null);
  async function search() { setLoading(true); setError(null); setData(null); try { setData(await getWeatherAlerts(city)); } catch (e) { setError(t(language, 'Unable to retrieve official weather warnings. Please try again later.')); } finally { setLoading(false); } }
  return <main id="main" className="mx-auto max-w-7xl px-5 py-10 sm:px-8"><p className="text-xs font-semibold uppercase tracking-wider text-brand">{t(language, 'Official warning intelligence')}</p><h1 className="mt-3 text-3xl font-semibold">{t(language, 'Weather Alerts')}</h1><p className="mt-2 text-sm text-muted">{t(language, 'District warnings published by the India Meteorological Department.')}</p><form className="mt-6 flex max-w-lg gap-3" onSubmit={(event) => { event.preventDefault(); void search(); }}><input aria-label={t(language, 'Search city for alerts')} value={city} onChange={(event) => setCity(event.target.value)} className="min-w-0 flex-1 rounded-xl border border-line bg-white px-4 py-3"/><button type="submit" disabled={loading || !city.trim()} className="rounded-xl bg-brand px-5 py-3 font-medium text-white">{loading ? t(language, 'Loading') : t(language, 'Search')}</button></form>
    <section className="mt-7 rounded-2xl border border-blue-100 bg-blue-50/70 p-5"><p className="font-semibold text-ink">Official Source</p><p className="mt-1 text-sm text-muted">India Meteorological Department (IMD)</p>{data && <p className="mt-2 text-xs text-muted">District: {data.district}, {data.state} · Issued {new Date(data.issued_at).toLocaleString()}</p>}</section>
    {loading && <p role="status" className="mt-6 text-sm text-muted">{t(language, 'Loading alerts…')}</p>}{error && <div role="alert" className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}<button type="button" onClick={() => void search()} className="ml-3 inline-flex items-center gap-1 font-semibold"><RefreshCw size={14}/>{t(language, 'Retry')}</button></div>}
    {data && <><div className="mt-5 flex items-center justify-between text-xs text-muted"><span>Official warning source: <a className="underline" href={data.source_url} target="_blank" rel="noreferrer">{data.source}</a></span><span>Retrieved {new Date(data.issued_at).toLocaleString()}</span></div>{!data.forecast_days.some((day) => day.is_active) && <p className="mt-5 rounded-xl bg-slate-100 p-4 text-sm text-muted">No official IMD weather warning is currently reported for {data.district} for the requested period. This does not mean there is zero weather risk.</p>}<section aria-label="Official IMD warning days" className="mt-5 grid gap-4 md:grid-cols-2">{data.forecast_days.map((day) => <AlertCard key={day.date} day={day} district={data.district}/>)}</section></>}
  </main>;
}
