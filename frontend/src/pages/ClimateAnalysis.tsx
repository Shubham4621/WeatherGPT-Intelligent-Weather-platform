import { useState } from 'react';
import { getClimatology, getHistoricalWeather, resolveLocation, WeatherApiError, type HistoricalResponse, type ResolvedLocation } from '../services/weatherApi';
import { t, useLanguage } from '../i18n';

const monthNumbers = Array.from({ length: 12 }, (_, index) => index + 1);
type Normal = Record<string, unknown>;
type ClimateResult = { location: ResolvedLocation | { query: string; latitude: number; longitude: number }; history: HistoricalResponse; normals: Array<{ month: number; response: Awaited<ReturnType<typeof getClimatology>> }> };
const value = (input: unknown, fallback = '—') => input === null || input === undefined || input === '' ? fallback : String(input);
const num = (input: unknown) => typeof input === 'number' && Number.isFinite(input) ? input : null;

export default function ClimateAnalysis() {
  const { language } = useLanguage();
  const [city, setCity] = useState('Dhule');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [start, setStart] = useState('2013-01-01');
  const [end, setEnd] = useState('2024-12-31');
  const [compareYear, setCompareYear] = useState('');
  const [result, setResult] = useState<ClimateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true); setError(null); setResult(null);
    try {
      const hasLat = latitude.trim() !== '', hasLon = longitude.trim() !== '';
      if (hasLat !== hasLon) throw new WeatherApiError(t(language, 'Enter both latitude and longitude.'));
      if (!city.trim() && !hasLat) throw new WeatherApiError(t(language, 'Enter a city or both coordinates.'));
      if (start > end) throw new WeatherApiError(t(language, 'Start date must be on or before end date.'));
      if (compareYear.trim() && (!Number.isInteger(Number(compareYear)) || Number(compareYear) < 1901 || Number(compareYear) > 2099)) throw new WeatherApiError(t(language, 'Compare year must be from 1901 through 2099.'));
      let resolved: ResolvedLocation | { query: string; latitude: number; longitude: number };
      if (hasLat && hasLon) {
        const lat = Number(latitude), lon = Number(longitude);
        if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) throw new WeatherApiError(t(language, 'Coordinates must be within latitude −90 to 90 and longitude −180 to 180.'));
        resolved = { query: `${lat}, ${lon}`, latitude: lat, longitude: lon };
      } else {
        resolved = await resolveLocation(city.trim());
      }
      const history = await getHistoricalWeather(hasLat ? '' : city.trim(), start, end, resolved.latitude, resolved.longitude, compareYear.trim() ? Number(compareYear) : undefined);
      const normals = await Promise.all(monthNumbers.map(async month => ({ month, response: await getClimatology(month, resolved.latitude, resolved.longitude) })));
      setResult({ location: resolved, history, normals });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t(language, 'Climate service error'));
    } finally { setLoading(false); }
  }

  const history = result?.history;
  const meta = history?.metadata ?? {};
  const summary = history?.summary ?? {};
  const trend = history?.analysis?.trends?.rainfall_mm_per_year;
  const monthly = history?.monthly ?? [];
  const annual = history?.yearly ?? [];
  const anomalies = (history?.analysis?.comparisons ?? []).filter(row => typeof row.year === 'number');
  const yearComparison = (history?.analysis?.comparisons ?? []).find(row => row.kind === 'year_over_year');
  const hasHistory = history?.status === 'available' || history?.status === 'partial';
  const insufficientHistory = history?.status === 'insufficient_data' || history?.status === 'partial';
const normalFor = (entry: { month: number; response: Awaited<ReturnType<typeof getClimatology>> } | undefined, variable: string): Normal | undefined => entry?.response.normals.find(item => item.variable === variable);
  const climateSources = result ? [...new Set(result.normals.flatMap(entry => entry.response.normals.map(normal => normal.source).filter(source => typeof source === 'string'))) ] : [];
  const resolvedLabel = result?.location && 'city' in result.location ? [result.location.city, result.location.state, result.location.country].filter(Boolean).join(', ') : result?.location.query;

  return <main id="main" className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
    <header className="mb-7"><p className="text-xs font-semibold uppercase tracking-[.16em] text-brand">{t(language, 'Long-term climate context')}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">{t(language, 'Climate Analysis')}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{t(language, 'Use a city or coordinates to review validated historical rainfall and IMD monthly normals.')}</p></header>
    <form onSubmit={submit} className="grid gap-3 rounded-2xl border border-line bg-white p-4 shadow-card sm:grid-cols-2 lg:grid-cols-6">
      <label className="text-xs font-medium text-muted lg:col-span-2">{t(language, 'City or location')}<input value={city} onChange={event => setCity(event.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" placeholder="Dhule" /></label>
      <label className="text-xs font-medium text-muted">{t(language, 'Latitude')}<input type="number" min="-90" max="90" step="any" value={latitude} onChange={event => setLatitude(event.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" placeholder="20.90" /></label>
      <label className="text-xs font-medium text-muted">{t(language, 'Longitude')}<input type="number" min="-180" max="180" step="any" value={longitude} onChange={event => setLongitude(event.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" placeholder="74.80" /></label>
      <label className="text-xs font-medium text-muted">{t(language, 'Start date')}<input required type="date" value={start} onChange={event => setStart(event.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" /></label>
      <label className="text-xs font-medium text-muted">{t(language, 'End date')}<input required type="date" value={end} onChange={event => setEnd(event.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" /></label>
      <label className="text-xs font-medium text-muted">{t(language, 'Compare year with next year')}<input type="number" min="1901" max="2099" step="1" value={compareYear} onChange={event => setCompareYear(event.target.value)} className="mt-1 min-h-11 w-full rounded-xl border border-line px-3 text-sm text-ink" placeholder="2023" /></label>
      <button disabled={loading} className="min-h-11 rounded-xl bg-brand px-5 text-sm font-semibold text-white disabled:opacity-60 sm:col-span-2 lg:col-span-6">{loading ? t(language, 'Resolving location and loading climate data…') : t(language, 'Load climate analysis')}</button>
    </form>

    {loading && <p role="status" className="mt-5 rounded-xl border border-line bg-white p-4 text-sm text-muted">{t(language, 'Resolving location and loading climate data…')}</p>}
    {error && <section role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><h2 className="font-semibold">{t(language, 'Climate service error')}</h2><p className="mt-1">{error}</p></section>}
    {!result && !loading && !error && <p className="mt-5 text-sm text-muted">{t(language, 'Choose a location and date range to view historical observations.')}</p>}

    {result && <div className="mt-6 space-y-5">
      <section className="rounded-2xl border border-line bg-white p-5 shadow-card">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><h2 className="text-lg font-semibold text-ink">{resolvedLabel}</h2><p className="mt-1 text-sm text-muted">{t(language, 'Requested period')}: {start} – {end}</p></div><span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-900">{t(language, 'IMD monthly climatology')} · 1991–2020</span></div>
        <p className="mt-3 text-xs text-muted">{t(language, 'Requested coordinates')}: {result.location.latitude}, {result.location.longitude}</p>
      </section>

      <section className="rounded-2xl border border-line bg-white p-5 shadow-card">
        <h2 className="text-lg font-semibold">{t(language, 'Historical observations')} <span className="ml-2 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold uppercase text-emerald-900">{t(language, 'Observation').toUpperCase()}</span></h2>
        {!hasHistory && <div role="status" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><h3 className="font-semibold">{history?.status === 'insufficient_data' ? t(language, 'Insufficient climate data') : t(language, 'Climate data unavailable')}</h3><p className="mt-1">{history?.reason || t(language, 'No data covers this location or period. No other grid cell was substituted.')}</p></div>}
        {hasHistory && <>
          <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[
            [t(language, 'Returned observations'), value(summary.record_count)], [t(language, 'Rainfall observations'), value(summary.rainfall_observations)], [t(language, 'Missing rainfall observations'), value(meta.missing_rainfall)], [t(language, 'Data coverage'), `${value(history.period_start)} – ${value(history.period_end)}`],
            [t(language, 'Dataset'), value(meta.dataset)], [t(language, 'Native grid resolution'), `${value(meta.grid_resolution)}°`], [t(language, 'Selected grid point'), `${value(meta.latitude)}, ${value(meta.longitude)}`], [t(language, 'Distance from requested location'), meta.distance_km == null ? '—' : `${meta.distance_km} km`],
          ].map(([label, data]) => <div key={label} className="rounded-xl border border-line bg-slate-50 p-3"><dt className="text-xs text-muted">{label}</dt><dd className="mt-1 break-words text-sm font-semibold text-ink">{data}</dd></div>)}</dl>
          {insufficientHistory && <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">{t(language, 'Partial coverage')}</p>}
        <p className="mt-3 text-xs text-muted">{t(language, 'Source')}: {value(history.source)} · {t(language, 'Dataset')}: {value(meta.dataset)} · {t(language, 'WeatherGPT analysis summarizes observations; this is not a forecast.')}</p>
        {yearComparison && <p role="status" className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">{t(language, 'Year-over-year rainfall difference')}: {value(yearComparison.first_year)} → {value(yearComparison.second_year)} · {yearComparison.status === 'available' ? `${value(yearComparison.rainfall_difference_mm)} mm` : t(language, 'Insufficient data')}</p>}
          {num(summary.temperature_observations) === 0 && <div className="mt-4 rounded-xl border border-dashed border-line bg-slate-50 p-4"><p className="font-semibold">{t(language, 'Temperature observations')}: 0</p><p className="mt-1 text-sm text-muted">{t(language, 'Historical daily temperature analysis is currently unavailable because validated daily Tmax/Tmin observations are not yet available for this location and period.')}</p></div>}
          {!!monthly.length && <div className="mt-6"><h3 className="font-semibold">{t(language, 'Monthly rainfall analysis')}</h3><div className="mt-2 overflow-x-auto"><table className="w-full min-w-[540px] text-left text-sm"><thead className="bg-slate-50 text-xs text-muted"><tr><th className="p-2">{t(language, 'Year')}</th><th className="p-2">{t(language, 'Month')}</th><th className="p-2">{t(language, 'Rainfall total')} (mm)</th><th className="p-2">{t(language, 'Observation days')}</th><th className="p-2">{t(language, 'Expected days')}</th></tr></thead><tbody>{monthly.map(row => <tr className="border-t border-line" key={`${row.year}-${row.month_number}`}><td className="p-2">{value(row.year)}</td><td className="p-2">{value(row.month_number)}</td><td className="p-2">{value(row.total_rainfall)}</td><td className="p-2">{value(row.rainfall_observation_count)}</td><td className="p-2">{value(row.expected_day_count)}</td></tr>)}</tbody></table></div></div>}
          {!!annual.length && <div className="mt-6"><h3 className="font-semibold">{t(language, 'Annual rainfall analysis')} · {t(language, 'Available year range')}: {value(annual[0]?.year)} – {value(annual[annual.length - 1]?.year)}</h3><div className="mt-2 overflow-x-auto"><table className="w-full min-w-[440px] text-left text-sm"><thead className="bg-slate-50 text-xs text-muted"><tr><th className="p-2">{t(language, 'Year')}</th><th className="p-2">{t(language, 'Rainfall total')} (mm)</th><th className="p-2">{t(language, 'Annual observations')}</th><th className="p-2">{t(language, 'Expected days')}</th></tr></thead><tbody>{annual.map(row => <tr className="border-t border-line" key={String(row.year)}><td className="p-2">{value(row.year)}</td><td className="p-2">{value(row.total_rainfall)}</td><td className="p-2">{value(row.rainfall_observation_count ?? row.record_count)}</td><td className="p-2">{value(row.expected_day_count)}</td></tr>)}</tbody></table></div></div>}
          {trend && <div className="mt-5 rounded-xl border border-blue-100 bg-blue-50 p-4"><h3 className="font-semibold">{t(language, 'Descriptive rainfall trend')}</h3>{trend.status === 'available' ? <p className="mt-1 text-sm">{t(language, 'Slope')}: {value(trend.slope_per_year)} mm/year · {t(language, 'Trend period')}: {value(trend.period_start)} – {value(trend.period_end)} · {t(language, 'Sample count')}: {value(trend.observations)} · {t(language, 'Coverage years')}: {value(trend.coverage_years)}</p> : <p role="status" className="mt-1 text-sm">{t(language, 'Insufficient data')} · {t(language, 'Sample count')}: {value(trend.observations)} / {value(trend.minimum_observations)}</p>}<p className="mt-2 text-xs text-muted">{value(trend.method, t(language, 'Limitations'))}</p></div>}
          {!!anomalies.length && <div className="mt-6"><h3 className="font-semibold">{t(language, 'Observed rainfall and anomaly')}</h3><p className="mt-1 text-xs text-muted">{t(language, 'Analytical comparison; not an official warning.')}</p><div className="mt-2 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead className="bg-slate-50 text-xs text-muted"><tr><th className="p-2">{t(language, 'Year')} / {t(language, 'Month')}</th><th className="p-2">{t(language, 'Observation')} (mm)</th><th className="p-2">{t(language, 'Climatology normal')} (mm)</th><th className="p-2">{t(language, 'Anomaly')} (mm)</th><th className="p-2">{t(language, 'Anomaly')} (%)</th></tr></thead><tbody>{anomalies.map((row, index) => <tr className="border-t border-line" key={`${row.year}-${row.month}-${index}`}><td className="p-2">{value(row.year)} / {value(row.month)}</td><td className="p-2">{value(row.observed_rainfall_mm)}</td><td className="p-2">{value(row.normal_rainfall_mm)}</td><td className="p-2">{value(row.anomaly_rainfall_mm)}</td><td className="p-2">{value(row.anomaly_percent)}</td></tr>)}</tbody></table></div></div>}
        </>}
      </section>

      <section className="rounded-2xl border border-line bg-white p-5 shadow-card"><h2 className="text-lg font-semibold">{t(language, 'IMD monthly climatology')} · {value(result.normals[0]?.response.baseline, '1991-2020')} <span className="ml-2 rounded-full bg-blue-50 px-2 py-1 text-[10px] font-bold uppercase text-blue-900">{t(language, 'Climatology normal').toUpperCase()}</span></h2><p className="mt-1 text-sm text-muted">{t(language, 'Source')}: {climateSources.join(', ') || 'India Meteorological Department (IMD)'}. {t(language, 'Rainfall mm; temperature °C. Resolution is shown per returned product.')}</p><div className="mt-3 overflow-x-auto"><table className="w-full min-w-[640px] text-left text-sm"><thead className="bg-slate-50 text-xs text-muted"><tr><th className="p-2">{t(language, 'Month')}</th><th className="p-2">{t(language, 'Normal monthly rainfall')} (mm)</th><th className="p-2">{t(language, 'Normal Tmax')} (°C)</th><th className="p-2">{t(language, 'Normal Tmin')} (°C)</th></tr></thead><tbody>{result.normals.map(entry => { const cells = [normalFor(entry, 'rainfall'), normalFor(entry, 'tmax'), normalFor(entry, 'tmin')]; return <tr className="border-t border-line" key={entry.month}><td className="p-2">{entry.month}</td>{cells.map((normal, index) => <td className="p-2" key={index}>{normal?.status === 'available' ? `${value(normal.normal)} · ${value(normal.resolution_degrees)}°` : t(language, 'Unavailable')}</td>)}</tr>; })}</tbody></table></div>{result.normals.some(entry => entry.response.status !== 'available') && <p role="status" className="mt-3 text-sm text-amber-900">{t(language, 'Climatology unavailable for this location/month.')}</p>}<p className="mt-3 text-xs text-muted">{t(language, 'Observation')}, {t(language, 'Climatology normal')}, and {t(language, 'Anomaly')} are distinct data types. {t(language, 'Analytical comparison; not an official warning.')}</p></section>
    </div>}
  </main>;
}
