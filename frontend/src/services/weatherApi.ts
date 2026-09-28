import type { AdvisoryActivity, ForecastResponse, WeatherAdvisory, WeatherResponse, WeatherAlertsResponse } from '../types/weather';
import { API_BASE_URL, apiFetch, getApiErrorMessage, ApiClientError } from './apiClient';
const REQUEST_TIMEOUT_MS = 12_000;

export interface RainfallPrediction {
  label: string;
  location: { latitude: number; longitude: number };
  selected_grid_point: { latitude: number; longitude: number; distance_km: number };
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
  status: 'available' | 'partial' | 'unavailable' | 'no_data' | 'data_not_available'; availability_status?: 'DATA_AVAILABLE' | 'DATA_NOT_AVAILABLE' | 'NO_WEATHER_DATA' | 'NO_HISTORICAL_DATA_CONFIGURED' | 'DATA_INVALID'; metadata?: Record<string, string | number | null>; location: string; source?: string | null;
  retrieved_at?: string | null; period_start?: string | null; period_end?: string | null; reason?: string | null;
  records?: Array<Record<string, unknown>>; summary?: Record<string, number | null>;
}

export async function getHistoricalWeather(city: string, start: string, end: string): Promise<HistoricalResponse> {
  const params = new URLSearchParams({ city: city.trim(), start_date: start, end_date: end });
  const response = await apiFetch(`/api/v1/weather/history?${params}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new WeatherApiError(await getApiErrorMessage(response, 'Unable to retrieve historical weather.'), response.status);
  const body = await response.json().catch(() => ({})) as HistoricalResponse & BackendError;
  if (!body || typeof body !== 'object' || typeof body.status !== 'string') throw new WeatherApiError('Historical service returned an unexpected response.');
  return body;
}

interface BackendError {
  error?: string;
  detail?: string;
}

export class WeatherApiError extends Error {
  constructor(message: string, public readonly status?: number) {
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

export async function getForecast(city: string): Promise<ForecastResponse> {
  const response = await apiFetch(`/api/v1/weather/forecast?${new URLSearchParams({ city: city.trim() })}`, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    throw new WeatherApiError(await getApiErrorMessage(response, `Forecast data for ${city.trim()} is temporarily unavailable.`), response.status);
  }
  const data: unknown = await response.json();
  if (!data || typeof data !== 'object' || !Array.isArray((data as ForecastResponse).forecast)) throw new WeatherApiError('The forecast service returned an unexpected response.');
  return data as ForecastResponse;
}

export async function getWeatherAlerts(city: string): Promise<WeatherAlertsResponse> {
  const normalized = city.trim();
  if (!normalized) throw new WeatherApiError('Enter a city to search.');
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await apiFetch(`/api/v1/weather/alerts?${new URLSearchParams({ city: normalized })}`, { headers: { Accept: 'application/json' }, signal: controller.signal });
    if (!response.ok) {
      throw new WeatherApiError(await getApiErrorMessage(response, 'Unable to retrieve official weather warnings.'), response.status);
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
