import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '../test/setup';
import App from '../App';

vi.mock('../components/map/WeatherMapCanvas', () => ({
  default: () => <div role="region" aria-label="Interactive geographic weather map"/>,
}));

afterEach(() => { cleanup(); vi.restoreAllMocks(); document.documentElement.classList.remove('dark'); window.localStorage.clear(); });

describe('WeatherGPT extended workspace sections', () => {
  it('renders the interactive map workspace and real data layer controls', async () => {
    const user = userEvent.setup(); render(<App/>);
    await user.click(screen.getByRole('button', { name: 'Weather Map' }));
    expect(screen.getByRole('heading', { name: 'Weather Map' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Interactive geographic weather map' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Current Weather/ })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /NWP \/ GFS/ })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Official IMD warnings/ })).toBeInTheDocument();
  });

  it('calls the existing one-day model API with generic coordinates and renders its labelled result', async () => {
    const payload = { label: 'WeatherGPT model prediction', location: { latitude: 20.9, longitude: 74.8 }, selected_grid_point: { latitude: 21, longitude: 74.75, distance_km: 12.4 }, prediction_date: '2026-09-28', rain_probability: 0.42, rain_expected: false, predicted_rainfall_mm: 0.8, model: 'RandomForest', training_period: { start: '2013-01-15', end: '2020-12-31' } };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup(); render(<App/>);
    await user.click(screen.getByRole('button', { name: 'Rainfall Prediction' }));
    await user.click(screen.getByRole('button', { name: 'Get 1-day prediction' }));
    expect(await screen.findByRole('heading', { name: 'WeatherGPT model prediction' })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(String(fetchMock.mock.calls[0][0])).toContain('/api/v1/weather/rainfall-prediction?lat=20.9&lon=74.8&horizon=1');
    expect(screen.getByText(/not an official IMD warning or forecast/i)).toBeInTheDocument();
  });

  it('does not display prediction values when the existing model API is unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Historical rainfall prediction model or validated data is unavailable.' }), { status: 503, headers: { 'Content-Type': 'application/json' } }));
    const user = userEvent.setup(); render(<App/>);
    await user.click(screen.getByRole('button', { name: 'Rainfall Prediction' }));
    await user.click(screen.getByRole('button', { name: 'Get 1-day prediction' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Prediction unavailable.');
    expect(screen.queryByText(/Rain probability/)).not.toBeInTheDocument();
  });

  it('persists a single shared light/dark appearance preference', async () => {
    const user = userEvent.setup(); render(<App/>);
    await user.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(document.documentElement).toHaveClass('dark');
    expect(window.localStorage.getItem('weathergpt-theme')).toBe('dark');
    await user.click(screen.getByRole('button', { name: 'Switch to light theme' }));
    expect(document.documentElement).not.toHaveClass('dark');
    expect(window.localStorage.getItem('weathergpt-theme')).toBe('light');
  });

  it('supports a persisted desktop sidebar collapse control', async () => {
    const user = userEvent.setup(); render(<App/>);
    await user.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    expect(window.localStorage.getItem('weathergpt-sidebar-collapsed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeInTheDocument();
  });
});
