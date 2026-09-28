import { afterEach, describe, expect, it, vi } from 'vitest';
import '../../src/test/setup';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Alerts, { AlertCard } from './Alerts';
import App from '../App';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const baseDay = { date: '2026-09-25T00:00:00Z', warnings: [{ warning_type: 'Heavy Rain', warning_code: 2 }, { warning_type: 'Hailstorm', warning_code: 5 }], warning_codes: [2, 5], severity: 'Orange', severity_code: 2, is_active: true };
const alertPayload = { location: 'Dhule', district: 'Dhule', state: 'Maharashtra', issued_at: '2026-09-24T10:30:00Z', forecast_days: [baseDay], source: 'India Meteorological Department (IMD)', source_url: 'https://mausam.imd.gov.in/api/warnings_district_api.php?id=9001' };

describe('Alerts page', () => {
  it('renders multiple official warnings, severity and source', () => {
    render(<><AlertCard day={baseDay} district="Dhule"/><p>{alertPayload.source}</p></>);
    expect(screen.getByText('Heavy Rain, Hailstorm')).toBeInTheDocument();
    expect(screen.getByText('IMD Level:')).toBeInTheDocument();
    expect(screen.getByLabelText('Severity Orange')).toBeInTheDocument();
    expect(screen.getByText('Meaning: Alert')).toBeInTheDocument();
    expect(screen.getByText(alertPayload.source)).toBeInTheDocument();
  });

  it('searches the API and renders official warning records', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(alertPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    render(<Alerts/>);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText('Heavy Rain, Hailstorm')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: alertPayload.source })).toHaveAttribute('href', alertPayload.source_url);
  });

  it('shows a clear no-warning state after a successful empty-warning response', async () => {
    const noWarning = { ...alertPayload, forecast_days: [{ ...baseDay, warnings: [], warning_codes: [1], severity: 'Green', severity_code: 4, is_active: false }] };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(noWarning), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    render(<Alerts/>);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText(/No official IMD weather warning is currently reported/)).toBeInTheDocument();
  });

  it('shows loading and provider error states', async () => {
    let finish!: (response: Response) => void;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    render(<Alerts/>);
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    expect(screen.getByRole('status')).toHaveTextContent('Loading alerts');
    finish(new Response(JSON.stringify({ error: 'WEATHER_ALERT_PROVIDER_UNAVAILABLE' }), { status: 503 }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Unable to retrieve official weather warnings/i);
  });

  it('supports city search and Alerts navigation', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(alertPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup(); render(<App/>);
    await user.click(screen.getByRole('button', { name: 'Alerts' }));
    expect(screen.getByRole('heading', { name: 'Weather Alerts' })).toBeInTheDocument();
    const input = screen.getByRole('textbox', { name: /search city/i });
    await user.clear(input); await user.type(input, 'Dhule');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    expect(await screen.findByText('Heavy Rain, Hailstorm')).toBeInTheDocument();
  });
});
