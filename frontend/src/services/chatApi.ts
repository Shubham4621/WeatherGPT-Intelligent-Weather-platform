import type { ChatResponse } from '../types/chat';
import { t, type Language } from '../i18n';
import { API_BASE_URL, apiFetch, getApiErrorMessage, ApiClientError } from './apiClient';
const REQUEST_TIMEOUT_MS = 60_000;

export class ChatApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = 'ChatApiError';
  }
}

export function localizeChatApiError(message: string, language: Language): string {
  if (language === 'en') return message;
  const value = message.toLowerCase();
  const key = value.includes('several locations match') || value.includes('location_ambiguous')
    ? 'Several locations match. Add a state or country to narrow the search.'
    : value.includes('no matching location') || value.includes('location_not_found')
      ? 'No matching location was found.'
      : value.includes('timed out') || value.includes('taking longer')
        ? 'WeatherGPT is taking longer than expected. Please try again.'
        : value.includes('location provider') || value.includes('geocod')
          ? 'Location provider is unavailable.'
          : value.includes('weather assistant') || value.includes('llm_service')
            ? 'Weather assistant is temporarily unavailable. Please try again later.'
            : value.includes('weather provider') || value.includes('weather service') || value.includes('provider_error')
              ? 'The weather service is temporarily unavailable. Please try again later.'
              : value.includes('unexpected response')
                ? 'WeatherGPT returned an unexpected response. Please try again.'
                : 'WeatherGPT could not process that request. Please try again.';
  return t(language, key);
}

export async function sendChatMessage(message: string, language: Language = 'en'): Promise<ChatResponse> {
  const normalizedMessage = message.trim();
  if (!normalizedMessage) throw new ChatApiError(t(language, 'Type a weather question to get started.'));

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
      const message = await getApiErrorMessage(response, 'WeatherGPT could not process that request.');
      throw new ChatApiError(localizeChatApiError(message, language), response.status);
    }

    const body: unknown = await response.json();
    if (!isChatResponse(body)) {
      throw new ChatApiError(t(language, 'WeatherGPT returned an unexpected response. Please try again.'));
    }
    return body;
  } catch (error) {
    if (error instanceof ChatApiError) throw error;
    if (error instanceof ApiClientError) throw new ChatApiError(localizeChatApiError(error.message, language), error.status);
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ChatApiError(t(language, 'WeatherGPT is taking longer than expected. Please try again.'));
    }
    throw new ChatApiError(localizeChatApiError(`Connection/CORS failure contacting ${API_BASE_URL}.`, language));
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
    && (response.intent === 'CURRENT_WEATHER' || response.intent === 'FORECAST' || response.intent === 'ALERT' || response.intent === 'ADVISORY' || response.intent === 'HISTORICAL_WEATHER' || response.intent === 'NWP' || response.intent === 'AGRICULTURE' || response.intent === 'UNKNOWN')
    && (response.location === null || typeof response.location === 'string')
    && (response.source === null || typeof response.source === 'string')
    && (response.tool_used === null || typeof response.tool_used === 'string')
    && (response.observed_at === null || typeof response.observed_at === 'string')
    && weatherIsValid;
}
