import { afterEach, describe, expect, it, vi } from 'vitest';
import '../../src/test/setup';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Advisory, { AdvisoryResult } from './Advisory';
import App from '../App';
import type { WeatherAdvisory } from '../types/weather';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const result: WeatherAdvisory = { location: 'Dhule', date: '2026-09-26T00:00:00Z', activity: 'TRAVEL', summary: 'Rain is likely based on the provider forecast.', risk_level: 'HIGH', risk_label: 'WeatherGPT advisory classification', factors: [{ code: 'PRECIPITATION_CHANCE', detail: 'High precipitation probability (80%)', source: 'OpenWeatherMap' }, { code: 'OFFICIAL_IMD_WARNING', detail: 'IMD reports: Heavy Rain; IMD level Orange', source: 'India Meteorological Department (IMD)' }], recommendations: ['Carry rain protection.', 'Allow extra travel time.'], official_warning: { warnings: ['Heavy Rain'], severity: 'Orange', date: '2026-09-26T00:00:00Z', source: 'India Meteorological Department (IMD)', source_url: 'https://mausam.imd.gov.in/warnings' }, official_warning_status: 'available', sources: ['OpenWeatherMap', 'India Meteorological Department (IMD)', 'WeatherGPT'] };

describe('WeatherGPT advisory', () => {
  it('renders risk, factors, recommendations, official warning and source distinction', () => {
    render(<AdvisoryResult data={result}/>);
    expect(screen.getByText(/WeatherGPT Advisory/)).toBeInTheDocument();
    expect(screen.getByText('Official IMD Information')).toBeInTheDocument();
    expect(screen.getByText('IMD Level: Orange')).toBeInTheDocument();
    expect(screen.getByText(/classification: HIGH/)).toBeInTheDocument();
    expect(screen.getByText('Allow extra travel time.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: result.official_warning!.source })).toHaveAttribute('href', result.official_warning!.source_url);
  });

  it('sends location, date and activity selection and renders response', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup(); render(<Advisory/>);
    await user.clear(screen.getByRole('textbox', { name: 'Location' })); await user.type(screen.getByRole('textbox', { name: 'Location' }), 'Dhule');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Date' }), '2');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Activity' }), 'TRAVEL');
    await user.click(screen.getByRole('button', { name: 'Get Advisory' }));
    expect(await screen.findByText('Allow extra travel time.')).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain('day_offset=2');
    expect(String(fetchMock.mock.calls[0][0])).toContain('activity=TRAVEL');
    expect(String(fetchMock.mock.calls[0][0])).toContain('city=Dhule');
  });

  it('keeps IMD unavailability distinct from a no-alert result', () => {
    const unavailable = { ...result, official_warning: null, official_warning_status: 'unavailable', factors: result.factors.filter((f) => f.code !== 'OFFICIAL_IMD_WARNING').concat([{ code: 'IMD_STATUS_UNAVAILABLE', detail: 'Official IMD warning information could not be retrieved.', source: 'India Meteorological Department (IMD)' }]) };
    render(<AdvisoryResult data={unavailable}/>);
    expect(screen.getByRole('status')).toHaveTextContent(/not confirmation that no warning exists/i);
    expect(screen.queryByText(/No official IMD warning was reported/)).not.toBeInTheDocument();
  });

  it('shows a no-alert statement only when IMD successfully reports none', () => {
    render(<AdvisoryResult data={{ ...result, official_warning: null, official_warning_status: 'none_reported' }}/>);
    expect(screen.getByText(/No official IMD warning was reported for this date/)).toBeInTheDocument();
  });

  it('shows loading and error states and is reachable through navigation', async () => {
    let finish!: (response: Response) => void;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    const user = userEvent.setup(); render(<App/>);
    await user.click(screen.getByRole('button', { name: 'Advisory' }));
    expect(screen.getByRole('heading', { name: 'Weather Advisory' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Get Advisory' }));
    expect(screen.getByRole('status')).toHaveTextContent(/Generating advisory/);
    finish(new Response(JSON.stringify({ error: 'failure' }), { status: 503 }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/HTTP 503: failure/);
  });
});
