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
});
