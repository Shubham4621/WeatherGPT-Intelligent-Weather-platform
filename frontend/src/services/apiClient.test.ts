import { afterEach, describe, expect, it, vi } from 'vitest';
import { API_BASE_URL, apiFetch, getApiErrorMessage } from './apiClient';

afterEach(() => vi.unstubAllGlobals());

describe('shared backend API client', () => {
  it('uses the single configured backend base URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await apiFetch('/api/v1/weather/forecast?city=Dhule');

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/api/v1/weather/forecast?city=Dhule`, undefined);
  });

  it('classifies browser fetch rejection as a connection or CORS issue', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('opaque browser network failure')));

    await expect(apiFetch('/api/v1/chat')).rejects.toThrow(/Connection\/CORS failure contacting .*Check that the WeatherGPT backend/);
  });

  it('identifies an HTTP 404 from the wrong backend or API route', async () => {
    const response = new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 });

    await expect(getApiErrorMessage(response, 'Fallback')).resolves.toMatch(/HTTP 404: no WeatherGPT route exists/);
  });

  it('preserves HTTP provider errors and their status', async () => {
    const response = new Response(JSON.stringify({ error: 'Weather API key is not configured.' }), { status: 503 });

    await expect(getApiErrorMessage(response, 'Fallback')).resolves.toBe('HTTP 503: Weather API key is not configured.');
  });
});
