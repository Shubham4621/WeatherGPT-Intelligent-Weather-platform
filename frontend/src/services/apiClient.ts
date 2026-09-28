const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const API_BASE_URL = (configuredBaseUrl || 'http://127.0.0.1:8000').replace(/\/+$/, '');

export class ApiClientError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = 'ApiClientError';
  }
}

/** Shared transport so every WeatherGPT feature uses the same backend origin. */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiClientError(
      `Connection/CORS failure contacting ${API_BASE_URL}. Check that the WeatherGPT backend is running at this address and allows this frontend origin.`,
    );
  }
}

/** Read FastAPI and provider errors without masking the HTTP status or detail. */
export async function getApiErrorMessage(response: Response, fallback: string): Promise<string> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  const message = extractMessage(body);
  if (response.status === 404 && (!message || /^not found\.?$/i.test(message))) {
    return `HTTP 404: no WeatherGPT route exists at ${API_BASE_URL}. Check the backend application and API version.`;
  }
  return `HTTP ${response.status}: ${message || fallback}`;
}

function extractMessage(body: unknown): string | undefined {
  if (!body || typeof body !== 'object') return undefined;
  const record = body as Record<string, unknown>;
  for (const key of ['detail', 'message', 'error']) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
    if (Array.isArray(value)) {
      const details = value.map((item) => {
        if (!item || typeof item !== 'object') return '';
        const detail = (item as Record<string, unknown>).msg;
        return typeof detail === 'string' ? detail : '';
      }).filter(Boolean);
      if (details.length) return details.join('; ');
    }
  }
  return undefined;
}
