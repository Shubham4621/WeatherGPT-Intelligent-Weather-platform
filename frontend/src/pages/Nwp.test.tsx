import { afterEach, describe, expect, it, vi } from 'vitest';
import '../../src/test/setup';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { NwpPage } from './PlatformPages';
import { getNwpForecast, WeatherApiError, type NwpForecastResponse } from '../services/weatherApi';

vi.mock('../services/weatherApi', async (importOriginal) => ({
  ...await importOriginal<typeof import('../services/weatherApi')>(),
  getNwpForecast: vi.fn(),
}));

afterEach(() => { cleanup(); vi.resetAllMocks(); });

const response: NwpForecastResponse = {
  status: 'available', location: { city: 'Nashik' }, source: 'NOAA/NCEP NOMADS', model: 'GFS 0.25 degree',
  initialization_time: '2026-09-29T00:00:00Z', retrieved_at: '2026-09-29T01:00:00Z',
  forecast_start: '2026-09-29T06:00:00Z', forecast_end: '2026-09-29T06:00:00Z', resolution_degrees: 0.25,
  units: { temperature: '°C' }, provenance: 'NOAA/NCEP GFS operational GRIB2 guidance', source_url: 'https://nomads.ncep.noaa.gov',
  selected_grid_point: { latitude: 20, longitude: 74, distance_km: 2 },
  points: [{ forecast_time: '2026-09-29T06:00:00Z', lead_hours: 6, temperature_c: 24 }], forecast: [], missing_leads: [],
};

describe('NWP page', () => {
  it('shows loading and retrieved model provenance/valid time', async () => {
    let finish!: (value: NwpForecastResponse) => void;
    vi.mocked(getNwpForecast).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    render(<NwpPage/>);
    fireEvent.click(screen.getByRole('button', { name: /get gfs model output/i }));
    expect(screen.getByRole('button')).toHaveTextContent(/loading nwp/i);
    finish(response);
    expect(await screen.findByText(/NOAA\/NCEP NOMADS/)).toBeInTheDocument();
    expect(screen.getByText('24.0 °C')).toBeInTheDocument();
    expect(screen.getByText(/model run \(UTC\)/i)).toBeInTheDocument();
  });

  it('shows explicit provider unavailable state', async () => {
    vi.mocked(getNwpForecast).mockResolvedValue({ ...response, status: 'unavailable', reason: 'grib_decoder_unavailable', points: [] });
    render(<NwpPage/>);
    fireEvent.click(screen.getByRole('button', { name: /get gfs model output/i }));
    expect(await screen.findByRole('status')).toHaveTextContent('grib_decoder_unavailable');
  });

  it('shows a provider error without displaying model values', async () => {
    vi.mocked(getNwpForecast).mockRejectedValue(new WeatherApiError('NWP provider timed out.'));
    render(<NwpPage/>);
    fireEvent.click(screen.getByRole('button', { name: /get gfs model output/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('NWP provider error: NWP provider timed out.');
    expect(screen.queryByText('24.0 °C')).not.toBeInTheDocument();
  });
});
