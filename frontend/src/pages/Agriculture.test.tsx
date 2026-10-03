import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Agriculture from './Agriculture';
import { LanguageContext } from '../i18n';
import '../test/setup';

vi.mock('../components/map/WeatherMapCanvas', () => ({ default: ({ location, station }: { location: { city?: string } | null; station: { station_id: string } | null }) => <div role="region" aria-label="Test map">{location?.city ?? 'No selected city'} {station?.station_id ?? ''}</div> }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const advice = {
  status: 'partial',
  location: { query: 'Nashik', city: 'Nashik', district: 'Nashik', state: 'Maharashtra', country: 'IN', latitude: 20.0112475, longitude: 73.7902364, timezone: null, source: 'OpenWeatherMap Geocoding API', resolution_method: 'provider_geocoding', status: 'resolved' },
  station: { metadata: { station_id: '42921', station_name: 'Nashik', district: 'Nashik', state: 'Maharashtra', latitude: 20.0333333, longitude: 73.7833333, coordinate_precision: "20°02'N, 73°47'E as supplied", elevation_m: 598.76, source: 'IMD Data Service Portal' }, distance_km: 2.56, retrieval_mode: 'validated local IMD DSP dataset; not a live DSP session', data_status: 'stale', latest_daily_observation: { station_id: '42921', station_name: 'Nashik', district: 'Nashik', state: 'Maharashtra', latitude: 20.0333, longitude: 73.7833, elevation_m: 598.76, observed_at: '2025-12-31T03:00:00Z', source: 'IMD Data Service Portal', dataset: 'SURFACE_TABLE_2_DAY_SUMMARY', temperature_c: null, temp_max_c: 28, temp_min_c: 13, wet_bulb_c: null, dew_point_c: null, relative_humidity_pct: null, pressure_hpa: null, wind_speed_kmh: null, wind_direction: null, rainfall_mm: 0, quality_flags: [], invalid_values: {} }, latest_synoptic_observation: null, quality_flags: {}, quality_summary: { daily: { row_count: 6212, normalized_row_count: 6212, coverage_start: '2007-01-05', coverage_end: '2025-12-31', duplicate_records: 0, missing_dates_or_slots_between_coverage: 724, invalid_date_or_station_rows: 0 }, synoptic: { row_count: 52011, normalized_row_count: 52011, coverage_start: '2000-06-09T12:00:00Z', coverage_end: '2025-12-31T21:00:00Z', duplicate_records: 0, missing_dates_or_slots_between_coverage: 22681, invalid_date_or_station_rows: 0 } } },
  current_weather: { location: { name: 'Nashik', country: 'IN', latitude: 20.01, longitude: 73.79 }, weather: { temperature: 29, feels_like: 29, temp_min: 28, temp_max: 30, humidity: 45, pressure: 1000, wind_speed: 2, wind_direction: null, wind_gust: null, visibility: null, cloudiness: 10, description: 'clear', icon: null }, sun: { sunrise: '2026-09-30T00:00:00Z', sunset: '2026-09-30T12:00:00Z' }, source: 'OpenWeatherMap', observed_at: '2026-09-30T00:00:00Z' },
  forecast_context: { source: 'OpenWeatherMap', forecasted_at: '2026-09-30T00:00:00Z', periods: [{ date: '2026-10-01T00:00:00Z', temperature_min: 20, temperature_max: 34, feels_like: null, humidity: 50, description: 'clouds', cloudiness: 30, wind_speed: 3, rain_probability: 60 }] },
  nwp_context: null, historical_context: { status: 'unavailable', source: null, record_count: 0 }, climatology_context: { status: 'available', baseline: '1991-2020', normal_monthly_rainfall_mm: 112, source: 'India Meteorological Department (IMD)' },
  official_warning: { status: 'location_mapping_unresolved', source: 'India Meteorological Department (IMD)' },
  recommendation: { activity: 'spraying', condition: 'unfavorable_weather_signal', recommendation: 'Rain potential, strong wind, or high temperature appears in the available data; consider postponing and follow product-label and local safety guidance.', evidence: [{ label: 'Maximum operational forecast precipitation probability', value: 60, unit: '%', source: 'OpenWeatherMap', valid_time: '2026-10-01T00:00:00Z' }], sources: ['OpenWeatherMap'], valid_period: 'Forecast valid period supplied by APIs.', confidence: 'moderate', limitations: ['WeatherGPT weather-based decision support only; not an official agricultural department instruction.', 'No soil-moisture observation was available.'] },
  data_quality: { current_weather: 'available', operational_forecast: 'available', nwp: 'unavailable', station: 'stale', historical: 'unavailable', climatology: 'available', official_warning: 'location_mapping_unresolved' },
  limitations: ['WeatherGPT weather-based decision support only; not an official agricultural department instruction.', 'No soil-moisture observation was available.'],
};

describe('WeatherGPT agriculture page', () => {
  it('submits a selected activity and displays station metadata, advice, evidence and provenance', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(advice), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup(); render(<Agriculture/>);
    await user.selectOptions(screen.getByRole('combobox', { name: 'Farm activity' }), 'spraying');
    await user.click(screen.getByRole('button', { name: 'Get weather-based guidance' }));
    expect(await screen.findByText(/consider postponing/)).toBeInTheDocument();
    expect(screen.getByText(/Station ID: 42921/)).toBeInTheDocument();
    expect(screen.getByText(/20°02'N, 73°47'E/)).toBeInTheDocument();
    expect(screen.getByText(/IMD Data Service Portal/)).toBeInTheDocument();
    expect(screen.getByText(/not an official agricultural department advisory/i)).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Test map' })).toHaveTextContent('Nashik 42921');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({ city: 'Nashik', activity: 'spraying' });
  });

  it('shows loading and unavailable states without invented advice', async () => {
    let finish!: (response: Response) => void;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    const user = userEvent.setup(); render(<Agriculture/>);
    await user.click(screen.getByRole('button', { name: 'Get weather-based guidance' }));
    expect(screen.getByRole('status')).toHaveTextContent(/Resolving location/);
    finish(new Response(JSON.stringify({ error: 'provider unavailable' }), { status: 503 }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/provider unavailable/i);
    expect(screen.queryByText(/Rain potential, strong wind/)).not.toBeInTheDocument();
  });

  it('supports coordinate input from the shared map and localizes core agriculture controls', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(advice), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup(); render(<LanguageContext.Provider value={{ language: 'hi', setLanguage: () => undefined }}><Agriculture/></LanguageContext.Provider>);
    await user.click(screen.getByRole('checkbox', { name: 'शहर के बजाय निर्देशांक उपयोग करें' }));
    const coordinateInputs = screen.getAllByRole('spinbutton');
    await user.type(coordinateInputs[0], '20.01');
    await user.type(coordinateInputs[1], '73.79');
    await user.click(screen.getByRole('button')); 
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toMatchObject({ latitude: 20.01, longitude: 73.79 });
  });
});
