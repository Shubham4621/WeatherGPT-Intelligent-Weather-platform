import { useRef, useState, type FormEvent } from 'react';
import { Cloud, CloudRain, Compass, MapPin, RefreshCw, Wind } from 'lucide-react';
import WeatherMapCanvas from '../components/map/WeatherMapCanvas';
import {
  getCurrentWeatherAtCoordinates, getForecast, getNwpForecast, getWeatherAdvisory, getWeatherAlerts,
  resolveLocation, WeatherApiError, type NwpForecastResponse, type NwpPoint, type ResolvedLocation,
} from '../services/weatherApi';
import type { ForecastResponse, WeatherAdvisory, WeatherAlertsResponse, WeatherResponse } from '../types/weather';

type LayerName = 'current' | 'forecast' | 'nwp' | 'precipitation' | 'wind' | 'alerts' | 'advisory';
type LayerStatus = 'loading' | 'available' | 'partial' | 'unavailable' | 'error';
type LayerState = { status: LayerStatus; message?: string };
type MapLayers = Record<LayerName, boolean>;

const LAYER_OPTIONS: Array<{ id: LayerName; label: string; detail: string }> = [
  { id: 'current', label: 'Current Weather', detail: 'OpenWeatherMap point observation' },
  { id: 'forecast', label: 'Operational Forecast', detail: 'Existing forecast provider, selected point' },
  { id: 'nwp', label: 'NWP / GFS', detail: 'NOAA/NCEP GFS selected model point' },
  { id: 'precipitation', label: 'GFS accumulated precipitation', detail: 'Since model initialization; selected point' },
  { id: 'wind', label: 'GFS 10 m wind speed', detail: 'Selected point; direction is not provided' },
  { id: 'alerts', label: 'Official IMD warnings', detail: 'Verified district lookup; no warning polygons' },
  { id: 'advisory', label: 'WeatherGPT Advisory', detail: 'Separate advisory result for selected city' },
];

const INITIAL_LAYERS: MapLayers = { current: true, forecast: false, nwp: false, precipitation: false, wind: false, alerts: false, advisory: false };

function keyFor(location: ResolvedLocation) { return `${location.latitude.toFixed(6)},${location.longitude.toFixed(6)}`; }

export default function WeatherMap() {
  const [query, setQuery] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [location, setLocation] = useState<ResolvedLocation | null>(null);
  const locationKeyRef = useRef('');
  const [layers, setLayers] = useState<MapLayers>(INITIAL_LAYERS);
  const [states, setStates] = useState<Partial<Record<LayerName, LayerState>>>({});
  const [current, setCurrent] = useState<WeatherResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [nwp, setNwp] = useState<NwpForecastResponse | null>(null);
  const [nwpKey, setNwpKey] = useState('');
  const [nwpTime, setNwpTime] = useState('');
  const [alerts, setAlerts] = useState<WeatherAlertsResponse | null>(null);
  const [advisory, setAdvisory] = useState<WeatherAdvisory | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tilesUnavailable, setTilesUnavailable] = useState(false);
  const lastRequestKeys = useRef<Partial<Record<LayerName, string>>>({});

  async function loadLayer(layer: LayerName, target: ResolvedLocation, force = false) {
    const targetKey = keyFor(target);
    if (!force && lastRequestKeys.current[layer] === targetKey) return;
    lastRequestKeys.current[layer] = targetKey;
    setStates((previous) => ({ ...previous, [layer]: { status: 'loading' } }));
    const stillSelected = () => locationKeyRef.current === targetKey;
    try {
      if (layer === 'current') {
        const result = await getCurrentWeatherAtCoordinates(target.latitude, target.longitude);
        if (!stillSelected()) return;
        setCurrent(result);
        setStates((previous) => ({ ...previous, current: { status: 'available' } }));
      } else if (layer === 'forecast') {
        const result = await getForecast({ latitude: target.latitude, longitude: target.longitude });
        if (!stillSelected()) return;
        setForecast(result);
        setStates((previous) => ({ ...previous, forecast: { status: 'available' } }));
      } else if (layer === 'nwp' || layer === 'precipitation' || layer === 'wind') {
        if (nwp && nwpKey === targetKey && !force) {
          const state: LayerState = nwp.status === 'available' || nwp.status === 'partial'
            ? { status: nwp.status } : { status: 'unavailable', message: nwp.reason ?? nwp.status };
          if (stillSelected()) setStates((previous) => ({ ...previous, nwp: state, precipitation: state, wind: state }));
          return;
        }
        const result = await getNwpForecast(`${target.latitude},${target.longitude}`, 2);
        if (!stillSelected()) return;
        setNwp(result);
        setNwpKey(targetKey);
        setNwpTime(result.points[0]?.forecast_time ?? '');
        const state: LayerState = result.status === 'available' || result.status === 'partial'
          ? { status: result.status, message: result.status === 'partial' ? `Missing forecast leads: ${result.missing_leads.join(', ')}.` : undefined }
          : { status: result.status === 'error' ? 'error' : 'unavailable', message: result.reason ?? result.status };
        setStates((previous) => ({ ...previous, nwp: state, precipitation: state, wind: state }));
      } else if (layer === 'alerts') {
        if (!target.city || target.resolution_method === 'coordinates') {
          if (stillSelected()) setStates((previous) => ({ ...previous, alerts: { status: 'unavailable', message: 'A city with a verified IMD district mapping is required. No warning geometry is available.' } }));
          return;
        }
        const result = await getWeatherAlerts(target.city);
        if (!stillSelected()) return;
        setAlerts(result);
        setStates((previous) => ({ ...previous, alerts: { status: 'available' } }));
      } else if (layer === 'advisory') {
        if (!target.city || target.resolution_method === 'coordinates') {
          if (stillSelected()) setStates((previous) => ({ ...previous, advisory: { status: 'unavailable', message: 'Select a resolved city to request its advisory.' } }));
          return;
        }
        const result = await getWeatherAdvisory(target.city, 1, 'GENERAL_PRECAUTION');
        if (!stillSelected()) return;
        setAdvisory(result);
        setStates((previous) => ({ ...previous, advisory: { status: 'available' } }));
      }
    } catch (cause) {
      if (!stillSelected()) return;
      const message = cause instanceof Error ? cause.message : 'The selected data source is unavailable.';
      const state: LayerState = cause instanceof WeatherApiError && cause.status !== undefined && cause.status >= 500
        ? { status: 'error', message } : { status: 'unavailable', message };
      setStates((previous) => ({ ...previous, [layer]: state }));
    }
  }

  function selectLocation(next: ResolvedLocation) {
    locationKeyRef.current = keyFor(next);
    lastRequestKeys.current = {};
    setLocation(next);
    setCurrent(null); setForecast(null); setNwp(null); setNwpKey(''); setNwpTime(''); setAlerts(null); setAdvisory(null);
    setStates({}); setSearchError(null);
    Object.entries(layers).forEach(([name, enabled]) => { if (enabled) void loadLayer(name as LayerName, next); });
  }

  async function searchCity(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) { setSearchError('Enter a city or place name.'); return; }
    setBusy(true); setSearchError(null);
    try { selectLocation(await resolveLocation(query.trim())); }
    catch (cause) { setSearchError(cause instanceof Error ? cause.message : 'Location could not be resolved.'); }
    finally { setBusy(false); }
  }

  function selectCoordinates(event: FormEvent) {
    event.preventDefault();
    const lat = Number(latitude); const lon = Number(longitude);
    if (!latitude.trim() || !longitude.trim() || !Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setSearchError('Enter valid coordinates: latitude -90 to 90 and longitude -180 to 180.'); return;
    }
    const next: ResolvedLocation = { query: `${lat}, ${lon}`, city: null, district: null, state: null, country: null,
      latitude: lat, longitude: lon, timezone: null, source: 'User-selected coordinates', resolution_method: 'coordinates', status: 'resolved' };
    setLatitude(String(lat)); setLongitude(String(lon)); selectLocation(next);
  }

  function selectMapPoint(lat: number, lon: number) {
    setLatitude(lat.toFixed(5)); setLongitude(lon.toFixed(5));
    selectLocation({ query: `${lat.toFixed(5)}, ${lon.toFixed(5)}`, city: null, district: null, state: null, country: null,
      latitude: lat, longitude: lon, timezone: null, source: 'Map-selected coordinates', resolution_method: 'coordinates', status: 'resolved' });
  }

  function toggleLayer(layer: LayerName, enabled: boolean) {
    setLayers((previous) => ({ ...previous, [layer]: enabled }));
    if (!enabled) {
      delete lastRequestKeys.current[layer];
      setStates((previous) => ({ ...previous, [layer]: undefined }));
      return;
    }
    if (location) void loadLayer(layer, location);
  }

  function refreshSelected() {
    if (!location) return;
    lastRequestKeys.current = {};
    for (const [layer, enabled] of Object.entries(layers)) if (enabled) void loadLayer(layer as LayerName, location, true);
  }

  const selectedNwpPoint: NwpPoint | null = nwp?.points.find((point) => point.forecast_time === nwpTime) ?? null;
  const locationTitle = location ? [location.city ?? location.query, location.state, location.country].filter(Boolean).join(', ') : 'No location selected';

  return <main id="main" className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
    <header className="mb-7"><p className="text-xs font-semibold uppercase tracking-[.16em] text-brand">Spatial weather visualization</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">Weather Map</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">Explore a real geographic map and request weather products for one selected location. Point data is not interpolated into a regional field.</p></header>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section aria-label="Weather map and selected point" className="space-y-3">
        <WeatherMapCanvas location={location} current={current} alerts={alerts} showAlerts={layers.alerts} nwp={nwp} nwpPoint={selectedNwpPoint} showNwp={layers.nwp} showPrecipitation={layers.precipitation} showWind={layers.wind} onMapSelect={selectMapPoint} onTileError={() => setTilesUnavailable(true)} onTileLoad={() => setTilesUnavailable(false)}/>
        {tilesUnavailable && <p role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">Base-map tiles are temporarily unavailable. Weather requests and location controls remain available.</p>}
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-white px-4 py-3 text-xs text-muted"><span>Base map: © <a className="underline" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>. Tiles require an internet connection and are best-effort.</span><span>Click the map to inspect coordinates.</span></div>
      </section>
      <aside className="space-y-4">
        <section className="rounded-2xl border border-line bg-white p-4 shadow-card"><h2 className="font-semibold text-ink">Choose a location</h2>
          <form onSubmit={searchCity} className="mt-3 flex gap-2"><label className="sr-only" htmlFor="weather-map-city">Search a city</label><input id="weather-map-city" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="City, state, country" className="min-h-11 min-w-0 flex-1 rounded-xl border border-line px-3 text-sm"/><button disabled={busy} className="min-h-11 rounded-xl bg-brand px-3 text-sm font-semibold text-white disabled:opacity-60">{busy ? 'Searching…' : 'Search'}</button></form>
          <form onSubmit={selectCoordinates} className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2"><label className="sr-only" htmlFor="weather-map-latitude">Latitude</label><input id="weather-map-latitude" aria-label="Latitude" inputMode="decimal" value={latitude} onChange={(event) => setLatitude(event.target.value)} placeholder="Latitude" className="min-h-10 min-w-0 rounded-xl border border-line px-2 text-sm"/><label className="sr-only" htmlFor="weather-map-longitude">Longitude</label><input id="weather-map-longitude" aria-label="Longitude" inputMode="decimal" value={longitude} onChange={(event) => setLongitude(event.target.value)} placeholder="Longitude" className="min-h-10 min-w-0 rounded-xl border border-line px-2 text-sm"/><button className="min-h-10 rounded-xl border border-line px-3 text-sm font-semibold">Select</button></form>
          {searchError && <p role="alert" className="mt-3 text-sm text-rose-700">{searchError}</p>}
          <div aria-live="polite" className="mt-3 rounded-xl bg-slate-50 p-3 text-sm"><p className="font-semibold text-ink">{locationTitle}</p>{location ? <><p className="mt-1 text-xs text-muted">{location.latitude.toFixed(5)}, {location.longitude.toFixed(5)} · {location.source}</p><p className="mt-1 text-xs text-muted">Resolution: {location.resolution_method}</p></> : <p className="mt-1 text-xs text-muted">Search for a city or select a point on the map.</p>}</div>
        </section>

        <section className="rounded-2xl border border-line bg-white p-4 shadow-card"><div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-ink">Weather layers</h2><button type="button" onClick={refreshSelected} disabled={!location} aria-label="Refresh selected map layers" className="rounded-lg p-2 text-muted hover:bg-slate-100 disabled:opacity-40"><RefreshCw size={16}/></button></div><div className="mt-2 space-y-1">{LAYER_OPTIONS.map((option) => <label key={option.id} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl px-2 py-1 hover:bg-slate-50"><input type="checkbox" checked={layers[option.id]} onChange={(event) => toggleLayer(option.id, event.target.checked)} className="h-4 w-4 accent-brand"/><span className="min-w-0"><span className="block text-sm font-medium text-ink">{option.label}</span><span className="block text-[11px] text-muted">{option.detail}</span></span></label>)}</div><p className="mt-3 text-xs text-muted">Requests are sent when you select a location or enable a layer, not while panning.</p></section>

        {location && layers.current && <LayerCard title="Current Weather" icon={<Cloud size={17}/>} state={states.current}>
          {current && <><p className="text-2xl font-semibold text-ink">{current.weather.temperature.toFixed(1)} °C <span className="text-base font-medium">· {current.weather.description}</span></p><p className="mt-1 text-sm text-muted">Humidity {current.weather.humidity}% · Wind {current.weather.wind_speed.toFixed(1)} m/s</p><p className="mt-2 text-xs text-muted">Observed {new Date(current.observed_at).toLocaleString()} · Source: {current.source}</p></>}
        </LayerCard>}

        {location && layers.forecast && <LayerCard title="Operational Forecast" icon={<Cloud size={17}/>} state={states.forecast}>
          {forecast && <><p className="text-xs text-muted">Source: {forecast.source} · Forecast generated {new Date(forecast.forecasted_at).toLocaleString()}</p><div className="mt-2 space-y-2">{forecast.forecast.slice(0, 3).map((day) => <div key={day.date} className="flex justify-between gap-3 border-t border-line pt-2 text-sm"><span>{new Date(day.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })} · {day.description}</span><span className="whitespace-nowrap">{day.temperature_min.toFixed(0)}–{day.temperature_max.toFixed(0)} °C</span></div>)}</div></>}
        </LayerCard>}

        {location && layers.nwp && <LayerCard title="NWP / GFS · Point data" icon={<Compass size={17}/>} state={states.nwp}>
          {nwp?.status && (nwp.status === 'available' || nwp.status === 'partial') && <><p className="text-xs text-muted">{nwp.model} · Provider: {nwp.source} · Native grid: {nwp.resolution_degrees}°</p><p className="mt-1 text-xs text-muted">Run: {nwp.initialization_time ? new Date(nwp.initialization_time).toUTCString() : 'Unavailable'}</p><p className="mt-1 text-xs text-muted">Requested: {location.latitude.toFixed(5)}, {location.longitude.toFixed(5)} · Grid: {nwp.selected_grid_point ? `${nwp.selected_grid_point.latitude.toFixed(3)}, ${nwp.selected_grid_point.longitude.toFixed(3)} (${nwp.selected_grid_point.distance_km.toFixed(2)} km)` : 'Unavailable'}</p>
            {nwp.points.length > 0 && <><label className="mt-3 block text-xs font-medium text-muted" htmlFor="gfs-valid-time">GFS forecast valid time</label><select id="gfs-valid-time" value={nwpTime} onChange={(event) => setNwpTime(event.target.value)} className="mt-1 min-h-10 w-full rounded-lg border border-line px-2 text-sm">{nwp.points.map((point) => <option key={point.forecast_time} value={point.forecast_time}>{new Date(point.forecast_time).toUTCString()} (f{String(point.lead_hours).padStart(3, '0')})</option>)}</select></>}
            {selectedNwpPoint && <div className="mt-3 grid grid-cols-2 gap-2 text-sm">{selectedNwpPoint.temperature_c != null && <Metric label="2 m temperature" value={`${selectedNwpPoint.temperature_c.toFixed(1)} °C`}/>}</div>}
            <p className="mt-2 text-xs text-muted">Valid data: {nwp.forecast_start ? new Date(nwp.forecast_start).toUTCString() : '—'} to {nwp.forecast_end ? new Date(nwp.forecast_end).toUTCString() : '—'} · {nwp.provenance}</p><p className="mt-1 text-xs text-muted">Single selected GFS point only; no area interpolation. NWP model output is not the operational forecast or an official warning.</p></>}
        </LayerCard>}

        {location && layers.precipitation && <LayerCard title="GFS precipitation · Point data" icon={<CloudRain size={17}/>} state={states.precipitation}>
          {selectedNwpPoint && selectedNwpPoint.precipitation_since_initialization_mm != null && <><p className="text-xl font-semibold text-ink">{selectedNwpPoint.precipitation_since_initialization_mm.toFixed(2)} mm</p><p className="mt-1 text-xs text-muted">Accumulated since model initialization, not a daily rainfall total. Valid {new Date(selectedNwpPoint.forecast_time).toUTCString()} · Run {nwp?.initialization_time ? new Date(nwp.initialization_time).toUTCString() : 'unavailable'} · Source: {nwp?.source}</p></>}
        </LayerCard>}

        {location && layers.wind && <LayerCard title="GFS wind · Point data" icon={<Wind size={17}/>} state={states.wind}>
          {selectedNwpPoint && selectedNwpPoint.wind_speed_ms != null && <><p className="text-xl font-semibold text-ink">{selectedNwpPoint.wind_speed_ms.toFixed(1)} m/s</p><p className="mt-1 text-xs text-muted">10 m wind speed · Valid {new Date(selectedNwpPoint.forecast_time).toUTCString()} · Source: {nwp?.source}. Direction is not available.</p></>}
        </LayerCard>}

        {location && layers.alerts && <LayerCard title="Official IMD Warning · District lookup" icon={<MapPin size={17}/>} state={states.alerts}>
          {alerts && <><p className="text-sm font-medium text-ink">{alerts.district}, {alerts.state}</p>{alerts.forecast_days.filter((day) => day.is_active).length ? alerts.forecast_days.filter((day) => day.is_active).map((day) => <p key={day.date} className="mt-2 text-sm">{new Date(day.date).toLocaleDateString()}: {day.warnings.map((warning) => warning.warning_type).join(', ')} · IMD level {day.severity ?? 'not specified'}</p>) : <p className="mt-1 text-sm text-muted">No active warning was returned for this district and period.</p>}<p className="mt-2 text-xs text-muted">Official source: {alerts.source}. The API supplies district lookup data, not warning polygons; no warning area is drawn.</p></>}
        </LayerCard>}

        {location && layers.advisory && <LayerCard title="WeatherGPT Advisory" icon={<Compass size={17}/>} state={states.advisory}>
          {advisory && <><p className="text-sm font-medium text-ink">WeatherGPT risk classification: {advisory.risk_level ?? 'Not assessed'}</p><p className="mt-1 text-sm text-muted">{advisory.summary}</p><p className="mt-2 text-xs text-muted">Source: WeatherGPT advisory engine. Separate from official IMD warnings and raw GFS model output.</p></>}
        </LayerCard>}
      </aside>
    </div>
  </main>;
}

function LayerCard({ title, icon, state, children }: { title: string; icon: React.ReactNode; state?: LayerState; children: React.ReactNode }) {
  return <section aria-label={title} className="rounded-2xl border border-line bg-white p-4 shadow-card"><h3 className="flex items-center gap-2 font-semibold text-ink">{icon}{title}</h3>
    {state?.status === 'loading' && <p role="status" className="mt-2 text-sm text-muted">Loading {title.toLowerCase()}…</p>}
    {state?.status === 'unavailable' && <p role="status" className="mt-2 text-sm text-amber-900">{title} unavailable: {state.message ?? 'No data returned for this location.'}</p>}
    {state?.status === 'error' && <p role="alert" className="mt-2 text-sm text-rose-800">{title} provider error: {state.message ?? 'The provider request failed.'}</p>}
    {state?.status === 'partial' && <p role="status" className="mt-2 text-sm text-amber-900">Partial data: {state.message ?? 'Some forecast periods are missing.'}</p>}
    {(state?.status === 'available' || state?.status === 'partial') && children}
  </section>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] text-muted">{label}</p><p className="mt-1 font-semibold text-ink">{value}</p></div>;
}
