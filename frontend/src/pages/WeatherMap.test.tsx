import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../test/setup';
import WeatherMap from './WeatherMap';
import { getCurrentWeatherAtCoordinates, getForecast, getNwpForecast, getWeatherAdvisory, getWeatherAlerts, resolveLocation, WeatherApiError } from '../services/weatherApi';
import type { NwpForecastResponse, ResolvedLocation } from '../services/weatherApi';
import type { WeatherResponse } from '../types/weather';

vi.mock('../components/map/WeatherMapCanvas', () => ({
  default: ({ onMapSelect }: { onMapSelect: (latitude: number, longitude: number) => void }) => <div role="region" aria-label="Interactive geographic weather map"><button type="button" onClick={() => onMapSelect(35.6762, 139.6503)}>Select map test point</button></div>,
}));
vi.mock('../services/weatherApi', async (importOriginal) => ({
  ...await importOriginal<typeof import('../services/weatherApi')>(),
  getCurrentWeatherAtCoordinates: vi.fn(), getForecast: vi.fn(), getNwpForecast: vi.fn(),
  getWeatherAdvisory: vi.fn(), getWeatherAlerts: vi.fn(), resolveLocation: vi.fn(),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const nashik: ResolvedLocation = { query: 'Nashik', city: 'Nashik', district: null, state: 'Maharashtra', country: 'IN', latitude: 20.0112475, longitude: 73.7902364, timezone: null, source: 'OpenWeatherMap Geocoding API', resolution_method: 'provider_geocoding', status: 'resolved' };
const current: WeatherResponse = { location: { name: 'Nashik', country: 'IN', latitude: 20.0112475, longitude: 73.7902364 }, weather: { temperature: 29, feels_like: 30, temp_min: 27, temp_max: 30, humidity: 55, pressure: 1008, wind_speed: 2.4, wind_direction: null, wind_gust: null, visibility: null, cloudiness: 20, description: 'clear sky', icon: null }, sun: { sunrise: '2026-09-30T00:00:00Z', sunset: '2026-09-30T12:00:00Z' }, source: 'OpenWeatherMap', observed_at: '2026-09-30T08:00:00Z' };
const nwp: NwpForecastResponse = { status: 'available', location: { city: 'Nashik', latitude: 20.0112475, longitude: 73.7902364 }, source: 'NOAA/NCEP NOMADS', model: 'GFS 0.25 degree', initialization_time: '2026-09-30T00:00:00Z', retrieved_at: '2026-09-30T08:00:00Z', forecast_start: '2026-09-30T06:00:00Z', forecast_end: '2026-09-30T12:00:00Z', resolution_degrees: 0.25, units: { temperature: '°C', precipitation_since_initialization: 'mm', wind_speed: 'm/s' }, provenance: 'NOAA/NCEP GFS via NOMADS', source_url: 'https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl', selected_grid_point: { latitude: 20, longitude: 73.75, distance_km: 4.386 }, points: [{ forecast_time: '2026-09-30T06:00:00Z', lead_hours: 6, temperature_c: 28, precipitation_since_initialization_mm: 1.25, wind_speed_ms: 3.2 }, { forecast_time: '2026-09-30T12:00:00Z', lead_hours: 12, temperature_c: 30, precipitation_since_initialization_mm: 2, wind_speed_ms: 4 }], forecast: [], missing_leads: [] };

describe('Weather Map page', () => {
  it('renders the interactive map region, city search, coordinates and available layer controls', () => {
    render(<WeatherMap/>);
    expect(screen.getByRole('region', { name: 'Interactive geographic weather map' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Search a city' })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Latitude' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /NWP \/ GFS/ })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Official IMD warnings/ })).toBeInTheDocument();
  });

  it('resolves a city, requests current data and displays source and observed values', async () => {
    vi.mocked(resolveLocation).mockResolvedValue(nashik);
    vi.mocked(getCurrentWeatherAtCoordinates).mockResolvedValue(current);
    const user = userEvent.setup(); render(<WeatherMap/>);
    await user.type(screen.getByRole('textbox', { name: 'Search a city' }), 'Nashik');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText(/29\.0 °C/)).toBeInTheDocument();
    expect(screen.getByText(/clear sky/)).toBeInTheDocument();
    expect(screen.getByText(/OpenWeatherMap Geocoding API/)).toBeInTheDocument();
    expect(screen.getByText(/Observed/)).toBeInTheDocument();
    expect(getCurrentWeatherAtCoordinates).toHaveBeenCalledWith(nashik.latitude, nashik.longitude);
  });

  it('selects a map coordinate and exposes it as the active location', async () => {
    vi.mocked(getCurrentWeatherAtCoordinates).mockResolvedValue(current);
    const user = userEvent.setup(); render(<WeatherMap/>);
    await user.click(screen.getByRole('button', { name: 'Select map test point' }));
    expect(await screen.findByText('35.67620, 139.65030', { exact: true })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Latitude' })).toHaveValue('35.67620');
    expect(getCurrentWeatherAtCoordinates).toHaveBeenCalledWith(35.6762, 139.6503);
  });

  it('shows the real API model point, grid metadata and valid-time selector', async () => {
    vi.mocked(resolveLocation).mockResolvedValue(nashik);
    vi.mocked(getCurrentWeatherAtCoordinates).mockResolvedValue(current);
    vi.mocked(getNwpForecast).mockResolvedValue(nwp);
    const user = userEvent.setup(); render(<WeatherMap/>);
    await user.type(screen.getByRole('textbox', { name: 'Search a city' }), 'Nashik');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    await user.click(screen.getByRole('checkbox', { name: /NWP \/ GFS/ }));
    expect(await screen.findByText(/NOAA\/NCEP NOMADS/)).toBeInTheDocument();
    expect(screen.getByText(/20\.000, 73\.750 \(4\.39 km\)/)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'GFS forecast valid time' })).toHaveValue(nwp.points[0].forecast_time);
    expect(getNwpForecast).toHaveBeenCalledWith(`${nashik.latitude},${nashik.longitude}`, 2);
  });

  it('shows unavailable and provider-error states without inventing values', async () => {
    vi.mocked(resolveLocation).mockResolvedValue(nashik);
    vi.mocked(getCurrentWeatherAtCoordinates).mockRejectedValue(new WeatherApiError('Current weather provider unavailable', 503));
    const user = userEvent.setup(); render(<WeatherMap/>);
    await user.type(screen.getByRole('textbox', { name: 'Search a city' }), 'Nashik');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Current Weather provider error/);
    expect(screen.queryByText(/29\.0 °C/)).not.toBeInTheDocument();
    expect(getForecast).not.toHaveBeenCalled();
    expect(getWeatherAlerts).not.toHaveBeenCalled();
    expect(getWeatherAdvisory).not.toHaveBeenCalled();
  });
});
