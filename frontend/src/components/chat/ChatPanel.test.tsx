import { afterEach, describe, expect, it, vi } from 'vitest';
import '../../test/setup';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../../App';
import type { RecognitionPort } from '../../services/speechRecognition';

const successfulChatResponse = {
  message: 'The current humidity in Dhule is 55%.',
  intent: 'CURRENT_WEATHER',
  location: 'Dhule',
  source: 'OpenWeatherMap',
  tool_used: 'get_current_weather',
  observed_at: '2026-09-24T08:00:00Z',
  weather: null,
};

async function openChat(user: ReturnType<typeof userEvent.setup>) {
  render(<App />);
  await user.click(screen.getByRole('button', { name: 'Chat' }));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('WeatherGPT chat UI', () => {
  it('renders chat from the existing dashboard navigation', async () => {
    const user = userEvent.setup();
    await openChat(user);
    expect(screen.getByRole('heading', { name: 'Ask WeatherGPT' })).toBeInTheDocument();
    expect(screen.getByText(/current weather assistant/i)).toBeInTheDocument();
  });

  it('accepts a user message and shows a typing state until the response arrives', async () => {
    const user = userEvent.setup();
    let resolveFetch!: (response: Response) => void;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise((resolve) => { resolveFetch = resolve; }));
    await openChat(user);
    const input = screen.getByRole('textbox', { name: /ask WeatherGPT/i });
    await user.type(input, 'What is the humidity in Dhule?{Enter}');
    expect(input).toHaveValue('');
    expect(screen.getByText('What is the humidity in Dhule?')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: /preparing a response/i })).toBeInTheDocument();
    resolveFetch(new Response(JSON.stringify(successfulChatResponse), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    expect(await screen.findByText('The current humidity in Dhule is 55%.')).toBeInTheDocument();
    expect(screen.getByText(/Source: OpenWeatherMap/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('status', { name: /preparing a response/i })).not.toBeInTheDocument());
  });

  it('shows a friendly error without exposing internal details', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('socket internal stack detail'));
    await openChat(user);
    await user.type(screen.getByRole('textbox', { name: /ask WeatherGPT/i }), 'Weather in Dhule');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Connection\/CORS failure contacting .*allows this frontend origin/i);
    expect(screen.queryByText(/internal stack detail/i)).not.toBeInTheDocument();
  });

  it('sends a suggested question when selected', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(successfulChatResponse), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await openChat(user);
    await user.click(screen.getByRole('button', { name: "What's the weather today in Dhule?" }));
    await screen.findByText('The current humidity in Dhule is 55%.');
    expect(JSON.parse(String(fetchSpy.mock.calls[0][1]?.body))).toEqual({ message: "What's the weather today in Dhule?", language: 'en' });
  });

  it('renders a grounded forecast response from the mocked chat API', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ message: 'Tomorrow in Dhule, rain probability is approximately 20%.', intent: 'FORECAST', location: 'Dhule', source: 'OpenWeatherMap', tool_used: 'get_forecast', observed_at: null, weather: null, forecast: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    await openChat(user);
    await user.type(screen.getByRole('textbox', { name: /ask WeatherGPT/i }), 'Will it rain tomorrow in Dhule?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText('Tomorrow in Dhule, rain probability is approximately 20%.')).toBeInTheDocument();
  });

  it('renders structured forecast details without inventing missing probability data', async () => {
    const forecastResponse = { message: 'Forecast details for Dhule.', intent: 'FORECAST', location: 'Dhule', source: 'OpenWeatherMap', tool_used: 'get_forecast', observed_at: null, weather: null, forecast: [{ date: '2026-09-25T00:00:00Z', temperature_min: 22, temperature_max: 30, feels_like: null, humidity: null, description: 'light rain', cloudiness: null, wind_speed: 2.4, rain_probability: null }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(forecastResponse), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup(); await openChat(user);
    await user.type(screen.getByRole('textbox', { name: /ask WeatherGPT/i }), 'Forecast Dhule');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByRole('region', { name: 'Forecast response cards' })).toBeInTheDocument();
    expect(screen.getByText('Wind 2.4 m/s')).toBeInTheDocument();
    expect(screen.queryByText(/Rain \d+%/)).not.toBeInTheDocument();
  });

  it('renders official attribution for a mocked alert chat response', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ message: 'Official IMD Weather Warning: Heavy Rain. WeatherGPT advisory: Check official updates.', intent: 'ALERT', location: 'Dhule', source: 'India Meteorological Department (IMD)', tool_used: 'get_weather_alerts', observed_at: null, weather: null, forecast: null, alert_days: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    await openChat(user);
    await user.type(screen.getByRole('textbox', { name: /ask WeatherGPT/i }), 'Is there a weather warning in Dhule?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText(/Official IMD Weather Warning: Heavy Rain/)).toBeInTheDocument();
    expect(screen.getByText('Official IMD information')).toBeInTheDocument();
  });

  it('renders an advisory response as WeatherGPT guidance', async () => {
    const user = userEvent.setup();
    const advisory = { location: 'Dhule', date: '2026-09-26T00:00:00Z', activity: 'TRAVEL', summary: 'Rain may affect your plans.', risk_level: 'MODERATE', risk_label: 'WeatherGPT advisory classification', factors: [], recommendations: ['Carry rain protection.'], official_warning: null, official_warning_status: 'unavailable', sources: ['OpenWeatherMap', 'India Meteorological Department (IMD) — unavailable', 'WeatherGPT'] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ message: 'WeatherGPT Advisory: Rain may affect your plans.', intent: 'ADVISORY', location: 'Dhule', source: 'WeatherGPT', tool_used: 'get_weather_advisory', observed_at: null, weather: null, advisory }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    await openChat(user);
    await user.type(screen.getByRole('textbox', { name: /ask WeatherGPT/i }), 'Should I travel tomorrow in Dhule?');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText(/WeatherGPT Advisory: Rain may affect your plans/)).toBeInTheDocument();
    expect(screen.getByText('WeatherGPT advisory')).toBeInTheDocument();
  });

  it('puts a reviewed voice transcript in the normal input and sends one existing chat request', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(successfulChatResponse), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    let activeRecognition!: MockRecognition;
    class MockRecognition {
      lang = ''; interimResults = false; continuous = false;
      onstart: (() => void) | null = null;
      onresult: RecognitionPort['onresult'] = null;
      onerror: RecognitionPort['onerror'] = null;
      onend: (() => void) | null = null;
      constructor() { activeRecognition = this; }
      start() { this.onstart?.(); }
      stop() { this.onend?.(); }
      abort() {}
    }
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: MockRecognition });
    await openChat(user);
    await user.click(screen.getByRole('button', { name: 'Start voice input' }));
    // The fake browser recognition instance is the latest instance created by the microphone control.
    const results = Object.assign([{ transcript: 'What is the humidity in Dhule?' }], { isFinal: true });
    activeRecognition.onresult?.({ resultIndex: 0, results: [results] });
    activeRecognition.onend?.();
    const input = screen.getByRole('textbox', { name: /ask WeatherGPT/i });
    await waitFor(() => expect(input).toHaveValue('What is the humidity in Dhule?'));
    await user.click(screen.getByRole('button', { name: 'Discard voice transcript' }));
    expect(input).toHaveValue('');
    await user.click(screen.getByRole('button', { name: 'Start voice input' }));
    activeRecognition.onresult?.({ resultIndex: 0, results: [results] });
    activeRecognition.onend?.();
    await waitFor(() => expect(input).toHaveValue('What is the humidity in Dhule?'));
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText(successfulChatResponse.message)).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String(fetchSpy.mock.calls[0][1]?.body)).message).toBe('What is the humidity in Dhule?');
  });
});
