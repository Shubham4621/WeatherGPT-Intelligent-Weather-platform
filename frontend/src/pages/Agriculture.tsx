import { useState, type FormEvent } from 'react';
import { Leaf, MapPin, Sprout } from 'lucide-react';
import WeatherMapCanvas from '../components/map/WeatherMapCanvas';
import { getAgricultureAdvice, type AgricultureAdvice, type AgricultureAdviceRequest, type FarmActivity, type ResolvedLocation } from '../services/weatherApi';
import { localeFor, t, useLanguage } from '../i18n';

const activities: Array<{ value: FarmActivity; label: string }> = [
  { value: 'irrigation', label: 'Irrigation planning' }, { value: 'sowing', label: 'Sowing guidance' },
  { value: 'spraying', label: 'Spraying weather' }, { value: 'harvesting', label: 'Harvesting' },
  { value: 'field_operations', label: 'Field operations' }, { value: 'heat_stress', label: 'Crop/weather heat concern' },
  { value: 'heavy_rain', label: 'Rainfall concern' }, { value: 'wind_risk', label: 'Wind concern' },
  { value: 'general', label: 'General farm weather' },
];

type StationMeta = { station_id: string; station_name: string; latitude: number; longitude: number; elevation_m: number | null; source: string; coordinate_precision?: string | null };
function isResolvedLocation(value: AgricultureAdvice['location'] | null): value is ResolvedLocation {
  return Boolean(value && 'latitude' in value && typeof value.latitude === 'number' && 'longitude' in value && typeof value.longitude === 'number' && value.status === 'resolved');
}

export default function Agriculture() {
  const { language } = useLanguage();
  const [city, setCity] = useState('Nashik');
  const [coordinateMode, setCoordinateMode] = useState(false);
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [activity, setActivity] = useState<FarmActivity>('general');
  const [crop, setCrop] = useState('');
  const [growthStage, setGrowthStage] = useState('');
  const [irrigationAvailable, setIrrigationAvailable] = useState('');
  const [result, setResult] = useState<AgricultureAdvice | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true); setError(null); setResult(null);
    try {
      const request: AgricultureAdviceRequest = coordinateMode
        ? { latitude: Number(latitude), longitude: Number(longitude), activity, crop: crop.trim() || undefined, growth_stage: growthStage.trim() || undefined, irrigation_available: irrigationAvailable === '' ? undefined : irrigationAvailable === 'yes' }
        : { city: city.trim(), activity, crop: crop.trim() || undefined, growth_stage: growthStage.trim() || undefined, irrigation_available: irrigationAvailable === '' ? undefined : irrigationAvailable === 'yes' };
      if (coordinateMode && (request.latitude === undefined || request.longitude === undefined || !Number.isFinite(request.latitude) || !Number.isFinite(request.longitude) || request.latitude < -90 || request.latitude > 90 || request.longitude < -180 || request.longitude > 180)) {
        setError(t(language, 'Enter valid latitude and longitude values.')); return;
      }
      setResult(await getAgricultureAdvice(request));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t(language, 'Unable to load agricultural weather guidance.'));
    } finally { setLoading(false); }
  }

  const selectedLocation = isResolvedLocation(result?.location ?? null) ? result!.location as ResolvedLocation : null;
  const stationMetadata = result?.station?.metadata as StationMeta | undefined;
  const station = stationMetadata && Number.isFinite(stationMetadata.latitude) && Number.isFinite(stationMetadata.longitude) ? stationMetadata : null;

  return <main id="main" className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
    <header className="mb-7"><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[.16em] text-brand"><Leaf size={15}/>{t(language, 'WeatherGPT Agriculture Advisory')}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">{t(language, 'Farm weather guidance')}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{t(language, 'Weather-based decision support from validated observations and available forecast sources. No soil moisture or crop-specific agronomic rules are assumed.')}</p></header>

    <form onSubmit={(event) => void submit(event)} className="grid gap-4 rounded-3xl border border-line bg-white p-5 shadow-card md:grid-cols-2 xl:grid-cols-4">
      <div className="flex items-center gap-2 md:col-span-2 xl:col-span-4"><MapPin size={17} className="text-brand"/><h2 className="font-semibold">{t(language, 'Location and farm context')}</h2></div>
      <label className="flex items-center gap-2 text-sm md:col-span-2 xl:col-span-4"><input type="checkbox" checked={coordinateMode} onChange={(event) => setCoordinateMode(event.target.checked)} aria-label={t(language, 'Use coordinates instead of a city')}/>{t(language, 'Use coordinates instead of a city')}</label>
      {coordinateMode ? <>
        <label className="text-sm font-medium">{t(language, 'Latitude')}<input aria-label={t(language, 'Latitude')} required type="number" min="-90" max="90" step="any" value={latitude} onChange={(event) => setLatitude(event.target.value)} className="mt-2 block min-h-11 w-full rounded-xl border border-line px-3"/></label>
        <label className="text-sm font-medium">{t(language, 'Longitude')}<input aria-label={t(language, 'Longitude')} required type="number" min="-180" max="180" step="any" value={longitude} onChange={(event) => setLongitude(event.target.value)} className="mt-2 block min-h-11 w-full rounded-xl border border-line px-3"/></label>
      </> : <label className="text-sm font-medium md:col-span-2">{t(language, 'City or location')}<input aria-label={t(language, 'City or location')} required value={city} onChange={(event) => setCity(event.target.value)} className="mt-2 block min-h-11 w-full rounded-xl border border-line px-3"/></label>}
      <label className="text-sm font-medium">{t(language, 'Farm activity')}<select aria-label={t(language, 'Farm activity')} value={activity} onChange={(event) => setActivity(event.target.value as FarmActivity)} className="mt-2 block min-h-11 w-full rounded-xl border border-line bg-white px-3">{activities.map((item) => <option key={item.value} value={item.value}>{t(language, item.label)}</option>)}</select></label>
      <label className="text-sm font-medium">{t(language, 'Crop (optional)')}<input aria-label={t(language, 'Crop (optional)')} value={crop} onChange={(event) => setCrop(event.target.value)} placeholder={t(language, 'For context only')} className="mt-2 block min-h-11 w-full rounded-xl border border-line px-3"/></label>
      <label className="text-sm font-medium">{t(language, 'Growth stage (optional)')}<input aria-label={t(language, 'Growth stage (optional)')} value={growthStage} onChange={(event) => setGrowthStage(event.target.value)} className="mt-2 block min-h-11 w-full rounded-xl border border-line px-3"/></label>
      <label className="text-sm font-medium">{t(language, 'Irrigation available (optional)')}<select aria-label={t(language, 'Irrigation available (optional)')} value={irrigationAvailable} onChange={(event) => setIrrigationAvailable(event.target.value)} className="mt-2 block min-h-11 w-full rounded-xl border border-line bg-white px-3"><option value="">{t(language, 'Not specified')}</option><option value="yes">{t(language, 'Yes')}</option><option value="no">{t(language, 'No')}</option></select></label>
      <button type="submit" disabled={loading} className="min-h-11 self-end rounded-xl bg-brand px-5 font-semibold text-white disabled:opacity-60 md:col-span-2 xl:col-span-4">{loading ? t(language, 'Loading agriculture context…') : t(language, 'Get weather-based guidance')}</button>
    </form>
    {coordinateMode && <p className="mt-3 text-xs text-muted">{t(language, 'Select a location on the map to fill coordinates; map clicks do not reverse-geocode.')}</p>}
    {loading && <p role="status" className="mt-5 text-sm text-muted">{t(language, 'Resolving location and validating weather inputs…')}</p>}
    {error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">{error}</p>}

    {result && <section className="mt-6 space-y-5" aria-label={t(language, 'Agriculture recommendation')}>
      <div role="status" className={`rounded-xl border p-4 text-sm ${result.status === 'available' ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : 'border-amber-200 bg-amber-50 text-amber-950'}`}><strong>{t(language, result.status === 'available' ? 'Weather context available' : result.status === 'partial' ? 'Partial weather context' : result.status === 'unavailable' ? 'Location or provider unavailable' : 'Insufficient data')}</strong>{selectedLocation && <span> · {selectedLocation.city ?? selectedLocation.query}, {selectedLocation.latitude.toFixed(4)}, {selectedLocation.longitude.toFixed(4)}</span>}</div>
      <div className="grid gap-5 lg:grid-cols-[1.1fr_.9fr]">
        <section className="overflow-hidden rounded-2xl border border-line bg-white shadow-card" aria-label={t(language, 'Selected farm location map')}>
          <WeatherMapCanvas location={selectedLocation} current={result.current_weather} alerts={null} showAlerts={false} nwp={null} nwpPoint={null} showNwp={false} showPrecipitation={false} showWind={false} station={station} onMapSelect={(lat, lon) => { setCoordinateMode(true); setLatitude(lat.toFixed(5)); setLongitude(lon.toFixed(5)); }} onTileError={() => undefined} onTileLoad={() => undefined}/>
          <div className="p-3 text-xs text-muted">{t(language, 'Selected location and configured IMD station only. No farm boundary or crop map is shown.')}</div>
        </section>
        <article className="rounded-2xl border border-line bg-white p-5 shadow-card"><p className="text-xs font-semibold uppercase tracking-wide text-brand">{t(language, 'WeatherGPT Agriculture Advisory')}</p><p className="mt-1 text-xs text-muted">{t(language, 'Not an official agricultural department advisory.')}</p><h2 className="mt-4 text-xl font-semibold">{t(language, activities.find((item) => item.value === activity)?.label ?? 'General farm weather')}</h2><p className="mt-2 text-xs uppercase tracking-wide text-muted">{t(language, result.recommendation.condition.replace(/_/g, ' '))} · {t(language, 'Confidence')}: {t(language, result.recommendation.confidence)}</p><p className="mt-3 leading-7">{t(language, result.recommendation.recommendation)}</p><p className="mt-3 text-xs text-muted">{result.recommendation.valid_period}</p></article>
      </div>

      {station && <section className="rounded-2xl border border-line bg-white p-5 shadow-card"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="flex items-center gap-2 font-semibold"><Sprout size={17} className="text-emerald-700"/>{t(language, 'IMD Station')}: {station.station_name}</h2><p className="mt-1 text-sm text-muted">{t(language, 'Station ID')}: {station.station_id} · {t(language, 'Station coordinates')}: {station.coordinate_precision ?? `${station.latitude}, ${station.longitude}`} · {t(language, 'Elevation')}: {station.elevation_m ?? t(language, 'Unavailable')} m</p><p className="mt-1 text-xs text-muted">{t(language, 'Source')}: {station.source} · {t(language, 'Distance from selected location')}: {result.station?.distance_km.toFixed(2)} km · {t(language, 'Observation state')}: {t(language, result.station?.data_status ?? 'unavailable')}</p></div></div>
        {result.station?.latest_daily_observation && <div className="mt-4 grid gap-2 text-sm sm:grid-cols-4"><StationValue label={t(language, 'Daily maximum')} value={result.station.latest_daily_observation.temp_max_c} unit="°C"/><StationValue label={t(language, 'Daily minimum')} value={result.station.latest_daily_observation.temp_min_c} unit="°C"/><StationValue label={t(language, '24 h rainfall')} value={result.station.latest_daily_observation.rainfall_mm} unit="mm"/><p className="text-xs text-muted sm:col-span-4">{t(language, 'Observed at')} {new Date(result.station.latest_daily_observation.observed_at).toLocaleString(localeFor(language))} · {result.station.latest_daily_observation.dataset}</p></div>}
        <p className="mt-2 text-xs text-muted">{t(language, result.station?.retrieval_mode ?? 'Station data retrieval mode unavailable.')}</p>
        {result.station?.data_status === 'stale' && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{t(language, 'Latest local DSP observations are stale and were not used in current recommendation rules.')}</p>}
        {result.station?.quality_summary && <div className="mt-4 grid gap-3 border-t border-line pt-3 sm:grid-cols-2">{Object.entries(result.station.quality_summary).map(([kind, quality]) => <p key={kind} className="text-xs text-muted">{t(language, kind === 'daily' ? 'Daily station-data quality' : 'Synoptic station-data quality')}: {t(language, 'rows')} {String(quality.row_count)} · {t(language, 'coverage')} {String(quality.coverage_start)} – {String(quality.coverage_end)} · {t(language, 'missing dates or slots')} {String(quality.missing_dates_or_slots_between_coverage)} · {t(language, 'duplicate records')} {String(quality.duplicate_records)} · {t(language, 'invalid rows')} {String(quality.invalid_date_or_station_rows)}</p>)}</div>}
      </section>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DataCard title="Current observations" source={result.current_weather?.source ?? 'Unavailable'}>{result.current_weather ? <p>{result.current_weather.weather.temperature.toFixed(1)} °C · {result.current_weather.weather.humidity}% RH · {result.current_weather.weather.wind_speed.toFixed(1)} m/s · {result.current_weather.weather.description}<br/><span className="text-xs text-muted">{t(language, 'Observed at')} {new Date(result.current_weather.observed_at).toLocaleString(localeFor(language))}</span></p> : <p>{t(language, 'Current weather unavailable.')}</p>}</DataCard>
        <DataCard title="Operational forecast" source={result.forecast_context?.source ?? 'Unavailable'}>{result.forecast_context?.periods.length ? <ul>{result.forecast_context.periods.map((period) => <li key={period.date}>{new Date(period.date).toLocaleDateString(localeFor(language), { timeZone: 'UTC' })}: {period.temperature_min.toFixed(1)}–{period.temperature_max.toFixed(1)} °C · {period.rain_probability == null ? t(language, 'Rain probability unavailable') : `${period.rain_probability.toFixed(0)}% rain probability`} · {period.wind_speed == null ? t(language, 'Wind unavailable') : `${period.wind_speed.toFixed(1)} m/s wind`}</li>)}</ul> : <p>{t(language, 'Forecast data unavailable.')}</p>}</DataCard>
        <DataCard title="NWP/GFS model context" source={result.nwp_context?.source ?? 'Unavailable'}>{result.nwp_context?.points.length ? <p>{result.nwp_context.model} · {result.nwp_context.initialization_time ? new Date(result.nwp_context.initialization_time).toUTCString() : t(language, 'Run time unavailable')}<br/>{result.nwp_context.points[0].temperature_c ?? t(language, 'Temperature unavailable')} °C · {result.nwp_context.points[0].precipitation_since_initialization_mm ?? t(language, 'Precipitation unavailable')} mm accumulated since run · {result.nwp_context.points[0].wind_speed_ms ?? t(language, 'Wind unavailable')} m/s<br/><span className="text-xs text-muted">{result.nwp_context.provenance}</span></p> : <p>{t(language, 'NWP data unavailable.')}</p>}</DataCard>
        <DataCard title="Historical observations" source={String(result.historical_context?.source ?? 'Unavailable')}>{result.historical_context ? <p>{t(language, String(result.historical_context.status))} · {t(language, 'Records')}: {String(result.historical_context.record_count ?? 0)} · {String((result.historical_context.period as { start?: string } | undefined)?.start ?? '')} – {String((result.historical_context.period as { end?: string } | undefined)?.end ?? '')}</p> : <p>{t(language, 'Historical data unavailable for this location and period.')}</p>}</DataCard>
        <DataCard title="IMD climatology (1991–2020)" source={String(result.climatology_context?.source ?? 'Unavailable')}>{result.climatology_context?.status === 'available' ? <p>{String(result.climatology_context.normal_monthly_rainfall_mm)} mm normal monthly rainfall</p> : <p>{t(language, 'Climatology unavailable for this location/month.')}</p>}</DataCard>
        <DataCard title="Official IMD warning" source={String(result.official_warning?.source ?? 'India Meteorological Department (IMD)')}>{result.official_warning?.status === 'available' ? <><p>{t(language, 'Official warning data; displayed separately from WeatherGPT advice.')}</p>{((result.official_warning.active_days as Array<{ date: string; severity?: string | null; warnings?: Array<{ warning_type: string }> }> | undefined) ?? []).map((day) => <p key={day.date} className="mt-2">{new Date(day.date).toLocaleDateString(localeFor(language))} · IMD {day.severity ?? t(language, 'level unavailable')}: {day.warnings?.map((warning) => warning.warning_type).join(', ') || t(language, 'No warning details supplied')}</p>)}</> : <p>{t(language, String(result.official_warning?.status ?? 'unavailable'))}</p>}</DataCard>
      </div>
      <section className="rounded-2xl border border-line bg-white p-5"><h2 className="font-semibold">{t(language, 'Evidence and data quality')}</h2><ul className="mt-3 space-y-2">{result.recommendation.evidence.map((item, index) => <li key={`${item.label}-${index}`} className="text-sm">{t(language, item.label)}: <strong>{item.value}{item.unit ? ` ${item.unit}` : ''}</strong> · {item.source}{item.valid_time ? ` · ${new Date(item.valid_time).toLocaleString(localeFor(language))}` : ''}{item.detail ? <span className="block text-xs text-muted">{t(language, item.detail)}</span> : null}</li>)}</ul><p className="mt-3 text-xs text-muted">{t(language, 'Input status')}: {Object.entries(result.data_quality).map(([key, value]) => `${t(language, key)} ${t(language, String(value))}`).join(' · ')}</p><ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted">{result.limitations.map((item) => <li key={item}>{t(language, item)}</li>)}</ul></section>
    </section>}
  </main>;
}

function DataCard({ title, source, children }: { title: string; source: string; children: React.ReactNode }) {
  const { language } = useLanguage();
  return <article className="rounded-2xl border border-line bg-white p-4 shadow-card"><h2 className="font-semibold">{t(language, title)}</h2><div className="mt-2 text-sm leading-6">{children}</div><p className="mt-3 text-xs text-muted">{t(language, 'Source')}: {source}</p></article>;
}

function StationValue({ label, value, unit }: { label: string; value: number | null; unit: string }) {
  const { language } = useLanguage();
  return <p><span className="text-muted">{label}</span><br/><strong>{value == null ? t(language, 'Missing') : `${value} ${unit}`}</strong></p>;
}
