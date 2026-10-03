import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ClimateAnalysis from './ClimateAnalysis';
import App from '../App';
import '../test/setup';
import { LanguageContext, type Language } from '../i18n';
import { getClimatology, getHistoricalWeather, resolveLocation } from '../services/weatherApi';

vi.mock('../services/weatherApi', () => ({
  getClimatology: vi.fn(), getHistoricalWeather: vi.fn(), resolveLocation: vi.fn(),
  WeatherApiError: class WeatherApiError extends Error {},
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const location = { query: 'Dhule', city: 'Dhule', district: null, state: 'Maharashtra', country: 'IN', latitude: 20.9, longitude: 74.8, timezone: null, source: 'OpenWeatherMap Geocoding API', resolution_method: 'provider_geocoding' as const, status: 'resolved' as const };
const history = {
  status: 'available' as const, location: 'Dhule', source: 'India Meteorological Department (IMD Pune)', period_start: '2024-07-01', period_end: '2024-07-31',
  metadata: { dataset: 'IMD daily rainfall 0.25-degree', grid_resolution: 0.25, latitude: 21, longitude: 74.75, distance_km: 14.2, missing_rainfall: 0 },
  summary: { record_count: 31, rainfall_observations: 31, temperature_observations: 0, total_rainfall: 92.4 },
  monthly: [{ year: 2024, month: 'July', month_number: 7, total_rainfall: 92.4, rainfall_observation_count: 31, expected_day_count: 31 }],
  yearly: [{ year: 2024, total_rainfall: 92.4, rainfall_observation_count: 31, expected_day_count: 366 }],
  analysis: { observations: { rainfall: 'OBSERVATION', temperature: 'unavailable' }, trends: { rainfall_mm_per_year: { status: 'available', slope_per_year: 12.5, observations: 8, coverage_years: 8, period_start: 2013, period_end: 2020, method: 'ordinary least squares descriptive slope; no significance test' } }, comparisons: [{ kind: 'ANOMALY', year: 2024, month: 7, observed_rainfall_mm: 92.4, normal_rainfall_mm: 110, anomaly_rainfall_mm: -17.6, anomaly_percent: -16, status: 'available' }] },
};
function normals(month: number) { return { status: 'available', kind: 'CLIMATOLOGY', baseline: '1991-2020', normals: [
  { status: 'available', variable: 'rainfall', normal: month === 7 ? 110 : 20, units: 'mm', baseline: '1991-2020', source: 'India Meteorological Department (IMD)', resolution_degrees: .25 },
  { status: 'available', variable: 'tmax', normal: 33, units: '°C', baseline: '1991-2020', source: 'India Meteorological Department (IMD)', resolution_degrees: .5 },
  { status: 'available', variable: 'tmin', normal: 24, units: '°C', baseline: '1991-2020', source: 'India Meteorological Department (IMD)', resolution_degrees: .5 },
] }; }
function renderPage(language: Language = 'en') { return render(<LanguageContext.Provider value={{ language, setLanguage: () => undefined }}><ClimateAnalysis /></LanguageContext.Provider>); }
async function loadPage() {
  vi.mocked(resolveLocation).mockResolvedValue(location);
  vi.mocked(getHistoricalWeather).mockResolvedValue(history);
  vi.mocked(getClimatology).mockImplementation(async month => normals(month));
  fireEvent.click(screen.getByRole('button', { name: /Load climate analysis|हवामान विश्लेषण दाखवा|जलवायु विश्लेषण दिखाएँ/ }));
}

describe('Climate Analysis page', () => {
  it('is reachable from the existing Climate Analysis route', async () => {
    const user = userEvent.setup(); render(<App />);
    await user.click(screen.getByRole('button', { name: 'Climate Analysis' }));
    expect(await screen.findByRole('heading', { name: 'Climate Analysis' })).toBeInTheDocument();
  });

  it('resolves a city and renders historical rainfall, climatology, anomaly, trend and provenance', async () => {
    renderPage(); await loadPage();
    expect((await screen.findAllByText('92.4')).length).toBeGreaterThan(0);
    expect(screen.getByText(/1991–2020/)).toBeInTheDocument();
    expect(screen.getByText(/-17.6/)).toBeInTheDocument();
    expect(screen.getByText(/12.5 mm\/year/)).toBeInTheDocument();
    expect(screen.getAllByText(/India Meteorological Department/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Historical daily temperature analysis is currently unavailable/)).toBeInTheDocument();
    expect(resolveLocation).toHaveBeenCalledWith('Dhule');
    expect(getHistoricalWeather).toHaveBeenCalledWith('Dhule', '2013-01-01', '2024-12-31', 20.9, 74.8, undefined);
    expect(getClimatology).toHaveBeenCalledTimes(12);
  });

  it('shows loading state while requests are pending', async () => {
    vi.mocked(resolveLocation).mockReturnValue(new Promise(() => undefined));
    renderPage(); fireEvent.click(screen.getByRole('button', { name: 'Load climate analysis' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Resolving location and loading climate data');
  });

  it('shows an out-of-coverage state and still displays climatology normals', async () => {
    vi.mocked(resolveLocation).mockResolvedValue(location);
    vi.mocked(getHistoricalWeather).mockResolvedValue({ status: 'no_data', location: 'Nashik', reason: 'No validated rainfall grid cell is available within 20 km.', records: [] });
    vi.mocked(getClimatology).mockImplementation(async month => normals(month));
    renderPage(); fireEvent.click(screen.getByRole('button', { name: 'Load climate analysis' }));
    expect(await screen.findByText('Climate data unavailable')).toBeInTheDocument();
    expect(screen.getByText('No validated rainfall grid cell is available within 20 km.')).toBeInTheDocument();
    expect(screen.getAllByText('33 · 0.5°').length).toBeGreaterThan(0);
  });

  it('supports coordinate selection and Hindi/Marathi labels', async () => {
    vi.mocked(getHistoricalWeather).mockResolvedValue({ status: 'insufficient_data', location: 'coordinate', reason: 'Insufficient data', records: [] });
    vi.mocked(getClimatology).mockImplementation(async month => normals(month));
    const { rerender } = renderPage('hi');
    expect(screen.getByText('जलवायु विश्लेषण')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('अक्षांश'), { target: { value: '20.9' } });
    fireEvent.change(screen.getByLabelText('देशांतर'), { target: { value: '74.8' } });
    fireEvent.click(screen.getByRole('button', { name: 'जलवायु विश्लेषण दिखाएँ' }));
    await waitFor(() => expect(getHistoricalWeather).toHaveBeenCalledWith('', '2013-01-01', '2024-12-31', 20.9, 74.8, undefined));
    expect(await screen.findByText('जलवायु डेटा अपर्याप्त')).toBeInTheDocument();
    rerender(<LanguageContext.Provider value={{ language: 'mr', setLanguage: () => undefined }}><ClimateAnalysis /></LanguageContext.Provider>);
    expect(screen.getByText('हवामान विश्लेषण')).toBeInTheDocument();
  });

  it('surfaces location/provider errors without inventing result data', async () => {
    vi.mocked(resolveLocation).mockRejectedValue(new Error('location_provider_unavailable'));
    renderPage(); fireEvent.click(screen.getByRole('button', { name: 'Load climate analysis' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('location_provider_unavailable');
    expect(screen.queryByText('Monthly rainfall analysis')).not.toBeInTheDocument();
  });
});
