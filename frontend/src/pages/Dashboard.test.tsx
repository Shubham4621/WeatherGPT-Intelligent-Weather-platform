import { afterEach, describe, expect, it, vi } from 'vitest';
import '../test/setup';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Dashboard from './Dashboard';

const sampleWeather = {
  location: { name: 'Dhule', country: 'IN', latitude: 20.9, longitude: 74.78 },
  weather: {
    temperature: 31.5, feels_like: 33.2, temp_min: 29, temp_max: 33,
    humidity: 58, pressure: 1008, wind_speed: 3.4, wind_direction: 240,
    wind_gust: 5.1, visibility: 10000, cloudiness: 20,
    description: 'scattered clouds', icon: null,
  },
  sun: { sunrise: '2026-09-24T00:00:00Z', sunset: '2026-09-24T12:00:00Z' },
  source: 'OpenWeatherMap',
  observed_at: '2026-09-24T08:00:00Z',
};

function renderDashboard() {
  return render(<Dashboard onOpenChat={vi.fn()} />);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('WeatherGPT dashboard', () => {
  it('renders the dashboard without making an automatic request', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderDashboard();
    expect(screen.getByRole('heading', { name: /weather, made clearer/i })).toBeInTheDocument();
    expect(screen.getByRole('searchbox', { name: /search weather by city/i })).toHaveValue('Dhule');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('shows loading and then renders a successful normalized response', async () => {
    const user = userEvent.setup();
    let resolveFetch!: (value: Response) => void;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise((resolve) => { resolveFetch = resolve; }));
    renderDashboard();

    await user.click(screen.getByRole('button', { name: /search/i }));
    expect(screen.getByRole('status')).toHaveTextContent(/checking conditions/i);
    expect(screen.getByRole('button', { name: /searching/i })).toBeDisabled();
    resolveFetch(new Response(JSON.stringify(sampleWeather), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    expect(await screen.findByRole('heading', { name: /Dhule/ })).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.tagName === 'P' && element.textContent === '32°')).toBeInTheDocument();
    expect(screen.getByText('58')).toBeInTheDocument();
    expect(screen.getByText(/Source: OpenWeatherMap/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  });

  it('shows a friendly backend error and does not display internal details', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('socket ECONNREFUSED internal stack'));
    renderDashboard();
    await user.click(screen.getByRole('button', { name: /search/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/unable to reach WeatherGPT/i);
    expect(screen.queryByText(/ECONNREFUSED|internal stack/i)).not.toBeInTheDocument();
  });

  it('rejects empty input accessibly without making a request', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderDashboard();
    const input = screen.getByRole('searchbox');
    await user.clear(input);
    expect(screen.getByRole('button', { name: /search/i })).toBeDisabled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('shows an official alert banner only after receiving active IMD warning data', async () => {
    const user = userEvent.setup();
    const active = { location: 'Dhule', district: 'Dhule', state: 'Maharashtra', issued_at: '2026-09-24T10:00:00Z', forecast_days: [{ date: '2026-09-25T00:00:00Z', warnings: [{ warning_type: 'Heavy Rain', warning_code: 2 }], warning_codes: [2], severity: 'Orange', severity_code: 2, is_active: true }], source: 'India Meteorological Department (IMD)', source_url: 'https://mausam.imd.gov.in/' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify(sampleWeather), { status: 200, headers: { 'Content-Type': 'application/json' } })).mockResolvedValueOnce(new Response(JSON.stringify(active), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const openAlerts = vi.fn();
    render(<Dashboard onOpenChat={vi.fn()} onOpenAlerts={openAlerts}/>);
    await user.click(screen.getByRole('button', { name: /search/i }));
    const banner = await screen.findByRole('button', { name: /IMD Weather Alert.*Heavy Rain/s });
    await user.click(banner);
    expect(openAlerts).toHaveBeenCalledOnce();
  });
});
