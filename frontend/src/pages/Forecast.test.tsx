import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Forecast, { ForecastCard } from './Forecast';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const payload = { location: { name: 'Dhule', country: 'IN', latitude: 20.9, longitude: 74.78 }, source: 'OpenWeatherMap', forecasted_at: '2026-09-24T10:00:00Z', forecast: [{ date: '2026-09-25T00:00:00Z', temperature_min: 24, temperature_max: 31, feels_like: 30, humidity: 65, description: 'scattered clouds', cloudiness: 40, wind_speed: 5.2, rain_probability: 20 }] };

describe('Forecast page', () => {
  it('renders a daily card and normalized forecast values', () => {
    render(<ForecastCard date={payload.forecast[0].date} low={24} high={31} description="scattered clouds" humidity={65} wind={5.2} rain={20} />);
    expect(screen.getByText('scattered clouds')).toBeTruthy();
    expect(screen.getByText(/31°/)).toBeTruthy();
    expect(screen.getByText('Rain probability 20%')).toBeTruthy();
  });

  it('loads and renders forecast data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    render(<Forecast />);
    fireEvent.click(screen.getByRole('button', { name: 'Get forecast' }));
    expect(await screen.findByText('Dhule, IN')).toBeTruthy();
    expect(screen.getByText('Humidity 65%')).toBeTruthy();
    expect(screen.getByText(/Temperature trend/)).toBeTruthy();
  });

  it('shows loading state while the API request is pending', async () => {
    let finish!: (value: unknown) => void;
    vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => { finish = resolve; })));
    render(<Forecast />);
    fireEvent.click(screen.getByRole('button', { name: 'Get forecast' }));
    expect(screen.getByRole('status').textContent).toContain('Loading forecast');
    finish({ ok: true, json: async () => payload });
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
  });

  it('shows a controlled API error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({ error: 'Location not found' }) }));
    render(<Forecast />);
    fireEvent.click(screen.getByRole('button', { name: 'Get forecast' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByRole('alert').textContent).toContain('couldn\'t find weather');
  });
});
