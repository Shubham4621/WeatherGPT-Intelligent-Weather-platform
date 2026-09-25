import type { ChatResponse } from '../types/chat';
import type { Language } from '../i18n';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
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
    const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ message: normalizedMessage, language }),
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new ChatApiError("We couldn't find weather for that city. Check its spelling and try again.", 404);
      }
      if (response.status >= 500) {
        throw new ChatApiError("WeatherGPT couldn't get a reliable response just now. Please try again shortly.", response.status);
      }
      throw new ChatApiError('Please enter a supported weather question with a city name.', response.status);
    }

    const body: unknown = await response.json();
    if (!isChatResponse(body)) {
      throw new ChatApiError('WeatherGPT returned an unexpected response. Please try again.');
    }
    return body;
  } catch (error) {
    if (error instanceof ChatApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ChatApiError('WeatherGPT is taking longer than expected. Please try again.');
    }
    throw new ChatApiError('Unable to reach WeatherGPT. Check that the backend is running and try again.');
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
    && (response.intent === 'CURRENT_WEATHER' || response.intent === 'FORECAST' || response.intent === 'ALERT' || response.intent === 'ADVISORY' || response.intent === 'UNKNOWN')
    && (response.location === null || typeof response.location === 'string')
    && (response.source === null || typeof response.source === 'string')
    && (response.tool_used === null || typeof response.tool_used === 'string')
    && (response.observed_at === null || typeof response.observed_at === 'string')
    && weatherIsValid;
}
