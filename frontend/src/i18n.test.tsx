import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import App from './App';
import { readLanguage, t } from './i18n';
import { sendChatMessage } from './services/chatApi';

afterEach(() => { cleanup(); window.localStorage.clear(); vi.restoreAllMocks(); });

describe('multilingual preference', () => {
  it('defaults to English and persists a Marathi selection across app remounts', () => {
    render(<App />);
    expect(screen.getByRole('button', { name: 'Dashboard' })).toBeTruthy();
    const selector = screen.getByRole('combobox', { name: 'Language' });
    fireEvent.change(selector, { target: { value: 'mr' } });
    expect(screen.getByRole('button', { name: 'डॅशबोर्ड' })).toBeTruthy();
    expect(readLanguage()).toBe('mr');
    cleanup();
    render(<App />);
    expect((screen.getByRole('combobox', { name: 'Language' }) as HTMLSelectElement).value).toBe('mr');
  });

  it('has Hindi navigation copy and safe English fallbacks for untranslated strings', () => {
    expect(t('hi', 'Forecast')).toBe('पूर्वानुमान');
    expect(t('mr', 'Future feature not in dictionary')).toBe('Future feature not in dictionary');
  });

  it('sends the selected language alongside the original chat message', async () => {
    const fetchMock = vi.spyOn(window, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ message: 'उद्या पावसाची शक्यता: 70%', intent: 'FORECAST', location: 'Dhule', source: 'OpenWeatherMap', tool_used: 'get_forecast', observed_at: null, weather: null }),
    } as Response);
    await sendChatMessage('उद्या धुळ्यात पाऊस पडेल का?', 'mr');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ message: 'उद्या धुळ्यात पाऊस पडेल का?', language: 'mr' });
  });
});
