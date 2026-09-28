import { useState } from 'react';
import { AlertTriangle, CheckCircle2, CloudSun } from 'lucide-react';
import { getWeatherAdvisory, WeatherApiError } from '../services/weatherApi';
import type { AdvisoryActivity, WeatherAdvisory } from '../types/weather';
import { localeFor, t, useLanguage } from '../i18n';

const activities: { value: AdvisoryActivity; label: string }[] = [
  { value: 'GENERAL_PRECAUTION', label: 'General' }, { value: 'TRAVEL', label: 'Travel' },
  { value: 'COMMUTE', label: 'Commute' }, { value: 'OUTDOOR_ACTIVITY', label: 'Outdoor activity' },
  { value: 'EXERCISE', label: 'Exercise' }, { value: 'EVENT', label: 'Event' }, { value: 'AGRICULTURE', label: 'Agriculture' },
];

export function AdvisoryResult({ data, agricultureMode = false }: { data: WeatherAdvisory; agricultureMode?: boolean }) {
  const { language } = useLanguage();
  const rainfallFactors = data.factors.filter((factor) => factor.code === 'PRECIPITATION_CHANCE' || factor.code === 'RAIN_CONDITION');
  const temperatureFactors = data.factors.filter((factor) => factor.code === 'TEMPERATURE');
  return <section aria-label="WeatherGPT advisory result" className="mt-7 space-y-5">
    {agricultureMode && <section aria-label="Agriculture weather summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <InfoCard title="Weather summary" value={data.summary}/>
      <InfoCard title="Rainfall" value={rainfallFactors.map((factor) => factor.detail).join(' · ') || 'No rainfall detail in this advisory response.'}/>
      <InfoCard title="Temperature" value={temperatureFactors.map((factor) => factor.detail).join(' · ') || 'No temperature detail in this advisory response.'}/>
      <InfoCard title="Crop risk" value={data.risk_level ? `${data.risk_label}: ${data.risk_level}` : 'Not assessed by this service.'}/>
      <InfoCard title="Irrigation guidance" value="Not provided by the current advisory service."/>
      <InfoCard title="Sowing guidance" value="Not provided by the current advisory service."/>
      <InfoCard title="7-day rainfall" value="Unavailable: this advisory request covers one selected day, not a 7-day rainfall series."/>
    </section>}
    <article className="rounded-3xl border border-line bg-white p-6 shadow-card"><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand"><CloudSun size={15}/> WeatherGPT {t(language, 'Advisory')}</p><h2 className="mt-3 text-xl font-semibold">{data.location} · {data.activity.replace(/_/g, ' ').toLowerCase()}</h2><p className="mt-1 text-sm text-muted">{data.date ? new Date(data.date).toLocaleDateString(localeFor(language), { dateStyle: 'long', timeZone: 'UTC' }) : 'Requested date'}</p><p className="mt-4 leading-7">{data.summary}</p><p className="mt-4 inline-flex rounded-full bg-blue-50 px-3 py-1.5 text-xs font-semibold text-brand">{data.risk_label}: {data.risk_level ?? 'NOT ASSESSED'}</p></article>
    {data.official_warning && <article className="rounded-2xl border-2 border-amber-400 bg-amber-50 p-5"><p className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-900"><AlertTriangle size={16}/> Official IMD Information</p><h3 className="mt-3 font-semibold">{data.official_warning.warnings.join(', ')}</h3><p className="mt-1 text-sm">IMD Level: {data.official_warning.severity ?? 'Not specified'}</p><a className="mt-2 inline-block text-xs underline" href={data.official_warning.source_url} target="_blank" rel="noreferrer">{data.official_warning.source}</a></article>}
    {data.official_warning_status === 'unavailable' && <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">Official IMD warning information could not be retrieved. This is not confirmation that no warning exists.</p>}
    {data.official_warning_status === 'none_reported' && <p className="rounded-xl bg-slate-100 p-4 text-sm">No official IMD warning was reported for this date; this does not mean there is zero weather risk.</p>}
    <div className="grid gap-5 md:grid-cols-2"><article className="rounded-2xl border border-line bg-white p-5"><h3 className="font-semibold">{t(language, 'Factors')}</h3>{data.factors.length ? <ul className="mt-3 space-y-2">{data.factors.map((factor, i) => <li key={`${factor.code}-${i}`} className="text-sm"><span>{factor.detail}</span><span className="ml-2 text-xs text-muted">· {factor.source}</span></li>)}</ul> : <p className="mt-3 text-sm text-muted">No elevated weather factors identified from the available data.</p>}</article><article className="rounded-2xl border border-line bg-white p-5"><h3 className="font-semibold">{t(language, 'Recommendations')}</h3><ul className="mt-3 space-y-2">{data.recommendations.map((recommendation) => <li key={recommendation} className="flex gap-2 text-sm"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-brand"/>{recommendation}</li>)}</ul></article></div>
    <p className="text-xs text-muted">Weather data and warning status are listed separately. Interpretation: WeatherGPT. Sources: {data.sources.join(', ')}</p>
  </section>;
}

export default function Advisory({ initialActivity = 'GENERAL_PRECAUTION', agricultureMode = false }: { initialActivity?: AdvisoryActivity; agricultureMode?: boolean } = {}) {
  const { language } = useLanguage();
  const [city, setCity] = useState('Dhule'); const [dayOffset, setDayOffset] = useState(1); const [activity, setActivity] = useState<AdvisoryActivity>(initialActivity); const [data, setData] = useState<WeatherAdvisory | null>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null);
  async function generate() { setLoading(true); setError(null); setData(null); try { setData(await getWeatherAdvisory(city, dayOffset, activity)); } catch (e) { setError(e instanceof WeatherApiError ? e.message : 'Unable to generate an advisory.'); } finally { setLoading(false); } }
  return <main id="main" className="mx-auto max-w-5xl px-5 py-10 sm:px-8"><p className="text-xs font-semibold uppercase tracking-wider text-brand">{agricultureMode ? t(language, 'Farm weather guidance') : t(language, 'Decision support')}</p><h1 className="mt-3 text-3xl font-semibold">{agricultureMode ? t(language, 'Agriculture Advisory') : t(language, 'Weather Advisory')}</h1><p className="mt-2 text-sm text-muted">{agricultureMode ? t(language, 'Weather-based recommendations for the selected date, using the existing advisory service. Crop-specific forecasts and pest predictions are not provided.') : t(language, 'Practical suggestions based on available forecast data and official IMD warnings. Risk levels below are WeatherGPT classifications, not official warning levels.')}</p><form className="mt-7 grid gap-4 rounded-3xl border border-line bg-white p-5 shadow-card sm:grid-cols-3" onSubmit={(event) => { event.preventDefault(); void generate(); }}><label className="text-sm font-medium">{t(language, 'Location')}<input aria-label={t(language, 'Location')} value={city} onChange={(event) => setCity(event.target.value)} className="mt-2 block w-full rounded-xl border border-line px-3 py-3"/></label><label className="text-sm font-medium">{t(language, 'Date')}<select aria-label={t(language, 'Date')} value={dayOffset} onChange={(event) => setDayOffset(Number(event.target.value))} className="mt-2 block w-full rounded-xl border border-line px-3 py-3"><option value={0}>{t(language, 'Today')}</option><option value={1}>{t(language, 'Tomorrow')}</option><option value={2}>{t(language, 'Day after tomorrow')}</option></select></label><label className="text-sm font-medium">{t(language, 'Activity')}<select aria-label={t(language, 'Activity')} value={activity} onChange={(event) => setActivity(event.target.value as AdvisoryActivity)} className="mt-2 block w-full rounded-xl border border-line px-3 py-3">{activities.map((item) => <option key={item.value} value={item.value}>{t(language, item.label)}</option>)}</select></label><button disabled={loading || !city.trim()} className="min-h-11 rounded-xl bg-brand px-5 py-3 font-semibold text-white sm:col-span-3">{loading ? t(language, 'Loading') : t(language, 'Get Advisory')}</button></form>{loading && <p role="status" className="mt-5 text-sm text-muted">{t(language, 'Generating advisory from available weather sources…')}</p>}{error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}{data && <AdvisoryResult data={data} agricultureMode={agricultureMode}/>}</main>;
}

function InfoCard({ title, value }: { title: string; value: string }) {
  const { language } = useLanguage();
  return <article className="rounded-2xl border border-line bg-white p-4 shadow-sm"><h2 className="text-xs font-semibold uppercase tracking-wide text-muted">{t(language, title)}</h2><p className="mt-2 text-sm leading-6 text-ink">{t(language, value)}</p></article>;
}
