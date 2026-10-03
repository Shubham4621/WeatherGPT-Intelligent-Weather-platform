import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Historical from './Historical';
import { LanguageContext } from '../i18n';

describe('Historical page', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
  it('renders period selectors and controlled unavailable response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'unavailable', location: 'Dhule', reason: 'Historical weather provider is not configured' }) }));
    render(<LanguageContext.Provider value={{ language: 'en', setLanguage: () => undefined }}><Historical /></LanguageContext.Provider>);
    expect(Boolean(screen.getByLabelText('Location'))).toBe(true);
    expect(Boolean(screen.getByLabelText('Start date'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(Boolean(screen.getByText('Historical data unavailable'))).toBe(true));
    expect(Boolean(screen.getByText(/provider is not configured/))).toBe(true);
    vi.unstubAllGlobals();
  });

  it('explains when the configured IMD archive is not installed', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'data_not_available', availability_status: 'DATA_NOT_AVAILABLE', location: 'Dhule', source: 'India Meteorological Department (IMD Pune)', reason: 'No normalized file installed', metadata: { period: '1901–2024 rainfall; 1951–2024 temperature', resolution: '0.25° rainfall; 1° Tmax/Tmin' } }) }));
    render(<LanguageContext.Provider value={{ language: 'en', setLanguage: () => undefined }}><Historical /></LanguageContext.Provider>);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(screen.getByText('IMD historical data is not installed')).toBeTruthy());
    expect(screen.getByText('0.25° rainfall; 1° Tmax/Tmin')).toBeTruthy();
    vi.unstubAllGlobals();
  });

  it('shows provenance and missing-value validation for installed records', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'available', availability_status: 'DATA_AVAILABLE', location: 'Dhule', source: 'IMD Pune', period_start: '2024-01-01', period_end: '2024-01-01', retrieved_at: '2024-01-02T00:00:00Z', records: [{ date: '2024-01-01', rainfall: 0 }], summary: {}, metadata: { dataset: 'IMD normalized grids', grid_resolution: 0.25, validation_status: 'PASS', missing_rainfall: 0, missing_tmax: 1, missing_tmin: 1 } }) }));
    render(<LanguageContext.Provider value={{ language: 'en', setLanguage: () => undefined }}><Historical /></LanguageContext.Provider>);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(screen.getByText(/IMD normalized grids/)).toBeTruthy());
    expect(screen.getByText(/Tmax 1/)).toBeTruthy();
  });

  it('renders observed summaries, separate climatology normals, anomaly and descriptive trend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'available', location: 'Dhule', source: 'IMD Pune', period_start: '2024-07-01', period_end: '2024-07-31', retrieved_at: '2024-08-01T00:00:00Z', records: [], summary: { total_rainfall: 200 }, monthly: [], yearly: [{ year: 2024, total_rainfall: 200, wettest_month: 'July', driest_month: 'July' }], metadata: { dataset: 'Daily IMD rainfall', grid_resolution: 0.25, validation_status: 'PASS', missing_rainfall: 0, latitude: 21, longitude: 74.75 }, analysis: { trends: { rainfall_mm_per_year: { status: 'available', slope_per_year: 5, observations: 12, period_start: 2013, period_end: 2024 } }, climatology: [{ month: 7, rainfall: { normal: 182.3 }, tmax: { normal: 30.7 }, tmin: { normal: 22.9 } }], comparisons: [{ year: 2024, month: 7, observed_rainfall_mm: 200, normal_rainfall_mm: 182.3, anomaly_rainfall_mm: 17.7, anomaly_percent: 9.71 }] } }) }));
    render(<LanguageContext.Provider value={{ language: 'en', setLanguage: () => undefined }}><Historical /></LanguageContext.Provider>);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(screen.getByText('IMD climatology normals · 1991–2020')).toBeTruthy());
    expect(screen.getByText('Annual observed summaries')).toBeTruthy();
    expect(screen.getByText('Observed rainfall and anomaly')).toBeTruthy();
    expect(screen.getByText(/5 mm\/year/)).toBeTruthy();
  });
});
