import type { AdvisoryActivity, ForecastResponse, WeatherAdvisory, WeatherResponse, WeatherAlertsResponse } from '../types/weather';
import { API_BASE_URL, apiFetch, getApiErrorMessage, ApiClientError } from './apiClient';
const REQUEST_TIMEOUT_MS = 12_000;

export interface NwpPoint {
  forecast_time: string;
  lead_hours: number;
  temperature_c?: number | null;
  precipitation_since_initialization_mm?: number | null;
  wind_speed_ms?: number | null;
}
export interface NwpForecastResponse {
  status: 'available' | 'partial' | 'unavailable' | 'error';
  location: Record<string, unknown> | null;
  source: string;
  model: string;
  initialization_time?: string | null;
  retrieved_at?: string | null;
  forecast_start?: string | null;
  forecast_end?: string | null;
  resolution_degrees: number;
  units: Record<string, string>;
  provenance: string;
  source_url: string;
  selected_grid_point?: { latitude: number; longitude: number; distance_km: number } | null;
  points: NwpPoint[];
  forecast: ForecastResponse['forecast'];
  missing_leads: number[];
  reason?: string | null;
}

export async function getNwpForecast(location: string, days = 5): Promise<NwpForecastResponse> {
  const query = location.trim();
  if (!query) throw new WeatherApiError('Enter a city or coordinates for NWP model output.');
  const params = new URLSearchParams({ days: String(days) });
  const coordinates = query.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
  if (coordinates) { params.set('lat', coordinates[1]); params.set('lon', coordinates[2]); }
  else params.set('city', query);
  const response = await apiFetch(`/api/v1/weather/nwp?${params}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'NWP model data is unavailable.'), response.status);
  const body = await response.json() as NwpForecastResponse;
  if (!body || !['available', 'partial', 'unavailable', 'error'].includes(body.status) || !Array.isArray(body.points)) {
    throw new WeatherApiError('The NWP provider returned an invalid response.');
  }
  return body;
}

export interface RainfallPrediction {
  label: string;
  location: { latitude: number; longitude: number };
  selected_grid_point: { latitude: number; longitude: number; distance_km: number };
  dataset?: string;
  grid_resolution_degrees?: number;
  source?: string;
  prediction_date: string;
  rain_probability: number;
  rain_expected: boolean;
  predicted_rainfall_mm: number;
  model: string;
  training_period: { start: string; end: string };
}

export async function getRainfallPrediction(latitude: number, longitude: number, horizon = 1): Promise<RainfallPrediction> {
  const params = new URLSearchParams({ lat: String(latitude), lon: String(longitude), horizon: String(horizon) });
  const response = await apiFetch(`/api/v1/weather/rainfall-prediction?${params}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'WeatherGPT rainfall prediction is currently unavailable.'), response.status);
  const body: unknown = await response.json().catch(() => ({}));
  if (!body || typeof body !== 'object' || !('rain_probability' in body) || !('selected_grid_point' in body)) throw new WeatherApiError('The rainfall prediction service returned an unexpected response.');
  return body as RainfallPrediction;
}

export interface HistoricalResponse {
  status: 'available' | 'partial' | 'unavailable' | 'insufficient_data' | 'no_data' | 'data_not_available'; availability_status?: string; metadata?: Record<string, string | number | null>; location: string; source?: string | null;
  retrieved_at?: string | null; period_start?: string | null; period_end?: string | null; reason?: string | null;
  records?: Array<Record<string, unknown>>; summary?: Record<string, number | null>; monthly?: Array<Record<string, string | number | null>>; yearly?: Array<Record<string, unknown>>; analysis?: { observations?: Record<string, string>; trends?: Record<string, Record<string, unknown>>; climatology?: Array<Record<string, unknown>>; comparisons?: Array<Record<string, unknown>> };
}

export async function getHistoricalWeather(city: string, start: string, end: string, latitude?: number, longitude?: number, compareYear?: number): Promise<HistoricalResponse> {
  const params = new URLSearchParams({ start_date: start, end_date: end });
  if (city.trim()) params.set('city', city.trim());
  if (latitude !== undefined && longitude !== undefined) { params.set('lat', String(latitude)); params.set('lon', String(longitude)); }
  if (compareYear !== undefined) params.set('compare_year', String(compareYear));
  const response = await apiFetch(`/api/v1/weather/history?${params}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'Unable to retrieve historical weather.'), response.status);
  const body = await response.json().catch(() => ({})) as HistoricalResponse & BackendError;
  if (!body || typeof body !== 'object' || typeof body.status !== 'string') throw new WeatherApiError('Historical service returned an unexpected response.');
  return body;
}

export async function getClimatology(month: number, latitude: number, longitude: number, variable?: 'rainfall' | 'tmax' | 'tmin'): Promise<{ status: string; kind: string; baseline: string; normals: Array<Record<string, unknown>> }> {
  const params = new URLSearchParams({ month: String(month), lat: String(latitude), lon: String(longitude) });
  if (variable) params.set('variable', variable);
  const response = await apiFetch(`/api/v1/weather/climatology?${params}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'Unable to retrieve IMD climatology.'));
  return response.json() as Promise<{ status: string; kind: string; baseline: string; normals: Array<Record<string, unknown>> }>;
}

interface BackendError {
  error?: string;
  detail?: string;
}

export class WeatherApiError extends Error {
  constructor(message: string, public readonly status?: number, public readonly reason?: string) {
    super(message);
    this.name = 'WeatherApiError';
  }
}

export async function getCurrentWeather(city: string): Promise<WeatherResponse> {
  const normalizedCity = city.trim();
  if (!normalizedCity) {
    throw new WeatherApiError('Enter a city to search.');
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const query = new URLSearchParams({ city: normalizedCity });
    const response = await apiFetch(`/api/v1/weather/current?${query}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });

    if (!response.ok) {
      let body: BackendError = {};
      try {
        body = (await response.json()) as BackendError;
      } catch {
        // Use the status-specific fallback when the backend did not return JSON.
      }
      if (response.status === 404 && body.detail === 'Not Found') {
        throw new WeatherApiError(await getApiErrorMessage(new Response(JSON.stringify(body), { status: response.status }), `Weather route not found for ${normalizedCity}.`), 404);
      }
      if (response.status === 404) {
        throw new WeatherApiError(`HTTP 404: Weather not found for ${normalizedCity}. Check the spelling and try again.`, 404);
      }
      if (response.status >= 500) {
        throw new WeatherApiError(await getApiErrorMessage(new Response(JSON.stringify(body), { status: response.status }), 'Weather data is temporarily unavailable.'), response.status);
      }
      throw new WeatherApiError(await getApiErrorMessage(new Response(JSON.stringify(body), { status: response.status }), 'We could not complete that weather search.'), response.status);
    }

    const data: unknown = await response.json();
    if (!isWeatherResponse(data)) {
      throw new WeatherApiError('The weather service returned an unexpected response. Please try again.');
    }
    return data;
  } catch (error) {
    if (error instanceof WeatherApiError) throw error;
    if (error instanceof ApiClientError) throw new WeatherApiError(error.message, error.status);
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new WeatherApiError('The request took too long. Please try again.');
    }
    throw new WeatherApiError(`Connection/CORS failure contacting ${API_BASE_URL}. Check the backend address and CORS allowlist.`);
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function getCurrentWeatherAtCoordinates(latitude: number, longitude: number): Promise<WeatherResponse> {
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
    throw new WeatherApiError('Coordinates must be within latitude -90 to 90 and longitude -180 to 180.');
  }
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const params = new URLSearchParams({ lat: String(latitude), lon: String(longitude) });
    const response = await apiFetch(`/api/v1/weather/current?${params}`, { headers: { Accept: 'application/json' }, signal: controller.signal });
    if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'Current weather is unavailable for these coordinates.'), response.status);
    const body: unknown = await response.json();
    if (!isWeatherResponse(body)) throw new WeatherApiError('The weather service returned an unexpected response.');
    return body;
  } catch (cause) {
    if (cause instanceof WeatherApiError) throw cause;
    if (cause instanceof ApiClientError) throw new WeatherApiError(cause.message, cause.status);
    if (cause instanceof DOMException && cause.name === 'AbortError') throw new WeatherApiError('The current weather request timed out.');
    throw new WeatherApiError(`Connection failure contacting ${API_BASE_URL}.`);
  } finally { window.clearTimeout(timeout); }
}

export async function getForecast(location: string | { latitude: number; longitude: number }): Promise<ForecastResponse> {
  const params = typeof location === 'string' ? new URLSearchParams({ city: location.trim() }) : new URLSearchParams({ lat: String(location.latitude), lon: String(location.longitude) });
  const label = typeof location === 'string' ? location.trim() : `${location.latitude},${location.longitude}`;
  const response = await apiFetch(`/api/v1/weather/forecast?${params}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new WeatherApiError(await getApiErrorMessage(response, `Forecast data for ${label} is temporarily unavailable.`), response.status);
  }
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object' || !Array.isArray((data as ForecastResponse).forecast)) throw new WeatherApiError('The forecast service returned an unexpected response.');
  return data as ForecastResponse;
}

export interface ResolvedLocation {
  query: string; city: string | null; district: string | null; state: string | null; country: string | null;
  latitude: number; longitude: number; timezone: string | null; source: string;
  resolution_method: 'provider_geocoding' | 'coordinates' | 'configured_reference'; status: 'resolved';
}

export async function resolveLocation(query: string): Promise<ResolvedLocation> {
  const response = await apiFetch(`/api/v1/location/resolve?${new URLSearchParams({ q: query.trim() })}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'Unable to resolve that location.'), response.status);
  return response.json() as Promise<ResolvedLocation>;
}

export async function getWeatherAlerts(city: string): Promise<WeatherAlertsResponse> {
  const normalized = city.trim();
  if (!normalized) throw new WeatherApiError('Enter a city to search.');
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await apiFetch(`/api/v1/weather/alerts?${new URLSearchParams({ city: normalized })}`, { headers: { Accept: 'application/json' }, signal: controller.signal });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({})) as { reason?: string };
      const reason = errorBody.reason;
      const message = reason === 'provider_authorization_required'
        ? 'IMD requires provider authorization before official warning information can be retrieved.'
        : reason === 'location_mapping_unresolved'
          ? 'No verified IMD district mapping is configured for this location.'
          : await getApiErrorMessage(new Response(JSON.stringify(errorBody), { status: response.status }), 'Unable to retrieve official weather warnings.');
      throw new WeatherApiError(message, response.status, reason);
    }
    const body = await response.json().catch(() => ({}));
    if (!body || typeof body !== 'object' || !Array.isArray((body as WeatherAlertsResponse).forecast_days)) throw new WeatherApiError('The IMD warning service returned an unexpected response.');
    return body as WeatherAlertsResponse;
  } catch (error) {
    if (error instanceof WeatherApiError) throw error;
    if (error instanceof ApiClientError) throw new WeatherApiError(error.message, error.status);
    if (error instanceof DOMException && error.name === 'AbortError') throw new WeatherApiError('The IMD warning request took too long. Please try again.');
    throw new WeatherApiError(`Connection/CORS failure contacting ${API_BASE_URL}. Check the backend address and CORS allowlist.`);
  } finally { window.clearTimeout(timeout); }
}

export async function getWeatherAdvisory(city: string, dayOffset: number, activity: AdvisoryActivity): Promise<WeatherAdvisory> {
  const normalized = city.trim();
  if (!normalized) throw new WeatherApiError('Enter a city to search.');
  const query = new URLSearchParams({ city: normalized, day_offset: String(dayOffset), activity });
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await apiFetch(`/api/v1/weather/advisory?${query}`, { headers: { Accept: 'application/json' }, signal: controller.signal });
    if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'Unable to generate a weather advisory.'), response.status);
    const data: unknown = await response.json();
    if (!data || typeof data !== 'object' || typeof (data as WeatherAdvisory).summary !== 'string' || !Array.isArray((data as WeatherAdvisory).recommendations)) throw new WeatherApiError('The advisory service returned an unexpected response.');
    return data as WeatherAdvisory;
  } catch (error) {
    if (error instanceof WeatherApiError) throw error;
    if (error instanceof ApiClientError) throw new WeatherApiError(error.message, error.status);
    if (error instanceof DOMException && error.name === 'AbortError') throw new WeatherApiError('The advisory request took too long. Please try again.');
    throw new WeatherApiError(`Connection/CORS failure contacting ${API_BASE_URL}. Check the backend address and CORS allowlist.`);
  } finally { window.clearTimeout(timeout); }
}

export type FarmActivity = 'irrigation' | 'sowing' | 'spraying' | 'harvesting' | 'field_operations' | 'heat_stress' | 'heavy_rain' | 'wind_risk' | 'general';
export interface StationObservationView {
  station_id: string; station_name: string; district: string | null; state: string | null; latitude: number; longitude: number;
  elevation_m: number | null; observed_at: string; source: string; dataset: string; temperature_c: number | null;
  temp_max_c: number | null; temp_min_c: number | null; wet_bulb_c: number | null; dew_point_c: number | null;
  relative_humidity_pct: number | null; pressure_hpa: number | null; sea_level_pressure_hpa?: number | null;
  wind_speed_kmh: number | null; wind_direction: string | null; rainfall_mm: number | null; quality_flags: string[];
  invalid_values: Record<string, string>;
}
export interface AgricultureAdvice {
  status: 'available' | 'partial' | 'unavailable' | 'insufficient_data';
  location: ResolvedLocation | { query: string; status: string };
  station: { metadata: Record<string, unknown>; distance_km: number; retrieval_mode: string; data_status: string; latest_daily_observation: StationObservationView | null; latest_synoptic_observation: StationObservationView | null; quality_flags: Record<string, string[]>; quality_summary: Record<string, Record<string, unknown>> } | null;
  current_weather: WeatherResponse | null;
  forecast_context: { source: string; periods: ForecastResponse['forecast']; forecasted_at: string } | null;
  nwp_context: NwpForecastResponse | null;
  historical_context: Record<string, unknown> | null;
  climatology_context: Record<string, unknown> | null;
  official_warning: Record<string, unknown> | null;
  recommendation: { activity: FarmActivity; condition: string; recommendation: string; evidence: Array<{ label: string; value: number | string; unit?: string | null; source: string; valid_time?: string | null; detail?: string | null }>; sources: string[]; valid_period: string | null; confidence: string; limitations: string[] };
  data_quality: Record<string, unknown>;
  limitations: string[];
}

export interface AgricultureAdviceRequest {
  city?: string; latitude?: number; longitude?: number; activity: FarmActivity; crop?: string; growth_stage?: string;
  irrigation_available?: boolean; soil_type?: string;
}

export async function getAgricultureAdvice(request: AgricultureAdviceRequest): Promise<AgricultureAdvice> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS * 3);
  try {
    const response = await apiFetch('/api/v1/agriculture/advice', {
      method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(request), signal: controller.signal,
    });
    if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'Weather-based agriculture guidance is unavailable.'), response.status);
    const body: unknown = await response.json();
    if (!body || typeof body !== 'object' || !('recommendation' in body) || !('data_quality' in body)) throw new WeatherApiError('Agriculture service returned an unexpected response.');
    return body as AgricultureAdvice;
  } catch (error) {
    if (error instanceof WeatherApiError) throw error;
    if (error instanceof ApiClientError) throw new WeatherApiError(error.message, error.status);
    if (error instanceof DOMException && error.name === 'AbortError') throw new WeatherApiError('Agriculture analysis took too long. Please retry.');
    throw new WeatherApiError(`Connection/CORS failure contacting ${API_BASE_URL}. Check the backend address and CORS allowlist.`);
  } finally { window.clearTimeout(timeout); }
}

function isWeatherResponse(value: unknown): value is WeatherResponse {
  if (!value || typeof value !== 'object') return false;
  const response = value as Partial<WeatherResponse>;
  return Boolean(
    response.location && typeof response.location.name === 'string' &&
    typeof response.location.country === 'string' &&
    response.weather && typeof response.weather.temperature === 'number' &&
    typeof response.weather.humidity === 'number' &&
    typeof response.weather.description === 'string' &&
    typeof response.source === 'string' && typeof response.observed_at === 'string',
  );
}
