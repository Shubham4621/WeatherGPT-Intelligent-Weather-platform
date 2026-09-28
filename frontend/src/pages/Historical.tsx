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
  const temperatureSeries = data?.metadata?.validation_status === 'PASS'
    ? (data.records ?? []).filter((row) => typeof row.temperature_mean === 'number') as Array<Record<string, number | string>>
    : [];
  const rainfallSeries = (data?.records ?? []).filter((row) => typeof row.rainfall === 'number') as Array<Record<string, number | string>>;
  const hasTemperatureObservations = data?.metadata?.validation_status === 'PASS' && (data.records ?? []).some((row) => typeof row.temperature_min === 'number' || typeof row.temperature_max === 'number' || typeof row.temperature_mean === 'number');
  async function search(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError(''); setData(null);
    try { setData(await getHistoricalWeather(city, start, end)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Historical data unavailable'); }
    finally { setLoading(false); }
  }
  return <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
    <div className="mb-6"><p className="text-sm font-semibold uppercase tracking-wide text-brand">{t(language, 'Historical')}</p><h1 className="mt-2 text-3xl font-bold">{t(language, 'Historical Weather')}</h1><p className="mt-2 text-muted">{t(language, 'Explore observed weather records. Historical data is separate from current conditions and forecasts.')}</p></div>
    <form onSubmit={search} className="grid gap-4 rounded-2xl border border-line bg-white p-5 shadow-card sm:grid-cols-4">
      <label className="text-sm font-medium">{t(language, 'Location')}<input required value={city} onChange={e => setCity(e.target.value)} className="mt-1 w-full rounded-lg border border-line px-3 py-2" placeholder="Dhule" /></label>
      <label className="text-sm font-medium">{t(language, 'Start date')}<input required type="date" value={start} onChange={e => setStart(e.target.value)} className="mt-1 w-full rounded-lg border border-line px-3 py-2" /></label>
      <label className="text-sm font-medium">{t(language, 'End date')}<input required type="date" value={end} onChange={e => setEnd(e.target.value)} className="mt-1 w-full rounded-lg border border-line px-3 py-2" /></label>
      <button disabled={loading} className="self-end rounded-lg bg-brand px-4 py-2 font-semibold text-white disabled:opacity-60">{loading ? t(language, 'Loading') : t(language, 'Search')}</button>
    </form>
    <section aria-live="polite" className="mt-6 rounded-2xl border border-line bg-white p-5 shadow-card sm:p-6">
      {loading && <p>{t(language, 'Loading historical weatherâ€¦')}</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {!loading && !error && data?.status === 'unavailable' && <><h2 className="text-lg font-semibold">{t(language, 'Historical data unavailable')}</h2><p className="mt-2 text-muted">{data.reason}</p></>}
      {!loading && !error && data?.status === 'data_not_available' && <><h2 className="text-lg font-semibold">{t(language, 'IMD historical data is not installed')}</h2><p className="mt-2 text-muted">{data.reason}</p><dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2"><div><dt className="font-medium">{t(language, 'Source')}</dt><dd className="text-muted">{data.source}</dd></div><div><dt className="font-medium">{t(language, 'Dataset status')}</dt><dd className="text-muted">{data.availability_status}</dd></div><div><dt className="font-medium">{t(language, 'Data period')}</dt><dd className="text-muted">{data.metadata?.period ?? '1901â€“2024 rainfall; 1951â€“2024 temperature'}</dd></div><div><dt className="font-medium">{t(language, 'Resolution')}</dt><dd className="text-muted">{data.metadata?.resolution ?? '0.25Â° rainfall; 1Â° temperature'}</dd></div></dl></>}
      {!loading && !error && data?.status === 'no_data' && <p>{t(language, 'No historical data available for the requested period.')}</p>}
      {(data?.status === 'available' || data?.status === 'partial') && <><div className="flex flex-wrap items-center gap-2"><span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-emerald-900">Historical observation</span><h2 className="text-lg font-semibold">{data.location} Â· {data.period_start} â€“ {data.period_end}</h2></div><p className="mt-2 text-sm text-muted">{t(language, 'Source')}: {data.source} Â· {t(language, 'Retrieved at')}: {data.retrieved_at}</p>{data.metadata && <div className="mt-3 grid gap-2 rounded-xl border border-line bg-slate-50 p-4 text-xs sm:grid-cols-2 lg:grid-cols-4"><p><strong>{t(language, 'Dataset')}:</strong> {data.metadata.dataset ?? 'â€”'}</p><p><strong>{t(language, 'Resolution')}:</strong> {data.metadata.grid_resolution ?? 'â€”'}Â°</p><p><strong>{t(language, 'Validation')}:</strong> {data.metadata.validation_status ?? 'â€”'}</p><p><strong>{t(language, 'Missing observations')}:</strong> Rain {data.metadata.missing_rainfall ?? 'â€”'}, Tmax {data.metadata.missing_tmax ?? 'â€”'}, Tmin {data.metadata.missing_tmin ?? 'â€”'}</p><p><strong>Grid:</strong> {data.metadata.latitude ?? 'â€”'}, {data.metadata.longitude ?? 'â€”'}</p><p><strong>Availability:</strong> {data.availability_status ?? data.status}</p></div>}{data.status === 'partial' && <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{t(language, 'Historical data is incomplete for the requested period.')}</p>}<h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted">Validated period summary</h3><dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(data.summary ?? {}).filter(([key, value]) => ['average_temperature','temperature_min','temperature_max','total_rainfall','rainy_days','average_humidity','average_wind_speed'].includes(key) && value !== null && (!key.includes('temperature') || data.metadata?.validation_status === 'PASS')).map(([key,value])=><div key={key} className="rounded-xl border border-line bg-white p-4"><dt className="text-xs text-muted">{t(language, key.replace(/_/g,' '))}</dt><dd className="mt-1 text-xl font-semibold">{value}<span className="ml-1 text-xs font-medium text-muted">{key.includes('temperature') ? 'Â°C' : key === 'total_rainfall' ? 'mm' : key === 'average_humidity' ? '%' : key === 'average_wind_speed' ? 'm/s' : ''}</span></dd></div>)}</dl>
        {!hasTemperatureObservations && <div className="mt-5 rounded-xl border border-dashed border-line bg-slate-50 p-4"><p className="text-sm font-semibold">Temperature observations unavailable</p><p className="mt-1 text-sm text-muted">No validated Tmax/Tmin observations are present in the returned records. Temperature trends are not plotted.</p></div>}
        {temperatureSeries.length > 1 && <div className="mt-8"><h3 className="font-semibold">{t(language, 'Temperature trend (Â°C)')}</h3><p className="mt-1 text-xs text-muted">{data.period_start} â€“ {data.period_end} Â· {data.location} Â· Source: {data.source}</p><div className="mt-3 overflow-x-auto"><svg role="img" aria-label={t(language, 'Temperature trend (Â°C)')} viewBox="0 0 600 180" className="h-44 min-w-[500px] w-full" preserveAspectRatio="none"><polyline fill="none" stroke="currentColor" strokeWidth="3" className="text-brand" points={temperatureSeries.map((row,index) => `${index*600/(temperatureSeries.length-1)},${170-Number(row.temperature_mean)*3}`).join(' ')} />{temperatureSeries.map((row,index)=><circle key={String(row.date)} cx={index*600/(temperatureSeries.length-1)} cy={170-Number(row.temperature_mean)*3} r="4" className="fill-brand" />)}</svg></div></div>}
        {rainfallSeries.length > 0 && <div className="mt-8"><h3 className="font-semibold">{t(language, 'Rainfall (mm)')}</h3><p className="mt-1 text-xs text-muted">{data.period_start} â€“ {data.period_end} Â· {data.location} Â· Source: {data.source}</p><div className="mt-3 overflow-x-auto"><div role="img" aria-label={t(language, 'Rainfall (mm)')} className="flex h-40 min-w-[500px] items-end gap-1 border-b border-line">{rainfallSeries.map((row)=><div key={String(row.date)} title={`${row.date}: ${row.rainfall} mm`} className="flex-1 rounded-t bg-sky-500" style={{height:`${Math.max(2, Number(row.rainfall) / Math.max(1,...rainfallSeries.map(item=>Number(item.rainfall))) * 100)}%`}} />)}</div></div></div>}
      </>}
      {!data && !loading && !error && <p className="text-muted">{t(language, 'Choose a location and date range to view historical observations.')}</p>}
    </section>
  </main>;
}
