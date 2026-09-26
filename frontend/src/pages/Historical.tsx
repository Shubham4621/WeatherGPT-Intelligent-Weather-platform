import { useState } from 'react';
import { useLanguage, t } from '../i18n';
import { getHistoricalWeather, type HistoricalResponse } from '../services/weatherApi';

export default function Historical() {
  const { language } = useLanguage();
  const [city, setCity] = useState('Dhule');
  const [start, setStart] = useState('2025-07-01');
  const [end, setEnd] = useState('2025-07-31');
  const [data, setData] = useState<HistoricalResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const temperatureSeries = (data?.records ?? []).filter((row) => typeof row.temperature_mean === 'number') as Array<Record<string, number | string>>;
  const rainfallSeries = (data?.records ?? []).filter((row) => typeof row.rainfall === 'number') as Array<Record<string, number | string>>;
  async function search(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError(''); setData(null);
    try { setData(await getHistoricalWeather(city, start, end)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Historical data unavailable'); }
    finally { setLoading(false); }
  }
  return <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
    <div className="mb-6"><p className="text-sm font-semibold uppercase tracking-wide text-brand">{t(language, 'Historical')}</p><h1 className="mt-2 text-3xl font-bold">{t(language, 'Historical Weather')}</h1><p className="mt-2 text-muted">{t(language, 'Explore observed weather records. Historical data is separate from current conditions and forecasts.')}</p></div>
    <form onSubmit={search} className="grid gap-4 rounded-2xl border border-line bg-white p-5 shadow-sm sm:grid-cols-4">
      <label className="text-sm font-medium">{t(language, 'Location')}<input required value={city} onChange={e => setCity(e.target.value)} className="mt-1 w-full rounded-lg border border-line px-3 py-2" placeholder="Dhule" /></label>
      <label className="text-sm font-medium">{t(language, 'Start date')}<input required type="date" value={start} onChange={e => setStart(e.target.value)} className="mt-1 w-full rounded-lg border border-line px-3 py-2" /></label>
      <label className="text-sm font-medium">{t(language, 'End date')}<input required type="date" value={end} onChange={e => setEnd(e.target.value)} className="mt-1 w-full rounded-lg border border-line px-3 py-2" /></label>
      <button disabled={loading} className="self-end rounded-lg bg-brand px-4 py-2 font-semibold text-white disabled:opacity-60">{loading ? t(language, 'Loading') : t(language, 'Search')}</button>
    </form>
    <section aria-live="polite" className="mt-6 rounded-2xl border border-line bg-white p-6 shadow-sm">
      {loading && <p>{t(language, 'Loading historical weather…')}</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {!loading && !error && data?.status === 'unavailable' && <><h2 className="text-lg font-semibold">{t(language, 'Historical data unavailable')}</h2><p className="mt-2 text-muted">{data.reason}</p></>}
      {!loading && !error && data?.status === 'no_data' && <p>{t(language, 'No historical data available for the requested period.')}</p>}
      {(data?.status === 'available' || data?.status === 'partial') && <><h2 className="text-lg font-semibold">{data.location} · {data.period_start} – {data.period_end}</h2><p className="mt-1 text-sm text-muted">{t(language, 'Source')}: {data.source} · {t(language, 'Retrieved at')}: {data.retrieved_at}</p>{data.status === 'partial' && <p className="mt-2 text-amber-800">{t(language, 'Historical data is incomplete for the requested period.')}</p>}<dl className="mt-5 grid gap-3 sm:grid-cols-3">{Object.entries(data.summary ?? {}).filter(([key, value]) => ['average_temperature','temperature_min','temperature_max','total_rainfall','rainy_days','average_humidity','average_wind_speed'].includes(key) && value !== null).map(([key,value])=><div key={key} className="rounded-xl bg-slate-50 p-4"><dt className="text-sm text-muted">{t(language, key.replace(/_/g,' '))}</dt><dd className="mt-1 text-xl font-semibold">{value}</dd></div>)}</dl>
        {temperatureSeries.length > 1 && <div className="mt-8"><h3 className="font-semibold">{t(language, 'Temperature trend (°C)')}</h3><svg role="img" aria-label={t(language, 'Temperature trend (°C)')} viewBox="0 0 600 180" className="mt-3 h-44 w-full" preserveAspectRatio="none"><polyline fill="none" stroke="currentColor" strokeWidth="3" className="text-brand" points={temperatureSeries.map((row,index) => `${index*600/(temperatureSeries.length-1)},${170-Number(row.temperature_mean)*3}`).join(' ')} />{temperatureSeries.map((row,index)=><circle key={String(row.date)} cx={index*600/(temperatureSeries.length-1)} cy={170-Number(row.temperature_mean)*3} r="4" className="fill-brand" />)}</svg></div>}
        {rainfallSeries.length > 0 && <div className="mt-8"><h3 className="font-semibold">{t(language, 'Rainfall (mm)')}</h3><div role="img" aria-label={t(language, 'Rainfall (mm)')} className="mt-3 flex h-40 items-end gap-1 border-b border-line">{rainfallSeries.map((row)=><div key={String(row.date)} title={`${row.date}: ${row.rainfall} mm`} className="flex-1 rounded-t bg-sky-500" style={{height:`${Math.max(2, Number(row.rainfall) / Math.max(1,...rainfallSeries.map(item=>Number(item.rainfall))) * 100)}%`}} />)}</div></div>}
      </>}
      {!data && !loading && !error && <p className="text-muted">{t(language, 'Choose a location and date range to view historical observations.')}</p>}
    </section>
  </main>;
}
