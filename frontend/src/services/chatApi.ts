import type { ChatResponse } from '../types/chat';
import type { Language } from '../i18n';
import { API_BASE_URL, apiFetch, getApiErrorMessage, ApiClientError } from './apiClient';
const REQUEST_TIMEOUT_MS = 60_000;

export class ChatApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = 'ChatApiError';
  }
}

export async function sendChatMessage(message: string, language: Language = 'en'): Promise<ChatResponse> {
  const normalizedMessage = message.trim();
  if (!normalizedMessage) throw new ChatApiError('Type a weather question to get started.');

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await apiFetch('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ message: normalizedMessage, language }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ChatApiError(await getApiErrorMessage(response, 'WeatherGPT could not process that request.'), response.status);
    }

    const body: unknown = await response.json();
    if (!isChatResponse(body)) {
      throw new ChatApiError('WeatherGPT returned an unexpected response. Please try again.');
    }
    return body;
  } catch (error) {
    if (error instanceof ChatApiError) throw error;
    if (error instanceof ApiClientError) throw new ChatApiError(error.message, error.status);
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ChatApiError('WeatherGPT is taking longer than expected. Please try again.');
    }
    throw new ChatApiError(`Connection/CORS failure contacting ${API_BASE_URL}. Check the backend address and CORS allowlist.`);
  } finally {
    window.clearTimeout(timeout);
  }
}

function isChatResponse(value: unknown): value is ChatResponse {
  if (!value || typeof value !== 'object') return false;
  const response = value as Partial<ChatResponse>;
  const weather = response.weather;
  const weatherIsValid = weather === null || Boolean(
    weather && typeof weather === 'object'
      && typeof weather.temperature === 'number'
      && typeof weather.feels_like === 'number'
      && typeof weather.humidity === 'number'
      && typeof weather.pressure === 'number'
      && typeof weather.wind_speed === 'number'
      && typeof weather.description === 'string',
  );
  return typeof response.message === 'string'
    && (response.intent === 'CURRENT_WEATHER' || response.intent === 'FORECAST' || response.intent === 'ALERT' || response.intent === 'ADVISORY' || response.intent === 'HISTORICAL_WEATHER' || response.intent === 'UNKNOWN')
    && (response.location === null || typeof response.location === 'string')
    && (response.source === null || typeof response.source === 'string')
    && (response.tool_used === null || typeof response.tool_used === 'string')
    && (response.observed_at === null || typeof response.observed_at === 'string')
    && weatherIsValid;
}
